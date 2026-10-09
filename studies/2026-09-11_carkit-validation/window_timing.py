"""The per-chirp frequency error against the chirp timing.

For a recording whose cases differ only in the ramp segments (the 2026-10-06
window captures: PRI, pre-payload, flyback and wait), this step reads the
results of window_scene.py and window_phase.py on that recording and adds:

- The cross-return slow-time spectrum of delta_f at full resolution, over the
  clean returns and pairs of window_phase.py with the same pair weights, so
  that its sum over the band is window_phase.py's pair mean. Its tilt is the
  mean density from PRF/4 to PRF/2 over that from 500 Hz to PRF/4: 0 dB for a
  white sequence, as the CW phase noise gives, positive where successive
  chirps' errors partly cancel.
- A fit of delta_f against the timing (carkit_common.settling_fit): a floor
  plus an excess that decays with the time in fast-settling mode (flyback and
  wait) and with the pre-payload. Its uncertainty per case is the bootstrap
  interval of window_phase.py combined with the spread between cases of equal
  timing, which shows how much a repeated capture differs.
- The fit extrapolated to the timing of Infineon's firmware (60 ns flyback and
  60 ns wait) and compared with the delta_f measured with it: the window
  recording of 2026-08-27 (window_phase.py's default outputs) and the
  reflector in the outdoor captures (outdoor_phase.py).
- The flyback and wait that bring delta_f to within 10 % of the floor at
  pre-payloads inside the tested range, and the coherence loss each case's
  delta_f gives at 1 km (radarperf SystemLosses).
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from carkit_common import (
    STUDY_DIR,
    FloatArray,
    SettlingFit,
    db,
    delay_s,
    display_groups,
    settling_fit,
    tone_model_errors,
    weighted_cross_spectrum,
    write_summary,
)
from radarperf.losses import SystemLosses
from window_common import (
    GENERATED_DIR,
    Capture,
    chirp_gains,
    data_arguments,
    doppler_window,
    load_capture,
)
from window_phase import LOW_DOPPLER_HZ, MIN_PAIR_SEPARATION_M

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUTDOOR_DIR = STUDY_DIR / "generated" / "outdoor"
# Every Infineon-era configuration found uses 60 ns flyback and 60 ns wait
# (NOTES, Firmware); the outdoor captures' summaries record only the
# pre-payload.
INFINEON_FAST_SETTLING_S = 0.12e-6
# Cases whose pre-payload and fast-settling time agree to this are repeats.
SAME_TIMING_S = 0.01e-6
# delta_f within this factor of the fitted floor counts as settled.
SETTLED_RATIO = 1.1
DESIGN_PRE_PAYLOADS_S = (2e-6, 4e-6, 6e-6)
# Timings proposed as follow-ups, (label, pre-payload, flyback + wait) [s]:
# Infineon's 2026-08-27 mode 0 with its flyback or wait lengthened, and a
# 25.5 us chirp period with the gap moved into the pre-payload (20 ns flyback,
# 3.2 us wait, the host tool's minimum being 3 us).
PREDICTIONS = (
    ("Infineon mode 0, 1 us flyback", 4.2e-6, 1.0e-6 + 0.06e-6),
    ("Infineon mode 0, 10 us wait", 4.2e-6, 0.06e-6 + 10e-6),
    ("Infineon mode 0, 20 us wait", 4.2e-6, 0.06e-6 + 20e-6),
    ("Infineon mode 0, 40 us wait", 4.2e-6, 0.06e-6 + 40e-6),
    ("PRI 25.5 us, 12 us pre-payload", 12e-6, 0.02e-6 + 3.2e-6),
)
COHERENCE_RANGE_M = 1000.0
DRAWS = 4000
# Two-sided p5-p95 of a normal distribution, in standard deviations.
P5_P95_WIDTH = 2 * 1.6449
# Pre-payload colours, short to long: one blue ramp, light to dark.
PRE_PAYLOAD_COLORS = ("#86b6ef", "#5598e7", "#256abf", "#104281")
REFERENCE_COLOR = "#8a8984"


def fast_settling_s(capture: Capture) -> float:
    """Time in the DPLL's fast-settling mode between payloads: flyback and wait."""
    return capture.flyback_s + capture.wait_s


