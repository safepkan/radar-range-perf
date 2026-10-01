"""Synthetic checks of the shared estimators and the outdoor normalizations."""

from __future__ import annotations

import numpy as np

from carkit_common import (
    ComplexArray,
    FloatArray,
    away_from_lines,
    chirp_fluctuations,
    chirp_gains,
    cross_channel_cross,
    cross_channel_power,
    detrend,
    enbw_bins,
    linear_rate,
    tone_model_errors,
    weighted_cross_power,
)
from outdoor_common import (
    FAR_DOPPLER_HZ,
    doppler_window,
    range_spectrum,
    range_window,
    slow_time_spectrum,
)

N_CHIRPS, N_SAMPLES, N_RX = 1024, 512, 8
SAMPLE_RATE_HZ = 50e6
CHIRP_PERIOD_S = 15.96e-6
FAR = np.abs(np.fft.fftfreq(N_CHIRPS, CHIRP_PERIOD_S)) > FAR_DOPPLER_HZ
# Doppler Hann window: a white sequence's power per bin is variance * ENBW / N.
PER_BIN = enbw_bins(doppler_window(N_CHIRPS)) / N_CHIRPS
WINDOW = range_window(N_SAMPLES)


def returns(
    rng: np.random.Generator,
    beat_bins: tuple[int, ...],
    phase: FloatArray,
    noise_std: float,
    amplitude: float = 500.0,
) -> FloatArray:
    """Real ADC data [chirp, sample, RX]: one cosine per return plus noise.

    ``phase`` is [chirp, return] and common to all RX; each RX and return gets
    its own fixed carrier phase.
    """
    time = np.arange(N_SAMPLES)
    x = rng.normal(0, noise_std, size=(N_CHIRPS, N_SAMPLES, N_RX))
    for k, beat_bin in enumerate(beat_bins):
        carrier = rng.uniform(0, 2 * np.pi, size=N_RX)
        x += amplitude * np.cos(
            2 * np.pi * beat_bin * time[None, :, None] / N_SAMPLES
            + carrier[None, None, :]
            + phase[:, k, None, None]
        )
    return x


def test_range_doppler_noise_normalization() -> None:
    rng = np.random.default_rng(1)
    noise_std, frames = 10.0, 8
    measured = 0.0
    for _ in range(frames):
        x = rng.normal(0, noise_std, size=(N_CHIRPS, N_SAMPLES, 1))
        rd = slow_time_spectrum(range_spectrum(x))
        measured += float(np.mean(np.abs(rd[:, 20:230]) ** 2)) / frames
    expected = noise_std**2 * enbw_bins(range_window(N_SAMPLES)) / N_SAMPLES * PER_BIN
    assert abs(measured / expected - 1) < 0.03


def test_common_phase_rejects_independent_noise() -> None:
    rng = np.random.default_rng(2)
    phase_std, frames = 0.005, 6
    measured = 0.0
    for _ in range(frames):
        phase = rng.normal(0, phase_std, size=(N_CHIRPS, 1))
        x = returns(rng, (23,), phase, noise_std=10.0)
        gains = chirp_gains(
            x, np.array([23 * SAMPLE_RATE_HZ / N_SAMPLES]), SAMPLE_RATE_HZ, WINDOW
        )
        spectrum = slow_time_spectrum(detrend(np.unwrap(np.angle(gains), axis=0)))
        measured += float(np.mean(cross_channel_power(spectrum)[FAR, 0])) / frames
    assert abs(measured / (phase_std**2 * PER_BIN) - 1) < 0.06


