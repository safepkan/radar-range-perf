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
    MultiBeamUniformArrayAntenna,
    PatternCutAntenna,
    RectangularArrayAntenna,
    UniformArrayAntenna,
    load_antenna_pair_csv,
    load_pattern_cut_csv,
)
from radarperf.protocols import Antenna
from radarperf.units import SPEED_OF_LIGHT

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


def test_rectangular_array_uniform_boresight_gain() -> None:
    antenna_model = RectangularArrayAntenna(
        [-0.25, 0.25],
        [-0.25, 0.25],
        np.ones((2, 2)),
        center_frequency_hz=SPEED_OF_LIGHT,
        element_gain_dbi=5.0,
        fft_size=256,
    )
    assert antenna_model.boresight_gain_dbi == pytest.approx(5.0 + 10.0 * np.log10(4.0))
    assert antenna_model.gain_dbi(0.0, 0.0) == pytest.approx(
        antenna_model.boresight_gain_dbi
    )
    # Half-wavelength horizontal spacing gives a null at u=1.
    assert antenna_model.gain_dbi(90.0, 0.0) < -200.0


def test_rectangular_array_fft_matches_direct_array_factor() -> None:
    horizontal = np.array([-0.75, -0.25, 0.25, 0.75])
    vertical = np.array([-0.25, 0.25])
    weights = np.array(
        [
            [0.2 + 0.1j, 0.4 - 0.2j],
            [0.7 + 0.3j, 1.0 - 0.1j],
            [0.9 - 0.2j, 0.6 + 0.4j],
            [0.3 + 0.2j, 0.1 - 0.1j],
        ]
    )
    antenna_model = RectangularArrayAntenna(
        horizontal,
        vertical,
        weights,
        center_frequency_hz=SPEED_OF_LIGHT,
        element_gain_dbi=3.0,
        fft_size=2048,
    )
    u = np.array([0.0, 0.17, -0.41])
    v = np.array([0.0, -0.23, 0.36])
    phase = np.exp(
        -2.0j
        * np.pi
        * (
            u[:, None, None] * horizontal[None, :, None]
            + v[:, None, None] * vertical[None, None, :]
        )
    )
    direct_power_gain = np.abs(np.sum(weights[None, :, :] * phase, axis=(1, 2))) ** 2
    direct_power_gain /= np.sum(np.abs(weights) ** 2)
    expected_gain_dbi = 3.0 + 10.0 * np.log10(direct_power_gain)
    assert np.asarray(antenna_model.gain_dbi_uv(u, v)) == pytest.approx(
        expected_gain_dbi, abs=2.0e-3
    )


def test_rectangular_array_normalizes_total_excitation_power() -> None:
    positions = np.array([-0.25, 0.25])
    weights = np.array([[0.5 + 0.2j, 1.0], [0.7j, 0.3 - 0.1j]])
    antenna_model = RectangularArrayAntenna(
        positions,
        positions,
        weights,
        center_frequency_hz=SPEED_OF_LIGHT,
        fft_size=256,
    )
    scaled_model = RectangularArrayAntenna(
        positions,
        positions,
        7.0 * weights,
        center_frequency_hz=SPEED_OF_LIGHT,
        fft_size=256,
    )
    u = np.array([-0.4, 0.0, 0.3])
    v = np.array([0.2, 0.0, -0.1])
    assert antenna_model.gain_dbi_uv(u, v) == pytest.approx(
        scaled_model.gain_dbi_uv(u, v), abs=1.0e-12
    )


def test_rectangular_array_builds_grid_from_shuffled_element_list() -> None:
    horizontal = np.array([1.0, 0.0, 1.0, 0.0])
    vertical = np.array([2.0, 2.0, 3.0, 3.0])
    weights = np.array([3.0, 1.0, 4.0, 2.0])
    antenna_model = RectangularArrayAntenna.from_element_list(
        horizontal,
        vertical,
        weights,
        center_frequency_hz=SPEED_OF_LIGHT,
        fft_size=64,
    )
    assert np.array_equal(antenna_model.horizontal_positions_m, [0.0, 1.0])
    assert np.array_equal(antenna_model.vertical_positions_m, [2.0, 3.0])
    assert np.array_equal(antenna_model.excitations, [[1.0, 2.0], [3.0, 4.0]])


