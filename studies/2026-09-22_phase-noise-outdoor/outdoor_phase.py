"""Per-chirp phase of each strong return: phase versus amplitude, and one delta_f.

Reads the returns found by outdoor_scene.py and the raw data. For every CPI,
each return's per-chirp complex amplitude (the range spectrum at its exact beat
frequency) gives an unwrapped phase and a fractional amplitude. A cubic per CPI
is removed from both, so slow drift is not counted; the drift itself is kept as
a linear phase rate in Hz. The detrended phase of a return at round-trip delay
tau is expressed as an equivalent frequency error delta_f = phi / (2 pi tau).

Slow-time spectra use a Hann window. The common component is estimated from
products between distinct RX channels, which rejects channel-independent noise
in expectation. The same estimator between two returns gives their common
cross-power, so

    rho_k = C(ref, k) / sqrt(C(ref, ref) C(k, k))

is the correlation of the common delta_f series at return k with that at the
reflector, free of additive noise. If every return's phase error is
2 pi tau_k delta_f with one delta_f, then rho_k = 1 and every return gives the
same delta_f rms.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from outdoor_common import (
    CASES,
    FAR_DOPPLER_HZ,
    GENERATED_DIR,
    FloatArray,
    chirp_gains,
    cross_channel_cross,
    cross_channel_power,
    data_argument,
    db,
    delay_s,
    detrend,
    display_groups,
    doppler_window,
    enbw_bins,
    linear_rate,
    load_capture,
    read_summary,
    slow_time_spectrum,
    write_summary,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def analyze(
    case: str, scene: dict[str, Any], data: Path | None
) -> tuple[dict[str, Any], dict[str, FloatArray]]:
    capture = load_capture(case, data)
    rx = int(scene["rx"]) - 1
    ranges = np.array([entry["range_m"] for entry in scene["returns"]])
    tau = delay_s(ranges)
    beat = capture.beat_frequency_hz(ranges)
    far = capture.far_doppler()
    nc = capture.n_chirps

    common = np.zeros((nc, ranges.size))
    cross = np.zeros((nc, ranges.size))
    phase_power = np.zeros((nc, ranges.size))
    amplitude_power = np.zeros((nc, ranges.size))
    carrier = 0.0
    drift = []
    frame_rms = []
    for frame in range(capture.n_frames):
        gains = chirp_gains(capture.load(frame), beat, capture.sample_rate_hz)
        magnitude = np.abs(gains)
        carrier += float(np.mean(magnitude[:, 0, rx]) ** 2)
        phase = np.unwrap(np.angle(gains), axis=0)
        drift.append(
            np.mean(linear_rate(phase, capture.chirp_period_s), axis=1) / (2 * np.pi)
        )
        phase = detrend(phase)
        amplitude = detrend(magnitude / magnitude.mean(axis=0) - 1)
        phase_spectrum = slow_time_spectrum(phase)
        frequency_spectrum = phase_spectrum / (2 * np.pi * tau[None, :, None])
        frame_common = cross_channel_power(frequency_spectrum)
        common += frame_common
        cross += cross_channel_cross(frequency_spectrum[:, :1, :], frequency_spectrum)
        phase_power += np.abs(phase_spectrum[:, :, rx]) ** 2
        amplitude_power += np.abs(slow_time_spectrum(amplitude)[:, :, rx]) ** 2
        frame_rms.append(float(np.sum(frame_common[far, 0])))
    count = capture.n_frames
    common /= count
    cross /= count
    phase_power /= count
    amplitude_power /= count
    carrier /= count
    drift_hz = np.array(drift)

    enbw = enbw_bins(doppler_window(nc))
    common_band = common[far].sum(axis=0)
    df_rms = np.sqrt(np.maximum(common_band, 0) / enbw)
    rho = cross[far].sum(axis=0) / np.sqrt(common_band[0] * common_band)
    reflector_common_phase = float(np.mean(common[far, 0]) * (2 * np.pi * tau[0]) ** 2)
    phase_mean = float(np.mean(phase_power[far, 0]))
    amplitude_mean = float(np.mean(amplitude_power[far, 0]))
    background = 10 ** (float(scene["far_doppler_background_db_counts2"]) / 10)
    scene_drift = drift_hz[:, 1:]
    summary: dict[str, Any] = {
        "case": case,
        "rx": rx + 1,
        "reflector": {
            "range_m": float(ranges[0]),
            "phase_dbc": float(db(phase_mean)),
            "amplitude_dbc": float(db(amplitude_mean)),
            "additive_half_background_dbc": float(db(background / 2 / carrier)),
            "phase_minus_amplitude_dbc": float(db(phase_mean - amplitude_mean)),
            "common_phase_dbc": float(db(reflector_common_phase)),
            "common_df_rms_per_cpi_hz": (
                np.sqrt(np.maximum(frame_rms, 0) / enbw).tolist()
            ),
        },
        "returns": [
            {
                "range_m": float(ranges[k]),
                "delay_ns": float(tau[k] * 1e9),
                "df_rms_hz": float(df_rms[k]),
                "correlation_with_reflector": float(rho[k]),
                "drift_hz_per_cpi": drift_hz[:, k].tolist(),
            }
            for k in range(ranges.size)
        ],
        "drift": {
            "scene_mean_rms_hz": float(np.sqrt(np.mean(scene_drift.mean(axis=1) ** 2))),
            "scene_spread_median_hz": float(np.median(scene_drift.std(axis=1))),
            "reflector_minus_scene_rms_hz": float(
                np.sqrt(np.mean((drift_hz[:, 0] - scene_drift.mean(axis=1)) ** 2))
            ),
        },
    }
    arrays = {
        "doppler_hz": capture.doppler_axis(),
        "chirp_period_s": np.array(capture.chirp_period_s),
        "delay_s": tau,
        "common_df_per_bin": common,
        "phase_per_bin": phase_power,
        "amplitude_per_bin": amplitude_power,
        "additive_half_background": np.array(background / 2 / carrier),
    }
    return summary, arrays


def plot(
    output: Path, results: dict[str, tuple[dict[str, Any], dict[str, FloatArray]]]
) -> None:
    figure, axes = plt.subplots(
        2, 2, figsize=(13, 9), sharex=True, layout="constrained"
    )
    for axis, (case, (summary, arrays)) in zip(axes.flat, results.items()):
        doppler = arrays["doppler_hz"]
        tau = float(arrays["delay_s"][0])
        common_phase = arrays["common_df_per_bin"][:, 0] * (2 * np.pi * tau) ** 2
        for values, label in (
            (arrays["phase_per_bin"][:, 0], f"Phase, RX{summary['rx']}"),
            (
                arrays["amplitude_per_bin"][:, 0],
                f"Fractional amplitude, RX{summary['rx']}",
            ),
            (common_phase, "Phase common to all RX"),
        ):
            frequency, level = display_groups(doppler, values)
            axis.plot(frequency / 1e3, db(level), label=label)
        axis.axhline(
            float(db(arrays["additive_half_background"])),
            color="black",
            linestyle=":",
            label="Half the remote-Doppler background",
        )
        axis.axvline(FAR_DOPPLER_HZ / 1e3, color="gray", linewidth=0.8)
        axis.set(
            ylim=(-100, -55),
            title=f"{case}: reflector at {summary['reflector']['range_m']:.2f} m",
            ylabel="dB rad² or dBc per Doppler bin",
        )
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    for axis in axes[1]:
        axis.set_xlabel("|Doppler| [kHz]")
    figure.suptitle(
        "Reflector per-chirp phase and amplitude after per-CPI cubic detrending, "
        "Hann slow-time window"
    )
    figure.savefig(output / "phase_amplitude.png", dpi=130)
    plt.close(figure)

    figure, axes = plt.subplots(1, 3, figsize=(16, 5), layout="constrained")
    for index, (case, (summary, arrays)) in enumerate(results.items()):
        doppler = arrays["doppler_hz"]
        tau = float(arrays["delay_s"][0])
        enbw_hz = enbw_bins(doppler_window(doppler.size)) / (
            doppler.size * float(arrays["chirp_period_s"])
        )
        frequency, level = display_groups(doppler, arrays["common_df_per_bin"][:, 0])
        axes[0].plot(
            frequency / 1e3,
            db(level * (2 * np.pi * tau) ** 2),
            label=case,
            color=f"C{index}",
        )
        axes[1].plot(
            frequency / 1e3, db(level / enbw_hz), label=case, color=f"C{index}"
        )
        returns = summary["returns"]
        axes[2].plot(
            [entry["range_m"] for entry in returns],
            [entry["df_rms_hz"] / 1e3 for entry in returns],
            "o",
            color=f"C{index}",
            label=case,
        )
    axes[0].set(
        ylim=(-95, -60),
        ylabel="dB rad² per bin",
        title="Reflector phase common to all RX",
    )
    axes[1].set(
        ylim=(20, 45),
        ylabel="dB Hz²/Hz",
        title="Divided by (2π × delay)²: equivalent frequency error",
    )
    for axis in axes[:2]:
        axis.set(xlabel="|Doppler| [kHz]", xlim=(0, 31.4))
    axes[2].set(
        xlim=(0, 45),
        ylim=(0, 25),
        xlabel="Apparent range of the return [m]",
        ylabel="kHz rms",
        title="Frequency error at every strong return, |Doppler| > 5 kHz",
    )
    for axis in axes:
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    figure.savefig(output / "delay_scaling.png", dpi=130)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "phase")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scene = read_summary("scene")

    results = {}
    for case in CASES:
        summary, arrays = analyze(case, scene["cases"][case], args.data)
        results[case] = (summary, arrays)
        np.savez_compressed(args.output / f"{case}.npz", allow_pickle=False, **arrays)
    plot(args.output, results)

    def reflector(case: str) -> dict[str, Any]:
        entry: dict[str, Any] = results[case][0]["reflector"]
        return entry

    scaling = {}
    for bandwidth in ("400MHz", "800MHz"):
        near, far = reflector(f"{bandwidth}-5m"), reflector(f"{bandwidth}-10m")
        scaling[bandwidth] = {
            "common_phase_rise_db": far["common_phase_dbc"] - near["common_phase_dbc"],
            "delay_squared_rise_db": float(
                20 * np.log10(far["range_m"] / near["range_m"])
            ),
        }
    chirp_period = float(next(iter(results.values()))[1]["chirp_period_s"])
    write_summary(
        args.output,
        {
            "band_hz": [FAR_DOPPLER_HZ, 0.5 / chirp_period],
            "delay_scaling_between_captures": scaling,
            "cases": {case: summary for case, (summary, _) in results.items()},
        },
    )


if __name__ == "__main__":
    main()
