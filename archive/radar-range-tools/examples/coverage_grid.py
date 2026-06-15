"""Example range/azimuth coverage grid."""

from __future__ import annotations

import numpy as np
from dataclasses import replace

from radar_range import (
    FmcwWaveform,
    PointTarget,
    ProcessingModel,
    RadarScenario,
    SeparablePatternAntenna,
    coverage_boundary_range,
    range_azimuth_grid,
)
from radar_range.presets import ti_awr2e44p


def main() -> None:
    # A crude separable antenna cut: replace with a measured pattern for real work.
    antenna = SeparablePatternAntenna(
        max_gain_dbi=15.0,
        azimuth_deg=[-70.0, -45.0, 0.0, 45.0, 70.0],
        azimuth_relative_gain_db=[-10.0, -3.0, 0.0, -3.0, -10.0],
        elevation_deg=[-15.0, 0.0, 15.0],
        elevation_relative_gain_db=[-10.0, 0.0, -10.0],
    )
    hardware = replace(
        ti_awr2e44p(),
        tx_antenna=antenna,
        rx_antenna=antenna,
    )

    waveform = FmcwWaveform(
        name="coverage mode",
        num_adc_samples=512,
        sample_rate_hz=12.5e6,
        bandwidth_hz=2.0e9,
        chirps_per_tx=64,
        num_tx=4,
    )
    scenario = RadarScenario(
        hardware=hardware,
        waveform=waveform,
        processing=ProcessingModel(coherent_virtual_channels=16, cfar_loss_db=2.0),
        target=PointTarget.from_dbsm(0.0, name="nominal pedestrian"),
    )
    ranges_m = np.linspace(2.0, 180.0, 300)
    azimuths_rad = np.deg2rad(np.linspace(-70.0, 70.0, 281))
    sweep = range_azimuth_grid(scenario, ranges_m, azimuths_rad, pfa=1.0e-6)
    boundary = coverage_boundary_range(sweep, pd_threshold=0.9)
    print(f"Boresight Pd=0.9 boundary: {boundary[boundary.size // 2]:.1f} m")


if __name__ == "__main__":
    main()
