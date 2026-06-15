"""FMCW waveform models."""

from __future__ import annotations

from dataclasses import dataclass

from radar_range.constants import SPEED_OF_LIGHT_M_PER_S


@dataclass(frozen=True)
class FmcwWaveform:
    """Parameters that determine FMCW processing gain and range scale.

    The default noise-bandwidth convention in this toolbox is to use the ADC
    sample rate as the receiver noise bandwidth. If your implementation has a
    known equivalent noise bandwidth after analog/digital filtering, set
    ``adc_noise_bandwidth_hz`` explicitly.
    """

    name: str
    num_adc_samples: int
    sample_rate_hz: float
    bandwidth_hz: float
    chirps_per_tx: int = 1
    num_tx: int = 1
    ramp_time_s: float | None = None
    chirp_repetition_time_s: float | None = None
    adc_noise_bandwidth_hz: float | None = None

    def __post_init__(self) -> None:
        if self.num_adc_samples < 1:
            raise ValueError("num_adc_samples must be at least one")
        if self.sample_rate_hz <= 0.0:
            raise ValueError("sample_rate_hz must be positive")
        if self.bandwidth_hz <= 0.0:
            raise ValueError("bandwidth_hz must be positive")
        if self.chirps_per_tx < 1 or self.num_tx < 1:
            raise ValueError("chirps_per_tx and num_tx must be at least one")
        if self.ramp_time_s is not None and self.ramp_time_s <= 0.0:
            raise ValueError("ramp_time_s must be positive when set")
        if (
            self.chirp_repetition_time_s is not None
            and self.chirp_repetition_time_s <= 0.0
        ):
            raise ValueError("chirp_repetition_time_s must be positive when set")
        if (
            self.adc_noise_bandwidth_hz is not None
            and self.adc_noise_bandwidth_hz <= 0.0
        ):
            raise ValueError("adc_noise_bandwidth_hz must be positive when set")

    @property
    def adc_duration_s(self) -> float:
        """Duration of the sampled part of one chirp."""

        return self.num_adc_samples / self.sample_rate_hz

    @property
    def effective_ramp_time_s(self) -> float:
        """Ramp time used for slope calculations.

        If ``ramp_time_s`` is not supplied, the sampled ADC duration is used.
        """

        return self.ramp_time_s if self.ramp_time_s is not None else self.adc_duration_s

    @property
    def sweep_slope_hz_per_s(self) -> float:
        """Linear FMCW sweep slope."""

        return self.bandwidth_hz / self.effective_ramp_time_s

    @property
    def range_resolution_m(self) -> float:
        """Nominal range resolution c/(2B)."""

        return SPEED_OF_LIGHT_M_PER_S / (2.0 * self.bandwidth_hz)

    @property
    def max_unambiguous_range_m(self) -> float:
        """Beat-frequency-limited range using fs/2 as the maximum beat frequency."""

        return SPEED_OF_LIGHT_M_PER_S * (self.sample_rate_hz / 2.0) / (
            2.0 * self.sweep_slope_hz_per_s
        )

    @property
    def noise_bandwidth_hz(self) -> float:
        """Noise bandwidth used by the thermal-noise calculation."""

        if self.adc_noise_bandwidth_hz is not None:
            return self.adc_noise_bandwidth_hz
        return self.sample_rate_hz
