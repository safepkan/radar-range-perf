"""Range scale of our firmware from moving vehicles, without measured distances.

A vehicle's apparent range comes from its beat frequency, so it carries any
error in the slope or the ADC sample rate. Its Doppler gives its radial speed
from the carrier frequency alone, and the CPIs start at intervals timed by the
board. Tracked over CPIs, the change in apparent range against the
Doppler-integrated distance (carkit_common.track_range_scale) is the range
scale: 1 if slope and sample rate are what the sidecar says.

In each CPI of the 2026-09-30 captures, moving targets are the local maxima of
the RX-summed range-Doppler power (fourfold padding in range and Doppler,
Blackman-Harris and Hann) at least 16 dB above that range bin's median over
Doppler, outside ±300 Hz and beyond 15 m. Targets are linked from CPI to CPI
by range alone: a speed of 8-45 m/s between neighbouring CPIs, then the
predicted range within 0.6 m and the aliased Doppler within 300 Hz. The
Doppler sign convention is the one under which the tracks agree with their
range rates. Tracks count if they span at least five CPIs, lie beyond 60 m
(nearer vehicles turn, so their strongest scatterer moves along the body) and
fit within 15 cm rms; the result is their median and the inverse-variance
weighted mean of those within 0.1 of it, with p5-p95 from resampling tracks.
The Infineon recording is not used: under DDMA every vehicle appears eight
times in Doppler.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.ndimage import maximum_filter

from carkit_common import (
    SPEED_OF_LIGHT,
    FloatArray,
    db,
    track_range_scale,
    write_summary,
)
from window_common import (
    CASES,
    GENERATED_DIR,
    Capture,
    data_arguments,
    load_capture,
    range_window,
    doppler_window,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PADDING = 4
MIN_LEVEL_DB = 16.0
MIN_DOPPLER_HZ = 300.0
MIN_RANGE_M = 15.0
MAX_DETECTIONS = 120
SPEED_LIMITS_MPS = (8.0, 45.0)
RANGE_GATE_M = 0.6
DOPPLER_GATE_HZ = 300.0
MIN_CPIS = 5
MIN_TRACK_RANGE_M = 60.0
MAX_RMS_M = 0.15
OUTLIER_LIMIT = 0.1
BOOTSTRAP = 2000
# No scene in view.
EXCLUDED = ("long-8TX-0dB",)


def detections(capture: Capture, frame: int) -> FloatArray:
    """Moving targets in one CPI: rows (range m, aliased Doppler Hz)."""
    raw = capture.load(frame)
    x = raw - raw.mean(axis=(0, 1), keepdims=True)
    nc, ns, _ = x.shape
    range_weights = range_window(ns)
    doppler_weights = doppler_window(nc)
    spectrum = np.fft.rfft(x * range_weights[None, :, None], PADDING * ns, axis=1)
    spectrum = np.fft.fft(
        spectrum * doppler_weights[:, None, None], PADDING * nc, axis=0
    )
    level = db(np.sum(np.abs(spectrum) ** 2, axis=-1))
    ranges = capture.range_axis(PADDING)
    doppler = np.fft.fftfreq(PADDING * nc, capture.chirp_period_s)
    peak = level == maximum_filter(level, size=(3 * PADDING, 3 * PADDING), mode="wrap")
    strong = level - np.median(level, axis=0, keepdims=True) > MIN_LEVEL_DB
    allowed = (ranges[None, :] > MIN_RANGE_M) & (
        np.abs(doppler)[:, None] > MIN_DOPPLER_HZ
    )
    found = np.argwhere(peak & strong & allowed)
    found = found[np.argsort(-level[found[:, 0], found[:, 1]])][:MAX_DETECTIONS]
    rows = []
    for d, k in found:
        if not 0 < k < level.shape[1] - 1:
            continue
        left, centre, right = level[d, k - 1 : k + 2]
        offset = 0.5 * (left - right) / (left - 2 * centre + right)
        below, above = (
            level[(d - 1) % level.shape[0], k],
            level[(d + 1) % level.shape[0], k],
        )
        doppler_offset = 0.5 * (below - above) / (below - 2 * centre + above)
        rows.append(
            (
                ranges[k] + offset * (ranges[1] - ranges[0]),
                doppler[d] + doppler_offset * (doppler[1] - doppler[0]),
            )
        )
    return np.array(rows).reshape(-1, 2)


def aliased_difference(first: float, second: float, prf: float) -> float:
    return float(abs((second - first + prf / 2) % prf - prf / 2))


def build_tracks(capture: Capture) -> list[FloatArray]:
    """Greedy CPI-to-CPI tracks: rows (time s, range m, aliased Doppler Hz)."""
    times = capture.cpi_times_s
    prf = 1 / capture.chirp_period_s
    found = [detections(capture, frame) for frame in range(capture.n_frames)]
    used = [np.zeros(len(rows), dtype=bool) for rows in found]
    tracks = []
    for start in range(capture.n_frames - 1):
        step = times[start + 1] - times[start]
        for i, (range_a, doppler_a) in enumerate(found[start]):
            if used[start][i]:
                continue
            for j, (range_b, doppler_b) in enumerate(found[start + 1]):
                speed = abs(range_b - range_a) / step
                if used[start + 1][j] or not (
                    SPEED_LIMITS_MPS[0] < speed < SPEED_LIMITS_MPS[1]
                ):
                    continue
                if aliased_difference(doppler_a, doppler_b, prf) > DOPPLER_GATE_HZ:
                    continue
                points = [
                    (times[start], range_a, doppler_a),
                    (times[start + 1], range_b, doppler_b),
                ]
                members = [(start, i), (start + 1, j)]
                rate = (range_b - range_a) / step
                for frame in range(start + 2, capture.n_frames):
                    last_time, last_range, last_doppler = points[-1]
                    predicted = last_range + rate * (times[frame] - last_time)
                    options = [
                        (abs(r - predicted), k)
                        for k, (r, f) in enumerate(found[frame])
                        if not used[frame][k]
                        and abs(r - predicted) < RANGE_GATE_M
                        and aliased_difference(last_doppler, f, prf) < DOPPLER_GATE_HZ
                    ]
                    if not options:
                        break
                    _, k = min(options)
                    points.append((times[frame], *found[frame][k]))
                    members.append((frame, k))
                    track = np.array(points)
                    rate = float(np.polyfit(track[:, 0], track[:, 1], 1)[0])
                if len(points) >= MIN_CPIS:
                    for frame, k in members:
                        used[frame][k] = True
                    tracks.append(np.array(points))
                    break
    return tracks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_arguments(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "range_scale")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261001)

    rows: list[dict[str, Any]] = []
    for case in CASES:
        if case in EXCLUDED:
            continue
        capture = load_capture(case, args.data)
        prf = 1 / capture.chirp_period_s
        wavelength = SPEED_OF_LIGHT / capture.center_frequency_hz
        for track in build_tracks(capture):
            times, ranges, doppler = track.T
            entry: dict[str, Any] = {
                "case": case,
                "cpis": len(track),
                "mean_range_m": float(ranges.mean()),
                "range_rate_mps": float(np.polyfit(times, ranges, 1)[0]),
            }
            for sign in (+1, -1):
                scale, error, rms = track_range_scale(
                    times, ranges, doppler, prf, wavelength, sign
                )
                entry[f"sign_{sign:+d}"] = {
                    "scale": scale,
                    "standard_error": error,
                    "rms_m": rms,
                }
            rows.append(entry)

    def selected(sign: int) -> list[dict[str, Any]]:
        key = f"sign_{sign:+d}"
        return [
            row
            for row in rows
            if row["mean_range_m"] >= MIN_TRACK_RANGE_M
            and row[key]["rms_m"] <= MAX_RMS_M
        ]

    medians = {
        sign: float(
            np.median([row[f"sign_{sign:+d}"]["scale"] for row in selected(sign)])
        )
        for sign in (+1, -1)
    }
    sign = min(medians, key=lambda value: abs(medians[value] - 1))
    key = f"sign_{sign:+d}"
    chosen = selected(sign)
    scales = np.array([row[key]["scale"] for row in chosen])
    errors = np.array([row[key]["standard_error"] for row in chosen])
    median = float(np.median(scales))
    inliers = np.abs(scales - median) < OUTLIER_LIMIT

    def weighted(values: FloatArray, sigma: FloatArray) -> float:
        weights = 1 / sigma**2
        return float(np.sum(weights * values) / np.sum(weights))

    estimate = weighted(scales[inliers], errors[inliers])
    resampled = []
    for _ in range(BOOTSTRAP):
        pick = rng.integers(0, inliers.sum(), inliers.sum())
        resampled.append(weighted(scales[inliers][pick], errors[inliers][pick]))

    figure, axis = plt.subplots(figsize=(9, 5), layout="constrained")
    for index, case in enumerate(sorted({row["case"] for row in chosen})):
        for keep, style in ((True, "o"), (False, "o")):
            mine = [
                row
                for row, inlier in zip(chosen, inliers)
                if row["case"] == case and inlier == keep
            ]
            if not mine:
                continue
            axis.errorbar(
                [row["mean_range_m"] for row in mine],
                [row[key]["scale"] for row in mine],
                yerr=[row[key]["standard_error"] for row in mine],
                fmt=style,
                color=f"C{index}",
                markerfacecolor=None if keep else "none",
                label=case if keep else f"{case}, excluded",
            )
    axis.axhline(1.0, color="black", linewidth=0.8)
    axis.axhline(estimate, color="gray", linestyle="--", linewidth=0.8)
    axis.set(
        ylim=(0.55, 1.2),
        xlabel="Mean apparent range of the track [m]",
        ylabel="Apparent range change / Doppler distance",
        title=f"Range scale from moving vehicles: {estimate:.4f} "
        f"(p5–p95 {np.percentile(resampled, 5):.4f}–{np.percentile(resampled, 95):.4f})",
    )
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8)
    figure.savefig(args.output / "range_scale.png", dpi=120)
    plt.close(figure)

    write_summary(
        args.output,
        {
            "criteria": {
                "min_level_db": MIN_LEVEL_DB,
                "min_cpis": MIN_CPIS,
                "min_track_range_m": MIN_TRACK_RANGE_M,
                "max_rms_m": MAX_RMS_M,
                "outlier_limit": OUTLIER_LIMIT,
            },
            "doppler_sign": sign,
            "median_scale_by_sign": {f"{s:+d}": v for s, v in medians.items()},
            "tracks_total": len(rows),
            "tracks_selected": len(chosen),
            "tracks_inliers": int(inliers.sum()),
            "median_scale": median,
            "weighted_scale": estimate,
            "weighted_scale_p5_p95": [
                float(np.percentile(resampled, 5)),
                float(np.percentile(resampled, 95)),
            ],
            "tracks": rows,
        },
    )


if __name__ == "__main__":
    main()
