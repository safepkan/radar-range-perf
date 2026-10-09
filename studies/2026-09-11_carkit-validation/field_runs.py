"""Field captures: the reflector carried towards the radar, against the
tripod placements of the same session and the walk.

Two runs per waveform with TX1, and one short run with eight TX at zero phase
(no calibration record). In every CPI the reflector is the strongest return
approaching at 0.4-4 m/s within 3-60 m in the mean of per-RX powers, with the
walk's processing: periodic Blackman windows normalized by their sums and
fourfold padding on both axes (walk_common), so the peak power of a tone does
not depend on the number of chirps. A CPI is on the track if its peak is
15 dB above the median power of the search region and it approaches faster
than 1 m/s. Its mean RX power is scaled to 16 m by R^-4 at its apparent range,
as field_level.py does for the tripod placements and the walk; neither the
runs nor the walk get the IF-response correction (within about 0.2 dB from
1.1 to 5.3 MHz, NOTES).

The CPI-length check splits each CPI into 256- and 128-chirp segments and
takes the mean of the segment peaks near the full CPI's range: equal to the
full CPI's peak for a tone of constant frequency, higher where the carried
reflector's motion spreads its return over the 51 ms CPI.

The static-scene check asks whether the radar pointed the same way in the runs
as during the placements. The static returns of the 40 m placement, 12 dB
above the range profile's floor and away from the reflector, are measured in
10-CPI coherent zero-Doppler means of the empty scene, every placement, and
the first and last 10 CPIs of each run: level and azimuth (from the per-RX
phases) against the placements' median for each return.

One capture at a time; peak memory about 0.8 GB. Writes
generated/field/runs/summary.json, per_cpi.csv and runs.png.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from scipy.fft import fft, fftshift, rfft
from scipy.signal import find_peaks

from carkit_common import (
    SPEED_OF_LIGHT,
    ComplexArray,
    FloatArray,
    db,
    write_summary,
)
from field_common import (
    GENERATED_DIR,
    NOMINAL_RANGES_M,
    WAVEFORMS,
    azimuth_deg,
    data_argument,
    empty_case,
    find_peak,
    kept_frames,
    load,
    placement_case,
    read_summary,
    static_samples,
    wavelength_m,
)
from field_level import SCALE_RANGE_M, WALK_BANDS_M, WALK_TRACK
from walk_common import PADDING, IntArray, window
from window_common import Capture, range_spectrum

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TX1_RUNS = ("short-run-1", "short-run-2", "medium-run-1", "medium-run-2")
EIGHT_TX_RUN = "run-8tx"
SEARCH_RANGE_M = (3.0, 60.0)
SEARCH_SPEED_MPS = (0.4, 4.0)
TRACK_MIN_SNR_DB = 15.0
TRACK_MAX_VELOCITY_MPS = -1.0
SEGMENTS = (256, 128)
SEGMENT_HALF_WIDTH_M = 1.5
# Tripod placements compared with the runs (apparent ranges, NOTES).
TRIPOD_RANGES_M = (15.0, 38.0)
# Static-scene check: returns of the 40 m placement this far above the
# range profile's floor at 0.35-0.45 of the sample rate, away from the
# reflector; 10-CPI coherent means in every capture; azimuths compared where
# both estimates are this coherent.
SCENE_MIN_RISE_DB = 12.0
SCENE_CPIS = 10
SCENE_PADDING = 8
SCENE_MIN_COHERENCE = 0.9
SCENE_EXCLUDE_M = 2.5
SCENE_MAX_RANGE_M = 120.0
RX_PITCH_M = 8.625e-3


def range_doppler(spectrum: ComplexArray) -> ComplexArray:
    """Windowed, sum-normalized, padded and centred slow-time FFT (axis 0)."""
    weights = window(spectrum.shape[0]).astype(np.float32)
    transformed = fft(
        spectrum * weights[:, None, None], n=PADDING * weights.size, axis=0
    )
    return np.asarray(fftshift(transformed, axes=0) / weights.sum())


def velocity_axis(capture: Capture, n_chirps: int) -> FloatArray:
    doppler_hz = fftshift(np.fft.fftfreq(PADDING * n_chirps, capture.chirp_period_s))
    return np.asarray(SPEED_OF_LIGHT * doppler_hz / (2 * capture.center_frequency_hz))


def track(capture: Capture) -> list[dict[str, Any]]:
    """Per-CPI reflector cell, level and segment peaks."""
    range_m = capture.range_axis(PADDING)
    search = np.flatnonzero(
        (range_m >= SEARCH_RANGE_M[0]) & (range_m <= SEARCH_RANGE_M[1])
    )
    weights = window(capture.n_samples).astype(np.float32)
    kept, dropped = kept_frames(capture)
    rows = []
    for frame in kept:
        raw = capture.load(frame).astype(np.float32)
        raw -= raw.mean(axis=(0, 1), keepdims=True)
        spectrum = (
            rfft(raw * weights[None, :, None], n=PADDING * raw.shape[1], axis=1)
            / weights.sum()
        )[:, search, :].astype(np.complex64)
        del raw

        def peak(chirps: slice, cells: IntArray) -> tuple[float, int, int, float]:
            block = spectrum[chirps]
            power = np.mean(np.abs(range_doppler(block[:, cells, :])) ** 2, axis=2)
            speed = np.abs(velocity_axis(capture, block.shape[0]))
            moving = (speed >= SEARCH_SPEED_MPS[0]) & (speed <= SEARCH_SPEED_MPS[1])
            background = float(np.median(power[moving][::PADDING, ::PADDING]))
            power[~moving] = 0.0
            v, r = np.unravel_index(int(np.argmax(power)), power.shape)
            return float(power[v, r]), int(v), int(r), background / np.log(2)

        full, v, r, background = peak(slice(None), np.arange(search.size))
        apparent = float(range_m[search[r]])
        near = np.flatnonzero(
            np.abs(range_m[search] - apparent) <= SEGMENT_HALF_WIDTH_M
        )
        row: dict[str, Any] = {
            "case": capture.case,
            "frame": frame,
            "time_s": capture.cpi_times_s[frame],
            "range_m": apparent,
            "velocity_mps": float(velocity_axis(capture, capture.n_chirps)[v]),
            "snr_db": float(db(full / background)),
            "power_db_counts2": float(db(full)),
            "scaled_db_counts2": float(
                db(full) + 40 * np.log10(apparent / SCALE_RANGE_M)
            ),
        }
        for length in SEGMENTS:
            segments = [
                peak(slice(start, start + length), near)[0]
                for start in range(0, capture.n_chirps, length)
            ]
            row[f"segment_{length}_minus_full_db"] = float(db(np.mean(segments) / full))
        row["on_track"] = bool(
            row["snr_db"] >= TRACK_MIN_SNR_DB
            and row["velocity_mps"] <= TRACK_MAX_VELOCITY_MPS
        )
        rows.append(row)
    if dropped:
        print(f"{capture.case}: dropped interfered CPIs {dropped}")
    return rows


def band_stats(range_m: FloatArray, level_db: FloatArray) -> dict[str, Any]:
    bands = {}
    for low, high in WALK_BANDS_M:
        mask = (range_m >= low) & (range_m < high)
        bands[f"{low:g}-{high:g}"] = {
            "cpis": int(mask.sum()),
            "mean_db": float(level_db[mask].mean()) if mask.any() else None,
            "std_db": float(level_db[mask].std()) if mask.any() else None,
        }
    return bands


def walk_legs() -> dict[str, dict[str, FloatArray]]:
    """The walk's per-CPI range, velocity and level at 16 m, by leg."""
    if not WALK_TRACK.is_file():
        raise SystemExit(f"{WALK_TRACK} not found; run walk_extract.py first")
    rows = list(csv.DictReader(WALK_TRACK.open()))
    legs = {}
    for leg in ("inbound", "outbound"):
        mine = [row for row in rows if row["leg"] == leg]
        range_m = np.array([float(row["range_m"]) for row in mine])
        power = np.array(
            [
                [float(row[f"rx{c}_signal_power_db"]) for c in range(1, 9)]
                for row in mine
            ]
        )
        legs[leg] = {
            "range_m": range_m,
            "velocity_mps": np.array([float(row["velocity_mps"]) for row in mine]),
            "scaled_db": db(np.mean(10 ** (power / 10), axis=1))
            + 40 * np.log10(range_m / SCALE_RANGE_M),
        }
    return legs


