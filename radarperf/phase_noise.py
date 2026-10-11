"""LO phase noise: single-return diagnostics and the per-chirp frequency error.

SSB input L(f) is in dBc/Hz. In the small-phase approximation, its linear
value is also the *two-sided* phase PSD at either signed offset: do not add
another factor of two per sideband. Shared-source noise is multiplied by
4 sin²(pi f delay); independent TX/RX residual contributions add in power.

FFT predictions integrate a band-limited stationary process over the actual
sample times, including chirp gaps. They return expected power, not a random
realization, and are independent of the link-budget engine.

The per-chirp frequency error delta_f, which sets the link budget's coherence
loss (``SystemLosses.chirp_frequency_error_rms_hz``), follows from a CW
spectrum with :func:`chirp_frequency_error_rms_hz`, or from the chirp timing
with an empirical :class:`ChirpSettling`. See docs/phase_noise.md for the
derivations and docs/phase_noise_diagnostic.md for the FFT diagnostic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol, cast

import numpy as np
import numpy.typing as npt
from scipy.fft import next_fast_len
from scipy.signal import get_window

from .units import SPEED_OF_LIGHT, FloatOrArray, db_to_linear, linear_to_db
from .waveform import FmcwWaveform

FloatArray = npt.NDArray[np.float64]
Extrapolation = Literal["error", "constant", "slope"]
Sampling = Literal["complex", "real_phase_averaged"]
ChirpCorrelation = Literal["stationary", "independent"]

# Zero-padded FFT length for the payload weighting's frequency response. Its
# spacing, fs / 2**20, is far finer than the window's bin width fs / n_samples.
_RESPONSE_FFT_SIZE = 2**20
# Slow-time grid for integrating the folded per-chirp PSD over a band.
_SLOW_TIME_POINTS = 2049
# Folds evaluated together in chirp_frequency_error_psd, to bound memory.
_FOLD_BLOCK = 64


class PhaseNoiseSpectrum(Protocol):
    """A source or independent residual spectrum at positive offsets."""

    def ssb_linear_per_hz(self, offset_hz: FloatArray) -> FloatArray: ...


@dataclass(frozen=True)
class TabulatedPhaseNoise:
    """SSB data interpolated in dB versus log10(offset frequency).

    Outside the table, raise by default. ``constant`` holds the end levels;
    ``slope`` extends the end segments. Neither is a measured specification.
    All evaluated offsets must be strictly positive, including for constant
    extrapolation. Use explicit integration bounds to handle DC and tails.
    """

    offset_hz: tuple[float, ...]
    ssb_dbc_hz: tuple[float, ...]
    extrapolation: Extrapolation = "error"
    name: str = "tabulated phase noise"
    source: str = "user supplied"

    def __post_init__(self) -> None:
        f = np.asarray(self.offset_hz, dtype=float)
        p = np.asarray(self.ssb_dbc_hz, dtype=float)
        if (
            f.ndim != 1
            or f.size < 2
            or p.shape != f.shape
            or not np.all(np.isfinite(f))
            or not np.all(np.isfinite(p))
            or np.any(f <= 0)
            or np.any(np.diff(f) <= 0)
        ):
            raise ValueError("need >= 2 finite levels and increasing positive offsets")
        if self.extrapolation not in ("error", "constant", "slope"):
            raise ValueError("extrapolation must be error, constant or slope")
        # Own immutable data, even if a caller supplied mutable sequences.
        object.__setattr__(self, "offset_hz", tuple(float(x) for x in f))
        object.__setattr__(self, "ssb_dbc_hz", tuple(float(x) for x in p))

    def ssb_db(self, offset_hz: npt.ArrayLike) -> FloatArray:
        """SSB density [dBc/Hz]; preserves input shape (including scalar)."""
        f = np.asarray(offset_hz, dtype=float)
        if not np.all(np.isfinite(f)) or np.any(f <= 0):
            raise ValueError("offsets must be finite and positive")
        if self.extrapolation == "error" and np.any(
            (f < self.offset_hz[0]) | (f > self.offset_hz[-1])
        ):
            raise ValueError("offset outside phase-noise table; choose extrapolation")
        x = np.log10(f)
        xp = np.log10(self.offset_hz)
        yp = np.asarray(self.ssb_dbc_hz)
        values = np.asarray(np.interp(x, xp, yp))
        if self.extrapolation == "slope":
            for a, b, mask in ((0, 1, x < xp[0]), (-2, -1, x > xp[-1])):
                slope = (yp[b] - yp[a]) / (xp[b] - xp[a])
                values = np.where(mask, yp[a] + slope * (x - xp[a]), values)
        return values

    def ssb_linear_per_hz(self, offset_hz: FloatArray) -> FloatArray:
        return db_to_linear(self.ssb_db(offset_hz))


@dataclass(frozen=True)
class SingleReturnPhaseNoise:
    """Shared source plus optional independent residual at the RF frequency.

    ``delay_s`` sets the nominal beat delay. ``differential_delay_s`` modifies
    only the shared-noise cancellation delay, e.g. for a calibrated hardware
    path imbalance. A negative effective delay is valid for LO-path excess.
    ``independent`` is the *sum* of independent TX/RX contributions, each added
    once; it does not undergo delay cancellation. Either spectrum may be absent.
    """

    delay_s: float
    shared: PhaseNoiseSpectrum | None = None
    independent: PhaseNoiseSpectrum | None = None
    differential_delay_s: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.delay_s) or self.delay_s < 0:
            raise ValueError("delay_s must be finite and non-negative")
        if not math.isfinite(self.differential_delay_s):
            raise ValueError("differential_delay_s must be finite")

    @classmethod
    def from_range(
        cls,
        range_m: float,
        *,
        shared: PhaseNoiseSpectrum | None = None,
        independent: PhaseNoiseSpectrum | None = None,
        differential_delay_s: float = 0.0,
    ) -> SingleReturnPhaseNoise:
        return cls(
            2 * range_m / SPEED_OF_LIGHT, shared, independent, differential_delay_s
        )

    @property
    def range_m(self) -> float:
        return self.delay_s * SPEED_OF_LIGHT / 2

    def cancellation(self, offset_hz: npt.ArrayLike) -> FloatArray:
        """Shared-source power transfer; signed offsets and zero are allowed."""
        f = np.asarray(offset_hz, dtype=float)
        if not np.all(np.isfinite(f)):
            raise ValueError("offsets must be finite")
        return np.asarray(
            4 * np.sin(np.pi * f * (self.delay_s + self.differential_delay_s)) ** 2
        )

    def residual_psd_per_hz(self, offset_hz: npt.ArrayLike) -> FloatArray:
        """Two-sided skirt/carrier density [1/Hz] at nonzero signed offsets."""
        f = np.abs(np.asarray(offset_hz, dtype=float))
        if not np.all(np.isfinite(f)) or np.any(f == 0):
            raise ValueError("PSD offsets must be finite and nonzero")
        out: FloatArray = np.zeros_like(f)
        if self.shared is not None:
            out += self.cancellation(f) * self.shared.ssb_linear_per_hz(f)
        if self.independent is not None:
            out += self.independent.ssb_linear_per_hz(f)
        if not np.all(np.isfinite(out)) or np.any(out < 0):
            raise ValueError("phase-noise spectrum must be finite and non-negative")
        return out

    def residual_variance_rad2(
        self,
        offset_band_hz: tuple[float, float],
        *,
        points_per_decade: int = 400,
        max_points: int = 10_000_000,
    ) -> float:
        """Residual phase variance [rad²] over both signs of the offset band.

        The first-order model needs this to be much less than one. Trapezoidal
        integration on a logarithmic grid, refined to 32 points per period of
        the delay transfer's ripple.
        """
        low, high = offset_band_hz
        if not (math.isfinite(low) and math.isfinite(high) and 0 < low < high):
            raise ValueError("offset_band_hz must be finite with 0 < low < high")
        _positive_int(points_per_decade, "points_per_decade")
        log_points = math.ceil(points_per_decade * math.log10(high / low)) + 1
        delay = abs(self.delay_s + self.differential_delay_s)
        ripple_points = (
            math.ceil(32 * delay * (high - low)) + 1 if self.shared is not None else 0
        )
        if log_points + ripple_points > max_points:
            raise ValueError(
                f"need {log_points + ripple_points} integration points; "
                "increase max_points or narrow the band"
            )
        grid = np.geomspace(low, high, log_points)
        if ripple_points > 1:
            grid = np.union1d(grid, np.linspace(low, high, ripple_points))
        return float(2 * np.trapezoid(self.residual_psd_per_hz(grid), grid))


@dataclass(frozen=True)
class PhaseNoiseResult:
    """Expected FFT power relative to a unit, bin-centered complex carrier.

    With ``real_phase_averaged`` sampling each conjugate lobe is such a unit
    carrier, so a bin-centered return away from DC still peaks near unit power.
    Arrays have shape (Doppler, range); a range-only result has one row.
    ``*_dbc`` properties instead reference the largest deterministic carrier
    bin, accounting for windowing and straddle. Add the measured peak level to
    these dBc values to obtain noise/leakage levels in the same measurement
    units. The measurement must use the same processing and target position.
    ``residual_variance_rad2`` is the model's residual phase variance over
    ``offset_band_hz``; the first-order result needs it to be much less than one.
    """

    range_m: FloatArray
    doppler_hz: FloatArray
    velocity_mps: FloatArray
    phase_noise_power: FloatArray
    carrier_power: FloatArray
    integration_step_hz: float
    offset_band_hz: tuple[float, float]
    sampling: Sampling
    chirp_correlation: ChirpCorrelation
    range_enbw_hz: float
    doppler_enbw_bins: float
    residual_variance_rad2: float

    @property
    def carrier_peak_power(self) -> float:
        return float(np.max(self.carrier_power))

    @property
    def phase_noise_dbc(self) -> FloatArray:
        return linear_to_db(self.phase_noise_power / self.carrier_peak_power)

    @property
    def carrier_dbc(self) -> FloatArray:
        return linear_to_db(self.carrier_power / self.carrier_peak_power)

    @property
    def total_dbc(self) -> FloatArray:
        """Carrier leakage plus phase noise, excluding thermal noise."""
        return linear_to_db(
            (self.carrier_power + self.phase_noise_power) / self.carrier_peak_power
        )


def _window(spec: str | FloatArray, size: int) -> FloatArray:
    w = np.asarray(
        get_window(spec, size, fftbins=True) if isinstance(spec, str) else spec,
        dtype=float,
    )
    if w.shape != (size,) or not np.all(np.isfinite(w)) or np.sum(w) <= 0:
        raise ValueError(
            "window must have the sample count, finite entries and positive sum"
        )
    return w


def _positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def phase_noise_fft(
    model: SingleReturnPhaseNoise,
    waveform: FmcwWaveform,
    *,
    offset_band_hz: tuple[float, float],
    range_doppler: bool = True,
    doppler_hz: float = 0.0,
    range_window: str | FloatArray = "hann",
    doppler_window: str | FloatArray = "hann",
    range_fft_size: int | None = None,
    doppler_fft_size: int | None = None,
    sampling: Sampling = "complex",
    chirp_correlation: ChirpCorrelation = "stationary",
    integration_oversample: int = 4,
    max_integration_points: int = 4_000_000,
) -> PhaseNoiseResult:
    """Expected range or range-Doppler FFT of one weakly phase-modulated tone.

    The signed complex-IF convention is fb = slope * delay + doppler_hz,
    with slow-time phase +2 pi doppler_hz * chirp time. Positive velocity means
    positive Doppler here. Range is apparent beat-derived range, without
    Doppler correction. No range migration, MIMO, CFAR or channel combining.

    Integration bounds are *positive oscillator offsets*, mirrored about the
    carrier and set to zero outside the band. They must be explicit: a result
    is only the contribution of that band. The IF filter is ideal unity in
    [-fs/2, fs/2), zero outside, before sampling. No out-of-band ADC aliasing.
    ``noise_bandwidth_hz`` is not a filter shape and is not used here.

    ``stationary`` preserves noise correlation over chirp gaps. ``independent``
    keeps within-chirp covariance but sets cross-chirp covariance to zero.
    Neither models PLL settling/reset transients. Range-only ignores chirp count.

    ``real_phase_averaged`` includes both conjugate IF lobes and returns only
    nonnegative range frequencies below Nyquist. It averages over an unknown
    reflection carrier phase, dropping cross terms between the lobes; this is
    not an exact fixed-phase real-ADC prediction near DC or overlapping lobes.

    Quadrature resolution is roughly 1/(integration_oversample * CPI span).
    Increase oversampling to check convergence, especially at hard band edges
    or for steep extrapolated spectra. A point limit guards accidental huge
    allocations; it raises rather than silently degrading the resolution.
    """
    ns = waveform.n_samples
    nc = waveform.n_chirps if range_doppler else 1
    for value, name in (
        (ns, "n_samples"),
        (nc, "n_chirps"),
        (integration_oversample, "integration_oversample"),
        (max_integration_points, "max_integration_points"),
    ):
        _positive_int(value, name)
    nr = ns if range_fft_size is None else range_fft_size
    nd = nc if doppler_fft_size is None else doppler_fft_size
    _positive_int(nr, "range_fft_size")
    _positive_int(nd, "doppler_fft_size")
    if nr < ns or nd < nc or (not range_doppler and nd != 1):
        raise ValueError(
            "FFT sizes must cover samples/chirps; range-only Doppler size is 1"
        )
    if sampling not in ("complex", "real_phase_averaged"):
        raise ValueError("invalid sampling mode")
    if chirp_correlation not in ("stationary", "independent"):
        raise ValueError("invalid chirp correlation")
    low, high = offset_band_hz
    if not (math.isfinite(low) and math.isfinite(high) and 0 < low < high):
        raise ValueError("offset_band_hz must be finite with 0 < low < high")
    fs = waveform.sample_rate_hz
    tr = waveform.chirp_repetition_time_s if range_doppler else waveform.adc_duration_s
    if not math.isfinite(tr) or tr < waveform.adc_duration_s:
        raise ValueError("range-Doppler requires chirp repetition time >= ADC duration")
    slope = waveform.effective_slope_hz_per_s
    if not math.isfinite(slope) or slope <= 0:
        raise ValueError("chirp slope must be finite and positive")
    fb = slope * model.delay_s + doppler_hz
    if not math.isfinite(doppler_hz) or not abs(fb) < fs / 2:
        raise ValueError(
            "target beat frequency must lie strictly inside the IF Nyquist band"
        )
    if range_doppler and not abs(doppler_hz) < 1 / (2 * tr):
        raise ValueError(
            "target Doppler must lie strictly inside the unambiguous interval"
        )
    wr = _window(range_window, ns)
    wd = _window(doppler_window, nc) if range_doppler else np.ones(1)
    span = (nc - 1) * tr + ns / fs
    required_points = max(
        2 * ns,
        math.ceil(integration_oversample * fs * span),
        math.ceil(16 * fs / (high - low)),
    )
    # An even grid makes the half-bin shift below symmetric about zero.
    count = 2 * int(next_fast_len((required_points + 1) // 2))
    if count > max_integration_points:
        raise ValueError(
            f"need {count} integration points; increase max_integration_points or reduce CPI/sample rate"
        )
    # Midpoint quadrature treats the two IF band edges symmetrically. The
    # half-grid frequency shift is restored in the covariance below.
    half_step = fs / (2 * count)
    frequencies = np.fft.fftfreq(count, d=1 / fs) + half_step
    offsets = frequencies - fb
    mask = (np.abs(offsets) >= low) & (np.abs(offsets) <= high)
    density = np.zeros(count)
    density[mask] = model.residual_psd_per_hz(offsets[mask])

    # R_IF(t) is the covariance of the positive beat lobe. Correct its
    # slow-time carrier phase from fb*m*Tr to fd*m*Tr after sampling R_IF.
    base_cov = np.fft.ifft(density) * fs
    fast_lags = np.arange(-(ns - 1), ns)
    slow_lags = np.arange(-(nc - 1), nc)
    covariance = np.zeros((2 * nc - 1, 2 * ns - 1), dtype=complex)
    period_samples = tr * fs
    integer_period = abs(period_samples - round(period_samples)) < 1e-9
    for m in range(nc):
        if m > 0 and chirp_correlation == "independent":
            continue
        if m == 0 or integer_period:
            indices = (m * round(period_samples) + fast_lags) % count
            row = base_cov[indices] * np.exp(
                2j * np.pi * half_step * (m * tr + fast_lags / fs)
            )
        else:
            shifted = (
                np.fft.ifft(density * np.exp(2j * np.pi * frequencies * m * tr)) * fs
            )
            row = shifted[fast_lags % count] * np.exp(
                2j * np.pi * half_step * fast_lags / fs
            )
        row = row * np.exp(2j * np.pi * (doppler_hz - fb) * m * tr)
        covariance[nc - 1 + m] = row
        if m > 0:
            covariance[nc - 1 - m] = row[::-1].conj()

    weighted = (
        covariance
        * np.correlate(wd, wd, "full")[:, None]
        * np.correlate(wr, wr, "full")[None, :]
    )
    folded = np.zeros((nd, nr), dtype=complex)
    np.add.at(folded, (slow_lags[:, None] % nd, fast_lags[None, :] % nr), weighted)
    norm = float((wr.sum() * wd.sum()) ** 2)
    noise = np.fft.fft2(folded).real / norm
    tolerance = 1e-10 * max(float(np.max(noise)), np.finfo(float).tiny)
    if np.min(noise) < -tolerance:
        raise ArithmeticError("negative expected power beyond floating-point tolerance")
    noise = np.maximum(noise, 0)
    tone_r = np.fft.fft(wr * np.exp(2j * np.pi * fb * np.arange(ns) / fs), n=nr)
    tone_d = np.fft.fft(wd * np.exp(2j * np.pi * doppler_hz * np.arange(nc) * tr), n=nd)
    carrier = np.abs(tone_d[:, None] * tone_r[None, :]) ** 2 / norm
    if sampling == "real_phase_averaged":
        mirror = np.ix_((-np.arange(nd)) % nd, (-np.arange(nr)) % nr)
        noise = noise + noise[mirror]
        carrier = carrier + carrier[mirror]

    range_f = np.fft.fftshift(np.fft.fftfreq(nr, d=1 / fs))
    doppler_f = np.fft.fftshift(np.fft.fftfreq(nd, d=tr))
    keep = (
        range_f >= 0 if sampling == "real_phase_averaged" else np.ones(nr, dtype=bool)
    )
    return PhaseNoiseResult(
        range_m=range_f[keep] * SPEED_OF_LIGHT / (2 * slope),
        doppler_hz=doppler_f,
        velocity_mps=doppler_f * waveform.wavelength_m / 2,
        phase_noise_power=np.fft.fftshift(noise)[:, keep],
        carrier_power=np.fft.fftshift(carrier)[:, keep],
        integration_step_hz=fs / count,
        offset_band_hz=(low, high),
        sampling=sampling,
        chirp_correlation=chirp_correlation,
        range_enbw_hz=float(fs * np.sum(wr**2) / wr.sum() ** 2),
        doppler_enbw_bins=float(nc * np.sum(wd**2) / wd.sum() ** 2),
        residual_variance_rad2=model.residual_variance_rad2((low, high)),
    )


def _offset_band(offset_band_hz: tuple[float, float]) -> tuple[float, float]:
    low, high = offset_band_hz
    if not (math.isfinite(low) and math.isfinite(high) and 0 < low < high):
        raise ValueError("offset_band_hz must be finite with 0 < low < high")
    return float(low), float(high)


@dataclass(frozen=True)
class _PerChirpDensity:
    """f² L(f) |H(f)|² [Hz²/Hz] at signed offsets, zero outside the band.

    f² is the small-delay limit; with a delay it is the exact
    4 sin²(pi f tau) / (2 pi tau)². H is the payload weighting's normalized
    response, zero beyond the IF Nyquist frequency.
    """

    source: PhaseNoiseSpectrum
    band: tuple[float, float]
    response_hz: FloatArray
    response: FloatArray
    delay_s: float | None

    @classmethod
    def build(
        cls,
        source: PhaseNoiseSpectrum,
        waveform: FmcwWaveform,
        offset_band_hz: tuple[float, float],
        range_window: str | FloatArray,
        range_m: float | None,
    ) -> _PerChirpDensity:
        band = _offset_band(offset_band_hz)
        if range_m is not None and not (math.isfinite(range_m) and range_m > 0):
            raise ValueError("range_m must be finite and positive, or None")
        _positive_int(waveform.n_samples, "n_samples")
        weights = _window(range_window, waveform.n_samples)
        size = max(_RESPONSE_FFT_SIZE, 64 * weights.size)
        response = np.abs(np.fft.rfft(weights, size) / weights.sum()) ** 2
        return cls(
            source=source,
            band=band,
            response_hz=np.asarray(
                np.fft.rfftfreq(size, 1 / waveform.sample_rate_hz), dtype=float
            ),
            response=np.asarray(response, dtype=float),
            delay_s=None if range_m is None else 2 * range_m / SPEED_OF_LIGHT,
        )

    def __call__(self, offset_hz: FloatArray) -> FloatArray:
        f = np.abs(offset_hz)
        inside = (f >= self.band[0]) & (f <= self.band[1])
        out: FloatArray = np.zeros(f.shape)
        g = f[inside]
        if self.delay_s is None:
            transfer = g**2
        else:
            # 4 sin²(pi f tau) / (2 pi tau)²
            transfer = (np.sin(np.pi * g * self.delay_s) / (np.pi * self.delay_s)) ** 2
        out[inside] = (
            transfer
            * self.source.ssb_linear_per_hz(g)
            * np.interp(g, self.response_hz, self.response, right=0.0)
        )
        return out


def _prf_hz(waveform: FmcwWaveform) -> float:
    period = waveform.chirp_repetition_time_s
    if not (math.isfinite(period) and period >= waveform.adc_duration_s):
        raise ValueError("need a chirp repetition time >= the ADC duration")
    return 1 / period


def chirp_frequency_error_psd(
    source: PhaseNoiseSpectrum,
    waveform: FmcwWaveform,
    slow_time_hz: npt.ArrayLike,
    *,
    offset_band_hz: tuple[float, float],
    range_window: str | FloatArray = "hann",
    range_m: float | None = None,
) -> FloatArray:
    """Two-sided PSD [Hz²/Hz] of the per-chirp frequency error over slow time.

    ``source`` is the LO's phase noise, shared by TX and RX. A return at delay
    tau carries phi(t) - phi(t - tau); for small f tau this is 2 pi tau times
    the LO's instantaneous frequency error, whose PSD is f² L(f). At its peak
    range bin the range FFT keeps the ``range_window``-weighted mean of that
    over the sampled payload, which multiplies the PSD by |H(f)|², the
    weighting's normalized response. Sampling once per chirp folds the result
    at the PRF:

        S(f_D) = sum over k of f² L(f) |H(f)|²,  f = f_D + k PRF.

    ``slow_time_hz`` must lie within +-PRF/2. ``range_m=None`` takes the
    small-delay limit, the same for every return. With ``range_m``, f² becomes
    the exact 4 sin²(pi f tau) / (2 pi tau)²: the per-chirp phase PSD at that
    range in frequency units, which falls below the limit once f tau is no
    longer small where |H|² passes. Independent TX/RX residuals follow no
    delay law and are not included. ``offset_band_hz`` bounds the positive
    offsets, as in :func:`phase_noise_fft`; H is taken as zero beyond the IF
    Nyquist frequency. See docs/phase_noise.md.
    """
    density = _PerChirpDensity.build(
        source, waveform, offset_band_hz, range_window, range_m
    )
    prf = _prf_hz(waveform)
    f_d = np.asarray(slow_time_hz, dtype=float)
    if not np.all(np.isfinite(f_d)) or np.any(np.abs(f_d) > prf / 2):
        raise ValueError("slow-time frequencies must lie within +-PRF/2")
    top = min(density.band[1], waveform.sample_rate_hz / 2)
    k_max = math.ceil((top + prf / 2) / prf)
    folds = np.arange(-k_max, k_max + 1)
    out: FloatArray = np.zeros(f_d.shape)
    flat = f_d.reshape(-1, 1)
    for start in range(0, folds.size, _FOLD_BLOCK):
        offsets = flat + prf * folds[None, start : start + _FOLD_BLOCK]
        out += density(offsets).sum(axis=1).reshape(f_d.shape)
    return out


def chirp_frequency_error_rms_hz(
    source: PhaseNoiseSpectrum,
    waveform: FmcwWaveform,
    *,
    offset_band_hz: tuple[float, float],
    range_window: str | FloatArray = "hann",
    range_m: float | None = None,
    slow_time_band_hz: tuple[float, float] | None = None,
) -> float:
    """RMS per-chirp frequency error delta_f [Hz] from the LO's phase noise.

    The value for ``SystemLosses.chirp_frequency_error_rms_hz``: the square
    root of :func:`chirp_frequency_error_psd` integrated over slow time. The
    arguments are the same. Folding keeps the variance, so over the whole
    slow-time band (the default) this is the integral of f² L(f) |H(f)|² over
    all offsets, and the chirp period is not needed. ``slow_time_band_hz=(a,
    b)`` integrates only |f_D| from a to b, within PRF/2, as when comparing
    with a measurement that leaves out slow motion.

    The default ``range_m=None`` gives the small-delay value, which the link
    budget's 2 pi delta_f tau then applies at every range; at long range it
    overstates the CW part (docs/phase_noise.md). The chirp timing can add an
    excess that a CW spectrum does not predict (:class:`ChirpSettling`).
    """
    if slow_time_band_hz is not None:
        a, b = slow_time_band_hz
        prf = _prf_hz(waveform)
        if not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= prf / 2):
            raise ValueError("slow_time_band_hz must satisfy 0 <= a < b <= PRF/2")
        grid = np.linspace(a, b, _SLOW_TIME_POINTS)
        psd = chirp_frequency_error_psd(
            source,
            waveform,
            grid,
            offset_band_hz=offset_band_hz,
            range_window=range_window,
            range_m=range_m,
        )
        return float(np.sqrt(2 * np.trapezoid(psd, grid)))
    density = _PerChirpDensity.build(
        source, waveform, offset_band_hz, range_window, range_m
    )
    low, high = density.band
    top = min(high, waveform.sample_rate_hz / 2)
    if top <= low:
        return 0.0
    # Resolve the window's sidelobes and, with a delay, the transfer's ripple.
    spacing = waveform.sample_rate_hz / (32 * waveform.n_samples)
    if density.delay_s is not None:
        spacing = min(spacing, 1 / (32 * density.delay_s))
    grid = np.union1d(
        np.geomspace(low, top, math.ceil(400 * math.log10(top / low)) + 1),
        np.linspace(low, top, math.ceil((top - low) / spacing) + 1),
    )
    return float(np.sqrt(2 * np.trapezoid(density(grid), grid)))


def ctrx8188f_phase_noise(
    *,
    rf_band: Literal["76-77", "77-81"] = "76-77",
    level: Literal["typical", "maximum"] = "typical",
    extrapolation: Extrapolation = "error",
) -> TabulatedPhaseNoise:
    """CTRX8188F TX-port CW data, revision 0.20, Table 22, pp. 26-27.

    Upper band means strictly above 77 GHz. These are TX output spectra, not
    a measured shared/independent decomposition and not a chirped spectrum.
    Treating the whole table as shared oscillator noise is an assumption.
    Maximum entries are specified points, not a guaranteed interpolated mask.

    On one CARKIT evaluation radar (``studies/2026-09-11_carkit-validation``)
    the assumption held up: a strong return's skirt at 1-12 MHz offset lay
    2.3-3.1 dB below the typical table treated as shared and delay-filtered,
    with both sidebands of the real beat signal counted, and between the
    typical and maximum tables at 0.3-0.5 MHz. The per-chirp frequency error
    matched the typical table when the synthesizer had enough time between
    chirps and grew with less (``docs/losses.md``).
    """
    tables = {
        ("76-77", "typical"): (-79.0, -80.0, -100.0, -116.0, -121.0),
        ("76-77", "maximum"): (-73.0, -75.0, -97.0, -111.0, -115.0),
        ("77-81", "typical"): (-78.0, -78.0, -98.0, -114.0, -120.0),
        ("77-81", "maximum"): (-73.0, -73.0, -95.0, -109.0, -114.0),
    }
    if (rf_band, level) not in tables:
        raise ValueError("invalid RF band or phase-noise level")
    return TabulatedPhaseNoise(
        offset_hz=(1e4, 1e5, 1e6, 5e6, 1e7),
        ssb_dbc_hz=tables[rf_band, level],
        extrapolation=extrapolation,
        name=f"CTRX8188F {rf_band} GHz, {level}, CW",
        source="Infineon CTRX8188F Target Datasheet v0.20, 2025-06-17, Table 22, pp. 26-27",
    )


@dataclass(frozen=True)
class ChirpSettling:
    """Per-chirp frequency error against the time between ramps (empirical).

        delta_f² = floor² + excess² exp(-T_fast / tau_fast - T_pre / tau_pre)

    T_fast is the time the synthesizer spends in fast-settling mode between
    payloads (flyback plus wait) and T_pre the pre-payload, the unsampled
    start of the ramp. The floor is the error with ample time, such as the
    LO's ordinary phase noise gives; the excess is the chirp-to-chirp part of
    a synthesizer that has not settled from the previous ramp. Both depend on
    the sampled payload and its window, so a fit holds for the waveform it
    was measured with. See docs/phase_noise.md.
    """

    floor_hz: float
    excess_hz: float
    fast_settling_time_constant_s: float
    pre_payload_time_constant_s: float
    name: str = "chirp settling"
    source: str = "user supplied"

    def __post_init__(self) -> None:
        for value, label in (
            (self.floor_hz, "floor_hz"),
            (self.excess_hz, "excess_hz"),
            (self.fast_settling_time_constant_s, "fast_settling_time_constant_s"),
            (self.pre_payload_time_constant_s, "pre_payload_time_constant_s"),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{label} must be finite and non-negative")
        if (
            self.fast_settling_time_constant_s == 0
            or self.pre_payload_time_constant_s == 0
        ):
            raise ValueError("time constants must be positive")

    def frequency_error_rms_hz(
        self, *, fast_settling_s: FloatOrArray, pre_payload_s: FloatOrArray
    ) -> FloatOrArray:
        """delta_f rms [Hz] for flyback plus wait and pre-payload [s], broadcast."""
        fast = np.asarray(fast_settling_s, dtype=float)
        pre = np.asarray(pre_payload_s, dtype=float)
        if not (np.all(np.isfinite(fast)) and np.all(np.isfinite(pre))) or (
            np.any(fast < 0) or np.any(pre < 0)
        ):
            raise ValueError("timings must be finite and non-negative")
        decay = np.exp(
            -fast / self.fast_settling_time_constant_s
            - pre / self.pre_payload_time_constant_s
        )
        return cast(FloatOrArray, np.sqrt(self.floor_hz**2 + self.excess_hz**2 * decay))


def ctrx8188f_chirp_settling() -> ChirpSettling:
    """Illustrative: delta_f against chirp timing on one CTRX8188F radar.

    A fit to ten chirp timings on one CARKIT evaluation radar
    (``studies/2026-09-11_carkit-validation``, NOTES.md "Window: the chirp
    timing sets the error"): floor 3.28 kHz, excess 84.8 kHz, time constants
    3.4 us in fast-settling mode and 1.68 us of pre-payload. Measured with
    a 10.24 us sampled ramp at 11.67 MHz/us, a Blackman-Harris range window,
    flyback plus wait 9.2-86 us and pre-payload 0.02-6 us, around 77 GHz;
    the delay law checked to 270 m. Extrapolated to Infineon's 0.12 us of
    flyback and wait it matched that unit's 14-30 kHz within the fit's
    factor-of-1.5 uncertainty. The floor lies between the CW table's typical
    values for the two RF bands (:func:`chirp_frequency_error_rms_hz`). Other
    units, ramps, windows and DPLL settings are untested.
    """
    return ChirpSettling(
        floor_hz=3.285e3,
        excess_hz=84.77e3,
        fast_settling_time_constant_s=3.435e-6,
        pre_payload_time_constant_s=1.678e-6,
        name="CTRX8188F chirp settling, one CARKIT unit",
        source="studies/2026-09-11_carkit-validation, window timing test 2026-10-06",
    )
