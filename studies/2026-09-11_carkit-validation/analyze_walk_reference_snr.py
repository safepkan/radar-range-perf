"""Estimate walk SNR from target-free same-range background controls.

The signal is the common range-Doppler cell already extracted from the raw ADC
data by analyze_walk_adc.py.  This script recomputes background spectra from raw
samples and estimates the additive baseline at each target's range and Doppler
from other CPIs in which the walking reflector is absent from that range.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.fft import fft, rfft
from scipy.signal.windows import blackman

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FloatArray = npt.NDArray[np.float64]

SPEED_OF_LIGHT = 299792458.0
CARRIER_HZ = 76.374237e9
RANGE_PADDING = 4
LEGS = {"outbound45": (26, 70), "inbound39": (89, 127)}
REFERENCE_RANGE_M = 100.0
PROVISIONAL_RCS_CORRECTION_DB = 1.27
MODEL_SNR_DB = 32.67
CONTROL_START_FRAME = 26
TRACKED_REFLECTOR_LAST_FRAME = 160
CONTROL_EXCLUSION_M = 8.0
RANGE_HALF_WIDTH_M = 299792458.0 / (2 * 100781248.0)
DOPPLER_HALF_WIDTH_MPS = 1.0
UPPER_TRIM_FRACTION = 0.10


def db(value: npt.ArrayLike) -> FloatArray:
    """Convert positive power-like values to dB."""
    return np.asarray(10 * np.log10(np.maximum(value, np.finfo(float).tiny)))


def corrected_upper_trim_mean(values: FloatArray, fraction: float) -> FloatArray:
    """Upper-trim powers and correct the mean for exponential noise power."""
    count = int(math.floor((1 - fraction) * values.shape[0]))
    kept = np.partition(values, count - 1, axis=0)[:count]
    threshold = -math.log(fraction)
    exponential_factor = (1 - (threshold + 1) * fraction) / (1 - fraction)
    return np.asarray(np.mean(kept, axis=0) / exponential_factor, dtype=float)


def summarize(
    snr: FloatArray,
    target_range: FloatArray,
    masks: dict[str, npt.NDArray[np.bool_]],
) -> dict[str, Any]:
    """Summarize explicit spatial and temporal averaging conventions."""
    result: dict[str, Any] = {}
    correction = 40 * np.log10(target_range / REFERENCE_RANGE_M)
    per_frame_linear_rx = np.mean(snr, axis=1)
    per_frame_anchor = db(per_frame_linear_rx) + correction
    per_rx_anchor = db(snr) + correction[:, None]
    for name, mask in masks.items():
        normalized_linear = per_frame_linear_rx[mask] * 10 ** (correction[mask] / 10)
        raw: dict[str, Any] = {
            "count": int(np.count_nonzero(mask)),
            "mean_db_over_rx_and_frames": float(np.mean(per_rx_anchor[mask])),
            "linear_rx_mean_then_mean_db_over_frames": float(
                np.mean(per_frame_anchor[mask])
            ),
            "linear_rx_mean_then_median_db_over_frames": float(
                np.median(per_frame_anchor[mask])
            ),
            "linear_rx_mean_then_p10_p90_db_over_frames": np.percentile(
                per_frame_anchor[mask], [10, 90]
            ).tolist(),
            "linear_mean_over_rx_and_range_normalized_frames_db": float(
                db(np.mean(normalized_linear))
            ),
        }
        result[name] = {
            "walking_reflector_11p27_dbsm": raw,
            "normalized_to_10_dbsm": {
                key: (
                    value
                    if key == "count"
                    else (
                        [item - PROVISIONAL_RCS_CORRECTION_DB for item in value]
                        if isinstance(value, list)
                        else value - PROVISIONAL_RCS_CORRECTION_DB
                    )
                )
                for key, value in raw.items()
            },
        }
        normalized = result[name]["normalized_to_10_dbsm"]
        result[name]["walking_reflector_11p27_dbsm"]["per_rx_mean_db"] = np.mean(
            per_rx_anchor[mask], axis=0
        ).tolist()
        normalized["per_rx_mean_db"] = (
            np.mean(per_rx_anchor[mask], axis=0) - PROVISIONAL_RCS_CORRECTION_DB
        ).tolist()
        normalized["model_residual_for_linear_rx_mean_then_mean_db"] = (
            normalized["linear_rx_mean_then_mean_db_over_frames"] - MODEL_SNR_DB
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent / "generated/walk_adc/per_frame.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "generated/reference_snr",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    with args.csv.open() as stream:
        rows = list(csv.DictReader(stream))
    all_range = np.array([float(row["range_m"]) for row in rows])
    all_velocity = np.array([float(row["velocity_mps"]) for row in rows])
    all_selected = np.array([row["selected"] == "True" for row in rows])
    signal_power = np.array(
        [
            [
                10 ** (float(row[f"rx{channel}_signal_power_db"]) / 10)
                for channel in range(1, 9)
            ]
            for row in rows
        ]
    )
    target_frames = np.concatenate(
        [np.arange(first, last + 1) for first, last in LEGS.values()]
    )
    target_range = all_range[target_frames]
    target_velocity = all_velocity[target_frames]
    target_signal = signal_power[target_frames]

    metadata = json.loads((args.data / "cpi_0000000000.json").read_text())
    shape = tuple(int(value) for value in metadata["sample_format"]["shape"])
    waveform = metadata["waveform"]
    sample_rate_hz = float(waveform["sample_rate_msps"]) * 1e6
    pri_s = float(waveform["chirp_period_us"]) * 1e-6
    slope = float(waveform["slope_hz_per_s"])
    range_axis = np.asarray(
        np.fft.rfftfreq(RANGE_PADDING * shape[1], 1 / sample_rate_hz)
        * SPEED_OF_LIGHT
        / (2 * slope),
        dtype=float,
    )
    velocity_axis = np.asarray(
        np.fft.fftfreq(shape[0], pri_s) * SPEED_OF_LIGHT / (2 * CARRIER_HZ),
        dtype=float,
    )
    range_masks = [
        np.abs(range_axis - center) <= RANGE_HALF_WIDTH_M for center in target_range
    ]
    velocity_masks = [
        np.abs(velocity_axis - center) <= DOPPLER_HALF_WIDTH_MPS
        for center in target_velocity
    ]
    samples: list[list[FloatArray]] = [[] for _ in target_frames]
    control_cpis = np.zeros(target_frames.size, dtype=int)
    range_window = np.asarray(blackman(shape[1], sym=False), dtype=float)
    doppler_window = np.asarray(blackman(shape[0], sym=False), dtype=float)

    for frame, row in enumerate(rows):
        if frame < CONTROL_START_FRAME:
            continue
        frame_metadata = json.loads((args.data / f"cpi_{frame:010d}.json").read_text())
        raw = (
            np.fromfile(args.data / frame_metadata["file"], dtype="<i2")
            .reshape(shape)
            .astype(float)
        )
        range_spectrum = (
            rfft(
                raw * range_window[None, :, None],
                n=RANGE_PADDING * shape[1],
                axis=1,
            )
            / range_window.sum()
        )
        rd = (
            fft(range_spectrum * doppler_window[:, None, None], axis=0)
            / doppler_window.sum()
        )
        power = np.abs(rd) ** 2
        for index in range(target_frames.size):
            reflector_nearby = (
                frame <= TRACKED_REFLECTOR_LAST_FRAME
                and abs(all_range[frame] - target_range[index]) <= CONTROL_EXCLUSION_M
            )
            if reflector_nearby:
                continue
            patch = power[velocity_masks[index]][:, range_masks[index], :]
            samples[index].append(np.asarray(patch.reshape(-1, shape[2]), dtype=float))
            control_cpis[index] += 1
        if frame % 20 == 0:
            print(f"processed control CPI {frame}/{len(rows) - 1}", flush=True)

    estimators = {
        "median_exponential_corrected": np.empty_like(target_signal),
        "upper_10_percent_trim_exponential_corrected": np.empty_like(target_signal),
        "arithmetic_mean": np.empty_like(target_signal),
    }
    sample_count = np.empty(target_frames.size, dtype=int)
    for index, pieces in enumerate(samples):
        values = np.concatenate(pieces, axis=0)
        sample_count[index] = values.shape[0]
        estimators["median_exponential_corrected"][index] = np.median(
            values, axis=0
        ) / math.log(2)
        estimators["upper_10_percent_trim_exponential_corrected"][index] = (
            corrected_upper_trim_mean(values, UPPER_TRIM_FRACTION)
        )
        estimators["arithmetic_mean"][index] = np.mean(values, axis=0)

    masks = {
        "selected37": all_selected[target_frames],
        **{
            name: (target_frames >= bounds[0]) & (target_frames <= bounds[1])
            for name, bounds in LEGS.items()
        },
    }
    summary: dict[str, Any] = {
        "definition": {
            "range_half_width_m": RANGE_HALF_WIDTH_M,
            "doppler_half_width_mps": DOPPLER_HALF_WIDTH_MPS,
            "control_start_frame": CONTROL_START_FRAME,
            "tracked_reflector_last_frame": TRACKED_REFLECTOR_LAST_FRAME,
            "control_exclusion_m": CONTROL_EXCLUSION_M,
            "primary_estimator": "median_exponential_corrected",
            "reference_range_m": REFERENCE_RANGE_M,
            "provisional_rcs_correction_db": PROVISIONAL_RCS_CORRECTION_DB,
        },
        "control_cpis_min_max": [int(control_cpis.min()), int(control_cpis.max())],
        "samples_per_target_min_max": [
            int(sample_count.min()),
            int(sample_count.max()),
        ],
        "estimators": {},
    }
    for name, baseline in estimators.items():
        summary["estimators"][name] = summarize(
            target_signal / baseline, target_range, masks
        )
    primary = estimators["median_exponential_corrected"]
    primary_snr_db = db(target_signal / primary)
    correction = 40 * np.log10(target_range / REFERENCE_RANGE_M)
    per_frame_anchor = (
        db(np.mean(target_signal / primary, axis=1))
        + correction
        - PROVISIONAL_RCS_CORRECTION_DB
    )

    figure, axes = plt.subplots(2, 1, figsize=(9, 8), constrained_layout=True)
    for leg, mask in {
        name: (target_frames >= bounds[0]) & (target_frames <= bounds[1])
        for name, bounds in LEGS.items()
    }.items():
        axes[0].plot(
            target_range[mask],
            db(np.mean(primary[mask], axis=1)),
            ".",
            label=leg,
        )
        axes[1].plot(target_range[mask], per_frame_anchor[mask], ".", label=leg)
    axes[0].set(
        xlabel="Target range [m]",
        ylabel="Target-free baseline power [dB, arbitrary reference]",
        title="Same-range, near-target-Doppler background controls",
    )
    axes[1].axhline(MODEL_SNR_DB, color="black", linestyle="--", label="model")
    axes[1].set(
        xlabel="Target range [m]",
        ylabel="R^-4 normalized SNR at 100 m [dB]",
        title="Linear RX mean, provisional 10 dBsm normalization",
    )
    for axis in axes:
        axis.grid(alpha=0.3)
        axis.legend()
    figure.savefig(args.output / "reference_snr.png", dpi=160)
    plt.close(figure)

    with (args.output / "per_frame.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "leg",
                "selected",
                "range_m",
                "velocity_mps",
                "control_cpis",
                "background_samples",
                *[f"rx{channel}_baseline_power" for channel in range(1, 9)],
                *[f"rx{channel}_snr_db" for channel in range(1, 9)],
            ]
        )
        for index, frame in enumerate(target_frames):
            leg = next(
                name for name, bounds in LEGS.items() if bounds[0] <= frame <= bounds[1]
            )
            writer.writerow(
                [
                    frame,
                    leg,
                    all_selected[frame],
                    target_range[index],
                    target_velocity[index],
                    control_cpis[index],
                    sample_count[index],
                    *primary[index],
                    *primary_snr_db[index],
                ]
            )
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
