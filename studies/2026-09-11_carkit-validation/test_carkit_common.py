"""Synthetic checks of the shared estimators and the outdoor normalizations."""

from __future__ import annotations

import numpy as np

from carkit_common import (
    FloatArray,
    chirp_gains,
    cross_channel_cross,
    cross_channel_power,
    detrend,
    enbw_bins,
    linear_rate,
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


def test_detrend_and_linear_rate() -> None:
    t = np.linspace(-1, 1, N_CHIRPS)
    ripple = 1e-3 * np.sin(2 * np.pi * 100 * t)
    values = np.stack((0.3 + 2 * t - t**2 + 0.5 * t**3 + ripple, 4 * t), axis=1)
    assert np.allclose(detrend(values)[:, 0], detrend(ripple[:, None])[:, 0])
    assert np.allclose(detrend(values)[:, 1], 0)
    step = 2 / (N_CHIRPS - 1)
    assert np.allclose(linear_rate(values[:, 1:], step), 4)
