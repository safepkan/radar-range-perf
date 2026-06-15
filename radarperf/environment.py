"""Propagation and volume-clutter environment models.

Two effects are modelled: excess two-way path loss (gaseous + rain) and rain
volume clutter (which both attenuates at long range and raises the effective
floor at short range).

Rain attenuation uses the ITU-R P.838 power law ``gamma = k * R**alpha``
[dB/km]; the default ``k``/``alpha`` are approximate values near 77 GHz and
should be replaced with the exact P.838 coefficients for your band and
polarisation.

.. warning::

   The rain *clutter* model uses the Probert-Jones distributed-target volume
   with a Marshall-Palmer Z-R relation and a Rayleigh reflectivity.  At 77 GHz
   raindrops are not Rayleigh scatterers (Mie regime), so the clutter
   reflectivity is approximate.  It is wired in so the signal-to-clutter path
   exists and is overridable; calibrate ``dielectric_factor`` and the Z-R
   coefficients against data before trusting absolute numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, cast

import numpy as np

from .geometry import Geometry
from .protocols import Antenna, Environment, Waveform
from .units import SPEED_OF_LIGHT, FloatOrArray


@dataclass(frozen=True)
class FreeSpace:
    """No excess loss and no clutter -- the default environment."""

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        return 0.0

    def clutter_rcs_m2(
        self, geometry: Geometry, waveform: Waveform, antenna: Antenna
    ) -> FloatOrArray:
        return 0.0


@dataclass(frozen=True)
class Atmosphere:
    """Clear-air gaseous attenuation as a constant specific attenuation.

    ``specific_attenuation_db_per_km`` is the one-way value (~0.4-0.7 dB/km is
    typical around 77 GHz; see ITU-R P.676 for the detailed line model).
    """

    specific_attenuation_db_per_km: float = 0.5

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        range_km = np.asarray(geometry.range_m, dtype=float) / 1000.0
        return cast(FloatOrArray, 2.0 * self.specific_attenuation_db_per_km * range_km)

    def clutter_rcs_m2(
        self, geometry: Geometry, waveform: Waveform, antenna: Antenna
    ) -> FloatOrArray:
        return 0.0


@dataclass(frozen=True)
class Rain:
    """Rain attenuation (P.838 power law) plus approximate volume clutter."""

    rain_rate_mm_per_hr: float
    k: float = 0.95
    alpha: float = 0.74
    z_a: float = 200.0  # Marshall-Palmer Z = z_a * R**z_b  [mm^6/m^3]
    z_b: float = 1.6
    dielectric_factor: float = 0.93  # |K|^2 for water (Rayleigh; ~lower at 77 GHz)
    beam_fill_factor: float = math.pi / (8.0 * math.log(2.0))

    def specific_attenuation_db_per_km(self) -> float:
        """One-way rain specific attenuation [dB/km]."""
        return float(self.k * self.rain_rate_mm_per_hr**self.alpha)

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        range_km = np.asarray(geometry.range_m, dtype=float) / 1000.0
        return cast(
            FloatOrArray, 2.0 * self.specific_attenuation_db_per_km() * range_km
        )

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
