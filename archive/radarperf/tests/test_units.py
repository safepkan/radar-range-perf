"""Tests for unit conversions."""

from __future__ import annotations

import numpy as np

from radarperf import units


def test_db_linear_round_trip() -> None:
    for value in (-20.0, 0.0, 3.0, 13.0, 40.0):
        assert np.isclose(units.linear_to_db(units.db_to_linear(value)), value)


def test_dbm_watt_round_trip() -> None:
    for value in (-30.0, 0.0, 10.0, 12.5):
        assert np.isclose(units.watt_to_dbm(units.dbm_to_watt(value)), value)


def test_known_values() -> None:
    assert np.isclose(units.db_to_linear(10.0), 10.0)
    assert np.isclose(units.db_to_linear(3.0103), 2.0, atol=1e-3)
    assert np.isclose(units.dbm_to_watt(30.0), 1.0)


def test_array_inputs() -> None:
    arr = np.array([0.0, 10.0, 20.0])
    out = units.db_to_linear(arr)
    assert out.shape == arr.shape
    assert np.allclose(out, [1.0, 10.0, 100.0])
