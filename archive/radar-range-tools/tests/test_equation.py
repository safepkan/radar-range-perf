from __future__ import annotations

import numpy as np

from radar_range import (
    ConstantGainAntenna,
    FmcwWaveform,
    PointTarget,
    ProcessingModel,
    RadarHardware,
    RadarScenario,
    calculate_snr,
    received_power_w,
)


def _scenario() -> RadarScenario:
    hardware = RadarHardware(
        name="test",
        center_frequency_hz=77.0e9,
        tx_power_dbm=10.0,
        noise_figure_db=10.0,
        tx_antenna=ConstantGainAntenna(10.0),
        rx_antenna=ConstantGainAntenna(10.0),
    )
    waveform = FmcwWaveform(
        name="test",
        num_adc_samples=128,
        sample_rate_hz=10.0e6,
        bandwidth_hz=1.0e9,
        chirps_per_tx=16,
    )
    return RadarScenario(
        hardware=hardware,
        waveform=waveform,
        processing=ProcessingModel(),
        target=PointTarget(1.0),
    )


def test_received_power_follows_r_to_minus_four() -> None:
    scenario = _scenario()
    p1 = received_power_w(
        scenario.hardware, scenario.target, scenario.environment, 50.0
    )
    p2 = received_power_w(
        scenario.hardware, scenario.target, scenario.environment, 100.0
    )
    np.testing.assert_allclose(float(p1 / p2), 16.0, rtol=1.0e-12)


def test_processing_gain_changes_snr() -> None:
    scenario = _scenario()
    snr_default = calculate_snr(scenario, 100.0).snr_linear
    scenario_more_gain = RadarScenario(
        hardware=scenario.hardware,
        waveform=scenario.waveform,
        processing=ProcessingModel(coherent_virtual_channels=4),
        target=scenario.target,
        environment=scenario.environment,
    )
    snr_more_gain = calculate_snr(scenario_more_gain, 100.0).snr_linear
    np.testing.assert_allclose(float(snr_more_gain / snr_default), 4.0)


def test_noncoherent_looks_change_total_detector_snr() -> None:
    scenario = _scenario()
    snr_default = calculate_snr(scenario, 100.0).snr_linear
    scenario_more_noncoherent_energy = RadarScenario(
        hardware=scenario.hardware,
        waveform=scenario.waveform,
        processing=ProcessingModel(noncoherent_looks=4),
        target=scenario.target,
        environment=scenario.environment,
    )
    result = calculate_snr(scenario_more_noncoherent_energy, 100.0)

    np.testing.assert_allclose(float(result.snr_linear / snr_default), 4.0)
    assert result.detector_looks == 4
    assert result.signal_looks == 4
