"""Track the walking reflector and extract per-RX target cells from raw ADC data.

For each CPI, one common range-Doppler cell is located from the mean of per-RX
powers normalized by far-quarter noise, within 3-70 m and 0.75-12 m/s. Every
per-RX value is read at that cell; RX channels are never summed coherently.

Also reproduces the report's statistic: an RX magnitude sum over far-quarter
noise, with its local upper-tail selection (15-51 m, within 6 dB of the local
R^-4-corrected maximum within +/-5 m). The headline comparison instead uses the
target-free background from walk_reference_snr.py.

Run first; later scripts read generated/walk/extract/per_frame.csv.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib
import numpy as np

from carkit_common import (
    N_RX,
    FloatArray,
    db,
    write_summary,
)
from walk_common import (
    FAR_RANGE_FRACTION,
    NOISE_ABS_VELOCITY_MIN_MPS,
    GENERATED_DIR,
    LEGS,
    REFERENCE_RANGE_M,
    REPORT_SNR_DB,
    BoolArray,
    Capture,
    data_argument,
    leg_of,
    load_capture,
    native_doppler,
    padded_doppler,
    range_spectrum,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SEARCH_RANGE_M = (3.0, 70.0)
SEARCH_ABS_VELOCITY_MPS = (0.75, 12.0)
SELECTION_RANGE_M = (15.0, 51.0)
SELECTION_NEIGHBORHOOD_M = 5.0
SELECTION_TOLERANCE_DB = 6.0


def extract(capture: Capture) -> dict[str, FloatArray]:
    """Locate the common target cell in every CPI and read per-RX values."""
    range_axis = capture.range_axis()
    velocity_axis = capture.padded_velocity()
    native_velocity = capture.native_velocity()
    search_range = np.flatnonzero(
        (range_axis >= SEARCH_RANGE_M[0]) & (range_axis <= SEARCH_RANGE_M[1])
    )
    abs_velocity = np.abs(velocity_axis)
    search_velocity = np.flatnonzero(
        (abs_velocity >= SEARCH_ABS_VELOCITY_MPS[0])
        & (abs_velocity <= SEARCH_ABS_VELOCITY_MPS[1])
    )
    far = range_axis >= FAR_RANGE_FRACTION * range_axis[-1]
    noise_velocity = np.abs(native_velocity) >= NOISE_ABS_VELOCITY_MIN_MPS

    n = capture.n_frames
    out = {
        "range_m": np.empty(n),
        "velocity_mps": np.empty(n),
        "locator_snr_db": np.empty(n),
        "magnitude_sum_snr_db": np.empty(n),
        "rx_signal_power_db": np.empty((n, N_RX)),
        "rx_far_noise_power_db": np.empty((n, N_RX)),
    }
    for frame in range(n):
        spectrum = range_spectrum(capture.load(frame))
        noise_cells = native_doppler(spectrum)[noise_velocity][:, far, :]
        far_noise = np.mean(np.abs(noise_cells) ** 2, axis=(0, 1))
        far_magnitude_sum_power = float(
            np.mean(np.sum(np.abs(noise_cells), axis=2) ** 2)
        )

        candidates = padded_doppler(spectrum[:, search_range, :])[search_velocity]
        locator = np.mean(np.abs(candidates) ** 2 / far_noise, axis=2)
        velocity_index, range_index = np.unravel_index(
            int(np.argmax(locator)), locator.shape
        )
        amplitude = np.abs(candidates[velocity_index, range_index, :])

        out["range_m"][frame] = range_axis[search_range[range_index]]
        out["velocity_mps"][frame] = velocity_axis[search_velocity[velocity_index]]
        out["locator_snr_db"][frame] = db(locator[velocity_index, range_index])
        out["magnitude_sum_snr_db"][frame] = 20 * math.log10(
            float(np.sum(amplitude)) / math.sqrt(far_magnitude_sum_power)
        )
        out["rx_signal_power_db"][frame] = db(amplitude**2)
        out["rx_far_noise_power_db"][frame] = db(far_noise)
        if frame % 20 == 0 or frame + 1 == n:
            print(f"extracted {frame + 1}/{n} CPIs", flush=True)
    return out


def report_selection(
    range_m: FloatArray, magnitude_sum_snr_db: FloatArray
) -> BoolArray:
    """The report's local R^-4-corrected upper-tail selection."""
    eligible = (range_m >= SELECTION_RANGE_M[0]) & (range_m <= SELECTION_RANGE_M[1])
    corrected = magnitude_sum_snr_db + 40 * np.log10(range_m)
    selected = np.zeros(range_m.shape, dtype=bool)
    for index in np.flatnonzero(eligible):
        neighborhood = eligible & (
            np.abs(range_m - range_m[index]) <= SELECTION_NEIGHBORHOOD_M
        )
        selected[index] = (
            corrected[index] >= np.max(corrected[neighborhood]) - SELECTION_TOLERANCE_DB
        )
    return selected


