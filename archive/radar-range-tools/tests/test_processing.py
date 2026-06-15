from __future__ import annotations

import numpy as np

from radar_range import FmcwWaveform, ProcessingModel
from radar_range.presets import awr2e44p_ddma_processing, infineon_ctrx8188f


def _unit_waveform() -> FmcwWaveform:
    return FmcwWaveform(
        name="unit",
        num_adc_samples=1,
        sample_rate_hz=1.0e6,
        bandwidth_hz=100.0e6,
        chirps_per_tx=1,
    )


def test_ddma_default_counts_noise_and_signal_looks_separately() -> None:
    processing = awr2e44p_ddma_processing(
        include_range_fft_gain=False,
        include_doppler_fft_gain=False,
    )

    assert processing.detector_looks == 24
    assert processing.signal_looks == 16
    assert processing.coherent_combining_gain_linear == 1.0
    np.testing.assert_allclose(
        processing.detector_signal_gain_linear(_unit_waveform()),
        16.0,
    )


def test_ddma_rx_coherent_subband_noncoherent_variant() -> None:
    processing = awr2e44p_ddma_processing(
        rx_mode="coherent",
        subband_mode="noncoherent",
        include_range_fft_gain=False,
        include_doppler_fft_gain=False,
    )

    assert processing.detector_looks == 6
    assert processing.signal_looks == 4
    np.testing.assert_allclose(processing.coherent_combining_gain_linear, 4.0)
    np.testing.assert_allclose(
        processing.detector_signal_gain_linear(_unit_waveform()),
        16.0,
    )


def test_ddma_rx_and_subband_coherent_variant_uses_only_active_subbands() -> None:
    processing = awr2e44p_ddma_processing(
        rx_mode="coherent",
        subband_mode="coherent",
        include_range_fft_gain=False,
        include_doppler_fft_gain=False,
    )

    assert processing.detector_looks == 1
    assert processing.signal_looks == 1
    np.testing.assert_allclose(processing.coherent_combining_gain_linear, 16.0)
    np.testing.assert_allclose(
        processing.detector_signal_gain_linear(_unit_waveform()),
        16.0,
    )


def test_legacy_noncoherent_looks_add_signal_energy_and_detector_looks() -> None:
    processing = ProcessingModel(
        include_range_fft_gain=False,
        include_doppler_fft_gain=False,
        noncoherent_looks=4,
    )

    assert processing.detector_looks == 4
    assert processing.signal_looks == 4
    np.testing.assert_allclose(
        processing.detector_signal_gain_linear(_unit_waveform()),
        4.0,
    )


def test_infineon_ctrx8188f_defaults_use_controlled_datasheet_typicals() -> None:
    hardware = infineon_ctrx8188f()

    assert hardware.tx_power_dbm == 14.5
    assert hardware.noise_figure_db == 9.7
