"""Test the per-chirp delay law out to about 200 m with passing vehicles.

After the walk, two vehicles approach at about 22 m/s from beyond 190 m. In
each post-walk CPI where the strongest moving return beyond 45 m is at least
MIN_SNR_DB above the per-chirp noise, its per-chirp phase is compared with that
of the strongest static return within 10-45 m (the reference, about 39 m).
Each phase is expressed as delta_f = phi / (2 pi tau). The vehicle's own
fluctuations (micro-Doppler, aspect changes) are uncorrelated with the
reference, and the cross-RX estimator removes additive noise, so

    beta = C(reference, vehicle) / C(reference, reference)

is the part of the reference's delta_f that the vehicle carries: 1 if the phase
error is 2 pi tau delta_f at both delays, tau_ref / tau_vehicle if every return
had the same phase error. Uncertainties are p5-p95 of a bootstrap over CPIs.

The reference is close to the per-chirp noise level, where phase unwrapping
slips, so phases come from the unwrap-free estimator in carkit_common. Windows
are the walk's Blackman windows; the band is the pedestal step's remote Doppler,
|v| >= 10 m/s about each return's own Doppler.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.signal import find_peaks

from carkit_common import (
    N_RX,
    SPEED_OF_LIGHT,
    FloatArray,
    chirp_fluctuations,
    chirp_gains,
    cross_channel_cross,
    cross_channel_power,
    db,
    write_summary,
)
from walk_common import (
    CARRIER_HZ,
    FAR_RANGE_FRACTION,
    GENERATED_DIR,
    LEGS,
    NOISE_ABS_VELOCITY_MIN_MPS,
    PADDING,
    Capture,
    data_argument,
    load_capture,
    native_doppler,
    range_spectrum,
    window,
    window_enbw_bins,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REFERENCE_SEARCH_M = (10.0, 45.0)
# Moving returns this close to the reference would modulate its phase.
REFERENCE_GUARD_M = 5.0
REFERENCE_MOVER_MAX_SNR_DB = -10.0
VEHICLE_SEARCH_M = (45.0, 380.0)
VEHICLE_MIN_ABS_VELOCITY_MPS = 1.0
MIN_SNR_DB = 10.0
SNR_SENSITIVITY_DB = (6.0, 8.0, 10.0, 12.0)
REMOTE_DOPPLER_MPS = 10.0
RANGE_GROUPS_M = ((45.0, 80.0), (80.0, 130.0), (130.0, 230.0))
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20260930


def parabolic_offset(left: float, centre: float, right: float) -> float:
    """Peak offset in bins from three dB values around a maximum."""
    denominator = left - 2 * centre + right
    return 0.0 if denominator == 0 else 0.5 * (left - right) / denominator


def reference_range(capture: Capture, frames: list[int]) -> float:
    """Strongest static return in REFERENCE_SEARCH_M, from the chirp-mean spectrum."""
    ranges = capture.range_axis(PADDING)
    power = np.zeros(ranges.size)
    for frame in frames:
        mean = capture.load(frame).mean(axis=0, keepdims=True)
        power += np.mean(np.abs(range_spectrum(mean)[0]) ** 2, axis=1)
    peaks, _ = find_peaks(power, distance=2 * PADDING)
    inside = peaks[
        (ranges[peaks] >= REFERENCE_SEARCH_M[0])
        & (ranges[peaks] <= REFERENCE_SEARCH_M[1])
    ]
    return float(ranges[inside[np.argmax(power[inside])]])


def analyze_frame(capture: Capture, frame: int, reference_m: float) -> dict[str, Any]:
    """Per-CPI common and cross powers of delta_f for the reference and the
    strongest moving return, with that return's per-chirp SNR."""
    raw = capture.load(frame)
    nc, ns = capture.n_chirps, capture.n_samples
    fs, slope, period = (
        capture.sample_rate_hz,
        capture.slope_hz_per_s,
        capture.chirp_period_s,
    )
    rd = native_doppler(range_spectrum(raw, padding=1))
    power = np.mean(np.abs(rd) ** 2, axis=2)
    ranges = capture.range_axis(1)
    velocity = capture.native_velocity()
    noise_cells = rd[np.abs(velocity) >= NOISE_ABS_VELOCITY_MIN_MPS][
        :, ranges >= FAR_RANGE_FRACTION * ranges[-1], :
    ]
    noise = float(np.mean(np.abs(noise_cells) ** 2))
    search = np.where(
        ((ranges >= VEHICLE_SEARCH_M[0]) & (ranges <= VEHICLE_SEARCH_M[1]))[None, :]
        & (np.abs(velocity) >= VEHICLE_MIN_ABS_VELOCITY_MPS)[:, None],
        power,
        0.0,
    )
    moving = (np.abs(velocity) >= VEHICLE_MIN_ABS_VELOCITY_MPS)[:, None]
    near_reference = (
        moving & (np.abs(ranges - reference_m) <= REFERENCE_GUARD_M)[None, :]
    )
    reference_mover_db = float(db(np.max(np.where(near_reference, power, 0.0)) / noise))
    row, col = np.unravel_index(int(np.argmax(search)), search.shape)
    # Range-Doppler SNR to per-chirp SNR: remove the Doppler integration gain.
    snr_db = float(db(power[row, col] / noise)) - 10 * np.log10(
        nc / window_enbw_bins(nc)
    )
    level = db(power)
    beat_hz = (col + parabolic_offset(*level[row, col - 1 : col + 2])) * fs / ns
    rows = [(row - 1) % nc, row, (row + 1) % nc]
    doppler_hz = float(np.fft.fftfreq(nc, period)[row]) + parabolic_offset(
        *level[rows, col]
    ) / (nc * period)
    delays = np.array(
        [2 * reference_m / SPEED_OF_LIGHT, (beat_hz - doppler_hz) / slope]
    )
    beats = np.array([slope * delays[0], beat_hz])

    gains = chirp_gains(raw, beats, fs, window(ns))
    phase, amplitude = chirp_fluctuations(gains, np.array([0.0, doppler_hz]), period)
    weights = window(nc)
    shape = (nc, 1, 1)
    frequency = (
        np.fft.fft(phase * weights.reshape(shape), axis=0)
        / weights.sum()
        / (2 * np.pi * delays[None, :, None])
    )
    relative = np.fft.fft(amplitude * weights.reshape(shape), axis=0) / weights.sum()
    band = (
        np.abs(np.fft.fftfreq(nc, period)) * SPEED_OF_LIGHT / (2 * CARRIER_HZ)
        >= REMOTE_DOPPLER_MPS
    )
    common = cross_channel_power(frequency)[band].sum(axis=0)
    return {
        "frame": frame,
        "range_m": float(delays[1] * SPEED_OF_LIGHT / 2),
        "velocity_mps": doppler_hz * SPEED_OF_LIGHT / (2 * CARRIER_HZ),
        "snr_db": snr_db,
        "reference_mover_snr_db": reference_mover_db
        - 10 * float(np.log10(nc / window_enbw_bins(nc))),
        "reference_common": float(common[0]),
        "vehicle_common": float(common[1]),
        "cross": float(
            cross_channel_cross(frequency[:, :1], frequency[:, 1:])[band].sum()
        ),
        # Vehicle phase and amplitude in rad^2 and fractional units, common to RX.
        "vehicle_phase_common": float(common[1] * (2 * np.pi * delays[1]) ** 2),
        "vehicle_amplitude_common": float(cross_channel_power(relative)[band, 1].sum()),
    }


