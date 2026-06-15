"""Target radar cross-section models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from radar_range.types import ArrayLikeFloat, FloatArray, as_float_array
from radar_range.units import dbsm_to_square_meters


class TargetModel(Protocol):
    """Protocol implemented by target/RCS models."""

    def rcs_sqm(
        self,
        azimuth_rad: ArrayLikeFloat = 0.0,
        elevation_rad: ArrayLikeFloat = 0.0,
    ) -> FloatArray:
        """Return radar cross section in square meters."""


@dataclass(frozen=True)
class PointTarget:
    """Point target with direction-independent RCS."""

    rcs_square_meters: float
    name: str = "point target"
    radial_velocity_m_per_s: float = 0.0

    def __post_init__(self) -> None:
        if self.rcs_square_meters < 0.0:
            raise ValueError("rcs_square_meters must be non-negative")

    @classmethod
    def from_dbsm(cls, rcs_dbsm: float, name: str = "point target") -> "PointTarget":
        """Create a point target from a dBsm value."""

        return cls(float(dbsm_to_square_meters(rcs_dbsm)), name=name)

    def rcs_sqm(
        self,
        azimuth_rad: ArrayLikeFloat = 0.0,
        elevation_rad: ArrayLikeFloat = 0.0,
    ) -> FloatArray:
        azimuth = as_float_array(azimuth_rad)
        elevation = as_float_array(elevation_rad)
        shape = np.broadcast_shapes(azimuth.shape, elevation.shape)
        return np.full(shape, self.rcs_square_meters, dtype=float)


@dataclass(frozen=True)
class AzimuthRcsTable:
    """Aspect-dependent RCS from an azimuth cut.

    ``rcs_dbsm`` is interpolated in dBsm versus azimuth angle in degrees. Values
    outside the table are filled with ``fill_dbsm``.
    """

    azimuth_deg: Sequence[float]
    rcs_dbsm: Sequence[float]
    name: str = "azimuth RCS table"
    fill_dbsm: float = -100.0

    def __post_init__(self) -> None:
        azimuth = np.asarray(self.azimuth_deg, dtype=float)
        rcs = np.asarray(self.rcs_dbsm, dtype=float)
        if azimuth.ndim != 1 or rcs.ndim != 1:
            raise ValueError("azimuth_deg and rcs_dbsm must be one-dimensional")
        if azimuth.size != rcs.size:
            raise ValueError("azimuth_deg and rcs_dbsm must have the same length")
        if azimuth.size < 2:
            raise ValueError("RCS table must contain at least two samples")
        if np.any(np.diff(azimuth) <= 0.0):
            raise ValueError("azimuth_deg must be strictly increasing")

    def rcs_sqm(
        self,
        azimuth_rad: ArrayLikeFloat = 0.0,
        elevation_rad: ArrayLikeFloat = 0.0,
    ) -> FloatArray:
        azimuth = as_float_array(azimuth_rad)
        elevation = as_float_array(elevation_rad)
        azimuth, _ = np.broadcast_arrays(azimuth, elevation)
        rcs_dbsm = np.interp(
            np.rad2deg(azimuth),
            np.asarray(self.azimuth_deg, dtype=float),
            np.asarray(self.rcs_dbsm, dtype=float),
            left=self.fill_dbsm,
            right=self.fill_dbsm,
        )
        return dbsm_to_square_meters(rcs_dbsm)


def nominal_car_target() -> PointTarget:
    """Illustrative 10 dBsm car target.

    This is a placeholder for early trade studies; use measured/aspect-specific
    RCS models for sign-off calculations.
    """

    return PointTarget.from_dbsm(10.0, name="nominal car, 10 dBsm")


def nominal_pedestrian_target() -> PointTarget:
    """Illustrative 0 dBsm pedestrian target.

    This is a placeholder for early trade studies; use measured/aspect-specific
    RCS models for sign-off calculations.
    """

    return PointTarget.from_dbsm(0.0, name="nominal pedestrian, 0 dBsm")
