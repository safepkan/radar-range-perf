"""Chamber captures: the TX and RX channels, the eight-TX beam and the calibration.

For one run of our host tool's calibration routine (chamber_common: CASES):

1. Each TX's return from the DDMA case (chamber_common.per_tx_amplitudes): its
   power at the reflector relative to TX1, against the report's Table 2, and
   the part of it the finite reflector's geometry predicts (each TX's
   finite-aperture factor as mean power over the eight RX, chamber_common.
   pair_power_db); the TX and RX phases of a rank-one fit, against the
   calibration the routine recorded from these CPIs.
2. The eight-TX beam: its gain over TX1's line in DDMA and over TX1 alone,
   against the gain the DDMA amplitudes predict with the phases that were
   applied, and against the largest possible (all eight in phase).
3. Stability: the reflector's level and phase per CPI in each case.
4. Calibration records compared as received RF phases (see the conventions in
   chamber_common): this run's against every other record in
   chamber_common.CALIBRATION_RECORDS, and the RX against the report's
   Figure 2 at 77.0 GHz. Each difference is fitted as a plane-wave change of
   the reflector's direction (chamber_common.plane_wave_fit): the RX array is
   horizontal and gives azimuth only, the TX positions span both axes.
5. Channel delays: the payload in eight sub-bands of 112.5 MHz, the received
   RF phase per TX and per RX from the DDMA case against RF frequency
   (chamber_common.delay_fit), and the phase slopes against the report's
   Figures 1 and 2 over 76.5-77.5 GHz, the part of its range this sweep covers.
6. The second static return beyond the reflector, at about twice its range.

Writes summary.json and channels.png to --output (default
generated/chamber/channels).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from carkit_common import SPEED_OF_LIGHT, ComplexArray, FloatArray, db, write_summary
from chamber_common import (
    CALIBRATION_RECORDS,
    CASES,
    COHERENT_CASE,
    DDMA_CASE,
    DOUBLE_BOUNCE_SEARCH,
    GENERATED_DIR,
    REFLECTOR_EDGE_M,
    REPORT_FREQUENCIES_HZ,
    REPORT_RX_CORRECTION_DEG,
    REPORT_TX_CORRECTION_DEG,
    REPORT_TX_POWER_DB,
    SINGLE_CASE,
    TX_POSITION_M,
    band_centres_hz,
    data_argument,
    delay_fit,
    gradient_to_angle_deg,
    load,
    pair_power_db,
    per_tx_amplitudes,
    plane_wave_fit,
    reflector_beat,
    reflector_gains,
    rx_positions_m,
    sidecar,
    tx_phase_steps_deg,
    wrap_deg,
)
from field_common import RX_X_M, static_power_profile
from window_common import Capture

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SUB_BANDS = 8
# The report's frequencies within this sweep's 76.55-77.45 GHz, for its slopes.
REPORT_SLOPE_BAND_HZ = (76.45e9, 77.55e9)
REPORT_INDEX_77_GHZ = 2
# The report's calibration reflector: "about 22 decimetres" (its section 1.1).
REPORT_RANGE_M = 2.2
RECORD_0930 = "2026-09-30T08:14:19Z"


def rank_one(amplitudes: ComplexArray) -> tuple[ComplexArray, ComplexArray, float]:
    """TX and RX factors of a [TX, RX] matrix and the rank-one power share."""
    u, s, vh = np.linalg.svd(amplitudes)
    return u[:, 0] * s[0], vh[0], float(s[0] ** 2 / np.sum(s**2))


def rf_phase_deg(factors: ComplexArray) -> FloatArray:
    """Received RF phase relative to the first channel: minus the range bin's."""
    return np.asarray(-np.degrees(np.angle(factors / factors[..., :1])))


