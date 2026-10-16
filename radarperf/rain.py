"""Rain's scattering at millimetre waves: reflectivity, extinction, fall speeds.

Rain's volume reflectivity is the backscatter of its drops summed over their
sizes, ``eta = integral of N(D) sigma_b(D) dD`` [1/m].  Here:

* ``water_permittivity`` -- Liebe, Hufford and Manabe (1991), the double Debye
  model of their equations (1) and (4)-(4b), fitted to data below 1 THz.
* ``mie_efficiencies`` -- Mie scattering by a sphere, with the extinction,
  scattering and backscattering efficiencies Maetzler (2002) defines.
* ``marshall_palmer_dsd`` -- the exponential drop-size distribution of
  Marshall and Palmer (1948), equations (1)-(3).
* ``terminal_fall_speed_mps`` -- the piecewise fall speed of Tsikoudi et al.
  (2025), equation (7).
* ``rain_scattering`` -- integrates them over the drop sizes: the volume
  reflectivity, the equivalent reflectivity factor, the specific attenuation
  and the backscatter-weighted fall speeds at one rain rate.

Drops are spheres and scatter singly.  Diameters are in millimetres, as the
drop-size distribution has them, and frequencies in hertz.  docs/rain_clutter.md
derives the integrals, gives the values at 77 GHz and says where the model
breaks down.  The tests check the Mie series against Maetzler's published
example and the Rayleigh limit, and the integration against the reflectivity
factor Marshall and Palmer give for their distribution.
"""

from __future__ import annotations

import cmath
import functools
import math
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import numpy.typing as npt
from scipy.special import spherical_jn, spherical_yn

from .units import SPEED_OF_LIGHT, FloatOrArray

FloatArray = npt.NDArray[np.float64]

# Conventional |K|^2 of water at centimetre wavelengths, which weather radars
# use to state an equivalent reflectivity factor.
DIELECTRIC_REFERENCE: float = 0.93


def water_permittivity(frequency_hz: float, temperature_c: float) -> complex:
    """Complex relative permittivity of liquid water, ``eps' + i eps''``.

    Liebe, Hufford and Manabe (1991): the double Debye model of equation (4),
    with ``theta = 1 - 300 / (273.15 + T)``, the static permittivity of
    equation (1) and the parameters of (4a)-(4b).  The imaginary part is
    positive, the sign of their ``1 - i f / gamma``, which matches a
    refractive index ``n + i k`` with ``k > 0`` for an absorbing medium.
    Equation (1) is fitted from -20 to 60 degrees C.
    """
    if not -20.0 <= temperature_c <= 60.0:
        raise ValueError("Liebe et al. (1991) fit water from -20 to 60 degrees C")
    theta = 1.0 - 300.0 / (273.15 + temperature_c)
    eps_0 = 77.66 - 103.3 * theta  # (1)
    eps_1 = 0.0671 * eps_0  # (4a)
    gamma_1 = 20.20 + 146.4 * theta + 316.0 * theta**2  # (4a) [GHz]
    eps_2 = 3.52 + 7.52 * theta  # (4b)
    gamma_2 = 39.8 * gamma_1  # (4b)
    f = frequency_hz / 1.0e9
    return (
        (eps_0 - eps_1) / (1.0 - 1j * f / gamma_1)
        + (eps_1 - eps_2) / (1.0 - 1j * f / gamma_2)
        + eps_2
    )  # (4)


class MieEfficiencies(NamedTuple):
    """A sphere's efficiencies: cross sections over its geometric cross section."""

    extinction: float
    scattering: float
    backscatter: float


