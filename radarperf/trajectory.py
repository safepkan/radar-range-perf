"""Target trajectories for multi-scan (track-acquisition) analysis.

A :class:`Trajectory` maps elapsed time since track start to a
:class:`~radarperf.geometry.Geometry`.  Single-scan link budgets and sweeps do
not need it; it comes into play when evaluating how detection probability
accumulates over successive scans as a target moves -- see
:func:`radarperf.sweeps.acquisition_sweep`.

The first concrete trajectory, :class:`RadialApproach`, is a target closing
straight along a fixed look direction at constant speed -- the simplest
acquisition scenario.  More general trajectories (crossing targets, waypoint or
numerically integrated paths) are future work: each need only implement
``geometry_at`` and the acquisition machinery picks it up unchanged.

The frame / revisit cadence (how often the radar looks) is deliberately *not*
part of the trajectory: it is a scheduling choice supplied to the sweep, so the
same trajectory can be evaluated under different scan rates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from .geometry import Geometry
from .units import FloatOrArray


@runtime_checkable
class Trajectory(Protocol):
    """A target's geometry as a function of elapsed time since track start."""

    def geometry_at(self, time_s: FloatOrArray) -> Geometry:
        """Target geometry at ``time_s`` [s] since track start.

        Accepts a scalar or a broadcastable array of times and returns a
        matching (scalar or batch) :class:`~radarperf.geometry.Geometry`, so a
        whole schedule of scan times is evaluated in one vectorised pass.
        """


@dataclass(frozen=True)
class RadialApproach:
    """A target closing straight at the radar at constant radial speed.

    The target moves directly along a fixed look direction
    (``azimuth_deg`` / ``elevation_deg``), so only its range changes with time:
    ``range(t) = initial_range_m - closing_speed_mps * t``.  Positive
    ``closing_speed_mps`` approaches the radar (negative recedes); the resulting
    :class:`~radarperf.geometry.Geometry` carries
    ``radial_velocity_mps = -closing_speed_mps`` to match the opening-positive
    Doppler sign convention.
    """

    initial_range_m: float
    closing_speed_mps: float
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    aspect_deg: float = 0.0

    def __post_init__(self) -> None:
        if self.initial_range_m <= 0.0:
            raise ValueError("initial_range_m must be positive")

    def geometry_at(self, time_s: FloatOrArray) -> Geometry:
        t = np.asarray(time_s, dtype=float)
        range_m = self.initial_range_m - self.closing_speed_mps * t
        return Geometry(
            range_m=float(range_m) if t.ndim == 0 else range_m,
            azimuth_deg=self.azimuth_deg,
            elevation_deg=self.elevation_deg,
            aspect_deg=self.aspect_deg,
            radial_velocity_mps=-self.closing_speed_mps,
        )