def test_rectangular_array_rejects_incomplete_or_irregular_grid() -> None:
    with pytest.raises(ValueError, match="complete rectangular grid"):
        RectangularArrayAntenna.from_element_list(
            [0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 1.0],
            center_frequency_hz=SPEED_OF_LIGHT,
        )
    with pytest.raises(ValueError, match="uniformly spaced"):
        RectangularArrayAntenna(
            [0.0, 1.0, 3.0],
            [0.0, 1.0],
            np.ones((3, 2)),
            center_frequency_hz=SPEED_OF_LIGHT,
        )


def test_uniform_array_adds_relative_factor_but_not_coherent_peak_gain() -> None:
    element = antenna.ConstantGainAntenna(10.0)
    array = UniformArrayAntenna(
        element,
        horizontal_count=4,
        vertical_count=1,
        horizontal_spacing_m=0.5,
        center_frequency_hz=SPEED_OF_LIGHT,
    )
    # The processing model supplies the ideal coherent factor of four. The
    # antenna wrapper is 0 dB relative at the beam center.
    assert array.element_count == 4
    assert array.boresight_gain_dbi == pytest.approx(10.0)
    assert array.array_factor_relative_db_uv(0.0, 0.0) == pytest.approx(0.0)
    # A four-element half-wavelength ULA has a null at u=0.5 (azimuth 30 deg).
    assert array.gain_dbi(30.0, 0.0) < -200.0


def test_uniform_array_steers_relative_factor() -> None:
    array = UniformArrayAntenna(
        antenna.ConstantGainAntenna(7.0),
        horizontal_count=4,
        vertical_count=2,
        horizontal_spacing_m=0.5,
        vertical_spacing_m=0.5,
        center_frequency_hz=SPEED_OF_LIGHT,
        steering_azimuth_deg=30.0,
        steering_elevation_deg=0.0,
    )
    assert array.steering_u == pytest.approx(0.5)
    assert array.gain_dbi(30.0, 0.0) == pytest.approx(7.0)
    assert array.gain_dbi(0.0, 0.0) < -200.0


def test_uniform_array_builds_from_uv_steering() -> None:
    array = UniformArrayAntenna.from_steering_uv(
        antenna.ConstantGainAntenna(7.0),
        horizontal_count=4,
        vertical_count=2,
        horizontal_spacing_m=0.5,
        vertical_spacing_m=0.5,
        center_frequency_hz=SPEED_OF_LIGHT,
        steering_u=0.5,
        steering_v=0.0,
    )
    assert array.steering_azimuth_deg == pytest.approx(30.0)
    assert array.steering_elevation_deg == pytest.approx(0.0)
    assert array.gain_dbi(30.0, 0.0) == pytest.approx(7.0)


def test_uniform_array_multiplies_element_pattern_and_array_factor() -> None:
    element = antenna.GaussianBeamAntenna(12.0, 80.0, 30.0)
    array = UniformArrayAntenna(
        element,
        horizontal_count=2,
        vertical_count=2,
        horizontal_spacing_m=0.4,
        vertical_spacing_m=0.6,
        center_frequency_hz=SPEED_OF_LIGHT,
    )
    azimuth_deg = np.array([0.0, 10.0, 20.0])
    elevation_deg = np.array([5.0, 0.0, -10.0])
    u = np.sin(np.radians(azimuth_deg)) * np.cos(np.radians(elevation_deg))
    v = np.sin(np.radians(elevation_deg))
    expected = np.asarray(element.gain_dbi(azimuth_deg, elevation_deg)) + np.asarray(
        array.array_factor_relative_db_uv(u, v)
    )
    assert array.gain_dbi(azimuth_deg, elevation_deg) == pytest.approx(expected)