def cross_return_spectrum(
    capture: Capture, ranges: FloatArray, frames: list[int]
) -> tuple[FloatArray, FloatArray]:
    """Pair-weighted cross-return delta_f PSD [Hz²/Hz, two-sided] per bin.

    The pairs are the returns at least MIN_PAIR_SEPARATION_M apart, weighted
    by the inverse product of their own powers in the band, as in
    window_phase.weighted_df. Returns the slow-time frequencies and the PSD.
    """
    tau = delay_s(ranges)
    beat = capture.beat_frequency_hz(ranges)
    window = doppler_window(capture.n_chirps)
    lines = capture.static_lines(tau)
    spectrum = np.zeros((capture.n_chirps, ranges.size, ranges.size))
    for frame in frames:
        gains = chirp_gains(capture.load(frame), beat, capture.sample_rate_hz)
        errors, weights, _ = tone_model_errors(gains, lines)
        spectrum += weighted_cross_spectrum(
            errors.imag / (2 * np.pi * tau), weights, window
        ) / len(frames)
    doppler = capture.doppler_axis()
    band = np.abs(doppler) >= LOW_DOPPLER_HZ
    own = np.diagonal(spectrum[band].sum(axis=0))
    pairs = [
        (i, j)
        for i, j in itertools.combinations(range(ranges.size), 2)
        if abs(ranges[i] - ranges[j]) >= MIN_PAIR_SEPARATION_M
    ]
    weights = np.array([1 / (own[i] * own[j]) for i, j in pairs])
    pooled = sum(w * spectrum[:, i, j] for w, (i, j) in zip(weights, pairs))
    bin_hz = 1 / (capture.n_chirps * capture.chirp_period_s)
    return doppler, np.asarray(pooled / weights.sum() / bin_hz)


def spectrum_tilt_db(doppler: FloatArray, psd: FloatArray, prf: float) -> float:
    """Mean density from PRF/4 to PRF/2 over that from LOW_DOPPLER_HZ to PRF/4."""
    frequency = np.abs(doppler)
    lower = (frequency >= LOW_DOPPLER_HZ) & (frequency < prf / 4)
    upper = frequency >= prf / 4
    return float(db(psd[upper].mean() / psd[lower].mean()))


def capture_spread(timings: FloatArray, df_hz: FloatArray) -> tuple[float, list[Any]]:
    """Pooled relative standard deviation of delta_f within groups of equal timing.

    ``timings`` is [case, (pre-payload, fast-settling)]. Returns the spread and
    the groups' case indices.
    """
    groups: list[list[int]] = []
    for k, timing in enumerate(timings):
        for group in groups:
            if np.all(np.abs(timings[group[0]] - timing) < SAME_TIMING_S):
                group.append(k)
                break
        else:
            groups.append([k])
    repeated = [group for group in groups if len(group) > 1]
    squares = sum(
        np.sum((df_hz[g] / df_hz[g].mean() - 1) ** 2) for g in map(np.array, repeated)
    )
    dof = sum(len(group) - 1 for group in repeated)
    return (float(np.sqrt(squares / dof)) if dof else 0.0), repeated


def interval(values: FloatArray) -> list[float]:
    return [float(v) for v in np.percentile(values, [5, 95])]


def settled_fast_settling_s(
    fit: SettlingFit, pre_payload_s: float, parameters: FloatArray
) -> FloatArray:
    """Fast-settling time at which delta_f falls to SETTLED_RATIO x the floor."""
    floor, log_excess, log_tau_fast, log_tau_pre = np.atleast_2d(parameters).T
    allowed = (SETTLED_RATIO**2 - 1) * floor**2
    value = np.exp(log_tau_fast) * (
        log_excess - np.log(allowed) - pre_payload_s / np.exp(log_tau_pre)
    )
    return np.asarray(np.maximum(value, 0.0))


