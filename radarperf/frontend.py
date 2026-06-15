"""Front-end (transceiver MMIC) models.

The generic model captures the two parameters that drive the range equation:
per-channel transmit power and receiver noise figure, plus the channel counts.
Cascaded configurations are produced with :func:`cascade`.

.. warning::

   The named presets (:func:`awr1243`, :func:`awr2243`, :func:`ctrx8188f`, ...)
   carry **illustrative ball-park numbers only**.  Output power and noise
   figure vary with chirp slope, RF band, temperature, EIRP back-off and board
   losses, and are exactly the kind of thing you should pull from the datasheet
   or your own measurements.  Treat the presets as templates: copy one and
   override the fields, or build a :class:`GenericFrontend` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


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


# --- Illustrative presets (verify against datasheet / measurements!) ---------


def awr1243(**overrides: object) -> GenericFrontend:
    """TI AWR1243 (77-81 GHz, 3 TX / 4 RX) -- illustrative numbers."""
    base = GenericFrontend(
        tx_power_w=10.0e-3,  # ~12 dBm/ch, ball-park
        noise_figure_db=15.0,
        n_tx=3,
        n_rx=4,
        name="AWR1243",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def awr2243(**overrides: object) -> GenericFrontend:
    """TI AWR2243 (76-81 GHz, 3 TX / 4 RX) -- illustrative numbers."""
    base = GenericFrontend(
        tx_power_w=12.6e-3,  # ~11 dBm/ch, ball-park
        noise_figure_db=12.0,
        n_tx=3,
        n_rx=4,
        name="AWR2243",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def awr2e44p(**overrides: object) -> GenericFrontend:
    """TI AWR2E44P (4 TX / 4 RX class) -- illustrative numbers."""
    base = GenericFrontend(
        tx_power_w=12.6e-3,
        noise_figure_db=11.0,
        n_tx=4,
        n_rx=4,
        name="AWR2E44P",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def ctrx8188f(**overrides: object) -> GenericFrontend:
    """Infineon CTRX8188F (76-81 GHz, 8 TX / 8 RX class) -- illustrative."""
    base = GenericFrontend(
        tx_power_w=12.6e-3,
        noise_figure_db=11.0,
        n_tx=8,
        n_rx=8,
        name="CTRX8188F",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]
