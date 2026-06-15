"""Radar range-equation and SNR calculations."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from radar_range.constants import BOLTZMANN_J_PER_K, STANDARD_TEMPERATURE_K
from radar_range.environment import EnvironmentModel
from radar_range.hardware import RadarHardware
from radar_range.processing import ProcessingModel
from radar_range.target import PointTarget, TargetModel
from radar_range.types import ArrayLikeFloat, FloatArray, as_float_array
from radar_range.units import db_to_linear, linear_to_db
from radar_range.waveform import FmcwWaveform


@dataclass(frozen=True)
class RadarScenario:
    """Complete inputs needed for a range-performance calculation."""

    hardware: RadarHardware
    waveform: FmcwWaveform
    processing: ProcessingModel = field(default_factory=ProcessingModel)
    target: TargetModel = field(default_factory=lambda: PointTarget(1.0))
    environment: EnvironmentModel = field(default_factory=EnvironmentModel.clear)


@dataclass(frozen=True)
class SnrResult:
    """Detailed output from :func:`calculate_snr`.

    ``snr_linear`` is the total detector signal-energy SNR after coherent gain
    and noncoherent signal-energy summation. ``detector_looks`` separately
    records the number of square-law looks that determine the detector degrees
    of freedom. This avoids overloading SNR with distribution-shape information.
    """

    range_m: FloatArray
    azimuth_rad: FloatArray
    elevation_rad: FloatArray
    tx_gain_db: FloatArray
    rx_gain_db: FloatArray
    rcs_sqm: FloatArray
    two_way_attenuation_db: FloatArray
    received_power_w: FloatArray
    thermal_noise_power_w: float
    equivalent_noise_after_processing_w: float
    clutter_power_w: FloatArray
    coherent_processing_gain_linear: float
    noncoherent_signal_gain_linear: float
    processing_gain_linear: float
    detector_looks: int
    signal_looks: int
    single_look_snr_linear: FloatArray
    snr_linear: FloatArray
    sinr_linear: FloatArray

    @property
    def snr_db(self) -> FloatArray:
        """Thermal-noise-limited post-processing detector SNR in dB."""

        return linear_to_db(self.snr_linear, floor=1.0e-300)

    @property
    def sinr_db(self) -> FloatArray:
        """Post-processing signal-to-noise-plus-clutter ratio in dB."""

        return linear_to_db(self.sinr_linear, floor=1.0e-300)

    @property
    def single_look_snr_db(self) -> FloatArray:
        """Per-target-bearing-look SNR after coherent processing, in dB."""

        return linear_to_db(self.single_look_snr_linear, floor=1.0e-300)

    @property
    def received_power_dbm(self) -> FloatArray:
        """Received target power at the receiver input in dBm."""

        return linear_to_db(self.received_power_w / 1.0e-3, floor=1.0e-300)


def thermal_noise_power_w(
    hardware: RadarHardware,
    waveform: FmcwWaveform,
    environment: EnvironmentModel,
) -> float:
    """Receiver-input equivalent thermal noise power in watts.

    The system temperature convention is

        T_sys = T_antenna + (F - 1) * T0

    so with T_antenna = T0 this reduces to k*T0*B*F.
    """

    receiver_noise_temperature = (hardware.noise_factor - 1.0) * STANDARD_TEMPERATURE_K
    system_temperature_k = (
        environment.antenna_noise_temperature_k + receiver_noise_temperature
    )
    return BOLTZMANN_J_PER_K * waveform.noise_bandwidth_hz * system_temperature_k


def received_power_w(
    hardware: RadarHardware,
    target: TargetModel,
    environment: EnvironmentModel,
    range_m: ArrayLikeFloat,
    azimuth_rad: ArrayLikeFloat = 0.0,
    elevation_rad: ArrayLikeFloat = 0.0,
) -> FloatArray:
    """Target received power from the monostatic radar range equation.

    The equation is

        Pr = Pt * Gt * Gr * lambda^2 * sigma / ((4*pi)^3 * R^4 * L)

    where L includes RF losses and two-way atmospheric attenuation.
    """

    range_array = as_float_array(range_m)
    azimuth = as_float_array(azimuth_rad)
    elevation = as_float_array(elevation_rad)
    range_array, azimuth, elevation = np.broadcast_arrays(
        range_array,
        azimuth,
        elevation,
    )
    if np.any(range_array <= 0.0):
        raise ValueError("range_m must contain only positive values")

    tx_gain_db = hardware.tx_antenna.gain_db(azimuth, elevation)
    rx_gain_db = hardware.rx_antenna.gain_db(azimuth, elevation)
    rcs = target.rcs_sqm(azimuth, elevation)
    two_way_attenuation_db = environment.two_way_path_loss_db(range_array)
    total_loss_linear = db_to_linear(
        hardware.total_frontend_loss_db + two_way_attenuation_db
    )

    numerator = (
        hardware.tx_power_w
        * db_to_linear(tx_gain_db)
        * db_to_linear(rx_gain_db)
        * hardware.wavelength_m**2
        * rcs
    )
    denominator = (4.0 * np.pi) ** 3 * range_array**4 * total_loss_linear
    return numerator / denominator


def calculate_snr(
    scenario: RadarScenario,
    range_m: ArrayLikeFloat,
    azimuth_rad: ArrayLikeFloat = 0.0,
    elevation_rad: ArrayLikeFloat = 0.0,
) -> SnrResult:
    """Calculate target SNR and SINR for scalar or array inputs."""

    range_array = as_float_array(range_m)
    azimuth = as_float_array(azimuth_rad)
    elevation = as_float_array(elevation_rad)
    range_array, azimuth, elevation = np.broadcast_arrays(
        range_array,
        azimuth,
        elevation,
    )

    rx_power = received_power_w(
        scenario.hardware,
        scenario.target,
        scenario.environment,
        range_array,
        azimuth,
        elevation,
    )
    noise_power = thermal_noise_power_w(
        scenario.hardware,
        scenario.waveform,
        scenario.environment,
    )
    coherent_gain = scenario.processing.coherent_gain_linear(scenario.waveform)
    noncoherent_signal_gain = scenario.processing.noncoherent_signal_gain_linear
    detector_signal_gain = scenario.processing.detector_signal_gain_linear(
        scenario.waveform
    )
    clutter_power = scenario.environment.clutter.clutter_power_w(
        range_array,
        azimuth,
        elevation,
        scenario.hardware,
        scenario.waveform,
    )

    if detector_signal_gain > 0.0:
        equivalent_noise_power = noise_power / detector_signal_gain
        single_look_snr = rx_power * coherent_gain / noise_power
        snr = rx_power / equivalent_noise_power
        sinr = rx_power / (equivalent_noise_power + clutter_power)
    else:
        equivalent_noise_power = float("inf")
        single_look_snr = np.zeros_like(rx_power, dtype=float)
        snr = np.zeros_like(rx_power, dtype=float)
        sinr = np.zeros_like(rx_power, dtype=float)

    return SnrResult(
        range_m=range_array,
        azimuth_rad=azimuth,
        elevation_rad=elevation,
        tx_gain_db=scenario.hardware.tx_antenna.gain_db(azimuth, elevation),
        rx_gain_db=scenario.hardware.rx_antenna.gain_db(azimuth, elevation),
        rcs_sqm=scenario.target.rcs_sqm(azimuth, elevation),
        two_way_attenuation_db=scenario.environment.two_way_path_loss_db(range_array),
        received_power_w=rx_power,
        thermal_noise_power_w=noise_power,
        equivalent_noise_after_processing_w=equivalent_noise_power,
        clutter_power_w=clutter_power,
        coherent_processing_gain_linear=coherent_gain,
        noncoherent_signal_gain_linear=noncoherent_signal_gain,
        processing_gain_linear=detector_signal_gain,
        detector_looks=scenario.processing.detector_looks,
        signal_looks=scenario.processing.signal_looks,
        single_look_snr_linear=single_look_snr,
        snr_linear=snr,
        sinr_linear=sinr,
    )
