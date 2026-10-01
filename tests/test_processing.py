"""Processing defaults and public constants."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import get_window

from radarperf import (
    FmcwWaveform,
    MimoScheme,
    StagedProcessing,
    StandardProcessing,
    WINDOW_LOSS_BLACKMAN_DB,
    WINDOW_LOSS_BLACKMAN_HARRIS_DB,
    WINDOW_LOSS_FLAT_TOP_DB,
    WINDOW_LOSS_HAMMING_DB,
    WINDOW_LOSS_HANN_DB,
    WINDOW_LOSS_RECTANGULAR_DB,
    straddle_loss_db,
    window_loss_db,
)


def test_common_window_loss_constants() -> None:
    assert WINDOW_LOSS_RECTANGULAR_DB == 0.0
    assert WINDOW_LOSS_HAMMING_DB == pytest.approx(1.34)
    assert WINDOW_LOSS_HANN_DB == pytest.approx(1.76)
    assert WINDOW_LOSS_BLACKMAN_DB == pytest.approx(2.37)
    assert WINDOW_LOSS_BLACKMAN_HARRIS_DB == pytest.approx(3.02)
    assert WINDOW_LOSS_FLAT_TOP_DB == pytest.approx(5.76)


@pytest.mark.parametrize(
    ("window", "constant"),
    [
        ("boxcar", WINDOW_LOSS_RECTANGULAR_DB),
        ("hann", WINDOW_LOSS_HANN_DB),
        ("hamming", WINDOW_LOSS_HAMMING_DB),
        ("blackman", WINDOW_LOSS_BLACKMAN_DB),
        ("blackmanharris", WINDOW_LOSS_BLACKMAN_HARRIS_DB),
        ("flattop", WINDOW_LOSS_FLAT_TOP_DB),
    ],
)
def test_window_loss_constants_are_enbw(window: str, constant: float) -> None:
    # The constants are 10 log10 of the periodic window's ENBW in bins.
    w = get_window(window, 4096)
    enbw_bins = len(w) * np.sum(w**2) / np.sum(w) ** 2
    assert 10 * np.log10(enbw_bins) == pytest.approx(constant, abs=0.005)


def _wf() -> FmcwWaveform:
    return FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
    )


@pytest.mark.parametrize("processing", [StandardProcessing(), StagedProcessing()])
def test_processing_defaults_compute_hann_losses(
    processing: StandardProcessing | StagedProcessing,
) -> None:
    losses = processing.budget(_wf(), 1, 1).losses_db
    assert losses["range_window"] == pytest.approx(WINDOW_LOSS_HANN_DB, abs=0.005)
    assert losses["doppler_window"] == pytest.approx(WINDOW_LOSS_HANN_DB, abs=0.005)
    # Hann without padding: 0.47 dB averaged over the target position.
    assert losses["range_straddle"] == pytest.approx(0.471, abs=0.002)
    assert losses["doppler_straddle"] == pytest.approx(0.471, abs=0.002)


@pytest.mark.parametrize(
    ("window", "scallop_db", "enbw_bins"),
    [
        # Harris (1978), Table 1: scalloping loss and equivalent noise bandwidth.
        ("boxcar", 3.92, 1.00),
        ("hann", 1.42, 1.50),
        ("blackman", 1.10, 1.73),
        ("blackmanharris", 0.83, 2.00),
    ],
)
def test_window_and_straddle_match_harris(
    window: str, scallop_db: float, enbw_bins: float
) -> None:
    assert straddle_loss_db(window, 256, statistic="max") == pytest.approx(
        scallop_db, abs=0.01
    )
    assert 10 ** (window_loss_db(window, 256) / 10) == pytest.approx(
        enbw_bins, abs=0.01
    )


def test_zero_padding_reduces_straddle() -> None:
    no_pad = straddle_loss_db("hann", 256)
    pad2 = straddle_loss_db("hann", 256, 512)
    pad4 = straddle_loss_db("hann", 256, 1024)
    assert no_pad > pad2 > pad4 > 0.0
    # Midway between bins of a 4x padded FFT is an eighth of a raw bin off.
    assert straddle_loss_db("hann", 256, 1024, statistic="max") == pytest.approx(
        0.088, abs=0.002
    )
    with pytest.raises(ValueError):
        straddle_loss_db("hann", 256, 128)


def test_padding_and_window_fields_feed_the_budget() -> None:
    padded = StandardProcessing(
        range_window="blackman", range_fft_size=1024, doppler_fft_size=512
    )
    losses = padded.budget(_wf(), 1, 1).losses_db
    assert losses["range_window"] == pytest.approx(WINDOW_LOSS_BLACKMAN_DB, abs=0.005)
    assert losses["range_straddle"] == pytest.approx(
        straddle_loss_db("blackman", 256, 1024)
    )
    assert losses["doppler_straddle"] == pytest.approx(
        straddle_loss_db("hann", 128, 512)
    )


def test_loss_overrides_win() -> None:
    fixed = StandardProcessing(
        range_window_loss_db=2.0,
        range_straddle_loss_db=0.0,
        doppler_straddle_loss_db=1.42,
    )
    losses = fixed.budget(_wf(), 1, 1).losses_db
    assert losses["range_window"] == 2.0
    assert losses["range_straddle"] == 0.0
    assert losses["doppler_straddle"] == 1.42


def test_tdm_doppler_window_uses_chirps_per_tx() -> None:
    tdm = StandardProcessing(mimo=MimoScheme.TDM, doppler_fft_size=64)
    # 128 chirps over 2 TX: a 64-chirp Doppler FFT, so no padding.
    losses = tdm.budget(_wf(), 2, 1).losses_db
    assert losses["doppler_straddle"] == pytest.approx(straddle_loss_db("hann", 64))
