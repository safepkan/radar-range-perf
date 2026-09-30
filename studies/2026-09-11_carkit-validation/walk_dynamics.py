"""Target dynamics: CPI length, Doppler structure, RX nulls and the pedestal.

Recomputes spectra from raw ADC data at the target cells from walk_extract.py,
for the two walk legs:

* CPI length: SNR gain from 128 to 1024 chirps against the ideal 3.01 dB per
  doubling, using every non-overlapping segment with its own window and target
  search. Measures mismatch to a constant-velocity tone, not oscillator
  coherence alone.
* Doppler structure: power fraction outside +/-0.5 m/s within +/-2 m/s of the
  target, and the fraction of range-bin power captured by one tone per RX.
* RX nulls: per-RX power at the common cell versus integrated over a patch,
  and the background's dominant spatial mode, for a few example CPIs.
* Pedestal: remote-Doppler background (|v| >= 10/20/30 m/s) at the target's
  range relative to the median over reflector-free control CPIs at the same
  range, and at +/-12 m pseudo-target ranges. walk_pedestal.py fits how it
  scales with target power and range.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import numpy.typing as npt
from scipy.stats import spearmanr

from carkit_common import (
    N_RX,
    SPEED_OF_LIGHT,
    FloatArray,
    db,
    write_summary,
)
from walk_common import (
    CARRIER_HZ,
    GENERATED_DIR,
    LEGS,
    PADDING,
    Capture,
    ComplexArray,
    Track,
    control_frames,
    data_argument,
    leg_frames,
    load_capture,
    native_doppler,
    padded_doppler,
    range_spectrum,
    read_track,
    window,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CHIRP_COUNTS = (128, 256, 512, 1024)
BACKGROUND_CUTOFFS_MPS = (10, 20, 30)
PSEUDO_OFFSETS_M = (-12.0, 12.0)
PATCH_EXAMPLE_FRAMES = (40, 89, 100, 105, 127)
SLOW_TIME_EXAMPLE_FRAMES = (40, 100)
NULL_PLOT_FRAME = 100


def velocity_mps(doppler_hz: npt.ArrayLike) -> FloatArray:
    """Radial velocity for Doppler frequencies at the carrier."""
    return np.asarray(
        SPEED_OF_LIGHT * np.asarray(doppler_hz, dtype=float) / (2 * CARRIER_HZ)
    )


def segment_snr(
    spectrum: ComplexArray,
    range_axis: FloatArray,
    capture: Capture,
    target_range_m: float,
    target_velocity_mps: float,
) -> float:
    """Common-cell linear-RX-mean SNR over far-quarter noise for one segment."""
    n_chirps = spectrum.shape[0]
    native_velocity = velocity_mps(np.fft.fftfreq(n_chirps, capture.chirp_period_s))
    far = range_axis >= 0.75 * range_axis[-1]
    native = native_doppler(spectrum)
    noise = np.mean(
        np.abs(native[np.abs(native_velocity) >= 10][:, far, :]) ** 2, axis=(0, 1)
    )
    ranges = np.abs(range_axis - target_range_m) <= 2.0
    velocity = capture.padded_velocity(n_chirps)
    velocities = np.abs(velocity - target_velocity_mps) <= 2.0
    candidate = np.abs(padded_doppler(spectrum[:, ranges, :])[velocities]) ** 2 / noise
    locator = np.mean(candidate, axis=2)
    index = np.unravel_index(int(np.argmax(locator)), locator.shape)
    return float(np.mean(candidate[index[0], index[1]]))


def best_tone_fraction(
    slow_time: ComplexArray, capture: Capture, target_velocity_mps: float
) -> FloatArray:
    """Fraction of window-weighted range-bin power captured by the best tone."""
    weights = window(slow_time.shape[0])
    transformed = padded_doppler(slow_time)
    nearby = np.abs(capture.padded_velocity() - target_velocity_mps) <= 2.0
    peak = np.max(np.abs(transformed[nearby]) ** 2, axis=0)
    weighted_input = (
        np.sum(weights[:, None] * np.abs(slow_time) ** 2, axis=0) / weights.sum()
    )
    return np.asarray(peak / weighted_input)


def patch_check(
    spectrum: ComplexArray,
    native: ComplexArray,
    range_axis: FloatArray,
    capture: Capture,
    target_range_m: float,
    target_velocity_mps: float,
) -> tuple[dict[str, Any], FloatArray, FloatArray]:
    """Common-cell versus patch power per RX and the background's dominant mode."""
    near = np.abs(range_axis - target_range_m) <= 2.0
    velocity = capture.padded_velocity()
    near_velocity = np.abs(velocity - target_velocity_mps) <= 1.0
    patch = padded_doppler(spectrum[:, near, :])[near_velocity]
    power = np.abs(patch) ** 2
    iv = int(np.argmin(np.abs(velocity[near_velocity] - target_velocity_mps)))
    ir = int(np.argmin(np.abs(range_axis[near] - target_range_m)))
    central = power[iv, ir]
    integrated = power.sum(axis=(0, 1))

    spacing = float(range_axis[1] - range_axis[0])
    remote = np.abs(capture.native_velocity()) >= 10
    at_range = np.abs(range_axis - target_range_m) <= (PADDING + 0.5) * spacing
    background = native[remote][:, at_range].reshape(-1, N_RX)
    moments = background.T @ background.conj() / len(background)
    eigenvalues, eigenvectors = np.linalg.eigh(moments)
    target = patch[iv, ir]
    alignment = float(
        np.abs(np.vdot(eigenvectors[:, -1], target)) ** 2 / np.vdot(target, target).real
    )
    result = {
        "common_cell_relative_to_strongest_rx_db": db(central / central.max()).tolist(),
        "patch_relative_to_strongest_rx_db": db(integrated / integrated.max()).tolist(),
        "background_largest_eigenvalue_fraction": float(
            eigenvalues[-1] / eigenvalues.sum()
        ),
        "background_dominant_mode_target_alignment": alignment,
    }
    cut = db(power[:, ir, :] / central.max())
    return result, velocity[near_velocity], cut


