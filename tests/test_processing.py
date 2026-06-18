"""Processing defaults and public constants."""

from __future__ import annotations

import pytest

from radarperf import (
    StagedProcessing,
    StandardProcessing,
    WINDOW_LOSS_BLACKMAN_DB,
    WINDOW_LOSS_BLACKMAN_HARRIS_DB,
    WINDOW_LOSS_FLAT_TOP_DB,
    WINDOW_LOSS_HAMMING_DB,
    WINDOW_LOSS_HANN_DB,
    WINDOW_LOSS_RECTANGULAR_DB,
)


def test_common_window_loss_constants() -> None:
    assert WINDOW_LOSS_RECTANGULAR_DB == 0.0
    assert WINDOW_LOSS_HAMMING_DB == pytest.approx(1.34)
    assert WINDOW_LOSS_HANN_DB == pytest.approx(1.76)
    assert WINDOW_LOSS_BLACKMAN_DB == pytest.approx(2.37)
    assert WINDOW_LOSS_BLACKMAN_HARRIS_DB == pytest.approx(3.02)
    assert WINDOW_LOSS_FLAT_TOP_DB == pytest.approx(5.76)


def test_processing_defaults_use_hann_window_loss() -> None:
    standard = StandardProcessing()
    staged = StagedProcessing()

    assert standard.range_window_loss_db == WINDOW_LOSS_HANN_DB
    assert standard.doppler_window_loss_db == WINDOW_LOSS_HANN_DB
    assert staged.range_window_loss_db == WINDOW_LOSS_HANN_DB
    assert staged.doppler_window_loss_db == WINDOW_LOSS_HANN_DB
