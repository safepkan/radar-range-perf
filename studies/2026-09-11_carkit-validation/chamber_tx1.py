"""Chamber captures of 2026-10-09: TX1 at a valid backoff, the high-pass, the level.

TX1 alone with the chamber's 10 dBsm reflector at an apparent 2.21 m and RX gain
+3 dB, as in the field captures (chamber_common: TX1_CASES, NOTX_CASES):

1. Backoff: the 2026-09-29 waveform at 0 and 10 dB backoff; the change of the
   reflector's level is the step.
2. High-pass: the same waveform at 10 dB backoff against the steep chirp at
   10 dB backoff. Both sweep the same RF band at the same gain, with the
   reflector at 162 kHz and 1.29 MHz, so their ratio is the IF response's,
   fitted with two coincident poles (chamber_common.high_pass_db). The fit to
   the field captures' chained IF response (field_if.py) is given beside it.
3. Receiver noise: the channel-independent floor of every capture as a
   density (chamber_common.floor_density), the TX-off captures against the
   field's TX-off capture of 2026-10-01, and the two sample rates (25 and
   50 MS/s) against each other with TX1 on.
4. The finite reflector: TX1's return in each RX, relative to the RX mean,
   against the finite-aperture prediction (chamber_common.pair_power_db),
   here and on 2026-09-29 (2.46 m).
5. Level: the steep chirp's SNR against the reference model
   (field_common.reference_radar, typical noise figure at +3 dB) with the TX
   power lowered by the measured step, and by the nominal 10 dB. The reflector's
   power is corrected for the high-pass at 1.29 MHz and for the finite-aperture
   factor (mean power over the eight RX); the noise is taken at 4-7 MHz
   (centred on 5.3 MHz, the baseline of the other sessions) and at the
   reflector's own beat frequency. The full-power capture, corrected by the
   measured high-pass at 162 kHz, gives the same level by a second route.

Writes generated/chamber/2026-10-09/tx1/summary.json and tx1.png.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.optimize import brentq

from carkit_common import SPEED_OF_LIGHT, STUDY_DIR, FloatArray, db, enbw_bins
from carkit_common import write_summary
from chamber_common import (
    BACKOFF_CASE,
    FULL_POWER_CASE,
    GENERATED_1009_DIR,
    HOME_MADE_EDGE_M,
    HIGH_PASS_NOMINAL_HZ,
    LAB_COMPARISON_RANGES_M,
    LAB_COMPARISON_RATIO_DB,
    NOTX_CASES,
    REFLECTOR_EDGE_M,
    REFLECTOR_RCS_DBSM,
    SINGLE_CASE,
    STEEP_CASE,
    TX_POSITION_M,
    TX1_CASES,
    cell_to_density,
    data_1009_argument,
    fit_high_pass_corner,
    floor_density,
    high_pass_db,
    load,
    load_1009,
    pair_power_db,
    reflector_beat,
    reflector_gains,
    rx_positions_m,
)
from field_common import reference_radar
from radarperf import ConstantRcsTarget, Geometry
from radarperf.frontend import GenericFrontend
from window_common import Capture, doppler_window, range_window

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIELD_IF_DIR = STUDY_DIR / "generated" / "field" / "if"
NOISE_BANDS_HZ = {
    "0.8-1.2": (0.8e6, 1.2e6),
    "1.8-2.2": (1.8e6, 2.2e6),
    "4-7": (4.0e6, 7.0e6),
    "7-10": (7.0e6, 10.0e6),
    "10-12": (10.0e6, 12.0e6),
    "18-24": (18.0e6, 24.0e6),
}
BASELINE_BAND = "4-7"  # centred on 5.3 MHz
# Bands where both sample rates have data, for their comparison.
RATE_BANDS = ("4-7", "7-10", "10-12")
LOCAL_HALF_WIDTH = 0.1  # local noise: within +-10 % of the beat frequency


def band_db(
    beat: FloatArray, density: FloatArray, lo: float, hi: float
) -> float | None:
    inside = (beat >= lo) & (beat < hi)
    return float(db(np.median(density[inside]))) if inside.any() else None


def reflector(capture: Capture) -> dict[str, Any]:
    """The reflector's zero-Doppler amplitudes per CPI and RX, level and stability."""
    beat = reflector_beat(capture)
    zero = reflector_gains(capture, beat)[0].mean(axis=1)  # [frame, RX]
    level = float(db(np.mean(np.abs(zero) ** 2)))
    per_cpi = db(np.mean(np.abs(zero) ** 2, axis=1))
    return {
        "beat_hz": beat,
        "range_m": float(beat * SPEED_OF_LIGHT / (2 * capture.slope_hz_per_s)),
        "level_db_counts2": level,
        "cpi_std_db": float(per_cpi.std()),
        "per_rx_db": (db(np.mean(np.abs(zero) ** 2, axis=0)) - level).tolist(),
    }


