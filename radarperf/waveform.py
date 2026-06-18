"""FMCW waveform / mode description.

A waveform is parametrised by the quantities a fast-chirp FMCW radar actually
programs -- centre frequency, swept bandwidth, ADC sample rate, samples per
chirp and chirps per CPI -- and exposes the derived range resolution, coherent
dwell time and, when a chirp repetition time is supplied, velocity resolution
and ambiguity figures.

The dwell time used for SNR is the total *active sampling* time,
``n_chirps * n_samples / sample_rate``; in the energy form of the FMCW radar
equation this is exactly the coherent integration time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .units import SPEED_OF_LIGHT


@dataclass(frozen=True)
class FmcwWaveform:
    """A fast-chirp FMCW waveform / mode."""

    center_frequency_hz: float
    bandwidth_hz: float
    sample_rate_hz: float
    n_samples: int
    n_chirps: int
    chirp_repetition_time_s: float = math.nan
    chirp_slope_hz_per_s: float = 0.0
    noise_bandwidth_hz: float = 0.0

    def __post_init__(self) -> None:
        positive = {
            "center_frequency_hz": self.center_frequency_hz,
            "bandwidth_hz": self.bandwidth_hz,
            "sample_rate_hz": self.sample_rate_hz,
        }
        for field_name, value in positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{field_name} must be finite and positive")
        if not math.isnan(self.chirp_repetition_time_s) and (
            not math.isfinite(self.chirp_repetition_time_s)
            or self.chirp_repetition_time_s <= 0.0
        ):
            raise ValueError(
                "chirp_repetition_time_s must be positive, or NaN when unused"
            )
        if self.n_samples < 1 or self.n_chirps < 1:
            raise ValueError("n_samples and n_chirps must be >= 1")
        if self.noise_bandwidth_hz < 0.0:
            raise ValueError("noise_bandwidth_hz must be non-negative (0 = auto)")

    # --- core derived quantities ---------------------------------------

    @property
    def wavelength_m(self) -> float:
        return SPEED_OF_LIGHT / self.center_frequency_hz

    @property
    def adc_duration_s(self) -> float:
        """Active ADC window within one chirp [s]."""
        return self.n_samples / self.sample_rate_hz

    @property
    def dwell_time_s(self) -> float:
        """Total coherent active-sampling time over the CPI [s]."""
        return self.n_chirps * self.adc_duration_s

    @property
    def cpi_duration_s(self) -> float:
        """Coherent processing interval, including chirp dead time [s].

        Returns NaN when ``chirp_repetition_time_s`` is unset.
        """
        return self.n_chirps * self.chirp_repetition_time_s

    @property
    def effective_slope_hz_per_s(self) -> float:
        """Chirp slope; falls back to ``bandwidth / adc_duration`` if unset."""
        if self.chirp_slope_hz_per_s > 0.0:
            return self.chirp_slope_hz_per_s
        return self.bandwidth_hz / self.adc_duration_s

    @property
    def effective_noise_bandwidth_hz(self) -> float:
        """Noise-equivalent bandwidth per complex sample [Hz].

        Defaults to the ADC sample rate (an ideal brick-wall anti-alias filter);
        set ``noise_bandwidth_hz`` to override when the receive chain's effective
        noise bandwidth differs.
        """
        if self.noise_bandwidth_hz > 0.0:
            return self.noise_bandwidth_hz
        return self.sample_rate_hz

    # --- resolution and ambiguity --------------------------------------

    @property
    def range_resolution_m(self) -> float:
        return SPEED_OF_LIGHT / (2.0 * self.bandwidth_hz)

    @property
    def max_unambiguous_range_m(self) -> float:
        """Range at which the beat frequency reaches half the sample rate [m]."""
        return (
            SPEED_OF_LIGHT * self.sample_rate_hz / (4.0 * self.effective_slope_hz_per_s)
        )

    @property
    def velocity_resolution_mps(self) -> float:
        """Doppler-bin velocity resolution [m/s], or NaN if CRT is unset."""
        return self.wavelength_m / (2.0 * self.cpi_duration_s)

    @property
    def max_unambiguous_velocity_mps(self) -> float:
        """Plus/minus this; full span is twice the value, or NaN if CRT is unset."""
        return self.wavelength_m / (4.0 * self.chirp_repetition_time_s)

    @classmethod
    def from_slope(
        cls,
        center_frequency_hz: float,
        chirp_slope_hz_per_s: float,
        sample_rate_hz: float,
        n_samples: int,
        n_chirps: int,
        chirp_repetition_time_s: float = math.nan,
    ) -> "FmcwWaveform":
        """Build from chirp slope instead of bandwidth (bandwidth derived)."""
        bandwidth = chirp_slope_hz_per_s * (n_samples / sample_rate_hz)
        return cls(
            center_frequency_hz=center_frequency_hz,
            bandwidth_hz=bandwidth,
            sample_rate_hz=sample_rate_hz,
            n_samples=n_samples,
            n_chirps=n_chirps,
            chirp_repetition_time_s=chirp_repetition_time_s,
            chirp_slope_hz_per_s=chirp_slope_hz_per_s,
        )