def mie_efficiencies(
    refractive_index: complex, size_parameter: float
) -> MieEfficiencies:
    """Mie efficiencies of a homogeneous sphere.

    ``refractive_index`` is ``n + i k``, ``k >= 0`` for an absorbing sphere,
    relative to the surrounding medium; ``size_parameter`` is ``x = pi D /
    lambda``.  With the coefficients ``a_n``, ``b_n`` of Bohren and Huffman
    (1983), as Maetzler (2002) gives them:

        Q_ext = (2 / x^2) sum (2n+1) Re(a_n + b_n)
        Q_sca = (2 / x^2) sum (2n+1) (|a_n|^2 + |b_n|^2)
        Q_b   = (1 / x^2) |sum (2n+1) (-1)^n (a_n - b_n)|^2

    ``Q_b`` is the radar backscattering efficiency: the monostatic radar
    cross section is ``Q_b pi D^2 / 4``, which tends to ``pi^5 |K|^2 D^6 /
    lambda^4``, ``K = (m^2 - 1) / (m^2 + 2)``, for a small sphere.  The series
    stops after ``x + 4 x^(1/3) + 2`` terms.  The logarithmic derivative of
    ``psi_n(m x)`` comes from downward recurrence, the Riccati-Bessel
    functions of ``x`` from SciPy's spherical Bessel functions.
    """
    m = complex(refractive_index)
    x = float(size_parameter)
    if x <= 0.0:
        raise ValueError("size_parameter must be positive")
    n_max = int(round(x + 4.0 * x ** (1.0 / 3.0) + 2.0))
    mx = m * x
    n_start = int(max(n_max, abs(mx))) + 16
    log_derivative = np.zeros(n_start + 1, dtype=complex)
    for k in range(n_start, 0, -1):
        log_derivative[k - 1] = k / mx - 1.0 / (log_derivative[k] + k / mx)
    d = log_derivative[1 : n_max + 1]

    orders = np.arange(n_max + 1)
    psi = x * spherical_jn(orders, x)
    xi = psi + 1j * x * spherical_yn(orders, x)
    n = orders[1:]
    ta = d / m + n / x
    tb = m * d + n / x
    a = (ta * psi[1:] - psi[:-1]) / (ta * xi[1:] - xi[:-1])
    b = (tb * psi[1:] - psi[:-1]) / (tb * xi[1:] - xi[:-1])

    weight = 2 * n + 1
    q_ext = 2.0 / x**2 * float(np.sum(weight * (a + b).real))
    q_sca = 2.0 / x**2 * float(np.sum(weight * (np.abs(a) ** 2 + np.abs(b) ** 2)))
    q_b = abs(complex(np.sum(weight * (-1.0) ** n * (a - b)))) ** 2 / x**2
    return MieEfficiencies(q_ext, q_sca, q_b)


def marshall_palmer_dsd(
    diameter_mm: FloatOrArray, rain_rate_mm_per_hr: float
) -> FloatOrArray:
    """Drops per unit volume and diameter [1/(m^3 mm)], Marshall and Palmer (1948).

    ``N(D) = N_0 exp(-Lambda D)`` with ``N_0 = 0.08 cm^-4 = 8000 m^-3 mm^-1``
    and ``Lambda = 41 R^-0.21 cm^-1 = 4.1 R^-0.21 mm^-1`` (their equations
    (1)-(3)).  Their observations fall short of it below about 1.5 mm.
    """
    if rain_rate_mm_per_hr <= 0.0:
        raise ValueError("rain_rate_mm_per_hr must be positive")
    slope = 4.1 * rain_rate_mm_per_hr**-0.21
    d = np.asarray(diameter_mm, dtype=float)
    return 8000.0 * np.exp(-slope * d)  # type: ignore[no-any-return]


def terminal_fall_speed_mps(
    diameter_mm: FloatOrArray, *, air_density_ratio: float = 1.0
) -> FloatOrArray:
    """A raindrop's terminal fall speed [m/s], Tsikoudi et al. (2025), eq. (7).

    In metres: ``1.2e8 (D/2)^2`` below 0.11 mm, ``8333 D/2 - 0.0833`` up to
    0.86 mm and ``9.65 - 10.3 exp(-600 D)`` above, which they attribute to
    Frisch et al. (1995) and Atlas et al. (1973).  ``air_density_ratio`` is
    the sea-level air density over the air's; the speeds scale as its 0.4th
    power.
    """
    d = np.asarray(diameter_mm, dtype=float) * 1.0e-3
    speed = np.where(
        d < 0.11e-3,
        1.2e8 * (d / 2.0) ** 2,
        np.where(
            d <= 0.86e-3, 8333.0 * d / 2.0 - 0.0833, 9.65 - 10.3 * np.exp(-600.0 * d)
        ),
    )
    return speed * air_density_ratio**0.4  # type: ignore[no-any-return]


