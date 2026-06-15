"""Optional Matplotlib helpers for the arrays the sweeps return.

Requires the ``plot`` extra (``pip install -e '.[plot]'``).  Import this module
explicitly -- the core package does not depend on Matplotlib::

    from radarperf.plotting import plot_pd_vs_range

Every helper takes an optional ``ax`` (creating one if omitted), draws into it,
and returns it -- so plots compose and overlay.  None of them call ``show()`` or
choose a backend; that is left to the caller.
"""

from __future__ import annotations

from typing import Optional, Sequence, cast

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from matplotlib.projections.polar import PolarAxes

from .sweeps import Map2D, RangeSweep


def _new_ax(ax: Optional[Axes]) -> Axes:
    if ax is None:
        _, ax = plt.subplots()
    return ax


def plot_snr_vs_range(
    sweep: RangeSweep,
    *,
    ax: Optional[Axes] = None,
    use_sinr: bool = True,
    label: Optional[str] = None,
) -> Axes:
    """Plot SINR (or SNR) in dB versus range from a :class:`RangeSweep`."""
    ax = _new_ax(ax)
    values = sweep.sinr_db if use_sinr else sweep.snr_db
    ax.plot(sweep.range_m, values, label=label)
    ax.set_xlabel("range [m]")
    ax.set_ylabel("SINR [dB]" if use_sinr else "SNR [dB]")
    ax.grid(True, alpha=0.3)
    if label is not None:
        ax.legend()
    return ax


def plot_pd_vs_range(
    sweep: RangeSweep,
    *,
    ax: Optional[Axes] = None,
    label: Optional[str] = None,
) -> Axes:
    """Plot probability of detection versus range from a :class:`RangeSweep`."""
    ax = _new_ax(ax)
    ax.plot(sweep.range_m, sweep.pd, label=label)
    ax.set_xlabel("range [m]")
    ax.set_ylabel("Pd")
    ax.set_ylim(0.0, 1.0)
    ax.grid(True, alpha=0.3)
    if label is not None:
        ax.legend()
    return ax


def plot_pd_map(
    grid: Map2D,
    *,
    ax: Optional[Axes] = None,
    xlabel: str = "coord 1",
    ylabel: str = "coord 2",
    contour_levels: Sequence[float] = (0.5, 0.9),
    colorbar: bool = True,
) -> Axes:
    """Plot a filled Pd map over a :class:`Map2D` grid.

    ``coord1`` runs along x and ``coord2`` along y.  ``contour_levels`` overlays
    Pd iso-contours (e.g. the 0.5 and 0.9 boundaries); pass an empty sequence to
    omit them.
    """
    ax = _new_ax(ax)
    mesh = ax.pcolormesh(
        grid.coord1, grid.coord2, grid.pd.T, vmin=0.0, vmax=1.0, shading="auto"
    )
    if len(contour_levels) > 0:
        lines = ax.contour(
            grid.coord1,
            grid.coord2,
            grid.pd.T,
            levels=list(contour_levels),
            colors="white",
            linewidths=1.0,
        )
        ax.clabel(lines, inline=True, fontsize=8, fmt="%.2f")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if colorbar:
        ax.figure.colorbar(mesh, ax=ax, label="Pd")
    return ax


def plot_coverage(
    azimuths_deg: npt.NDArray[np.float64],
    coverage_range_m: npt.NDArray[np.float64],
    *,
    ax: Optional[Axes] = None,
    polar: bool = True,
    label: Optional[str] = None,
) -> Axes:
    """Plot a coverage diagram: detection range versus azimuth.

    With ``polar`` (the default) the azimuth is the polar angle (0 deg up,
    positive to the left) and the radius is range; otherwise it is a plain
    range-vs-azimuth line.  Azimuths with no coverage (NaN) leave a gap.  When an
    ``ax`` is supplied its existing projection is used.
    """
    az = np.asarray(azimuths_deg, dtype=float)
    rng = np.asarray(coverage_range_m, dtype=float)
    if ax is None:
        _, ax = plt.subplots(subplot_kw={"projection": "polar"} if polar else None)
    if getattr(ax, "name", "") == "polar":
        polar_ax = cast(PolarAxes, ax)
        polar_ax.plot(np.radians(az), rng, label=label)
        polar_ax.set_theta_zero_location("N")
        polar_ax.set_theta_direction(1)  # azimuth positive to the left
    else:
        ax.plot(az, rng, label=label)
        ax.set_xlabel("azimuth [deg]")
        ax.set_ylabel("coverage range [m]")
    if label is not None:
        ax.legend()
    return ax
