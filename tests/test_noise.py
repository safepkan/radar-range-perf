"""System-temperature noise model.

``T_sys = T_ant + (F - 1) T0`` with a noise bandwidth that defaults to the ADC
sample rate.  The defaults must reproduce the legacy ``k T0 F f_s`` noise power.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from radarperf import (
    AntennaPair,
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    MimoScheme,
    Radar,
    StandardProcessing,
    frontend,
    target,
)
from radarperf.units import BOLTZMANN, REFERENCE_TEMPERATURE, db_to_linear, watt_to_dbm


def make_waveform() -> FmcwWaveform:
    return FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )


def make_radar(waveform: FmcwWaveform | None = None) -> Radar:
    ant = GaussianBeamAntenna(12.0, 60.0, 12.0)
    return Radar(
        frontend=frontend.awr2243(),
        waveform=make_waveform() if waveform is None else waveform,
        processing=StandardProcessing(mimo=MimoScheme.NONE),
        antenna=AntennaPair.from_element(ant),
    )


GEOM = Geometry(range_m=100.0)


def test_defaults_reduce_to_kt0bf_fs() -> None:
    radar = make_radar()
    budget = radar.link_budget(target.car(), GEOM)
    noise_factor = db_to_linear(radar.frontend.noise_figure_db)
    expected_w = (
        BOLTZMANN
        * REFERENCE_TEMPERATURE
        * noise_factor
        * make_waveform().sample_rate_hz
    )
    assert np.isclose(budget.noise_power_dbm, float(watt_to_dbm(expected_w)), atol=1e-9)


def test_effective_noise_bandwidth_property() -> None:
    wf = make_waveform()
    assert wf.effective_noise_bandwidth_hz == wf.sample_rate_hz
    assert replace(wf, noise_bandwidth_hz=5e6).effective_noise_bandwidth_hz == 5e6


def test_negative_noise_bandwidth_rejected() -> None:
    with pytest.raises(ValueError):
        replace(make_waveform(), noise_bandwidth_hz=-1.0)


def test_higher_antenna_temperature_raises_noise_and_lowers_snr() -> None:
    base = make_radar()
    hot = replace(base, antenna_noise_temperature_k=600.0)
    b0 = base.link_budget(target.car(), GEOM)
    b1 = hot.link_budget(target.car(), GEOM)
    assert b1.noise_power_dbm > b0.noise_power_dbm
    # Signal/gain/loss are unchanged, so SNR drops by exactly the noise increase.
    assert np.isclose(
        b0.snr_db - b1.snr_db, b1.noise_power_dbm - b0.noise_power_dbm, atol=1e-9
    )


def test_noise_bandwidth_override_scales_noise() -> None:
    base = make_radar()
    wide = make_radar(replace(make_waveform(), noise_bandwidth_hz=2.0 * 20e6))
    b0 = base.link_budget(target.car(), GEOM)
    b1 = wide.link_budget(target.car(), GEOM)
    expected_delta = 10.0 * np.log10(2.0)
    assert np.isclose(
        b1.noise_power_dbm - b0.noise_power_dbm, expected_delta, atol=1e-9
    )
    assert np.isclose(b0.snr_db - b1.snr_db, expected_delta, atol=1e-9)
