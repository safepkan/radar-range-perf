"""Physical limits, FFT normalization and independent spectral integration."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from radarperf import FmcwWaveform
from radarperf.phase_noise import (
    SingleReturnPhaseNoise,
    TabulatedPhaseNoise,
    ctrx8188f_phase_noise,
    phase_noise_fft,
)
from radarperf.units import SPEED_OF_LIGHT


def waveform(
    *, samples: int = 16, chirps: int = 4, period: float = 24e-6
) -> FmcwWaveform:
    return FmcwWaveform.from_slope(77e9, 1e12, 1e6, samples, chirps, period)


def white(level_db: float = -100) -> TabulatedPhaseNoise:
    return TabulatedPhaseNoise((1e-6, 2e6), (level_db, level_db))


def test_table_interpolation_and_extrapolation() -> None:
    spectrum = TabulatedPhaseNoise((1e3, 1e5), (-60, -100))
    assert spectrum.ssb_db([1e3, 1e4, 1e5]) == pytest.approx([-60, -80, -100])
    with pytest.raises(ValueError, match="outside"):
        spectrum.ssb_db([10])
    assert replace(spectrum, extrapolation="constant").ssb_db(
        [10, 1e8]
    ) == pytest.approx([-60, -100])
    assert replace(spectrum, extrapolation="slope").ssb_db([10, 1e8]) == pytest.approx(
        [-20, -160]
    )
    assert spectrum.ssb_db(1e4).shape == ()
    with pytest.raises(ValueError):
        spectrum.ssb_db(0)
    with pytest.raises(ValueError):
        TabulatedPhaseNoise((100, 10), (-100, -100))


def test_infineon_presets() -> None:
    for band, level, expected in (
        ("76-77", "typical", [-79, -80, -100, -116, -121]),
        ("76-77", "maximum", [-73, -75, -97, -111, -115]),
        ("77-81", "typical", [-78, -78, -98, -114, -120]),
        ("77-81", "maximum", [-73, -73, -95, -109, -114]),
    ):
        spectrum = ctrx8188f_phase_noise(rf_band=band, level=level)  # type: ignore[arg-type]
        assert spectrum.ssb_db([1e4, 1e5, 1e6, 5e6, 1e7]) == pytest.approx(expected)
        assert "Table 22" in spectrum.source


def test_delay_cancellation_and_independent_residual() -> None:
    model = SingleReturnPhaseNoise.from_range(2.3, shared=white())
    assert model.delay_s == pytest.approx(4.6 / SPEED_OF_LIGHT)
    assert model.range_m == pytest.approx(2.3)
    offsets = np.array([-1e6, 1e6])
    assert model.residual_psd_per_hz(offsets) == pytest.approx(
        [9.287476e-13] * 2, rel=1e-5
    )
    zero = replace(model, delay_s=0)
    assert zero.residual_psd_per_hz(offsets) == pytest.approx([0, 0])
    assert replace(zero, independent=white()).residual_psd_per_hz(
        offsets
    ) == pytest.approx([1e-10, 1e-10])
    assert replace(model, differential_delay_s=-model.delay_s).cancellation(
        offsets
    ) == pytest.approx([0, 0])
    assert model.cancellation(1 / (2 * model.delay_s)) == pytest.approx(4)
    assert model.cancellation(1 / model.delay_s) == pytest.approx(0, abs=1e-28)
    small = model.cancellation(np.array([100, 200]))
    assert small[1] / small[0] == pytest.approx(4, rel=1e-8)


@pytest.mark.parametrize("window,enbw", [("boxcar", 1.0), ("hann", 1.5)])
def test_white_noise_fft_gain_and_peak_scaling(window: str, enbw: float) -> None:
    wf = waveform()
    # Off-grid carrier avoids a quadrature node at the excluded DC offset.
    model = SingleReturnPhaseNoise(delay_s=0.173123e-6, independent=white())
    result = phase_noise_fft(
        model,
        wf,
        offset_band_hz=(1e-6, 2e6),
        range_window=window,
        doppler_window=window,
    )
    expected = 1e-10 * wf.sample_rate_hz * enbw**2 / (wf.n_samples * wf.n_chirps)
    assert result.phase_noise_power == pytest.approx(
        np.full((4, 16), expected), rel=1e-10
    )
    assert np.max(result.carrier_dbc) == pytest.approx(0)
    assert result.carrier_peak_power < 1  # actual off-bin peak, not ideal 0 dBc carrier
    stronger = phase_noise_fft(
        replace(model, independent=white(-90)),
        wf,
        offset_band_hz=(1e-6, 2e6),
        range_window=window,
        doppler_window=window,
    )
    assert stronger.phase_noise_dbc - result.phase_noise_dbc == pytest.approx(
        np.full((4, 16), 10.0)
    )
    assert result.range_enbw_hz == pytest.approx(
        wf.sample_rate_hz / wf.n_samples * enbw
    )
    assert result.doppler_enbw_bins == pytest.approx(enbw)


def test_zero_padding_does_not_change_bin_power_or_integration_gain() -> None:
    wf = waveform()
    model = SingleReturnPhaseNoise(0.125e-6, independent=white())
    base = phase_noise_fft(
        model,
        wf,
        offset_band_hz=(1, 2e6),
        range_window="boxcar",
        doppler_window="boxcar",
    )
    padded = phase_noise_fft(
        model,
        wf,
        offset_band_hz=(1, 2e6),
        range_window="boxcar",
        doppler_window="boxcar",
        range_fft_size=32,
        doppler_fft_size=8,
    )
    assert base.carrier_peak_power == pytest.approx(1)
    assert padded.phase_noise_power[::2, ::2] == pytest.approx(base.phase_noise_power)
    assert padded.carrier_power[::2, ::2] == pytest.approx(base.carrier_power)


@pytest.mark.parametrize("period", [12e-6, 12.375e-6])
def test_expected_map_matches_direct_spectral_integration(period: float) -> None:
    """Independent frequency-mode propagation checks arbitrary chirp timing."""
    wf = waveform(samples=8, chirps=3, period=period)
    model = SingleReturnPhaseNoise(
        0.17123e-6, shared=white(-70), independent=white(-110)
    )
    band = (1e3, 350e3)
    wr = np.array([0.1, 0.3, 0.6, 0.9, 1, 0.8, 0.4, 0.2])
    wd = np.array([0.5, 1, 0.8])
    fd = 4000.0
    result = phase_noise_fft(
        model,
        wf,
        offset_band_hz=band,
        doppler_hz=fd,
        range_window=wr,
        doppler_window=wd,
        range_fft_size=11,
        doppler_fft_size=5,
    )
    count = round(wf.sample_rate_hz / result.integration_step_hz)
    fi = np.fft.fftfreq(count, d=1 / wf.sample_rate_hz) + result.integration_step_hz / 2
    fb = wf.effective_slope_hz_per_s * model.delay_s + fd
    t_fast = np.arange(8) / wf.sample_rate_hz
    t_slow = np.arange(3) * period
    t = t_slow[:, None] + t_fast[None, :]
    carrier = np.exp(2j * np.pi * (fb * t_fast[None, :] + fd * t_slow[:, None]))
    expected = np.zeros((5, 11))
    for freq in fi:
        offset = freq - fb
        if not band[0] <= abs(offset) <= band[1]:
            continue
        mode = carrier * np.exp(2j * np.pi * offset * t)
        response = np.fft.fft2(mode * wd[:, None] * wr[None, :], s=(5, 11)) / (
            wr.sum() * wd.sum()
        )
        expected += (
            np.abs(response) ** 2
            * float(model.residual_psd_per_hz(offset))
            * result.integration_step_hz
        )
    assert result.phase_noise_power == pytest.approx(
        np.fft.fftshift(expected), rel=1e-10, abs=1e-20
    )


def test_stationary_noise_preserves_chirp_correlation() -> None:
    wf = waveform(samples=16, chirps=8, period=24e-6)
    model = SingleReturnPhaseNoise(0.125e-6, independent=white(-80))
    opts = dict(
        offset_band_hz=(10.0, 400.0),
        integration_oversample=64,
        range_window="boxcar",
        doppler_window="boxcar",
    )
    stationary = phase_noise_fft(model, wf, **opts)  # type: ignore[arg-type]
    independent = phase_noise_fft(model, wf, chirp_correlation="independent", **opts)  # type: ignore[arg-type]
    # Independent chirps have a flat Doppler noise profile. Stationary close-in
    # noise stays near target Doppler; chirp averaging is not a blanket 1/N.
    assert np.ptp(independent.phase_noise_power, axis=0) == pytest.approx(
        np.zeros(16), abs=1e-20
    )
    col = int(np.argmax(stationary.carrier_power[4]))
    assert (
        stationary.phase_noise_power[4, col] > 5 * independent.phase_noise_power[4, col]
    )


def test_range_only_and_real_adc_mirror() -> None:
    wf = waveform()
    model = SingleReturnPhaseNoise(0.173123e-6, independent=white())
    complex_result = phase_noise_fft(
        model, wf, offset_band_hz=(1e-6, 2e6), range_doppler=False
    )
    real_result = phase_noise_fft(
        model,
        wf,
        offset_band_hz=(1e-6, 2e6),
        range_doppler=False,
        sampling="real_phase_averaged",
    )
    assert real_result.phase_noise_power.shape == (1, 8)
    # For white noise both carrier lobes contribute equally to the real ADC.
    assert real_result.phase_noise_power == pytest.approx(
        2 * complex_result.phase_noise_power[:, 8:]
    )
    assert np.all(real_result.range_m >= 0)
    assert real_result.doppler_hz == pytest.approx([0])
    longer = phase_noise_fft(
        model,
        replace(wf, n_chirps=80, chirp_repetition_time_s=float("nan")),
        offset_band_hz=(1e-6, 2e6),
        range_doppler=False,
    )
    assert longer.phase_noise_power == pytest.approx(complex_result.phase_noise_power)


def test_bin_centers_and_doppler_range_coupling() -> None:
    wf = waveform()
    fd = 1 / (wf.n_chirps * wf.chirp_repetition_time_s)
    fb = 3 * wf.sample_rate_hz / wf.n_samples
    model = SingleReturnPhaseNoise((fb - fd) / wf.effective_slope_hz_per_s)
    result = phase_noise_fft(
        model,
        wf,
        offset_band_hz=(1, 1e6),
        doppler_hz=fd,
        range_window="boxcar",
        doppler_window="boxcar",
    )
    row, col = np.unravel_index(
        np.argmax(result.carrier_power), result.carrier_power.shape
    )
    assert result.carrier_power[row, col] == pytest.approx(1)
    assert result.range_m[col] == pytest.approx(
        fb * SPEED_OF_LIGHT / (2 * wf.effective_slope_hz_per_s)
    )
    assert result.doppler_hz[row] == pytest.approx(fd)
    assert result.velocity_mps[row] == pytest.approx(fd * wf.wavelength_m / 2)
    assert np.all(np.isneginf(result.phase_noise_dbc))


def test_real_adc_matches_phase_averaged_real_signal() -> None:
    """Propagate real sinusoid phase perturbations, not a mirrored FFT model."""
    wf = waveform(samples=16, chirps=3, period=32e-6)
    fd = 1 / (3 * 32e-6)
    fb = 125e3
    model = SingleReturnPhaseNoise((fb - fd) / 1e12, independent=white(-90))
    band = (1e4, 6e4)  # both lobes and their sidebands are inside the IF band
    result = phase_noise_fft(
        model,
        wf,
        offset_band_hz=band,
        doppler_hz=fd,
        range_window="boxcar",
        doppler_window="boxcar",
        sampling="real_phase_averaged",
    )
    nf = round(wf.sample_rate_hz / result.integration_step_hz)
    offsets = np.fft.fftfreq(nf, d=1e-6) + result.integration_step_hz / 2 - fb
    fast = np.arange(16) * 1e-6
    slow = np.arange(3) * 32e-6
    times = slow[:, None] + fast[None, :]
    theta = 2 * np.pi * (fd * slow[:, None] + fb * fast[None, :])
    expected = np.zeros((3, 16))
    carrier = np.zeros_like(expected)
    # Two quadrature carrier phases give the exact uniform-phase mean for
    # second-order powers, including cancellation of lobe cross terms.
    for alpha in (0.0, np.pi / 2):
        carrier += 0.5 * abs(np.fft.fft2(2 * np.cos(theta + alpha)) / 48) ** 2
        for offset in offsets:
            if not band[0] <= abs(offset) <= band[1]:
                continue
            perturbation = (
                -2 * np.sin(theta + alpha) * np.exp(2j * np.pi * offset * times)
            )
            response = np.fft.fft2(perturbation) / 48
            expected += 0.5 * abs(response) ** 2 * 1e-9 * result.integration_step_hz
    assert result.phase_noise_power == pytest.approx(
        np.fft.fftshift(expected)[:, 8:], rel=1e-10, abs=1e-20
    )
    assert result.carrier_power == pytest.approx(
        np.fft.fftshift(carrier)[:, 8:], abs=1e-14
    )


def test_integration_grid_is_even_and_symmetric() -> None:
    # This timing would yield an odd fast FFT length without enforcing parity.
    wf = waveform(samples=10, chirps=4, period=12.3e-6)
    result = phase_noise_fft(
        SingleReturnPhaseNoise(0, independent=white()), wf, offset_band_hz=(1e-6, 2e6)
    )
    assert round(wf.sample_rate_hz / result.integration_step_hz) % 2 == 0


def test_quadrature_convergence() -> None:
    wf = waveform(samples=24, chirps=5, period=35.25e-6)
    model = SingleReturnPhaseNoise.from_range(
        2.3, shared=ctrx8188f_phase_noise(extrapolation="constant")
    )
    coarse = phase_noise_fft(
        model, wf, offset_band_hz=(1, 2e6), integration_oversample=8
    )
    fine = phase_noise_fft(
        model, wf, offset_band_hz=(1, 2e6), integration_oversample=16
    )
    assert coarse.phase_noise_power == pytest.approx(fine.phase_noise_power, rel=0.005)


def test_invalid_inputs() -> None:
    wf = waveform()
    model = SingleReturnPhaseNoise(0, shared=ctrx8188f_phase_noise())
    with pytest.raises(ValueError, match="outside"):
        phase_noise_fft(model, wf, offset_band_hz=(1, 1e6))
    for low, high in [(0, 1e6), (-1, 10), (20, 10), (1, float("inf"))]:
        with pytest.raises(ValueError, match="offset_band"):
            phase_noise_fft(model, wf, offset_band_hz=(low, high))
    with pytest.raises(ValueError, match="repetition"):
        phase_noise_fft(
            model, replace(wf, chirp_repetition_time_s=1e-6), offset_band_hz=(1e4, 1e6)
        )
    with pytest.raises(ValueError, match="integration points"):
        phase_noise_fft(model, wf, offset_band_hz=(1e4, 1e6), max_integration_points=10)
    with pytest.raises(ValueError, match="FFT sizes"):
        phase_noise_fft(model, wf, offset_band_hz=(1e4, 1e6), range_fft_size=2)
    with pytest.raises(ValueError, match="window"):
        phase_noise_fft(model, wf, offset_band_hz=(1e4, 1e6), range_window=np.zeros(16))
    with pytest.raises(ValueError, match="Nyquist"):
        phase_noise_fft(SingleReturnPhaseNoise(1), wf, offset_band_hz=(1e4, 1e6))


def test_plotting_helpers() -> None:
    import matplotlib.pyplot as plt
    from radarperf.plotting import (
        plot_phase_noise_cut,
        plot_phase_noise_map,
        plot_phase_noise_spectrum,
    )

    model = SingleReturnPhaseNoise.from_range(
        2.3, shared=ctrx8188f_phase_noise(extrapolation="constant")
    )
    result = phase_noise_fft(model, waveform(), offset_band_hz=(1, 1e6))
    ax = plot_phase_noise_spectrum(model, np.geomspace(1e4, 1e7, 50))
    assert len(ax.lines) == 2
    ax = plot_phase_noise_cut(result)
    assert len(ax.lines) == 3
    assert plot_phase_noise_cut(result, axis="doppler", at=2.3, ax=ax) is ax
    ax = plot_phase_noise_map(result, colorbar=False)
    assert len(ax.collections) == 1
    plt.close("all")
