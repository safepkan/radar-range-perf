from __future__ import annotations

import numpy as np

from radar_range.antennas import (
    ConstantGainAntenna,
    SeparablePatternAntenna,
    UvGridPatternAntenna,
)


def test_constant_gain_broadcasts() -> None:
    antenna = ConstantGainAntenna(12.0)
    gain = antenna.gain_db(np.asarray([0.0, 0.1]), 0.0)
    np.testing.assert_allclose(gain, [12.0, 12.0])


def test_separable_pattern_boresight() -> None:
    antenna = SeparablePatternAntenna(
        max_gain_dbi=15.0,
        azimuth_deg=[-10.0, 0.0, 10.0],
        azimuth_relative_gain_db=[-3.0, 0.0, -3.0],
        elevation_deg=[-10.0, 0.0, 10.0],
        elevation_relative_gain_db=[-3.0, 0.0, -3.0],
    )
    np.testing.assert_allclose(antenna.gain_db(0.0, 0.0), 15.0)


def test_uv_grid_interpolates_center() -> None:
    antenna = UvGridPatternAntenna(
        u_axis=[-1.0, 0.0, 1.0],
        v_axis=[-1.0, 0.0, 1.0],
        gain_dbi_grid=[[-10.0, -5.0, -10.0], [-5.0, 0.0, -5.0], [-10.0, -5.0, -10.0]],
    )
    np.testing.assert_allclose(antenna.gain_db(0.0, 0.0), 0.0)
