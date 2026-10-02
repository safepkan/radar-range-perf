"""Checks of the range-curve helpers and beam tests in ``lannik_psi.py``."""

from __future__ import annotations

import numpy as np
import pytest

from lannik_psi import (
    RX_SQUARE_LAYOUT,
    BoresightSinr,
    build_rx_antenna,
    lannik_psi,
    rx_array_factor_periods,
)
from radarperf import (
    FreeSpace,
    MultiBeamUniformArrayAntenna,
    SystemLosses,
    false_alarm_budget,
)


def test_boresight_sinr_inverts_and_follows_r4_in_free_space() -> None:
    product = lannik_psi(losses=SystemLosses(), environment=FreeSpace())
    curve = BoresightSinr.of(product)
    ranges_m = np.array([200.0, 500.0, 1000.0])
    assert curve.range_at(curve.at_range(ranges_m)) == pytest.approx(ranges_m, rel=1e-4)
    assert float(curve.at_range(1000.0)) == pytest.approx(
        float(curve.at_range(500.0)) - 40.0 * np.log10(2.0), abs=1e-3
    )
    assert curve.range_at(np.inf) == 0.0
    assert curve.range_at(-np.inf) == np.inf


def _beams(u: list[float], v: list[float]) -> MultiBeamUniformArrayAntenna:
    array = build_rx_antenna(RX_SQUARE_LAYOUT)
    return MultiBeamUniformArrayAntenna(
        array.element,
        horizontal_count=array.horizontal_count,
        vertical_count=array.vertical_count,
        horizontal_spacing_m=array.horizontal_spacing_m,
        vertical_spacing_m=array.vertical_spacing_m,
        center_frequency_hz=array.center_frequency_hz,
        steering_u=u,
        steering_v=v,
    )


def test_beam_tests_for_one_beam_and_for_orthogonal_beams() -> None:
    pfa_per_cell = 1.0e-6
    # One beam: one test per cell.
    single = false_alarm_budget(
        pfa_per_cell, beam_weights=_beams([0.0], [0.0]).beam_weights()
    )
    assert single.effective_tests == 1.0
    # Eight orthogonal beams (the 2 x 4 DFT grid of one period) are
    # independent tests: P = 1 - (1 - p)**8, so p is about pfa_per_cell / 8.
    period_u, period_v = rx_array_factor_periods(build_rx_antenna(RX_SQUARE_LAYOUT))
    grid_u, grid_v = np.meshgrid(
        np.arange(2) * period_u / 2.0, np.arange(4) * period_v / 4.0, indexing="ij"
    )
    orthogonal = false_alarm_budget(
        pfa_per_cell,
        beam_weights=_beams(list(grid_u.ravel()), list(grid_v.ravel())).beam_weights(),
    )
    assert orthogonal.effective_tests == pytest.approx(8.0, rel=1e-3)
