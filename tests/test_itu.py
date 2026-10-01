"""ITU-R P.676-13, P.838-3 and P.835-7 against published values."""

from __future__ import annotations

import math

import pytest

from radarperf import Atmosphere, FmcwWaveform, Geometry, Rain
from radarperf.itu import (
    gaseous_specific_attenuation_db_per_km,
    rain_coefficients,
    reference_atmosphere,
)

# ITU-R validation examples for P.676-13 (CG-3M3J-13-ValEx, rev. 8.3.0, sheet
# "P.676-13 SpAtt"): dry-air pressure 1013.25 hPa, 7.5 g/m^3, 288.15 K.
# frequency [GHz]: (oxygen, water vapour) [dB/km]
P676_13_VALIDATION = {
    12.0: (0.00869826406877357, 0.00953538822024593),
    20.0: (0.01188355047780760, 0.09704730481511170),
    60.0: (14.6234747964861, 0.15484184100000),
    90.0: (0.03886971107242350, 0.34197339400000),
    130.0: (0.04150908359952280, 0.75184470400000),
}

# ITU-R P.838-3, Table 5: frequency [GHz]: (k_H, alpha_H, k_V, alpha_V)
P838_3_TABLE_5 = {
    10.0: (0.01217, 1.2571, 0.01129, 1.2156),
    60.0: (0.8606, 0.7656, 0.8515, 0.7486),
    76.0: (1.1185, 0.7199, 1.1139, 0.7091),
    77.0: (1.1320, 0.7177, 1.1276, 0.7073),
    81.0: (1.1827, 0.7096, 1.1793, 0.7004),
    100.0: (1.3671, 0.6815, 1.3680, 0.6765),
}


@pytest.mark.parametrize("frequency_ghz", sorted(P676_13_VALIDATION))
def test_p676_matches_itu_validation_examples(frequency_ghz: float) -> None:
    temperature_k = 288.15
    vapour_pressure = 7.5 * temperature_k / 216.7
    oxygen, water = gaseous_specific_attenuation_db_per_km(
        frequency_ghz * 1e9,
        temperature_c=temperature_k - 273.15,
        pressure_hpa=1013.25 + vapour_pressure,  # total = dry + vapour
        water_vapour_density_g_m3=7.5,
    )
    ref_oxygen, ref_water = P676_13_VALIDATION[frequency_ghz]
    assert oxygen == pytest.approx(ref_oxygen, rel=1e-6)
    assert water == pytest.approx(ref_water, rel=1e-6)


def test_atmosphere_default_is_p676_standard_atmosphere() -> None:
    standard = Atmosphere.itu_p676()
    assert standard.specific_attenuation_db_per_km == pytest.approx(0.347, abs=5e-4)
    assert Atmosphere().specific_attenuation_db_per_km == pytest.approx(
        standard.specific_attenuation_db_per_km, abs=0.005
    )


def test_humid_air_attenuates_more() -> None:
    dry = Atmosphere.itu_p676(water_vapour_density_g_m3=0.0)
    humid = Atmosphere.itu_p676(temperature_c=30.0, water_vapour_density_g_m3=20.0)
    assert (
        dry.specific_attenuation_db_per_km
        < 0.347
        < humid.specific_attenuation_db_per_km
    )


@pytest.mark.parametrize("frequency_ghz", sorted(P838_3_TABLE_5))
def test_p838_matches_table_5(frequency_ghz: float) -> None:
    k_h, alpha_h, k_v, alpha_v = P838_3_TABLE_5[frequency_ghz]
    horizontal = rain_coefficients(frequency_ghz * 1e9)
    vertical = rain_coefficients(frequency_ghz * 1e9, polarization_tilt_deg=90.0)
    # Table 5 is rounded to four significant digits.
    assert horizontal == pytest.approx((k_h, alpha_h), rel=5e-4)
    assert vertical == pytest.approx((k_v, alpha_v), rel=5e-4)


def test_rain_uses_p838_at_the_waveform_frequency() -> None:
    wf = FmcwWaveform(
        center_frequency_hz=77e9,
        bandwidth_hz=1e9,
        sample_rate_hz=20e6,
        n_samples=256,
        n_chirps=128,
    )
    rain = Rain(rain_rate_mm_per_hr=10.0)
    k, alpha = P838_3_TABLE_5[77.0][:2]
    expected_one_way = k * 10.0**alpha
    loss = rain.two_way_loss_db(Geometry(range_m=500.0), wf)
    assert float(loss) == pytest.approx(2 * expected_one_way * 0.5, rel=1e-3)
    fixed = Rain(rain_rate_mm_per_hr=10.0, k=1.0, alpha=0.7)
    assert fixed.specific_attenuation_db_per_km(77e9) == pytest.approx(10.0**0.7)
    with pytest.raises(ValueError):
        Rain(rain_rate_mm_per_hr=10.0, k=1.0)


# U.S. Standard Atmosphere 1976, which P.835-7 Annex 1 adopts for temperature
# and pressure: geometric height [m]: (temperature [K], pressure [hPa]).
US_STANDARD_ATMOSPHERE_1976 = {
    0.0: (288.150, 1013.25),
    1000.0: (281.651, 898.76),
    5000.0: (255.676, 540.48),
}


@pytest.mark.parametrize("height_m", sorted(US_STANDARD_ATMOSPHERE_1976))
def test_reference_atmosphere_matches_us_standard_atmosphere(height_m: float) -> None:
    temperature_k, pressure_hpa = US_STANDARD_ATMOSPHERE_1976[height_m]
    conditions = reference_atmosphere(height_m)
    assert conditions.temperature_c + 273.15 == pytest.approx(temperature_k, abs=1e-3)
    assert conditions.pressure_hpa == pytest.approx(pressure_hpa, abs=0.01)


def test_reference_atmosphere_water_vapour_and_limits() -> None:
    # P.835-7 equation (6): 7.5 g/m^3 at sea level, 2 km scale height.
    assert reference_atmosphere(0.0).water_vapour_density_g_m3 == 7.5
    assert reference_atmosphere(2000.0).water_vapour_density_g_m3 == pytest.approx(
        7.5 / math.e
    )
    with pytest.raises(ValueError):
        reference_atmosphere(-1.0)
    with pytest.raises(ValueError):
        reference_atmosphere(12000.0)


def test_atmosphere_itu_reference_at_sea_level_is_the_standard_value() -> None:
    assert Atmosphere.itu_reference(0.0).specific_attenuation_db_per_km == (
        pytest.approx(Atmosphere.itu_p676().specific_attenuation_db_per_km)
    )
    assert (
        Atmosphere.itu_reference(1000.0).specific_attenuation_db_per_km
        < Atmosphere.itu_reference(0.0).specific_attenuation_db_per_km
    )
