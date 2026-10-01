"""Hardware, installation and coherence losses outside the processing chain.

The front-end preset gives datasheet TX power and noise figure at the MMIC's RF
reference plane, the antenna pattern is usually a directivity, and the
processing model covers windows, straddle, CFAR and combining.  The terms in
between are easy to leave out because leaving them out means zero.
:class:`SystemLosses` names them, so a study states each one even when it
chooses zero, and the link budget lists each one.  ``docs/losses.md``
catalogues these and every other term, including those that live in other
components or are not modelled.

Where each term acts
--------------------
* Transmit side (signal and clutter alike): ``tx_power_derating_db``,
  ``tx_feed_loss_db``, ``tx_antenna_loss_db`` and one radome pass.
* Receive side: one radome pass, ``rx_antenna_loss_db`` and ``rx_feed_loss_db``.
  These are passive losses at the reference temperature ``T0``, so they also
  emit noise: referred to the MMIC, ``T_sys = T_ant / L + T0 (1 - 1/L) +
  (F - 1) T0``.  With the default ``T_ant = T0`` this is still ``F T0``, and a
  receive loss lowers SNR by exactly its value.
* Noise: ``noise_figure_derating_db`` raises the front-end noise figure.
* Coherence: ``chirp_frequency_error_rms_hz`` gives a range-dependent loss of
  the coherent Doppler peak (see :meth:`SystemLosses.coherence_loss_db`).

All values default to zero, which reproduces the ideal model exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import cast

import numpy as np

from .units import SPEED_OF_LIGHT, FloatOrArray

_DB_PER_NEPER_POWER = 10.0 / math.log(10.0)  # 10 log10(e)


@dataclass(frozen=True)
class SystemLosses:
    """Named losses between the datasheet front-end, the antenna and the target.

    Each value is a non-negative loss in dB (or, for the chirp error, an rms
    frequency in Hz).  Zero is a valid choice but should be a conscious one.

    Parameters
    ----------
    tx_power_derating_db:
        TX power below the front-end's datasheet figure: junction temperature,
        part spread (typical to minimum), band edge or programmed back-off.
    noise_figure_derating_db:
        Noise figure above the front-end's datasheet figure: temperature, part
        spread, an RX gain step below the datasheet condition, or a low IF where
        flicker noise rises.
    tx_feed_loss_db, rx_feed_loss_db:
        From the MMIC's RF reference plane to the antenna port: PCB lines,
        transitions, waveguide runs, feed network and the PCB-to-antenna
        interface.  Check where the datasheet puts its reference plane; for the
        CTRX8188F it is the waveguide port on the far side of a reference PCB.
    tx_antenna_loss_db, rx_antenna_loss_db:
        Antenna directivity to realized gain: ohmic and dielectric loss and port
        mismatch.  Zero when the pattern already is a realized gain.
    radome_one_way_loss_db:
        Radome (or bumper) transmission loss for one pass; applied on both
        transmit and receive.  Includes any water film, ice or dirt assumed.
    chirp_frequency_error_rms_hz:
        RMS RF frequency offset of each chirp from the ideal ramp, constant
        within a chirp and independent from chirp to chirp.  It gives a beat
        phase error ``2 pi df tau`` at delay ``tau = 2 R / c``.  It depends on
        the MMIC and on how its ramps are programmed (flyback, wait,
        pre-payload); ``docs/losses.md`` lists datasheet-based and measured
        values.
    """

    tx_power_derating_db: float = 0.0
    noise_figure_derating_db: float = 0.0
    tx_feed_loss_db: float = 0.0
    rx_feed_loss_db: float = 0.0
    tx_antenna_loss_db: float = 0.0
    rx_antenna_loss_db: float = 0.0
    radome_one_way_loss_db: float = 0.0
    chirp_frequency_error_rms_hz: float = 0.0

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{f.name} must be finite and non-negative")

    @property
    def transmit_loss_db(self) -> float:
        """Transmit-side loss: derating, feed, antenna and one radome pass [dB]."""
        return (
            self.tx_power_derating_db
            + self.tx_feed_loss_db
            + self.tx_antenna_loss_db
            + self.radome_one_way_loss_db
        )

    @property
    def receive_loss_db(self) -> float:
        """Passive receive-side loss: one radome pass, antenna and feed [dB]."""
        return (
            self.radome_one_way_loss_db + self.rx_antenna_loss_db + self.rx_feed_loss_db
        )

    def coherence_loss_db(self, range_m: FloatOrArray) -> FloatOrArray:
        """Doppler-peak loss from independent per-chirp phase errors [dB].

        With Gaussian phase errors of rms ``sigma = 2 pi df (2 R / c)``, the
        coherent sum over chirps keeps ``exp(-sigma**2)`` of its peak power; the
        rest spreads into a pedestal across Doppler.  The loss is therefore
        ``10 log10(e) sigma**2``, growing as ``R**2``.
        """
        delay_s = 2.0 * np.asarray(range_m, dtype=float) / SPEED_OF_LIGHT
        sigma_rad = 2.0 * math.pi * self.chirp_frequency_error_rms_hz * delay_s
        return cast(FloatOrArray, _DB_PER_NEPER_POWER * sigma_rad**2)

    def itemised_db(self, range_m: float) -> dict[str, float]:
        """Every term at one range, in signal-path order, zeros included [dB].

        The signal-path items sum to the system loss reported by the link
        budget; ``noise_figure_derating`` acts on the noise instead.
        """
        return {
            "tx_power_derating": self.tx_power_derating_db,
            "tx_feed": self.tx_feed_loss_db,
            "tx_antenna": self.tx_antenna_loss_db,
            "radome_two_way": 2.0 * self.radome_one_way_loss_db,
            "rx_antenna": self.rx_antenna_loss_db,
            "rx_feed": self.rx_feed_loss_db,
            "chirp_coherence": float(self.coherence_loss_db(range_m)),
            "noise_figure_derating": self.noise_figure_derating_db,
        }
