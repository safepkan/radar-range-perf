"""Per-chirp frequency error at the static scene returns of the window captures.

Reads the noise floors and static profiles of window_scene.py and the raw data.
The returns are the static profile's local maxima at least 8 dB above the
per-chirp noise, 10 m out and four range cells apart. For every CPI, each
return's per-chirp complex amplitude (the range spectrum at its exact beat
frequency) is compared with a smooth model (carkit_common.tone_model_errors):
one line at zero Doppler for our firmware, where a static return is one tone;
eight lines for the Infineon firmware's DDMA, at the transmitters' slots plus
the skew that the carrier step between chirps gives a static return,
step x delay, refined per return on the data. The model's error gives a
per-chirp phase and amplitude per return.

The slow-time band is |f_D| >= 500 Hz: the whole per-chirp variance except
slow motion. Under DDMA, bins within four of a multiple of PRF/16 are left out,
where the model weighting and spurious slot lines put deterministic content,
and the in-band variance is scaled up by the fraction left out.

The additive noise in a return's amplitude and phase follows from its
RX-summed per-chirp SNR. Moving clutter in a return's range cell, such as
traffic or vegetation, fluctuates amplitude and phase alike, whereas an LO
error is pure phase. A return is clean if its amplitude fluctuation is within a
factor of two of the additive noise, or its excess is at least ten times
smaller than the phase's. Between two clean returns at least 10 m apart, the
cross-power of their phases in delta_f units, phi / (2 pi tau), keeps only
what they share, since noise and clutter in different range cells are
independent.

What two returns share is fitted, weighted by the inverse product of their
own powers, as

    C_ij = delta_f² (sqrt(tau_i tau_j) / tau_0)^(2 gamma) + b / (tau_i tau_j):

one frequency error at every delay, as an LO error gives (gamma = 0), plus a
phase common to all returns, of rms 2 pi sqrt(b), as motion of the radar
gives. The case's delta_f is the fit at gamma = 0; gamma free tests the delay
law. p5-p95 come from resampling CPIs.

CPIs that window_scene.py flags as interfered by other radars are dropped:
an interference burst reaches many range cells and all RX channels at once, so
it is not independent between returns.

The CW datasheet prediction uses the toolbox's CTRX8188F tables, typical and
maximum, from both RF bands, since our firmware's sweep is centred at 77.0 GHz,
the boundary between them.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, Literal

import matplotlib
import numpy as np
import numpy.typing as npt
from scipy.optimize import minimize_scalar, nnls

from carkit_common import (
    SPEED_OF_LIGHT,
    ComplexArray,
    FloatArray,
    away_from_lines,
    db,
    delay_s,
    per_chirp_frequency_psd,
    tone_model_errors,
    weighted_cross_power,
    write_summary,
)
from radarperf.phase_noise import SingleReturnPhaseNoise, ctrx8188f_phase_noise
from window_common import (
    ALL_CASES,
    GENERATED_DIR,
    Capture,
    case_arguments,
    chirp_gains,
    data_arguments,
    doppler_window,
    load_capture,
    per_chirp_noise,
    range_window,
    resolve_cases,
    static_peaks,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MIN_SNR_DB = 8.0
MIN_SEPARATION_CELLS = 4
MIN_PAIR_SEPARATION_M = 10.0
LOW_DOPPLER_HZ = 500.0
DDMA_GUARD_BINS = 4
# A return is clean if its amplitude fluctuation is within a factor of two of
# the additive noise, or its excess over the noise is at least ten times
# smaller than the phase's: clutter moves amplitude and phase alike, whereas an
# LO error is pure phase (a large one, to second order, not quite).
CLEAN_AMPLITUDE_RATIO = 2.0
PHASE_DOMINANCE = 0.1
# Skew search around step x apparent delay, cycles per chirp.
SKEW_SEARCH = 0.01
SKEW_STEPS = 401
SKEW_ZERO_PADDING = 16
REFERENCE_DELAY_S = 0.5e-6
GAMMA_BOUNDS = (-0.9, 1.0)
# For converting the common phase to a displacement.
WAVELENGTH_M = SPEED_OF_LIGHT / 77e9
BOOTSTRAP = 400
FAMILIES = ("short", "medium", "long", "infineon")
# Bands of the farther return of a pair, for the delay-law table.
RANGE_BANDS_M = ((10.0, 60.0), (60.0, 130.0), (130.0, 200.0), (200.0, 290.0))
RF_BANDS: tuple[Literal["76-77", "77-81"], ...] = ("76-77", "77-81")
LEVELS: tuple[Literal["typical", "maximum"], ...] = ("typical", "maximum")


def refine_lines(capture: Capture, gains: ComplexArray, tau: FloatArray) -> FloatArray:
    """Static lines [return, line]; under DDMA, the skew refined on the data.

    The apparent delay is off by up to about 1 %, which at 175 m is 0.004 cycles
    per chirp, several cycles over a CPI; the skew that maximizes the power at
    the eight slots is used instead.
    """
    if capture.ddma_length == 1:
        return capture.static_lines(tau)
    n = gains.shape[0]
    size = SKEW_ZERO_PADDING * n
    window = doppler_window(n)
    slots = np.array(capture.ddma_slots) / capture.ddma_length
    skews = []
    for k in range(tau.size):
        power = np.sum(
            np.abs(np.fft.fft(gains[:, k] * window[:, None], n=size, axis=0)) ** 2,
            axis=-1,
        )
        candidates = capture.frequency_step_hz * tau[k] + np.linspace(
            -SKEW_SEARCH, SKEW_SEARCH, SKEW_STEPS
        )
        bins = np.round(((slots[None, :] + candidates[:, None]) % 1) * size)
        score = power[bins.astype(int) % size].sum(axis=1)
        skews.append(candidates[int(np.argmax(score))])
    return np.asarray((slots[None, :] + np.array(skews)[:, None]) % 1)


def analyze(
    capture: Capture, scene: dict[str, FloatArray], frames: list[int]
) -> dict[str, Any]:
    """Per-CPI cross-powers and per-return amplitude checks for one case,
    over the CPIs in ``frames``."""
    padded_range = scene["padded_range_m"]
    cell = SPEED_OF_LIGHT / (2 * capture.sampled_bandwidth_hz)
    ranges, snr = static_peaks(
        padded_range,
        scene["static_snr_db"],
        MIN_SNR_DB,
        MIN_SEPARATION_CELLS * cell,
    )
    tau = delay_s(ranges)
    beat = capture.beat_frequency_hz(ranges)
    nc = capture.n_chirps
    window = doppler_window(nc)
    doppler = capture.doppler_axis()
    outside_low = np.abs(doppler) >= LOW_DOPPLER_HZ
    band = outside_low.copy()
    if capture.ddma_length > 1:
        band &= away_from_lines(nc, capture.ddma_length, DDMA_GUARD_BINS)
    kept = band.sum() / outside_low.sum()

    lines: FloatArray | None = None
    cross = []
    amplitude = []
    power = np.zeros(ranges.size)
    weight_square = np.zeros(ranges.size)
    for frame in frames:
        gains = chirp_gains(capture.load(frame), beat, capture.sample_rate_hz)
        if lines is None:
            lines = refine_lines(capture, gains, tau)
        errors, weights, frame_power = tone_model_errors(gains, lines)
        power += frame_power / len(frames)
        weight_square += np.mean(weights**2, axis=0) / len(frames)
        cross.append(
            weighted_cross_power(errors.imag / (2 * np.pi * tau), weights, band, window)
            / kept
        )
        amplitude.append(
            np.diag(weighted_cross_power(errors.real, weights, band, window)) / kept
        )
    noise = per_chirp_noise(
        capture, np.interp(ranges, scene["range_m"], scene["noise_floor"])
    )
    additive = noise / (2 * power) / weight_square * outside_low.mean()
    amplitude_power = np.median(amplitude, axis=0)
    phase_power = (
        np.median(np.diagonal(np.array(cross), axis1=1, axis2=2), axis=0)
        * (2 * np.pi * tau) ** 2
    )
    amplitude_excess = amplitude_power - additive
    phase_excess = phase_power - additive
    clean = (amplitude_power < CLEAN_AMPLITUDE_RATIO * additive) | (
        amplitude_excess < PHASE_DOMINANCE * phase_excess
    )
    return {
        "ranges": ranges,
        "snr": snr,
        "tau": tau,
        "cross": np.array(cross),
        "amplitude_excess_db": db(amplitude_power / additive),
        "phase_excess_db": db(phase_power / additive),
        "clean": clean,
        "kept_fraction": kept,
        "lines": lines,
    }


def pairs(result: dict[str, Any], clean_only: bool = True) -> list[tuple[int, int]]:
    """Returns at least MIN_PAIR_SEPARATION_M apart, by default clean ones."""
    chosen = np.flatnonzero(result["clean"] | (not clean_only))
    ranges = result["ranges"]
    return [
        (int(i), int(j))
        for i, j in itertools.combinations(chosen, 2)
        if abs(ranges[i] - ranges[j]) >= MIN_PAIR_SEPARATION_M
    ]


def pair_table(
    results: list[dict[str, Any]],
    frames: list[npt.NDArray[np.int64]] | None = None,
    clean_only: bool = True,
) -> FloatArray:
    """Rows (range_i, range_j, tau_i, tau_j, C_ij, C_ii, C_jj, result index)."""
    rows = []
    for index, result in enumerate(results):
        chosen = result["cross"] if frames is None else result["cross"][frames[index]]
        mean = chosen.mean(axis=0)
        for i, j in pairs(result, clean_only):
            rows.append(
                (
                    result["ranges"][i],
                    result["ranges"][j],
                    result["tau"][i],
                    result["tau"][j],
                    mean[i, j],
                    mean[i, i],
                    mean[j, j],
                    index,
                )
            )
    return np.array(rows).reshape(-1, 8)


def weighted_df(table: FloatArray) -> float:
    """Inverse-power-weighted mean cross-power over pairs, as an rms in Hz."""
    if not len(table):
        return float("nan")
    weights = 1 / (table[:, 5] * table[:, 6])
    return float(np.sqrt(max(np.sum(weights * table[:, 4]) / np.sum(weights), 0.0)))


def lo_and_motion(
    table: FloatArray, n_results: int, gamma: float
) -> tuple[float, FloatArray, float]:
    """Weighted non-negative fit of C_ij = a g^(2 gamma) + b_c / (tau_i tau_j).

    g = sqrt(tau_i tau_j) / tau_0. The first term is an LO frequency error,
    shared by all results, delta_f² at tau_0 if gamma = 0; the second a phase
    common to all returns of result c, such as the radar's motion during that
    capture, of variance (2 pi)² b_c. Returns a, b per result and the cost.
    """
    weights = 1 / np.sqrt(table[:, 5] * table[:, 6])
    product = table[:, 2] * table[:, 3]
    owner = table[:, 7].astype(int)
    motion = np.zeros((len(table), n_results))
    motion[np.arange(len(table)), owner] = REFERENCE_DELAY_S**2 / product
    design = np.column_stack(
        ((np.sqrt(product) / REFERENCE_DELAY_S) ** (2 * gamma), motion)
    )
    # Both kinds of column are Hz² at tau_0, so the solver sees similar sizes.
    solution, residual = nnls(design * weights[:, None], table[:, 4] * weights)
    return (
        float(solution[0]),
        np.asarray(solution[1:] * REFERENCE_DELAY_S**2),
        float(residual**2),
    )


def delay_fit(table: FloatArray, n_results: int) -> dict[str, Any]:
    """The LO-plus-motion fit at gamma = 0 and with gamma free."""
    if len(table) < 3:
        nan = float("nan")
        return {
            "df": nan,
            "motion_rad": np.full(n_results, nan),
            "gamma": nan,
            "df_gamma": nan,
        }
    fixed_a, fixed_b, _ = lo_and_motion(table, n_results, 0.0)
    gamma = float(
        minimize_scalar(
            lambda value: lo_and_motion(table, n_results, value)[2],
            bounds=GAMMA_BOUNDS,
            method="bounded",
        ).x
    )
    free_a, _, _ = lo_and_motion(table, n_results, gamma)
    return {
        "df": float(np.sqrt(fixed_a)),
        "motion_rad": 2 * np.pi * np.sqrt(fixed_b),
        "gamma": gamma,
        "df_gamma": float(np.sqrt(free_a)),
    }


def bootstrap(
    results: list[dict[str, Any]],
    labels: list[str],
    rng: np.random.Generator,
    clean_only: bool = True,
) -> dict[str, Any]:
    """Estimates over the pairs of ``results`` with CPI-resampled p5-p95."""
    table = pair_table(results, clean_only=clean_only)
    fit = delay_fit(table, len(results))
    samples = []
    for _ in range(BOOTSTRAP):
        frames = [
            rng.integers(0, len(result["cross"]), len(result["cross"]))
            for result in results
        ]
        resampled = pair_table(results, frames, clean_only)
        samples.append(
            {"mean": weighted_df(resampled), **delay_fit(resampled, len(results))}
        )

    def interval(key: str, index: int | None = None) -> list[float] | None:
        values = np.array(
            [sample[key] if index is None else sample[key][index] for sample in samples]
        )
        finite = values[np.isfinite(values)]
        if not finite.size:
            return None
        return [float(np.percentile(finite, 5)), float(np.percentile(finite, 95))]

    def finite(value: float) -> float | None:
        return float(value) if np.isfinite(value) else None

    # Delay-law table: pairs by their farther return, each with its capture's
    # fitted common phase removed.
    far = np.maximum(table[:, 0], table[:, 1]) if len(table) else np.zeros(0)
    corrected = table.copy()
    if len(table):
        motion_b = np.nan_to_num(fit["motion_rad"] / (2 * np.pi)) ** 2
        corrected[:, 4] -= motion_b[table[:, 7].astype(int)] / (
            table[:, 2] * table[:, 3]
        )
    by_band = []
    for low, high in RANGE_BANDS_M:
        inside = (far >= low) & (far < high)
        if inside.any():
            by_band.append(
                {
                    "farther_return_m": [low, high],
                    "pairs": int(inside.sum()),
                    "df_rms_hz": weighted_df(corrected[inside]),
                }
            )
    return {
        "pairs": len(table),
        "df_rms_hz": finite(fit["df"]),
        "df_rms_p5_p95_hz": interval("df"),
        "motion": {
            label: {
                "phase_rms_mrad": finite(1e3 * fit["motion_rad"][k]),
                "phase_rms_p5_p95_mrad": [
                    1e3 * value for value in (interval("motion_rad", k) or [])
                ],
                "displacement_rms_um": finite(
                    fit["motion_rad"][k] * WAVELENGTH_M / (4 * np.pi) * 1e6
                ),
            }
            for k, label in enumerate(labels)
        },
        "gamma": finite(fit["gamma"]),
        "gamma_p5_p95": interval("gamma"),
        "df_rms_at_75m_free_gamma_hz": finite(fit["df_gamma"]),
        "pair_mean_df_rms_hz": finite(weighted_df(table)),
        "pair_mean_df_rms_p5_p95_hz": interval("mean"),
        "by_farther_return": by_band,
    }


def cw_prediction(capture: Capture, range_m: float) -> dict[str, float]:
    """CW-table delta_f rms over the analysed band, for both RF bands."""
    doppler = capture.doppler_axis()
    band = np.abs(doppler) >= LOW_DOPPLER_HZ
    bin_hz = 1 / (capture.n_chirps * capture.chirp_period_s)
    prediction = {}
    for rf_band in RF_BANDS:
        for level in LEVELS:
            model = SingleReturnPhaseNoise.from_range(
                range_m,
                shared=ctrx8188f_phase_noise(
                    rf_band=rf_band, level=level, extrapolation="constant"
                ),
            )
            psd = per_chirp_frequency_psd(
                model,
                doppler,
                capture.chirp_period_s,
                capture.sample_rate_hz,
                range_window(capture.n_samples),
            )
            prediction[f"{rf_band}_{level}_hz"] = float(
                np.sqrt(psd[band].sum() * bin_hz)
            )
    return prediction


def band_spectrum(
    results: list[list[dict[str, Any]]], edges_hz: list[float]
) -> list[dict[str, Any]]:
    """Pooled cross-return delta_f PSD (two-sided, Hz²/Hz) per slow-time band.

    ``results`` holds, per band, the results whose cross-powers cover only that
    band (sub_band_results); the band's variance is spread over its two-sided
    width.
    """
    rows = []
    for (low, high), result_set in zip(zip(edges_hz[:-1], edges_hz[1:]), results):
        df = weighted_df(pair_table(result_set))
        rows.append(
            {
                "band_hz": [low, high],
                "psd_db_hz2_per_hz": float(db(df**2 / (2 * (high - low)))),
            }
        )
    return rows


def sub_band_results(
    capture: Capture,
    scene: dict[str, FloatArray],
    base: dict[str, Any],
    edges_hz: list[float],
    frames: list[int],
) -> list[dict[str, Any]]:
    """The base result's returns and cleanliness, cross-powers per sub-band."""
    nc = capture.n_chirps
    window = doppler_window(nc)
    doppler = np.abs(capture.doppler_axis())
    allowed = np.ones(nc, dtype=bool)
    if capture.ddma_length > 1:
        allowed = away_from_lines(nc, capture.ddma_length, DDMA_GUARD_BINS)
    bands = []
    for low, high in zip(edges_hz[:-1], edges_hz[1:]):
        inside = (doppler >= low) & (doppler < high)
        bands.append(
            (inside & allowed, inside.sum() / max((inside & allowed).sum(), 1))
        )
    cross: list[list[FloatArray]] = [[] for _ in bands]
    tau = base["tau"]
    for frame in frames:
        gains = chirp_gains(
            capture.load(frame),
            capture.beat_frequency_hz(base["ranges"]),
            capture.sample_rate_hz,
        )
        errors, weights, _ = tone_model_errors(gains, base["lines"])
        values = errors.imag / (2 * np.pi * tau)
        for k, (mask, scale) in enumerate(bands):
            cross[k].append(weighted_cross_power(values, weights, mask, window) * scale)
    return [dict(base, cross=np.array(entries)) for entries in cross]


