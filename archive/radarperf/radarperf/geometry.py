"""Geometry of a target relative to the radar.

A :class:`Geometry` is a single point in the radar's field of regard: a slant
range plus a look direction (azimuth/elevation), together with the kinematic
and aspect information the rest of the toolbox needs.  Sweeps build large
collections of these.

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

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Geometry:
    """A target location and kinematic state relative to the radar."""

    range_m: float
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    aspect_deg: float = 0.0
    radial_velocity_mps: float = 0.0

    def __post_init__(self) -> None:
        if self.range_m <= 0.0:
            raise ValueError("range_m must be positive")

    @property
    def u(self) -> float:
        """Azimuth direction cosine, ``sin(az) * cos(el)``."""
        az = math.radians(self.azimuth_deg)
        el = math.radians(self.elevation_deg)
        return math.sin(az) * math.cos(el)

    @property
    def v(self) -> float:
        """Elevation direction cosine, ``sin(el)``."""
        return math.sin(math.radians(self.elevation_deg))

    @classmethod
    def from_cartesian(
        cls,
        x_m: float,
        y_m: float,
        z_m: float = 0.0,
        *,
        aspect_deg: float = 0.0,
        radial_velocity_mps: float = 0.0,
    ) -> "Geometry":
        """Build a :class:`Geometry` from radar-frame Cartesian coordinates.

        The radar sits at the origin looking along +x.  ``y`` is cross-range
        (left positive) and ``z`` is up.  This is convenient for x/y and x/z
        coverage maps.
        """
        ground = math.hypot(x_m, y_m)
        range_m = math.sqrt(ground * ground + z_m * z_m)
        azimuth_deg = math.degrees(math.atan2(y_m, x_m))
        elevation_deg = math.degrees(math.atan2(z_m, ground))
        return cls(
            range_m=range_m,
            azimuth_deg=azimuth_deg,
            elevation_deg=elevation_deg,
            aspect_deg=aspect_deg,
            radial_velocity_mps=radial_velocity_mps,
        )
