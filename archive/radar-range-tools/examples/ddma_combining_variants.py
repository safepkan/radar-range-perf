"""Compare AWR2E44P DDMA combining variants at one range.

This example keeps the waveform and target fixed and changes only how RX
channels and DDMA subbands are combined before detection.
"""

from __future__ import annotations

from radar_range import FmcwWaveform, PointTarget, RadarScenario, calculate_snr
from radar_range.presets import awr2e44p_ddma_processing, ti_awr2e44p


def main() -> None:
    hardware = ti_awr2e44p(tx_antenna_gain_dbi=15.0, rx_antenna_gain_dbi=15.0)
    waveform = FmcwWaveform(
        name="example DDMA frame",
        num_adc_samples=256,
        sample_rate_hz=10.0e6,
        bandwidth_hz=1.0e9,
        chirps_per_tx=64,
        num_tx=4,
    )
    target = PointTarget.from_dbsm(10.0, name="nominal car")

    variants = {
        "SDK-like noncoherent RX/subbands": awr2e44p_ddma_processing(),
        "coherent RX, noncoherent subbands": awr2e44p_ddma_processing(
            rx_mode="coherent",
        ),
        "coherent RX and active subbands": awr2e44p_ddma_processing(
            rx_mode="coherent",
            subband_mode="coherent",
        ),
    }

    for name, processing in variants.items():
        scenario = RadarScenario(
            hardware=hardware,
            waveform=waveform,
            processing=processing,
            target=target,
        )
        result = calculate_snr(scenario, 100.0)
        print(
            f"{name}: "
            f"SNR={float(result.snr_db):.1f} dB, "
            f"detector_looks={result.detector_looks}, "
            f"signal_looks={result.signal_looks}"
        )


if __name__ == "__main__":
    main()
