"""Smoke tests for the optional Matplotlib helpers (headless, Agg backend)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pytest

from radarperf import (
    AntennaPair,
    FmcwWaveform,
    GaussianBeamAntenna,
    MimoScheme,
    Radar,
    StandardProcessing,
    antenna,
    frontend,
    target,
)
from radarperf.plotting import (
    is_non_interactive_backend,
    plot_coverage,
    plot_pattern_cut,
    plot_pattern_cuts,
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
        antenna=AntennaPair.from_element(element),
    )


RANGES = np.linspace(5.0, 250.0, 60)
AZIMUTHS = np.linspace(-50.0, 50.0, 21)


def test_is_non_interactive_backend_matches_matplotlib() -> None:
    assert plt.get_backend().lower() == "agg"
    assert is_non_interactive_backend()


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


def test_pattern_cut_draws_and_overlays() -> None:
    element = antenna.sencity_this_ii().tx
    ax = plot_pattern_cut(element, axis="az", label="THIS-II")
    assert len(ax.lines) == 1
    assert ax.get_ylabel() == "gain [dBi]"
    # Boresight sample equals the peak gain.
    line = ax.lines[0]
    xs = np.asarray(line.get_xdata(), dtype=float)
    ys = np.asarray(line.get_ydata(), dtype=float)
    assert ys[int(np.argmin(np.abs(xs)))] == element.boresight_gain_dbi
    # A second antenna on the same axes overlays.
    plot_pattern_cut(antenna.sencity_farad_iv().tx, axis="az", ax=ax, label="FARAD-IV")
    assert len(ax.lines) == 2
    plt.close("all")


def test_pattern_cut_relative_axis() -> None:
    ax = plot_pattern_cut(antenna.sencity_farad_iv().tx, axis="el", relative=True)
    assert ax.get_xlabel() == "elevation [deg]"
    assert ax.get_ylabel() == "relative gain [dB]"
    # Referenced to boresight: ~0 dB at the peak (a touch above, where the
    # measured cut ripples over its own on-axis value), negative elsewhere.
    xs = np.asarray(ax.lines[0].get_xdata(), dtype=float)
    ys = np.asarray(ax.lines[0].get_ydata(), dtype=float)
    assert ys[int(np.argmin(np.abs(xs)))] == pytest.approx(0.0, abs=1e-9)
    assert float(np.max(ys)) == pytest.approx(0.0, abs=0.5)
    plt.close("all")


def test_pattern_cut_rejects_bad_axis() -> None:
    with pytest.raises(ValueError):
        plot_pattern_cut(antenna.sencity_this_ii().tx, axis="bogus")


def test_pattern_cuts_pair_and_reuse() -> None:
    ax_az, ax_el = plot_pattern_cuts(antenna.sencity_this_ii().tx, label="THIS-II")
    assert (len(ax_az.lines), len(ax_el.lines)) == (1, 1)
    assert ax_az.get_title() == "azimuth cut"
    assert ax_el.get_title() == "elevation cut"
    # Reusing the returned axes overlays a second antenna.
    plot_pattern_cuts(
        antenna.sencity_farad_iv().tx, axes=(ax_az, ax_el), label="FARAD-IV"
    )
    assert (len(ax_az.lines), len(ax_el.lines)) == (2, 2)
    plt.close("all")


def test_pattern_cut_distinct_tx_rx_draws_both() -> None:
    bundle = antenna.sencity_this_ii()
    ax = plot_pattern_cut(bundle.tx, bundle.rx, axis="az")
    assert len(ax.lines) == 2  # separate TX and RX traces
    labels = [t.get_text() for t in ax.legend().get_texts()]
    assert labels == ["TX", "RX"]
    # The TX and RX elements differ (sidelobes), so the traces differ.
    assert not np.allclose(ax.lines[0].get_ydata(), ax.lines[1].get_ydata())
    plt.close("all")


def test_pattern_cut_two_way_replaces_one_way() -> None:
    element = antenna.sencity_this_ii().tx
    one_ax = plot_pattern_cut(element, axis="az", label="THIS-II")
    one_way = np.asarray(one_ax.lines[0].get_ydata(), dtype=float)
    plt.close("all")

    ax = plot_pattern_cut(element, axis="az", two_way=True, label="THIS-II")
    assert len(ax.lines) == 1  # two-way replaces the one-way curve
    assert ax.get_ylabel() == "two-way gain [dBi]"
    two_way = np.asarray(ax.lines[0].get_ydata(), dtype=float)
    assert np.allclose(two_way, 2.0 * one_way)  # TX == RX here
    plt.close("all")
