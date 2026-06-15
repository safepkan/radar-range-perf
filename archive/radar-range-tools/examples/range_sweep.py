"""Example range sweep for a 77 GHz FMCW radar."""

from __future__ import annotations

import numpy as np

from radar_range import (
    FmcwWaveform,
    PointTarget,
    ProcessingModel,
    RadarScenario,
    range_sweep,
)
from radar_range.presets import ti_awr2243


def main() -> None:
    hardware = ti_awr2243(tx_antenna_gain_dbi=15.0, rx_antenna_gain_dbi=15.0)
    waveform = FmcwWaveform(
        name="example long-range mode",
        num_adc_samples=512,
        sample_rate_hz=12.5e6,
        bandwidth_hz=1.5e9,
        chirps_per_tx=64,
        num_tx=3,
    )
    processing = ProcessingModel(
        coherent_virtual_channels=hardware.virtual_channel_count,
        range_window_loss_db=1.5,
        doppler_window_loss_db=1.5,
        range_straddle_loss_db=1.0,
        cfar_loss_db=2.0,
    )
    target = PointTarget.from_dbsm(10.0, name="nominal car")
    scenario = RadarScenario(
        hardware=hardware,
        waveform=waveform,
        processing=processing,
        target=target,
    )

    ranges_m = np.linspace(5.0, 250.0, 246)
    sweep = range_sweep(scenario, ranges_m, pfa=1.0e-6)

    for range_m, snr_db, pd in zip(ranges_m[::40], sweep.sinr_db[::40], sweep.pd[::40]):
        print(f"{range_m:6.1f} m  SINR={snr_db:6.1f} dB  Pd={pd:6.3f}")


if __name__ == "__main__":
    main()
