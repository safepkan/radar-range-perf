"""Chamber captures: receiver noise, and the background a strong return raises.

For each case (TX1, eight TX in DDMA, the eight-TX beam), per native range bin,
the 8x8 RX covariance over remote-Doppler cells (chamber_common.remote_doppler)
and CPIs, split into the channel-independent floor (middle four eigenvalues, as
in window_scene.py) and the common part above it (chamber_common.
background_split). Beyond a few metres the chamber holds nothing, so the
independent floor is the receiver's noise and the common part comes from the
reflector.

1. Receiver noise: the independent floor as a density in counts^2/Hz
   (chamber_common.cell_to_density), at RX gain 0 dB, against the floors of
   the +3 dB captures stored by window_scene.py and field_if.py.
2. The common part relative to the reflector's mean per-chirp power, per Hz of
   range-bin bandwidth, by offset from the reflector's beat frequency: the
   reflector's own phase-noise skirt if it scales with its power across the
   three cases and has its spatial signature (top eigenvector against its
   per-RX amplitudes). The high-pass filter cuts the reflector at its low beat
   frequency but not the skirt above 1 MHz, so the ratio is corrected by the
   response (chamber_common.high_pass_db) at both frequencies, with the corner
   chamber_tx1.py measured on the reflector and at the datasheet's nominal
   300 kHz. Compared
   with the CTRX8188F CW table, typical and maximum, averaged over its two
   bands (the sweep spans 76.55-77.45 GHz), delay-filtered for the reflector's
   range, both sidebands (chamber_common.real_tone_skirt).
3. The coherent RX gain against that background (chamber_common.
   coherent_rx_gain_db), per IF band.
4. The window capture with no scene beyond 10 m (long-8TX-0dB, which ran TX1)
   and long-1TX-0dB: the common part predicted from the skirt of the strongest
   static return within 0.5-10 m (CW table, typical; its level before the
   high-pass from the measured corner), against the measured one.

Writes summary.json and background.png to --output (default
generated/chamber/background).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from carkit_common import SPEED_OF_LIGHT, STUDY_DIR, ComplexArray, FloatArray, db
from carkit_common import enbw_bins, write_summary
from chamber_common import (
    CASES,
    COHERENT_CASE,
    DDMA_CASE,
    GENERATED_DIR,
    HIGH_PASS_NOMINAL_HZ,
    LINE_GUARD_HZ,
    SINGLE_CASE,
    background_split,
    cell_to_density,
    coherent_rx_gain_db,
    data_argument,
    doppler_window,
    high_pass_db,
    load,
    measured_high_pass_corner_hz,
    per_tx_amplitudes,
    real_tone_skirt,
    reflector_beat,
    remote_covariance,
    reflector_gains,
    remote_doppler,
    signature_alignment,
    tx_phase_steps_deg,
)
from radarperf.phase_noise import (
    SingleReturnPhaseNoise,
    TabulatedPhaseNoise,
    ctrx8188f_phase_noise,
)
from window_common import Capture, range_window
from window_common import doppler_window as hann_window

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

WINDOW_SCENE_DIR = STUDY_DIR / "generated" / "window" / "scene"
FIELD_IF_DIR = STUDY_DIR / "generated" / "field" / "if"
# +3 dB captures whose stored receiver floors the chamber's is compared with.
REFERENCE_FLOORS = ("long-1TX-0dB", "long-8TX-0dB", "medium-1TX-0dB")
# IF bands of the noise comparison; the chamber's Nyquist frequency is 12.5 MHz.
DENSITY_BANDS_HZ = (
    (0.10e6, 0.15e6),
    (0.15e6, 0.20e6),
    (0.20e6, 0.30e6),
    (0.3e6, 0.5e6),
    (0.5e6, 0.8e6),
    (0.8e6, 1.2e6),
    (1.8e6, 2.2e6),
    (3.0e6, 3.6e6),
    (4.0e6, 7.0e6),
    (7.0e6, 10.0e6),
    (10.0e6, 12.0e6),
)
# The comparison's summary band: above the high-pass's region, below Nyquist.
DENSITY_SUMMARY_HZ = (0.3e6, 12.0e6)
# Offsets from the reflector's beat frequency for the skirt and the RX gain.
OFFSET_BANDS_HZ = (
    (0.3e6, 0.5e6),
    (0.5e6, 1.0e6),
    (1.0e6, 2.0e6),
    (2.0e6, 4.0e6),
    (4.0e6, 7.0e6),
    (7.0e6, 10.0e6),
    (10.0e6, 12.0e6),
)
SKIRT_SUMMARY_HZ = (2.0e6, 12.0e6)
# One colour per chamber case in every panel.
CASE_COLOURS = {SINGLE_CASE: "C0", DDMA_CASE: "C1", COHERENT_CASE: "C2"}
# Where the window captures' strongest near return is sought, and the IF band
# over which their common part is compared (as in window_scene's summary).
NEAR_RETURNS_M = (0.5, 10.0)
COMMON_BAND_HZ = (1e6, 10e6)


def phase_noise_tables() -> dict[str, TabulatedPhaseNoise]:
    return {
        f"{band}/{level}": ctrx8188f_phase_noise(
            rf_band=band, level=level, extrapolation="slope"  # type: ignore[arg-type]
        )
        for band in ("76-77", "77-81")
        for level in ("typical", "maximum")
    }


def cw_skirt(
    delay_s: float, beat_hz: float, if_hz: FloatArray, level: str
) -> FloatArray:
    """CW-table skirt of a real-sampled return, mean of the table's two bands."""
    tables = phase_noise_tables()
    return np.asarray(
        np.mean(
            [
                real_tone_skirt(
                    SingleReturnPhaseNoise(
                        delay_s=delay_s, shared=tables[f"{b}/{level}"]
                    ),
                    beat_hz,
                    if_hz,
                )
                for b in ("76-77", "77-81")
            ],
            axis=0,
        )
    )