def plot_slow_time_examples(
    capture: Capture, output: Path, range_axis: FloatArray, track: Track
) -> None:
    """Amplitude and nonlinear phase left after a per-RX constant-tone fit."""
    figure, axes = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    time_s = np.arange(capture.n_chirps) * capture.chirp_period_s
    velocity = capture.padded_velocity()
    for column, frame in enumerate(SLOW_TIME_EXAMPLE_FRAMES):
        spectrum = range_spectrum(capture.load(frame))
        slow_time = spectrum[
            :, int(np.argmin(np.abs(range_axis - track.range_m[frame]))), :
        ]
        transformed = padded_doppler(slow_time)
        nearby = np.flatnonzero(np.abs(velocity - track.velocity_mps[frame]) <= 2.0)
        for channel in range(N_RX):
            peak = nearby[int(np.argmax(np.abs(transformed[nearby, channel])))]
            frequency_hz = 2 * velocity[peak] * CARRIER_HZ / SPEED_OF_LIGHT
            residual = slow_time[:, channel] * np.exp(
                -2j * np.pi * frequency_hz * time_s
            )
            amplitude_db = 20 * np.log10(
                np.maximum(np.abs(residual) / np.median(np.abs(residual)), 1e-300)
            )
            phase = np.unwrap(np.angle(residual))
            phase -= np.polyval(np.polyfit(time_s, phase, 1), time_s)
            axes[0, column].plot(
                time_s * 1e3, amplitude_db, alpha=0.75, label=f"RX{channel + 1}"
            )
            axes[1, column].plot(time_s * 1e3, phase, alpha=0.75)
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


