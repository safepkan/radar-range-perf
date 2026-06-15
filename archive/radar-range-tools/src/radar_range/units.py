"""Unit conversion helpers."""

from __future__ import annotations

import numpy as np

from radar_range.types import ArrayLikeFloat, FloatArray, as_float_array


def db_to_linear(value_db: ArrayLikeFloat) -> FloatArray:
    """Convert dB to a linear power ratio."""

    return np.power(10.0, as_float_array(value_db) / 10.0)


def linear_to_db(
    value_linear: ArrayLikeFloat,
    floor: float | None = None,
) -> FloatArray:
    """Convert a linear power ratio to dB.

    Args:
        value_linear: Linear power ratio.
        floor: Optional minimum linear value before taking the logarithm. This is
            useful for plotting arrays that may contain zeros.
    """

    value = as_float_array(value_linear)
    if floor is not None:
        value = np.maximum(value, floor)
    return 10.0 * np.log10(value)


def dbm_to_w(value_dbm: ArrayLikeFloat) -> FloatArray:
    """Convert dBm to watts."""

    return 1.0e-3 * db_to_linear(value_dbm)


def w_to_dbm(value_w: ArrayLikeFloat, floor: float | None = None) -> FloatArray:
    """Convert watts to dBm."""

    return linear_to_db(as_float_array(value_w) / 1.0e-3, floor=floor)


def dbsm_to_square_meters(value_dbsm: ArrayLikeFloat) -> FloatArray:
    """Convert dBsm to square meters."""

    return db_to_linear(value_dbsm)


def square_meters_to_dbsm(
    value_sqm: ArrayLikeFloat,
    floor: float | None = None,
) -> FloatArray:
    """Convert square meters to dBsm."""

    return linear_to_db(value_sqm, floor=floor)