def analyze(capture: Capture) -> dict[str, Any]:
    """Remote-Doppler covariance per bin and the reflector's per-chirp gains."""
    covariance = remote_covariance(capture)
    beat = reflector_beat(capture)
    per_chirp = reflector_gains(capture, beat)[0]  # [frame, chirp, RX]
    if np.any(tx_phase_steps_deg(capture)):
        signature: ComplexArray = np.mean(
            [per_tx_amplitudes(g, tx_phase_steps_deg(capture))[0] for g in per_chirp],
            axis=0,
        )
    else:
        signature = per_chirp.mean(axis=(0, 1))
    return {
        "covariance": covariance,
        "remote_cells": int(remote_doppler(capture).sum()),
        "beat_hz": float(beat),
        "range_m": float(beat * SPEED_OF_LIGHT / (2 * capture.slope_hz_per_s)),
        "carrier": float(np.mean(np.abs(per_chirp) ** 2)),
        "signature": signature,
    }


def receiver_noise(
    chamber: dict[str, tuple[FloatArray, FloatArray]],
) -> tuple[dict[str, Any], dict[str, tuple[FloatArray, FloatArray]]]:
    """Independent floors as densities [counts^2/Hz] by IF band, all captures."""
    scene = json.loads((WINDOW_SCENE_DIR / "summary.json").read_text())["cases"]
    curves = dict(chamber)
    for case in REFERENCE_FLOORS:
        stored = np.load(WINDOW_SCENE_DIR / f"{case}.npz")
        nc, ns, _ = scene[case]["shape_chirp_sample_rx"]
        fs = ns / (scene[case]["payload_us"] * 1e-6)
        curves[f"window {case} (+3 dB)"] = (
            stored["beat_hz"],
            cell_to_density(
                stored["independent_floor"],
                ns,
                nc,
                fs,
                range_window(ns),
                hann_window(nc),
            ),
        )
    stored = np.load(FIELD_IF_DIR / "notx_background.npz")
    curves["field notx (+3 dB, TX off)"] = (
        stored["beat_hz"],
        cell_to_density(
            stored["independent_floor"],
            512,
            512,
            50e6,
            range_window(512),
            hann_window(512),
        ),
    )
    table: dict[str, Any] = {}
    for name, (beat, density) in curves.items():
        table[name] = {
            f"{lo / 1e6:g}-{hi / 1e6:g}": (
                float(db(np.median(density[(beat >= lo) & (beat < hi)])))
                if np.any((beat >= lo) & (beat < hi))
                else None
            )
            for lo, hi in DENSITY_BANDS_HZ
        }
    lo, hi = DENSITY_SUMMARY_HZ
    inside = [
        f"{a / 1e6:g}-{b / 1e6:g}" for a, b in DENSITY_BANDS_HZ if a >= lo and b <= hi
    ]
    reference = [n for n in table if "+3 dB" in n]
    differences = [
        table[f"chamber {case}"][band] - np.mean([table[r][band] for r in reference])
        for case in CASES
        for band in inside
    ]
    summary = {
        "db_counts2_per_hz": table,
        "chamber_minus_plus3db_captures_db": {
            "band_mhz": [lo / 1e6, hi / 1e6],
            "mean": float(np.mean(differences)),
            "range": [float(np.min(differences)), float(np.max(differences))],
        },
    }
    return summary, curves


