"""Synthetic checks of the chamber estimators."""

from __future__ import annotations

import numpy as np
from scipy.signal import get_window

from carkit_common import SPEED_OF_LIGHT
from chamber_common import (
    TX_POSITION_M,
    background_split,
    cell_to_density,
    coherent_rx_gain_db,
    delay_fit,
    fit_high_pass_corner,
    gradient_to_angle_deg,
    high_pass_db,
    pair_power_db,
    per_tx_amplitudes,
    plane_wave_fit,
    real_tone_skirt,
    rx_positions_m,
    signature_alignment,
    trihedral_factor,
)
from field_common import RX_X_M, near_field_loss_db
from radarperf.phase_noise import SingleReturnPhaseNoise, TabulatedPhaseNoise


def test_per_tx_amplitudes_with_the_firmware_sign() -> None:
    """A TX's shifter phase shows negated in the range bin, so TX t's return
    advances by -step_t per chirp; demodulating recovers each TX x RX product."""
    rng = np.random.default_rng(1)
    n_chirps = 256
    steps = np.arange(8, dtype=np.float64) * 45.0
    tx = rng.normal(size=8) + 1j * rng.normal(size=8)
    rx = rng.normal(size=8) + 1j * rng.normal(size=8)
    n = np.arange(n_chirps)
    codes = np.exp(-1j * np.radians(steps)[:, None] * n[None, :])  # [TX, chirp]
    gains = codes.T @ (tx[:, None] * rx[None, :])  # [chirp, RX]
    gains += 0.01 * (rng.normal(size=gains.shape) + 1j * rng.normal(size=gains.shape))
    found = per_tx_amplitudes(gains, steps)
    np.testing.assert_allclose(found, tx[:, None] * rx[None, :], atol=0.005)
    # With the opposite sign, TX2..TX8 come out mirrored: TX2 <-> TX8 etc.
    mirrored = per_tx_amplitudes(gains, -steps)
    np.testing.assert_allclose(mirrored[1], found[7], atol=1e-9)


def test_background_split_of_independent_noise_plus_a_rank_one_part() -> None:
    signature = np.exp(1j * np.linspace(0, 3, 8))
    covariance = np.asarray(
        2.0 * np.eye(8) + 0.5 * np.outer(signature, signature.conj()),
        dtype=np.complex128,
    )
    parts = background_split(covariance[None])
    np.testing.assert_allclose(parts["total"], [2.5])
    np.testing.assert_allclose(parts["independent"], [2.0])
    np.testing.assert_allclose(parts["common"], [0.5])
    np.testing.assert_allclose(signature_alignment(covariance, signature), 1.0)


def test_coherent_rx_gain_against_independent_and_common_backgrounds() -> None:
    """10 log10(8) against independent noise; 0 dB against a background with
    the return's own signature; 8 (1 + c) / (1 + 8 c) in between, with c the
    common part per RX relative to the independent noise."""
    signature = 3.0 * np.exp(1j * np.linspace(0, 5, 8))
    unit = signature / np.abs(signature)
    common = np.outer(unit, unit.conj())
    identity = np.eye(8, dtype=np.complex128)
    assert (
        abs(float(coherent_rx_gain_db(identity, signature)) - 10 * np.log10(8)) < 1e-9
    )
    assert abs(float(coherent_rx_gain_db(common + 1e-9 * identity, signature))) < 1e-6
    c = 0.55
    expected = 10 * np.log10(8 * (1 + c) / (1 + 8 * c))
    assert (
        abs(float(coherent_rx_gain_db(identity + c * common, signature)) - expected)
        < 1e-9
    )


def test_high_pass_corner_is_its_minus_6_db_point_and_is_recovered() -> None:
    assert abs(float(high_pass_db(300e3, 300e3)) + 20 * np.log10(2)) < 1e-12
    frequency = np.array([0.29e6, 0.58e6, 1.2e6])
    reference = 2.5e6
    response = high_pass_db(frequency, 265e3) - high_pass_db(reference, 265e3)
    corner, rms = fit_high_pass_corner(frequency, response, reference)
    assert abs(corner / 265e3 - 1) < 1e-4 and rms < 1e-6


def test_real_tone_skirt_adds_both_sidebands() -> None:
    """Far from the carrier both complex tones' sidebands land at the same IF:
    twice one sideband for a flat spectrum."""
    flat = TabulatedPhaseNoise(
        offset_hz=(1e3, 1e8), ssb_dbc_hz=(-120.0, -120.0), extrapolation="constant"
    )
    single = SingleReturnPhaseNoise(delay_s=0.0, independent=flat)
    skirt = real_tone_skirt(single, 180e3, [5e6])
    np.testing.assert_allclose(skirt, 2 * 1e-12, rtol=1e-9)


