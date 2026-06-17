"""Range profiles, a Pd map and a coverage diagram via radarperf.plotting.

Requires the plot extra (``pip install -e '.[plot]'``).  Opens an interactive
window via ``plt.show()``; under a non-interactive backend (e.g. CI with
``MPLBACKEND=Agg``) it saves a PNG to the temp directory instead.

Run with::

    python examples/plotting_demo.py
"""

from __future__ import annotations

import os
import tempfile

import matplotlib.pyplot as plt
import numpy as np

from radarperf import (
    AntennaPair,
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


def main() -> None:
    waveform = FmcwWaveform(
        center_frequency_hz=76.5e9,
        bandwidth_hz=1.0e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
        chirp_repetition_time_s=50e-6,
    )
    element = GaussianBeamAntenna(11.0, 80.0, 20.0)
    radar = Radar(
        frontend=frontend.awr2243(),
        waveform=waveform,
        processing=StandardProcessing(mimo=MimoScheme.TDM),
        antenna=AntennaPair.from_element(element),
    )
    car = target.car()

    ranges = np.linspace(5.0, 250.0, 250)
    azimuths = np.linspace(-60.0, 60.0, 121)

    fig = plt.figure(figsize=(11, 8))
    ax_snr = fig.add_subplot(2, 2, 1)
    ax_pd = fig.add_subplot(2, 2, 2)
    ax_map = fig.add_subplot(2, 2, 3)
    ax_cov = fig.add_subplot(2, 2, 4, projection="polar")

    sweep = range_sweep(radar, car, ranges)
    plot_snr_vs_range(sweep, ax=ax_snr, label="SINR")
    plot_pd_vs_range(sweep, ax=ax_pd, label="Pd")

    grid = map_2d(radar, car, ranges, azimuths, range_azimuth_geometry())
    plot_pd_map(grid, ax=ax_map, xlabel="range [m]", ylabel="azimuth [deg]")

    coverage = coverage_vs_azimuth(radar, car, 0.9, azimuths)
    plot_coverage(azimuths, coverage, ax=ax_cov)

    fig.tight_layout()

    if plt.get_backend().lower() == "agg":
        path = os.path.join(tempfile.gettempdir(), "radarperf_plotting_demo.png")
        fig.savefig(path, dpi=120)
        print(f"non-interactive backend; saved figure to {path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
