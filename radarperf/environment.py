"""Propagation and volume-clutter environment models.

Two effects are modelled: excess two-way path loss (gaseous + rain) and rain
volume clutter (which both attenuates at long range and raises the effective
floor at short range).

Gaseous attenuation follows ITU-R P.676-13 and rain attenuation the ITU-R
P.838-3 power law ``gamma = k * R**alpha`` [dB/km]; both are implemented in
``radarperf.itu``.

Warning: the rain *clutter* model is a placeholder, and it overstates rain's
level in three ways.

* Reflectivity.  It uses ``Z = 200 R**1.6``, the relation usually called
  Marshall-Palmer, with Rayleigh scattering and ``|K|^2 = 0.93``, the usual
  values for water at centimetre wavelengths.  At 77 GHz raindrops are Mie
  scatterers.  ``radarperf.rain`` computes the reflectivity from Mie
  scattering over Marshall-Palmer (1948) drop sizes.  At 77 GHz and 10
  degrees C, ``200 R**1.6`` overstates it by 3.7 dB at 1 mm/h, 11.9 dB at
  10 mm/h and 21.8 dB at 100 mm/h (docs/rain_clutter.md).
* Volume.  It takes the Probert-Jones (1962) volume from the receive
  antenna's beamwidths, as if transmit and receive shared one beam, over a
  range cell of ``c / 2B``.  That leaves out the range window's widening and
  any difference between the transmit and receive patterns.
* Doppler.  The engine gives the clutter the target's coherent gain, as if
  all of rain's power fell in the target's range-Doppler cell.  Rain spreads
  over a band of Doppler bins, and a target outside that band does not meet
  it at all.  Inside the band the level is overstated by about the number of
  bins the band spans.

The model is wired in so that the signal-to-clutter path exists and can be
overridden.  Do not use its numbers in studies.  Passing a ``Rain`` to the
engine brings its clutter with it.  For attenuation alone, add
``Rain.specific_attenuation_db_per_km`` into an ``Atmosphere``, as the Lannik
Psi studies do.  docs/rain_clutter.md builds the better model in steps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, cast

import numpy as np

from .geometry import Geometry
from .itu import (
    gaseous_specific_attenuation_db_per_km,
    rain_coefficients,
    reference_atmosphere,
)
from .protocols import Antenna, Environment, Waveform
from .units import SPEED_OF_LIGHT, FloatOrArray


@dataclass(frozen=True)
class FreeSpace:
    """No excess loss and no clutter -- the default environment.

    Useful for idealised comparisons and hand calculations; at 77 GHz the
    clear-air loss is not zero (see ``Atmosphere``).
    """

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        return 0.0

    def clutter_rcs_m2(
        self, geometry: Geometry, waveform: Waveform, antenna: Antenna
    ) -> FloatOrArray:
        return 0.0


@dataclass(frozen=True)
class Atmosphere:
    """Clear-air gaseous attenuation as a constant specific attenuation.

    ``specific_attenuation_db_per_km`` is the one-way value; the two-way loss is
    ``2 * gamma * R``, independent of frequency and altitude.  The default, 0.35
    dB/km, is ITU-R P.676-13 at 76.5 GHz for its standard sea-level atmosphere
    (1013.25 hPa, 15 degC, 7.5 g/m^3 water vapour), rounded.  Use ``itu_p676``
    for other conditions or frequencies, or ``itu_reference`` for the ITU-R
    reference atmosphere at a height; ``docs/losses.md`` tabulates a few.
    """

    specific_attenuation_db_per_km: float = 0.35

    @classmethod
    def itu_p676(
        cls,
        frequency_hz: float = 76.5e9,
        *,
        temperature_c: float = 15.0,
        pressure_hpa: float = 1013.25,
        water_vapour_density_g_m3: float = 7.5,
    ) -> "Atmosphere":
        """Build from ITU-R P.676-13 (Annex 1) for the given conditions.

        ``pressure_hpa`` is the total barometric pressure.  The value is
        computed once, at ``frequency_hz``; it is not re-evaluated at the
        waveform's frequency.
        """
        oxygen, water_vapour = gaseous_specific_attenuation_db_per_km(
            frequency_hz,
            temperature_c=temperature_c,
            pressure_hpa=pressure_hpa,
            water_vapour_density_g_m3=water_vapour_density_g_m3,
        )
        return cls(oxygen + water_vapour)

    @classmethod
    def itu_reference(
        cls, height_m: float, frequency_hz: float = 76.5e9
    ) -> "Atmosphere":
        """Build from ITU-R P.676-13 in the ITU-R P.835-7 reference atmosphere.

        The conditions at ``height_m`` (geometric, above mean sea level) come
        from ``radarperf.itu.reference_atmosphere``.  The path is taken as
        horizontal at that height; a slant path would need the attenuation
        integrated over height.
        """
        conditions = reference_atmosphere(height_m)
        return cls.itu_p676(
            frequency_hz,
            temperature_c=conditions.temperature_c,
            pressure_hpa=conditions.pressure_hpa,
            water_vapour_density_g_m3=conditions.water_vapour_density_g_m3,
        )

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        range_km = np.asarray(geometry.range_m, dtype=float) / 1000.0
        return cast(FloatOrArray, 2.0 * self.specific_attenuation_db_per_km * range_km)

    def clutter_rcs_m2(
        self, geometry: Geometry, waveform: Waveform, antenna: Antenna
    ) -> FloatOrArray:
        return 0.0


@dataclass(frozen=True)
class Rain:
    """Rain attenuation (ITU-R P.838-3) plus placeholder volume clutter.

    The clutter overstates rain's level; the module docstring says by how
    much and why.

    By default ``k`` and ``alpha`` come from ITU-R P.838-3 at the waveform's
    centre frequency for a horizontal path, with ``polarization_tilt_deg`` 0
    for horizontal, 90 for vertical and 45 for circular polarization.  Set
    ``k`` and ``alpha`` to override both.
    """

    rain_rate_mm_per_hr: float
    polarization_tilt_deg: float = 0.0
    k: float | None = None
    alpha: float | None = None
    z_a: float = 200.0  # Marshall-Palmer Z = z_a * R**z_b  [mm^6/m^3]
    z_b: float = 1.6
    dielectric_factor: float = 0.93  # |K|^2 for water (Rayleigh, cm wavelengths)
    beam_fill_factor: float = math.pi / (8.0 * math.log(2.0))  # Probert-Jones

    def __post_init__(self) -> None:
        if (self.k is None) != (self.alpha is None):
            raise ValueError("set both k and alpha, or neither")

    def coefficients(self, frequency_hz: float) -> tuple[float, float]:
        """Power-law ``(k, alpha)``: the overrides, or P.838-3 at this frequency."""
        if self.k is not None and self.alpha is not None:
            return self.k, self.alpha
        return rain_coefficients(
            frequency_hz, polarization_tilt_deg=self.polarization_tilt_deg
        )

    def specific_attenuation_db_per_km(self, frequency_hz: float) -> float:
        """One-way rain specific attenuation [dB/km] at ``frequency_hz``."""
        k, alpha = self.coefficients(frequency_hz)
        return float(k * self.rain_rate_mm_per_hr**alpha)

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        range_km = np.asarray(geometry.range_m, dtype=float) / 1000.0
        gamma = self.specific_attenuation_db_per_km(waveform.center_frequency_hz)
        return cast(FloatOrArray, 2.0 * gamma * range_km)

    def clutter_rcs_m2(
        self, geometry: Geometry, waveform: Waveform, antenna: Antenna
    ) -> FloatOrArray:
        bw_az = antenna.beamwidth_az_deg
        bw_el = antenna.beamwidth_el_deg
        if math.isnan(bw_az) or math.isnan(bw_el):
            raise ValueError(
                "Rain clutter needs finite antenna beamwidths; set "
                "beamwidth_az_deg / beamwidth_el_deg on the antenna."
            )
        # Marshall-Palmer reflectivity factor, converted mm^6/m^3 -> m^3.
        z_si = self.z_a * self.rain_rate_mm_per_hr**self.z_b * 1.0e-18
        lam = waveform.wavelength_m
        eta = math.pi**5 * self.dielectric_factor * z_si / lam**4  # [1/m]
        # Probert-Jones illuminated volume.
        theta_az = math.radians(bw_az)
        theta_el = math.radians(bw_el)
        delta_r = SPEED_OF_LIGHT / (2.0 * waveform.bandwidth_hz)
        range_m = np.asarray(geometry.range_m, dtype=float)
        volume = self.beam_fill_factor * theta_az * theta_el * range_m**2 * delta_r
        return cast(FloatOrArray, eta * volume)


class CompositeEnvironment:
    """Sum the losses and clutter of several environment models."""

    def __init__(self, models: Sequence[Environment]) -> None:
        self._models = tuple(models)

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        total = np.zeros(())
        for model in self._models:
            total = total + np.asarray(
                model.two_way_loss_db(geometry, waveform), dtype=float
            )
        return cast(FloatOrArray, total)

    def clutter_rcs_m2(
        self, geometry: Geometry, waveform: Waveform, antenna: Antenna
    ) -> FloatOrArray:
        total = np.zeros(())
        for model in self._models:
            total = total + np.asarray(
                model.clutter_rcs_m2(geometry, waveform, antenna), dtype=float
            )
        return cast(FloatOrArray, total)
