"""Antenna gain models.

All antenna models return gain in dBi as a function of azimuth and elevation in
radians. The convention used by this first version is:

* azimuth is positive to the left/right in the horizontal plane;
* elevation is positive upward;
* boresight is azimuth = elevation = 0;
* u = sin(azimuth) cos(elevation), v = sin(elevation).

The models are intentionally small and composable. They can be replaced by more
specific classes fed by measured data, EM-solver exports, or vendor pattern
files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from radar_range.types import ArrayLikeFloat, FloatArray, as_float_array


class AntennaModel(Protocol):
    """Protocol implemented by all antenna models."""

    def gain_db(
        self,
        azimuth_rad: ArrayLikeFloat = 0.0,
        elevation_rad: ArrayLikeFloat = 0.0,
    ) -> FloatArray:
        """Return antenna gain in dBi."""


def _broadcast_angles(
    azimuth_rad: ArrayLikeFloat,
    elevation_rad: ArrayLikeFloat,
) -> tuple[FloatArray, FloatArray]:
    azimuth = as_float_array(azimuth_rad)
    elevation = as_float_array(elevation_rad)
    return np.broadcast_arrays(azimuth, elevation)


@dataclass(frozen=True)
class ConstantGainAntenna:
    """A boresight-only or direction-independent antenna gain model."""

    gain_dbi: float

    def gain_db(
        self,
        azimuth_rad: ArrayLikeFloat = 0.0,
        elevation_rad: ArrayLikeFloat = 0.0,
    ) -> FloatArray:
        azimuth, elevation = _broadcast_angles(azimuth_rad, elevation_rad)
        shape = np.broadcast_shapes(azimuth.shape, elevation.shape)
        return np.full(shape, self.gain_dbi, dtype=float)


@dataclass(frozen=True)
class SeparablePatternAntenna:
    """Approximate pattern with independent azimuth and elevation cuts.

    The relative gain cuts should normally be zero at boresight and non-positive
    away from boresight. The returned gain is

        max_gain_dbi + azimuth_relative_gain_db + elevation_relative_gain_db

    This is a pragmatic interpolation model for datasheet plots. It is not a
    substitute for a measured 2-D pattern when one is available.
    """

    max_gain_dbi: float
    azimuth_deg: Sequence[float]
    azimuth_relative_gain_db: Sequence[float]
    elevation_deg: Sequence[float]
    elevation_relative_gain_db: Sequence[float]
    fill_relative_gain_db: float = -100.0

    def __post_init__(self) -> None:
        _validate_axis_and_values(self.azimuth_deg, self.azimuth_relative_gain_db)
        _validate_axis_and_values(self.elevation_deg, self.elevation_relative_gain_db)

    def gain_db(
        self,
        azimuth_rad: ArrayLikeFloat = 0.0,
        elevation_rad: ArrayLikeFloat = 0.0,
    ) -> FloatArray:
        azimuth, elevation = _broadcast_angles(azimuth_rad, elevation_rad)
        azimuth_deg = np.rad2deg(azimuth)
        elevation_deg = np.rad2deg(elevation)
        azimuth_rel = np.interp(
            azimuth_deg,
            np.asarray(self.azimuth_deg, dtype=float),
            np.asarray(self.azimuth_relative_gain_db, dtype=float),
            left=self.fill_relative_gain_db,
            right=self.fill_relative_gain_db,
        )
        elevation_rel = np.interp(
            elevation_deg,
            np.asarray(self.elevation_deg, dtype=float),
            np.asarray(self.elevation_relative_gain_db, dtype=float),
            left=self.fill_relative_gain_db,
            right=self.fill_relative_gain_db,
        )
        return self.max_gain_dbi + azimuth_rel + elevation_rel


@dataclass(frozen=True)
class UvGridPatternAntenna:
    """Bilinear interpolation of a 2-D gain grid in direction-cosine space.

    Args:
        u_axis: Monotonic u coordinates, where u = sin(az) cos(el).
        v_axis: Monotonic v coordinates, where v = sin(el).
        gain_dbi_grid: Gain grid with shape ``(len(v_axis), len(u_axis))``.
        fill_gain_dbi: Gain used outside the supplied grid.
    """

    u_axis: Sequence[float]
    v_axis: Sequence[float]
    gain_dbi_grid: Sequence[Sequence[float]]
    fill_gain_dbi: float = -100.0

    def __post_init__(self) -> None:
        u_axis = np.asarray(self.u_axis, dtype=float)
        v_axis = np.asarray(self.v_axis, dtype=float)
        grid = np.asarray(self.gain_dbi_grid, dtype=float)
        if u_axis.ndim != 1 or v_axis.ndim != 1:
            raise ValueError("u_axis and v_axis must be one-dimensional")
        if grid.shape != (v_axis.size, u_axis.size):
            raise ValueError("gain_dbi_grid must have shape (len(v_axis), len(u_axis))")
        if np.any(np.diff(u_axis) <= 0.0) or np.any(np.diff(v_axis) <= 0.0):
            raise ValueError("u_axis and v_axis must be strictly increasing")

    def gain_db(
        self,
        azimuth_rad: ArrayLikeFloat = 0.0,
        elevation_rad: ArrayLikeFloat = 0.0,
    ) -> FloatArray:
        azimuth, elevation = _broadcast_angles(azimuth_rad, elevation_rad)
        u_value = np.sin(azimuth) * np.cos(elevation)
        v_value = np.sin(elevation)
        return _interpolate_uv_grid(
            u_value,
            v_value,
            np.asarray(self.u_axis, dtype=float),
            np.asarray(self.v_axis, dtype=float),
            np.asarray(self.gain_dbi_grid, dtype=float),
            self.fill_gain_dbi,
        )


def _validate_axis_and_values(axis: Sequence[float], values: Sequence[float]) -> None:
    axis_array = np.asarray(axis, dtype=float)
    values_array = np.asarray(values, dtype=float)
    if axis_array.ndim != 1 or values_array.ndim != 1:
        raise ValueError("pattern axes and values must be one-dimensional")
    if axis_array.size != values_array.size:
        raise ValueError("pattern axis and value arrays must have the same length")
    if axis_array.size < 2:
        raise ValueError("pattern cuts must contain at least two samples")
    if np.any(np.diff(axis_array) <= 0.0):
        raise ValueError("pattern axes must be strictly increasing")


def _interpolate_uv_grid(
    u_value: FloatArray,
    v_value: FloatArray,
    u_axis: FloatArray,
    v_axis: FloatArray,
    grid: FloatArray,
    fill_gain_dbi: float,
) -> FloatArray:
    result = np.full(u_value.shape, fill_gain_dbi, dtype=float)
    valid = (
        (u_value >= u_axis[0])
        & (u_value <= u_axis[-1])
        & (v_value >= v_axis[0])
        & (v_value <= v_axis[-1])
    )
    if not np.any(valid):
        return result

    flat_u = u_value[valid]
    flat_v = v_value[valid]
    u_index = np.searchsorted(u_axis, flat_u, side="right") - 1
    v_index = np.searchsorted(v_axis, flat_v, side="right") - 1
    u_index = np.clip(u_index, 0, u_axis.size - 2)
    v_index = np.clip(v_index, 0, v_axis.size - 2)

    u0 = u_axis[u_index]
    u1 = u_axis[u_index + 1]
    v0 = v_axis[v_index]
    v1 = v_axis[v_index + 1]
    u_fraction = (flat_u - u0) / (u1 - u0)
    v_fraction = (flat_v - v0) / (v1 - v0)

    q11 = grid[v_index, u_index]
    q21 = grid[v_index, u_index + 1]
    q12 = grid[v_index + 1, u_index]
    q22 = grid[v_index + 1, u_index + 1]
    result[valid] = (
        q11 * (1.0 - u_fraction) * (1.0 - v_fraction)
        + q21 * u_fraction * (1.0 - v_fraction)
        + q12 * (1.0 - u_fraction) * v_fraction
        + q22 * u_fraction * v_fraction
    )
    return result