def cell_db(capture: Capture) -> float:
    """dB from a density [counts^2/Hz] to the model's RD cell (Blackman-Harris
    range, Hann Doppler; inverse of chamber_common.cell_to_density)."""
    ns, nc = capture.n_samples, capture.n_chirps
    return float(
        db(
            capture.sample_rate_hz
            / 2
            * enbw_bins(range_window(ns))
            / ns
            * enbw_bins(doppler_window(nc))
            / nc
        )
    )


def finite_reflector_mean_db(
    range_m: float, wavelength_m: float, edge_m: float = REFLECTOR_EDGE_M
) -> float:
    """TX1's finite-aperture factor as mean power over the eight RX [dB]."""
    pairs = pair_power_db(
        edge_m, range_m, TX_POSITION_M[:1], rx_positions_m(), wavelength_m
    )[0]
    return float(db(np.mean(10 ** (pairs / 10))))


def home_made_rcs(wavelength_m: float) -> dict[str, float]:
    """The home-made reflector's RCS from the lab comparison, with each
    reflector's finite-aperture factor at its distance taken out."""
    chamber_m, home_made_m = LAB_COMPARISON_RANGES_M
    chamber = finite_reflector_mean_db(chamber_m, wavelength_m)
    home_made = finite_reflector_mean_db(home_made_m, wavelength_m, HOME_MADE_EDGE_M)
    return {
        "chamber_reflector_factor_db": chamber,
        "home_made_factor_db": home_made,
        "lab_ratio_db": LAB_COMPARISON_RATIO_DB,
        "rcs_dbsm": REFLECTOR_RCS_DBSM + LAB_COMPARISON_RATIO_DB + chamber - home_made,
    }


def model_snr_db(capture: Capture, range_m: float, backoff_db: float) -> float:
    radar = reference_radar(capture)
    if not isinstance(radar.frontend, GenericFrontend):
        raise TypeError("expected the CTRX8188F preset's GenericFrontend")
    power = radar.frontend.tx_power_w * 10 ** (-backoff_db / 10)
    radar = replace(radar, frontend=replace(radar.frontend, tx_power_w=power))
    target = ConstantRcsTarget.from_dbsm(REFLECTOR_RCS_DBSM, swerling=0)
    return float(radar.link_budget(target, Geometry(range_m=range_m)).snr_db)


