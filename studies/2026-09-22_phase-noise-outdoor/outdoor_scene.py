"""Scene, reflector identification and single-RX remote-Doppler levels.

For each case: validate the capture (sizes and SHA-256), locate the reflector
and the strongest other static returns, and average the single-RX
range-Doppler power over CPIs. Levels are power per native range-Doppler bin,
in absolute ADC-count² or relative (dBc) to the reflector's own zero-Doppler
bin. The remote-Doppler background is the median over 2-15 m, excluding
±1.5 m around the reflector. Two checks accompany it: whether the remote-Doppler
power changes when the Hann slow-time window is replaced by Blackman-Harris
(noise-bandwidth corrected), which leakage from the carrier would; and the
squared coherence between RX channels, which separates channel-independent
noise from a disturbance common to all channels.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.signal import find_peaks

from outdoor_common import (
    ADC_BITS,
    CASES,
    GENERATED_DIR,
    REFLECTOR_GATE_M,
    Capture,
    FloatArray,
    data_argument,
    db,
    doppler_window,
    enbw_bins,
    load_capture,
    range_spectrum,
    range_window,
    slow_time_spectrum,
    write_summary,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

STATIC_PADDING = 8
BACKGROUND_RANGE_M = (2.0, 15.0)
BACKGROUND_EXCLUSION_M = 1.5
# Scene returns considered for the per-return phase analysis.
SCENE_RANGE_M = (2.0, 45.0)
SCENE_EXCLUSION_M = 1.0
N_SCENE_RETURNS = 3


def analyze(capture: Capture, rx: int) -> tuple[dict[str, Any], dict[str, FloatArray]]:
    """Accumulate one case over its CPIs; return its summary and arrays."""
    nc, ns, nrx = capture.shape
    ranges = capture.range_axis()
    padded_ranges = capture.range_axis(STATIC_PADDING)
    far = capture.far_doppler()
    nominal = CASES[capture.case]
    gate = (ranges >= nominal + REFLECTOR_GATE_M[0]) & (
        ranges <= nominal + REFLECTOR_GATE_M[1]
    )
    padded_gate = (padded_ranges >= nominal + REFLECTOR_GATE_M[0]) & (
        padded_ranges <= nominal + REFLECTOR_GATE_M[1]
    )
    hann = doppler_window(nc)
    blackman_harris = range_window(nc)
    enbw_ratio = enbw_bins(blackman_harris) / enbw_bins(hann)

    static = np.zeros(padded_ranges.size)
    rd_power = np.zeros((nc, ranges.size))
    far_bh = np.zeros(ranges.size)
    far_cross = np.zeros((ranges.size, nrx, nrx), dtype=complex)
    frame_peak = []
    extrema = [0, 0]
    rail_samples = 0
    for frame in range(capture.n_frames):
        raw = capture.load(frame)
        extrema = [min(extrema[0], int(raw.min())), max(extrema[1], int(raw.max()))]
        rail_samples += int(
            np.sum((raw <= -(2 ** (ADC_BITS - 1))) | (raw >= 2 ** (ADC_BITS - 1) - 1))
        )
        static += (
            np.abs(
                range_spectrum(raw[:, :, rx].mean(axis=0)[None, :], STATIC_PADDING)[0]
            )
            ** 2
        )
        spectrum = range_spectrum(raw)
        rd = slow_time_spectrum(spectrum)
        power = np.abs(rd[:, :, rx]) ** 2
        rd_power += power
        frame_peak.append(float(np.max(power[0, gate])))
        far_bh += np.mean(
            np.abs(slow_time_spectrum(spectrum[:, :, rx], blackman_harris)[far]) ** 2,
            axis=0,
        )
        remote = rd[far]
        far_cross += np.einsum("dbr,dbs->brs", remote, remote.conj()) / far.sum()
    count = capture.n_frames
    static /= count
    rd_power /= count
    far_bh /= count * enbw_ratio
    far_cross /= count

    reflector_bin = int(np.flatnonzero(padded_gate)[np.argmax(static[padded_gate])])
    reflector_m = float(padded_ranges[reflector_bin])
    peaks, _ = find_peaks(static, distance=STATIC_PADDING)
    candidates = [
        int(k)
        for k in peaks[np.argsort(static[peaks])[::-1]]
        if SCENE_RANGE_M[0] < padded_ranges[k] < SCENE_RANGE_M[1]
        and abs(padded_ranges[k] - reflector_m) > SCENE_EXCLUSION_M
    ][:N_SCENE_RETURNS]

    zero = rd_power[0]
    far_power = np.mean(rd_power[far], axis=0)
    peak_bin = int(np.flatnonzero(gate)[np.argmax(zero[gate])])
    peak = float(zero[peak_bin])
    background_mask = (
        (ranges >= BACKGROUND_RANGE_M[0])
        & (ranges <= BACKGROUND_RANGE_M[1])
        & (np.abs(ranges - reflector_m) > BACKGROUND_EXCLUSION_M)
    )
    background = float(np.median(far_power[background_mask]))
    auto = np.real(np.diagonal(far_cross, axis1=1, axis2=2))
    coherence = np.abs(far_cross) ** 2 / (auto[:, :, None] * auto[:, None, :])
    pairs = ~np.eye(nrx, dtype=bool)

    def return_entry(range_m: float) -> dict[str, Any]:
        k = int(np.argmin(np.abs(ranges - range_m)))
        return {
            "range_m": range_m,
            "static_power_db_counts2": float(
                db(static[np.argmin(np.abs(padded_ranges - range_m))])
            ),
            "native_bin_range_m": float(ranges[k]),
            "far_doppler_dbc_own_peak": float(db(far_power[k] / zero[k])),
            "window_change_db": float(db(far_bh[k] / far_power[k])),
        }

    summary: dict[str, Any] = {
        "case": capture.case,
        "nominal_range_m": CASES[capture.case],
        "frames": count,
        "shape_chirp_sample_rx": list(capture.shape),
        "sample_rate_hz": capture.sample_rate_hz,
        "chirp_period_s": capture.chirp_period_s,
        "slope_hz_per_s": capture.slope_hz_per_s,
        "center_frequency_hz": capture.center_frequency_hz,
        "sampled_bandwidth_hz": capture.sampled_bandwidth_hz,
        "pre_payload_s": capture.pre_payload_s,
        "rx_gain_db": capture.rx_gain_db,
        "adc_extrema": extrema,
        "adc_rail_samples": rail_samples,
        "reflector_range_m": reflector_m,
        "reflector_peak_db_counts2": float(db(peak)),
        "reflector_peak_per_cpi_db_counts2": db(frame_peak).tolist(),
        "far_doppler_background_db_counts2": float(db(background)),
        "far_doppler_background_dbc": float(db(background / peak)),
        "far_doppler_at_reflector_dbc": float(db(far_power[peak_bin] / peak)),
        "rx_coherence_background_median": float(
            np.median(coherence[background_mask][:, pairs])
        ),
        "rx_coherence_reflector_median": float(np.median(coherence[peak_bin][pairs])),
        "returns": [return_entry(reflector_m)]
        + [return_entry(float(padded_ranges[k])) for k in candidates],
    }
    arrays = {
        "range_m": ranges,
        "padded_range_m": padded_ranges,
        "static_power": static,
        "zero_doppler_power": zero,
        "far_doppler_power": far_power,
        "rd_power": rd_power,
    }
    return summary, arrays


def plot(
    output: Path, results: dict[str, tuple[dict[str, Any], dict[str, FloatArray]]]
) -> None:
    rx = next(iter(results.values()))[0]["rx"]
    figure, axes = plt.subplots(
        2, 1, figsize=(12, 8.5), sharex=True, layout="constrained"
    )
    for index, (case, (summary, arrays)) in enumerate(results.items()):
        color = f"C{index}"
        axes[0].plot(
            arrays["padded_range_m"],
            db(arrays["static_power"]),
            color=color,
            label=case,
        )
        axes[1].plot(
            arrays["range_m"], db(arrays["far_doppler_power"]), color=color, label=case
        )
        for axis in axes:
            axis.axvline(summary["reflector_range_m"], color=color, linestyle=":", lw=1)
    axes[0].set(
        ylim=(-30, 55),
        ylabel="dB ADC-count²",
        title=f"Static scene: chirp-mean range spectrum, RX{rx}, 8× padded",
    )
    axes[1].set(
        xlim=(0, 50),
        ylim=(-40, -20),
        xlabel="Apparent range [m]",
        ylabel="dB ADC-count² per bin",
        title=f"Mean power over |Doppler| > 5 kHz, RX{rx}; dotted: reflector",
    )
    for axis in axes:
        axis.grid(alpha=0.3)
        axis.legend(ncol=4)
    figure.savefig(output / "scene.png", dpi=130)
    plt.close(figure)

    figure, axes = plt.subplots(2, 2, figsize=(13, 9.5), layout="constrained")
    for axis, (case, (summary, arrays)) in zip(axes.flat, results.items()):
        nc = arrays["rd_power"].shape[0]
        doppler = np.fft.fftshift(np.fft.fftfreq(nc, summary["chirp_period_s"]))
        peak = 10 ** (summary["reflector_peak_db_counts2"] / 10)
        image = axis.pcolormesh(
            arrays["range_m"],
            doppler / 1e3,
            db(np.fft.fftshift(arrays["rd_power"], axes=0) / peak),
            shading="auto",
            vmin=-100,
            vmax=-40,
            rasterized=True,
        )
        axis.set(
            xlim=(0, 40),
            xlabel="Apparent range [m]",
            ylabel="Doppler [kHz]",
            title=f"{case}: reflector at {summary['reflector_range_m']:.2f} m",
        )
        figure.colorbar(
            image, ax=axis, label="dBc per bin (reflector zero-Doppler bin)"
        )
    figure.suptitle(f"Range-Doppler power, RX{rx}, averaged over ten CPIs")
    figure.savefig(output / "maps.png", dpi=110)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--rx", type=int, default=1, help="primary RX, 1-based")
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "scene")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    results = {}
    for case in CASES:
        capture = load_capture(case, args.data, verify=True)
        summary, arrays = analyze(capture, args.rx - 1)
        summary["rx"] = args.rx
        results[case] = (summary, arrays)
        np.savez_compressed(args.output / f"{case}.npz", allow_pickle=False, **arrays)
    plot(args.output, results)
    backgrounds = [s["far_doppler_background_db_counts2"] for s, _ in results.values()]
    write_summary(
        args.output,
        {
            "rx": args.rx,
            "background_range_m": list(BACKGROUND_RANGE_M),
            "background_exclusion_m": BACKGROUND_EXCLUSION_M,
            "background_spread_db": float(max(backgrounds) - min(backgrounds)),
            "max_abs_window_change_db": float(
                max(
                    abs(entry["window_change_db"])
                    for summary, _ in results.values()
                    for entry in summary["returns"]
                )
            ),
            "cases": {case: summary for case, (summary, _) in results.items()},
        },
    )


if __name__ == "__main__":
    main()
