"""Convenience presets for early trade studies.

The values here are intentionally shallow wrappers around public headline
specifications. Treat them as starting points, not sign-off data. For controlled
projects, copy the preset into project-specific configuration and replace the
headline values with measured or controlled-datasheet values.
"""

from __future__ import annotations

from typing import Any

from radar_range.antennas import ConstantGainAntenna
from radar_range.hardware import RadarHardware
from radar_range.processing import CombiningMode, ProcessingModel

TI_AWR1243_URL = "https://www.ti.com/product/AWR1243"
TI_AWR2243_URL = "https://www.ti.com/product/AWR2243"
TI_AWR2E44P_URL = "https://www.ti.com/lit/ds/symlink/awr2944p.pdf"
HUBER_SUHNER_THIS_II_URL = (
    "https://www.hubersuhner.com/en/shop/product/antennas/antennas/radar/"
    "85214625/sencity-this-ii-radar-antenna"
)
HUBER_SUHNER_FARAD_IV_URL = (
    "https://www.hubersuhner.com/en/shop/product/antennas/antennas/radar/"
    "85270538/sencity-farad-iv-radar-antenna"
)


def ti_awr1243(
    tx_antenna_gain_dbi: float = 0.0,
    rx_antenna_gain_dbi: float = 0.0,
) -> RadarHardware:
    """TI AWR1243 headline preset.

    Uses 12 dBm TX power and the more conservative 15 dB NF headline for the
    77-81 GHz part of the band.
    """

    return RadarHardware(
        name="TI AWR1243 headline preset",
        center_frequency_hz=77.0e9,
        tx_power_dbm=12.0,
        noise_figure_db=15.0,
        tx_count=3,
        rx_count=4,
        tx_antenna=ConstantGainAntenna(tx_antenna_gain_dbi),
        rx_antenna=ConstantGainAntenna(rx_antenna_gain_dbi),
        source_url=TI_AWR1243_URL,
        notes="Public headline values; verify against the exact datasheet revision.",
    )


def ti_awr2243(
    tx_antenna_gain_dbi: float = 0.0,
    rx_antenna_gain_dbi: float = 0.0,
) -> RadarHardware:
    """TI AWR2243 headline preset."""

    return RadarHardware(
        name="TI AWR2243 headline preset",
        center_frequency_hz=77.0e9,
        tx_power_dbm=13.0,
        noise_figure_db=13.0,
        tx_count=3,
        rx_count=4,
        tx_antenna=ConstantGainAntenna(tx_antenna_gain_dbi),
        rx_antenna=ConstantGainAntenna(rx_antenna_gain_dbi),
        source_url=TI_AWR2243_URL,
        notes="Public headline values; verify against the exact datasheet revision.",
    )


def ti_awr2e44p(
    tx_antenna_gain_dbi: float = 0.0,
    rx_antenna_gain_dbi: float = 0.0,
) -> RadarHardware:
    """TI AWR2E44P headline preset."""

    return RadarHardware(
        name="TI AWR2E44P headline preset",
        center_frequency_hz=77.0e9,
        tx_power_dbm=13.5,
        noise_figure_db=11.0,
        tx_count=4,
        rx_count=4,
        tx_antenna=ConstantGainAntenna(tx_antenna_gain_dbi),
        rx_antenna=ConstantGainAntenna(rx_antenna_gain_dbi),
        source_url=TI_AWR2E44P_URL,
        notes="Public headline values; verify against the exact datasheet revision.",
    )


def infineon_ctrx8188f(
    tx_power_dbm: float = 14.5,
    noise_figure_db: float = 9.7,
    tx_antenna_gain_dbi: float = 0.0,
    rx_antenna_gain_dbi: float = 0.0,
    tx_count: int = 8,
    rx_count: int = 8,
) -> RadarHardware:
    """Infineon CTRX8188F controlled-datasheet typical-value preset.

    Defaults use the local controlled datasheet values supplied by the project:
    14.5 dBm typical output power and 9.7 dB typical receiver noise figure.
    Override these arguments for measured data or a different datasheet corner.
    """

    return RadarHardware(
        name="Infineon CTRX8188F typical preset",
        center_frequency_hz=77.0e9,
        tx_power_dbm=tx_power_dbm,
        noise_figure_db=noise_figure_db,
        tx_count=tx_count,
        rx_count=rx_count,
        tx_antenna=ConstantGainAntenna(tx_antenna_gain_dbi),
        rx_antenna=ConstantGainAntenna(rx_antenna_gain_dbi),
        notes=(
            "Defaults are controlled-datasheet typical values supplied by the "
            "project; replace with measured or corner values when needed."
        ),
    )


def awr2e44p_ddma_processing(
    *,
    rx_mode: CombiningMode = "noncoherent",
    subband_mode: CombiningMode = "noncoherent",
    rx_channels: int = 4,
    detector_subbands: int = 6,
    active_tx_subbands: int = 4,
    **kwargs: Any,
) -> ProcessingModel:
    """Processing preset for the AWR2E44P DDMA SDK-style detector.

    The default models detection after noncoherent summation over all four RX
    channels and six DDMA subbands, of which four are active target-bearing TX
    subbands and two are empty/noise-only subbands. This gives 24 detector looks
    and 16 target-bearing signal looks.

    Set ``rx_mode='coherent'`` to model coherent RX summation followed by
    subband summation. Set ``subband_mode='coherent'`` to model coherent
    summation over only the active TX/subbands; empty subbands are not included
    in coherent summation. Additional :class:`ProcessingModel` keyword arguments
    such as window, straddling, CFAR, and implementation losses are forwarded.
    """

    if subband_mode == "coherent":
        subband_count = active_tx_subbands
        signal_subband_count = None
    else:
        subband_count = detector_subbands
        signal_subband_count = active_tx_subbands

    return ProcessingModel.with_mimo_combining(
        rx_channels=rx_channels,
        tx_or_subband_bins=subband_count,
        rx_mode=rx_mode,
        tx_or_subband_mode=subband_mode,
        signal_tx_or_subband_bins=signal_subband_count,
        **kwargs,
    )


def huber_suhner_this_ii_gain() -> ConstantGainAntenna:
    """Boresight directivity preset for SENCITY THIS-II, per channel."""

    return ConstantGainAntenna(16.4)


def huber_suhner_farad_iv_gain() -> ConstantGainAntenna:
    """Boresight directivity preset for SENCITY FARAD-IV, per channel."""

    return ConstantGainAntenna(15.0)
