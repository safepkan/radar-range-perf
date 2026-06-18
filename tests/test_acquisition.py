"""Trajectory kinematics and the multi-scan acquisition sweep.

The acquisition sweep evaluates a trajectory over scan times in one vectorised
pass; these tests pin it to the per-point :meth:`Radar.probability_of_detection`
and to the detection-module primitives it builds on.
"""

from __future__ import annotations

import numpy as np
import pytest

from radarperf import (
    AntennaPair,
    FmcwWaveform,
    GaussianBeamAntenna,
    MimoScheme,
    Radar,
    RadialApproach,
    StandardProcessing,
    Trajectory,
    frontend,
    target,
)
from radarperf.detection import cumulative_pd, probability_of_acquisition_mofn
from radarperf.sweeps import acquisition_sweep


def make_radar(*, with_crt: bool = True) -> Radar:
    wf = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6 if with_crt else float("nan"),
    )
    ant = GaussianBeamAntenna(
        boresight_gain_dbi=12.0, beamwidth_az_deg=60.0, beamwidth_el_deg=12.0
    )
    return Radar(
        frontend=frontend.awr2243(),
        waveform=wf,
        processing=StandardProcessing(mimo=MimoScheme.DDM),
        antenna=AntennaPair.from_element(ant),
    )


def test_radial_approach_satisfies_trajectory_protocol() -> None:
    assert isinstance(RadialApproach(100.0, 5.0), Trajectory)


def test_radial_approach_geometry_scalar_and_array() -> None:
    approach = RadialApproach(initial_range_m=100.0, closing_speed_mps=5.0)

    scalar = approach.geometry_at(2.0)
    assert scalar.is_scalar
    assert scalar.range_m == pytest.approx(90.0)
    assert scalar.radial_velocity_mps == pytest.approx(-5.0)  # closing -> negative

    batch = approach.geometry_at(np.array([0.0, 1.0, 2.0]))
    assert not batch.is_scalar
    assert np.allclose(np.asarray(batch.range_m), [100.0, 95.0, 90.0])


def test_radial_approach_rejects_nonpositive_initial_range() -> None:
    with pytest.raises(ValueError, match="initial_range_m"):
        RadialApproach(initial_range_m=0.0, closing_speed_mps=1.0)


def test_acquisition_sweep_matches_pointwise() -> None:
    radar = make_radar()
    tgt = target.pedestrian()
    approach = RadialApproach(initial_range_m=200.0, closing_speed_mps=4.0)
    acq = acquisition_sweep(
        radar, tgt, approach, frame_time_s=1.0, n_scans=10, confirm=(2, 3)
    )

    assert acq.range_m.shape == (10,)
    for i, t in enumerate(acq.time_s):
        geom = approach.geometry_at(float(t))
        assert acq.range_m[i] == pytest.approx(float(geom.range_m))
        assert acq.pd[i] == pytest.approx(
            radar.probability_of_detection(tgt, geom), abs=1e-9
        )


def test_acquisition_sweep_cumulative_and_confirmation_consistent() -> None:
    radar = make_radar()
    approach = RadialApproach(initial_range_m=150.0, closing_speed_mps=4.0)
    acq = acquisition_sweep(
        radar,
        target.pedestrian(),
        approach,
        frame_time_s=1.0,
        n_scans=20,
        confirm=(2, 3),
    )
    assert np.allclose(acq.cumulative_pd, cumulative_pd(acq.pd))
    assert acq.confirmation_pd is not None
    assert np.allclose(
        acq.confirmation_pd, probability_of_acquisition_mofn(acq.pd, m=2, n=3)
    )


def test_acquisition_sweep_no_confirm_leaves_field_none() -> None:
    radar = make_radar()
    approach = RadialApproach(initial_range_m=120.0, closing_speed_mps=4.0)
    acq = acquisition_sweep(radar, target.car(), approach, frame_time_s=1.0, n_scans=5)
    assert acq.confirmation_pd is None


def test_acquisition_frame_time_defaults_to_cpi_duration() -> None:
    radar = make_radar()
    approach = RadialApproach(initial_range_m=120.0, closing_speed_mps=4.0)
    acq = acquisition_sweep(radar, target.car(), approach, n_scans=3)
    cpi = radar.waveform.cpi_duration_s
    assert np.allclose(acq.time_s, np.arange(3) * cpi)


def test_acquisition_requires_a_frame_time_without_crt() -> None:
    radar = make_radar(with_crt=False)
    approach = RadialApproach(initial_range_m=120.0, closing_speed_mps=4.0)
    with pytest.raises(ValueError, match="frame_time_s must be positive"):
        acquisition_sweep(radar, target.car(), approach, n_scans=3)


def test_acquisition_auto_scan_count_stops_at_min_range() -> None:
    radar = make_radar()
    approach = RadialApproach(initial_range_m=200.0, closing_speed_mps=4.0)
    acq = acquisition_sweep(
        radar, target.car(), approach, frame_time_s=1.0, min_range_m=10.0
    )
    # 200, 196, ..., 12 (next step would be 8 < 10).
    assert acq.range_m[0] == pytest.approx(200.0)
    assert acq.range_m[-1] == pytest.approx(12.0)
    assert np.all(acq.range_m >= 10.0)


def test_acquisition_duration_sets_scan_count() -> None:
    radar = make_radar()
    approach = RadialApproach(initial_range_m=200.0, closing_speed_mps=4.0)
    acq = acquisition_sweep(
        radar, target.car(), approach, frame_time_s=1.0, duration_s=5.0
    )
    # Scans at 0, 1, 2, 3, 4, 5 s.
    assert acq.time_s.shape == (6,)
    assert acq.time_s[-1] == pytest.approx(5.0)


def test_acquisition_auto_rejects_non_closing_target() -> None:
    radar = make_radar()
    receding = RadialApproach(initial_range_m=100.0, closing_speed_mps=-1.0)
    with pytest.raises(ValueError, match="closing trajectory"):
        acquisition_sweep(radar, target.car(), receding, frame_time_s=1.0)


def test_acquisition_rejects_bad_scan_count() -> None:
    radar = make_radar()
    approach = RadialApproach(initial_range_m=100.0, closing_speed_mps=4.0)
    with pytest.raises(ValueError, match="n_scans"):
        acquisition_sweep(radar, target.car(), approach, frame_time_s=1.0, n_scans=0)
