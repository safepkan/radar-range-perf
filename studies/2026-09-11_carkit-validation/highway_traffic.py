"""Highway captures: what traffic seen from a bridge can and cannot show.

Captures of 2026-10-01 from a bridge over the E6 at Sandsjöbacka, pointed along
a straight stretch of about 1.2 km, our firmware, the long waveform
(unambiguous to 1259 m): TX1 and three captures with all eight TX coherently
phased. Location from ``--data``, else ``$CARKIT_HIGHWAY_DATA``, else
``~/Data/carkit/2026-10-01_highway_sandsjobacka``.

Per CPI: the moving-target SNR profile, the strongest range-Doppler cell over
|f_D| > 300 Hz per range bin (RX-mean power, Blackman-Harris/Hann windows)
over the median of those cells divided by ln 2 (the per-cell noise, which the
sparse traffic barely affects); and the CPI's broadband background for the
interference flags. Interfered CPIs are dropped. Vehicles are tracked with a
greedy constant-speed tracker; each straight segment is followed along its
line through all CPIs, and SNR_dB = a - 10 n log10(R) is fitted per pass to
its points above PASS_MIN_SNR_DB. A target of fixed RCS in free space gives
n = 4. Writes generated/highway/summary.json and range_time.png.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.signal import find_peaks

import carkit_common
from carkit_common import (
    INTERFERENCE_BAND_HZ,
    STUDY_DIR,
    BoolArray,
    FloatArray,
    db,
    interference_flags,
    write_summary,
)
from field_common import reference_radar
from radarperf import ConstantRcsTarget, Geometry
from window_common import (
    Capture,
    discover_cases,
    doppler_window,
    load_capture,
    range_window,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GENERATED_DIR = STUDY_DIR / "generated" / "highway"
DATA_ENV = "CARKIT_HIGHWAY_DATA"
DEFAULT_DATA_DIR = Path.home() / "Data" / "carkit" / "2026-10-01_highway_sandsjobacka"
MIN_DOPPLER_HZ = 300.0
FAR_DOPPLER_HZ = 1000.0
# Tracker: detection threshold, gate, longest gap, and the straight segments
# kept (points, extent, speed, residual).
DETECTION_SNR_DB = 14.0
GATE_M = 6.0
MAX_GAP_S = 0.6
SEGMENT_MIN_POINTS = 15
SEGMENT_MIN_EXTENT_M = 150.0
SPEED_RANGE_MPS = (15.0, 45.0)
SEGMENT_MAX_RESIDUAL_M = 3.0
# Passes: gate around the line, points used for the fit, minimum extent.
PASS_GATE_M = 3.0
PASS_MIN_SNR_DB = 15.0
PASS_MIN_POINTS = 20
PASS_MIN_EXTENT_M = 200.0
FAR_RANGE_M = 900.0
RANGE_LIMITS_M = (20.0, 1250.0)


def maps(capture: Capture) -> dict[str, FloatArray]:
    """Per-CPI moving-target SNR profile and interference level."""
    weights_r = range_window(capture.n_samples)
    weights_d = doppler_window(capture.n_chirps)
    doppler = capture.doppler_axis()
    moving = np.abs(doppler) > MIN_DOPPLER_HZ
    far = np.abs(doppler) > FAR_DOPPLER_HZ
    beat = capture.beat_frequency_hz(capture.range_axis())
    band = (beat > INTERFERENCE_BAND_HZ[0]) & (beat < INTERFERENCE_BAND_HZ[1])
    peak = np.zeros((capture.n_frames, beat.size))
    noise = np.zeros((capture.n_frames, beat.size))
    level = np.zeros(capture.n_frames)
    for frame in range(capture.n_frames):
        raw = capture.load(frame)
        x = raw - raw.mean(axis=(0, 1), keepdims=True)
        spectrum = np.fft.rfft(x * weights_r[None, :, None], axis=1) / weights_r.sum()
        cells = np.fft.fft(
            spectrum * (weights_d / weights_d.sum())[:, None, None], axis=0
        )
        power = np.mean(np.abs(cells) ** 2, axis=-1)  # [doppler, range]
        peak[frame] = power[moving].max(axis=0)
        noise[frame] = np.median(power[moving], axis=0) / np.log(2)
        level[frame] = float(db(np.median(power[far][:, band])))
    return {
        "snr_db": db(peak / np.median(noise, axis=0)[None, :]),
        "level_db": level,
        # CPI index times the board's CPI interval: about half the CPIs of
        # these captures were not recorded.
        "time_s": np.array(capture.cpi_times_s),
        "range_m": capture.range_axis(),
    }


def track(times: FloatArray, detections: list[FloatArray]) -> list[FloatArray]:
    """Greedy constant-speed tracks; each row is (time, range, SNR)."""
    tracks: list[list[FloatArray]] = []
    for t, rows in zip(times, detections):
        live = [tr for tr in tracks if t - tr[-1][0] <= MAX_GAP_S]
        predictions = []
        for tr in live:
            first = tr[max(0, len(tr) - 6)]
            last = tr[-1]
            rate = (
                (last[1] - first[1]) / (last[0] - first[0])
                if last[0] > first[0]
                else 0.0
            )
            predictions.append(last[1] + rate * (t - last[0]))
        candidates = sorted(
            (abs(row[1] - predictions[i]), i, j)
            for i in range(len(live))
            for j, row in enumerate(rows)
            if abs(row[1] - predictions[i]) < GATE_M
        )
        taken_tracks: set[int] = set()
        taken_rows: set[int] = set()
        for _, i, j in candidates:
            if i in taken_tracks or j in taken_rows:
                continue
            live[i].append(rows[j])
            taken_tracks.add(i)
            taken_rows.add(j)
        tracks.extend([row] for j, row in enumerate(rows) if j not in taken_rows)
    return [np.array(tr) for tr in tracks]


def passes(values: dict[str, FloatArray], keep: BoolArray) -> list[dict[str, Any]]:
    """Straight segments followed along their line; range exponent per pass."""
    snr, range_m = values["snr_db"], values["range_m"]
    times = values["time_s"]
    detections = []
    for frame in range(len(times)):
        if not keep[frame]:
            detections.append(np.zeros((0, 3)))
            continue
        peaks, _ = find_peaks(snr[frame], height=DETECTION_SNR_DB, distance=4)
        peaks = peaks[
            (range_m[peaks] > RANGE_LIMITS_M[0]) & (range_m[peaks] < RANGE_LIMITS_M[1])
        ]
        detections.append(
            np.column_stack(
                (np.full(peaks.size, times[frame]), range_m[peaks], snr[frame, peaks])
            )
        )
    lines: list[tuple[float, float]] = []
    for segment in track(times, detections):
        if (
            len(segment) < SEGMENT_MIN_POINTS
            or np.ptp(segment[:, 1]) < SEGMENT_MIN_EXTENT_M
        ):
            continue
        speed, start = np.polyfit(segment[:, 0], segment[:, 1], 1)
        residual = segment[:, 1] - (start + speed * segment[:, 0])
        if not SPEED_RANGE_MPS[0] < abs(speed) < SPEED_RANGE_MPS[1]:
            continue
        if residual.std() > SEGMENT_MAX_RESIDUAL_M:
            continue
        if any(abs(speed - s) < 1.0 and abs(start - r0) < 8.0 for s, r0 in lines):
            continue
        lines.append((float(speed), float(start)))
    found = []
    for speed, start in lines:
        ranges, levels = [], []
        for index in np.flatnonzero(keep):
            predicted = start + speed * times[index]
            if not RANGE_LIMITS_M[0] < predicted < RANGE_LIMITS_M[1]:
                continue
            near = np.flatnonzero(np.abs(range_m - predicted) < PASS_GATE_M)
            k = near[np.argmax(snr[index, near])]
            ranges.append(range_m[k])
            levels.append(snr[index, k])
        r, s = np.array(ranges), np.array(levels)
        used = s > PASS_MIN_SNR_DB
        if used.sum() < PASS_MIN_POINTS or np.ptp(r[used]) < PASS_MIN_EXTENT_M:
            continue
        exponent = -np.polyfit(np.log10(r[used]), s[used], 1)[0] / 10
        far = used & (r > FAR_RANGE_M)
        found.append(
            {
                "speed_mps": speed,
                "range_m": [float(r[used].min()), float(r[used].max())],
                "points": int(used.sum()),
                "range_exponent": float(exponent),
                "snr_beyond_900_m_db": (
                    [float(s[far].min()), float(s[far].max())] if far.any() else None
                ),
            }
        )
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    carkit_common.data_argument(parser, DATA_ENV, DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = carkit_common.resolve_data_dir(args.data, DATA_ENV, DEFAULT_DATA_DIR)

    summary: dict[str, Any] = {}
    kept: dict[str, tuple[dict[str, FloatArray], BoolArray, int]] = {}
    model_db = None
    for case in discover_cases(root):
        capture = load_capture(case, root, verify=True)
        values = maps(capture)
        flags = interference_flags(values["level_db"])
        found = passes(values, ~flags)
        exponents = np.array([p["range_exponent"] for p in found])
        far = [p["snr_beyond_900_m_db"] for p in found if p["snr_beyond_900_m_db"]]
        cpis = [
            json.loads(p.with_suffix(".json").read_text())["cpi"]
            for p in capture.binary_paths
        ]
        summary[case] = {
            "tx_channels": list(capture.tx_channels),
            "coherent_tx": capture.coherent_tx,
            "cpis": capture.n_frames,
            "cpi_index_span": int(max(cpis) - min(cpis) + 1),
            "interfered_cpis": int(flags.sum()),
            "passes": len(found),
            "range_exponent": (
                {
                    "median": float(np.median(exponents)),
                    "min": float(exponents.min()),
                    "max": float(exponents.max()),
                }
                if found
                else None
            ),
            "passes_beyond_900_m": len(far),
            "snr_beyond_900_m_db": (
                [min(f[0] for f in far), max(f[1] for f in far)] if far else None
            ),
            "pass_list": found,
        }
        kept[case] = (values, flags, len(capture.tx_channels))
        if capture.tx_channels == (1,):
            model_db = (
                reference_radar(capture)
                .link_budget(
                    ConstantRcsTarget.from_dbsm(10.0, swerling=0),
                    Geometry(range_m=1000.0),
                )
                .snr_db
            )
        print(
            f"{case}: {capture.n_frames} CPIs, {int(flags.sum())} interfered, {len(found)} passes, "
            f"exponent median {summary[case]['range_exponent']}"
        )

    # The TX1 capture and the 8TX capture with the most CPIs.
    shown: dict[str, tuple[dict[str, FloatArray], BoolArray]] = {}
    for n_tx in (1, 8):
        cases = [c for c, (_, _, n) in kept.items() if n == n_tx]
        if cases:
            best = max(cases, key=lambda c: len(kept[c][0]["time_s"]))
            shown[best] = (kept[best][0], kept[best][1])
    figure, axes = plt.subplots(
        1, len(shown), figsize=(7 * len(shown), 7), layout="constrained"
    )
    for axis, (case, (values, flags)) in zip(np.atleast_1d(axes), shown.items()):
        snr = values["snr_db"].copy()
        snr[flags] = np.nan
        image = axis.pcolormesh(
            values["range_m"], values["time_s"], snr, vmin=10, vmax=40, shading="auto"
        )
        axis.set(
            xlabel="Apparent range [m]",
            ylabel="Time [s]",
            title=f"{case}: moving-target SNR",
        )
    figure.colorbar(image, ax=axes, label="dB per RX (interfered CPIs blank)")
    figure.savefig(args.output / "range_time.png", dpi=90)
    plt.close(figure)
    write_summary(
        args.output,
        {
            "model_snr_tx1_10_dbsm_1_km_db": model_db,
            "cases": summary,
        },
    )


if __name__ == "__main__":
    main()
