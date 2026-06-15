"""Tests for geometry, waveform, engine and environment."""

from __future__ import annotations

import numpy as np
import pytest

from radarperf import (
    Atmosphere,
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    MimoScheme,
    Radar,
    Rain,
    StandardProcessing,
    frontend,
    target,
)
from radarperf.units import SPEED_OF_LIGHT


def make_radar(mimo: MimoScheme = MimoScheme.NONE) -> Radar:
    wf = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )
    ant = GaussianBeamAntenna(
        boresight_gain_dbi=12.0, beamwidth_az_deg=60.0, beamwidth_el_deg=12.0
    )
    return Radar(
        frontend=frontend.awr2243(),
        waveform=wf,
        processing=StandardProcessing(mimo=mimo),
        tx_antenna=ant,
        rx_antenna=ant,
    )


def test_geometry_cartesian_round_trip() -> None:
    geom = Geometry.from_cartesian(100.0, 50.0, 10.0)
    assert np.isclose(geom.range_m, np.sqrt(100.0**2 + 50.0**2 + 10.0**2))
    assert np.isclose(geom.azimuth_deg, np.degrees(np.arctan2(50.0, 100.0)))


def test_geometry_rejects_nonpositive_range() -> None:
    with pytest.raises(ValueError):
        Geometry(range_m=0.0)


def test_waveform_resolutions() -> None:
    wf = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )
    assert np.isclose(wf.range_resolution_m, SPEED_OF_LIGHT / 2e9)
    assert np.isclose(wf.wavelength_m, SPEED_OF_LIGHT / 77e9)
    assert wf.dwell_time_s > 0.0
    assert wf.max_unambiguous_velocity_mps > 0.0


def test_snr_falls_as_r4() -> None:
    radar = make_radar()
    tgt = target.car()
    b1 = radar.link_budget(tgt, Geometry(range_m=50.0))
    b2 = radar.link_budget(tgt, Geometry(range_m=100.0))
    assert np.isclose(b2.snr_db - b1.snr_db, -40.0 * np.log10(2.0), atol=1e-6)


def test_snr_scales_with_rcs() -> None:
    radar = make_radar()
    geom = Geometry(range_m=100.0)
    b1 = radar.link_budget(target.ConstantRcsTarget(rcs=1.0), geom)
    b2 = radar.link_budget(target.ConstantRcsTarget(rcs=10.0), geom)
    assert np.isclose(b2.snr_db - b1.snr_db, 10.0, atol=1e-6)


def test_link_budget_internal_consistency() -> None:
    radar = make_radar()
    b = radar.link_budget(target.car(), Geometry(range_m=120.0))
    reconstructed = (
        b.signal_power_dbm
        - b.noise_power_dbm
        + b.coherent_gain_db
        - b.processing_loss_db
    )
    assert np.isclose(reconstructed, b.snr_db, atol=1e-6)


def test_tdm_matches_none_in_snr() -> None:
    # TDM with n_tx transmitters has the same SNR as single-TX/n_rx (NONE).
    none = make_radar(MimoScheme.NONE)
    tdm = make_radar(MimoScheme.TDM)
    geom = Geometry(range_m=100.0)
    b_none = none.link_budget(target.car(), geom)
    b_tdm = tdm.link_budget(target.car(), geom)
    assert np.isclose(b_none.snr_db, b_tdm.snr_db, atol=1e-9)


def test_ddm_beats_none_by_ntx() -> None:
    none = make_radar(MimoScheme.NONE)
    ddm = make_radar(MimoScheme.DDM)
    n_tx = none.frontend.n_tx
    geom = Geometry(range_m=100.0)
    b_none = none.link_budget(target.car(), geom)
    b_ddm = ddm.link_budget(target.car(), geom)
    assert np.isclose(b_ddm.snr_db - b_none.snr_db, 10.0 * np.log10(n_tx), atol=1e-9)


def test_environment_rain_attenuation() -> None:
    wf = make_radar().waveform
    light = Rain(rain_rate_mm_per_hr=2.0)
    heavy = Rain(rain_rate_mm_per_hr=25.0)
    geom_near = Geometry(range_m=50.0)
    geom_far = Geometry(range_m=200.0)
    assert light.two_way_loss_db(geom_far, wf) > light.two_way_loss_db(geom_near, wf)
    assert heavy.two_way_loss_db(geom_far, wf) > light.two_way_loss_db(geom_far, wf)


def test_environment_free_space_is_lossless() -> None:
    radar = make_radar()
    geom = Geometry(range_m=100.0)
    b = radar.link_budget(target.car(), geom)
    assert b.path_loss_db == 0.0
    assert b.clutter_rcs_m2 == 0.0
    assert np.isinf(b.scr_db)


def test_rain_clutter_positive_and_reduces_sinr() -> None:
    radar = make_radar()
    geom = Geometry(range_m=40.0)
    rain = Rain(rain_rate_mm_per_hr=25.0)
    clear = radar.link_budget(target.pedestrian(), geom)
    wet = radar.link_budget(target.pedestrian(), geom, rain)
    assert wet.clutter_rcs_m2 > 0.0
    assert wet.sinr_db <= clear.sinr_db


def test_atmosphere_two_way_loss() -> None:
    wf = make_radar().waveform
    atmos = Atmosphere(specific_attenuation_db_per_km=0.5)
    geom = Geometry(range_m=1000.0)
    assert np.isclose(atmos.two_way_loss_db(geom, wf), 2.0 * 0.5 * 1.0)


def test_probability_of_detection_decreases_with_range() -> None:
    radar = make_radar()
    tgt = target.car()
    near = radar.probability_of_detection(tgt, Geometry(range_m=50.0))
    far = radar.probability_of_detection(tgt, Geometry(range_m=300.0))
    assert near >= far
    assert 0.0 <= far <= 1.0 and 0.0 <= near <= 1.0