def case_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    on = [r for r in rows if r["on_track"]]
    range_m = np.array([r["range_m"] for r in on])
    level = np.array([r["scaled_db_counts2"] for r in on])
    times = np.array([r["time_s"] for r in on])
    in_bands = (range_m >= WALK_BANDS_M[0][0]) & (range_m < WALK_BANDS_M[-1][1])
    return {
        "cpis_analysed": len(rows),
        "cpis_on_track": len(on),
        "track_range_m": [float(range_m.min()), float(range_m.max())],
        "median_velocity_mps": float(np.median([r["velocity_mps"] for r in on])),
        "range_rate_from_track_mps": float(np.polyfit(times, range_m, 1)[0]),
        "bands": band_stats(range_m, level),
        "segment_minus_full_db_15_52_m": {
            str(length): float(
                np.mean(
                    [
                        r[f"segment_{length}_minus_full_db"]
                        for r, inside in zip(on, in_bands)
                        if inside
                    ]
                )
            )
            for length in SEGMENTS
        },
    }


def plot(
    output: Path,
    rows: list[dict[str, Any]],
    walk: dict[str, dict[str, FloatArray]],
    tripod: list[dict[str, Any]],
) -> None:
    figure, axis = plt.subplots(figsize=(9, 5.5), layout="constrained")
    runs = [r for r in rows if r["on_track"] and r["case"] in TX1_RUNS]
    axis.plot(
        [r["range_m"] for r in runs],
        [r["scaled_db_counts2"] for r in runs],
        ".",
        color="C0",
        alpha=0.5,
        label="Field, carried towards the radar (four TX1 runs)",
    )
    for leg, colour in (("inbound", "C2"), ("outbound", "C3")):
        axis.plot(
            walk[leg]["range_m"],
            walk[leg]["scaled_db"],
            "o",
            ms=4,
            color=colour,
            label=f"Walk, carried {'towards' if leg == 'inbound' else 'away from'} the radar",
        )
    axis.plot(
        [p["range_m"] for p in tripod],
        [p["corrected_db_counts2"] for p in tripod],
        "ks",
        ms=7,
        label="Field, on a tripod (both waveforms)",
    )
    axis.set(
        xlim=(10, 55),
        ylim=(5, 45),
        xlabel="Apparent range [m]",
        ylabel=f"Reflector power scaled to {SCALE_RANGE_M:g} m by R⁻⁴ [dB ADC-count²]",
        title="The walking reflector carried and on a tripod",
    )
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8, loc="lower left")
    figure.savefig(output / "runs.png", dpi=120)
    plt.close(figure)


