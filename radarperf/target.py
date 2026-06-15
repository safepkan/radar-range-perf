"""Target radar-cross-section and fluctuation models.

The ``swerling`` attribute selects the fluctuation statistics used by
:mod:`radarperf.detection` (0/5 non-fluctuating, 1-4 fluctuating).  RCS may be
constant, a tabulated function of aspect angle, or any callable.

.. warning::

   The presets (:func:`car`, :func:`pedestrian`, ...) use **illustrative** RCS
   and Swerling assignments.  Real automotive RCS is strongly aspect- and
   range-dependent and best taken from measurement; treat presets as starting
   points.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence, cast

import numpy as np
import numpy.typing as npt

from .geometry import Geometry
from .units import FloatOrArray, db_to_linear, linear_to_db


@dataclass(frozen=True)
class ConstantRcsTarget:
    """A target with a single RCS value [m^2] regardless of aspect."""

    rcs: float
    swerling: int = 1
    name: str = "target"

    def __post_init__(self) -> None:
        if self.rcs <= 0.0:
            raise ValueError("rcs must be positive")
        _check_swerling(self.swerling)

    @classmethod
    def from_dbsm(
        cls, rcs_dbsm: float, swerling: int = 1, name: str = "target"
    ) -> "ConstantRcsTarget":
        """Build from RCS in dBsm (dB relative to 1 m^2)."""
        return cls(rcs=float(db_to_linear(rcs_dbsm)), swerling=swerling, name=name)

    def rcs_m2(self, geometry: Geometry) -> FloatOrArray:  # noqa: ARG002 - constant
        return self.rcs


@dataclass(frozen=True)
class AspectRcsTarget:
    """RCS given by an arbitrary callable of aspect angle [deg] -> m^2."""

    rcs_function: Callable[[float], float]
    swerling: int = 1
    name: str = "target"

    def __post_init__(self) -> None:
        _check_swerling(self.swerling)

    def rcs_m2(self, geometry: Geometry) -> FloatOrArray:
        aspect = geometry.aspect_deg
        if np.ndim(aspect) == 0:
            value = float(self.rcs_function(float(aspect)))
            if value <= 0.0:
                raise ValueError("rcs_function returned a non-positive RCS")
            return value
        values = np.vectorize(self.rcs_function, otypes=[float])(aspect)
        if np.any(values <= 0.0):
            raise ValueError("rcs_function returned a non-positive RCS")
        return cast(FloatOrArray, values)


class RcsTableTarget:
    """Aspect-dependent RCS interpolated (in dBsm) from a table.

    Interpolation is done in dBsm because RCS spans orders of magnitude; the
    table is treated as periodic over 360 deg of aspect.
    """

    def __init__(
        self,
        aspect_deg: Sequence[float],
        rcs_dbsm: Sequence[float],
        swerling: int = 1,
        name: str = "target",
    ) -> None:
        _check_swerling(swerling)
        order = np.argsort(np.asarray(aspect_deg, dtype=float))
        self._aspect: npt.NDArray[np.float64] = np.asarray(aspect_deg, dtype=float)[
            order
        ]
        self._rcs_dbsm: npt.NDArray[np.float64] = np.asarray(rcs_dbsm, dtype=float)[
            order
        ]
        self.swerling = swerling
        self.name = name

    def rcs_m2(self, geometry: Geometry) -> FloatOrArray:
        wrapped = np.mod(np.asarray(geometry.aspect_deg, dtype=float), 360.0)
        rcs_dbsm = np.interp(wrapped, self._aspect, self._rcs_dbsm, period=360.0)
        rcs = db_to_linear(rcs_dbsm)
        return float(rcs) if rcs.ndim == 0 else cast(FloatOrArray, rcs)


# --- Illustrative presets (replace with measured RCS) ------------------------


def car(rcs_dbsm: float = 10.0, swerling: int = 1) -> ConstantRcsTarget:
    """Passenger car, ~10 dBsm, Swerling 1 -- illustrative."""
    return ConstantRcsTarget.from_dbsm(rcs_dbsm, swerling=swerling, name="car")


def truck(rcs_dbsm: float = 20.0, swerling: int = 1) -> ConstantRcsTarget:
    """Truck / large vehicle, ~20 dBsm, Swerling 1 -- illustrative."""
    return ConstantRcsTarget.from_dbsm(rcs_dbsm, swerling=swerling, name="truck")


def pedestrian(rcs_dbsm: float = -3.0, swerling: int = 1) -> ConstantRcsTarget:
    """Pedestrian, ~-3 dBsm, Swerling 1 -- illustrative."""
    return ConstantRcsTarget.from_dbsm(rcs_dbsm, swerling=swerling, name="pedestrian")


def motorcycle(rcs_dbsm: float = 3.0, swerling: int = 1) -> ConstantRcsTarget:
    """Motorcycle, ~3 dBsm, Swerling 1 -- illustrative."""
    return ConstantRcsTarget.from_dbsm(rcs_dbsm, swerling=swerling, name="motorcycle")


def _check_swerling(swerling: int) -> None:
    if swerling not in (0, 1, 2, 3, 4, 5):
        raise ValueError("swerling must be one of 0,1,2,3,4,5")


def linear_to_dbsm(rcs_m2: float) -> float:
    """Convenience: RCS in m^2 to dBsm."""
    return float(linear_to_db(rcs_m2))
