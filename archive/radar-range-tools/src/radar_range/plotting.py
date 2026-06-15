"""Optional plotting helpers."""

from __future__ import annotations

from typing import Any

import numpy as np

from radar_range.coverage import RangeSweepResult


def plot_snr_vs_range(
    sweep: RangeSweepResult,
    use_sinr: bool = True,
    ax: Any | None = None,
) -> Any:
    """Plot SNR or SINR versus range and return the Matplotlib axes."""

    import matplotlib.pyplot as plt

    axes = ax if ax is not None else plt.subplots()[1]
    y_value = sweep.sinr_db if use_sinr else sweep.snr_db
    label = "SINR" if use_sinr else "SNR"
    axes.plot(np.ravel(sweep.range_m), np.ravel(y_value))
    axes.set_xlabel("Range [m]")
    axes.set_ylabel(f"{label} [dB]")
    axes.grid(True)
    return axes


def plot_pd_vs_range(sweep: RangeSweepResult, ax: Any | None = None) -> Any:
    """Plot single-scan Pd versus range and return the Matplotlib axes."""

    import matplotlib.pyplot as plt

    axes = ax if ax is not None else plt.subplots()[1]
    axes.plot(np.ravel(sweep.range_m), np.ravel(sweep.pd))
    axes.set_xlabel("Range [m]")
    axes.set_ylabel("Single-scan Pd")
    axes.set_ylim(-0.02, 1.02)
    axes.grid(True)
    return axes


def plot_range_azimuth_pd(
    sweep: RangeSweepResult,
    azimuths_rad: np.ndarray,
    ax: Any | None = None,
) -> Any:
    """Plot a range/azimuth Pd grid and return the Matplotlib axes."""

    import matplotlib.pyplot as plt

    if sweep.pd.ndim != 2:
        raise ValueError("plot_range_azimuth_pd expects a 2-D range/azimuth sweep")
    axes = ax if ax is not None else plt.subplots()[1]
    azimuth_deg = np.rad2deg(azimuths_rad)
    range_axis = sweep.range_m[:, 0]
    mesh = axes.pcolormesh(azimuth_deg, range_axis, sweep.pd, shading="auto")
    axes.set_xlabel("Azimuth [deg]")
    axes.set_ylabel("Range [m]")
    axes.figure.colorbar(mesh, ax=axes, label="Single-scan Pd")
    return axes
