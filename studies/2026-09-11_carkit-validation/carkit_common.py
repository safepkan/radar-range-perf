"""Shared paths, I/O and estimators for the CARKIT validation study.

Each dataset has its own module for its capture format, windows and
constants: walk_common.py for the 2026-09-11 walk, outdoor_common.py for the
2026-09-22 outdoor reflector captures, window_common.py for the out-of-window
captures (2026-08-27 in Infineon's format; 2026-09-30, 2026-10-02,
2026-10-06 and any other recording in our firmware's format) and field_common.py for the
2026-10-01 field captures, which highway_traffic.py also draws on. Scripts
import from their dataset module, which re-exports what they need from here.
The estimators here take their windows as arguments, so each dataset's
processing stays explicit.

The raw recordings are not in the repo. Each module looks for its recording in
a subfolder of ``$CARKIT_DATA_ROOT`` (default ``~/Data/carkit``) named as on the
shared drive; a dataset's own environment variable or ``--data`` overrides it.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.optimize import least_squares

from radarperf.phase_noise import SingleReturnPhaseNoise
from radarperf.units import SPEED_OF_LIGHT as SPEED_OF_LIGHT

FloatArray = npt.NDArray[np.float64]
ComplexArray = npt.NDArray[np.complex128]
BoolArray = npt.NDArray[np.bool_]

STUDY_DIR = Path(__file__).parent
# Folder holding one subfolder per recording, named as on the shared drive.
DATA_ROOT_ENV = "CARKIT_DATA_ROOT"
DEFAULT_DATA_ROOT = Path.home() / "Data" / "carkit"
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
# A CPI whose broadband background (median remote-Doppler power over this band
# of beat frequencies) exceeds its capture's median by more than this is
# treated as interfered (interference_flags).
INTERFERENCE_BAND_HZ = (2e6, 20e6)
INTERFERENCE_THRESHOLD_DB = 1.0
# CTRX8188F RX gain steps [dB] by gain code: GAIN_SEL in Configure_RX() and
# RX_GAINSET_SEL per ramp segment (user manual rev. 0.20, Tables 46 and 120),
# also Infineon's CARKIT gainSelection.
RX_GAIN_STEPS_DB = (3.0, 0.0, -3.0, -6.0, -12.0, -18.0)
# CTRX8188F typical total RX SSB noise figure [dB] at 1 and 10 MHz IF by RX gain
# step: target datasheet rev. 0.20, Table 30, the "ultra low noise operation
# mode" rows at +3 dB and the "low noise" rows at 0 dB. Infineon confirmed by
# email on 2026-10-02 that these modes are the gain steps, with no separate
# setting; typical means a nominal part at nominal supply and room temperature.
NOISE_FIGURE_TYPICAL_DB = {3.0: (9.9, 9.7), 0.0: (10.5, 10.2)}


def db(value: npt.ArrayLike) -> FloatArray:
    """Convert positive power-like values to dB."""
    return np.asarray(10 * np.log10(np.maximum(value, np.finfo(float).tiny)))


def default_data_dir(name: str) -> Path:
    """Return a recording's folder under $CARKIT_DATA_ROOT, else ~/Data/carkit."""
    return Path(os.environ.get(DATA_ROOT_ENV, DEFAULT_DATA_ROOT)) / name


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
        raise SystemExit(
            f"raw data not found at {root}; pass --data, set ${env} or set "
            f"${DATA_ROOT_ENV} to the folder holding the recordings"
        )
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


def weighted_cross_spectrum(
    values: FloatArray, weights: FloatArray, window: FloatArray
) -> FloatArray:
    """Cross-power per unshifted slow-time bin [bin, return, return].

    The terms that weighted_cross_power sums over its band: summed over a band's
    bins, this gives the same result. Divided by the bin width, a bin is a
    two-sided cross-PSD.
    """
    spectra = np.fft.fft(values * window[:, None], axis=0) / window.sum()
    cross = (spectra[:, :, None] * spectra[:, None, :].conj()).real
    return np.asarray(
        cross / enbw_bins(window) / (weights.T @ weights / len(weights))[None]
    )


