"""Environment, attenuation, and clutter hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from radar_range.constants import STANDARD_TEMPERATURE_K
from radar_range.hardware import RadarHardware
from radar_range.types import ArrayLikeFloat, FloatArray, as_float_array
from radar_range.waveform import FmcwWaveform


class ClutterModel(Protocol):
    """Protocol for effective clutter power in the detection cell.

    A clutter model should return an equivalent input power in watts competing
    with the target in the same range/Doppler/angle cell. The SNR calculation
    then compares target power with thermal noise after processing plus this
    clutter term.
    """

    def clutter_power_w(
        self,
        range_m: ArrayLikeFloat,
        azimuth_rad: ArrayLikeFloat,
        elevation_rad: ArrayLikeFloat,
        hardware: RadarHardware,
        waveform: FmcwWaveform,
    ) -> FloatArray:
        """Return clutter power in watts."""


@dataclass(frozen=True)
class NoClutter:
    """No-clutter model."""

    def clutter_power_w(
        self,
        range_m: ArrayLikeFloat,
        azimuth_rad: ArrayLikeFloat,
        elevation_rad: ArrayLikeFloat,
        hardware: RadarHardware,
        waveform: FmcwWaveform,
    ) -> FloatArray:
        range_array = as_float_array(range_m)
        azimuth = as_float_array(azimuth_rad)
        elevation = as_float_array(elevation_rad)
        shape = np.broadcast_shapes(range_array.shape, azimuth.shape, elevation.shape)
        return np.zeros(shape, dtype=float)


@dataclass(frozen=True)
class ConstantClutterPower:
    """Constant equivalent clutter power in every detection cell."""

    power_w: float

    def __post_init__(self) -> None:
        if self.power_w < 0.0:
            raise ValueError("power_w must be non-negative")

    def clutter_power_w(
        self,
        range_m: ArrayLikeFloat,
        azimuth_rad: ArrayLikeFloat,
        elevation_rad: ArrayLikeFloat,
        hardware: RadarHardware,
        waveform: FmcwWaveform,
    ) -> FloatArray:
        range_array = as_float_array(range_m)
        azimuth = as_float_array(azimuth_rad)
        elevation = as_float_array(elevation_rad)
        shape = np.broadcast_shapes(range_array.shape, azimuth.shape, elevation.shape)
        return np.full(shape, self.power_w, dtype=float)


@dataclass(frozen=True)
class RainPowerLawAttenuation:
    """Rain attenuation using gamma = k * R**alpha in dB/km.

    The coefficients ``k`` and ``alpha`` are supplied by the caller so the model
    can be aligned with the chosen polarization, frequency, and standard/table.
    """

    rain_rate_mm_per_h: float
    k: float
    alpha: float

    def __post_init__(self) -> None:
        if self.rain_rate_mm_per_h < 0.0:
            raise ValueError("rain_rate_mm_per_h must be non-negative")
        if self.k < 0.0:
            raise ValueError("k must be non-negative")
        if self.alpha < 0.0:
            raise ValueError("alpha must be non-negative")

    @property
    def specific_attenuation_db_per_km(self) -> float:
        """One-way specific attenuation in dB/km."""

        return self.k * self.rain_rate_mm_per_h**self.alpha


@dataclass(frozen=True)
class EnvironmentModel:
    """Propagation and noise environment.

    ``one_way_attenuation_db_per_km`` can represent clear-air, rain, radome, or
    any other range-proportional one-way attenuation. Fixed losses are better
    placed on the hardware model.
    """

    name: str = "clear"
    antenna_noise_temperature_k: float = STANDARD_TEMPERATURE_K
    one_way_attenuation_db_per_km: float = 0.0
    clutter: ClutterModel = field(default_factory=NoClutter)

    def __post_init__(self) -> None:
        if self.antenna_noise_temperature_k < 0.0:
            raise ValueError("antenna_noise_temperature_k must be non-negative")
        if self.one_way_attenuation_db_per_km < 0.0:
            raise ValueError("one_way_attenuation_db_per_km must be non-negative")

    @classmethod
    def clear(cls) -> "EnvironmentModel":
        """Standard clear-air environment with 290 K antenna temperature."""

        return cls()

    @classmethod
    def with_rain_attenuation(
        cls,
        rain: RainPowerLawAttenuation,
        antenna_noise_temperature_k: float = STANDARD_TEMPERATURE_K,
    ) -> "EnvironmentModel":
        """Create an attenuation-only rain environment."""

        return cls(
            name=f"rain {rain.rain_rate_mm_per_h:g} mm/h attenuation only",
            antenna_noise_temperature_k=antenna_noise_temperature_k,
            one_way_attenuation_db_per_km=rain.specific_attenuation_db_per_km,
        )

    def two_way_path_loss_db(self, range_m: ArrayLikeFloat) -> FloatArray:
        """Two-way atmospheric attenuation for the supplied range."""

        return (
            2.0
            * self.one_way_attenuation_db_per_km
            * as_float_array(range_m)
            / 1000.0
        )
