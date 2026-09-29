"""Reproduce and audit the CARKIT single-TX walking-reflector analysis.

The input is the offline PSI-style conversion: one JSON/bin pair per CPI, with
real int16 ADC data ordered as [chirp, fast-time sample, RX].  Processing is
deliberately explicit and per RX.  A common target cell is located from the
mean of noise-normalized RX powers; every reported per-RX value is then read at
that same cell.

The script also reproduces the less conventional RX-magnitude-sum statistic
shown in the supplied follow-up plot, and quantifies the difference between its
far-quarter noise reference and the noise spectrum near the walking reflector.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import numpy.typing as npt
from scipy.fft import fft, fftshift, rfft
from scipy.signal.windows import blackman

from radarperf.units import SPEED_OF_LIGHT

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]

REPORT_CENTER_FREQUENCY_HZ = 76.374237e9
REFERENCE_RCS_DBSM = 10.0
PROVISIONAL_WALKING_RCS_DBSM = 11.27
STABLE_OUTBOUND_FRAME_RANGE = (26, 70)
STABLE_INBOUND_FRAME_RANGE = (89, 127)


@dataclass(frozen=True)
class Capture:
    """Validated capture layout and waveform values used by the analysis."""

    json_paths: tuple[Path, ...]
    shape: tuple[int, int, int]
    sample_rate_hz: float
    chirp_period_s: float
    slope_hz_per_s: float
    start_frequency_hz: float
    sampled_bandwidth_hz: float


@dataclass(frozen=True)
class Axes:
    """Zero-padded physical-range and Doppler axes plus processing masks."""

    range_m: FloatArray
    velocity_mps: FloatArray
    velocity_native_mps: FloatArray
    search_range_indices: npt.NDArray[np.int64]
    search_velocity_indices: npt.NDArray[np.int64]
    far_range: BoolArray
    local_range: BoolArray
    noise_velocity: BoolArray
    thermal_velocity: BoolArray


@dataclass(frozen=True)
class Results:
    """One common target cell and per-RX values for every CPI."""

    frame: npt.NDArray[np.int64]
    range_m: FloatArray
    velocity_mps: FloatArray
    locator_snr_db: FloatArray
    magnitude_sum_snr_db: FloatArray
    magnitude_sum_signal_power_db: FloatArray
    rx_snr_db: FloatArray
    rx_signal_power_db: FloatArray
    rx_far_noise_power_db: FloatArray
    rx_range_m: FloatArray
    local_to_far_noise_db: FloatArray
    median_noise_profile: FloatArray


def _require_number(mapping: dict[str, Any], key: str) -> float:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def load_capture(root: Path) -> Capture:
    """Load and validate the common layout from a directory of CPI pairs."""
    json_paths = tuple(sorted(root.glob("cpi_*.json")))
    if not json_paths:
        raise ValueError(f"no cpi_*.json files found under {root}")

    first = json.loads(json_paths[0].read_text())
    sample = first["sample_format"]
    waveform = first["waveform"]
    if sample["dtype"] != "int16" or sample["byte_order"] != "little":
        raise ValueError("only little-endian int16 input is supported")
    if sample["axes"] != ["chirp", "sample", "rx"]:
        raise ValueError("expected axes [chirp, sample, rx]")
    shape_values = sample["shape"]
    if not isinstance(shape_values, list) or len(shape_values) != 3:
        raise ValueError("sample shape must contain three dimensions")
    shape = tuple(int(value) for value in shape_values)
    if any(value < 1 for value in shape):
        raise ValueError("sample dimensions must be positive")

    expected_bytes = math.prod(shape) * np.dtype("<i2").itemsize
    for expected_cpi, json_path in enumerate(json_paths):
        metadata = json.loads(json_path.read_text())
        if int(metadata["cpi"]) != expected_cpi:
            raise ValueError(f"non-contiguous CPI numbering at {json_path}")
        if tuple(int(value) for value in metadata["sample_format"]["shape"]) != shape:
            raise ValueError(f"shape changes at {json_path}")
        binary_path = root / str(metadata["file"])
        if not binary_path.is_file() or binary_path.stat().st_size != expected_bytes:
            raise ValueError(f"missing or incorrectly sized binary {binary_path}")

    return Capture(
        json_paths=json_paths,
        shape=(shape[0], shape[1], shape[2]),
        sample_rate_hz=_require_number(waveform, "sample_rate_msps") * 1e6,
        chirp_period_s=_require_number(waveform, "chirp_period_us") * 1e-6,
        slope_hz_per_s=_require_number(waveform, "slope_hz_per_s"),
        start_frequency_hz=_require_number(waveform, "carkit_start_frequency_hz"),
        sampled_bandwidth_hz=_require_number(waveform, "adc_bandwidth_hz"),
    )


def make_axes(
    capture: Capture,
    *,
    center_frequency_hz: float,
    padding: int,
    search_range_m: tuple[float, float],
    search_abs_velocity_mps: tuple[float, float],
    local_noise_range_m: tuple[float, float],
    far_range_fraction: float,
    noise_abs_velocity_min_mps: float,
    thermal_abs_velocity_min_mps: float,
) -> Axes:
    """Construct axes and fixed masks from explicit analysis settings."""
    n_chirps, n_samples, _ = capture.shape
    range_frequency_hz = np.fft.rfftfreq(
        padding * n_samples, 1 / capture.sample_rate_hz
    )
    range_m = np.asarray(
        SPEED_OF_LIGHT * range_frequency_hz / (2 * capture.slope_hz_per_s),
        dtype=float,
    )
    doppler_hz = fftshift(np.fft.fftfreq(padding * n_chirps, capture.chirp_period_s))
    velocity_mps = np.asarray(
        SPEED_OF_LIGHT * doppler_hz / (2 * center_frequency_hz), dtype=float
    )
    native_doppler_hz = np.fft.fftfreq(n_chirps, capture.chirp_period_s)
    velocity_native_mps = np.asarray(
        SPEED_OF_LIGHT * native_doppler_hz / (2 * center_frequency_hz), dtype=float
    )

    range_search = (range_m >= search_range_m[0]) & (range_m <= search_range_m[1])
    abs_velocity = np.abs(velocity_mps)
    velocity_search = (abs_velocity >= search_abs_velocity_mps[0]) & (
        abs_velocity <= search_abs_velocity_mps[1]
    )
    local_range = (range_m >= local_noise_range_m[0]) & (
        range_m <= local_noise_range_m[1]
    )
    return Axes(
        range_m=range_m,
        velocity_mps=velocity_mps,
        velocity_native_mps=velocity_native_mps,
        search_range_indices=np.flatnonzero(range_search),
        search_velocity_indices=np.flatnonzero(velocity_search),
        far_range=range_m >= far_range_fraction * range_m[-1],
        local_range=local_range,
        noise_velocity=np.abs(velocity_native_mps) >= noise_abs_velocity_min_mps,
        thermal_velocity=(np.abs(velocity_native_mps) >= thermal_abs_velocity_min_mps),
    )


def analyze(
    root: Path,
    capture: Capture,
    axes: Axes,
    *,
    padding: int,
    workers: int,
) -> Results:
    """Process all CPIs and extract one common cell plus per-RX measurements."""
    n_frames = len(capture.json_paths)
    n_chirps, n_samples, n_rx = capture.shape
    range_window = blackman(n_samples, sym=False).astype(np.float32)
    doppler_window = blackman(n_chirps, sym=False).astype(np.float32)
    range_norm = float(np.sum(range_window))
    doppler_norm = float(np.sum(doppler_window))

    frame = np.arange(n_frames, dtype=np.int64)
    target_range_m = np.empty(n_frames)
    target_velocity_mps = np.empty(n_frames)
    locator_snr_db = np.empty(n_frames)
    magnitude_sum_snr_db = np.empty(n_frames)
    magnitude_sum_signal_power_db = np.empty(n_frames)
    rx_snr_db = np.empty((n_frames, n_rx))
    rx_signal_power_db = np.empty((n_frames, n_rx))
    rx_far_noise_power_db = np.empty((n_frames, n_rx))
    rx_range_m = np.empty((n_frames, n_rx))
    local_to_far_noise_db = np.empty((n_frames, n_rx))
    noise_profiles = np.empty((n_frames, axes.range_m.size, n_rx), dtype=np.float32)

    for index, json_path in enumerate(capture.json_paths):
        metadata = json.loads(json_path.read_text())
        raw = np.fromfile(root / str(metadata["file"]), dtype="<i2").reshape(
            capture.shape
        )
        range_spectrum = (
            rfft(
                raw.astype(np.float32) * range_window[None, :, None],
                n=padding * n_samples,
                axis=1,
                workers=workers,
            )
            / range_norm
        )

        native_rd = (
            fft(
                range_spectrum * doppler_window[:, None, None],
                axis=0,
                workers=workers,
            )
            / doppler_norm
        )
        noise_cells = native_rd[axes.noise_velocity, :, :]
        far_noise_power = np.mean(
            np.abs(noise_cells[:, axes.far_range, :]) ** 2, axis=(0, 1)
        )
        far_magnitude_sum_power = float(
            np.mean(np.sum(np.abs(noise_cells[:, axes.far_range, :]), axis=2) ** 2)
        )

        thermal_profile = np.mean(
            np.abs(native_rd[axes.thermal_velocity, :, :]) ** 2, axis=0
        )
        noise_profiles[index] = thermal_profile
        local_power = np.mean(thermal_profile[axes.local_range, :], axis=0)
        local_to_far_noise_db[index] = 10 * np.log10(local_power / far_noise_power)

        range_subset = range_spectrum[:, axes.search_range_indices, :]
        padded_rd = (
            fftshift(
                fft(
                    range_subset * doppler_window[:, None, None],
                    n=padding * n_chirps,
                    axis=0,
                    workers=workers,
                ),
                axes=0,
            )
            / doppler_norm
        )
        candidates = padded_rd[axes.search_velocity_indices, :, :]
        candidate_power = np.abs(candidates) ** 2
        locator = np.mean(candidate_power / far_noise_power[None, None, :], axis=2)
        candidate_index = np.unravel_index(int(np.argmax(locator)), locator.shape)
        local_velocity_index = int(candidate_index[0])
        local_range_index = int(candidate_index[1])
        velocity_index = axes.search_velocity_indices[local_velocity_index]
        range_index = axes.search_range_indices[local_range_index]
        amplitude = np.abs(candidates[local_velocity_index, local_range_index, :])

        target_range_line = np.abs(candidates[local_velocity_index, :, :]) ** 2
        peak_radius = 2 * padding
        peak_start = max(1, local_range_index - peak_radius)
        peak_stop = min(
            target_range_line.shape[0] - 1,
            local_range_index + peak_radius + 1,
        )
        range_spacing_m = float(axes.range_m[1] - axes.range_m[0])
        for channel in range(n_rx):
            peak_index = peak_start + int(
                np.argmax(target_range_line[peak_start:peak_stop, channel])
            )
            peak_log_power = np.log(
                np.maximum(
                    target_range_line[peak_index - 1 : peak_index + 2, channel],
                    np.finfo(float).tiny,
                )
            )
            denominator = peak_log_power[0] - 2 * peak_log_power[1] + peak_log_power[2]
            fractional_bin = 0.0
            if denominator != 0:
                fractional_bin = float(
                    np.clip(
                        0.5 * (peak_log_power[0] - peak_log_power[2]) / denominator,
                        -1,
                        1,
                    )
                )
            global_peak_index = axes.search_range_indices[peak_index]
            rx_range_m[index, channel] = (
                axes.range_m[global_peak_index] + fractional_bin * range_spacing_m
            )

        target_range_m[index] = axes.range_m[range_index]
        target_velocity_mps[index] = axes.velocity_mps[velocity_index]
        locator_snr_db[index] = 10 * math.log10(
            float(locator[local_velocity_index, local_range_index])
        )
        magnitude_sum_snr_db[index] = 20 * math.log10(
            float(np.sum(amplitude)) / math.sqrt(far_magnitude_sum_power)
        )
        magnitude_sum_signal_power_db[index] = 20 * math.log10(float(np.sum(amplitude)))
        rx_snr_db[index] = 10 * np.log10(amplitude**2 / far_noise_power)
        rx_signal_power_db[index] = 10 * np.log10(amplitude**2)
        rx_far_noise_power_db[index] = 10 * np.log10(far_noise_power)

        if index % 20 == 0 or index + 1 == n_frames:
            print(f"processed {index + 1}/{n_frames} CPIs", flush=True)

    return Results(
        frame=frame,
        range_m=target_range_m,
        velocity_mps=target_velocity_mps,
        locator_snr_db=locator_snr_db,
        magnitude_sum_snr_db=magnitude_sum_snr_db,
        magnitude_sum_signal_power_db=magnitude_sum_signal_power_db,
        rx_snr_db=rx_snr_db,
        rx_signal_power_db=rx_signal_power_db,
        rx_far_noise_power_db=rx_far_noise_power_db,
        rx_range_m=rx_range_m,
        local_to_far_noise_db=local_to_far_noise_db,
        median_noise_profile=np.median(noise_profiles, axis=0),
    )


def local_peak_selection(
    results: Results,
    *,
    fit_range_m: tuple[float, float],
    neighborhood_m: float,
    tolerance_db: float,
) -> BoolArray:
    """Apply the report's stated local R^-4-corrected upper-tail selection."""
    eligible = (results.range_m >= fit_range_m[0]) & (results.range_m <= fit_range_m[1])
    corrected = results.magnitude_sum_snr_db + 40 * np.log10(results.range_m)
    selected = np.zeros(results.range_m.shape, dtype=bool)
    for index in np.flatnonzero(eligible):
        neighborhood = eligible & (
            np.abs(results.range_m - results.range_m[index]) <= neighborhood_m
        )
        selected[index] = (
            corrected[index] >= np.max(corrected[neighborhood]) - tolerance_db
        )
    return selected


