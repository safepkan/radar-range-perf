"""Pd versus range, coverage, a MIMO-scheme comparison and track acquisition.

Prints tables and opens a plot window via ``plt.show()``.  Under a
non-interactive backend (e.g. CI with ``MPLBACKEND=Agg``) it saves a PNG to the
temp directory instead.

Run with::

    python examples/pd_vs_range.py
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
    sweeps,
    target,
)
from radarperf.detection import cumulative_pd, probability_of_acquisition_mofn
from radarperf.plotting import is_non_interactive_backend, plot_pd_vs_range


def build(mimo: MimoScheme) -> Radar:
    waveform = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1.0e9,
        sample_rate_hz=20.0e6,
        n_samples=256,
        n_chirps=128,
    )
    element = GaussianBeamAntenna(11.0, 80.0, 20.0)
    return Radar(
        frontend=frontend.awr2243(),
        waveform=waveform,
        processing=StandardProcessing(mimo=mimo),
        antenna=AntennaPair.from_element(element),
    )


def main() -> None:
    pedestrian = target.pedestrian()  # ~-3 dBsm, Swerling 1 (illustrative)

    # 1) Pd vs range for three MIMO schemes.
    ranges = np.linspace(5.0, 250.0, 50)
    print("Pd vs range (pedestrian, Pfa 1e-6)")
    print(f"{'range [m]':>10}  {'none':>8}  {'TDM':>8}  {'DDM':>8}")
    sweeps_by_scheme = {
        scheme: sweeps.range_sweep(build(scheme), pedestrian, ranges)
        for scheme in (MimoScheme.NONE, MimoScheme.TDM, MimoScheme.DDM)
    }
    for i in range(0, len(ranges), 7):
        row = "  ".join(
            f"{sweeps_by_scheme[s].pd[i]:8.3f}"
            for s in (MimoScheme.NONE, MimoScheme.TDM, MimoScheme.DDM)
        )
        print(f"{ranges[i]:10.1f}  {row}")
    print()

    # 2) Coverage range at Pd = 0.9 for each scheme.
    print("Coverage range at Pd = 0.9 (boresight):")
    for scheme in (MimoScheme.NONE, MimoScheme.TDM, MimoScheme.DDM):
        rng = sweeps.coverage_range(
            build(scheme), pedestrian, target_pd=0.9, max_range_m=300.0
        )
        print(f"  {scheme.value:>5}: {rng:6.1f} m")
    print()

    # 3) Track acquisition: cumulative vs sliding M-of-N over successive scans
    #    as a target closes from 200 m to 120 m at 4 m per scan.
    radar = build(MimoScheme.DDM)
    scan_ranges = np.arange(200.0, 116.0, -4.0)
    pd_per_scan = [
        radar.probability_of_detection(pedestrian, _at(r)) for r in scan_ranges
    ]
    cumulative = cumulative_pd(pd_per_scan)
    confirm_2of3 = probability_of_acquisition_mofn(pd_per_scan, m=2, n=3)

    print("Track acquisition as target closes (DDM, pedestrian):")
    print(f"{'range [m]':>10}  {'Pd/scan':>8}  {'cum 1+':>8}  {'2-of-3':>8}")
    for r, p, c, t in zip(scan_ranges, pd_per_scan, cumulative, confirm_2of3):
        print(f"{r:10.1f}  {p:8.3f}  {c:8.3f}  {t:8.3f}")

    fig, (ax_pd, ax_track) = plt.subplots(1, 2, figsize=(11, 4.5))
    for scheme in (MimoScheme.NONE, MimoScheme.TDM, MimoScheme.DDM):
        plot_pd_vs_range(
            sweeps_by_scheme[scheme],
            ax=ax_pd,
            label=scheme.value,
        )
    ax_pd.set_title("Pd vs range")

    ax_track.plot(scan_ranges, pd_per_scan, label="Pd/scan")
    ax_track.plot(scan_ranges, cumulative, label="cum 1+")
    ax_track.plot(scan_ranges, confirm_2of3, label="2-of-3")
    ax_track.set_xlabel("range [m]")
    ax_track.set_ylabel("probability")
    ax_track.set_ylim(0.0, 1.0)
    ax_track.grid(True, alpha=0.3)
    ax_track.legend()
    ax_track.set_title("Track acquisition")

    fig.tight_layout()

    if is_non_interactive_backend():
        path = os.path.join(tempfile.gettempdir(), "radarperf_pd_vs_range.png")
        fig.savefig(path, dpi=120)
        print(f"non-interactive backend; saved figure to {path}")
    else:
        plt.show()


def _at(range_m: float):  # type: ignore[no-untyped-def]
    from radarperf import Geometry

    return Geometry(range_m=float(range_m))


if __name__ == "__main__":
    main()