def plane_wave_summary(
    difference: FloatArray, positions: FloatArray, wavelength_m: float, kind: str
) -> dict[str, Any]:
    gradient, residual = plane_wave_fit(difference, positions)
    out: dict[str, Any] = {
        f"{kind}_difference_deg": difference.tolist(),
        f"{kind}_azimuth_change_deg": gradient_to_angle_deg(
            float(gradient[0]), wavelength_m
        ),
        f"{kind}_residual_deg": residual.tolist(),
        f"{kind}_residual_rms_deg": float(np.sqrt(np.mean(residual**2))),
    }
    if gradient.size > 1:
        out[f"{kind}_elevation_change_deg"] = gradient_to_angle_deg(
            float(gradient[1]), wavelength_m
        )
    return out


def calibration_difference(
    tx_a: FloatArray,
    rx_a: FloatArray,
    tx_b: FloatArray,
    rx_b: FloatArray,
    wavelength_m: float,
) -> dict[str, Any]:
    """Record b minus record a as received RF phases, with plane-wave fits."""
    return {
        **plane_wave_summary(
            wrap_deg(rx_b - rx_a), RX_X_M[:, None], wavelength_m, "rx"
        ),
        **plane_wave_summary(
            wrap_deg(-(tx_b - tx_a)), TX_POSITION_M, wavelength_m, "tx"
        ),
    }


def report_slopes(corrections: FloatArray) -> FloatArray:
    """The report's phase slopes [deg/GHz] over REPORT_SLOPE_BAND_HZ."""
    inside = (REPORT_FREQUENCIES_HZ >= REPORT_SLOPE_BAND_HZ[0]) & (
        REPORT_FREQUENCIES_HZ <= REPORT_SLOPE_BAND_HZ[1]
    )
    return np.array(
        [
            np.polyfit(REPORT_FREQUENCIES_HZ[inside] / 1e9, c[inside], 1)[0]
            for c in corrections
        ]
    )


def finite_tx_pattern_db(range_m: float, wavelength_m: float) -> FloatArray:
    """Each TX's finite-aperture factor, mean power over RX, relative to TX1."""
    pairs = pair_power_db(
        REFLECTOR_EDGE_M, range_m, TX_POSITION_M, rx_positions_m(), wavelength_m
    )
    per_tx = db(np.mean(10 ** (pairs / 10), axis=1))
    return np.asarray(per_tx - per_tx[0])


def stability(gains: ComplexArray) -> dict[str, Any]:
    """Per-CPI level [dB] and common phase [deg] of zero-Doppler amplitudes."""
    zero = gains.mean(axis=1)  # [frame, RX]
    level = db(np.mean(np.abs(zero) ** 2, axis=1))
    phase = np.degrees(np.angle(np.sum(zero * zero.mean(axis=0).conj(), axis=1)))
    return {
        "level_db_counts2": level.tolist(),
        "level_std_db": float(level.std()),
        "phase_deg": (phase - phase.mean()).tolist(),
        "phase_span_deg": float(np.ptp(phase)),
    }


def double_bounce(capture: Capture, reflector_m: float) -> dict[str, float]:
    profile = static_power_profile(capture, 16)
    range_m = capture.range_axis(16)
    inside = (range_m >= DOUBLE_BOUNCE_SEARCH[0] * reflector_m) & (
        range_m <= DOUBLE_BOUNCE_SEARCH[1] * reflector_m
    )
    k = int(np.flatnonzero(inside)[np.argmax(profile[inside])])
    reflector = int(np.argmin(np.abs(range_m - reflector_m)))
    return {
        "range_m": float(range_m[k]),
        "twice_reflector_range_m": 2 * reflector_m,
        "level_relative_to_reflector_db": float(db(profile[k] / profile[reflector])),
    }


