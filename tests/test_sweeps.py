"""Vectorised engine / sweep behaviour.

The engine broadcasts over an array :class:`Geometry`; these tests pin the
vectorised path to the per-point :meth:`Radar.link_budget` result so the two can
never drift apart.
"""

from __future__ import annotations

import numpy as np
import pytest

from radarperf import (
    Antenna,
    AntennaPair,
    ConstantGainAntenna,
    FmcwWaveform,
    GaussianBeamAntenna,
    Geometry,
    MimoScheme,
    PatternCutAntenna,
    PatternUVAntenna,
    Radar,
    Rain,
    StandardProcessing,
    frontend,
    target,
)
from radarperf.sweeps import map_2d, range_azimuth_geometry, range_sweep


def make_radar(mimo: MimoScheme = MimoScheme.DDM) -> Radar:
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
        antenna=AntennaPair.from_element(ant),
    )


def test_geometry_is_scalar() -> None:
    assert Geometry(range_m=100.0).is_scalar
    assert Geometry(range_m=100.0, azimuth_deg=5.0).is_scalar
    assert not Geometry(range_m=np.array([50.0, 100.0])).is_scalar
    assert not Geometry(range_m=100.0, azimuth_deg=np.array([0.0, 5.0])).is_scalar


def test_link_budget_rejects_array_geometry() -> None:
    radar = make_radar()
    with pytest.raises(ValueError, match="single-point"):
        radar.link_budget(target.car(), Geometry(range_m=np.array([50.0, 100.0])))


def test_range_sweep_matches_pointwise() -> None:
    radar = make_radar()
    tgt = target.car()
    ranges = np.linspace(10.0, 250.0, 9)
    sweep = range_sweep(radar, tgt, ranges)
    for i, rng in enumerate(ranges):
        geom = Geometry(range_m=float(rng))
        budget = radar.link_budget(tgt, geom)
        assert np.isclose(sweep.snr_db[i], budget.snr_db, atol=1e-9)
        assert np.isclose(sweep.sinr_db[i], budget.sinr_db, atol=1e-9)
        assert np.isclose(
            sweep.pd[i], radar.probability_of_detection(tgt, geom), atol=1e-9
        )


def test_range_sweep_with_clutter_matches_pointwise() -> None:
    # Exercises the vectorised clutter (np.where) branch against the scalar one.
    radar = make_radar()
    tgt = target.pedestrian()
    rain = Rain(rain_rate_mm_per_hr=25.0)
    ranges = np.linspace(10.0, 120.0, 7)
    sweep = range_sweep(radar, tgt, ranges, environment=rain)
    for i, rng in enumerate(ranges):
        budget = radar.link_budget(tgt, Geometry(range_m=float(rng)), rain)
        assert np.isclose(sweep.snr_db[i], budget.snr_db, atol=1e-9)
        assert np.isclose(sweep.sinr_db[i], budget.sinr_db, atol=1e-9)


def test_map_2d_matches_pointwise() -> None:
    radar = make_radar()
    tgt = target.car()
    ranges = np.linspace(20.0, 200.0, 4)
    azimuths = np.linspace(-25.0, 25.0, 5)
    grid = map_2d(radar, tgt, ranges, azimuths, range_azimuth_geometry())
    for i, rng in enumerate(ranges):
        for j, az in enumerate(azimuths):
            geom = Geometry(range_m=float(rng), azimuth_deg=float(az))
            budget = radar.link_budget(tgt, geom)
            assert np.isclose(grid.sinr_db[i, j], budget.sinr_db, atol=1e-9)
            assert np.isclose(
                grid.pd[i, j],
                radar.probability_of_detection(tgt, geom),
                atol=1e-9,
            )


def test_antenna_gain_vectorised_matches_scalar() -> None:
    az = np.linspace(-40.0, 40.0, 11)
    antennas: list[Antenna] = [
        ConstantGainAntenna(boresight_gain_dbi=10.0),
        GaussianBeamAntenna(12.0, 60.0, 12.0),
        PatternCutAntenna.from_cuts(
            15.0,
            az_cut=[(-30.0, -12.0), (0.0, 0.0), (30.0, -12.0)],
            el_cut=[(-10.0, -8.0), (0.0, 0.0), (10.0, -8.0)],
        ),
        PatternUVAntenna(
            azimuth_grid_deg=np.array([-45.0, 0.0, 45.0]),
            elevation_grid_deg=np.array([-15.0, 0.0, 15.0]),
            gain_grid_dbi=np.array(
                [[0.0, 5.0, 0.0], [6.0, 14.0, 6.0], [0.0, 5.0, 0.0]]
            ),
        ),
    ]
    for antenna in antennas:
        vectorised = np.broadcast_to(np.asarray(antenna.gain_dbi(az, 2.0)), az.shape)
        pointwise = np.array([antenna.gain_dbi(float(a), 2.0) for a in az])
        assert np.allclose(vectorised, pointwise, atol=1e-9)