@dataclass(frozen=True)
class SettlingFit:
    """A per-chirp frequency error that falls with the time between ramps.

        delta_f² = floor² + excess exp(-T_fast / tau_fast - T_pre / tau_pre):

    a floor that the timing does not change, such as the LO's ordinary phase
    noise, plus an excess that decays with the time T_fast the synthesizer
    spends in fast-settling mode (flyback and wait) and with the pre-payload
    T_pre, the unsampled start of the next ramp. ``parameters`` are the floor
    [Hz], ln excess [ln Hz²], ln tau_fast and ln tau_pre [ln s]; the
    logarithms keep the excess and the time constants positive.
    """

    parameters: FloatArray
    covariance: FloatArray
    reduced_chi2: float

    @property
    def floor_hz(self) -> float:
        return float(self.parameters[0])

    @property
    def tau_fast_s(self) -> float:
        return float(np.exp(self.parameters[2]))

    @property
    def tau_pre_s(self) -> float:
        return float(np.exp(self.parameters[3]))

    def df_hz(
        self,
        pre_payload_s: npt.ArrayLike,
        fast_settling_s: npt.ArrayLike,
        parameters: FloatArray | None = None,
    ) -> FloatArray:
        """delta_f rms at the given timing [s], broadcast.

        With ``parameters`` [n, 4], such as draws, one result per row [n, ...].
        """
        p = np.atleast_2d(self.parameters if parameters is None else parameters)
        pre = np.asarray(pre_payload_s, dtype=float)
        fast = np.asarray(fast_settling_s, dtype=float)
        shape = (-1,) + (1,) * np.broadcast(pre, fast).ndim
        floor, log_excess, log_tau_fast, log_tau_pre = (
            p[:, k].reshape(shape) for k in range(4)
        )
        value = np.sqrt(
            floor**2
            + np.exp(
                log_excess - fast / np.exp(log_tau_fast) - pre / np.exp(log_tau_pre)
            )
        )
        return np.asarray(value if parameters is not None else value[0])

    def draws(self, rng: np.random.Generator, n: int) -> FloatArray:
        """Parameter draws [n, 4] from the fit's covariance."""
        return np.asarray(rng.multivariate_normal(self.parameters, self.covariance, n))


def settling_fit(
    pre_payload_s: FloatArray,
    fast_settling_s: FloatArray,
    df_hz: FloatArray,
    df_sigma_hz: FloatArray,
) -> SettlingFit:
    """Least-squares SettlingFit of measured delta_f with standard errors.

    The residuals are in delta_f rms, scaled by ``df_sigma_hz``. The
    covariance is the Gauss-Newton one, scaled by the reduced chi² where that
    exceeds 1. Internally the fit runs in kHz and microseconds.
    """
    pre_us = pre_payload_s * 1e6
    fast_us = fast_settling_s * 1e6
    df_khz = df_hz / 1e3
    sigma_khz = df_sigma_hz / 1e3

    def model(p: FloatArray) -> FloatArray:
        excess = np.exp(p[1] - fast_us / np.exp(p[2]) - pre_us / np.exp(p[3]))
        return np.asarray(np.sqrt(p[0] ** 2 + excess))

    floor_guess = float(df_khz.min())
    start = np.array(
        [
            floor_guess,
            np.log(max(df_khz.max() ** 2 - floor_guess**2, 1.0)) + 3,
            1.0,
            1.0,
        ]
    )
    result = least_squares(lambda p: (model(p) - df_khz) / sigma_khz, start)
    dof = max(df_khz.size - start.size, 1)
    reduced_chi2 = float(np.sum(result.fun**2) / dof)
    covariance = np.linalg.inv(result.jac.T @ result.jac) * max(reduced_chi2, 1.0)
    # kHz -> Hz on the floor, kHz² -> Hz² and microseconds -> seconds in the
    # logarithms, which shifts them without scaling their errors.
    scale = np.array([1e3, 1.0, 1.0, 1.0])
    parameters = result.x * scale + np.array(
        [0.0, np.log(1e6), np.log(1e-6), np.log(1e-6)]
    )
    return SettlingFit(
        parameters=np.asarray(parameters),
        covariance=np.asarray(covariance * np.outer(scale, scale)),
        reduced_chi2=reduced_chi2,
    )


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


def noise_figure_db(rx_gain_db: float, at_1_mhz: bool = False) -> float:
    """The datasheet's typical noise figure for an RX gain step.

    At 10 MHz IF, the toolbox preset's convention, unless ``at_1_mhz``. The
    datasheet specifies only the +3 and 0 dB steps; for negative steps it
    gives a worst-case bound, not a typical value.
    """
    if rx_gain_db not in NOISE_FIGURE_TYPICAL_DB:
        raise ValueError(f"no typical noise figure for RX gain {rx_gain_db} dB")
    at_1, at_10 = NOISE_FIGURE_TYPICAL_DB[rx_gain_db]
    return at_1 if at_1_mhz else at_10


def interference_flags(
    levels_db: npt.ArrayLike, threshold_db: float = INTERFERENCE_THRESHOLD_DB
) -> BoolArray:
    """CPIs whose broadband background is raised, as by another radar's chirps.

    ``levels_db`` holds one background level per CPI, such as the median
    remote-Doppler power over a wide band of beat frequencies. Another radar's
    chirps crossing ours raise it at all ranges at once, unlike a target or
    its pedestal. A CPI is flagged when its level exceeds the capture's median
    by more than ``threshold_db``.
    """
    levels = np.asarray(levels_db, dtype=float)
    return np.asarray(levels > np.median(levels) + threshold_db)


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
