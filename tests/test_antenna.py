"""Datasheet antenna presets/bundles, CSV loading and PatternCutAntenna.

Pins the digitised SENCITY pattern cuts (peak gain, beamwidths) so the loaded
numbers can't silently drift, and exercises the generic CSV pattern loaders.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

from radarperf import antenna
from radarperf.antenna import (
    PatternCutAntenna,
    load_antenna_pair_csv,
    load_pattern_cut_csv,
)
from radarperf.protocols import Antenna

# (preset, boresight dBi, az 10-dB beamwidth deg, el 10-dB beamwidth deg)
PRESETS = [
    (antenna.sencity_this_ii, 16.2, 140.0, 16.0),
    (antenna.sencity_farad_iv, 15.0, 94.0, 30.0),
]


def _beamwidth_at(ant: Antenna, axis: str, drop_db: float) -> float:
    """Full beamwidth (deg) at ``drop_db`` below boresight.

    Sampled within each cut's own tabulated angle range (PatternCutAntenna
    clamps outside it, which would otherwise smear the edge crossing).
    """
    tab = ant.az_angles_deg if axis == "az" else ant.el_angles_deg  # type: ignore[attr-defined]
    angles = np.linspace(float(tab.min()), float(tab.max()), 36001)
    zeros = np.zeros_like(angles)
    swept = ant.gain_dbi(angles, zeros) if axis == "az" else ant.gain_dbi(zeros, angles)
    cut = np.asarray(swept, dtype=float)
    above = angles[cut - cut.max() >= -drop_db]
    return float(above.max() - above.min())


@pytest.mark.parametrize("preset, peak_dbi, az_bw10, el_bw10", PRESETS)
def test_preset_peak_and_beamwidths(preset, peak_dbi, az_bw10, el_bw10) -> None:  # type: ignore[no-untyped-def]
    bundle = preset()
    for element in (bundle.tx, bundle.rx):
        assert element.az_angles_deg.size == element.el_angles_deg.size == 281
        assert element.gain_dbi(0.0, 0.0) == pytest.approx(peak_dbi, abs=0.5)
        # 10-dB beamwidths match the datasheet headline numbers.
        assert _beamwidth_at(element, "az", 10.0) == pytest.approx(az_bw10, abs=4.0)
        assert _beamwidth_at(element, "el", 10.0) == pytest.approx(el_bw10, abs=4.0)


@pytest.mark.parametrize("preset", [p[0] for p in PRESETS])
def test_preset_pair_has_distinct_tx_rx(preset) -> None:  # type: ignore[no-untyped-def]
    pair = preset()
    assert isinstance(pair, antenna.AntennaPair)
    assert pair.name
    # TX and RX are similar but not identical (they differ in the sidelobes).
    assert pair.tx.boresight_gain_dbi != pair.rx.boresight_gain_dbi
    assert float(pair.tx.gain_dbi(0.0, 35.0)) != float(pair.rx.gain_dbi(0.0, 35.0))


def test_pair_from_element_shares_one_pattern() -> None:
    element = antenna.sencity_this_ii().tx
    pair = antenna.AntennaPair.from_element(element, name="custom")
    assert pair.tx is element
    assert pair.rx is element
    assert pair.name == "custom"


def test_separable_gain_adds_cuts() -> None:
    ant = antenna.sencity_farad_iv().tx
    expected = (
        ant.boresight_gain_dbi
        + (ant.gain_dbi(40.0, 0.0) - ant.boresight_gain_dbi)
        + (ant.gain_dbi(0.0, 10.0) - ant.boresight_gain_dbi)
    )
    assert ant.gain_dbi(40.0, 10.0) == pytest.approx(expected)


def test_from_absolute_cuts_references_each_cut_to_boresight() -> None:
    ant = PatternCutAntenna.from_absolute_cuts(
        az_cut=[(-30.0, 5.0), (0.0, 12.0), (30.0, 7.0)],
        el_cut=[(-20.0, 4.0), (0.0, 14.0), (20.0, 6.0)],
    )
    # Boresight is the mean of the two on-axis gains.
    assert ant.boresight_gain_dbi == pytest.approx(13.0)
    assert ant.gain_dbi(0.0, 0.0) == pytest.approx(13.0)
    # Each cut reproduces its own off-axis drop relative to its on-axis value.
    assert ant.gain_dbi(30.0, 0.0) - ant.gain_dbi(0.0, 0.0) == pytest.approx(7.0 - 12.0)
    assert ant.gain_dbi(0.0, 20.0) - ant.gain_dbi(0.0, 0.0) == pytest.approx(6.0 - 14.0)


_CSV = """antenna_name,part_number,plane,frequency_ghz,angle_deg,avg_rx_gain_dbi,avg_tx_gain_dbi
A,P1,azimuth,77.0,0.0,10.0,12.0
A,P1,azimuth,77.0,30.0,6.0,8.0
A,P1,elevation,77.0,0.0,10.0,12.0
A,P1,elevation,77.0,20.0,4.0,6.0
"""


def test_load_csv_reads_named_gain_column() -> None:
    tx = load_pattern_cut_csv(io.StringIO(_CSV), gain_column="avg_tx_gain_dbi")
    rx = load_pattern_cut_csv(io.StringIO(_CSV), gain_column="avg_rx_gain_dbi")
    assert tx.gain_dbi(0.0, 0.0) == pytest.approx(12.0)
    assert rx.gain_dbi(0.0, 0.0) == pytest.approx(10.0)


def test_load_pair_csv_splits_tx_and_rx() -> None:
    pair = load_antenna_pair_csv(io.StringIO(_CSV))
    assert pair.tx.gain_dbi(0.0, 0.0) == pytest.approx(12.0)  # avg_tx column
    assert pair.rx.gain_dbi(0.0, 0.0) == pytest.approx(10.0)  # avg_rx column
    assert pair.name == "A"  # from the antenna_name column


def test_load_csv_requires_both_planes() -> None:
    az_only = "\n".join(_CSV.splitlines()[:3]) + "\n"
    with pytest.raises(ValueError, match="azimuth and one elevation"):
        load_pattern_cut_csv(io.StringIO(az_only), gain_column="avg_tx_gain_dbi")


def test_load_csv_rejects_missing_column() -> None:
    with pytest.raises(ValueError, match="missing column"):
        load_pattern_cut_csv(io.StringIO(_CSV), gain_column="nope")


def test_load_csv_filters_multiple_antennas() -> None:
    two = _CSV + ("B,P2,azimuth,77.0,0.0,5.0,5.0\n" "B,P2,elevation,77.0,0.0,5.0,5.0\n")
    with pytest.raises(ValueError, match="several antennas"):
        load_antenna_pair_csv(io.StringIO(two))
    only_b = load_antenna_pair_csv(io.StringIO(two), antenna_name="P2")
    assert only_b.tx.gain_dbi(0.0, 0.0) == pytest.approx(5.0)
    assert only_b.name == "B"
