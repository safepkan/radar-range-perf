"""Out-of-window captures: validation, scene, receiver background and levels.

For each case of both recordings: check sizes and SHA-256, the ADC levels, and
the static range profile, which is the per-chirp power of the static scene. For
a single or coherently phased transmitter that is the squared magnitude of the
range spectrum averaged coherently over the chirps; under DDMA (the 2026-08-27
recording) the transmitters' lines spread over Doppler, so the per-chirp power
averaged over chirps is used instead. Both are averaged over RX and CPIs.

The receiver background is the channel-independent part of the remote-Doppler
power (|f_D| > 1 kHz): per native range bin, the eigenvalues of the 8x8 RX
covariance over remote-Doppler cells and CPIs, of which the middle four are
averaged. A disturbance with one spatial signature (a scene return, its
pedestal, a vehicle) takes the largest eigenvalue, whatever its angle, which
products between RX pairs would not separate. Its shape against beat frequency
is compared between 0 and 10 dB TX backoff and a capture without scene.

Levels of matched static returns compare the TX settings, and the linear phase
rate of the strongest returns within each CPI is the radar's own motion.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.fft import rfft
from scipy.ndimage import median_filter

from carkit_common import (
    FloatArray,
    db,
    linear_rate,
    write_summary,
)
from window_common import (
    ADC_BITS,
    ALL_CASES,
    CASES,
    FAR_DOPPLER_HZ,
    GENERATED_DIR,
    PADDING,
    Capture,
    chirp_gains,
    data_arguments,
    load_capture,
    per_chirp_noise,
    range_spectrum,
    range_window,
    slow_time_spectrum,
    static_peaks,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Beat frequencies at which the background shape is tabulated, and its
# reference band, as in the walk's background table.
BACKGROUND_POINTS_HZ = (0.7e6, 1.0e6, 2.0e6, 3.3e6, 6.6e6, 13e6)
BACKGROUND_REFERENCE_HZ = (18e6, 24e6)
# Walk background excess over its far quarter (NOTES.md), for the figure.
WALK_BACKGROUND = {1.0e6: 1.5, 2.0e6: 1.2, 3.3e6: 0.9, 6.6e6: 0.5, 13e6: 0.2}
# Running median over range bins for the per-return noise estimate.
FLOOR_SMOOTHING_BINS = 21
# Static returns used for levels and drift.
LEVEL_MIN_SNR_DB = 10.0
# Range beyond the 2026-08-27 scene in mode 0 (unambiguous to 449 m).
INFINEON_THERMAL_RANGE_M = 300.0
MATCH_TOLERANCE_M = 0.7
DRIFT_MIN_SNR_DB = 20.0
DRIFT_RETURNS = 6
# (case, reference) pairs whose matched static returns are compared.
LEVEL_PAIRS = (
    ("medium-1TX-10dB", "medium-1TX-0dB"),
    ("short-1TX-10dB", "short-1TX-0dB"),
    ("medium-8TX-0dB", "medium-1TX-0dB"),
    ("short-8TX-0dB", "short-1TX-0dB"),
    ("medium-8TX-0dB-highway", "medium-8TX-0dB"),
    ("medium-8TX-0dB-2", "medium-8TX-0dB"),
    ("short-8TX-0dB-2", "short-8TX-0dB"),
)
BACKGROUND_CASES = (
    "short-1TX-0dB",
    "short-1TX-10dB",
    "medium-1TX-0dB",
    "medium-1TX-10dB",
    "long-1TX-0dB",
    "long-8TX-0dB",
)


def centred(raw: FloatArray) -> FloatArray:
    """Remove each RX's mean: the ADC offsets are 40-95 counts."""
    return np.asarray(raw - raw.mean(axis=(0, 1), keepdims=True))


