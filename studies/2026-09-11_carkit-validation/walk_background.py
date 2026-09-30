"""Characterize the additive background versus range, time and RX channel.

Uses remote Doppler bins (|v| >= 10 m/s) of every CPI, with native range and
Doppler bins. Three questions:

* Spectrum: how the background varies with range (beat frequency), relative to
  the farthest range quarter. Robust per-CPI levels are medians over Doppler
  divided by ln 2, the mean of exponential (complex Gaussian) power.
* Time: whether it is stable over the recording. CPIs whose mean remote power
  exceeds the robust level by more than MOVING_RETURN_DB in any range band
  contain moving returns (traffic, the walker) rather than background only.
* Channels: whether the excess at low beat frequencies is correlated between
  RX channels. A common source such as LO phase noise on leakage or nearby
  returns would be; receiver noise and IF gain shaping would not. This uses
  post-walk CPIs free of moving returns.
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
    LAST_TRACKED_FRAME,
    N_RX,
    SPEED_OF_LIGHT,
    Capture,
    FloatArray,
    data_argument,
    db,
    load_capture,
    native_doppler,
    range_spectrum,
    write_summary,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REMOTE_ABS_VELOCITY_MPS = 10.0
FAR_RANGE_FRACTION = 0.75
BANDS_M = ((13.0, 20.0), (20.0, 30.0), (30.0, 50.0), (75.0, 150.0))
MOVING_RETURN_DB = 0.2
REPORT_RANGES_M = (5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 100.0, 200.0, 300.0)


def band_label(band: tuple[float, float]) -> str:
    return f"{band[0]:g}_{band[1]:g}m"


def accumulate(capture: Capture) -> dict[str, Any]:
    """Per-CPI robust/mean remote power and spatial second moments per range."""
    range_axis = capture.range_axis(padding=1)
    remote = np.abs(capture.native_velocity()) >= REMOTE_ABS_VELOCITY_MPS
    n = capture.n_frames
    robust = np.empty((n, range_axis.size, N_RX))
    mean = np.empty((n, range_axis.size, N_RX))
    moments = np.empty((n, range_axis.size, N_RX, N_RX), dtype=complex)
    for frame in range(n):
        cells = native_doppler(range_spectrum(capture.load(frame), padding=1))[remote]
        power = np.abs(cells) ** 2
        robust[frame] = np.median(power, axis=0) / math.log(2)
        mean[frame] = np.mean(power, axis=0)
        moments[frame] = np.einsum("drk,drl->rkl", cells, cells.conj()) / len(cells)
        if frame % 20 == 0 or frame + 1 == n:
            print(f"background {frame + 1}/{n} CPIs", flush=True)
    return {
        "range_m": range_axis,
        "robust": robust,
        "mean": mean,
        "moments": moments,
        "samples_per_cpi": int(np.count_nonzero(remote)),
    }


def band_excess_db(levels: FloatArray, range_m: FloatArray) -> FloatArray:
    """RX-mean level in each band relative to the far quarter, per CPI [dB]."""
    far = range_m >= FAR_RANGE_FRACTION * range_m[-1]
    reference = np.mean(levels[:, far, :], axis=(1, 2))
    columns = []
    for low, high in BANDS_M:
        band = (range_m >= low) & (range_m < high)
        columns.append(db(np.mean(levels[:, band, :], axis=(1, 2)) / reference))
    return np.stack(columns, axis=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "background")
    args = parser.parse_args()

    capture = load_capture(args.data)
    acc = accumulate(capture)
    range_m: FloatArray = acc["range_m"]
    far = range_m >= FAR_RANGE_FRACTION * range_m[-1]
    frames = np.arange(capture.n_frames)

    robust_excess = band_excess_db(acc["robust"], range_m)
    mean_excess = band_excess_db(acc["mean"], range_m)
    moving = np.any(mean_excess - robust_excess > MOVING_RETURN_DB, axis=1)
    clean_post_walk = (frames > LAST_TRACKED_FRAME) & ~moving

    # Background spectrum: median over all CPIs of robust levels.
    spectrum = np.median(acc["robust"], axis=0)
    per_rx_db = db(spectrum / np.mean(spectrum[far], axis=0))
    rx_mean_db = db(np.mean(spectrum, axis=1) / np.mean(spectrum[far]))

    # Spatial second moments over clean post-walk CPIs.
    moments = np.mean(acc["moments"][clean_post_walk], axis=0)
    power = np.real(np.einsum("rkk->rk", moments))
    pairs = [(k, m) for k in range(N_RX) for m in range(k + 1, N_RX)]
    coherence = np.array(
        [
            np.mean(
                [
                    abs(moments[r, k, m]) ** 2 / (power[r, k] * power[r, m])
                    for k, m in pairs
                ]
            )
            for r in range(range_m.size)
        ]
    )
    eigenvalues = np.linalg.eigvalsh(moments)
    largest_fraction = eigenvalues[:, -1] / np.sum(eigenvalues, axis=1)
    clean_excess = np.mean(power, axis=1) / np.mean(power[far])
    # If the excess over the far-quarter floor were one component common to all
    # channels, pairwise squared coherence would be ((e - 1) / e)**2.
    common_coherence = np.clip((clean_excess - 1) / clean_excess, 0, None) ** 2

    def at(values: FloatArray, target_m: float) -> float:
        return float(values[int(np.argmin(np.abs(range_m - target_m)))])

    walk_band = (range_m >= 15) & (range_m <= 51)
    summary = {
        "definition": {
            "remote_abs_velocity_mps": REMOTE_ABS_VELOCITY_MPS,
            "range_bins": "native (unpadded), periodic Blackman",
            "robust_level": "median power over remote Doppler bins / ln 2",
            "reference": "farthest range quarter",
            "moving_return_threshold_db": MOVING_RETURN_DB,
            "samples_per_cpi_and_range": acc["samples_per_cpi"],
        },
        "spectrum_rx_mean_excess_db": {
            f"{target:g}m": at(rx_mean_db, target) for target in REPORT_RANGES_M
        },
        "spectrum_per_rx_excess_db_at_15m": per_rx_db[
            int(np.argmin(np.abs(range_m - 15)))
        ].tolist(),
        "beat_frequency_mhz_at_15_51m": (
            capture.beat_frequency_hz([15, 51]) / 1e6
        ).tolist(),
        "robust_band_excess_db_median_over_cpis": {
            band_label(band): float(np.median(robust_excess[:, index]))
            for index, band in enumerate(BANDS_M)
        },
        "robust_band_excess_db_p10_p90_over_cpis": {
            band_label(band): np.percentile(robust_excess[:, index], [10, 90]).tolist()
            for index, band in enumerate(BANDS_M)
        },
        "cpis_with_moving_returns": frames[moving].tolist(),
        "clean_post_walk_cpis": frames[clean_post_walk].tolist(),
        "cross_rx": {
            "walk_band_15_51m_mean_squared_coherence": float(
                np.mean(coherence[walk_band])
            ),
            "far_quarter_mean_squared_coherence": float(np.mean(coherence[far])),
            "walk_band_if_excess_were_common": float(
                np.mean(common_coherence[walk_band])
            ),
            "walk_band_largest_eigenvalue_fraction": float(
                np.mean(largest_fraction[walk_band])
            ),
            "far_quarter_largest_eigenvalue_fraction": float(
                np.mean(largest_fraction[far])
            ),
            "independent_channels_eigenvalue_fraction": 1 / N_RX,
        },
    }
    write_summary(args.output, summary)

    with (args.output / "per_cpi.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                *[f"robust_excess_{band_label(band)}_db" for band in BANDS_M],
                *[f"mean_excess_{band_label(band)}_db" for band in BANDS_M],
                "moving_returns",
            ]
        )
        for frame in frames:
            writer.writerow(
                [
                    int(frame),
                    *robust_excess[frame],
                    *mean_excess[frame],
                    bool(moving[frame]),
                ]
            )

    figure, axes = plt.subplots(3, 1, figsize=(10, 11), constrained_layout=True)
    for channel in range(N_RX):
        axes[0].plot(
            range_m,
            per_rx_db[:, channel],
            linewidth=1,
            alpha=0.6,
            label=f"RX{channel + 1}",
        )
    axes[0].plot(range_m, rx_mean_db, color="black", linewidth=2, label="RX mean")
    axes[0].axvspan(15, 51, color="tab:orange", alpha=0.12, label="walk ranges")
    axes[0].axvspan(
        range_m[far][0], range_m[-1], color="0.5", alpha=0.12, label="far quarter"
    )
    axes[0].set(
        ylim=(-3, 3),
        ylabel="Background relative to far quarter [dB]",
        title="Background spectrum, median over CPIs, |v| >= 10 m/s",
    )
    scale = 2 * capture.slope_hz_per_s / SPEED_OF_LIGHT / 1e6
    top = axes[0].secondary_xaxis(
        "top",
        functions=(lambda r: np.asarray(r) * scale, lambda f: np.asarray(f) / scale),
    )
    top.set_xlabel("Beat frequency [MHz]")
    axes[0].legend(ncol=4, fontsize="small")

    for frame in frames[moving]:
        axes[1].axvspan(frame - 0.5, frame + 0.5, color="0.85", linewidth=0)
    for index, band in enumerate(BANDS_M):
        line = axes[1].plot(
            frames,
            mean_excess[:, index],
            linewidth=1,
            label=f"{band[0]:g}-{band[1]:g} m",
        )
        axes[1].plot(
            frames,
            robust_excess[:, index],
            linestyle="--",
            color=line[0].get_color(),
            linewidth=1,
        )
    axes[1].set(
        ylim=(-0.5, 4.0),
        xlabel="CPI",
        ylabel="Band level relative to far quarter [dB]",
        title=(
            "Per-CPI band levels: mean (solid), robust median (dashed); "
            "grey = moving returns, clipped"
        ),
    )
    axes[1].legend(ncol=2, fontsize="small")

    axes[2].plot(range_m, coherence, label="measured, clean post-walk CPIs")
    axes[2].plot(
        range_m,
        common_coherence,
        linestyle="--",
        label="if the excess were common to all RX",
    )
    axes[2].axhline(
        np.mean(coherence[far]), color="0.5", linestyle=":", label="far-quarter level"
    )
    axes[2].set(
        yscale="log",
        ylim=(1e-5, 1),
        xlabel="Range [m]",
        ylabel="Mean pairwise |coherence|²",
        title="Cross-RX coherence of the background",
    )
    axes[2].legend(fontsize="small")
    for axis in axes[[0, 2]]:
        axis.set(xlim=(0, range_m[-1]))
    for axis in axes:
        axis.grid(alpha=0.3)
    axes[0].set_xlabel("Range [m]")
    figure.savefig(args.output / "background.png", dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
