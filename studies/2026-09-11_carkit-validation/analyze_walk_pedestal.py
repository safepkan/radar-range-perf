"""Fit how the walk's target-associated Doppler pedestal scales with power and range.

Reads the per-frame output of analyze_walk_dynamics.py; the raw capture is not
needed.  For each remote-Doppler cutoff, the excess background at the target
range relative to its same-range control is fitted as

    ratio_db = 10 log10(1 + 10**c * S**a * (R / 30 m)**b),

where S is the mean-RX target-cell power (arbitrary ADC/FFT reference).  A
purely multiplicative disturbance with a fixed fractional level has a=1, b=0.
A per-chirp phase error proportional to round-trip delay, such as an effective
chirp-to-chirp frequency error delta_f giving delta_phi = 2 pi tau delta_f, has
a=1, b=2.  The legs separate a from b because the outbound return is about
12 dB weaker than the inbound return at the same range.

The excess-to-peak ratio is also converted to the equivalent in-band RMS
frequency error used by the 2026-09-22 phase-noise-outdoor study on the
phase-noise branch, under the small-phase interpretation.  Amplitude
fluctuations and RX-independent contributions are not separated here, so this
is an equivalent quantity, not an RF source specification.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import numpy.typing as npt
from scipy.optimize import least_squares
from scipy.signal.windows import blackman

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FloatArray = npt.NDArray[np.float64]

SPEED_OF_LIGHT = 299792458.0
CARRIER_HZ = 76.374237e9
N_SAMPLES = 512
N_CHIRPS = 1024
PRI_S = 15.96e-6
RANGE_PADDING = 4
REFERENCE_RANGE_M = 30.0
CUTOFFS_MPS = (10, 20, 30)
PLOT_CUTOFF_MPS = 20
# Frames with less excess than this give unreliable excess-to-peak ratios.
MIN_RATIO_FOR_LEVEL_DB = 0.5
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 20260929


def db(value: npt.ArrayLike) -> FloatArray:
    """Convert positive power-like values to dB."""
    return np.asarray(10 * np.log10(np.maximum(value, np.finfo(float).tiny)))


def predicted_ratio_db(
    params: FloatArray, signal_db: FloatArray, range_m: FloatArray
) -> FloatArray:
    """Excess background ratio for log10 level c, power exponent a, range exponent b."""
    level, power_exponent, range_exponent = params
    excess = 10 ** (
        level
        + power_exponent * signal_db / 10
        + range_exponent * np.log10(range_m / REFERENCE_RANGE_M)
    )
    return db(1 + excess)


def fit(
    ratio_db: FloatArray,
    signal_db: FloatArray,
    range_m: FloatArray,
    fixed: tuple[float, float] | None,
) -> FloatArray:
    """Least-squares fit in the dB ratio domain; fixed=(a, b) fits only c."""
    if fixed is None:
        result = least_squares(
            lambda p: predicted_ratio_db(p, signal_db, range_m) - ratio_db,
            [-3.0, 1.0, 0.0],
        )
        return np.asarray(result.x, dtype=float)
    result = least_squares(
        lambda p: predicted_ratio_db(np.array([p[0], *fixed]), signal_db, range_m)
        - ratio_db,
        [-3.0],
    )
    return np.array([float(result.x[0]), *fixed])


def range_band_dilution() -> float:
    """Mean over the +/-1 native-bin band of the target's range response, peak=1.

    analyze_walk_dynamics.py averages background over padded range bins within
    one native bin of the target peak.  A disturbance that multiplies the whole
    chirp inherits the target's range response, so its band mean is lower than
    its value at the peak by this factor.
    """
    window = np.asarray(blackman(N_SAMPLES, sym=False), dtype=float)
    n = np.arange(N_SAMPLES)
    offsets = np.arange(-RANGE_PADDING, RANGE_PADDING + 1) / RANGE_PADDING
    response = np.array(
        [
            abs(np.sum(window * np.exp(-2j * np.pi * offset * n / N_SAMPLES))) ** 2
            for offset in offsets
        ]
    )
    return float(np.mean(response / response[RANGE_PADDING]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent / "generated/dynamics/per_frame.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "generated/pedestal",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    with args.csv.open() as stream:
        rows = list(csv.DictReader(stream))
    leg = np.array([row["leg"] for row in rows])
    range_m = np.array([float(row["range_m"]) for row in rows])
    signal_db = np.array([float(row["mean_rx_signal_power_db"]) for row in rows])
    delay_s = 2 * range_m / SPEED_OF_LIGHT

    doppler_window = np.asarray(blackman(N_CHIRPS, sym=False), dtype=float)
    doppler_enbw = float(
        N_CHIRPS * np.sum(doppler_window**2) / np.sum(doppler_window) ** 2
    )
    native_doppler_hz = np.fft.fftfreq(N_CHIRPS, PRI_S)
    wavelength_m = SPEED_OF_LIGHT / CARRIER_HZ
    dilution = range_band_dilution()
    rng = np.random.default_rng(BOOTSTRAP_SEED)

    summary: dict[str, Any] = {
        "input": str(args.csv),
        "model": "ratio_db = 10 log10(1 + 10**c * S**a * (R / 30 m)**b)",
        "frames": int(len(rows)),
        "doppler_blackman_enbw_bins": doppler_enbw,
        "range_band_dilution_db": float(db(dilution)),
        "cutoffs": {},
    }
    for cutoff in CUTOFFS_MPS:
        ratio_db = np.array(
            [float(row[f"background_ratio_{cutoff}_db"]) for row in rows]
        )
        variants: dict[str, Any] = {}
        for name, fixed in (
            ("free", None),
            ("fixed_fraction_a1_b0", (1.0, 0.0)),
            ("delay_squared_a1_b2", (1.0, 2.0)),
        ):
            params = fit(ratio_db, signal_db, range_m, fixed)
            residual = predicted_ratio_db(params, signal_db, range_m) - ratio_db
            variants[name] = {
                "c_log10": float(params[0]),
                "a_power_exponent": float(params[1]),
                "b_range_exponent": float(params[2]),
                "rms_residual_db": float(np.sqrt(np.mean(residual**2))),
                "mean_residual_db_by_leg": {
                    name: float(np.mean(residual[leg == name]))
                    for name in ("outbound", "inbound")
                },
            }

        # Frames are resampled independently.  Consecutive CPIs are correlated,
        # so these intervals are descriptive rather than calibrated.
        exponents = np.empty((BOOTSTRAP_RESAMPLES, 2))
        for index in range(BOOTSTRAP_RESAMPLES):
            pick = rng.integers(0, len(rows), len(rows))
            exponents[index] = fit(
                ratio_db[pick], signal_db[pick], range_m[pick], None
            )[1:]
        variants["free"]["bootstrap_p5_p95"] = {
            "a_power_exponent": np.percentile(exponents[:, 0], [5, 95]).tolist(),
            "b_range_exponent": np.percentile(exponents[:, 1], [5, 95]).tolist(),
        }

        doppler_min_hz = 2 * cutoff / wavelength_m
        band_bins = int(np.count_nonzero(np.abs(native_doppler_hz) >= doppler_min_hz))
        excess_to_peak_db = np.array(
            [float(row[f"positive_excess_to_target_{cutoff}_db"]) for row in rows]
        )
        reliable = np.isfinite(excess_to_peak_db) & (ratio_db > MIN_RATIO_FOR_LEVEL_DB)
        # Per-bin excess relative to the peak, corrected to the target's range
        # peak, integrated over the band and divided by the Doppler ENBW gives
        # the in-band phase variance under the small-phase interpretation.
        per_bin = 10 ** (excess_to_peak_db[reliable] / 10) / dilution
        phase_rms_rad = np.sqrt(per_bin * band_bins / doppler_enbw)
        frequency_rms_hz = phase_rms_rad / (2 * np.pi * delay_s[reliable])
        phase_at_reference = phase_rms_rad * REFERENCE_RANGE_M / range_m[reliable]
        summary["cutoffs"][str(cutoff)] = {
            "doppler_band_hz": [doppler_min_hz, 1 / (2 * PRI_S)],
            "band_bins": band_bins,
            "fits": variants,
            "equivalent_level": {
                "frames": int(np.count_nonzero(reliable)),
                "frames_by_leg": {
                    name: int(np.count_nonzero(leg[reliable] == name))
                    for name in ("outbound", "inbound")
                },
                "range_span_m": [
                    float(range_m[reliable].min()),
                    float(range_m[reliable].max()),
                ],
                "excess_to_peak_at_30m_db_median_p10_p90": np.percentile(
                    excess_to_peak_db[reliable]
                    + 20 * np.log10(REFERENCE_RANGE_M / range_m[reliable]),
                    [50, 10, 90],
                ).tolist(),
                "excess_to_peak_spread_db_raw_vs_range_normalized": [
                    float(np.std(excess_to_peak_db[reliable])),
                    float(
                        np.std(
                            excess_to_peak_db[reliable]
                            + 20 * np.log10(REFERENCE_RANGE_M / range_m[reliable])
                        )
                    ),
                ],
                "in_band_phase_rms_at_30m_rad_median": float(
                    np.median(phase_at_reference)
                ),
                "equivalent_frequency_rms_hz_median_p10_p90": np.percentile(
                    frequency_rms_hz, [50, 10, 90]
                ).tolist(),
            },
        }

    plot_ratio = np.array(
        [float(row[f"background_ratio_{PLOT_CUTOFF_MPS}_db"]) for row in rows]
    )
    params = fit(plot_ratio, signal_db, range_m, (1.0, 2.0))
    delay_scaled_db = signal_db + 20 * np.log10(range_m / REFERENCE_RANGE_M)
    figure, axes = plt.subplots(
        1, 2, figsize=(11, 4.6), sharey=True, constrained_layout=True
    )
    for name in ("outbound", "inbound"):
        mask = leg == name
        axes[0].scatter(signal_db[mask], plot_ratio[mask], s=18, alpha=0.75, label=name)
        axes[1].scatter(
            delay_scaled_db[mask], plot_ratio[mask], s=18, alpha=0.75, label=name
        )
    curve_x = np.linspace(delay_scaled_db.min() - 1, delay_scaled_db.max() + 1, 200)
    axes[1].plot(
        curve_x,
        predicted_ratio_db(params, curve_x, np.full(curve_x.shape, REFERENCE_RANGE_M)),
        color="black",
        linewidth=1.5,
        label="fit, excess ∝ S·R²",
    )
    axes[0].set(
        xlabel="Mean-RX target-cell power S [dB, arbitrary reference]",
        ylabel="Target-range background / same-range control [dB]",
        title="Against target power",
    )
    axes[1].set(
        xlabel="S + 20 log10(R / 30 m) [dB]",
        title="Against target power × (range / 30 m)²",
    )
    for axis in axes:
        axis.axhline(0, color="black", linestyle=":", linewidth=0.8)
        axis.grid(alpha=0.3)
        axis.legend()
    figure.suptitle(
        f"Remote-Doppler background at the reflector's range, |v| ≥ {PLOT_CUTOFF_MPS} m/s"
    )
    figure.savefig(args.output / "pedestal_scaling.png", dpi=160)
    plt.close(figure)

    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.output / 'pedestal_scaling.png'}")


if __name__ == "__main__":
    main()