def intercept_at_reference(
    snr_db: FloatArray, range_m: FloatArray, selected: BoolArray, reference_m: float
) -> FloatArray:
    """Fixed-R^-4 least-squares intercept in dB at ``reference_m``."""
    range_correction_db = 40 * np.log10(range_m[selected] / reference_m)
    if snr_db.ndim == 2:
        range_correction_db = range_correction_db[:, None]
    values = snr_db[selected] + range_correction_db
    return np.asarray(np.mean(values, axis=0), dtype=float)


def slope_db_per_decade(
    values_db: FloatArray, range_m: FloatArray, selected: BoolArray
) -> FloatArray:
    """Fit a free linear slope against log10(range)."""
    x = np.log10(range_m[selected])
    x_centered = x - np.mean(x)
    values = values_db[selected]
    if values.ndim == 1:
        values = values[:, None]
    values_centered = values - np.mean(values, axis=0)
    slopes = np.sum(x_centered[:, None] * values_centered, axis=0) / np.sum(
        x_centered**2
    )
    return np.asarray(slopes, dtype=float)


def write_csv(path: Path, results: Results, selected: BoolArray) -> None:
    """Write per-frame target cells and per-RX SNRs."""
    with path.open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "frame",
                "range_m",
                "velocity_mps",
                "selected",
                "locator_snr_db",
                "magnitude_sum_snr_db",
                "magnitude_sum_signal_power_db",
                *[f"rx{channel}_snr_db" for channel in range(1, 9)],
                *[f"rx{channel}_signal_power_db" for channel in range(1, 9)],
                *[f"rx{channel}_far_noise_power_db" for channel in range(1, 9)],
                *[f"rx{channel}_range_m" for channel in range(1, 9)],
                *[f"rx{channel}_local_to_far_noise_db" for channel in range(1, 9)],
            ]
        )
        for index in range(results.frame.size):
            writer.writerow(
                [
                    int(results.frame[index]),
                    results.range_m[index],
                    results.velocity_mps[index],
                    bool(selected[index]),
                    results.locator_snr_db[index],
                    results.magnitude_sum_snr_db[index],
                    results.magnitude_sum_signal_power_db[index],
                    *results.rx_snr_db[index],
                    *results.rx_signal_power_db[index],
                    *results.rx_far_noise_power_db[index],
                    *results.rx_range_m[index],
                    *results.local_to_far_noise_db[index],
                ]
            )