def near_return_prediction(case: str, corner_hz: float) -> dict[str, Any]:
    """Common part of a window capture predicted from its strongest near return.

    The strongest point of the static profile within NEAR_RETURNS_M, taken as
    one return, its level before the high-pass from the measured corner, and its
    CW-table skirt (typical). The long waveform's range bins are 1.23 m and the
    return sits deep in the high-pass, so the prediction is repeated half a
    native bin either side.
    """
    scene = json.loads((WINDOW_SCENE_DIR / "summary.json").read_text())["cases"][case]
    stored = np.load(WINDOW_SCENE_DIR / f"{case}.npz")
    nc, ns, _ = scene["shape_chirp_sample_rx"]
    fs = ns / (scene["payload_us"] * 1e-6)
    slope = scene["slope_mhz_per_us"] * 1e12
    padded_range, profile = stored["padded_range_m"], stored["static_profile"]
    near = (padded_range >= NEAR_RETURNS_M[0]) & (padded_range <= NEAR_RETURNS_M[1])
    k = int(np.flatnonzero(near)[np.argmax(profile[near])])
    beat = stored["beat_hz"]
    band = (beat >= COMMON_BAND_HZ[0]) & (beat <= COMMON_BAND_HZ[1])
    enbw_hz = enbw_bins(range_window(ns)) * fs / ns
    per_cell = enbw_bins(hann_window(nc)) / nc  # white over chirps
    independent = stored["independent_floor"][band]
    total = stored["total_floor"][band]
    half_bin_m = float(stored["range_m"][1]) / 2
    predictions = {}
    for shift in (-half_bin_m, 0.0, half_bin_m):
        range_m = float(padded_range[k]) + shift
        f_b = 2 * slope * range_m / SPEED_OF_LIGHT
        before = float(profile[k] / 10 ** (high_pass_db(f_b, corner_hz) / 10))
        skirt = cw_skirt(2 * range_m / SPEED_OF_LIGHT, f_b, beat[band], "typical")
        common = before * skirt * enbw_hz * per_cell
        predictions[f"{range_m:.2f}"] = {
            "beat_khz": f_b / 1e3,
            "high_pass_db": float(high_pass_db(f_b, corner_hz)),
            "predicted_common_lift_db": float(np.median(db(1 + common / independent))),
        }
    return {
        "strongest_near_range_m": float(padded_range[k]),
        "strongest_near_level_db_counts2": float(db(profile[k])),
        "native_bin_m": 2 * half_bin_m,
        "measured_common_lift_db": float(np.median(db(total) - db(independent))),
        "predicted_at_range_m": predictions,
    }