def analyze(capture: Capture) -> tuple[dict[str, Any], dict[str, FloatArray]]:
    nc, ns, n_rx = capture.shape
    far = np.abs(capture.doppler_axis()) > FAR_DOPPLER_HZ
    weights = range_window(ns)
    profile = np.zeros(PADDING * ns // 2 + 1)
    covariance = np.zeros((ns // 2 + 1, n_rx, n_rx), dtype=complex)
    extremes = [np.inf, -np.inf]
    rms = 0.0
    offsets = np.zeros(n_rx)
    for frame in range(capture.n_frames):
        raw = capture.load(frame)
        extremes = [min(extremes[0], raw.min()), max(extremes[1], raw.max())]
        offsets += raw.mean(axis=(0, 1)) / capture.n_frames
        x = centred(raw)
        rms += float(np.mean(x.std(axis=(0, 1)))) / capture.n_frames
        padded = (
            rfft(x * weights[None, :, None], n=PADDING * ns, axis=1) / weights.sum()
        )
        if capture.ddma_length == 1:
            profile += np.mean(np.abs(padded.mean(axis=0)) ** 2, axis=-1)
        else:
            profile += np.mean(np.abs(padded) ** 2, axis=(0, 2))
        cells = slow_time_spectrum(range_spectrum(x))[far]
        covariance += np.einsum("drk,drl->rkl", cells, cells.conj())
    profile /= capture.n_frames
    covariance /= capture.n_frames * far.sum()
    eigenvalues = np.linalg.eigvalsh(covariance)
    independent = eigenvalues[:, 2:6].mean(axis=1)
    total = np.real(np.trace(covariance, axis1=1, axis2=2)) / n_rx
    native_range = capture.range_axis()
    padded_range = capture.range_axis(PADDING)
    beat = capture.beat_frequency_hz(native_range)

    reference = (beat >= BACKGROUND_REFERENCE_HZ[0]) & (
        beat <= BACKGROUND_REFERENCE_HZ[1]
    )
    reference_db = float(np.median(db(independent[reference])))
    mid_if = (beat > 1e6) & (beat < 10e6)
    summary: dict[str, Any] = {
        "recording": capture.recording,
        "firmware": capture.firmware,
        "first_timestamp": capture.timestamps[0],
        "cpis": capture.n_frames,
        "shape_chirp_sample_rx": list(capture.shape),
        "chirp_period_us": capture.chirp_period_s * 1e6,
        "slope_mhz_per_us": capture.slope_hz_per_s / 1e12,
        "sampled_bandwidth_mhz": capture.sampled_bandwidth_hz / 1e6,
        "start_frequency_ghz": capture.start_frequency_hz / 1e9,
        "pre_payload_us": capture.pre_payload_s * 1e6,
        "payload_us": capture.payload_s * 1e6,
        "flyback_us": capture.flyback_s * 1e6,
        "wait_us": capture.wait_s * 1e6,
        "max_unambiguous_range_m": float(native_range[-1]),
        "tx_channels": list(capture.tx_channels),
        "coherent_tx": capture.coherent_tx,
        "ddma_slots": list(capture.ddma_slots),
        "ddma_length": capture.ddma_length,
        "frequency_step_hz": capture.frequency_step_hz,
        "tx_backoff_db": capture.tx_backoff_db,
        "rx_setting": capture.rx_setting,
        "notes": list(capture.notes),
        "adc": {
            "full_scale_counts": 2 ** (ADC_BITS - 1),
            "min_counts": float(extremes[0]),
            "max_counts": float(extremes[1]),
            "mean_rx_rms_counts": rms,
            "offset_range_counts": [float(offsets.min()), float(offsets.max())],
        },
        "independent_background_db_counts2": reference_db,
        "total_over_independent_1_10_mhz_db": float(
            np.median(db(total[mid_if]) - db(independent[mid_if]))
        ),
        "background_shape_db": {
            f"{point / 1e6:g}": float(
                np.median(
                    db(independent[(beat >= 0.85 * point) & (beat <= 1.15 * point)])
                )
                - reference_db
            )
            for point in BACKGROUND_POINTS_HZ
        },
    }
    arrays = {
        "range_m": native_range,
        "beat_hz": beat,
        "independent_floor": independent,
        "total_floor": total,
        "padded_range_m": padded_range,
        "static_profile": profile,
    }
    return summary, arrays


def thermal_floor(case: str, arrays: dict[str, dict[str, FloatArray]]) -> FloatArray:
    """RD-cell noise floor per native range bin for SNRs and the phase step.

    For our firmware, the channel-independent floor smoothed over range. Under
    the Infineon firmware the pedestals of several scatterers in one range bin
    fill more than one eigenvalue, so both modes use the independent floor of
    mode 0 beyond its scene; they share RX settings, sample rate and chirp
    count, so their white-noise floors per cell are equal.
    """
    values = arrays[case]
    if case in CASES:
        return np.asarray(
            median_filter(
                values["independent_floor"], FLOOR_SMOOTHING_BINS, mode="nearest"
            )
        )
    reference = arrays["infineon-mode0"]
    beyond = reference["range_m"] > INFINEON_THERMAL_RANGE_M
    level = float(np.median(reference["independent_floor"][beyond]))
    return np.full(values["range_m"].shape, level)


def add_peaks(
    capture: Capture, summary: dict[str, Any], values: dict[str, FloatArray]
) -> None:
    """Per-chirp SNR profile and the strongest static returns."""
    padded_range = values["padded_range_m"]
    noise = per_chirp_noise(
        capture, np.interp(padded_range, values["range_m"], values["noise_floor"])
    )
    snr = db(values["static_profile"] / noise)
    peak_range, peak_snr = static_peaks(
        padded_range, snr, LEVEL_MIN_SNR_DB, 4 * padded_range[PADDING]
    )
    values["static_snr_db"] = snr
    values["peak_range_m"] = peak_range
    values["peak_level_db"] = np.interp(
        peak_range, padded_range, db(values["static_profile"])
    )
    summary["noise_floor_db_counts2"] = float(np.median(db(values["noise_floor"])))
    summary["strongest_static_returns"] = [
        {"range_m": float(r), "snr_per_chirp_db": float(s)}
        for r, s in sorted(zip(peak_range, peak_snr), key=lambda item: -item[1])[:10]
    ]


def drift(capture: Capture, arrays: dict[str, FloatArray]) -> dict[str, Any]:
    """Linear phase rate of the strongest static returns within each CPI."""
    strong = arrays["peak_range_m"][
        np.interp(
            arrays["peak_range_m"], arrays["padded_range_m"], arrays["static_snr_db"]
        )
        >= DRIFT_MIN_SNR_DB
    ]
    levels = np.interp(strong, arrays["padded_range_m"], arrays["static_profile"])
    strong = np.sort(strong[np.argsort(levels)[::-1][:DRIFT_RETURNS]])
    if strong.size == 0:
        return {"returns_m": [], "common_rms_hz": None}
    rates = []
    for frame in range(capture.n_frames):
        gains = chirp_gains(
            capture.load(frame),
            capture.beat_frequency_hz(strong),
            capture.sample_rate_hz,
        )
        combined = np.sum(gains * gains.mean(axis=0, keepdims=True).conj(), axis=-1)
        phase = np.unwrap(np.angle(combined), axis=0)
        rates.append(linear_rate(phase, capture.chirp_period_s) / (2 * np.pi))
    rate = np.array(rates)
    return {
        "returns_m": strong.tolist(),
        "common_rms_hz": float(np.sqrt(np.mean(rate.mean(axis=1) ** 2))),
        "common_max_abs_hz": float(np.abs(rate.mean(axis=1)).max()),
        "spread_among_returns_median_hz": float(np.median(rate.std(axis=1))),
    }


def compare_levels(
    arrays: dict[str, dict[str, FloatArray]], case: str, reference: str
) -> dict[str, Any]:
    """Level of each reference peak in ``case`` at the nearest peak within 0.7 m."""
    ref_range, ref_level = (
        arrays[reference]["peak_range_m"],
        arrays[reference]["peak_level_db"],
    )
    other = arrays[case]
    matched = []
    for r, level in zip(ref_range, ref_level):
        near = np.abs(other["padded_range_m"] - r) <= MATCH_TOLERANCE_M
        k = np.flatnonzero(near)[np.argmax(other["static_profile"][near])]
        if abs(other["padded_range_m"][k] - r) < MATCH_TOLERANCE_M:
            matched.append(
                (float(r), float(db(other["static_profile"][k])) - float(level))
            )
    changes = np.array([change for _, change in matched])
    return {
        "reference": reference,
        "matched": len(matched),
        "median_change_db": float(np.median(changes)),
        "min_change_db": float(changes.min()),
        "max_change_db": float(changes.max()),
        "per_return": [{"range_m": r, "change_db": c} for r, c in matched],
    }


def plot(output: Path, arrays: dict[str, dict[str, FloatArray]]) -> None:
    families = ("short", "medium", "long", "infineon")
    titles = {
        "short": "2026-09-30 short: 240 MHz, 23.5 MHz/µs",
        "medium": "2026-09-30 medium: 120 MHz, 11.7 MHz/µs",
        "long": "2026-09-30 long: 122 MHz, 2.98 MHz/µs",
        "infineon": "2026-08-27 Infineon firmware, 8TX DDMA (per-chirp power)",
    }
    figure, axes = plt.subplots(4, 1, figsize=(13, 15), layout="constrained")
    for axis, family in zip(axes, families):
        for case, values in arrays.items():
            if case.split("-")[0] != family:
                continue
            (line,) = axis.plot(
                values["padded_range_m"],
                db(values["static_profile"]),
                lw=0.8,
                label=case,
            )
            axis.plot(
                values["range_m"],
                db(values["independent_floor"]),
                lw=0.6,
                linestyle=":",
                color=line.get_color(),
            )
        axis.set(
            xlabel="Apparent range [m]",
            ylabel="dB ADC-count²",
            title=f"{titles[family]}; static profile (solid), independent "
            "remote-Doppler floor per cell (dotted)",
        )
        axis.grid(alpha=0.3)
        axis.legend(fontsize=8)
    figure.savefig(output / "scene.png", dpi=110)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5), layout="constrained")
    for case in BACKGROUND_CASES:
        values = arrays[case]
        capture_beat = values["beat_hz"]
        reference = (capture_beat >= BACKGROUND_REFERENCE_HZ[0]) & (
            capture_beat <= BACKGROUND_REFERENCE_HZ[1]
        )
        level = db(median_filter(values["independent_floor"], 9, mode="nearest"))
        axis.plot(
            capture_beat / 1e6,
            level - np.median(level[reference]),
            lw=0.9,
            label=case + (" (no scene)" if case == "long-8TX-0dB" else ""),
        )
    axis.plot(
        np.array(list(WALK_BACKGROUND)) / 1e6,
        list(WALK_BACKGROUND.values()),
        "ko",
        label="Walk, over far quarter",
    )
    axis.set(
        xscale="log",
        xlim=(0.3, 25),
        ylim=(-3, 3),
        xlabel="Beat frequency [MHz]",
        ylabel="dB relative to 18–24 MHz",
        title="Channel-independent remote-Doppler background",
    )
    axis.grid(alpha=0.3, which="both")
    axis.legend(fontsize=8)
    figure.savefig(output / "background.png", dpi=120)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_arguments(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "scene")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    summaries: dict[str, Any] = {}
    arrays: dict[str, dict[str, FloatArray]] = {}
    captures = {}
    for case in ALL_CASES:
        captures[case] = load_capture(case, args.data, args.infineon_data, verify=True)
        summaries[case], arrays[case] = analyze(captures[case])
    for case, capture in captures.items():
        arrays[case]["noise_floor"] = thermal_floor(case, arrays)
        add_peaks(capture, summaries[case], arrays[case])
        if case in CASES:
            summaries[case]["drift"] = drift(capture, arrays[case])
        np.savez_compressed(
            args.output / f"{case}.npz", allow_pickle=False, **arrays[case]
        )
    plot(args.output, arrays)
    write_summary(
        args.output,
        {
            "far_doppler_hz": FAR_DOPPLER_HZ,
            "background_reference_mhz": [f / 1e6 for f in BACKGROUND_REFERENCE_HZ],
            "levels": {
                case: compare_levels(arrays, case, reference)
                for case, reference in LEVEL_PAIRS
            },
            "cases": summaries,
        },
    )


if __name__ == "__main__":
    main()
