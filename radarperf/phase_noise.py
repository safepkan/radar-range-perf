"""Single-return phase-noise diagnostics, independent of the link-budget engine.

SSB input L(f) is in dBc/Hz. In the small-phase approximation, its linear
value is also the *two-sided* phase PSD at either signed offset: do not add
another factor of two per sideband. Shared-source noise is multiplied by
4 sin²(pi f delay); independent TX/RX residual contributions add in power.

FFT predictions integrate a band-limited stationary process over the actual
sample times, including chirp gaps. They return expected power, not a random
realization. See docs/phase_noise.md for normalization and model boundaries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
import numpy.typing as npt
from scipy.fft import next_fast_len
from scipy.signal import get_window

from .units import SPEED_OF_LIGHT, db_to_linear, linear_to_db
from .waveform import FmcwWaveform

FloatArray = npt.NDArray[np.float64]
Extrapolation = Literal["error", "constant", "slope"]
Sampling = Literal["complex", "real_phase_averaged"]
ChirpCorrelation = Literal["stationary", "independent"]


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


@dataclass(frozen=True)
class PhaseNoiseResult:
    """Expected FFT power relative to a unit, bin-centered complex carrier.

    Arrays have shape (Doppler, range); a range-only result has one row.
    ``*_dbc`` properties instead reference the largest deterministic carrier
    bin, accounting for windowing and straddle. Add the measured peak level to
    these dBc values to obtain noise/leakage levels in the same measurement
    units. The measurement must use the same processing and target position.
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
    )
