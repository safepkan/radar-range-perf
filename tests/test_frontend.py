"""Chipset preset values and cascading.

Pins the datasheet-sourced per-channel power / noise figure / channel counts so
the controlled numbers can't silently drift.
"""

from __future__ import annotations

import numpy as np
import pytest

from radarperf import frontend
from radarperf.units import watt_to_dbm

# (preset, tx power dBm/ch, noise figure dB, n_tx, n_rx)
PRESETS = [
    (frontend.awr1243, 12.0, 14.0, 3, 4),
    (frontend.awr2243, 13.0, 12.0, 3, 4),
    (frontend.awr2e44p, 13.5, 11.0, 4, 4),
    (frontend.ctrx8188f, 14.5, 10.2, 8, 8),
]


@pytest.mark.parametrize("preset, power_dbm, nf_db, n_tx, n_rx", PRESETS)
def test_preset_values(preset, power_dbm, nf_db, n_tx, n_rx) -> None:  # type: ignore[no-untyped-def]
    fe = preset()
    assert np.isclose(float(watt_to_dbm(fe.tx_power_w)), power_dbm, atol=1e-9)
    assert fe.noise_figure_db == nf_db
    assert (fe.n_tx, fe.n_rx) == (n_tx, n_rx)


def test_cascade_adds_channels_keeps_per_channel_specs() -> None:
    unit = frontend.ctrx8188f()
    pair = frontend.cascade(unit, 2)
    assert (pair.n_tx, pair.n_rx) == (16, 16)
    assert pair.tx_power_w == unit.tx_power_w
    assert pair.noise_figure_db == unit.noise_figure_db


def test_overrides_apply() -> None:
    fe = frontend.awr2243(noise_figure_db=10.0, name="bench part")
    assert fe.noise_figure_db == 10.0
    assert fe.name == "bench part"
    # Unspecified fields keep the preset value.
    assert np.isclose(float(watt_to_dbm(fe.tx_power_w)), 13.0, atol=1e-9)