def slope_db_per_decade(values_db: FloatArray, range_m: FloatArray) -> float:
    """Least-squares slope of ``values_db`` against log10(range)."""
    return float(np.polyfit(np.log10(range_m), values_db, 1)[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "extract")
    args = parser.parse_args()

    capture = load_capture(args.data, verify=True)
    values = extract(capture)
    range_m = values["range_m"]
    selected = report_selection(range_m, values["magnitude_sum_snr_db"])
    frames = np.arange(capture.n_frames)
    legs = {name: (frames >= a) & (frames <= b) for name, (a, b) in LEGS.items()}
    to_reference = 40 * np.log10(range_m / REFERENCE_RANGE_M)
    magnitude_sum_at_reference = values["magnitude_sum_snr_db"] + to_reference
    mean_rx_signal_db = db(np.mean(10 ** (values["rx_signal_power_db"] / 10), axis=1))
    center_hz = (
        capture.start_frequency_hz
        + capture.slope_hz_per_s * capture.pre_payload_s
        + capture.sampled_bandwidth_hz / 2
    )

    summary = {
        "capture": {
            "input": str(capture.root),
            "cpis": capture.n_frames,
            "shape_chirp_sample_rx": list(capture.shape),
            "sha256_verified": True,
            "sample_rate_hz": capture.sample_rate_hz,
            "chirp_period_s": capture.chirp_period_s,
            "slope_hz_per_s": capture.slope_hz_per_s,
            "sampled_bandwidth_hz": capture.sampled_bandwidth_hz,
            "sampled_sweep_center_hz": center_hz,
            "rx_gain_db": capture.rx_gain_db,
        },
        "processing": {
            "windows": "periodic Blackman, range and Doppler",
            "padding": "4x range and Doppler for the target cell",
            "search_range_m": list(SEARCH_RANGE_M),
            "search_abs_velocity_mps": list(SEARCH_ABS_VELOCITY_MPS),
            "far_noise": "farthest range quarter, |v| >= 1 m/s, native Doppler bins",
        },
        "legs": {
            name: {
                "cpis": list(LEGS[name]),
                "range_m": [float(range_m[mask].min()), float(range_m[mask].max())],
            }
            for name, mask in legs.items()
        },
        "report_reproduction": {
            "report_value_db": REPORT_SNR_DB,
            "selected_count": int(np.count_nonzero(selected)),
            "selected_frames_all_inbound": bool(np.all(legs["inbound"][selected])),
            "magnitude_sum_at_100m_selected_db": float(
                np.mean(magnitude_sum_at_reference[selected])
            ),
            "magnitude_sum_at_100m_inbound_db": float(
                np.mean(magnitude_sum_at_reference[legs["inbound"]])
            ),
        },
        "free_range_slope_of_mean_rx_signal_db_per_decade": {
            name: slope_db_per_decade(mean_rx_signal_db[mask], range_m[mask])
            for name, mask in legs.items()
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
                "range_m",
                "velocity_mps",
                "selected",
                "locator_snr_db",
                "magnitude_sum_snr_db",
                *[f"rx{channel}_signal_power_db" for channel in channels],
                *[f"rx{channel}_far_snr_db" for channel in channels],
            ]
        )
        far_snr_db = values["rx_signal_power_db"] - values["rx_far_noise_power_db"]
        for frame in frames:
            writer.writerow(
                [
                    int(frame),
                    leg_of(int(frame)),
                    range_m[frame],
                    values["velocity_mps"][frame],
                    bool(selected[frame]),
                    values["locator_snr_db"][frame],
                    values["magnitude_sum_snr_db"][frame],
                    *values["rx_signal_power_db"][frame],
                    *far_snr_db[frame],
                ]
            )

    figure, axes = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)
    axes[0].plot(frames, range_m, ".", color="0.6", markersize=3, label="all CPIs")
    for name, mask in legs.items():
        axes[0].plot(frames[mask], range_m[mask], ".", markersize=5, label=name)
    axes[0].scatter(
        frames[selected],
        range_m[selected],
        marker="o",
        facecolors="none",
        edgecolors="black",
        label="report-style selection",
    )
    axes[0].set(xlabel="CPI", ylabel="Tracked range [m]", title="Reflector track")
    far_mean_snr_db = db(
        np.mean(
            10
            ** ((values["rx_signal_power_db"] - values["rx_far_noise_power_db"]) / 10),
            axis=1,
        )
    )
    for name, mask in legs.items():
        axes[1].plot(
            range_m[mask], far_mean_snr_db[mask] + to_reference[mask], ".", label=name
        )
    axes[1].scatter(
        range_m[selected],
        magnitude_sum_at_reference[selected],
        marker="o",
        facecolors="none",
        edgecolors="black",
        label="magnitude sum, selected",
    )
    axes[1].axhline(REPORT_SNR_DB, color="black", linestyle=":", label="report fit")
    axes[1].set(
        xlabel="Tracked range [m]",
        ylabel="SNR over far-quarter noise, R^-4 scaled to 100 m [dB]",
        title="Linear RX mean (points) and report statistic, walking reflector RCS",
    )
    for axis in axes:
        axis.grid(alpha=0.3)
        axis.legend()
    figure.savefig(args.output / "track.png", dpi=160)
    plt.close(figure)


if __name__ == "__main__":
    main()
