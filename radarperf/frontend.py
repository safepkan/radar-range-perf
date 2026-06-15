"""Front-end (transceiver MMIC) models.

The generic model captures the two parameters that drive the range equation:
per-channel transmit power and receiver noise figure, plus the channel counts.
Cascaded configurations are produced with :func:`cascade`.

.. note::

   The TI presets (:func:`awr1243`, :func:`awr2243`, :func:`awr2e44p`) use public
   datasheet headline figures from ti.com; :func:`ctrx8188f` uses controlled
   datasheet typical values.  Output power and noise figure still vary with chirp
   slope, RF band, temperature, EIRP back-off and board losses, so verify against
   the exact datasheet revision or your own measurements.  Treat the presets as
   templates: copy one and override the fields, or build a
   :class:`GenericFrontend` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .units import dbm_to_watt


@dataclass(frozen=True)
class GenericFrontend:
    """A transceiver front-end characterised by power, noise figure and size.

    Parameters
    ----------
    tx_power_w:
        Transmit power *per active TX channel*, in watts.  (Use
        :func:`~radarperf.units.dbm_to_watt` if you have dBm.)
    noise_figure_db:
        Receiver noise figure at the antenna port, in dB.
    n_tx, n_rx:
        Number of transmit and receive channels.
    name:
        Human-readable label used in reports.
    """

    tx_power_w: float
    noise_figure_db: float
    n_tx: int = 1
    n_rx: int = 1
    name: str = "generic"

    def __post_init__(self) -> None:
        if self.tx_power_w <= 0.0:
            raise ValueError("tx_power_w must be positive")
        if self.n_tx < 1 or self.n_rx < 1:
            raise ValueError("n_tx and n_rx must be >= 1")


def cascade(
    unit: GenericFrontend, count: int, *, name: str | None = None
) -> GenericFrontend:
    """Model ``count`` identical MMICs cascaded into one larger array.

    TX and RX channel counts add up; per-channel power and noise figure are
    assumed unchanged (a deliberately optimistic first approximation -- real
    cascades pay distribution and synchronisation losses you can fold into the
    processing-loss budget).
    """
    if count < 1:
        raise ValueError("count must be >= 1")
    label = name if name is not None else f"{count}x {unit.name} cascade"
    return replace(
        unit,
        n_tx=unit.n_tx * count,
        n_rx=unit.n_rx * count,
        name=label,
    )


# --- Presets (datasheet figures; verify against the exact revision) ----------


def awr1243(**overrides: object) -> GenericFrontend:
    """TI AWR1243 (76-81 GHz, 3 TX / 4 RX).

    Public datasheet headline figures (ti.com/product/AWR1243): 12 dBm/ch output
    power; RX noise figure 14 dB (76-77 GHz) / 15 dB (77-81 GHz). The 76-77 GHz
    primary-band value (14 dB) is used here. Phase noise -95 dBc/Hz at 1 MHz
    (76-77 GHz), not yet modelled.
    """
    base = GenericFrontend(
        tx_power_w=dbm_to_watt(12.0),
        noise_figure_db=14.0,
        n_tx=3,
        n_rx=4,
        name="AWR1243",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def awr2243(**overrides: object) -> GenericFrontend:
    """TI AWR2243 (76-81 GHz, 3 TX / 4 RX).

    Public datasheet headline figures (ti.com/product/AWR2243): 13 dBm/ch output
    power, 12 dB RX noise figure. Phase noise -96 dBc/Hz at 1 MHz (76-77 GHz),
    not yet modelled.
    """
    base = GenericFrontend(
        tx_power_w=dbm_to_watt(13.0),
        noise_figure_db=12.0,
        n_tx=3,
        n_rx=4,
        name="AWR2243",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def awr2e44p(**overrides: object) -> GenericFrontend:
    """TI AWR2E44P (76-81 GHz, 4 TX / 4 RX).

    Public datasheet headline figures (AWR2x44 family datasheet,
    ti.com/lit/ds/symlink/awr2944p.pdf): 13.5 dBm/ch output power, 11 dB RX noise
    figure. VCO phase noise -96 dBc/Hz at 1 MHz (76-77 GHz, VCO1), not yet
    modelled.
    """
    base = GenericFrontend(
        tx_power_w=dbm_to_watt(13.5),
        noise_figure_db=11.0,
        n_tx=4,
        n_rx=4,
        name="AWR2E44P",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def ctrx8188f(**overrides: object) -> GenericFrontend:
    """Infineon CTRX8188F (76-81 GHz, 8 TX / 8 RX).

    Controlled datasheet typical values: 14.5 dBm/ch output power; RX noise figure
    10.2 dB (low-noise mode @ 10 MHz, the datasheet headline). Ultra-low-noise
    mode reaches 9.7 dB @ 10 MHz. TX phase noise -100 dBc/Hz at 1 MHz, not yet
    modelled.
    """
    base = GenericFrontend(
        tx_power_w=dbm_to_watt(14.5),
        noise_figure_db=10.2,
        n_tx=8,
        n_rx=8,
        name="CTRX8188F",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]