def reference_points(
    rng: np.random.Generator, fit: SettlingFit
) -> list[dict[str, Any]]:
    """delta_f measured with Infineon's timing against the extrapolated fit."""
    scene = json.loads((GENERATED_DIR / "scene" / "summary.json").read_text())["cases"]
    phase = json.loads((GENERATED_DIR / "phase" / "summary.json").read_text())["cases"]
    outdoor_scene = json.loads((OUTDOOR_DIR / "scene" / "summary.json").read_text())
    outdoor_phase = json.loads((OUTDOOR_DIR / "phase" / "summary.json").read_text())
    points = []
    for case in ("infineon-mode1", "infineon-mode0"):
        timing = scene[case]
        result = phase[case]
        # Mode 0 has no clean pair; its pair mean over all returns stands in,
        # as in window_phase.py's notes.
        if result["df_rms_hz"] is not None:
            measured = [result["df_rms_hz"], *result["df_rms_p5_p95_hz"]]
        else:
            every = result["all_returns"]
            measured = [
                every["pair_mean_df_rms_hz"],
                *every["pair_mean_df_rms_p5_p95_hz"],
            ]
        points.append(
            {
                "name": f"window 2026-08-27, mode {case.removeprefix('infineon-mode')}",
                "pre_payload_us": timing["pre_payload_us"],
                "fast_settling_us": timing["flyback_us"] + timing["wait_us"],
                "measured_df_rms_hz": measured[0],
                "measured_p5_p95_hz": measured[1:],
            }
        )
    pre_payloads = {case["pre_payload_s"] for case in outdoor_scene["cases"].values()}
    if len(pre_payloads) != 1:
        raise ValueError("outdoor captures with different pre-payloads")
    reflector = [
        case["returns"][0]["df_rms_hz"] for case in outdoor_phase["cases"].values()
    ]
    points.append(
        {
            "name": "outdoor reflector, 4 captures",
            "pre_payload_us": 1e6 * pre_payloads.pop(),
            "fast_settling_us": 1e6 * INFINEON_FAST_SETTLING_S,
            "measured_df_rms_hz": float(np.median(reflector)),
            "measured_range_hz": [float(min(reflector)), float(max(reflector))],
        }
    )
    draws = fit.draws(rng, DRAWS)
    for point in points:
        pre, fast = 1e-6 * point["pre_payload_us"], 1e-6 * point["fast_settling_us"]
        point["predicted_df_rms_hz"] = float(fit.df_hz(pre, fast))
        point["predicted_p5_p95_hz"] = interval(fit.df_hz(pre, fast, draws))
    return points


