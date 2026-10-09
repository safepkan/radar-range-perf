"""Synthetic checks of the field estimators."""

from __future__ import annotations

import numpy as np

from carkit_common import SPEED_OF_LIGHT, interference_flags
from field_common import (
    CALIBRATION_RX_PHASE_DEG,
    RX_X_M,
    azimuth_deg,
    find_peak,
    matching_samples,
    near_field_loss_db,
    static_samples,
    trihedral_aim_loss_db,
)

SAMPLE_RATE_HZ = 50e6
N_SAMPLES, N_CHIRPS = 512, 64
# The field captures' frequency plans (sidecars of medium-20m and short-20m).
MEDIUM_START_HZ, MEDIUM_BANDWIDTH_HZ = 76940235900.8789, 119531250.0
SHORT_START_HZ, SHORT_BANDWIDTH_HZ = 76879884338.3789, 240234375.0


def test_matching_samples_of_the_field_waveforms() -> None:
    selected = matching_samples(
        SHORT_START_HZ,
        SHORT_BANDWIDTH_HZ,
        N_SAMPLES,
        MEDIUM_START_HZ,
        MEDIUM_BANDWIDTH_HZ,
    )
    assert (selected.start, selected.stop) == (129, 384)
    step = SHORT_BANDWIDTH_HZ / N_SAMPLES
    assert abs(SHORT_START_HZ + selected.start * step - MEDIUM_START_HZ) < step


def chirps(rng: np.random.Generator, beat_hz: float, amplitude: float) -> np.ndarray:
    """Static real tone with per-RX phases plus white noise, [chirp, sample, RX]."""
    n = np.arange(N_SAMPLES)
    phases = rng.uniform(0, 2 * np.pi, 8)
    tone = amplitude * np.cos(
        2 * np.pi * beat_hz * n[:, None] / SAMPLE_RATE_HZ + phases
    )
    noise = rng.normal(0, 3.0, (N_CHIRPS, N_SAMPLES, 8))
    return np.asarray(tone[None] + noise + 50.0)  # with an ADC offset


def test_two_slope_ratio_recovers_the_if_response() -> None:
    """A tone at 2f in the short ramp's sub-band against f in the medium ramp:
    the zero-Doppler power ratio is the IF gain ratio, whatever the window
    length (256 against 512 samples)."""
    rng = np.random.default_rng(3)
    range_m = 16.0
    medium_slope = MEDIUM_BANDWIDTH_HZ / (N_SAMPLES / SAMPLE_RATE_HZ)
    short_slope = SHORT_BANDWIDTH_HZ / (N_SAMPLES / SAMPLE_RATE_HZ)
    f_medium = 2 * medium_slope * range_m / SPEED_OF_LIGHT
    f_short = 2 * short_slope * range_m / SPEED_OF_LIGHT
    gain_ratio_db = -0.4
    medium = chirps(rng, f_medium, 200.0)
    short = chirps(rng, f_short, 200.0 * 10 ** (gain_ratio_db / 20))
    sub = matching_samples(
        SHORT_START_HZ,
        SHORT_BANDWIDTH_HZ,
        N_SAMPLES,
        MEDIUM_START_HZ,
        MEDIUM_BANDWIDTH_HZ,
    )
    found_m, a_m = find_peak(static_samples(medium), SAMPLE_RATE_HZ, f_medium * 1.002)
    found_s, a_s = find_peak(
        static_samples(short)[sub], SAMPLE_RATE_HZ, f_short * 0.998
    )
    ratio_db = 10 * np.log10(np.mean(np.abs(a_s) ** 2) / np.mean(np.abs(a_m) ** 2))
    assert abs(found_m / f_medium - 1) < 2e-3 and abs(found_s / f_short - 1) < 2e-3
    assert abs(ratio_db - gain_ratio_db) < 0.05


def test_near_field_loss_reproduces_the_lab_distances() -> None:
    """NOTES, Reflector: 0.24 dB for the 77.8 mm chamber reflector at 2.22 m and
    0.51 dB for the 100 mm walking reflector at 2.51 m."""
    wavelength = SPEED_OF_LIGHT / 76.4e9
    assert abs(float(near_field_loss_db(0.0778, 2.22, wavelength)) - 0.24) < 0.015
    assert abs(float(near_field_loss_db(0.100, 2.51, wavelength)) - 0.51) < 0.015
    assert float(near_field_loss_db(0.100, 16.0, wavelength)) < 0.02


def test_trihedral_aim_loss() -> None:
    """NOTES, Reflector: 0.69 and 3.21 dB at 10 and 20 deg (two independent
    geometric-optics computations), and no triple bounce with the radar in a
    plate's plane, arcsin(1/sqrt(3)) = 35.26 deg off the axis."""
    loss = trihedral_aim_loss_db([0.0, 10.0, 20.0])
    np.testing.assert_allclose(loss, [0.0, 0.69, 3.21], atol=0.005)
    assert trihedral_aim_loss_db(np.degrees(np.arcsin(1 / np.sqrt(3)))) > 100
    assert np.isinf(trihedral_aim_loss_db(40.0))


def test_azimuth_of_a_calibrated_plane_wave() -> None:
    wavelength = SPEED_OF_LIGHT / 77e9
    angle = 5.0
    steer = np.exp(2j * np.pi * RX_X_M * np.sin(np.radians(angle)) / wavelength)
    measured = 3.0 * steer * np.exp(-1j * np.radians(CALIBRATION_RX_PHASE_DEG))
    found, coherence = azimuth_deg(measured, wavelength)
    assert abs(found - angle) < 0.05 and coherence > 0.999
    # Without its calibration the same return is not a plane wave.
    _, uncalibrated = azimuth_deg(steer, wavelength)
    assert uncalibrated < 0.9


def test_interference_flags() -> None:
    levels = np.array([-30.0, -30.1, -29.9, -28.5, -30.0, -24.0])
    assert interference_flags(levels).tolist() == [
        False,
        False,
        False,
        True,
        False,
        True,
    ]