def spectrum_edges(capture: Capture) -> list[float]:
    nyquist = 0.5 / capture.chirp_period_s
    if nyquist < 10e3:
        return [500.0, 1000.0, 2000.0, 3000.0, 4000.0, nyquist]
    return [500.0, 2000.0, 5000.0, 10e3, 20e3, nyquist]


def plot(
    output: Path,
    spectra: dict[str, list[dict[str, Any]]],
    predictions: dict[str, dict[str, float]],
    captures: dict[str, Capture],
    per_return: dict[str, list[tuple[float, float]]],
    fits: dict[str, dict[str, Any]],
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(15, 5.5), layout="constrained")
    axis = axes[0]
    for index, (label, rows) in enumerate(spectra.items()):
        centres = [np.mean(row["band_hz"]) / 1e3 for row in rows]
        levels = [row["psd_db_hz2_per_hz"] for row in rows]
        axis.plot(centres, levels, "o-", color=f"C{index}", label=f"{label}, measured")
        capture = captures[label]
        prf = 1 / capture.chirp_period_s
        for rf_band, style in zip(RF_BANDS, ("--", ":")):
            rms = predictions[label][f"{rf_band}_typical_hz"]
            axis.hlines(
                db(rms**2 / (prf - 2 * LOW_DOPPLER_HZ)),
                0.5,
                prf / 2e3,
                color=f"C{index}",
                linestyle=style,
                linewidth=0.8,
            )
    for rf_band, style in zip(RF_BANDS, ("--", ":")):
        axis.plot(
            [], [], color="black", linestyle=style, label=f"CW typical, {rf_band} GHz"
        )
    axis.set(
        xscale="log",
        xlabel="Slow-time frequency [kHz]",
        ylabel="dB Hz²/Hz (two-sided)",
        title="Per-chirp frequency error, cross-return over clean returns",
    )
    axis.grid(alpha=0.3, which="both")
    axis.legend(fontsize=8)

    axis = axes[1]
    for index, (label, points) in enumerate(per_return.items()):
        if not points:
            continue
        values = np.array(points)
        axis.plot(
            values[:, 0], values[:, 1] / 1e3, "o", color=f"C{index}", ms=4, label=label
        )
        fit = fits[label]
        if fit["df_rms_hz"] is not None:
            axis.axhline(fit["df_rms_hz"] / 1e3, color=f"C{index}", linewidth=0.8)
    axis.set(
        yscale="log",
        xlabel="Apparent range of the return [m]",
        ylabel="delta_f rms shared with the other clean returns [kHz]",
        title="Delay law: one delta_f at every delay is a flat line (the fit)\n"
        "a phase common to all returns (motion) rises towards short range",
    )
    axis.grid(alpha=0.3, which="both")
    axis.legend(fontsize=8)
    figure.savefig(output / "phase.png", dpi=120)
    plt.close(figure)


