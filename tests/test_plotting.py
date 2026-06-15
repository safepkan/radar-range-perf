"""Smoke tests for the optional Matplotlib helpers (headless, Agg backend)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from radarperf import (
    FmcwWaveform,
    GaussianBeamAntenna,
    MimoScheme,
    Radar,
    StandardProcessing,
    frontend,
    target,
)
from radarperf.plotting import (
    plot_coverage,
    plot_pd_map,
    plot_pd_vs_range,
    plot_snr_vs_range,
)
from radarperf.sweeps import (
    coverage_vs_azimuth,
    map_2d,
    range_azimuth_geometry,
    range_sweep,
)


def make_radar() -> Radar:
    wf = FmcwWaveform(
        center_frequency_hz=76.5e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )
    element = GaussianBeamAntenna(11.0, 80.0, 20.0)
    return Radar(
        frontend=frontend.awr2243(),
        waveform=wf,
        processing=StandardProcessing(mimo=MimoScheme.TDM),
        tx_antenna=element,
        rx_antenna=element,
    )


RANGES = np.linspace(5.0, 250.0, 60)
AZIMUTHS = np.linspace(-50.0, 50.0, 21)


def test_range_profile_helpers_draw_lines() -> None:
    sweep = range_sweep(make_radar(), target.car(), RANGES)
    ax = plot_snr_vs_range(sweep, label="SINR")
    assert len(ax.lines) == 1
    # A second call on the same axes overlays (composition).
    plot_snr_vs_range(sweep, ax=ax, use_sinr=False, label="SNR")
    assert len(ax.lines) == 2
    plt.close("all")

    ax = plot_pd_vs_range(sweep)
    assert len(ax.lines) == 1
    assert ax.get_ylim() == (0.0, 1.0)
    plt.close("all")


def test_pd_map_draws_mesh_and_contours() -> None:
    grid = map_2d(
        make_radar(), target.car(), RANGES, AZIMUTHS, range_azimuth_geometry()
    )
    ax = plot_pd_map(grid, xlabel="range [m]", ylabel="azimuth [deg]")
    assert len(ax.collections) >= 1  # the pcolormesh
    plt.close("all")


def test_coverage_polar_and_rectangular() -> None:
    coverage = coverage_vs_azimuth(make_radar(), target.car(), 0.5, AZIMUTHS)

    polar = plot_coverage(AZIMUTHS, coverage)
    assert polar.name == "polar"
    assert len(polar.lines) == 1
    plt.close("all")

    rect = plot_coverage(AZIMUTHS, coverage, polar=False)
    assert rect.name == "rectilinear"
    plt.close("all")