def cross_return(shared: bool) -> tuple[FloatArray, float]:
    """Delta_f rms at two returns and their correlation, as outdoor_phase.py."""
    rng = np.random.default_rng(3)
    beat_bins = (23, 97)
    delays = np.array([40e-9, 200e-9])
    beat_hz = np.array(beat_bins) * SAMPLE_RATE_HZ / N_SAMPLES
    df_std, frames = 20e3, 6
    common = np.zeros(2)
    cross = 0.0
    for _ in range(frames):
        df = rng.normal(0, df_std, size=(N_CHIRPS, 2))
        if shared:
            df[:, 1] = df[:, 0]
        x = returns(rng, beat_bins, 2 * np.pi * delays * df, noise_std=10.0)
        phase = np.unwrap(
            np.angle(chirp_gains(x, beat_hz, SAMPLE_RATE_HZ, WINDOW)), axis=0
        )
        spectrum = slow_time_spectrum(detrend(phase)) / (
            2 * np.pi * delays[None, :, None]
        )
        common += cross_channel_power(spectrum)[FAR].sum(axis=0)
        cross += float(cross_channel_cross(spectrum[:, :1], spectrum[:, 1:])[FAR].sum())
    rms = np.sqrt(common / (FAR.sum() * PER_BIN * frames))
    return rms / df_std, cross / np.sqrt(common[0] * common[1])


def test_cross_return_correlation_of_shared_frequency_error() -> None:
    rms_ratio, correlation = cross_return(shared=True)
    assert np.all(np.abs(rms_ratio - 1) < 0.05)
    assert abs(correlation - 1) < 0.05


def test_cross_return_correlation_of_independent_errors() -> None:
    rms_ratio, correlation = cross_return(shared=False)
    assert np.all(np.abs(rms_ratio - 1) < 0.05)
    assert abs(correlation) < 0.1


def test_chirp_fluctuations_follow_a_moving_return_without_unwrapping() -> None:
    """A static and an 11 kHz Doppler return share one delta_f at 8.5 dB SNR."""
    rng = np.random.default_rng(4)
    beat_bins = (23, 97)
    delays = np.array([600e-9, 1.5e-6])
    doppler_hz = np.array([0.0, 11e3])
    beat_hz = np.array(beat_bins) * SAMPLE_RATE_HZ / N_SAMPLES
    chirp_time = np.arange(N_CHIRPS) * CHIRP_PERIOD_S
    df_std, frames = 20e3, 4
    common = np.zeros(2)
    cross = 0.0
    for _ in range(frames):
        df = rng.normal(0, df_std, size=N_CHIRPS)
        phase = 2 * np.pi * (np.outer(df, delays) + np.outer(chirp_time, doppler_hz))
        x = returns(rng, beat_bins, phase, noise_std=1500.0)
        gains = chirp_gains(x, beat_hz, SAMPLE_RATE_HZ, WINDOW)
        fluctuation, _ = chirp_fluctuations(gains, doppler_hz, CHIRP_PERIOD_S)
        spectrum = slow_time_spectrum(fluctuation) / (2 * np.pi * delays[None, :, None])
        common += cross_channel_power(spectrum)[FAR].sum(axis=0)
        cross += float(cross_channel_cross(spectrum[:, :1], spectrum[:, 1:])[FAR].sum())
    rms = np.sqrt(common / (FAR.sum() * PER_BIN * frames))
    assert np.all(np.abs(rms / df_std - 1) < 0.1)
    assert abs(cross / common[0] - 1) < 0.1


def test_detrend_and_linear_rate() -> None:
    t = np.linspace(-1, 1, N_CHIRPS)
    ripple = 1e-3 * np.sin(2 * np.pi * 100 * t)
    values = np.stack((0.3 + 2 * t - t**2 + 0.5 * t**3 + ripple, 4 * t), axis=1)
    assert np.allclose(detrend(values)[:, 0], detrend(ripple[:, None])[:, 0])
    assert np.allclose(detrend(values)[:, 1], 0)
    step = 2 / (N_CHIRPS - 1)
    assert np.allclose(linear_rate(values[:, 1:], step), 4)


