"""Geometry of a target relative to the radar.

A :class:`Geometry` is a point in the radar's field of regard: a slant range
plus a look direction (azimuth/elevation), together with the kinematic and
aspect information the rest of the toolbox needs.

The fields may be plain floats (a single point) or broadcastable NumPy arrays (a
batch of points evaluated in one vectorised pass).  :attr:`Geometry.is_scalar`
reports which.  :meth:`~radarperf.engine.Radar.link_budget` requires a single
point; the sweep helpers in :mod:`radarperf.sweeps` build array geometries.

Conventions
-----------
* Azimuth is measured in the horizontal plane, positive to the left looking
  out from the radar (right-handed about the up axis).  Boresight is 0 deg.
* Elevation is measured from the horizontal plane, positive up.
* ``aspect_deg`` describes the orientation of the *target* as seen by the
  radar and is what aspect-dependent RCS models key off; it is independent of
  where the target sits in the beam.
* ``radial_velocity_mps`` is positive for *opening* (receding) targets and
  negative for closing targets, matching the usual Doppler sign convention.

Direction cosines ``u`` (azimuth) and ``v`` (elevation) are provided because
waveguide-antenna patterns are frequently tabulated in uv-space.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import cast

import numpy as np

from .units import FloatOrArray


@dataclass(frozen=True)
class Geometry:
    """A target location and kinematic state relative to the radar.

    Each field is a scalar or a broadcastable array (see the module docstring).
    """

    range_m: FloatOrArray
    azimuth_deg: FloatOrArray = 0.0
    elevation_deg: FloatOrArray = 0.0
    aspect_deg: FloatOrArray = 0.0
    radial_velocity_mps: FloatOrArray = 0.0

    def __post_init__(self) -> None:
        if np.any(np.asarray(self.range_m, dtype=float) <= 0.0):
            raise ValueError("range_m must be positive")

    @property
    def is_scalar(self) -> bool:
        """True when every field is a scalar (i.e. a single point)."""
        return all(np.ndim(getattr(self, f.name)) == 0 for f in fields(self))

    @property
    def u(self) -> FloatOrArray:
        """Azimuth direction cosine, ``sin(az) * cos(el)``."""
        az = np.radians(self.azimuth_deg)
        el = np.radians(self.elevation_deg)
        return cast(FloatOrArray, np.sin(az) * np.cos(el))

    @property
    def v(self) -> FloatOrArray:
        """Elevation direction cosine, ``sin(el)``."""
        return cast(FloatOrArray, np.sin(np.radians(self.elevation_deg)))

    @classmethod
    def from_cartesian(
        cls,
        x_m: FloatOrArray,
        y_m: FloatOrArray,
        z_m: FloatOrArray = 0.0,
        *,
        aspect_deg: FloatOrArray = 0.0,
        radial_velocity_mps: FloatOrArray = 0.0,
    ) -> "Geometry":
        """Build a :class:`Geometry` from radar-frame Cartesian coordinates.

        The radar sits at the origin looking along +x.  ``y`` is cross-range
        (left positive) and ``z`` is up.  This is convenient for x/y and x/z
        coverage maps.
        """
        ground = np.hypot(x_m, y_m)
        range_m = np.hypot(ground, z_m)
        azimuth_deg = np.degrees(np.arctan2(y_m, x_m))
        elevation_deg = np.degrees(np.arctan2(z_m, ground))
        return cls(
            range_m=cast(FloatOrArray, range_m),
            azimuth_deg=cast(FloatOrArray, azimuth_deg),
            elevation_deg=cast(FloatOrArray, elevation_deg),
            aspect_deg=aspect_deg,
            radial_velocity_mps=radial_velocity_mps,
        )