def range_band_mean(
    values: FloatArray, range_axis: FloatArray, center_m: float
) -> FloatArray:
    """Mean over padded range bins within one native bin of ``center_m``."""
    spacing = float(range_axis[1] - range_axis[0])
    return np.asarray(
        np.mean(
            values[np.abs(range_axis - center_m) <= (PADDING + 0.5) * spacing], axis=0
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "dynamics")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    track = read_track()
    capture = load_capture(args.data)
    range_axis = capture.range_axis()
    native_velocity = capture.native_velocity()
    frames_by_leg = {leg: leg_frames(leg) for leg in LEGS}
    analyzed = np.concatenate(tuple(frames_by_leg.values()))
    target_signal = np.mean(track.rx_signal_power, axis=1)

    tone_fraction = np.full((capture.n_frames, N_RX), np.nan)
    segments: dict[int, dict[int, float]] = {count: {} for count in CHIRP_COUNTS}
    centered: dict[int, FloatArray] = {}
    patches: list[dict[str, Any]] = []
    null_plot: tuple[FloatArray, FloatArray] | None = None
    background = {
        cutoff: np.empty((capture.n_frames, range_axis.size, N_RX))
        for cutoff in BACKGROUND_CUTOFFS_MPS
    }
    offsets = np.arange(-160, 161)

    for frame in range(capture.n_frames):
        spectrum = range_spectrum(capture.load(frame))
        native = native_doppler(spectrum)
        for cutoff in BACKGROUND_CUTOFFS_MPS:
            # One fixed mask in every CPI, so the same-range temporal control is
            # not confounded by the tracked target's velocity.
            remote = np.abs(native_velocity) >= cutoff
            background[cutoff][frame] = np.mean(np.abs(native[remote]) ** 2, axis=0)
        if frame % 20 == 0:
            print(f"dynamics CPI {frame}/{capture.n_frames - 1}", flush=True)
        if frame not in analyzed:
            continue

        r, v = float(track.range_m[frame]), float(track.velocity_mps[frame])
        range_index = int(np.argmin(np.abs(range_axis - r)))
        tone_fraction[frame] = best_tone_fraction(
            spectrum[:, range_index, :], capture, v
        )

        near = np.abs(range_axis - r) <= 2.0
        profile = np.mean(
            np.abs(
                padded_doppler(spectrum[:, near, :])[
                    :, int(np.argmin(np.abs(range_axis[near] - r))), :
                ]
            )
            ** 2,
            axis=1,
        )
        peak = int(np.argmin(np.abs(capture.padded_velocity() - v)))
        valid = (peak + offsets >= 0) & (peak + offsets < profile.size)
        line = np.full(offsets.size, np.nan)
        line[valid] = profile[peak + offsets[valid]] / np.max(profile)
        centered[frame] = line

        for count in CHIRP_COUNTS:
            values = [
                segment_snr(spectrum[start : start + count], range_axis, capture, r, v)
                for start in range(0, capture.n_chirps, count)
            ]
            segments[count][frame] = float(np.mean(values))

        if frame in PATCH_EXAMPLE_FRAMES:
            result, cut_velocity, cut = patch_check(
                spectrum, native, range_axis, capture, r, v
            )
            patches.append({"frame": frame, **result})
            if frame == NULL_PLOT_FRAME:
                null_plot = (cut_velocity, cut)

    summary: dict[str, Any] = {
        "capture": {
            "cpi_span_ms": capture.n_chirps * capture.chirp_period_s * 1e3,
            "sampled_time_ms": capture.n_chirps
            * capture.n_samples
            / capture.sample_rate_hz
            * 1e3,
            "native_doppler_spacing_mps": float(native_velocity[1]),
        },
        "cpi_length": {},
        "best_tone_fraction": {},
        "doppler_structure": {},
        "rx_null_examples": patches,
        "pedestal": {},
    }

    offset_velocity = offsets * float(
        capture.padded_velocity()[1] - capture.padded_velocity()[0]
    )
    core = np.abs(offset_velocity) <= 0.5
    patch = np.abs(offset_velocity) <= 2.0
    outer = {
        frame: float(1 - np.nansum(line[core]) / np.nansum(line[patch]))
        for frame, line in centered.items()
    }
    for leg, frames in frames_by_leg.items():
        reference = np.array([segments[128][f] for f in frames])
        leg_result = {}
        for count in CHIRP_COUNTS:
            gain_db = db(np.array([segments[count][f] for f in frames]) / reference)
            deficit_db = gain_db - 10 * math.log10(count / 128)
            leg_result[str(count)] = {
                "duration_ms": count * capture.chirp_period_s * 1e3,
                "median_gain_from_128_db": float(np.median(gain_db)),
                "median_deficit_db": float(np.median(deficit_db)),
                "p10_p90_deficit_db": np.percentile(deficit_db, [10, 90]).tolist(),
            }
        summary["cpi_length"][leg] = leg_result
        summary["best_tone_fraction"][leg] = float(np.nanmedian(tone_fraction[frames]))
        leg_outer = np.array([outer[f] for f in frames])
        summary["doppler_structure"][leg] = {
            "outer_fraction_median": float(np.median(leg_outer)),
            "outer_fraction_p10_p90": np.percentile(leg_outer, [10, 90]).tolist(),
            "spearman_with_tone_fraction": float(
                spearmanr(np.mean(tone_fraction[frames], axis=1), leg_outer).statistic
            ),
        }
    # A constant tone halfway between padded bins: window-only baseline.
    weights = window(capture.n_chirps)
    tone = np.exp(2j * np.pi * 0.125 * np.arange(capture.n_chirps) / capture.n_chirps)
    tone_power = (
        np.abs(
            np.fft.fftshift(np.fft.fft(weights * tone, n=PADDING * capture.n_chirps))
            / weights.sum()
        )
        ** 2
    )
    tone_offset = (np.arange(tone_power.size) - int(np.argmax(tone_power))) * float(
        capture.padded_velocity()[1] - capture.padded_velocity()[0]
    )
    summary["doppler_structure"]["constant_tone_outer_fraction"] = float(
        1
        - np.sum(tone_power[np.abs(tone_offset) <= 0.5])
        / np.sum(tone_power[np.abs(tone_offset) <= 2.0])
    )
    summary["doppler_structure"]["residual_scalloping_db"] = float(
        db(np.max(tone_power))
    )

    pedestal_columns: dict[str, FloatArray] = {}
    for cutoff in BACKGROUND_CUTOFFS_MPS:
        ratios, pseudo, excess_to_peak = [], [], []
        for frame in analyzed:
            r = float(track.range_m[frame])
            baseline = np.median(
                background[cutoff][control_frames(track.range_m, r)], axis=0
            )
            observed = range_band_mean(background[cutoff][frame], range_axis, r)
            reference = range_band_mean(baseline, range_axis, r)
            ratios.append(float(np.mean(observed / reference)))
            excess = float(np.mean(observed - reference))
            excess_to_peak.append(
                excess / target_signal[frame] if excess > 0 else np.nan
            )
            pseudo_ratios = [
                float(
                    np.mean(
                        range_band_mean(
                            background[cutoff][frame], range_axis, r + offset
                        )
                        / range_band_mean(baseline, range_axis, r + offset)
                    )
                )
                for offset in PSEUDO_OFFSETS_M
                if 3 < r + offset < 70
            ]
            pseudo.append(float(np.mean(pseudo_ratios)))
        ratio_db = db(ratios)
        pedestal_columns[f"background_ratio_{cutoff}_db"] = ratio_db
        pedestal_columns[f"pseudo_ratio_{cutoff}_db"] = db(pseudo)
        pedestal_columns[f"positive_excess_to_target_{cutoff}_db"] = db(excess_to_peak)
        by_leg = {}
        for leg in LEGS:
            mask = np.isin(analyzed, frames_by_leg[leg])
            by_leg[leg] = {
                "median_excess_db": float(np.median(ratio_db[mask])),
                "median_pseudo_range_excess_db": float(np.median(db(pseudo)[mask])),
                "spearman_with_target_power": float(
                    spearmanr(target_signal[analyzed][mask], ratio_db[mask]).statistic
                ),
            }
        summary["pedestal"][f"abs_v_ge_{cutoff}_mps"] = by_leg
    write_summary(args.output, summary)

    with (args.output / "per_frame.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "leg",
                "range_m",
                "velocity_mps",
                "mean_rx_signal_power_db",
                "best_tone_fraction",
                "outer_doppler_power_fraction",
                *pedestal_columns,
            ]
        )
        for index, frame in enumerate(analyzed):
            writer.writerow(
                [
                    int(frame),
                    next(
                        leg for leg, frames in frames_by_leg.items() if frame in frames
                    ),
                    track.range_m[frame],
                    track.velocity_mps[frame],
                    float(db(target_signal[frame])),
                    float(np.mean(tone_fraction[frame])),
                    outer[int(frame)],
                    *[values[index] for values in pedestal_columns.values()],
                ]
            )

    figure, axis = plt.subplots(figsize=(7, 5), constrained_layout=True)
    ideal = 10 * np.log10(np.array(CHIRP_COUNTS) / CHIRP_COUNTS[0])
    axis.plot(CHIRP_COUNTS, ideal, "k--", label="ideal constant tone")
    for leg, frames in frames_by_leg.items():
        reference = np.array([segments[128][f] for f in frames])
        gains = [
            db(np.array([segments[count][f] for f in frames]) / reference)
            for count in CHIRP_COUNTS
        ]
        axis.plot(CHIRP_COUNTS, [np.median(g) for g in gains], ".-", label=leg)
        axis.fill_between(
            CHIRP_COUNTS,
            [np.percentile(g, 10) for g in gains],
            [np.percentile(g, 90) for g in gains],
            alpha=0.15,
        )
    axis.set(
        xscale="log",
        xlabel="Chirps per processed segment",
        ylabel="SNR gain relative to 128 chirps [dB]",
        title="SNR gain versus CPI length (median, p10-p90)",
    )
    axis.set_xticks(CHIRP_COUNTS, [str(count) for count in CHIRP_COUNTS])
    axis.minorticks_off()
    axis.grid(alpha=0.3)
    axis.legend()
    figure.savefig(args.output / "cpi_length.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    for leg, frames in frames_by_leg.items():
        median = np.nanmedian(np.array([centered[f] for f in frames]), axis=0)
        axis.plot(offset_velocity, db(median), label=leg)
    axis.set(
        xlim=(-3, 3),
        ylim=(-55, 2),
        xlabel="Velocity offset from target cell [m/s]",
        ylabel="Mean-RX power relative to CPI peak [dB]",
        title="Median target-centred Doppler profiles",
    )
    axis.grid(alpha=0.3)
    axis.legend()
    figure.savefig(args.output / "doppler_profiles.png", dpi=160)
    plt.close(figure)

    if null_plot is not None:
        figure, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
        for channel in range(N_RX):
            axis.plot(null_plot[0], null_plot[1][:, channel], label=f"RX{channel + 1}")
        axis.axvline(
            track.velocity_mps[NULL_PLOT_FRAME],
            color="black",
            linestyle=":",
            label="common cell",
        )
        axis.set(
            xlabel="Radial velocity [m/s]",
            ylabel="Power relative to strongest RX at common cell [dB]",
            ylim=(-50, 3),
            title=f"CPI {NULL_PLOT_FRAME}: per-RX Doppler cuts at the common target range",
        )
        axis.legend(ncol=3)
        axis.grid(alpha=0.3)
        figure.savefig(args.output / "rx_null_example.png", dpi=160)
        plt.close(figure)

    plot_slow_time_examples(capture, args.output, range_axis, track)


if __name__ == "__main__":
    main()