def plot(output: Path, summary: dict[str, Any], field_chain: dict[str, float]) -> None:
    figure, (left, right) = plt.subplots(1, 2, figsize=(14, 5.2), layout="constrained")
    f = np.geomspace(0.1e6, 6e6, 300)
    corners = summary["high_pass"]
    for corner, style, label in (
        (corners["corner_khz"] * 1e3, "-", "two poles, fitted here"),
        (
            corners["field_fit_corner_khz"] * 1e3,
            "--",
            "two poles, fitted to the field chain",
        ),
        (HIGH_PASS_NOMINAL_HZ, ":", "two poles, nominal 300 kHz"),
    ):
        left.plot(
            f / 1e6,
            high_pass_db(f, corner),
            style,
            color="k",
            lw=1,
            label=f"{label} ({corner / 1e3:.0f} kHz)",
        )
    chain_f = np.array([float(k) for k in field_chain])
    left.plot(
        chain_f / 1e6,
        list(field_chain.values()),
        "s",
        color="C1",
        label="Field captures, two slopes (re 2.5 MHz)",
    )
    point = corners["measured_low_minus_high_db"] + float(
        high_pass_db(corners["high_hz"], corners["corner_khz"] * 1e3)
    )
    left.plot(
        corners["low_hz"] / 1e6,
        point,
        "o",
        color="C0",
        ms=8,
        label="Chamber, 162 kHz against 1.29 MHz",
    )
    left.set(
        xscale="log",
        ylim=(-16, 1),
        xlabel="Beat frequency [MHz]",
        ylabel="IF response [dB]",
        title="The analog high-pass filter",
    )
    left.grid(alpha=0.3, which="both")
    left.legend(fontsize=8, loc="lower right")

    rx = np.arange(1, 9)
    pattern = summary["finite_reflector"]
    for key, marker, colour, label in (
        ("2026-10-09", "o", "C0", "2026-10-09, 2.21 m"),
        ("2026-09-29", "s", "C1", "2026-09-29, 2.46 m"),
    ):
        right.plot(
            rx,
            pattern[key]["measured_db"],
            marker,
            color=colour,
            ms=7,
            label=f"Measured, {label}",
        )
        right.plot(
            rx,
            pattern[key]["predicted_db"],
            "-",
            color=colour,
            lw=1,
            label=f"Finite-aperture prediction, {label}",
        )
    right.axhline(0, color="k", lw=0.6)
    right.set(
        xticks=rx,
        xlabel="RX (RX7 is the farthest from TX1, RX8 next)",
        ylabel="TX1's return relative to the RX mean [dB]",
        title="TX1's return in each RX at short range",
    )
    right.grid(alpha=0.3)
    right.legend(fontsize=8)
    figure.savefig(output / "tx1.png", dpi=110)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_1009_argument(parser)
    parser.add_argument(
        "--data-0929", type=Path, default=None, help="2026-09-29 chamber captures"
    )
    parser.add_argument("--output", type=Path, default=GENERATED_1009_DIR / "tx1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    captures = {
        case: load_1009(case, args.data, verify=True) for case in TX1_CASES + NOTX_CASES
    }
    returns = {case: reflector(captures[case]) for case in TX1_CASES}
    for case, values in returns.items():
        print(
            f"{case}: {values['level_db_counts2']:.2f} dB counts^2 at {values['beat_hz'] / 1e3:.1f} kHz"
        )

    # 1-2. Backoff step and high-pass.
    step = (
        returns[FULL_POWER_CASE]["level_db_counts2"]
        - returns[BACKOFF_CASE]["level_db_counts2"]
    )
    low_hz, high_hz = returns[BACKOFF_CASE]["beat_hz"], returns[STEEP_CASE]["beat_hz"]
    ratio = (
        returns[BACKOFF_CASE]["level_db_counts2"]
        - returns[STEEP_CASE]["level_db_counts2"]
    )
    corner = float(
        brentq(
            lambda c: float(high_pass_db(low_hz, c) - high_pass_db(high_hz, c)) - ratio,
            30e3,
            3e6,
        )
    )
    chain_summary = json.loads((FIELD_IF_DIR / "summary.json").read_text())
    chain = chain_summary["if_response_db"]
    field_corner, field_rms = fit_high_pass_corner(
        np.array([float(k) for k in chain]),
        np.array(list(chain.values())),
        float(chain_summary["if_response_db_relative_to_hz"]),
    )

    # 3. Receiver noise.
    floors = {case: floor_density(captures[case]) for case in TX1_CASES + NOTX_CASES}
    stored = np.load(FIELD_IF_DIR / "notx_background.npz")
    field_beat = stored["beat_hz"]
    field_density = cell_to_density(
        stored["independent_floor"],
        512,
        512,
        50e6,
        range_window(512),
        doppler_window(512),
    )
    noise: dict[str, dict[str, float | None]] = {
        case: {
            name: band_db(*floors[case], *band) for name, band in NOISE_BANDS_HZ.items()
        }
        for case in floors
    }
    noise["field notx, 2026-10-01"] = {
        name: band_db(field_beat, field_density, *band)
        for name, band in NOISE_BANDS_HZ.items()
    }

    def mean_of(cases: tuple[str, ...], band: str) -> float:
        values = [noise[c][band] for c in cases]
        return float(np.mean([v for v in values if v is not None]))

    noise_checks = {
        "notx_spread_db": {
            band: float(np.ptp([noise[c][band] for c in NOTX_CASES]))
            for band in RATE_BANDS
        },
        "notx_minus_field_notx_db": {
            band: mean_of(NOTX_CASES, band)
            - float(noise["field notx, 2026-10-01"][band] or 0.0)
            for band in RATE_BANDS
        },
        "steep_tx1_minus_notx_db": {
            band: float(noise[STEEP_CASE][band] or 0.0) - mean_of(NOTX_CASES, band)
            for band in RATE_BANDS
        },
        "rate_25_minus_50_msps_with_tx1_db": {
            band: float(noise[BACKOFF_CASE][band] or 0.0)
            - float(noise[STEEP_CASE][band] or 0.0)
            for band in RATE_BANDS
        },
    }

    # 4. TX1's return per RX against the finite reflector, both sessions.
    steep = captures[STEEP_CASE]
    wavelength = SPEED_OF_LIGHT / steep.center_frequency_hz
    earlier = load(SINGLE_CASE, args.data_0929)
    earlier_return = reflector(earlier)
    pattern: dict[str, Any] = {}
    for key, values in (
        ("2026-10-09", returns[STEEP_CASE]),
        ("2026-09-29", earlier_return),
    ):
        pairs = pair_power_db(
            REFLECTOR_EDGE_M,
            values["range_m"],
            TX_POSITION_M[:1],
            rx_positions_m(),
            wavelength,
        )[0]
        predicted = pairs - db(np.mean(10 ** (pairs / 10)))
        measured = np.array(values["per_rx_db"])
        pattern[key] = {
            "range_m": values["range_m"],
            "measured_db": measured.tolist(),
            "predicted_db": predicted.tolist(),
            "residual_db": (measured - predicted).tolist(),
            "measured_rms_db": float(np.sqrt(np.mean(measured**2))),
            "residual_rms_db": float(np.sqrt(np.mean((measured - predicted) ** 2))),
        }
    pattern["residual_difference_between_days_rms_db"] = float(
        np.sqrt(
            np.mean(
                (
                    np.array(pattern["2026-10-09"]["residual_db"])
                    - np.array(pattern["2026-09-29"]["residual_db"])
                )
                ** 2
            )
        )
    )

    # 5. Level against the model.
    level: dict[str, Any] = {}
    for route, case, backoffs in (
        (
            "steep chirp, 10 dB backoff",
            STEEP_CASE,
            {"measured step": step, "nominal": 10.0},
        ),
        ("2026-09-29 waveform, full power", FULL_POWER_CASE, {"none": 0.0}),
    ):
        capture, values = captures[case], returns[case]
        finite = finite_reflector_mean_db(values["range_m"], wavelength)
        high_pass = float(high_pass_db(values["beat_hz"], corner))
        beat, density = floors[case]
        local = (
            values["beat_hz"] * (1 - LOCAL_HALF_WIDTH),
            values["beat_hz"] * (1 + LOCAL_HALF_WIDTH),
        )
        noise_db = {
            "5.3 MHz": float(
                band_db(beat, density, *NOISE_BANDS_HZ[BASELINE_BAND]) or 0.0
            )
            + cell_db(capture),
            "local": float(band_db(beat, density, *local) or 0.0) + cell_db(capture),
        }
        if values["beat_hz"] < HIGH_PASS_NOMINAL_HZ:
            # Below the high-pass the noise is not shaped like the signal.
            del noise_db["local"]
        for backoff_name, backoff in backoffs.items():
            model = model_snr_db(capture, values["range_m"], backoff)
            for noise_name, noise_cell in noise_db.items():
                snr = values["level_db_counts2"] - high_pass - finite - noise_cell
                level[f"{route}; backoff {backoff_name}; noise {noise_name}"] = {
                    "range_m": values["range_m"],
                    "high_pass_db": high_pass,
                    "finite_reflector_db": finite,
                    "noise_per_cell_db_counts2": noise_cell,
                    "measured_snr_db": snr,
                    "model_snr_db": model,
                    "measured_minus_model_db": snr - model,
                    "without_finite_reflector_db": snr + finite - model,
                }
    summary = {
        "firmware": steep.firmware,
        "cases": {
            case: {
                **{k: v for k, v in returns[case].items() if k != "per_rx_db"},
                "first_cpi_utc": captures[case].timestamps[0],
                "tx_backoff_db": captures[case].tx_backoff_db,
                "slope_mhz_per_us": captures[case].slope_hz_per_s / 1e12,
            }
            for case in TX1_CASES
        },
        "backoff_step_db": step,
        "high_pass": {
            "low_hz": low_hz,
            "high_hz": high_hz,
            "measured_low_minus_high_db": ratio,
            "corner_khz": corner / 1e3,
            "field_fit_corner_khz": field_corner / 1e3,
            "field_fit_rms_db": field_rms,
            "field_fit_low_minus_high_db": float(
                high_pass_db(low_hz, field_corner) - high_pass_db(high_hz, field_corner)
            ),
            "at_2026_09_29_reflector_db": {
                "measured_corner": float(high_pass_db(180.05e3, corner)),
                "field_fit_corner": float(high_pass_db(180.05e3, field_corner)),
            },
        },
        "noise_db_counts2_per_hz": noise,
        "noise_checks": noise_checks,
        "finite_reflector": pattern,
        "finite_reflector_tx1_mean_db": {
            key: finite_reflector_mean_db(values["range_m"], wavelength)
            for key, values in (
                ("2026-10-09", returns[STEEP_CASE]),
                ("2026-09-29", earlier_return),
            )
        },
        "home_made_reflector_rcs": home_made_rcs(wavelength),
        "range_sensitivity_db_per_cm": float(
            40 * np.log10(1 + 0.01 / returns[STEEP_CASE]["range_m"])
        ),
        "level": level,
    }
    plot(args.output, summary, chain)
    write_summary(args.output, summary)


if __name__ == "__main__":
    main()