def line_gains(
    rng: np.random.Generator,
    lines: FloatArray,
    phase: FloatArray,
    noise_std: float,
) -> ComplexArray:
    """Per-chirp gains [chirp, return, RX]: each return a sum of slow-time lines.

    ``lines`` is [return, line] in cycles per chirp; every line of a return gets
    its own random amplitude and phase per RX, as transmitters seen at one angle
    through different paths would. ``phase`` [chirp, return] multiplies all
    lines of a return alike.
    """
    chirps = np.arange(N_CHIRPS)
    n_returns, n_lines = lines.shape
    amplitudes = rng.normal(size=(n_returns, n_lines, N_RX)) + 1j * rng.normal(
        size=(n_returns, n_lines, N_RX)
    )
    tones = np.exp(2j * np.pi * chirps[:, None, None] * lines[None, :, :])
    clean = (
        np.einsum("cil,ilr->cir", tones, amplitudes) * np.exp(1j * phase)[:, :, None]
    )
    noise = rng.normal(0, noise_std, clean.shape) + 1j * rng.normal(
        0, noise_std, clean.shape
    )
    return np.asarray(clean + noise / np.sqrt(2))


def test_tone_model_errors_match_chirp_fluctuations_for_one_line() -> None:
    rng = np.random.default_rng(5)
    phase = rng.normal(0, 0.01, size=(N_CHIRPS, 1))
    gains = line_gains(rng, np.zeros((1, 1)), phase, noise_std=0.01)
    errors, weights, _ = tone_model_errors(gains, np.zeros((1, 1)))
    fluctuation, _ = chirp_fluctuations(gains, np.zeros(1), CHIRP_PERIOD_S)
    power = np.abs(gains.mean(axis=0)) ** 2
    expected = np.sum(fluctuation * power, axis=-1) / power.sum(axis=-1)
    assert np.allclose(weights, 1, atol=0.01)
    assert np.corrcoef(errors[:, 0].imag, expected[:, 0])[0, 1] > 0.999
    assert np.corrcoef(errors[:, 0].imag, detrend(phase)[:, 0])[0, 1] > 0.9


def ddma_cross(shared: bool) -> tuple[float, float]:
    """Cross-return delta_f power over its variance, and one return's own.

    Two returns under 8-slot-of-16 DDMA with a range skew, as the Infineon
    firmware's; additive noise 20 dB below each line.
    """
    rng = np.random.default_rng(6)
    slots = np.array([2, 5, 8, 11, 12, 13, 14, 15]) / 16
    delays = np.array([300e-9, 1.1e-6])
    lines = (slots[None, :] + np.array([0.09, 0.33])[:, None]) % 1
    df_std, frames = 20e3, 6
    window = doppler_window(N_CHIRPS)
    doppler = np.fft.fftfreq(N_CHIRPS, CHIRP_PERIOD_S)
    outside_low = np.abs(doppler) >= 500
    band = outside_low & away_from_lines(N_CHIRPS, 16, 4)
    kept = band.sum() / outside_low.sum()
    cross = own = 0.0
    for _ in range(frames):
        df = rng.normal(0, df_std, size=(N_CHIRPS, 2))
        if shared:
            df[:, 1] = df[:, 0]
        gains = line_gains(rng, lines, 2 * np.pi * delays * df, noise_std=0.1)
        errors, weights, _ = tone_model_errors(gains, lines)
        power = weighted_cross_power(
            errors.imag / (2 * np.pi * delays), weights, band, window
        ) / (kept * outside_low.mean())
        cross += power[0, 1] / frames
        own += power[1, 1] / frames
    return cross / df_std**2, own / df_std**2


def test_ddma_cross_return_power_of_a_shared_frequency_error() -> None:
    cross, own = ddma_cross(shared=True)
    assert abs(cross - 1) < 0.1
    assert abs(own - 1) < 0.1


def test_ddma_cross_return_power_of_independent_errors() -> None:
    cross, own = ddma_cross(shared=False)
    assert abs(cross) < 0.1
    assert abs(own - 1) < 0.1


def test_away_from_lines() -> None:
    keep = away_from_lines(1024, 16, 4)
    assert keep.sum() == 1024 - 16 * 9
    assert not keep[0] and not keep[64] and keep[5] and not keep[4]
