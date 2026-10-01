"""Shared paths, I/O and estimators for the CARKIT validation study.

Three datasets feed the study, each with its own capture format, windows and
constants: walk_common.py for the 2026-09-11 walk, outdoor_common.py for the
2026-09-22 outdoor reflector captures and window_common.py for the
out-of-window captures of 2026-08-27 and 2026-09-30. Scripts import from their
dataset module, which re-exports what they need from here. The estimators here
take their windows as arguments, so each dataset's processing stays explicit.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from radarperf.phase_noise import SingleReturnPhaseNoise
from radarperf.units import SPEED_OF_LIGHT as SPEED_OF_LIGHT

FloatArray = npt.NDArray[np.float64]
ComplexArray = npt.NDArray[np.complex128]
BoolArray = npt.NDArray[np.bool_]

STUDY_DIR = Path(__file__).parent
N_RX = 8
# Per-CPI polynomial removed from phase and amplitude before slow-time spectra.
DETREND_ORDER = 3
# Adjacent positive-frequency bins averaged together (with their negative
# mirrors) for display only.
DISPLAY_GROUP = 8
# Offset band of the CW phase-noise tables integrated in per_chirp_frequency_psd,
# and the resolution of the range weighting's response there (2^20-point FFT).
CW_OFFSET_BAND_HZ = (1.0, 20e6)
RESPONSE_FFT_SIZE = 2**20


def db(value: npt.ArrayLike) -> FloatArray:
    """Convert positive power-like values to dB."""
    return np.asarray(10 * np.log10(np.maximum(value, np.finfo(float).tiny)))


def data_argument(parser: argparse.ArgumentParser, env: str, default: Path) -> None:
    """Add the optional raw-data directory argument."""
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help=f"raw data directory (default: ${env} or {default})",
    )


def resolve_data_dir(data: Path | None, env: str, default: Path) -> Path:
    """Return the raw data directory from argument, environment or default."""
    root = data or Path(os.environ.get(env, default))
    if not root.is_dir():
        raise SystemExit(f"raw data not found at {root}; pass --data or set ${env}")
    return root


def write_summary(output: Path, summary: dict[str, Any]) -> None:
    """Write summary.json and echo it."""
    output.mkdir(parents=True, exist_ok=True)
    text = json.dumps(summary, indent=2) + "\n"
    (output / "summary.json").write_text(text)
    print(text, end="")


def enbw_bins(weights: FloatArray) -> float:
    """Equivalent noise bandwidth of a window in bins."""
    return float(weights.size * np.sum(weights**2) / np.sum(weights) ** 2)


def chirp_gains(
    raw: FloatArray, beat_hz: FloatArray, sample_rate_hz: float, weights: FloatArray
) -> ComplexArray:
    """Per-chirp complex amplitude of each return, [chirp, return, RX].

    Each chirp is projected onto a tone at the return's beat frequency,
    weighted by ``weights`` and normalized by their sum: the range spectrum
    evaluated at that exact frequency rather than at the nearest bin.
    """
    time = np.arange(raw.shape[1]) / sample_rate_hz
    tones = np.exp(-2j * np.pi * np.outer(beat_hz, time)) * weights / weights.sum()
    return np.asarray(np.einsum("csr,ks->ckr", raw, tones))


def detrend(values: FloatArray, order: int = DETREND_ORDER) -> FloatArray:
    """Remove a least-squares polynomial along axis 0 from every column."""
    basis = np.polynomial.polynomial.polyvander(
        np.linspace(-1, 1, values.shape[0]), order
    )
    flat = values.reshape(values.shape[0], -1)
    fitted = basis @ np.linalg.lstsq(basis, flat, rcond=None)[0]
    return np.asarray((flat - fitted).reshape(values.shape))


def chirp_fluctuations(
    gains: ComplexArray,
    doppler_hz: FloatArray,
    chirp_period_s: float,
    order: int = DETREND_ORDER,
) -> tuple[FloatArray, FloatArray]:
    """Per-chirp phase [rad] and fractional amplitude, without phase unwrapping.

    ``gains`` is [chirp, return, RX] and ``doppler_hz`` holds one Doppler per
    return. Each return is derotated by its Doppler, a complex polynomial of
    ``order`` per return and RX is fitted as the smooth return s, and z/s - 1
    is split into its imaginary part (phase) and real part (amplitude). Being
    linear in additive noise, it holds down to per-chirp SNRs where unwrapping
    slips; for small fluctuations it equals the detrended phase and amplitude.
    """
    n_chirps = gains.shape[0]
    chirp_time = np.arange(n_chirps) * chirp_period_s
    derotated = (
        gains * np.exp(-2j * np.pi * np.outer(chirp_time, doppler_hz))[:, :, None]
    )
    basis = np.polynomial.polynomial.polyvander(np.linspace(-1, 1, n_chirps), order)
    flat = derotated.reshape(n_chirps, -1)
    smooth = (basis @ np.linalg.lstsq(basis, flat, rcond=None)[0]).reshape(gains.shape)
    ratio = derotated / smooth - 1
    return np.asarray(ratio.imag), np.asarray(ratio.real)


def tone_model_errors(
    gains: ComplexArray, tones: FloatArray, order: int = DETREND_ORDER
) -> tuple[ComplexArray, FloatArray, FloatArray]:
    """Per-chirp error of each return against a smooth multi-tone model.

    ``gains`` is [chirp, return, RX] and ``tones`` [return, line] holds each
    return's slow-time lines in cycles per chirp: one line for a single or
    coherently phased transmitter, one per transmitter under DDMA. The model s
    is a complex polynomial of ``order`` per line, fitted per return and RX by
    least squares. A per-chirp phase error delta_phi multiplies all lines
    alike, z = s (1 + j delta_phi), so

        y = sum_RX (z - s) conj(s) / mean(sum_RX |s|²)

    has Im(y) = g delta_phi and Re(y) = g delta_a plus additive noise, with
    g = sum_RX |s|² / its mean. Weighting by the model keeps the estimate finite
    where the transmitters' sum is small; for one line it is the RX-power-weighted
    mean of chirp_fluctuations. Returns y and g, both [chirp, return], and the
    mean RX-summed model power per chirp [return].
    """
    n_chirps, n_returns, _ = gains.shape
    chirps = np.arange(n_chirps)
    basis = np.polynomial.polynomial.polyvander(np.linspace(-1, 1, n_chirps), order)
    errors = np.empty((n_chirps, n_returns), dtype=complex)
    weights = np.empty((n_chirps, n_returns))
    power = np.empty(n_returns)
    for k in range(n_returns):
        lines = np.exp(2j * np.pi * np.outer(chirps, tones[k]))
        design = (lines[:, :, None] * basis[:, None, :]).reshape(n_chirps, -1)
        smooth = design @ np.linalg.lstsq(design, gains[:, k], rcond=None)[0]
        summed = np.sum(np.abs(smooth) ** 2, axis=-1)
        power[k] = summed.mean()
        errors[:, k] = np.sum((gains[:, k] - smooth) * smooth.conj(), axis=-1)
        errors[:, k] /= power[k]
        weights[:, k] = summed / power[k]
    return errors, weights, power


def away_from_lines(n_chirps: int, n_lines: int, guard_bins: int) -> BoolArray:
    """Unshifted slow-time bins more than ``guard_bins`` from every k/n_lines.

    Under DDMA with ``n_lines`` phase slots, the model weighting g and any
    spurious slot lines put deterministic content at multiples of PRF/n_lines;
    these bins are left out of the error spectra.
    """
    offset = (np.arange(n_chirps) * n_lines / n_chirps + 0.5) % 1 - 0.5
    return np.asarray(np.abs(offset) * n_chirps / n_lines > guard_bins)


def weighted_cross_power(
    values: FloatArray,
    weights: FloatArray,
    band: BoolArray,
    window: FloatArray,
) -> FloatArray:
    """Band-limited cross-power [return, return] of g-weighted series.

    ``values`` [chirp, return] are g x plus noise, with ``weights`` g as from
    tone_model_errors. Their windowed, sum-normalized slow-time spectra are
    multiplied pairwise, summed over the unshifted ``band`` bins, divided by the
    window's ENBW and by the mean of g_i g_j. For a stationary x this is its
    variance within the band; between two returns it keeps only what their x
    share, since noise and clutter at different ranges are independent.
    """
    spectra = np.fft.fft(values * window[:, None], axis=0)[band] / window.sum()
    cross = np.einsum("fi,fj->ij", spectra, spectra.conj()).real
    return np.asarray(cross / enbw_bins(window) / (weights.T @ weights / len(weights)))


def track_range_scale(
    times_s: FloatArray,
    ranges_m: FloatArray,
    doppler_hz: FloatArray,
    prf_hz: float,
    wavelength_m: float,
    sign: int,
) -> tuple[float, float, float]:
    """Range scale of one moving target tracked over CPIs.

    ``ranges_m`` are the apparent (beat-derived) ranges and ``doppler_hz`` the
    aliased Doppler frequencies at ``times_s``. Each Doppler is unwrapped to the
    alias nearest the apparent range rate, turned into a radial velocity
    sign * f * wavelength / 2, and integrated (trapezoid) into a distance D(t),
    which depends on the carrier frequency and the CPI timing only. The apparent
    range is fitted as a + scale * D; a correct range scale gives 1. Returns
    the scale, its standard error and the rms residual in metres.
    """
    range_rate = np.polyfit(times_s, ranges_m, 1)[0]
    folds = np.arange(-8, 9)
    candidates = (
        sign * (doppler_hz[:, None] + folds[None, :] * prf_hz) * wavelength_m / 2
    )
    pick = np.argmin(np.abs(candidates - range_rate), axis=1)
    velocity = candidates[np.arange(len(times_s)), pick]
    distance = np.concatenate(
        ([0.0], np.cumsum(0.5 * (velocity[1:] + velocity[:-1]) * np.diff(times_s)))
    )
    design = np.column_stack((np.ones_like(distance), distance))
    coefficients = np.linalg.lstsq(design, ranges_m, rcond=None)[0]
    residual = ranges_m - design @ coefficients
    dof = max(len(ranges_m) - 2, 1)
    spread = np.sum((distance - distance.mean()) ** 2)
    error = float(np.sqrt(np.sum(residual**2) / dof / spread)) if spread > 0 else np.inf
    return float(coefficients[1]), error, float(np.sqrt(np.mean(residual**2)))


def per_chirp_frequency_psd(
    phase_noise: SingleReturnPhaseNoise,
    doppler_hz: FloatArray,
    chirp_period_s: float,
    sample_rate_hz: float,
    weights: FloatArray,
    offset_band_hz: tuple[float, float] = CW_OFFSET_BAND_HZ,
) -> FloatArray:
    """Two-sided PSD [Hz²/Hz] of the per-chirp equivalent frequency error.

    A return's per-chirp phase is the ``weights``-weighted mean of its phase
    difference over the sampled payload, sampled once per chirp. Its slow-time
    PSD is therefore

        S(f_D) = sum_k P(f_D + k PRF) |H(f_D + k PRF)|²,

    with P the delay-filtered phase PSD of ``phase_noise`` and H the normalized
    weighting's frequency response. Divided by (2 pi tau)², this is the
    equivalent frequency-error PSD that the phase steps measure.
    """
    response = np.abs(np.fft.rfft(weights, RESPONSE_FFT_SIZE) / weights.sum()) ** 2
    response_hz = np.fft.rfftfreq(RESPONSE_FFT_SIZE, 1 / sample_rate_hz)
    prf = 1 / chirp_period_s
    folds = np.arange(
        -int(offset_band_hz[1] / prf) - 1, int(offset_band_hz[1] / prf) + 2
    )
    offsets = doppler_hz[:, None] + folds[None, :] * prf
    inside = (np.abs(offsets) >= offset_band_hz[0]) & (
        np.abs(offsets) <= offset_band_hz[1]
    )
    density = np.zeros(offsets.shape)
    density[inside] = phase_noise.residual_psd_per_hz(offsets[inside]) * np.interp(
        np.abs(offsets[inside]), response_hz, response
    )
    return np.asarray(density.sum(axis=1) / (2 * np.pi * phase_noise.delay_s) ** 2)


def linear_rate(values: FloatArray, step: float) -> FloatArray:
    """Least-squares slope along axis 0 per unit of ``step`` spacing."""
    time = (np.arange(values.shape[0]) - (values.shape[0] - 1) / 2) * step
    flat = values.reshape(values.shape[0], -1)
    slope = time @ (flat - flat.mean(axis=0)) / np.sum(time**2)
    return np.asarray(slope.reshape(values.shape[1:]))


def cross_channel_power(spectrum: ComplexArray) -> FloatArray:
    """Mean of Re(F_r conj(F_s)) over distinct RX pairs; RX on the last axis.

    Independent per-RX noise averages to zero in expectation, so this
    estimates the power of the component common to all channels.
    """
    n = spectrum.shape[-1]
    total = spectrum.sum(axis=-1)
    own = np.sum(np.abs(spectrum) ** 2, axis=-1)
    return np.asarray((np.abs(total) ** 2 - own) / (n * (n - 1)))


def cross_channel_cross(first: ComplexArray, second: ComplexArray) -> FloatArray:
    """Mean of Re(F_r conj(G_s)) over distinct RX pairs; RX on the last axis."""
    n = first.shape[-1]
    mixed = first.sum(axis=-1) * np.conj(second.sum(axis=-1))
    own = np.sum(first * np.conj(second), axis=-1)
    return np.asarray(((mixed - own) / (n * (n - 1))).real)


def delay_s(range_m: npt.ArrayLike) -> FloatArray:
    """Round-trip delay of apparent (beat-derived) range."""
    return np.asarray(2 * np.asarray(range_m, dtype=float) / SPEED_OF_LIGHT)


def display_groups(
    doppler_hz: FloatArray, values: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Average unshifted positive/negative mirror bins, then DISPLAY_GROUP bins."""
    n = doppler_hz.size
    positive = np.flatnonzero(doppler_hz > 0)
    groups = positive[: positive.size // DISPLAY_GROUP * DISPLAY_GROUP].reshape(
        -1, DISPLAY_GROUP
    )
    mirrored = 0.5 * (values[groups] + values[(-groups) % n])
    return (
        np.asarray(doppler_hz[groups].mean(axis=1)),
        np.asarray(mirrored.mean(axis=1)),
    )
