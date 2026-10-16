"""Rain's scattering: the Mie series, water, drop sizes and their integration."""

from __future__ import annotations

import cmath
import math

import pytest

from radarperf.itu import rain_coefficients
from radarperf.rain import (
    marshall_palmer_dsd,
    mie_efficiencies,
    rain_scattering,
    terminal_fall_speed_mps,
    water_permittivity,
)


def test_mie_reproduces_maetzler_example() -> None:
    # Maetzler (2002), Section 4.1, printed p. 14: m = 5 + 0.4i, x = 1.
    q = mie_efficiencies(5.0 + 0.4j, 1.0)
    assert q.extinction == pytest.approx(1.9794, abs=1e-4)
    assert q.scattering == pytest.approx(0.8795, abs=1e-4)
    assert q.backscatter == pytest.approx(1.1138, abs=1e-4)


def test_mie_small_sphere_tends_to_rayleigh() -> None:
    m = cmath.sqrt(water_permittivity(77e9, 10.0))
    k = (m**2 - 1.0) / (m**2 + 2.0)
    x = 1e-3
    q = mie_efficiencies(m, x)
    # sigma_b = pi^5 |K|^2 D^6 / lambda^4 over pi D^2 / 4 is 4 x^4 |K|^2.
    assert q.backscatter == pytest.approx(4.0 * x**4 * abs(k) ** 2, rel=1e-4)
    # C_abs = (2 pi / lambda) Im(4 pi a^3 K) over pi a^2 is 4 x Im K.
    assert q.extinction - q.scattering == pytest.approx(4.0 * x * k.imag, rel=1e-4)


def test_permittivity_matches_liebe_rationalized_form() -> None:
    # Liebe et al. (1991) eq. (5), the real and imaginary parts written out.
    f, theta = 77.0, 1.0 - 300.0 / 283.15
    e0 = 77.66 - 103.3 * theta
    e1, e2 = 0.0671 * e0, 3.52 + 7.52 * theta
    g1 = 20.20 + 146.4 * theta + 316.0 * theta**2
    g2 = 39.8 * g1
    real = (e0 - e1) / (1 + (f / g1) ** 2) + (e1 - e2) / (1 + (f / g2) ** 2) + e2
    imag = (e0 - e1) * (f / g1) / (1 + (f / g1) ** 2) + (e1 - e2) * (f / g2) / (
        1 + (f / g2) ** 2
    )
    eps = water_permittivity(77e9, 10.0)
    assert eps.real == pytest.approx(real, rel=1e-12)
    assert eps.imag == pytest.approx(imag, rel=1e-12)
    # Static limit, eq. (1) at 20 degrees C.
    assert water_permittivity(1.0, 20.0).real == pytest.approx(80.074, abs=1e-3)
    with pytest.raises(ValueError):
        water_permittivity(77e9, 70.0)


def test_marshall_palmer_dsd() -> None:
    assert marshall_palmer_dsd(0.0, 5.0) == pytest.approx(8000.0)
    assert marshall_palmer_dsd(1.0, 1.0) == pytest.approx(8000.0 * math.exp(-4.1))
    with pytest.raises(ValueError):
        marshall_palmer_dsd(1.0, 0.0)


def test_fall_speed_branches() -> None:
    # The drizzle and rain branches of Tsikoudi et al. (2025) eq. (7) meet at
    # 0.86 mm within 2 mm/s; the rain branch at 2 mm is 9.65 - 10.3 exp(-1.2).
    below = float(terminal_fall_speed_mps(0.86))
    above = float(terminal_fall_speed_mps(0.86 + 1e-9))
    assert above == pytest.approx(below, abs=0.005)
    assert terminal_fall_speed_mps(2.0) == pytest.approx(9.65 - 10.3 * math.exp(-1.2))
    thin = terminal_fall_speed_mps(2.0, air_density_ratio=2.0)
    assert thin == pytest.approx(2.0**0.4 * float(terminal_fall_speed_mps(2.0)))


@pytest.mark.parametrize("rain_rate", [1.0, 10.0])
def test_rayleigh_limit_gives_marshall_palmer_reflectivity_factor(
    rain_rate: float,
) -> None:
    # Integrating N_0 exp(-Lambda D) D^6 gives N_0 6! / Lambda^7, which is
    # Marshall and Palmer's (1948) Table 1 entry "from equations (1) and (3)",
    # 296 R^1.47.  At 1 GHz the drops are Rayleigh scatterers.
    eps = water_permittivity(1e9, 10.0)
    k2 = abs((eps - 1.0) / (eps + 2.0)) ** 2
    s = rain_scattering(rain_rate, 1e9, temperature_c=10.0, dielectric_reference=k2)
    expected = 8000.0 * math.factorial(6) / (4.1 * rain_rate**-0.21) ** 7
    assert 10.0 * math.log10(s.equivalent_reflectivity_mm6_per_m3 / expected) == (
        pytest.approx(0.0, abs=0.05)
    )


@pytest.mark.parametrize("rain_rate", [1.0, 100.0])
def test_reflectivity_converges(rain_rate: float) -> None:
    base = rain_scattering(rain_rate, 77e9, temperature_c=10.0)
    finer = rain_scattering(rain_rate, 77e9, temperature_c=10.0, diameter_step_mm=0.005)
    shorter = rain_scattering(rain_rate, 77e9, temperature_c=10.0, diameter_max_mm=8.0)
    assert finer.volume_reflectivity_db == pytest.approx(
        base.volume_reflectivity_db, abs=0.01
    )
    assert shorter.volume_reflectivity_db == pytest.approx(
        base.volume_reflectivity_db, abs=0.01
    )


def test_mie_attenuation_near_p838() -> None:
    # Mie extinction over Marshall-Palmer drops against ITU-R P.838-3: within
    # 30 % from 1 to 100 mm/h (docs/rain_clutter.md tabulates the difference).
    k, alpha = rain_coefficients(77e9)
    for rain_rate in (1.0, 10.0, 100.0):
        s = rain_scattering(rain_rate, 77e9, temperature_c=10.0)
        assert s.specific_attenuation_db_per_km == pytest.approx(
            k * rain_rate**alpha, rel=0.3
        )
