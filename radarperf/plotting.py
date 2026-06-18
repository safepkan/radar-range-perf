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

from .protocols import Antenna
from .sweeps import Map2D, RangeSweep

# Default principal-plane sweep for antenna pattern cuts: +/-90 deg, 0.5 deg step.
_PATTERN_ANGLES_DEG = np.linspace(-90.0, 90.0, 361)
_NON_INTERACTIVE_BACKENDS = frozenset(
    ("agg", "cairo", "pdf", "pgf", "ps", "svg", "template")
)


def _new_ax(ax: Optional[Axes]) -> Axes:
    if ax is None:
        _, ax = plt.subplots()
    return ax


def is_non_interactive_backend() -> bool:
    """Return whether Matplotlib is using a non-interactive backend."""
    return plt.get_backend().lower() in _NON_INTERACTIVE_BACKENDS


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


def _join_label(prefix: Optional[str], suffix: Optional[str]) -> Optional[str]:
    if prefix and suffix:
        return f"{prefix} {suffix}"
    return prefix or suffix


def _pattern_cut(
    antenna: Antenna, axis: str, angles: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Absolute gain [dBi] along a principal-plane cut."""
    zeros = np.zeros_like(angles)
    if axis == "az":
        swept = antenna.gain_dbi(angles, zeros)
    else:
        swept = antenna.gain_dbi(zeros, angles)
    return np.asarray(swept, dtype=float)


def plot_pattern_cut(
    tx_antenna: Antenna,
    rx_antenna: Optional[Antenna] = None,
    *,
    axis: str = "az",
    angles_deg: Optional[npt.NDArray[np.float64]] = None,
    ax: Optional[Axes] = None,
    relative: bool = False,
    two_way: bool = False,
    label: Optional[str] = None,
) -> Axes:
    """Plot a principal-plane gain cut of the transmit and receive elements.

    ``axis="az"`` sweeps azimuth at zero elevation; ``axis="el"`` sweeps
    elevation at zero azimuth -- the two cuts the SENCITY datasheets plot.

    By default the one-way element gain is drawn: a single curve, or separate
    TX and RX traces when a distinct ``rx_antenna`` is given (``rx_antenna``
    defaults to ``tx_antenna``, the case where the two coincide and the datasheet
    plots near-identical ``Avg. TX``/``Avg. RX`` curves).  With ``two_way`` a
    single round-trip curve (TX gain + RX gain, in dB) is drawn *instead* of the
    one-way gain(s).  ``relative`` references each curve to its own boresight
    peak; ``angles_deg`` defaults to +/-90 deg.
    """
    if axis not in ("az", "el"):
        raise ValueError('axis must be "az" or "el"')
    if angles_deg is None:
        angles = _PATTERN_ANGLES_DEG
    else:
        angles = np.asarray(angles_deg, dtype=float)

    distinct = rx_antenna is not None
    rx = rx_antenna if rx_antenna is not None else tx_antenna
    tx_gain = _pattern_cut(tx_antenna, axis, angles)
    rx_gain = tx_gain if not distinct else _pattern_cut(rx, axis, angles)

    ax = _new_ax(ax)

    def draw(gain: npt.NDArray[np.float64], peak: float, suffix: Optional[str]) -> None:
        ax.plot(
            angles, gain - peak if relative else gain, label=_join_label(label, suffix)
        )

    if two_way:
        peak = tx_antenna.boresight_gain_dbi + rx.boresight_gain_dbi
        draw(tx_gain + rx_gain, peak, None)
    elif distinct:
        draw(tx_gain, tx_antenna.boresight_gain_dbi, "TX")
        draw(rx_gain, rx.boresight_gain_dbi, "RX")
    else:
        draw(tx_gain, tx_antenna.boresight_gain_dbi, None)

    ax.set_xlabel("azimuth [deg]" if axis == "az" else "elevation [deg]")
    kind = "two-way gain" if two_way else "gain"
    unit = "dB" if relative else "dBi"
    ax.set_ylabel(f"{'relative ' if relative else ''}{kind} [{unit}]")
    ax.grid(True, alpha=0.3)
    if label is not None or (distinct and not two_way):
        ax.legend()
    return ax


def plot_pattern_cuts(
    tx_antenna: Antenna,
    rx_antenna: Optional[Antenna] = None,
    *,
    angles_deg: Optional[npt.NDArray[np.float64]] = None,
    axes: Optional[tuple[Axes, Axes]] = None,
    relative: bool = False,
    two_way: bool = False,
    label: Optional[str] = None,
) -> tuple[Axes, Axes]:
    """Plot the azimuth and elevation cuts side by side; return the two axes.

    Forwards ``rx_antenna``/``two_way`` to :func:`plot_pattern_cut` (see there
    for how TX, RX and round-trip traces are chosen).  Creates a 1x2 figure when
    ``axes`` is omitted; pass the returned pair back in (or reuse it across
    calls) to overlay several antennas on one figure.
    """
    if axes is None:
        _, created = plt.subplots(1, 2, figsize=(10, 4))
        ax_az, ax_el = created[0], created[1]
    else:
        ax_az, ax_el = axes
    for axis, ax in (("az", ax_az), ("el", ax_el)):
        plot_pattern_cut(
            tx_antenna,
            rx_antenna,
            axis=axis,
            angles_deg=angles_deg,
            ax=ax,
            relative=relative,
            two_way=two_way,
            label=label,
        )
    ax_az.set_title("azimuth cut")
    ax_el.set_title("elevation cut")
    return ax_az, ax_el


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