def per_return_df(result: dict[str, Any]) -> list[tuple[float, float]]:
    """Each clean return's weighted cross-power with its partners, as rms."""
    mean = result["cross"].mean(axis=0)
    points = []
    for i in np.flatnonzero(result["clean"]):
        partners = [
            j for a, b in pairs(result) for j in (a, b) if i in (a, b) and j != i
        ]
        if not partners:
            continue
        weights = np.array([1 / (mean[i, i] * mean[j, j]) for j in partners])
        value = (
            np.sum(weights * np.array([mean[i, j] for j in partners])) / weights.sum()
        )
        points.append((float(result["ranges"][i]), float(np.sqrt(max(value, 0.0)))))
    return points


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    data_arguments(parser)
    case_arguments(parser, ALL_CASES)
    parser.add_argument(
        "--scene",
        type=Path,
        default=GENERATED_DIR / "scene",
        help="window_scene.py output for these cases",
    )
    parser.add_argument("--output", type=Path, default=GENERATED_DIR / "phase")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260930)
    scene_cases = json.loads((args.scene / "summary.json").read_text())["cases"]

    captures: dict[str, Capture] = {}
    frames: dict[str, list[int]] = {}
    results: dict[str, dict[str, Any]] = {}
    cases: dict[str, Any] = {}
    for case in resolve_cases(args.cases, args.data, ALL_CASES):
        if case == "long-8TX-0dB":
            continue
        capture = load_capture(case, args.data, args.infineon_data)
        scene = dict(np.load(args.scene / f"{case}.npz"))
        dropped = scene_cases[case].get("interference_cpis", [])
        frames[case] = [k for k in range(capture.n_frames) if k not in dropped]
        result = analyze(capture, scene, frames[case])
        captures[case] = capture
        results[case] = result
        estimate = bootstrap([result], [case], rng)
        every = bootstrap([result], [case], rng, clean_only=False)
        clean_ranges = result["ranges"][result["clean"]]
        cases[case] = {
            "cpis_dropped_interference": dropped,
            "returns": [
                {
                    "range_m": float(r),
                    "snr_per_chirp_db": float(s),
                    "amplitude_over_additive_db": float(a),
                    "phase_over_additive_db": float(p),
                    "clean": bool(c),
                }
                for r, s, a, p, c in zip(
                    result["ranges"],
                    result["snr"],
                    result["amplitude_excess_db"],
                    result["phase_excess_db"],
                    result["clean"],
                )
            ],
            "kept_band_fraction": float(result["kept_fraction"]),
            **estimate,
            "all_returns": {
                key: every[key]
                for key in (
                    "pairs",
                    "df_rms_hz",
                    "df_rms_p5_p95_hz",
                    "motion",
                    "pair_mean_df_rms_hz",
                    "pair_mean_df_rms_p5_p95_hz",
                )
            },
            "cw_prediction_rms_hz": cw_prediction(
                capture, float(np.median(clean_ranges)) if clean_ranges.size else 100.0
            ),
        }

    families: dict[str, Any] = {}
    for family in FAMILIES:
        members = [case for case in results if captures[case].family == family]
        if family == "infineon":
            groups = {case: [case] for case in members}
        else:
            groups = {family: members}
        for label, group in groups.items():
            families[label] = {
                "cases": group,
                **bootstrap([results[case] for case in group], group, rng),
            }

    # Slow-time spectra, pooled per family for the default cases (Infineon
    # mode 0 has no clean pair), per case otherwise.
    spectrum_sets = {
        "medium": ["medium-1TX-0dB", "medium-8TX-0dB", "medium-8TX-0dB-2"],
        "short": ["short-8TX-0dB", "short-8TX-0dB-2"],
        "infineon-mode1": ["infineon-mode1"],
    }
    if args.cases is not None:
        spectrum_sets = {case: [case] for case in results if cases[case]["pairs"] >= 3}
    spectra: dict[str, list[dict[str, Any]]] = {}
    for label, group in spectrum_sets.items():
        edges = spectrum_edges(captures[group[0]])
        per_band: list[list[dict[str, Any]]] = [[] for _ in edges[:-1]]
        for case in group:
            scene = dict(np.load(args.scene / f"{case}.npz"))
            for k, sub in enumerate(
                sub_band_results(
                    captures[case], scene, results[case], edges, frames[case]
                )
            ):
                per_band[k].append(sub)
        spectra[label] = band_spectrum(per_band, edges)
    for label, rows in spectra.items():
        if args.cases is None:
            families.setdefault(label, {})["slow_time_psd"] = rows
        else:
            cases[label]["slow_time_psd"] = rows

    predictions = {
        label: cases[group[0]]["cw_prediction_rms_hz"]
        for label, group in spectrum_sets.items()
    }
    per_return = {
        label: [point for case in group for point in per_return_df(results[case])]
        for label, group in spectrum_sets.items()
    }
    plot(
        args.output,
        spectra,
        predictions,
        {label: captures[group[0]] for label, group in spectrum_sets.items()},
        per_return,
        {
            label: families[label] if args.cases is None else cases[label]
            for label in spectrum_sets
        },
    )
    write_summary(
        args.output,
        {
            "min_snr_per_chirp_db": MIN_SNR_DB,
            "low_doppler_hz": LOW_DOPPLER_HZ,
            "ddma_guard_bins": DDMA_GUARD_BINS,
            "clean_amplitude_ratio": CLEAN_AMPLITUDE_RATIO,
            "phase_dominance": PHASE_DOMINANCE,
            "min_pair_separation_m": MIN_PAIR_SEPARATION_M,
            "families": families,
            "cases": cases,
        },
    )


if __name__ == "__main__":
    main()