def plot(
    output: Path,
    cases: dict[str, dict[str, Any]],
    spectra: dict[str, tuple[FloatArray, FloatArray, float]],
    fit: SettlingFit,
    draws: FloatArray,
    references: list[dict[str, Any]],
    cw_typical_hz: dict[str, float],
) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(17, 5.5), layout="constrained")
    pre_levels = sorted({case["pre_payload_us"] for case in cases.values()})
    if len(pre_levels) > len(PRE_PAYLOAD_COLORS):
        raise ValueError("more pre-payloads than colours")
    color = dict(zip(pre_levels, PRE_PAYLOAD_COLORS[-len(pre_levels) :]))

    axis = axes[0]
    fast = np.geomspace(5, 100, 200)
    for pre in pre_levels:
        axis.plot(
            fast,
            fit.df_hz(pre * 1e-6, fast * 1e-6) / 1e3,
            color=color[pre],
            linewidth=1.5,
        )
    for pre in pre_levels:
        members = [case for case in cases.values() if case["pre_payload_us"] == pre]
        values = np.array([case["df_rms_hz"] for case in members]) / 1e3
        bounds = np.array([case["df_rms_p5_p95_hz"] for case in members]).T / 1e3
        axis.errorbar(
            [case["fast_settling_us"] for case in members],
            values,
            yerr=np.abs(bounds - values),
            fmt="o",
            ms=7,
            color=color[pre],
            markeredgecolor="white",
            label=f"pre-payload {pre:g} µs",
        )
    for (label, value), style in zip(cw_typical_hz.items(), ("--", ":")):
        axis.axhline(
            value / 1e3,
            color=REFERENCE_COLOR,
            linestyle=style,
            linewidth=1,
            label=f"CW datasheet, typical, {label} GHz",
        )
    axis.set(
        xscale="log",
        yscale="log",
        xlim=(5, 100),
        ylim=(2, 12),
        xlabel="Flyback + wait (fast-settling mode) [µs]",
        ylabel="δf rms [kHz]",
        title="Measured δf (p5–p95) and the fit (lines)",
    )
    axis.set_xticks([5, 10, 20, 50, 100], labels=["5", "10", "20", "50", "100"])
    axis.set_yticks([2, 3, 4, 6, 8, 10], labels=["2", "3", "4", "6", "8", "10"])
    axis.grid(alpha=0.3, which="both")
    axis.legend(fontsize=8)

    axis = axes[1]
    pre = np.linspace(3, 6, 61)
    band = fit.df_hz(pre * 1e-6, INFINEON_FAST_SETTLING_S, draws)
    low, high = np.percentile(band, [5, 95], axis=0)
    axis.fill_between(pre, low / 1e3, high / 1e3, color="#cde2fb", label="fit, p5–p95")
    axis.plot(
        pre,
        fit.df_hz(pre * 1e-6, INFINEON_FAST_SETTLING_S) / 1e3,
        color="#256abf",
        linewidth=1.5,
        label=f"fit at {1e9 * INFINEON_FAST_SETTLING_S:.0f} ns flyback + wait",
    )
    for point in references:
        value = point["measured_df_rms_hz"] / 1e3
        bounds = (
            np.array(point.get("measured_p5_p95_hz") or point["measured_range_hz"])
            / 1e3
        )
        axis.errorbar(
            point["pre_payload_us"],
            value,
            yerr=np.abs(bounds - value)[:, None],
            fmt="D" if "window" in point["name"] else "s",
            ms=7,
            color="#0b0b0b",
            markeredgecolor="white",
            capsize=3,
            label=f"Infineon's firmware: {point['name']}",
        )
    axis.set(
        yscale="log",
        ylim=(5, 80),
        xlabel="Pre-payload [µs]",
        ylabel="δf rms [kHz]",
        title="The fit extrapolated to Infineon's timing",
    )
    axis.set_yticks([5, 10, 20, 40, 80], labels=["5", "10", "20", "40", "80"])
    axis.grid(alpha=0.3, which="both")
    axis.legend(fontsize=8)

    axis = axes[2]
    for case, (doppler, psd, prf) in spectra.items():
        frequency, density = display_groups(doppler, psd)
        info = cases[case]
        reference = info["chirp_period_us"] == max(
            entry["chirp_period_us"] for entry in cases.values()
        )
        axis.plot(
            frequency / prf,
            density * prf / 1e6,
            color=REFERENCE_COLOR if reference else color[info["pre_payload_us"]],
            linewidth=2 if not reference else 1.5,
            linestyle="--" if reference else "-",
            label=(
                f"PRI {info['chirp_period_us']:g} µs, pre-payload "
                f"{info['pre_payload_us']:g} µs, flyback + wait "
                f"{info['fast_settling_us']:.1f} µs"
            ),
        )
    axis.axhline(
        fit.floor_hz**2 / 1e6,
        color="#0b0b0b",
        linewidth=0.8,
        label=f"fitted floor, {fit.floor_hz / 1e3:.2f} kHz rms if white",
    )
    axis.set(
        yscale="log",
        xlim=(0, 0.5),
        xlabel="Slow-time frequency / PRF",
        ylabel="δf PSD × PRF [kHz²]; a white δf is flat at its variance",
        title="Cross-return slow-time spectrum of δf",
    )
    axis.grid(alpha=0.3, which="both")
    axis.legend(fontsize=8)
    figure.savefig(output / "timing.png", dpi=120)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_arguments(parser)
    parser.add_argument(
        "--scene", type=Path, required=True, help="window_scene.py output"
    )
    parser.add_argument(
        "--phase", type=Path, required=True, help="window_phase.py output"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261006)
    scene = json.loads((args.scene / "summary.json").read_text())["cases"]
    phase = json.loads((args.phase / "summary.json").read_text())["cases"]

    captures: dict[str, Capture] = {}
    cases: dict[str, dict[str, Any]] = {}
    spectra: dict[str, tuple[FloatArray, FloatArray, float]] = {}
    for case in sorted(phase, key=lambda name: scene[name]["first_timestamp"]):
        capture = load_capture(case, args.data)
        result = phase[case]
        dropped = scene[case].get("interference_cpis", [])
        frames = [k for k in range(capture.n_frames) if k not in dropped]
        ranges = np.array(
            [entry["range_m"] for entry in result["returns"] if entry["clean"]]
        )
        doppler, psd = cross_return_spectrum(capture, ranges, frames)
        prf = 1 / capture.chirp_period_s
        bin_hz = prf / capture.n_chirps
        band = np.abs(doppler) >= LOW_DOPPLER_HZ
        captures[case] = capture
        spectra[case] = (doppler, psd, prf)
        cases[case] = {
            "first_timestamp": scene[case]["first_timestamp"],
            "cpis": len(frames),
            "chirp_period_us": 1e6 * capture.chirp_period_s,
            "pre_payload_us": 1e6 * capture.pre_payload_s,
            "flyback_us": 1e6 * capture.flyback_s,
            "wait_us": 1e6 * capture.wait_s,
            "fast_settling_us": 1e6 * fast_settling_s(capture),
            "clean_returns": int(ranges.size),
            "pairs": result["pairs"],
            "df_rms_hz": result["df_rms_hz"],
            "df_rms_p5_p95_hz": result["df_rms_p5_p95_hz"],
            "gamma": result["gamma"],
            "by_farther_return": result["by_farther_return"],
            "pair_mean_df_rms_hz": result["pair_mean_df_rms_hz"],
            "spectrum_df_rms_hz": float(np.sqrt(psd[band].sum() * bin_hz)),
            "spectrum_tilt_db": spectrum_tilt_db(doppler, psd, prf),
            "cw_prediction_rms_hz": result["cw_prediction_rms_hz"],
            "coherence_loss_1km_db": float(
                SystemLosses(
                    chirp_frequency_error_rms_hz=result["df_rms_hz"]
                ).coherence_loss_db(COHERENCE_RANGE_M)
            ),
            "drift_common_rms_hz": scene[case]["drift"]["common_rms_hz"],
        }

    names = list(cases)
    df = np.array([cases[name]["df_rms_hz"] for name in names])
    bootstrap_sigma = np.array(
        [np.diff(cases[name]["df_rms_p5_p95_hz"])[0] / P5_P95_WIDTH for name in names]
    )
    timings = np.array(
        [
            [captures[name].pre_payload_s, fast_settling_s(captures[name])]
            for name in names
        ]
    )
    spread, groups = capture_spread(timings, df)
    sigma = np.sqrt(bootstrap_sigma**2 + (spread * df) ** 2)
    fit = settling_fit(timings[:, 0], timings[:, 1], df, sigma)
    draws = fit.draws(rng, DRAWS)
    for name, value in zip(names, fit.df_hz(timings[:, 0], timings[:, 1])):
        cases[name]["fit_df_rms_hz"] = float(value)
    references = reference_points(rng, fit)
    predictions = [
        {
            "timing": label,
            "pre_payload_us": 1e6 * pre,
            "fast_settling_us": 1e6 * fast,
            "df_rms_hz": float(fit.df_hz(pre, fast)),
            "df_rms_p5_p95_hz": interval(fit.df_hz(pre, fast, draws)),
        }
        for label, pre, fast in PREDICTIONS
    ]
    # The sampled ramp: payload and post-payload, the same in every case.
    first = captures[names[0]]
    ramp_s = first.chirp_period_s - first.pre_payload_s - fast_settling_s(first)
    design = []
    for pre in DESIGN_PRE_PAYLOADS_S:
        needed = settled_fast_settling_s(fit, pre, draws)
        best = float(settled_fast_settling_s(fit, pre, fit.parameters)[0])
        design.append(
            {
                "pre_payload_us": 1e6 * pre,
                "fast_settling_us": 1e6 * best,
                "fast_settling_p5_p95_us": [1e6 * v for v in interval(needed)],
                "pri_us": 1e6 * (pre + ramp_s + best),
            }
        )

    shortest = min(cases[name]["chirp_period_us"] for name in names)
    longest = max(cases[name]["chirp_period_us"] for name in names)
    shown = [name for name in names if cases[name]["chirp_period_us"] == longest][:1]
    for pre in sorted({cases[name]["pre_payload_us"] for name in names}):
        candidates = [
            name
            for name in names
            if cases[name]["chirp_period_us"] == shortest
            and cases[name]["pre_payload_us"] == pre
        ]
        if candidates:
            shown.append(max(candidates, key=lambda name: cases[name]["flyback_us"]))
    # CW prediction at the shortest PRI; it changes by 4 % between the PRIs.
    shortest_case = min(names, key=lambda name: cases[name]["chirp_period_us"])
    cw_typical = {
        band.replace("-", "–"): cases[shortest_case]["cw_prediction_rms_hz"][
            f"{band}_typical_hz"
        ]
        for band in ("76-77", "77-81")
    }
    plot(
        args.output,
        cases,
        {name: spectra[name] for name in shown},
        fit,
        draws,
        references,
        cw_typical,
    )

    names_by_group = [[names[k] for k in group] for group in groups]
    write_summary(
        args.output,
        {
            "low_doppler_hz": LOW_DOPPLER_HZ,
            "settled_ratio": SETTLED_RATIO,
            "coherence_range_m": COHERENCE_RANGE_M,
            "capture_spread": {"relative_std": spread, "groups": names_by_group},
            "fit": {
                "floor_hz": fit.floor_hz,
                "floor_p5_p95_hz": interval(draws[:, 0]),
                "excess_at_zero_hz2": float(np.exp(fit.parameters[1])),
                "tau_fast_us": 1e6 * fit.tau_fast_s,
                "tau_fast_p5_p95_us": [1e6 * v for v in interval(np.exp(draws[:, 2]))],
                "tau_pre_us": 1e6 * fit.tau_pre_s,
                "tau_pre_p5_p95_us": [1e6 * v for v in interval(np.exp(draws[:, 3]))],
                "reduced_chi2": fit.reduced_chi2,
            },
            "infineon_timing": references,
            "settled": design,
            "predictions": predictions,
            "spectrum_cases": shown,
            "cases": cases,
        },
    )


if __name__ == "__main__":
    main()
