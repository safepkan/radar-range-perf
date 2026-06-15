"""Sweeps over range and angle: profiles, 2-D maps and coverage.

These wrap the per-point :meth:`~radarperf.engine.Radar.link_budget` into the
arrays you actually plot:

* :func:`range_sweep` -- SNR/SINR/Pd versus range along a fixed direction.
* :func:`map_2d` -- a grid of Pd over any two coordinates, with helper geometry
  builders for range/azimuth, range/elevation, x/y and x/z.
* :func:`coverage_range` / :func:`coverage_vs_azimuth` -- the maximum range that
  still meets a target Pd.

Both the link budget and Pd are evaluated vectorised over the whole grid in a
single call (the engine broadcasts over an array :class:`Geometry`), so large
sweeps stay fast.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import numpy.typing as npt

from .detection import probability_of_detection
from .engine import Radar
from .environment import FreeSpace
from .geometry import Geometry
from .protocols import Environment, Target

GeometryBuilder = Callable[[float, float], Geometry]


@dataclass(frozen=True)
class RangeSweep:
    """Arrays from a range profile along one direction."""

    range_m: npt.NDArray[np.float64]
    snr_db: npt.NDArray[np.float64]
    sinr_db: npt.NDArray[np.float64]
    pd: npt.NDArray[np.float64]


def range_sweep(
    radar: Radar,
    target: Target,
    ranges_m: npt.NDArray[np.float64],
    *,
    azimuth_deg: float = 0.0,
    elevation_deg: float = 0.0,
    aspect_deg: float = 0.0,
    radial_velocity_mps: float = 0.0,
    environment: Environment = FreeSpace(),
    pfa: Optional[float] = None,
    swerling: Optional[int] = None,
    use_sinr: bool = True,
) -> RangeSweep:
    """SNR/SINR/Pd versus range along a fixed look direction."""
    ranges = np.asarray(ranges_m, dtype=float)
    geometry = Geometry(
        range_m=ranges,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        aspect_deg=aspect_deg,
        radial_velocity_mps=radial_velocity_mps,
    )
    terms = radar._budget_terms(target, geometry, environment)
    snr = np.asarray(terms.snr_db, dtype=float)
    sinr = np.asarray(terms.sinr_db, dtype=float)

    metric = sinr if use_sinr else snr
    case = target.swerling if swerling is None else swerling
    pd = np.asarray(
        probability_of_detection(
            metric,
            radar.default_pfa if pfa is None else pfa,
            swerling=case,
            n_pulses=terms.n_noncoherent,
            n_collapsing=terms.n_collapsing,
        ),
        dtype=float,
    )
    return RangeSweep(range_m=ranges, snr_db=snr, sinr_db=sinr, pd=pd)


@dataclass(frozen=True)
class Map2D:
    """A grid of Pd (and SINR) over two coordinates."""

    coord1: npt.NDArray[np.float64]
    coord2: npt.NDArray[np.float64]
    pd: npt.NDArray[np.float64]
    sinr_db: npt.NDArray[np.float64]


def map_2d(
    radar: Radar,
    target: Target,
    coord1_values: npt.NDArray[np.float64],
    coord2_values: npt.NDArray[np.float64],
    geometry_from: GeometryBuilder,
    *,
    environment: Environment = FreeSpace(),
    pfa: Optional[float] = None,
    swerling: Optional[int] = None,
    use_sinr: bool = True,
) -> Map2D:
    """Pd over a ``(coord1, coord2)`` grid.

    ``geometry_from(c1, c2)`` maps a grid point to a :class:`Geometry`; use one
    of the builders below or supply your own.  Result arrays are indexed
    ``[i1, i2]``.
    """
    c1 = np.asarray(coord1_values, dtype=float)
    c2 = np.asarray(coord2_values, dtype=float)
    geometry = _grid_geometry(geometry_from, c1, c2)
    terms = radar._budget_terms(target, geometry, environment)
    snr = np.asarray(terms.snr_db, dtype=float)
    sinr = np.asarray(terms.sinr_db, dtype=float)

    metric = sinr if use_sinr else snr
    case = target.swerling if swerling is None else swerling
    pd = np.asarray(
        probability_of_detection(
            metric,
            radar.default_pfa if pfa is None else pfa,
            swerling=case,
            n_pulses=terms.n_noncoherent,
            n_collapsing=terms.n_collapsing,
        ),
        dtype=float,
    )
    return Map2D(coord1=c1, coord2=c2, pd=pd, sinr_db=sinr)


def _grid_geometry(
    geometry_from: GeometryBuilder,
    c1: npt.NDArray[np.float64],
    c2: npt.NDArray[np.float64],
) -> Geometry:
    """Assemble a single batched :class:`Geometry` over the ``(c1, c2)`` grid.

    The per-point builder runs in a Python loop (cheap object construction); the
    expensive range-equation and detection maths then runs once, vectorised.
    """
    shape = (c1.size, c2.size)
    rng = np.empty(shape)
    az = np.empty(shape)
    el = np.empty(shape)
    aspect = np.empty(shape)
    velocity = np.empty(shape)
    for i, v1 in enumerate(c1):
        for j, v2 in enumerate(c2):
            point = geometry_from(float(v1), float(v2))
            rng[i, j] = float(point.range_m)
            az[i, j] = float(point.azimuth_deg)
            el[i, j] = float(point.elevation_deg)
            aspect[i, j] = float(point.aspect_deg)
            velocity[i, j] = float(point.radial_velocity_mps)
    return Geometry(
        range_m=rng,
        azimuth_deg=az,
        elevation_deg=el,
        aspect_deg=aspect,
        radial_velocity_mps=velocity,
    )


# --- geometry builders for common map planes --------------------------------


def range_azimuth_geometry(elevation_deg: float = 0.0) -> GeometryBuilder:
    """Builder for a range (coord1) by azimuth (coord2) map."""

    def build(range_m: float, azimuth_deg: float) -> Geometry:
        return Geometry(
            range_m=range_m, azimuth_deg=azimuth_deg, elevation_deg=elevation_deg
        )

    return build


def range_elevation_geometry(azimuth_deg: float = 0.0) -> GeometryBuilder:
    """Builder for a range (coord1) by elevation (coord2) map."""

    def build(range_m: float, elevation_deg: float) -> Geometry:
        return Geometry(
            range_m=range_m, azimuth_deg=azimuth_deg, elevation_deg=elevation_deg
        )

    return build


def xy_geometry(z_m: float = 0.0) -> GeometryBuilder:
    """Builder for an x (coord1) by y (coord2) ground-plane map."""

    def build(x_m: float, y_m: float) -> Geometry:
        return Geometry.from_cartesian(x_m, y_m, z_m)

    return build


def xz_geometry(y_m: float = 0.0) -> GeometryBuilder:
    """Builder for an x (coord1) by z (coord2) vertical-plane map."""

    def build(x_m: float, z_m: float) -> Geometry:
        return Geometry.from_cartesian(x_m, y_m, z_m)

    return build


# --- coverage ---------------------------------------------------------------


def coverage_range(
    radar: Radar,
    target: Target,
    target_pd: float,
    *,
    azimuth_deg: float = 0.0,
    elevation_deg: float = 0.0,
    aspect_deg: float = 0.0,
    environment: Environment = FreeSpace(),
    pfa: Optional[float] = None,
    swerling: Optional[int] = None,
    use_sinr: bool = True,
    min_range_m: float = 1.0,
    max_range_m: float = 1000.0,
    n_samples: int = 400,
) -> float:
    """Largest range whose Pd still meets ``target_pd`` along a direction.

    Robust to non-monotonic Pd(range) (e.g. from short-range clutter): scans a
    fine range grid and returns the outermost crossing, interpolated.  Returns
    ``nan`` if the target Pd is never met.
    """
    ranges = np.linspace(min_range_m, max_range_m, n_samples)
    sweep = range_sweep(
        radar,
        target,
        ranges,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        aspect_deg=aspect_deg,
        environment=environment,
        pfa=pfa,
        swerling=swerling,
        use_sinr=use_sinr,
    )
    meets = sweep.pd >= target_pd
    if not meets.any():
        return float("nan")
    last = int(np.max(np.nonzero(meets)[0]))
    if last == n_samples - 1:
        return float(ranges[last])
    # Interpolate the crossing between last (meets) and last+1 (fails).
    r0, r1 = ranges[last], ranges[last + 1]
    p0, p1 = sweep.pd[last], sweep.pd[last + 1]
    if p0 == p1:
        return float(r0)
    frac = (p0 - target_pd) / (p0 - p1)
    return float(r0 + frac * (r1 - r0))


def coverage_vs_azimuth(
    radar: Radar,
    target: Target,
    target_pd: float,
    azimuths_deg: npt.NDArray[np.float64],
    *,
    elevation_deg: float = 0.0,
    environment: Environment = FreeSpace(),
    pfa: Optional[float] = None,
    swerling: Optional[int] = None,
    use_sinr: bool = True,
    max_range_m: float = 1000.0,
    n_samples: int = 400,
) -> npt.NDArray[np.float64]:
    """Coverage range at ``target_pd`` for each azimuth (a coverage contour)."""
    azimuths = np.asarray(azimuths_deg, dtype=float)
    return np.array(
        [
            coverage_range(
                radar,
                target,
                target_pd,
                azimuth_deg=float(az),
                elevation_deg=elevation_deg,
                environment=environment,
                pfa=pfa,
                swerling=swerling,
                use_sinr=use_sinr,
                max_range_m=max_range_m,
                n_samples=n_samples,
            )
            for az in azimuths
        ]
    )