def scene_check(data: Path | None, reflector_m: dict[str, float]) -> dict[str, Any]:
    """Whether the radar's static scene is the same in every capture of a
    waveform: level and azimuth of the 40 m placement's static returns in
    10-CPI coherent means (runs: their first and last 10 kept CPIs), against
    the placements' median. Azimuth shifts are taken in sine space, wrapped
    to the array's unambiguous interval, and given in degrees."""
    result: dict[str, Any] = {}
    for waveform in WAVEFORMS:
        base = load(placement_case(waveform, 40), data)
        mean = np.mean(
            [static_samples(base.load(k)) for k in kept_frames(base)[0]], axis=0
        )
        profile = db(
            np.mean(np.abs(range_spectrum(mean[None], SCENE_PADDING)[0]) ** 2, axis=-1)
        )
        beat = np.fft.rfftfreq(SCENE_PADDING * mean.shape[0], 1 / base.sample_rate_hz)
        range_m = beat / base.beat_frequency_hz(1.0)
        far = (beat > 0.35 * base.sample_rate_hz) & (beat < 0.45 * base.sample_rate_hz)
        peaks, _ = find_peaks(
            profile, prominence=6, height=np.median(profile[far]) + SCENE_MIN_RISE_DB
        )
        peaks = peaks[
            (range_m[peaks] > 2)
            & (range_m[peaks] < SCENE_MAX_RANGE_M)
            & (np.abs(range_m[peaks] - reflector_m[base.case]) > SCENE_EXCLUDE_M)
        ]
        beats = [find_peak(mean, base.sample_rate_hz, beat[k])[0] for k in peaks]
        metres_per_hz = 1 / float(base.beat_frequency_hz(1.0))
        returns_m = [float(b * metres_per_hz) for b in beats]
        wavelength = wavelength_m(base)
        half = wavelength / (2 * RX_PITCH_M)

        def measure(
            capture: Capture, frames: list[int]
        ) -> list[tuple[float, float, float]]:
            static = np.mean([static_samples(capture.load(k)) for k in frames], axis=0)
            values = []
            for b in beats:
                _, amplitudes = find_peak(static, capture.sample_rate_hz, b)
                angle, coherence = azimuth_deg(amplitudes, wavelength)
                values.append(
                    (
                        float(db(np.mean(np.abs(amplitudes) ** 2))),
                        float(np.sin(np.radians(angle))),
                        coherence,
                    )
                )
            return values

        captures: dict[str, tuple[str, list[tuple[float, float, float]]]] = {}
        for case in [empty_case(waveform)] + [
            placement_case(waveform, d) for d in NOMINAL_RANGES_M
        ]:
            capture = load(case, data)
            captures[case] = (
                capture.timestamps[0],
                measure(capture, kept_frames(capture)[0][:SCENE_CPIS]),
            )
        for run in (f"{waveform}-run-1", f"{waveform}-run-2"):
            capture = load(run, data)
            kept = kept_frames(capture)[0]
            captures[f"{run} first"] = (
                capture.timestamps[kept[0]],
                measure(capture, kept[:SCENE_CPIS]),
            )
            captures[f"{run} last"] = (
                capture.timestamps[kept[-1]],
                measure(capture, kept[-SCENE_CPIS:]),
            )

        def usable(case: str, r: float) -> bool:
            return (
                case not in reflector_m or abs(reflector_m[case] - r) > SCENE_EXCLUDE_M
            )

        placements = [placement_case(waveform, d) for d in NOMINAL_RANGES_M]
        reference = []
        for j, r in enumerate(returns_m):
            mine = [captures[c][1][j] for c in placements if usable(c, r)]
            coherent = [v[1] for v in mine if v[2] >= SCENE_MIN_COHERENCE]
            reference.append(
                (
                    float(np.median([v[0] for v in mine])),
                    float(np.median(coherent)) if coherent else float("nan"),
                )
            )
        rows = {}
        for case, (time, values) in captures.items():
            levels, shifts = [], []
            for j, (level, sine, coherence) in enumerate(values):
                if not usable(case.split(" ")[0], returns_m[j]):
                    continue
                levels.append(level - reference[j][0])
                if coherence >= SCENE_MIN_COHERENCE and np.isfinite(reference[j][1]):
                    shift = (sine - reference[j][1] + half) % (2 * half) - half
                    shifts.append(float(np.degrees(np.arcsin(shift))))
            rows[case] = {
                "time_utc": time,
                "returns": len(levels),
                "median_level_change_db": float(np.median(levels)),
                "level_change_range_db": [float(min(levels)), float(max(levels))],
                "coherent_returns": len(shifts),
                "median_azimuth_shift_deg": (
                    float(np.median(shifts)) if shifts else None
                ),
                "azimuth_shift_range_deg": (
                    [float(min(shifts)), float(max(shifts))] if shifts else None
                ),
            }
            shift_text = f"{np.median(shifts):+5.1f} deg" if shifts else "  n/a"
            print(
                f"scene {case:18s} {time[11:19]}  level "
                f"{np.median(levels):+5.1f} dB  azimuth {shift_text}"
                f" ({len(shifts)} coherent)"
            )
        result[waveform] = {
            "returns_m": returns_m,
            "against": "median over the placements",
            "captures": rows,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_argument(parser)
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "runs")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    level_placements = read_summary("level")["placements"]
    scene = scene_check(args.data, {p["case"]: p["range_m"] for p in level_placements})
    rows: list[dict[str, Any]] = []
    cases: dict[str, Any] = {}
    for case in (*TX1_RUNS, EIGHT_TX_RUN):
        capture = load(case, args.data)
        mine = track(capture)
        rows.extend(mine)
        cases[case] = case_summary(mine)
        print(f"{case}: {cases[case]['cpis_on_track']} CPIs on the track")

    on = [r for r in rows if r["on_track"]]
    tx1 = [r for r in on if r["case"] in TX1_RUNS]
    eight = [r for r in on if r["case"] == EIGHT_TX_RUN]
    tx1_bands = band_stats(
        np.array([r["range_m"] for r in tx1]),
        np.array([r["scaled_db_counts2"] for r in tx1]),
    )
    eight_bands = band_stats(
        np.array([r["range_m"] for r in eight]),
        np.array([r["scaled_db_counts2"] for r in eight]),
    )
    walk = walk_legs()
    walk_bands = {
        leg: band_stats(values["range_m"], values["scaled_db"])
        for leg, values in walk.items()
    }
    walk_velocity = {
        leg: float(np.median(values["velocity_mps"])) for leg, values in walk.items()
    }
    tripod = [
        p
        for p in level_placements
        if p["corrected_db_counts2"] is not None
        and TRIPOD_RANGES_M[0] <= p["range_m"] <= TRIPOD_RANGES_M[1]
    ]
    tripod_db = float(np.mean([p["corrected_db_counts2"] for p in tripod]))

    with (args.output / "per_cpi.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot(args.output, rows, walk, tripod)
    write_summary(
        args.output,
        {
            "scale_range_m": SCALE_RANGE_M,
            "track": {
                "search_range_m": SEARCH_RANGE_M,
                "search_speed_mps": SEARCH_SPEED_MPS,
                "min_snr_db": TRACK_MIN_SNR_DB,
                "max_velocity_mps": TRACK_MAX_VELOCITY_MPS,
            },
            "cases": cases,
            "tx1_runs_bands": tx1_bands,
            "eight_tx_run_bands": eight_bands,
            "walk_bands": walk_bands,
            "walk_median_velocity_mps": walk_velocity,
            "tripod_16_34_m": {
                "placements": [p["case"] for p in tripod],
                "mean_corrected_db_counts2": tripod_db,
            },
            "tx1_runs_minus_walk_inbound_db": {
                band: tx1_bands[band]["mean_db"]
                - walk_bands["inbound"][band]["mean_db"]
                for band in tx1_bands
            },
            "tx1_runs_minus_walk_outbound_db": {
                band: tx1_bands[band]["mean_db"]
                - walk_bands["outbound"][band]["mean_db"]
                for band in tx1_bands
            },
            "tx1_runs_minus_tripod_db": {
                band: tx1_bands[band]["mean_db"] - tripod_db for band in tx1_bands
            },
            "static_scene": scene,
            "eight_tx_minus_tx1_runs_db": {
                band: eight_bands[band]["mean_db"] - tx1_bands[band]["mean_db"]
                for band in tx1_bands
            },
        },
    )


if __name__ == "__main__":
    main()