def test_cell_to_density_of_white_noise() -> None:
    rng = np.random.default_rng(2)
    n_chirps, n_samples, fs, sigma = 64, 256, 25e6, 3.0
    wr = np.asarray(get_window("blackmanharris", n_samples))
    wd = np.asarray(get_window("blackmanharris", n_chirps))
    x = rng.normal(0, sigma, (40, n_chirps, n_samples))
    spectrum = np.fft.rfft(x * wr, axis=2) / wr.sum()
    cells = np.fft.fft(spectrum * wd[:, None], axis=1) / wd.sum()
    power = np.mean(np.abs(cells[:, :, 10:100]) ** 2)
    density = cell_to_density(power, n_samples, n_chirps, fs, wr, wd)
    assert abs(10 * np.log10(density / (2 * sigma**2 / fs))) < 0.05


def test_delay_fit_recovers_path_delays_through_wrapping() -> None:
    frequency = 76.55e9 + 112.5e6 * (np.arange(8, dtype=np.float64) + 0.5)
    delays = np.array([0.0, 60e-12, -190e-12, 1e-9])
    phase = -360 * np.outer(frequency, delays)  # received RF phase [deg]
    found, residual = delay_fit((phase + 180) % 360 - 180, frequency)
    np.testing.assert_allclose(found - found[0], delays, atol=1e-15)
    assert np.all(residual < 1e-6)


def test_plane_wave_fit_recovers_an_angle_change() -> None:
    """A reflector moved by 0.5 deg in azimuth and 2 deg in elevation, seen by
    the FARAD-IV TX positions, with per-element offsets that cancel in the
    difference of two calibrations."""
    wavelength = SPEED_OF_LIGHT / 77e9
    gradient = 360 / wavelength * np.sin(np.radians([0.5, 2.0]))
    offsets = np.random.default_rng(3).uniform(-180, 180, 8)
    before = offsets
    after = offsets + TX_POSITION_M @ gradient
    found, residual = plane_wave_fit((after - before + 180) % 360 - 180, TX_POSITION_M)
    assert abs(gradient_to_angle_deg(found[0], wavelength) - 0.5) < 1e-6
    assert abs(gradient_to_angle_deg(found[1], wavelength) - 2.0) < 1e-6
    assert np.all(np.abs(residual) < 1e-6)
    rx_found, _ = plane_wave_fit(RX_X_M * gradient[0], RX_X_M[:, None])
    assert abs(gradient_to_angle_deg(rx_found[0], wavelength) - 0.5) < 1e-6


def test_trihedral_factor_on_axis_is_the_near_field_loss() -> None:
    """At zero baseline |F|^2 is the on-axis near-field loss, which
    field_common.near_field_loss_db gives for a disk of the same area; the
    hexagon differs from it by about 0.01 dB at the lab distance."""
    wavelength = SPEED_OF_LIGHT / 77e9
    for range_m in (2.22, 16.0):
        found = -20 * np.log10(
            abs(trihedral_factor(0.0778, range_m, [0.0, 0.0], wavelength))
        )
        assert (
            abs(found - float(near_field_loss_db(0.0778, range_m, wavelength))) < 0.02
        )


def test_trihedral_factor_reproduces_the_l2sp_carkit_taper() -> None:
    """l2-sp pa_260916_antenna_centers.md, finite-aperture model: across all 64
    CARKIT TX-RX pairs at 2.3 m, 77 GHz, the aperture inferred from 10 dBsm at
    76.5 GHz, the predicted amplitude spread is 3.261 dB."""
    rated = SPEED_OF_LIGHT / 76.5e9
    area = np.sqrt(10.0 * rated**2 / (4 * np.pi))
    edge = float(np.sqrt(np.sqrt(3) * area))
    pairs = pair_power_db(
        edge, 2.3, TX_POSITION_M, rx_positions_m(), SPEED_OF_LIGHT / 77e9
    )
    assert abs(float(pairs.max() - pairs.min()) - 3.261) < 0.01


def test_trihedral_factor_falls_off_the_returned_beam() -> None:
    wavelength = SPEED_OF_LIGHT / 77e9
    offsets = np.array([[0.0, d] for d in (0.0, 0.01, 0.02, 0.03)])
    power = np.abs(trihedral_factor(0.0778, 2.2, offsets, wavelength)) ** 2
    assert np.all(np.diff(power) < 0)
    mirrored = trihedral_factor(0.0778, 2.2, [0.0, -0.02], wavelength)
    assert (
        abs(abs(mirrored) - abs(trihedral_factor(0.0778, 2.2, [0.0, 0.02], wavelength)))
        < 1e-9
    )
