"""Analyze CPI coherence, Doppler structure and target-conditioned background.

This is a diagnostic companion to analyze_walk_adc.py.  It deliberately keeps
the original target coordinates and leg definitions, but recomputes every
reported spectrum from the raw int16 samples.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import numpy.typing as npt
from scipy.fft import fft, fftshift, rfft
from scipy.signal.windows import blackman
from scipy.stats import spearmanr

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FloatArray = npt.NDArray[np.float64]
ComplexArray = npt.NDArray[np.complexfloating[Any, Any]]

SPEED_OF_LIGHT = 299792458.0
CARRIER_HZ = 76.374237e9
RANGE_PADDING = 4
DOPPLER_PADDING = 4
CHIRP_COUNTS = (128, 256, 512, 1024)
LEGS = {"outbound": (26, 70), "inbound": (89, 127)}


def db(value: npt.ArrayLike) -> FloatArray:
    """Convert positive power-like values to dB."""
    return np.asarray(10 * np.log10(np.maximum(value, np.finfo(float).tiny)))


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read the target coordinates produced by analyze_walk_adc.py."""
    with path.open() as stream:
        return list(csv.DictReader(stream))


def load_raw(data: Path, frame: int, shape: tuple[int, ...]) -> FloatArray:
    """Load one CPI without changing the original capture."""
    metadata = json.loads((data / f"cpi_{frame:010d}.json").read_text())
    return (
        np.fromfile(data / metadata["file"], dtype="<i2").reshape(shape).astype(float)
    )


def range_spectrum(raw: FloatArray, range_window: FloatArray) -> ComplexArray:
    """Window and transform real fast-time samples."""
    return np.asarray(
        rfft(
            raw * range_window[None, :, None],
            n=RANGE_PADDING * raw.shape[1],
            axis=1,
        )
        / range_window.sum()
    )


def padded_doppler(
    values: ComplexArray, window: FloatArray, *, axis: int = 0
) -> ComplexArray:
    """Window, normalize, pad and center a slow-time transform."""
    reshape = [1] * values.ndim
    reshape[axis] = window.size
    weighted = values * window.reshape(reshape)
    return np.asarray(
        fftshift(fft(weighted, n=DOPPLER_PADDING * window.size, axis=axis), axes=axis)
        / window.sum()
    )


def native_doppler(values: ComplexArray, window: FloatArray) -> ComplexArray:
    """Return an unpadded slow-time transform for background estimates."""
    return np.asarray(fft(values * window[:, None, None], axis=0) / window.sum())


def segment_measurement(
    spectrum: ComplexArray,
    range_axis: FloatArray,
    pri_s: float,
    target_range_m: float,
    target_velocity_mps: float,
) -> tuple[float, FloatArray]:
    """Measure a common-cell linear-RX-mean SNR for one slow-time segment."""
    n_chirps = spectrum.shape[0]
    window = np.asarray(blackman(n_chirps, sym=False), dtype=float)
    velocity_native = (
        np.fft.fftfreq(n_chirps, pri_s) * SPEED_OF_LIGHT / (2 * CARRIER_HZ)
    )
    native = native_doppler(spectrum, window)
    far = range_axis >= 0.75 * range_axis[-1]
    noise = np.mean(
        np.abs(native[np.abs(velocity_native) >= 10][:, far, :]) ** 2,
        axis=(0, 1),
    )

    ranges = np.abs(range_axis - target_range_m) <= 2.0
    local = padded_doppler(spectrum[:, ranges, :], window)
    velocity = (
        fftshift(np.fft.fftfreq(DOPPLER_PADDING * n_chirps, pri_s))
        * SPEED_OF_LIGHT
        / (2 * CARRIER_HZ)
    )
    velocities = np.abs(velocity - target_velocity_mps) <= 2.0
    candidate = np.abs(local[velocities]) ** 2 / noise[None, None, :]
    locator = np.mean(candidate, axis=2)
    index = np.unravel_index(int(np.argmax(locator)), locator.shape)
    per_rx = np.asarray(candidate[index[0], index[1]], dtype=float)
    return float(np.mean(per_rx)), per_rx


