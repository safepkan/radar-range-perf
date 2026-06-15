"""Hardware and RF-chain models."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from radar_range.antennas import AntennaModel, ConstantGainAntenna
from radar_range.constants import SPEED_OF_LIGHT_M_PER_S
from radar_range.units import db_to_linear, dbm_to_w


def _constant_zero_gain() -> ConstantGainAntenna:
    return ConstantGainAntenna(0.0)


@dataclass(frozen=True)
class RadarHardware:
    """RF hardware parameters for a monostatic FMCW radar.

    ``tx_power_dbm`` is interpreted as power per active transmitter. Multi-chip
    or MIMO systems should normally use the same per-channel value and express
    coherent virtual-array gain through :class:`radar_range.processing.ProcessingModel`.
    """

    name: str
    center_frequency_hz: float = 77.0e9
    tx_power_dbm: float = 12.0
    noise_figure_db: float = 12.0
    tx_count: int = 1
    rx_count: int = 1
    tx_antenna: AntennaModel = field(default_factory=_constant_zero_gain)
    rx_antenna: AntennaModel = field(default_factory=_constant_zero_gain)
    tx_loss_db: float = 0.0
    rx_loss_db: float = 0.0
    shared_system_loss_db: float = 0.0
    source_url: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.center_frequency_hz <= 0.0:
            raise ValueError("center_frequency_hz must be positive")
        if self.tx_count < 1 or self.rx_count < 1:
            raise ValueError("tx_count and rx_count must be at least one")

    @property
    def wavelength_m(self) -> float:
        """Carrier wavelength."""

        return SPEED_OF_LIGHT_M_PER_S / self.center_frequency_hz

    @property
    def tx_power_w(self) -> float:
        """Per-transmitter output power in watts."""

        return float(dbm_to_w(self.tx_power_dbm))

    @property
    def noise_factor(self) -> float:
        """Receiver noise factor as a linear ratio."""

        return float(db_to_linear(self.noise_figure_db))

    @property
    def total_frontend_loss_db(self) -> float:
        """Sum of TX feed, RX feed, and shared implementation losses."""

        return self.tx_loss_db + self.rx_loss_db + self.shared_system_loss_db

    @property
    def virtual_channel_count(self) -> int:
        """Nominal number of virtual channels for TDM-MIMO metadata."""

        return int(np.multiply(self.tx_count, self.rx_count))