def plot(output: Path, summary: dict[str, Any], label: str) -> None:
    figure, (left, middle, right) = plt.subplots(
        1, 3, figsize=(17, 5.2), layout="constrained"
    )
    tx = np.arange(1, 9)
    ddma = summary["ddma"]
    left.plot(tx, ddma["tx_power_relative_to_tx1_db"], "o-", color="C0", label=label)
    left.plot(
        tx,
        REPORT_TX_POWER_DB,
        "s--",
        color="C1",
        mfc="none",
        label="Report, Table 2 (Infineon's firmware, 20 dB backoff)",
    )
    left.plot(
        tx,
        ddma["finite_reflector_tx_pattern_db"],
        "k:",
        lw=1.2,
        label="Finite reflector alone (geometry, this range)",
    )
    left.set(
        xlabel="TX",
        ylabel="Power at the reflector relative to TX1 [dB]",
        title="TX powers from DDMA",
        xticks=tx,
    )
    left.grid(alpha=0.3)
    left.legend(fontsize=8)

    delays = summary["delays"]
    names = [f"TX{k}" for k in range(2, 9)] + [f"RX{k}" for k in range(2, 9)]
    position = np.arange(len(names))
    mine = np.concatenate(
        [
            delays["tx_phase_slope_deg_per_ghz"][1:],
            delays["rx_phase_slope_deg_per_ghz"][1:],
        ]
    )
    theirs = np.concatenate(
        [
            delays["report_tx_phase_slope_deg_per_ghz"][1:],
            delays["report_rx_phase_slope_deg_per_ghz"][1:],
        ]
    )
    middle.plot(
        position, mine, "o", color="C0", label="Chamber: sub-bands of one 900 MHz chirp"
    )
    middle.plot(
        position,
        theirs,
        "s",
        color="C1",
        mfc="none",
        ms=8,
        label="Report: calibrations at 76.5-77.5 GHz",
    )
    middle.axhline(0, color="k", lw=0.6)
    middle.axvline(6.5, color="k", lw=0.6, ls=":")
    middle.set(
        xticks=position,
        ylabel="Slope of the received RF phase [deg/GHz]",
        title="Phase against RF frequency, relative to TX1 / RX1",
    )
    middle.set_xticklabels(names, fontsize=8)
    middle.grid(alpha=0.3)
    middle.legend(fontsize=8)

    x_mm = RX_X_M * 1e3
    order = np.argsort(x_mm)
    comparisons = summary["calibration"]
    shown = [
        (key, f"{key[:10]} {key[11:16]} minus this run")
        for key in comparisons
        if key in CALIBRATION_RECORDS
    ] + [("report_77ghz_minus_2026-09-30", "Report at 77.0 GHz minus 2026-09-30")]
    for (key, text), colour in zip(shown, ("C0", "C2", "C3", "C1")):
        values = comparisons[key]
        difference = np.array(values["rx_difference_deg"])
        fit = difference - np.array(values["rx_residual_deg"])
        right.plot(
            x_mm,
            difference,
            "o",
            color=colour,
            label=f"{text}: azimuth {values['rx_azimuth_change_deg']:+.2f} deg, "
            f"residual {values['rx_residual_rms_deg']:.1f} deg rms",
        )
        right.plot(x_mm[order], fit[order], "-", color=colour, lw=0.8)
    for k, x in enumerate(x_mm, start=1):
        right.annotate(
            f"RX{k}", (x, 0), textcoords="offset points", xytext=(-8, 6), fontsize=7
        )
    right.axhline(0, color="k", lw=0.6)
    right.set(
        xlabel="RX position across the antenna [mm]",
        ylabel="RX calibration difference, received RF phase [deg]",
        title="RX calibration between sessions and firmwares",
    )
    right.grid(alpha=0.3)
    right.legend(fontsize=7, loc="lower left")
    figure.savefig(output / "channels.png", dpi=110)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "channels")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    captures = {case: load(case, args.data, verify=True) for case in CASES}
    beats = {case: reflector_beat(capture) for case, capture in captures.items()}
    ranges = {
        case: float(beat * SPEED_OF_LIGHT / (2 * captures[case].slope_hz_per_s))
        for case, beat in beats.items()
    }
    gains = {
        case: reflector_gains(capture, beats[case])[0]
        for case, capture in captures.items()
    }
    ddma = captures[DDMA_CASE]
    bands = reflector_gains(ddma, beats[DDMA_CASE], SUB_BANDS)
    steps = tx_phase_steps_deg(ddma)
    wavelength = SPEED_OF_LIGHT / ddma.center_frequency_hz

    # 1. DDMA: per-TX amplitudes [frame, TX, RX].
    per_tx = np.array([per_tx_amplitudes(g, steps) for g in gains[DDMA_CASE]])
    mean_tx = per_tx.mean(axis=0)
    tx_power = np.mean(np.abs(mean_tx) ** 2, axis=1)
    tx_factor, rx_factor, share = rank_one(mean_tx)
    calibration = sidecar(captures[COHERENT_CASE])["calibration"]
    record_tx = np.array(calibration["tx_phase_deg"])
    record_rx = np.array(calibration["rx_phase_deg"])
    measured_tx = -rf_phase_deg(tx_factor)  # in tx_phase_deg's convention
    measured_rx = rf_phase_deg(rx_factor)
    relative = db(tx_power / tx_power[0])
    finite = finite_tx_pattern_db(ranges[DDMA_CASE], wavelength)
    finite_report = finite_tx_pattern_db(REPORT_RANGE_M, wavelength)
    print(f"TX power re TX1: {np.round(relative, 2)}")

    # 2. The beam against TX1's DDMA line and against TX1 alone.
    single = np.mean(np.abs(gains[SINGLE_CASE].mean(axis=1)) ** 2)
    beam = np.mean(np.abs(gains[COHERENT_CASE].mean(axis=1)) ** 2)
    applied = np.radians(
        sidecar(captures[COHERENT_CASE])["actual_waveform"]["tx_initial_phase_deg"]
    )
    predicted = np.mean(
        np.abs(np.sum(mean_tx * np.exp(-1j * applied)[:, None], axis=0)) ** 2
    )
    best = np.mean(np.sum(np.abs(mean_tx), axis=0) ** 2)

    # 4. Calibration records.
    own = str(calibration["created_utc"])
    comparisons: dict[str, Any] = {}
    for key, (tx_b, rx_b, note) in CALIBRATION_RECORDS.items():
        if key != own:
            comparisons[key] = {
                "source": note,
                **calibration_difference(record_tx, record_rx, tx_b, rx_b, wavelength),
            }
    report_rx = REPORT_RX_CORRECTION_DEG[:, REPORT_INDEX_77_GHZ]
    comparisons["report_77ghz_minus_this_run"] = plane_wave_summary(
        wrap_deg(report_rx - record_rx), RX_X_M[:, None], wavelength, "rx"
    )
    comparisons["report_77ghz_minus_2026-09-30"] = plane_wave_summary(
        wrap_deg(report_rx - CALIBRATION_RECORDS[RECORD_0930][1]),
        RX_X_M[:, None],
        wavelength,
        "rx",
    )

    # 5. Channel delays from the DDMA sub-bands.
    centres = band_centres_hz(ddma, SUB_BANDS)
    tx_bands = np.array(
        [np.mean([per_tx_amplitudes(g, steps) for g in band], axis=0) for band in bands]
    )  # [band, TX, RX]
    tx_weights = rx_factor.conj() / np.abs(rx_factor)
    rx_weights = tx_factor.conj() / np.abs(tx_factor)
    tx_delay, tx_residual = delay_fit(rf_phase_deg(tx_bands @ tx_weights), centres)
    rx_delay, rx_residual = delay_fit(
        rf_phase_deg(np.einsum("btr,t->br", tx_bands, rx_weights)), centres
    )
    to_slope = -360 * 1e9  # deg/GHz of received RF phase per second of delay

    summary: dict[str, Any] = {
        "recording": ddma.recording,
        "firmware": ddma.firmware,
        "tx_backoff_db": ddma.tx_backoff_db,
        "rx_gain_db": ddma.rx_gain_db,
        "reflector_range_m": ranges,
        "ddma": {
            "tx_power_relative_to_tx1_db": relative.tolist(),
            "tx_power_cpi_std_db": db(np.mean(np.abs(per_tx) ** 2, axis=2))
            .std(axis=0)
            .tolist(),
            "finite_reflector_tx_pattern_db": finite.tolist(),
            "minus_finite_reflector_db": (relative - finite).tolist(),
            "minus_report_table_2_db": (relative - REPORT_TX_POWER_DB).tolist(),
            "tx2_to_tx8_minus_report_mean_db": float(
                np.mean((relative - REPORT_TX_POWER_DB)[1:])
            ),
            "tx2_to_tx8_minus_report_std_db": float(
                np.std((relative - REPORT_TX_POWER_DB)[1:])
            ),
            "tx2_to_tx8_std_db": float(np.std(relative[1:])),
            "tx2_to_tx8_minus_finite_std_db": float(np.std((relative - finite)[1:])),
            "report_finite_reflector_tx_pattern_db": finite_report.tolist(),
            "report_tx2_to_tx8_std_db": float(np.std(REPORT_TX_POWER_DB[1:])),
            "report_tx2_to_tx8_minus_finite_std_db": float(
                np.std((REPORT_TX_POWER_DB - finite_report)[1:])
            ),
            "rank_one_power_share": share,
            "tx_phase_deg_measured": wrap_deg(measured_tx).tolist(),
            "tx_phase_deg_recorded": wrap_deg(record_tx).tolist(),
            "rx_phase_deg_measured": wrap_deg(measured_rx).tolist(),
            "rx_phase_deg_recorded": wrap_deg(record_rx).tolist(),
            "max_tx_phase_deviation_deg": float(
                np.max(np.abs(wrap_deg(measured_tx - record_tx)))
            ),
            "max_rx_phase_deviation_deg": float(
                np.max(np.abs(wrap_deg(measured_rx - record_rx)))
            ),
            "recorded": {
                key: calibration[key]
                for key in (
                    "created_utc",
                    "measured_range_m",
                    "min_cycle_coherence",
                    "phase_model_residual_rms_deg",
                )
            },
        },
        "beam": {
            "tx1_alone_db_counts2": float(db(single)),
            "ddma_tx1_minus_tx1_alone_db": float(db(tx_power[0] / single)),
            "measured_gain_over_ddma_tx1_db": float(db(beam / tx_power[0])),
            "predicted_over_ddma_tx1_db": float(db(predicted / tx_power[0])),
            "all_eight_in_phase_over_ddma_tx1_db": float(db(best / tx_power[0])),
            "measured_gain_over_tx1_alone_db": float(db(beam / single)),
            "predicted_over_tx1_alone_db": float(db(predicted / single)),
            "eight_equal_tx_db": float(20 * np.log10(8)),
        },
        "stability": {case: stability(g) for case, g in gains.items()},
        "calibration": comparisons,
        "delays": {
            "band_centres_ghz": (centres / 1e9).tolist(),
            "rx_delay_ps": (rx_delay * 1e12).tolist(),
            "rx_fit_residual_deg": rx_residual.tolist(),
            "tx_delay_ps": (tx_delay * 1e12).tolist(),
            "tx_fit_residual_deg": tx_residual.tolist(),
            "rx_phase_slope_deg_per_ghz": (rx_delay * to_slope).tolist(),
            "tx_phase_slope_deg_per_ghz": (tx_delay * to_slope).tolist(),
            "report_rx_phase_slope_deg_per_ghz": report_slopes(
                REPORT_RX_CORRECTION_DEG
            ).tolist(),
            "report_tx_phase_slope_deg_per_ghz": report_slopes(
                REPORT_TX_CORRECTION_DEG
            ).tolist(),
        },
        "double_bounce": double_bounce(ddma, ranges[DDMA_CASE]),
    }
    for kind in ("rx", "tx"):
        ours = np.array(summary["delays"][f"{kind}_phase_slope_deg_per_ghz"])[1:]
        theirs = np.array(summary["delays"][f"report_{kind}_phase_slope_deg_per_ghz"])[
            1:
        ]
        summary["delays"][f"{kind}_slope_minus_report_rms_deg_per_ghz"] = float(
            np.sqrt(np.mean((ours - theirs) ** 2))
        )
    label = (
        f"Chamber, {ddma.recording} (our firmware, {ddma.tx_backoff_db:g} dB backoff)"
    )
    plot(args.output, summary, label)
    write_summary(args.output, summary)


if __name__ == "__main__":
    main()