def test_uniform_subarrays_reconstruct_complete_aperture_with_coherent_gain() -> None:
    spacing_m = 0.4
    subarray = RectangularArrayAntenna(
        [-0.2, 0.2],
        [-0.4, 0.0, 0.4],
        np.ones((2, 3)),
        center_frequency_hz=SPEED_OF_LIGHT,
        fft_size=1024,
    )
    channel_array = UniformArrayAntenna(
        subarray,
        horizontal_count=3,
        vertical_count=2,
        horizontal_spacing_m=2 * spacing_m,
        vertical_spacing_m=3 * spacing_m,
        center_frequency_hz=SPEED_OF_LIGHT,
    )
    complete_aperture = RectangularArrayAntenna(
        np.arange(6) * spacing_m,
        np.arange(6) * spacing_m,
        np.ones((6, 6)),
        center_frequency_hz=SPEED_OF_LIGHT,
        fft_size=1024,
    )
    azimuth_deg = np.array([0.0, 4.0, 9.0, 17.0])
    elevation_deg = np.array([0.0, -3.0, 7.0, 12.0])
    combined_gain = np.asarray(
        channel_array.gain_dbi(azimuth_deg, elevation_deg)
    ) + 10.0 * np.log10(channel_array.element_count)
    assert combined_gain == pytest.approx(
        complete_aperture.gain_dbi(azimuth_deg, elevation_deg), abs=2.0e-3
    )


def test_uniform_array_validates_counts_spacings_and_steering() -> None:
    element = antenna.ConstantGainAntenna(0.0)
    with pytest.raises(ValueError, match="horizontal_count"):
        UniformArrayAntenna(
            element,
            horizontal_count=0,
            vertical_count=1,
            center_frequency_hz=SPEED_OF_LIGHT,
        )
    with pytest.raises(ValueError, match="horizontal_spacing"):
        UniformArrayAntenna(
            element,
            horizontal_count=2,
            vertical_count=1,
            center_frequency_hz=SPEED_OF_LIGHT,
        )
    with pytest.raises(ValueError, match="steering_azimuth"):
        UniformArrayAntenna(
            element,
            horizontal_count=1,
            vertical_count=1,
            center_frequency_hz=SPEED_OF_LIGHT,
            steering_azimuth_deg=91.0,
        )


def test_multi_beam_uniform_array_matches_maximum_individual_gain() -> None:
    element = antenna.GaussianBeamAntenna(12.0, 80.0, 30.0)
    steering_u = np.array([-0.1, 0.0, 0.1])
    steering_v = np.array([0.0, 0.0, 0.0])
    beam_set = MultiBeamUniformArrayAntenna(
        element,
        horizontal_count=4,
        vertical_count=2,
        horizontal_spacing_m=0.5,
        vertical_spacing_m=0.5,
        center_frequency_hz=SPEED_OF_LIGHT,
        steering_u=steering_u,
        steering_v=steering_v,
    )
    azimuth_deg = np.array([-8.0, -2.0, 0.0, 4.0, 9.0])
    elevation_deg = np.zeros_like(azimuth_deg)
    individual = np.stack(
        [
            beam_set.beam(index).gain_dbi(azimuth_deg, elevation_deg)
            for index in range(beam_set.beam_count)
        ]
    )
    assert beam_set.gain_dbi_per_beam(azimuth_deg, elevation_deg) == pytest.approx(
        individual
    )
    assert beam_set.gain_dbi(azimuth_deg, elevation_deg) == pytest.approx(
        np.max(individual, axis=0)
    )
    assert beam_set.element_count == 8
    assert beam_set.beam_count == 3
    assert beam_set.boresight_gain_dbi == pytest.approx(12.0)


def test_multi_beam_uniform_array_validates_steering_grid() -> None:
    element = antenna.ConstantGainAntenna(0.0)
    with pytest.raises(ValueError, match="equal nonzero lengths"):
        MultiBeamUniformArrayAntenna(
            element,
            horizontal_count=2,
            vertical_count=1,
            horizontal_spacing_m=0.5,
            center_frequency_hz=SPEED_OF_LIGHT,
            steering_u=[0.0, 0.1],
            steering_v=[0.0],
        )
    with pytest.raises(ValueError, match="visible"):
        MultiBeamUniformArrayAntenna(
            element,
            horizontal_count=2,
            vertical_count=1,
            horizontal_spacing_m=0.5,
            center_frequency_hz=SPEED_OF_LIGHT,
            steering_u=[0.8],
            steering_v=[0.8],
        )


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