@dataclass(frozen=True)
class RainScattering:
    """Rain's scattering at one rain rate, frequency and temperature.

    ``volume_reflectivity_per_m`` is ``eta``, the radar cross section per unit
    volume.  ``equivalent_reflectivity_mm6_per_m3`` is the reflectivity factor
    a Rayleigh scatterer with ``|K|^2 = dielectric_reference`` would need for
    the same ``eta``: ``Z_e = lambda^4 eta / (pi^5 |K|^2)``.  The specific
    attenuation is one-way, from the drops' extinction.  The fall speeds are
    weighted by each diameter's share of ``eta``, as a Doppler spectrum weighs
    them.  ``water_flux_mm_per_hr`` is the rain rate the drop sizes carry at
    those fall speeds, which need not equal the rain rate the distribution was
    set for.
    """

    rain_rate_mm_per_hr: float
    frequency_hz: float
    temperature_c: float
    volume_reflectivity_per_m: float
    equivalent_reflectivity_mm6_per_m3: float
    specific_attenuation_db_per_km: float
    mean_fall_speed_mps: float
    rms_fall_speed_mps: float
    water_flux_mm_per_hr: float

    @property
    def volume_reflectivity_db(self) -> float:
        """``10 log10(eta / (1 m^-1))`` [dB]."""
        return 10.0 * math.log10(self.volume_reflectivity_per_m)

    @property
    def equivalent_reflectivity_dbz(self) -> float:
        """``10 log10(Z_e / (1 mm^6 m^-3))`` [dBZ]."""
        return 10.0 * math.log10(self.equivalent_reflectivity_mm6_per_m3)


@functools.lru_cache(maxsize=32)
def _drop_cross_sections(
    frequency_hz: float,
    temperature_c: float,
    diameter_max_mm: float,
    diameter_step_mm: float,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Midpoint diameters [mm], backscatter and extinction cross sections [m^2]."""
    count = int(round(diameter_max_mm / diameter_step_mm))
    diameter_mm = (np.arange(count, dtype=np.float64) + 0.5) * diameter_step_mm
    wavelength_m = SPEED_OF_LIGHT / frequency_hz
    m = cmath.sqrt(water_permittivity(frequency_hz, temperature_c))
    area_m2 = math.pi * (diameter_mm * 1.0e-3) ** 2 / 4.0
    q = [mie_efficiencies(m, math.pi * d * 1.0e-3 / wavelength_m) for d in diameter_mm]
    backscatter = area_m2 * np.array([e.backscatter for e in q], dtype=np.float64)
    extinction = area_m2 * np.array([e.extinction for e in q], dtype=np.float64)
    return diameter_mm, backscatter, extinction


def rain_scattering(
    rain_rate_mm_per_hr: float,
    frequency_hz: float,
    *,
    temperature_c: float,
    air_density_ratio: float = 1.0,
    dielectric_reference: float = DIELECTRIC_REFERENCE,
    diameter_max_mm: float = 10.0,
    diameter_step_mm: float = 0.01,
) -> RainScattering:
    """Rain's reflectivity, attenuation and fall speeds, Mie over Marshall-Palmer.

    Integrates the Mie cross sections of water spheres at ``temperature_c``
    over the Marshall-Palmer distribution for ``rain_rate_mm_per_hr``, by the
    midpoint rule up to ``diameter_max_mm``.  The defaults reach 0.01 dB in
    ``eta`` from 1 to 100 mm/h at 77 GHz (the tests check it).
    ``air_density_ratio`` affects the fall speeds and the water flux only.
    """
    diameter_mm, backscatter, extinction = _drop_cross_sections(
        float(frequency_hz),
        float(temperature_c),
        float(diameter_max_mm),
        float(diameter_step_mm),
    )
    drops = np.asarray(marshall_palmer_dsd(diameter_mm, rain_rate_mm_per_hr))
    weight = drops * backscatter * diameter_step_mm
    eta = float(np.sum(weight))
    wavelength_m = SPEED_OF_LIGHT / frequency_hz
    z_e = wavelength_m**4 * eta / (math.pi**5 * dielectric_reference) * 1.0e18
    gamma = 10.0 * math.log10(math.e) * 1.0e3
    gamma *= float(np.sum(drops * extinction * diameter_step_mm))
    speed = np.asarray(
        terminal_fall_speed_mps(diameter_mm, air_density_ratio=air_density_ratio)
    )
    mean_speed = float(np.sum(weight * speed)) / eta
    rms_speed = math.sqrt(float(np.sum(weight * speed**2)) / eta)
    volume_m3 = math.pi / 6.0 * (diameter_mm * 1.0e-3) ** 3
    flux = 3.6e6 * float(np.sum(drops * volume_m3 * speed * diameter_step_mm))
    return RainScattering(
        rain_rate_mm_per_hr=rain_rate_mm_per_hr,
        frequency_hz=frequency_hz,
        temperature_c=temperature_c,
        volume_reflectivity_per_m=eta,
        equivalent_reflectivity_mm6_per_m3=z_e,
        specific_attenuation_db_per_km=gamma,
        mean_fall_speed_mps=mean_speed,
        rms_fall_speed_mps=rms_speed,
        water_flux_mm_per_hr=flux,
    )