def plot_results(
    output_dir: Path,
    results: Results,
    selected: BoolArray,
    axes: Axes,
    capture: Capture,
) -> None:
    """Plot the extracted trajectory, R^-4-normalized points and noise spectrum."""
    figure, plot_axes = plt.subplots(2, 1, figsize=(11, 8), constrained_layout=True)
    plot_axes[0].plot(results.frame, results.range_m, ".-", markersize=3)
    plot_axes[0].scatter(
        results.frame[selected],
        results.range_m[selected],
        marker="o",
        facecolors="none",
    )
    plot_axes[0].set(xlabel="CPI index", ylabel="Extracted range [m]")
    plot_axes[0].grid(True, alpha=0.3)

    normalized = results.rx_snr_db + 40 * np.log10(results.range_m[:, None] / 100)
    for channel in range(normalized.shape[1]):
        plot_axes[1].plot(
            results.range_m[selected],
            normalized[selected, channel],
            ".",
            alpha=0.55,
            label=f"RX{channel + 1}",
        )
    plot_axes[1].scatter(
        results.range_m[selected],
        results.magnitude_sum_snr_db[selected]
        + 40 * np.log10(results.range_m[selected] / 100),
        marker="o",
        facecolors="none",
        edgecolors="black",
        label="selected magnitude sum",
    )
    plot_axes[1].set(
        xlabel="Extracted range [m]",
        ylabel="SNR normalized to 100 m [dB]",
        xlim=(0, 70),
    )
    plot_axes[1].grid(True, alpha=0.3)
    plot_axes[1].legend()
    figure.savefig(output_dir / "trajectory_and_snr.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(11, 5), constrained_layout=True)
    far_reference = np.mean(results.median_noise_profile[axes.far_range, :], axis=0)
    relative_db = 10 * np.log10(results.median_noise_profile / far_reference[None, :])
    for channel in range(relative_db.shape[1]):
        axis.plot(
            axes.range_m,
            relative_db[:, channel],
            alpha=0.55,
            linewidth=1,
            label=f"RX{channel + 1}",
        )
    axis.plot(
        axes.range_m,
        np.median(relative_db, axis=1),
        color="black",
        linewidth=2,
        label="RX median",
    )
    axis.axhline(0, color="black", linewidth=0.8, linestyle=":")
    axis.axvspan(15, 51, color="tab:orange", alpha=0.12, label="reflector fit range")
    axis.axvspan(
        0.75 * axes.range_m[-1],
        axes.range_m[-1],
        color="tab:gray",
        alpha=0.12,
        label="far-quarter noise region",
    )
    axis.set(
        xlabel="Apparent range [m]",
        ylabel="Median background power relative to far quarter [dB]",
        xlim=(0, axes.range_m[-1]),
        ylim=(-3, 3),
        title=(
            "Background-noise spectrum: |velocity| >= 10 m/s, " "median over 200 CPIs"
        ),
    )
    range_to_beat_scale = 2 * capture.slope_hz_per_s / SPEED_OF_LIGHT / 1e6

    def range_to_beat_mhz(range_m: npt.ArrayLike) -> FloatArray:
        return np.asarray(range_m, dtype=float) * range_to_beat_scale

    def beat_mhz_to_range(frequency_mhz: npt.ArrayLike) -> FloatArray:
        return np.asarray(frequency_mhz, dtype=float) / range_to_beat_scale

    frequency_axis = axis.secondary_xaxis(
        "top",
        functions=(range_to_beat_mhz, beat_mhz_to_range),
    )
    frequency_axis.set_xlabel("Equivalent beat frequency [MHz]")
    axis.grid(True, alpha=0.3)
    axis.legend(ncol=3)
    figure.savefig(output_dir / "noise_spectrum.png", dpi=160)
    plt.close(figure)

    stable_inbound = (results.frame >= STABLE_INBOUND_FRAME_RANGE[0]) & (
        results.frame <= STABLE_INBOUND_FRAME_RANGE[1]
    )
    stable_outbound = (results.frame >= STABLE_OUTBOUND_FRAME_RANGE[0]) & (
        results.frame <= STABLE_OUTBOUND_FRAME_RANGE[1]
    )
    stable_range_m = results.range_m[stable_inbound]
    mean_rx_signal_db = 10 * np.log10(
        np.mean(10 ** (results.rx_signal_power_db[stable_inbound] / 10), axis=1)
    )
    r4_corrected_signal_db = mean_rx_signal_db + 40 * np.log10(stable_range_m)
    r4_corrected_signal_db -= np.mean(r4_corrected_signal_db)
    residual_slope = float(
        slope_db_per_decade(
            mean_rx_signal_db,
            stable_range_m,
            np.ones(stable_range_m.shape, dtype=bool),
        )[0]
        + 40
    )
    log_range_centered = np.log10(stable_range_m) - np.mean(np.log10(stable_range_m))
    target_fit_db = residual_slope * log_range_centered

    outbound_range_m = results.range_m[stable_outbound]
    outbound_mean_rx_signal_db = 10 * np.log10(
        np.mean(10 ** (results.rx_signal_power_db[stable_outbound] / 10), axis=1)
    )
    outbound_r4_corrected_db = outbound_mean_rx_signal_db + 40 * np.log10(
        outbound_range_m
    )
    outbound_r4_corrected_db -= np.mean(outbound_r4_corrected_db)
    outbound_residual_slope = float(
        slope_db_per_decade(
            outbound_mean_rx_signal_db,
            outbound_range_m,
            np.ones(outbound_range_m.shape, dtype=bool),
        )[0]
        + 40
    )
    outbound_log_range_centered = np.log10(outbound_range_m) - np.mean(
        np.log10(outbound_range_m)
    )
    outbound_fit_db = outbound_residual_slope * outbound_log_range_centered

    stable_spectrum = (
        axes.range_m >= min(np.min(stable_range_m), np.min(outbound_range_m))
    ) & (axes.range_m <= max(np.max(stable_range_m), np.max(outbound_range_m)))
    median_noise_db = np.median(relative_db, axis=1)[stable_spectrum]
    median_noise_db -= np.mean(median_noise_db)

    figure, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
    axis.scatter(
        stable_range_m,
        r4_corrected_signal_db,
        s=25,
        alpha=0.7,
        label="Inbound mean RX target power x R^4",
    )
    order = np.argsort(stable_range_m)
    axis.plot(
        stable_range_m[order],
        target_fit_db[order],
        color="tab:blue",
        linewidth=2,
        label=f"Inbound fit: {residual_slope:+.1f} dB/decade beyond R^-4",
    )
    axis.scatter(
        outbound_range_m,
        outbound_r4_corrected_db,
        s=25,
        alpha=0.55,
        color="tab:orange",
        label="Outbound mean RX target power x R^4",
    )
    outbound_order = np.argsort(outbound_range_m)
    axis.plot(
        outbound_range_m[outbound_order],
        outbound_fit_db[outbound_order],
        color="tab:orange",
        linewidth=2,
        label=(
            f"Outbound fit: {outbound_residual_slope:+.1f} dB/decade " "beyond R^-4"
        ),
    )
    axis.plot(
        axes.range_m[stable_spectrum],
        median_noise_db,
        color="black",
        linewidth=2,
        label="Measured background-noise shape (centered)",
    )
    axis.axhline(0, color="gray", linestyle=":", label="Pure R^-4 target")
    axis.set(
        xlabel="Range [m]",
        ylabel="Centered power [dB]",
        title="Target residual after R^-4 correction versus noise spectral shape",
    )
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.savefig(output_dir / "signal_slope.png", dpi=160)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "data", type=Path, help="directory containing CPI JSON/bin pairs"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "generated" / "walk_adc",
    )
    parser.add_argument("--workers", type=int, default=-1)
    args = parser.parse_args()

    capture = load_capture(args.data)
    padding = 4
    axes = make_axes(
        capture,
        center_frequency_hz=REPORT_CENTER_FREQUENCY_HZ,
        padding=padding,
        search_range_m=(3.0, 70.0),
        search_abs_velocity_mps=(0.75, 12.0),
        local_noise_range_m=(15.0, 51.0),
        far_range_fraction=0.75,
        noise_abs_velocity_min_mps=1.0,
        thermal_abs_velocity_min_mps=10.0,
    )
    results = analyze(args.data, capture, axes, padding=padding, workers=args.workers)
    selected = local_peak_selection(
        results, fit_range_m=(15.0, 51.0), neighborhood_m=5.0, tolerance_db=6.0
    )
    stable_inbound = (results.frame >= STABLE_INBOUND_FRAME_RANGE[0]) & (
        results.frame <= STABLE_INBOUND_FRAME_RANGE[1]
    )
    stable_outbound = (results.frame >= STABLE_OUTBOUND_FRAME_RANGE[0]) & (
        results.frame <= STABLE_OUTBOUND_FRAME_RANGE[1]
    )

    magnitude_intercept = float(
        intercept_at_reference(
            results.magnitude_sum_snr_db, results.range_m, selected, 100.0
        )
    )
    stable_inbound_magnitude_intercept = float(
        intercept_at_reference(
            results.magnitude_sum_snr_db,
            results.range_m,
            stable_inbound,
            100.0,
        )
    )
    rx_intercepts = intercept_at_reference(
        results.rx_snr_db, results.range_m, selected, 100.0
    )
    local_noise_correction = np.median(results.local_to_far_noise_db, axis=0)
    selected_local_noise_correction = np.median(
        results.local_to_far_noise_db[selected], axis=0
    )
    local_rx_intercepts = intercept_at_reference(
        results.rx_snr_db - results.local_to_far_noise_db,
        results.range_m,
        selected,
        100.0,
    )
    rcs_normalized_mean = float(
        np.mean(local_rx_intercepts)
        - (PROVISIONAL_WALKING_RCS_DBSM - REFERENCE_RCS_DBSM)
    )
    rcs_normalized_linear_power_mean = float(
        10 * np.log10(np.mean(10 ** (local_rx_intercepts / 10)))
        - (PROVISIONAL_WALKING_RCS_DBSM - REFERENCE_RCS_DBSM)
    )
    implied_center_hz = capture.start_frequency_hz + 0.5 * capture.sampled_bandwidth_hz
    relative_rx_range_m = results.rx_range_m - np.mean(
        results.rx_range_m, axis=1, keepdims=True
    )
    relative_range_median = np.median(relative_rx_range_m[selected], axis=0)
    relative_range_mad = np.median(
        np.abs(relative_rx_range_m[selected] - relative_range_median), axis=0
    )
    relative_delay_ps = 2e12 * relative_range_median / SPEED_OF_LIGHT
    relative_delay_mad_ps = 2e12 * relative_range_mad / SPEED_OF_LIGHT
    stable_range_min_m = float(np.min(results.range_m[stable_inbound]))
    stable_range_max_m = float(np.max(results.range_m[stable_inbound]))
    stable_rx_signal_slopes = slope_db_per_decade(
        results.rx_signal_power_db, results.range_m, stable_inbound
    )
    selected_rx_signal_slopes = slope_db_per_decade(
        results.rx_signal_power_db, results.range_m, selected
    )
    stable_magnitude_signal_slope = float(
        slope_db_per_decade(
            results.magnitude_sum_signal_power_db,
            results.range_m,
            stable_inbound,
        )[0]
    )
    selected_magnitude_signal_slope = float(
        slope_db_per_decade(
            results.magnitude_sum_signal_power_db,
            results.range_m,
            selected,
        )[0]
    )
    mean_rx_signal_power_db = 10 * np.log10(
        np.mean(10 ** (results.rx_signal_power_db / 10), axis=1)
    )
    stable_mean_rx_power_signal_slope = float(
        slope_db_per_decade(mean_rx_signal_power_db, results.range_m, stable_inbound)[0]
    )
    selected_mean_rx_power_signal_slope = float(
        slope_db_per_decade(mean_rx_signal_power_db, results.range_m, selected)[0]
    )
    stable_outbound_mean_rx_power_signal_slope = float(
        slope_db_per_decade(mean_rx_signal_power_db, results.range_m, stable_outbound)[
            0
        ]
    )
    stable_far_noise_slopes = slope_db_per_decade(
        results.rx_far_noise_power_db, results.range_m, stable_inbound
    )
    spectrum_range = (axes.range_m >= stable_range_min_m) & (
        axes.range_m <= stable_range_max_m
    )
    noise_spectrum_db = 10 * np.log10(results.median_noise_profile)
    noise_spectrum_slopes = slope_db_per_decade(
        noise_spectrum_db, axes.range_m, spectrum_range
    )

    summary = {
        "input": str(args.data),
        "cpi_count": len(capture.json_paths),
        "adc_shape": capture.shape,
        "processing": {
            "range_window": "periodic Blackman",
            "doppler_window": "periodic Blackman",
            "range_padding": padding,
            "doppler_padding": padding,
            "target_search_range_m": [3.0, 70.0],
            "target_search_abs_velocity_mps": [0.75, 12.0],
            "target_locator": "mean of per-RX powers normalized by far-quarter RMS power",
            "noise_region": "farthest physical-range quarter; |velocity| >= 1 m/s",
            "local_noise_check": "15-51 m; |velocity| >= 10 m/s; median over CPIs",
            "selection": "15-51 m and within 6 dB of local +/-5 m R^-4-corrected magnitude-sum peak",
            "diagnostic_stable_inbound_frame_range_inclusive": list(
                STABLE_INBOUND_FRAME_RANGE
            ),
            "diagnostic_stable_outbound_frame_range_inclusive": list(
                STABLE_OUTBOUND_FRAME_RANGE
            ),
        },
        "frequency_hz": {
            "report_center_assumed_for_velocity": REPORT_CENTER_FREQUENCY_HZ,
            "json_start_plus_half_sampled_bandwidth": implied_center_hz,
        },
        "range_slope_check": {
            "stable_inbound_range_m": [stable_range_min_m, stable_range_max_m],
            "stable_outbound_range_m": [
                float(np.min(results.range_m[stable_outbound])),
                float(np.max(results.range_m[stable_outbound])),
            ],
            "ideal_r4_signal_slope_db_per_decade": -40.0,
            "stable_rx_signal_slopes_db_per_decade": (stable_rx_signal_slopes.tolist()),
            "selected_rx_signal_slopes_db_per_decade": (
                selected_rx_signal_slopes.tolist()
            ),
            "stable_magnitude_sum_signal_slope_db_per_decade": (
                stable_magnitude_signal_slope
            ),
            "selected_magnitude_sum_signal_slope_db_per_decade": (
                selected_magnitude_signal_slope
            ),
            "stable_mean_rx_power_signal_slope_db_per_decade": (
                stable_mean_rx_power_signal_slope
            ),
            "selected_mean_rx_power_signal_slope_db_per_decade": (
                selected_mean_rx_power_signal_slope
            ),
            "stable_outbound_mean_rx_power_signal_slope_db_per_decade": (
                stable_outbound_mean_rx_power_signal_slope
            ),
            "stable_far_noise_temporal_slopes_db_per_decade": (
                stable_far_noise_slopes.tolist()
            ),
            "noise_spectrum_slopes_over_same_range_db_per_decade": (
                noise_spectrum_slopes.tolist()
            ),
            "common_filter_expected_rx_signal_slopes_db_per_decade": (
                (-40 + noise_spectrum_slopes).tolist()
            ),
        },
        "selected_count": int(np.sum(selected)),
        "magnitude_sum_intercept_db_at_100m_far_noise": magnitude_intercept,
        "stable_inbound_count": int(np.sum(stable_inbound)),
        "stable_inbound_magnitude_sum_intercept_db_at_100m_far_noise": (
            stable_inbound_magnitude_intercept
        ),
        "rx_intercepts_db_at_100m_far_noise": rx_intercepts.tolist(),
        "rx_local_to_far_noise_db_median_all_cpis": (local_noise_correction.tolist()),
        "rx_local_to_far_noise_db_median_selected_cpis": (
            selected_local_noise_correction.tolist()
        ),
        "rx_intercepts_db_at_100m_local_noise": local_rx_intercepts.tolist(),
        "rx_relative_range_offset_m_median": relative_range_median.tolist(),
        "rx_relative_range_offset_m_mad": relative_range_mad.tolist(),
        "rx_relative_group_delay_ps_median": relative_delay_ps.tolist(),
        "rx_relative_group_delay_ps_mad": relative_delay_mad_ps.tolist(),
        "mean_rx_intercept_db_at_100m_far_noise": float(np.mean(rx_intercepts)),
        "mean_rx_intercept_db_at_100m_local_noise": float(np.mean(local_rx_intercepts)),
        "mean_rx_intercept_db_at_100m_local_noise_normalized_to_10dbsm": (
            rcs_normalized_mean
        ),
        "linear_mean_rx_intercept_db_at_100m_local_noise_normalized_to_10dbsm": (
            rcs_normalized_linear_power_mean
        ),
        "provisional_walking_reflector_rcs_dbsm": PROVISIONAL_WALKING_RCS_DBSM,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_csv(args.output_dir / "per_frame.csv", results, selected)
    plot_results(args.output_dir, results, selected, axes, capture)

    print(json.dumps(summary, indent=2))
    print(f"wrote outputs under {args.output_dir}")


if __name__ == "__main__":
    main()