def group_result(
    rows: list[dict[str, Any]],
    reference: FloatArray,
    enbw: float,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """beta, correlation and delta_f rms of the vehicle for a group of CPIs.

    The reference's delta_f is stationary, so its common power is pooled over
    all post-walk CPIs (``reference``) rather than only this group's.
    """
    cross = np.array([row["cross"] for row in rows])
    vehicle = np.array([row["vehicle_common"] for row in rows])
    phase = np.array([row["vehicle_phase_common"] for row in rows])
    amplitude = np.array([row["vehicle_amplitude_common"] for row in rows])
    numerator = rng.integers(0, cross.size, (BOOTSTRAP_RESAMPLES, cross.size))
    denominator = rng.integers(0, reference.size, (BOOTSTRAP_RESAMPLES, reference.size))
    samples = cross[numerator].mean(axis=1) / reference[denominator].mean(axis=1)
    return {
        "cpis": int(cross.size),
        "mean_range_m": float(np.mean([row["range_m"] for row in rows])),
        "beta": float(cross.mean() / reference.mean()),
        "beta_p5_p95": np.percentile(samples, [5, 95]).tolist(),
        "correlation": float(cross.mean() / np.sqrt(reference.mean() * vehicle.mean())),
        "vehicle_df_rms_hz": float(np.sqrt(max(vehicle.mean(), 0) / enbw)),
        "vehicle_amplitude_over_phase_db": float(db(amplitude.sum() / phase.sum())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "long_range")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    capture = load_capture(args.data)

    frames = list(range(LEGS["inbound"][1] + 1, capture.n_frames))
    reference_m = reference_range(capture, frames)
    analyzed = [analyze_frame(capture, frame, reference_m) for frame in frames]
    rows = [
        row
        for row in analyzed
        if row["reference_mover_snr_db"] < REFERENCE_MOVER_MAX_SNR_DB
    ]
    excluded = [
        row["frame"]
        for row in analyzed
        if row["reference_mover_snr_db"] >= REFERENCE_MOVER_MAX_SNR_DB
    ]
    reference = np.array([row["reference_common"] for row in rows])
    enbw = window_enbw_bins(capture.n_chirps)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    vehicles = [row for row in rows if row["snr_db"] >= MIN_SNR_DB]
    groups = {
        f"{low:g}-{high:g} m": group_result(
            [row for row in vehicles if low <= row["range_m"] < high],
            reference,
            enbw,
            rng,
        )
        for low, high in RANGE_GROUPS_M
    }
    beyond_80 = group_result(
        [row for row in vehicles if row["range_m"] >= 80], reference, enbw, rng
    )
    sensitivity = {
        f"{threshold:g} dB": group_result(
            [
                row
                for row in rows
                if row["snr_db"] >= threshold and row["range_m"] >= 80
            ],
            reference,
            enbw,
            rng,
        )["beta"]
        for threshold in SNR_SENSITIVITY_DB
    }

    with (args.output / "per_frame.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "vehicle_range_m",
                "vehicle_velocity_mps",
                "vehicle_snr_db",
                "selected",
                "beta",
                "reference_df_rms_hz",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["frame"],
                    f"{row['range_m']:.2f}",
                    f"{row['velocity_mps']:.2f}",
                    f"{row['snr_db']:.2f}",
                    row["snr_db"] >= MIN_SNR_DB,
                    f"{row['cross'] / reference.mean():.3f}",
                    f"{np.sqrt(max(row['reference_common'], 0) / enbw):.0f}",
                ]
            )

    figure, axis = plt.subplots(figsize=(9, 5.5), layout="constrained")
    axis.scatter(
        [row["range_m"] for row in vehicles],
        [row["cross"] / reference.mean() for row in vehicles],
        s=12,
        color="0.6",
        label="Single CPI",
    )
    for group in groups.values():
        low, high = group["beta_p5_p95"]
        axis.errorbar(
            group["mean_range_m"],
            group["beta"],
            yerr=[[group["beta"] - low], [high - group["beta"]]],
            fmt="o",
            color="C0",
            capsize=4,
        )
    axis.plot([], [], "o", color="C0", label="Range group, bootstrap p5–p95")
    line = np.linspace(40, 230, 100)
    axis.axhline(1, color="black", linewidth=1.2, label="Phase error ∝ delay (β = 1)")
    axis.plot(
        line,
        reference_m / line,
        color="C3",
        linestyle="--",
        label="Same phase error at every return",
    )
    axis.set(
        xlim=(40, 230),
        ylim=(0, 1.6),
        xlabel="Vehicle range [m]",
        ylabel="β: vehicle δf shared with the reference / reference δf",
        title=f"Passing vehicles against the static return at {reference_m:.1f} m, "
        f"|v| ≥ {REMOTE_DOPPLER_MPS:g} m/s",
    )
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8)
    figure.savefig(args.output / "long_range.png", dpi=150)
    plt.close(figure)

    write_summary(
        args.output,
        {
            "reference_range_m": reference_m,
            "frames_searched": [frames[0], frames[-1]],
            "min_snr_db": MIN_SNR_DB,
            "cpis": len(rows),
            "cpis_excluded_mover_near_reference": excluded,
            "cpis_with_vehicle": len(vehicles),
            "reference_df_rms_hz": float(np.sqrt(reference.mean() / enbw)),
            "rx_channels": N_RX,
            "band_min_abs_velocity_mps": REMOTE_DOPPLER_MPS,
            "groups": groups,
            "beyond_80_m": beyond_80,
            "beyond_80_m_beta_by_min_snr": sensitivity,
        },
    )


if __name__ == "__main__":
    main()