def best_tone_coherence(
    slow_time: ComplexArray, pri_s: float, target_velocity_mps: float
) -> FloatArray:
    """Fraction of weighted range-bin power explained by each RX's best tone."""
    n_chirps = slow_time.shape[0]
    window = np.asarray(blackman(n_chirps, sym=False), dtype=float)
    transformed = padded_doppler(slow_time, window)
    velocity = (
        fftshift(np.fft.fftfreq(DOPPLER_PADDING * n_chirps, pri_s))
        * SPEED_OF_LIGHT
        / (2 * CARRIER_HZ)
    )
    nearby = np.abs(velocity - target_velocity_mps) <= 2.0
    peak = np.max(np.abs(transformed[nearby]) ** 2, axis=0)
    weighted_input = np.sum(window[:, None] * np.abs(slow_time) ** 2, axis=0) / sum(
        window
    )
    return np.asarray(peak / weighted_input, dtype=float)


def range_band_mean(values: FloatArray, axis: FloatArray, center: float) -> FloatArray:
    """Average profiles within one native range resolution cell of center."""
    half_width = SPEED_OF_LIGHT / (2 * 100781248.0)
    return np.asarray(np.mean(values[np.abs(axis - center) <= half_width], axis=0))


def plot_slow_time_examples(
    data: Path,
    output: Path,
    shape: tuple[int, ...],
    range_axis: FloatArray,
    range_window: FloatArray,
    pri_s: float,
    target_range: FloatArray,
    target_velocity: FloatArray,
) -> None:
    """Plot amplitude and nonlinear phase left after a per-RX tone fit."""
    examples = (40, 100)
    figure, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    time_ms = np.arange(shape[0]) * pri_s * 1e3
    window = np.asarray(blackman(shape[0], sym=False), dtype=float)
    velocity = (
        fftshift(np.fft.fftfreq(DOPPLER_PADDING * shape[0], pri_s))
        * SPEED_OF_LIGHT
        / (2 * CARRIER_HZ)
    )
    for column, frame in enumerate(examples):
        raw = load_raw(data, frame, shape)
        spectrum = range_spectrum(raw, range_window)
        range_index = int(np.argmin(np.abs(range_axis - target_range[frame])))
        slow_time = spectrum[:, range_index, :]
        transformed = padded_doppler(slow_time, window)
        nearby_indices = np.flatnonzero(
            np.abs(velocity - target_velocity[frame]) <= 2.0
        )
        for channel in range(shape[2]):
            local_peak = int(np.argmax(np.abs(transformed[nearby_indices, channel])))
            fitted_velocity = velocity[nearby_indices[local_peak]]
            fitted_frequency = 2 * fitted_velocity * CARRIER_HZ / SPEED_OF_LIGHT
            demodulated = slow_time[:, channel] * np.exp(
                -2j * np.pi * fitted_frequency * np.arange(shape[0]) * pri_s
            )
            amplitude_db = 20 * np.log10(
                np.maximum(
                    np.abs(demodulated) / np.median(np.abs(demodulated)),
                    np.finfo(float).tiny,
                )
            )
            phase = np.unwrap(np.angle(demodulated))
            phase_fit = np.polyval(np.polyfit(time_ms, phase, 1), time_ms)
            residual_phase = phase - phase_fit
            axes[0, column].plot(
                time_ms, amplitude_db, alpha=0.75, label=f"RX{channel + 1}"
            )
            axes[1, column].plot(time_ms, residual_phase, alpha=0.75)
        axes[0, column].set(
            title=f"CPI {frame}: amplitude after per-RX tone fit",
            ylabel="Amplitude / RX median [dB]",
            ylim=(-25, 15),
        )
        axes[1, column].set(
            title=f"CPI {frame}: nonlinear phase residual",
            xlabel="Time from CPI start [ms]",
            ylabel="Residual phase [rad]",
            ylim=(-4, 4),
        )
        for axis in axes[:, column]:
            axis.grid(alpha=0.3)
    axes[0, 0].legend(ncol=2, fontsize="small")
    figure.savefig(output / "slow_time_examples.png", dpi=160)
    plt.close(figure)


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
        default=Path(__file__).parent / "generated/dynamics",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    rows = read_rows(args.csv)
    target_range = np.array([float(row["range_m"]) for row in rows])
    target_velocity = np.array([float(row["velocity_mps"]) for row in rows])
    target_signal = np.array(
        [
            np.mean(
                [
                    10 ** (float(row[f"rx{channel}_signal_power_db"]) / 10)
                    for channel in range(1, 9)
                ]
            )
            for row in rows
        ]
    )

    first = json.loads((args.data / "cpi_0000000000.json").read_text())
    shape = tuple(int(value) for value in first["sample_format"]["shape"])
    waveform = first["waveform"]
    sample_rate_hz = float(waveform["sample_rate_msps"]) * 1e6
    pri_s = float(waveform["chirp_period_us"]) * 1e-6
    slope = float(waveform["slope_hz_per_s"])
    range_axis = np.asarray(
        np.fft.rfftfreq(RANGE_PADDING * shape[1], 1 / sample_rate_hz)
        * SPEED_OF_LIGHT
        / (2 * slope),
        dtype=float,
    )
    range_window = np.asarray(blackman(shape[1], sym=False), dtype=float)
    native_velocity = np.asarray(
        np.fft.fftfreq(shape[0], pri_s) * SPEED_OF_LIGHT / (2 * CARRIER_HZ),
        dtype=float,
    )

    leg_frames = {
        name: np.arange(bounds[0], bounds[1] + 1, dtype=int)
        for name, bounds in LEGS.items()
    }
    analyzed_frames = np.concatenate(tuple(leg_frames.values()))
    coherence = np.full((len(rows), 8), np.nan)
    segment_snr: dict[int, list[list[float]]] = {count: [] for count in CHIRP_COUNTS}
    centered_spectra: list[FloatArray] = []

    # Retain scalar high-Doppler power versus range for every frame.  The median
    # over other times then supplies a same-range background control.
    background_cutoffs = (10, 20, 30)
    background = {
        cutoff: np.empty((len(rows), range_axis.size, 8), dtype=np.float32)
        for cutoff in background_cutoffs
    }

    for frame in range(len(rows)):
        raw = load_raw(args.data, frame, shape)
        spectrum = range_spectrum(raw, range_window)
        full_window = np.asarray(blackman(shape[0], sym=False), dtype=float)
        native = native_doppler(spectrum, full_window)
        for cutoff in background_cutoffs:
            # Keep an identical mask in every CPI so that the same-range temporal
            # control is not confounded by the tracked target velocity.
            remote = np.abs(native_velocity) >= cutoff
            background[cutoff][frame] = np.mean(np.abs(native[remote]) ** 2, axis=0)

        if frame not in analyzed_frames:
            if frame % 20 == 0:
                print(f"background {frame + 1}/{len(rows)}", flush=True)
            continue

        target_ranges = np.abs(range_axis - target_range[frame]) <= 2.0
        target_range_index = int(np.argmin(np.abs(range_axis - target_range[frame])))
        slow_time = spectrum[:, target_range_index, :]
        coherence[frame] = best_tone_coherence(slow_time, pri_s, target_velocity[frame])

        full_rd = padded_doppler(spectrum[:, target_ranges, :], full_window)
        velocity = (
            fftshift(np.fft.fftfreq(DOPPLER_PADDING * shape[0], pri_s))
            * SPEED_OF_LIGHT
            / (2 * CARRIER_HZ)
        )
        range_index = int(
            np.argmin(np.abs(range_axis[target_ranges] - target_range[frame]))
        )
        profile = np.mean(np.abs(full_rd[:, range_index, :]) ** 2, axis=1)
        peak_index = int(np.argmin(np.abs(velocity - target_velocity[frame])))
        offsets = np.arange(-160, 161)
        valid = (peak_index + offsets >= 0) & (peak_index + offsets < profile.size)
        centered = np.full(offsets.size, np.nan)
        centered[valid] = profile[peak_index + offsets[valid]] / np.max(profile)
        centered_spectra.append(centered)

        for count in CHIRP_COUNTS:
            measurements = []
            for start in range(0, shape[0], count):
                measurement, _ = segment_measurement(
                    spectrum[start : start + count],
                    range_axis,
                    pri_s,
                    target_range[frame],
                    target_velocity[frame],
                )
                measurements.append(measurement)
            segment_snr[count].append(measurements)
        if frame % 10 == 0:
            print(f"dynamics frame {frame}", flush=True)

    summary: dict[str, Any] = {
        "capture": {
            "cpi_span_ms": shape[0] * pri_s * 1e3,
            "sampled_time_ms": shape[0] * shape[1] / sample_rate_hz * 1e3,
            "native_doppler_spacing_mps": SPEED_OF_LIGHT
            / (2 * CARRIER_HZ * shape[0] * pri_s),
        },
        "coherent_gain": {},
        "best_tone_coherence": {},
        "doppler_structure": {},
        "target_conditioned_background": {},
    }

    frame_position = {frame: index for index, frame in enumerate(analyzed_frames)}
    for leg, frames in leg_frames.items():
        indices = np.array([frame_position[frame] for frame in frames])
        reference = np.array(
            [np.mean(segment_snr[128][index]) for index in indices], dtype=float
        )
        leg_result: dict[str, Any] = {}
        for count in CHIRP_COUNTS:
            values = np.array(
                [np.mean(segment_snr[count][index]) for index in indices], dtype=float
            )
            relative_db = db(values / reference)
            deficit_db = relative_db - 10 * math.log10(count / 128)
            leg_result[str(count)] = {
                "duration_ms": count * pri_s * 1e3,
                "median_gain_from_128_db": float(np.median(relative_db)),
                "median_deficit_from_ideal_db": float(np.median(deficit_db)),
                "p10_p90_deficit_db": np.percentile(deficit_db, [10, 90]).tolist(),
            }
        summary["coherent_gain"][leg] = leg_result
        values = coherence[frames]
        summary["best_tone_coherence"][leg] = {
            "median_per_rx": np.nanmedian(values, axis=0).tolist(),
            "p10_all_rx_frames": float(np.nanpercentile(values, 10)),
            "median_all_rx_frames": float(np.nanmedian(values)),
        }

    spectra = np.array(centered_spectra)
    offset_velocity = np.arange(-160, 161) * (
        SPEED_OF_LIGHT / (2 * CARRIER_HZ * DOPPLER_PADDING * shape[0] * pri_s)
    )
    core = np.abs(offset_velocity) <= 0.5
    patch = np.abs(offset_velocity) <= 2.0
    per_frame_outer = 1 - np.nansum(spectra[:, core], axis=1) / np.nansum(
        spectra[:, patch], axis=1
    )
    summary["doppler_structure"] = {
        "fraction_of_plus_minus_2_mps_power_outside_plus_minus_0_5_mps": {
            "median": float(np.nanmedian(per_frame_outer)),
            "p10_p90": np.nanpercentile(per_frame_outer, [10, 90]).tolist(),
            "by_leg": {},
        }
    }
    for leg, frames in leg_frames.items():
        indices = np.array([frame_position[frame] for frame in frames])
        leg_outer = per_frame_outer[indices]
        leg_coherence = np.mean(coherence[frames], axis=1)
        relationship = spearmanr(leg_coherence, leg_outer)
        summary["doppler_structure"][
            "fraction_of_plus_minus_2_mps_power_outside_plus_minus_0_5_mps"
        ]["by_leg"][leg] = {
            "median": float(np.nanmedian(leg_outer)),
            "p10_p90": np.nanpercentile(leg_outer, [10, 90]).tolist(),
            "coherence_spearman": float(relationship.statistic),
        }
    # A constant tone halfway between two fourfold-padded bins is the worst
    # frequency-grid placement.  It quantifies the Blackman/window baseline for
    # the same core/patch statistic and the maximum residual scalloping.
    tone_window = np.asarray(blackman(shape[0], sym=False), dtype=float)
    tone = np.exp(2j * np.pi * 0.125 * np.arange(shape[0]) / shape[0])
    tone_spectrum = (
        np.abs(
            fftshift(fft(tone_window * tone, n=DOPPLER_PADDING * shape[0]))
            / tone_window.sum()
        )
        ** 2
    )
    tone_peak = int(np.argmax(tone_spectrum))
    tone_offsets = np.arange(tone_spectrum.size) - tone_peak
    tone_velocity = tone_offsets * (
        SPEED_OF_LIGHT / (2 * CARRIER_HZ * DOPPLER_PADDING * shape[0] * pri_s)
    )
    tone_core = np.abs(tone_velocity) <= 0.5
    tone_patch = np.abs(tone_velocity) <= 2.0
    summary["doppler_structure"]["constant_tone_baseline"] = {
        "outer_fraction": float(
            1 - np.sum(tone_spectrum[tone_core]) / np.sum(tone_spectrum[tone_patch])
        ),
        "residual_scalloping_loss_db": float(db(np.max(tone_spectrum))),
    }

    target_leg = np.zeros(len(rows), dtype=bool)
    target_leg[analyzed_frames] = True
    background_per_frame: dict[int, FloatArray] = {}
    pseudo_per_frame: dict[int, FloatArray] = {}
    excess_to_signal_per_frame: dict[int, FloatArray] = {}
    for cutoff in background_cutoffs:
        ratios = []
        pseudo_ratios = []
        excess_to_signal = []
        signals = []
        for frame in analyzed_frames:
            # Exclude times when either walk leg put the reflector near this range.
            control = ~target_leg | (np.abs(target_range - target_range[frame]) > 8)
            baseline = np.median(background[cutoff][control], axis=0)
            observed = range_band_mean(
                background[cutoff][frame], range_axis, target_range[frame]
            )
            reference = range_band_mean(baseline, range_axis, target_range[frame])
            ratios.append(float(np.mean(observed / reference)))
            excess = float(np.mean(observed - reference))
            excess_to_signal.append(
                excess / target_signal[frame] if excess > 0 else np.nan
            )
            controls = []
            for offset in (-12.0, 12.0):
                if 3 < target_range[frame] + offset < 70:
                    pseudo = range_band_mean(
                        background[cutoff][frame],
                        range_axis,
                        target_range[frame] + offset,
                    )
                    pseudo_reference = range_band_mean(
                        baseline, range_axis, target_range[frame] + offset
                    )
                    controls.append(float(np.mean(pseudo / pseudo_reference)))
            pseudo_ratios.append(float(np.mean(controls)))
            signals.append(float(target_signal[frame]))
        ratio_db = db(ratios)
        pseudo_db = db(pseudo_ratios)
        excess_to_signal_db = db(excess_to_signal)
        background_per_frame[cutoff] = ratio_db
        pseudo_per_frame[cutoff] = pseudo_db
        excess_to_signal_per_frame[cutoff] = excess_to_signal_db
        correlation = spearmanr(db(signals), ratio_db)
        cutoff_result: dict[str, Any] = {
            "target_median_db_over_same_range_control": float(np.median(ratio_db)),
            "target_p10_p90_db": np.percentile(ratio_db, [10, 90]).tolist(),
            "pseudo_range_median_db_over_control": float(np.median(pseudo_db)),
            "median_positive_excess_to_target_peak_db": float(
                np.nanmedian(excess_to_signal_db)
            ),
            "signal_to_background_ratio_spearman": float(correlation.statistic),
            "spearman_pvalue": float(correlation.pvalue),
            "by_leg": {},
        }
        signal_db = db(signals)
        ranges = target_range[analyzed_frames]
        for leg, frames in leg_frames.items():
            indices = np.array([frame_position[frame] for frame in frames])
            signal_correlation = spearmanr(signal_db[indices], ratio_db[indices])
            range_correlation = spearmanr(ranges[indices], ratio_db[indices])
            cutoff_result["by_leg"][leg] = {
                "median_db_over_same_range_control": float(
                    np.median(ratio_db[indices])
                ),
                "signal_spearman": float(signal_correlation.statistic),
                "signal_spearman_pvalue": float(signal_correlation.pvalue),
                "range_spearman": float(range_correlation.statistic),
                "median_positive_excess_to_target_peak_db": float(
                    np.nanmedian(excess_to_signal_db[indices])
                ),
            }
        summary["target_conditioned_background"][str(cutoff)] = cutoff_result

    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    figure, axis = plt.subplots(figsize=(7, 5), constrained_layout=True)
    expected = 10 * np.log10(np.array(CHIRP_COUNTS) / CHIRP_COUNTS[0])
    axis.plot(CHIRP_COUNTS, expected, "k--", label="ideal constant tone")
    for leg, frames in leg_frames.items():
        indices = np.array([frame_position[frame] for frame in frames])
        reference = np.array(
            [np.mean(segment_snr[128][index]) for index in indices], dtype=float
        )
        medians = []
        lower = []
        upper = []
        for count in CHIRP_COUNTS:
            values = np.array(
                [np.mean(segment_snr[count][index]) for index in indices], dtype=float
            )
            gain = db(values / reference)
            medians.append(np.median(gain))
            percentiles = np.percentile(gain, [10, 90])
            lower.append(percentiles[0])
            upper.append(percentiles[1])
        axis.plot(CHIRP_COUNTS, medians, ".-", label=leg)
        axis.fill_between(CHIRP_COUNTS, lower, upper, alpha=0.15)
    axis.set(
        xscale="log",
        xticks=CHIRP_COUNTS,
        xticklabels=[str(value) for value in CHIRP_COUNTS],
        xlabel="Chirps per processed segment",
        ylabel="SNR gain relative to 128 chirps [dB]",
        title="Coherent concentration versus slow-time aperture",
    )
    axis.grid(alpha=0.3)
    axis.legend()
    figure.savefig(args.output / "coherent_gain.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    for leg, frames in leg_frames.items():
        indices = np.array([frame_position[frame] for frame in frames])
        median = np.nanmedian(spectra[indices], axis=0)
        axis.plot(offset_velocity, db(median), label=leg)
    axis.set(
        xlim=(-3, 3),
        ylim=(-55, 2),
        xlabel="Velocity offset from selected target cell [m/s]",
        ylabel="Mean-RX power relative to CPI peak [dB]",
        title="Median target-centered Doppler profiles",
    )
    axis.grid(alpha=0.3)
    axis.legend()
    figure.savefig(args.output / "target_centered_doppler.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(7, 5), constrained_layout=True)
    signal_db = db(target_signal[analyzed_frames])
    for leg, frames in leg_frames.items():
        indices = np.array([frame_position[frame] for frame in frames])
        axis.scatter(
            signal_db[indices],
            background_per_frame[20][indices],
            s=18,
            alpha=0.75,
            label=leg,
        )
    axis.axhline(0, color="black", linestyle=":")
    axis.set(
        xlabel="Mean-RX target-cell power [dB, arbitrary reference]",
        ylabel="Target-range background / same-range control [dB]",
        title="Background at absolute velocities beyond 20 m/s",
    )
    axis.grid(alpha=0.3)
    axis.legend()
    figure.savefig(args.output / "background_vs_signal.png", dpi=160)
    plt.close(figure)

    plot_slow_time_examples(
        args.data,
        args.output,
        shape,
        range_axis,
        range_window,
        pri_s,
        target_range,
        target_velocity,
    )

    with (args.output / "per_frame.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "leg",
                "range_m",
                "velocity_mps",
                "mean_rx_signal_power_db",
                "mean_best_tone_coherence",
                "outer_doppler_power_fraction",
                *[f"background_ratio_{cutoff}_db" for cutoff in background_cutoffs],
                *[f"pseudo_ratio_{cutoff}_db" for cutoff in background_cutoffs],
                *[
                    f"positive_excess_to_target_{cutoff}_db"
                    for cutoff in background_cutoffs
                ],
            ]
        )
        for index, frame in enumerate(analyzed_frames):
            leg = next(name for name, frames in leg_frames.items() if frame in frames)
            writer.writerow(
                [
                    frame,
                    leg,
                    target_range[frame],
                    target_velocity[frame],
                    signal_db[index],
                    np.mean(coherence[frame]),
                    per_frame_outer[index],
                    *[
                        background_per_frame[cutoff][index]
                        for cutoff in background_cutoffs
                    ],
                    *[pseudo_per_frame[cutoff][index] for cutoff in background_cutoffs],
                    *[
                        excess_to_signal_per_frame[cutoff][index]
                        for cutoff in background_cutoffs
                    ],
                ]
            )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