def plot(
    output: Path,
    curves: dict[str, tuple[FloatArray, FloatArray]],
    common: dict[str, tuple[FloatArray, FloatArray]],
    skirt: dict[str, Any],
) -> None:
    figure, (left, middle, right) = plt.subplots(
        1, 3, figsize=(17, 5.2), layout="constrained"
    )
    others = iter(f"C{k}" for k in range(3, 10))
    for name, (beat, density) in curves.items():
        case = name.removeprefix("chamber ")
        chamber = case in CASE_COLOURS
        left.plot(
            beat / 1e6,
            db(density),
            lw=1.2 if chamber else 0.8,
            ls="-" if chamber else "--",
            color=CASE_COLOURS[case] if chamber else next(others),
            label=name,
        )
    left.set(
        xscale="log",
        xlim=(0.1, 25),
        ylim=(-64, -52),
        xlabel="Beat frequency [MHz]",
        ylabel="dB ADC-count² / Hz",
        title="Receiver noise: channel-independent floor\n(chamber at RX gain 0 dB, others +3 dB)",
    )
    left.grid(alpha=0.3, which="both")
    left.legend(fontsize=7)
    for name, (beat, lift) in common.items():
        middle.plot(beat / 1e6, lift, lw=0.9, color=CASE_COLOURS[name], label=name)
    middle.set(
        xscale="log",
        xlim=(0.1, 12.5),
        ylim=(-0.5, 6),
        xlabel="Beat frequency [MHz]",
        ylabel="Total over independent floor [dB]",
        title="Common part of the remote-Doppler background",
    )
    middle.grid(alpha=0.3, which="both")
    middle.legend(fontsize=8)
    offsets = np.array(skirt["offset_mhz"])
    for case, marker in ((COHERENT_CASE, "o"), (DDMA_CASE, "s")):
        values = skirt["cases"][case]
        right.plot(
            offsets,
            values["measured_corner"],
            marker=marker,
            ls="-",
            color=CASE_COLOURS[case],
            label=f"{case}, reflector corrected for the high-pass (measured corner)",
        )
        right.plot(
            offsets,
            values["nominal_corner"],
            marker=marker,
            ls=":",
            mfc="none",
            color=CASE_COLOURS[case],
            label=f"{case}, with the nominal 300 kHz corner",
        )
    right.plot(offsets, skirt["cw_typical"], "k-", lw=1.2, label="CW table, typical")
    right.plot(offsets, skirt["cw_maximum"], "k--", lw=1.0, label="CW table, maximum")
    right.set(
        xscale="log",
        ylim=(-125, -100),
        xlabel="Offset from the reflector's beat frequency [MHz]",
        ylabel="dBc/Hz (both sidebands)",
        title="The reflector's skirt against the CTRX8188F CW table\n(delay-filtered at the reflector's range)",
    )
    right.grid(alpha=0.3, which="both")
    right.legend(fontsize=7)
    figure.savefig(output / "background.png", dpi=110)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "background")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    corner_hz = measured_high_pass_corner_hz()
    print(f"high-pass corner measured on the reflector: {corner_hz / 1e3:.0f} kHz")

    cases: dict[str, Any] = {}
    chamber_curves: dict[str, tuple[FloatArray, FloatArray]] = {}
    common_curves: dict[str, tuple[FloatArray, FloatArray]] = {}
    skirt_rows: dict[str, Any] = {}
    offsets_mhz = [np.sqrt(lo * hi) / 1e6 for lo, hi in OFFSET_BANDS_HZ]
    cw: dict[str, list[float]] = {"typical": [], "maximum": []}
    for case in CASES:
        capture = load(case, args.data, verify=True)
        values = analyze(capture)
        nc, ns, _ = capture.shape
        fs = capture.sample_rate_hz
        beat = capture.beat_frequency_hz(capture.range_axis())
        parts = background_split(values["covariance"])
        chamber_curves[f"chamber {case}"] = (
            beat,
            cell_to_density(
                parts["independent"], ns, nc, fs, range_window(ns), doppler_window(nc)
            ),
        )
        common_curves[case] = (beat, db(parts["total"]) - db(parts["independent"]))
        enbw_hz = enbw_bins(range_window(ns)) * fs / ns
        per_chirp = parts["common"] * nc / enbw_bins(doppler_window(nc))
        delay = 2 * values["range_m"] / SPEED_OF_LIGHT
        f_b = values["beat_hz"]
        bands = []
        for lo, hi in OFFSET_BANDS_HZ:
            m = (beat - f_b >= lo) & (beat - f_b < hi)
            at_adc = float(db(np.median(per_chirp[m]) / values["carrier"] / enbw_hz))
            centre = float(np.median(beat[m]))
            row = {
                "offset_mhz": [lo / 1e6, hi / 1e6],
                "common_over_independent_db": float(
                    np.median(db(parts["total"][m]) - db(parts["independent"][m]))
                ),
                "skirt_at_adc_dbc_per_hz": at_adc,
                "skirt_measured_corner_dbc_per_hz": float(
                    at_adc
                    + high_pass_db(f_b, corner_hz)
                    - high_pass_db(centre, corner_hz)
                ),
                "skirt_nominal_corner_dbc_per_hz": float(
                    at_adc
                    + high_pass_db(f_b, HIGH_PASS_NOMINAL_HZ)
                    - high_pass_db(centre, HIGH_PASS_NOMINAL_HZ)
                ),
                "alignment_with_reflector": float(
                    np.median(
                        signature_alignment(
                            values["covariance"][m], values["signature"]
                        )
                    )
                ),
                "coherent_rx_gain_db": float(
                    np.median(
                        coherent_rx_gain_db(
                            values["covariance"][m], values["signature"]
                        )
                    )
                ),
            }
            if case == SINGLE_CASE:
                for level in cw:
                    cw[level].append(
                        float(db(np.median(cw_skirt(delay, f_b, beat[m], level))))
                    )
            bands.append(row)
        summary_band = (beat - f_b >= SKIRT_SUMMARY_HZ[0]) & (
            beat - f_b < SKIRT_SUMMARY_HZ[1]
        )
        cases[case] = {
            "remote_doppler_cells": values["remote_cells"],
            "reflector_range_m": values["range_m"],
            "reflector_beat_khz": f_b / 1e3,
            "reflector_per_chirp_db_counts2": float(db(values["carrier"])),
            "high_pass_at_reflector_db": {
                "measured_corner": float(high_pass_db(f_b, corner_hz)),
                "nominal_corner": float(high_pass_db(f_b, HIGH_PASS_NOMINAL_HZ)),
            },
            "offset_bands": bands,
            "common_over_independent_2_12_mhz_db": float(
                np.median(
                    db(parts["total"][summary_band])
                    - db(parts["independent"][summary_band])
                )
            ),
            "coherent_rx_gain_2_12_mhz_db": float(
                np.median(
                    coherent_rx_gain_db(
                        values["covariance"][summary_band], values["signature"]
                    )
                )
            ),
        }
        skirt_rows[case] = {
            "measured_corner": [b["skirt_measured_corner_dbc_per_hz"] for b in bands],
            "nominal_corner": [b["skirt_nominal_corner_dbc_per_hz"] for b in bands],
        }
        print(
            f"{case}: reflector {values['range_m']:.3f} m, {db(values['carrier']):.1f} dB "
            f"counts^2 per chirp; common part 2-12 MHz "
            f"{cases[case]['common_over_independent_2_12_mhz_db']:+.2f} dB; RX gain "
            f"{cases[case]['coherent_rx_gain_2_12_mhz_db']:.2f} dB"
        )

    noise, curves = receiver_noise(chamber_curves)
    near = {
        case: near_return_prediction(case, corner_hz)
        for case in ("long-8TX-0dB", "long-1TX-0dB")
    }
    skirt = {
        "offset_mhz": offsets_mhz,
        "cases": skirt_rows,
        "cw_typical": cw["typical"],
        "cw_maximum": cw["maximum"],
    }
    plot(args.output, curves, common_curves, skirt)
    write_summary(
        args.output,
        {
            "high_pass": {
                "measured_corner_khz": corner_hz / 1e3,
                "nominal_corner_khz": HIGH_PASS_NOMINAL_HZ / 1e3,
            },
            "remote_doppler_guard_hz": LINE_GUARD_HZ,
            "receiver_noise": noise,
            "cases": cases,
            "cw_table_skirt_dbc_per_hz": {
                "offset_bands_mhz": [
                    [lo / 1e6, hi / 1e6] for lo, hi in OFFSET_BANDS_HZ
                ],
                "typical": cw["typical"],
                "maximum": cw["maximum"],
            },
            "window_near_returns": near,
        },
    )


if __name__ == "__main__":
    main()
