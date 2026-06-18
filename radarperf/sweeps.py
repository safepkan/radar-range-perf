"""Sweeps over range and angle: profiles, 2-D maps, coverage and acquisition.

These produce the arrays you actually plot:

* :func:`range_sweep` -- SNR/SINR/Pd versus range along a fixed direction.
* :func:`map_2d` -- a grid of Pd over any two coordinates, with helper geometry
  builders for range/azimuth, range/elevation, x/y and x/z.
* :func:`coverage_range` / :func:`coverage_vs_azimuth` -- the maximum range that
  still meets a target Pd.
* :func:`acquisition_sweep` -- per-scan, cumulative and M-of-N detection
  probability as a target moves along a :class:`~radarperf.trajectory.Trajectory`.

Both the link budget and Pd are evaluated vectorised over the whole grid in a
single call (the engine broadcasts over an array :class:`Geometry`), so large
sweeps stay fast.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import numpy.typing as npt

from .detection import (
    cumulative_pd,
    probability_of_acquisition_mofn,
    probability_of_detection,
)
from .engine import Radar
from .environment import FreeSpace
from .geometry import Geometry
from .protocols import Environment, Target
from .trajectory import Trajectory

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


# --- track acquisition ------------------------------------------------------


@dataclass(frozen=True)
class AcquisitionSweep:
    """Per-scan detection statistics as a target moves over successive scans."""

    scan_index: npt.NDArray[np.int_]
    time_s: npt.NDArray[np.float64]
    range_m: npt.NDArray[np.float64]
    pd: npt.NDArray[np.float64]
    cumulative_pd: npt.NDArray[np.float64]
    #: Sliding M-of-N confirmation probability, or ``None`` if ``confirm`` unset.
    confirmation_pd: Optional[npt.NDArray[np.float64]]


def acquisition_sweep(
    radar: Radar,
    target: Target,
    trajectory: Trajectory,
    *,
    frame_time_s: Optional[float] = None,
    n_scans: Optional[int] = None,
    duration_s: Optional[float] = None,
    min_range_m: float = 1.0,
    confirm: Optional[tuple[int, int]] = None,
    environment: Environment = FreeSpace(),
    pfa: Optional[float] = None,
    swerling: Optional[int] = None,
    use_sinr: bool = True,
) -> AcquisitionSweep:
    """Detection probability accumulated over scans as a target moves.

    The radar looks every ``frame_time_s`` seconds and the ``trajectory`` is
    sampled at those scan times to give the range (and look direction) per scan;
    the link budget and single-scan Pd are then evaluated for all scans in one
    vectorised pass.  ``frame_time_s`` defaults to the waveform's CPI duration
    (a radar that stares and reframes back to back) -- the staring lower bound;
    set it to the actual revisit interval of the scan schedule.

    The number of scans is taken from ``n_scans`` if given, else from
    ``duration_s`` (scans at ``0, frame, 2*frame, ...`` up to and including
    ``duration_s``), else chosen automatically as the target closes: scans run
    until the range first falls below ``min_range_m``.  Automatic selection
    needs a closing trajectory; supply ``n_scans`` or ``duration_s`` otherwise.

    With ``confirm=(m, n)`` the sliding M-of-N confirmation probability is also
    returned (see :func:`~radarperf.detection.probability_of_acquisition_mofn`).
    The cumulative "at least one detection" curve is always returned.
    """
    frame_time = radar.waveform.cpi_duration_s if frame_time_s is None else frame_time_s
    if not np.isfinite(frame_time) or frame_time <= 0.0:
        raise ValueError(
            "frame_time_s must be positive; pass it explicitly or set the "
            "waveform's chirp_repetition_time_s so cpi_duration_s is defined"
        )

    count = _resolve_scan_count(
        trajectory, frame_time, n_scans, duration_s, min_range_m
    )
    times = np.arange(count, dtype=float) * frame_time
    geometry = trajectory.geometry_at(times)
    ranges = np.broadcast_to(np.asarray(geometry.range_m, dtype=float), times.shape)

    terms = radar._budget_terms(target, geometry, environment)
    metric = terms.sinr_db if use_sinr else terms.snr_db
    case = target.swerling if swerling is None else swerling
    pd = np.asarray(
        probability_of_detection(
            np.asarray(metric, dtype=float),
            radar.default_pfa if pfa is None else pfa,
            swerling=case,
            n_pulses=terms.n_noncoherent,
            n_collapsing=terms.n_collapsing,
        ),
        dtype=float,
    )

    confirmation = None
    if confirm is not None:
        m, window = confirm
        confirmation = probability_of_acquisition_mofn(pd, m=m, n=window)

    return AcquisitionSweep(
        scan_index=np.arange(count),
        time_s=times,
        range_m=np.array(ranges, dtype=float),
        pd=pd,
        cumulative_pd=cumulative_pd(pd),
        confirmation_pd=confirmation,
    )


def _resolve_scan_count(
    trajectory: Trajectory,
    frame_time_s: float,
    n_scans: Optional[int],
    duration_s: Optional[float],
    min_range_m: float,
    *,
    max_scans: int = 1_000_000,
) -> int:
    """Number of scans to evaluate; see :func:`acquisition_sweep` for the rules."""
    if n_scans is not None:
        if n_scans < 1:
            raise ValueError("n_scans must be >= 1")
        return int(n_scans)
    if duration_s is not None:
        if duration_s < 0.0:
            raise ValueError("duration_s must be non-negative")
        return int(duration_s // frame_time_s) + 1

    # Automatic: advance scan by scan until the range first drops below
    # min_range_m.  Geometry rejects a non-positive range, so a step that
    # overshoots the radar raises -- treat that (None) as having reached the
    # floor.  The range must keep decreasing, or we would never stop; a
    # non-closing trajectory is rejected at once rather than ground to the cap.
    def range_at(scan: int) -> Optional[float]:
        try:
            geometry = trajectory.geometry_at(float(scan * frame_time_s))
        except ValueError:
            return None
        return float(np.asarray(geometry.range_m, dtype=float))

    first = range_at(0)
    if first is None or first < min_range_m:
        raise ValueError("trajectory begins within min_range_m; no scans to evaluate")

    count, previous = 1, first
    while count < max_scans:
        current = range_at(count)
        if current is None or current < min_range_m:
            break
        if current >= previous:
            raise ValueError(
                "automatic scan count needs a closing trajectory (range is not "
                "decreasing) -- pass n_scans or duration_s instead"
            )
        count, previous = count + 1, current
    if count >= max_scans:
        raise ValueError("automatic scan count hit the cap; pass n_scans or duration_s")
    return count
