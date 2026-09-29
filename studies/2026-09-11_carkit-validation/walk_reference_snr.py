"""Measured per-RX SNR reference from target-free same-range background.

Signal: each RX's power at the common target cell from walk_extract.py.
Background N0: the same RX's power within +/-1 native range bin and +/-1 m/s of
the target's range and velocity, pooled over control CPIs without the
reflector near that range (carkit_common.control_frames). Primary estimator:
median / ln 2, robust to the traffic in the post-walk CPIs.

Headline convention: average the RX SNRs linearly within each CPI, scale each
CPI by R^-4 to 100 m and from the 11.27 dBsm walking reflector to the 10 dBsm
used by the model, then average in dB over CPIs (a fixed-slope fit). Other
averaging conventions and the far-quarter noise reference are reported
alongside, as is the step-by-step reconciliation with the report's 36.57 dB.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from carkit_common import (
    GENERATED_DIR,
    N_RX,
    RCS_CORRECTION_DB,
    REFERENCE_RANGE_M,
    REPORT_SNR_DB,
    BoolArray,
    FloatArray,
    IntArray,
    control_frames,
    data_argument,
    db,
    leg_frames,
    leg_of,
    load_capture,
    native_doppler,
    range_spectrum,
    read_track,
    write_summary,
)
from walk_model import model_snr_db

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DOPPLER_HALF_WIDTH_MPS = 1.0
UPPER_TRIM_FRACTION = 0.10
INBOUND_RANGE_BANDS_M = ((15.0, 27.0), (27.0, 38.0), (38.0, 52.0))


def corrected_upper_trim_mean(values: FloatArray, fraction: float) -> FloatArray:
    """Upper-trimmed mean corrected to the mean of exponential noise power."""
    count = int(math.floor((1 - fraction) * values.shape[0]))
    kept = np.partition(values, count - 1, axis=0)[:count]
    threshold = -math.log(fraction)
    exponential_factor = (1 - (threshold + 1) * fraction) / (1 - fraction)
    return np.asarray(np.mean(kept, axis=0) / exponential_factor, dtype=float)


def estimate_background(
    data: Path | None, target_range: FloatArray, target_velocity: FloatArray
) -> tuple[dict[str, FloatArray], IntArray, IntArray]:
    """Pool same-range, near-velocity control powers for each target CPI."""
    capture = load_capture(data)
    track_range = read_track().range_m
    range_axis = capture.range_axis()
    native_velocity = capture.native_velocity()
    # +/-1 native bin inclusive: offsets -4..4 on the fourfold padded grid. The
    # half-width sits between grid points so rounding cannot drop the edges.
    range_half_width_m = 4.5 * float(range_axis[1] - range_axis[0])
    range_masks = [np.abs(range_axis - r) <= range_half_width_m for r in target_range]
    velocity_masks = [
        np.abs(native_velocity - v) <= DOPPLER_HALF_WIDTH_MPS for v in target_velocity
    ]
    controls = np.array([control_frames(track_range, r) for r in target_range])
    samples: list[list[FloatArray]] = [[] for _ in target_range]
    for frame in range(capture.n_frames):
        users = np.flatnonzero(controls[:, frame])
        if users.size == 0:
            continue
        power = np.abs(native_doppler(range_spectrum(capture.load(frame)))) ** 2
        for index in users:
            patch = power[velocity_masks[index]][:, range_masks[index], :]
            samples[index].append(patch.reshape(-1, N_RX))
        if frame % 20 == 0:
            print(f"control CPI {frame}/{capture.n_frames - 1}", flush=True)
    pooled = [np.concatenate(pieces) for pieces in samples]
    estimators = {
        "median_over_ln2": np.array(
            [np.median(v, axis=0) / math.log(2) for v in pooled]
        ),
        "upper_10_percent_trimmed": np.array(
            [corrected_upper_trim_mean(v, UPPER_TRIM_FRACTION) for v in pooled]
        ),
        "arithmetic_mean": np.array([np.mean(v, axis=0) for v in pooled]),
    }
    control_counts = np.asarray(np.sum(controls, axis=1), dtype=np.int64)
    pooled_counts = np.array([v.shape[0] for v in pooled], dtype=np.int64)
    return estimators, control_counts, pooled_counts


def to_reference_db(range_m: FloatArray) -> FloatArray:
    """R^-4 scaling to 100 m and RCS scaling to 10 dBsm."""
    return np.asarray(40 * np.log10(range_m / REFERENCE_RANGE_M) - RCS_CORRECTION_DB)


def statistics(snr: FloatArray, range_m: FloatArray) -> dict[str, Any]:
    """Averaging conventions for linear per-RX SNRs [CPI, RX] at 100 m, 10 dBsm."""
    scale = to_reference_db(range_m)
    per_frame = db(np.mean(snr, axis=1)) + scale
    per_rx = db(snr) + scale[:, None]
    return {
        "count": int(snr.shape[0]),
        "linear_rx_mean_then_db_mean_over_cpis": float(np.mean(per_frame)),
        "linear_rx_mean_then_median_over_cpis": float(np.median(per_frame)),
        "linear_mean_over_rx_and_cpis": float(db(np.mean(10 ** (per_frame / 10)))),
        "db_mean_over_rx_and_cpis": float(np.mean(per_rx)),
        "per_cpi_std_db": float(np.std(per_frame)),
        "per_cpi_p10_p90_db": np.percentile(per_frame, [10, 90]).tolist(),
        "per_rx_db_mean_over_cpis": np.mean(per_rx, axis=0).tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "reference_snr")
    args = parser.parse_args()

    track = read_track()
    frames = np.concatenate([leg_frames("outbound"), leg_frames("inbound")])
    target_range = track.range_m[frames]
    target_velocity = track.velocity_mps[frames]
    signal = track.rx_signal_power[frames]
    estimators, control_cpis, pooled_samples = estimate_background(
        args.data, target_range, target_velocity
    )
    background = estimators["median_over_ln2"]
    snr = signal / background
    far_snr = 10 ** (track.rx_far_snr_db[frames] / 10)

    masks: dict[str, BoolArray] = {
        "inbound": np.array([leg_of(int(f)) == "inbound" for f in frames]),
        "selected": track.selected[frames],
        "outbound": np.array([leg_of(int(f)) == "outbound" for f in frames]),
    }
    model_db = model_snr_db()
    headline_key = "linear_rx_mean_then_db_mean_over_cpis"
    target_free = {
        name: statistics(snr[m], target_range[m]) for name, m in masks.items()
    }
    far_quarter = {
        name: statistics(far_snr[m], target_range[m]) for name, m in masks.items()
    }

    comparison = {
        "inbound, target-free (headline)": target_free["inbound"][headline_key],
        "selected, target-free": target_free["selected"][headline_key],
        "inbound, far-quarter noise": far_quarter["inbound"][headline_key],
    }

    selected = masks["selected"]
    reproduction = float(
        np.mean(
            track.magnitude_sum_snr_db[frames][selected]
            + 40 * np.log10(target_range[selected] / REFERENCE_RANGE_M)
        )
    )
    walking = RCS_CORRECTION_DB
    steps = [
        ("report, 33 selected CPIs", REPORT_SNR_DB),
        ("reproduction, 37 selected CPIs", reproduction),
        (
            "magnitude sum -> linear mean of RX power",
            far_quarter["selected"][headline_key] + walking,
        ),
        (
            "far-quarter -> target-free local noise",
            target_free["selected"][headline_key] + walking,
        ),
        ("reflector RCS 10 -> 11.27 dBsm", target_free["selected"][headline_key]),
        ("all 39 inbound CPIs", target_free["inbound"][headline_key]),
    ]
    breakdown = [
        {
            "step": name,
            "value_db": value,
            "change_db": None if index == 0 else value - steps[index - 1][1],
        }
        for index, (name, value) in enumerate(steps)
    ]

    inbound = masks["inbound"]
    per_frame = db(np.mean(snr, axis=1)) + to_reference_db(target_range)
    by_band = {}
    for low, high in INBOUND_RANGE_BANDS_M:
        band = inbound & (target_range >= low) & (target_range < high)
        by_band[f"{low:g}-{high:g} m"] = {
            "count": int(np.count_nonzero(band)),
            "mean_db": float(np.mean(per_frame[band])),
            "median_db": float(np.median(per_frame[band])),
            "std_db": float(np.std(per_frame[band])),
        }

    summary = {
        "definition": {
            "background": "median / ln 2 of same-range controls",
            "range_half_width": "one native range bin",
            "doppler_half_width_mps": DOPPLER_HALF_WIDTH_MPS,
            "scaling": "R^-4 to 100 m; 11.27 -> 10 dBsm",
            "headline": headline_key,
            "control_cpis_min_max": [int(control_cpis.min()), int(control_cpis.max())],
            "pooled_powers_min_max": [
                int(pooled_samples.min()),
                int(pooled_samples.max()),
            ],
        },
        "model_db": model_db,
        "comparison": {
            name: {"measured_db": value, "residual_db": value - model_db}
            for name, value in comparison.items()
        },
        "breakdown_from_report": breakdown,
        "inbound_by_range_band": by_band,
        "target_free": target_free,
        "far_quarter": far_quarter,
        "background_estimator_sensitivity_inbound_db": {
            name: statistics(signal[inbound] / values[inbound], target_range[inbound])[
                headline_key
            ]
            for name, values in estimators.items()
        },
    }
    write_summary(args.output, summary)

    with (args.output / "per_frame.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        channels = range(1, N_RX + 1)
        writer.writerow(
            [
                "frame",
                "leg",
                "selected",
                "range_m",
                "velocity_mps",
                "control_cpis",
                "pooled_powers",
                "snr_at_100m_10dbsm_db",
                *[f"rx{channel}_background_power" for channel in channels],
                *[f"rx{channel}_snr_db" for channel in channels],
            ]
        )
        for index, frame in enumerate(frames):
            writer.writerow(
                [
                    int(frame),
                    leg_of(int(frame)),
                    bool(selected[index]),
                    target_range[index],
                    target_velocity[index],
                    int(control_cpis[index]),
                    int(pooled_samples[index]),
                    per_frame[index],
                    *background[index],
                    *db(snr[index]),
                ]
            )

    figure, axes = plt.subplots(2, 1, figsize=(9, 8), constrained_layout=True)
    for leg in ("outbound", "inbound"):
        mask = masks[leg]
        axes[0].plot(
            target_range[mask], db(np.mean(background[mask], axis=1)), ".", label=leg
        )
        axes[1].plot(target_range[mask], per_frame[mask], ".", label=leg)
    axes[0].set(
        xlabel="Target range [m]",
        ylabel="Background power [dB, arbitrary reference]",
        title="Target-free background at the target's range and velocity",
    )
    axes[1].axhline(model_db, color="black", linestyle="--", label="model, 10 dBsm")
    axes[1].set(
        xlabel="Target range [m]",
        ylabel="SNR scaled to 100 m and 10 dBsm [dB]",
        title="Linear RX mean; measured 11.27 dBsm reflector scaled to 10 dBsm",
    )
    for axis in axes:
        axis.grid(alpha=0.3)
        axis.legend()
    figure.savefig(args.output / "reference_snr.png", dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
