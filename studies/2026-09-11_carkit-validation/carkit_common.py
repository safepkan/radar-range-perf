"""Shared paths, I/O and estimators for the CARKIT validation study.

Two datasets feed the study, each with its own capture format, windows and
constants: walk_common.py for the 2026-09-11 walk and outdoor_common.py for the
2026-09-22 outdoor reflector captures. Scripts import from their dataset
module, which re-exports what they need from here. The estimators here take
their windows as arguments, so each dataset's processing stays explicit.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from radarperf.units import SPEED_OF_LIGHT as SPEED_OF_LIGHT

FloatArray = npt.NDArray[np.float64]
ComplexArray = npt.NDArray[np.complex128]

STUDY_DIR = Path(__file__).parent
N_RX = 8
# Per-CPI polynomial removed from phase and amplitude before slow-time spectra.
DETREND_ORDER = 3
# Adjacent positive-frequency bins averaged together (with their negative
# mirrors) for display only.
DISPLAY_GROUP = 8


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
