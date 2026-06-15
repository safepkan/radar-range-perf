"""Signal-processing model: integration gain, MIMO bookkeeping and losses.

This component decides how the raw per-sample SNR becomes a per-look detection
SNR, how many non-coherent looks the detector sees, and how many of those looks
are noise-only (the collapsing case).

Combination per axis
---------------------
The virtual data cube has three relevant axes beyond range/Doppler: the RX
channels, and -- for MIMO -- the TX channels (which in DDMA appear as Doppler
subbands).  Each axis can be combined either *coherently* (beamforming: adds to
the coherent gain, costs an angular beamforming/straddle loss for off-pointing
targets) or *non-coherently* (magnitude summation across cells: becomes detector
looks, direction-insensitive, no beamforming loss).  Setting ``rx_combination``
and ``tx_combination`` independently covers the practical combinations:

* RX non-coherent + TX/subband non-coherent -- the TI DDMA detection path:
  detect on the magnitude sum over all RX x all subbands, resolve TX and
  estimate DOA afterwards.
* RX coherent + subband non-coherent -- RX beamform within each subband, then
  sum subbands non-coherently.
* RX coherent + TX coherent -- full coherent virtual-array beamforming.

DDMA empty subbands
-------------------
DDMA usually allocates more Doppler subbands than transmitters (e.g. 6 for 4 TX)
to leave guard/empty bands.  When the TX/subband axis is summed *non-coherently*,
those empty subbands contribute noise but no signal: a collapsing loss, reported
via ``ProcessingBudget.n_collapsing`` and handled exactly by the detector.  When
the TX axis is combined *coherently* the transmitters are resolved first, so the
empty subbands are discarded and there is no collapsing.

MIMO SNR bookkeeping
--------------------
Per virtual channel the coherent range-Doppler gain is ``N_s * chirps_per_tx``
(``N_c`` for NONE/DDM/DDMA, ``N_c / n_tx`` for TDM).  Coherently combined axes
multiply the coherent gain (``n_rx`` and/or ``n_tx``); non-coherently combined
axes become looks.  TDM therefore matches single-TX/``n_rx`` SNR while buying the
``n_tx`` virtual aperture; DDM/DDMA keep all TX on every chirp and gain ``n_tx``
in coherent combination at the cost of Doppler ambiguity.

In-phase (coherent) transmit
----------------------------
As an alternative to orthogonal MIMO, ``transmit_coherent=True`` models all
``n_tx`` transmitters radiating the same waveform in phase (a transmit phased
array steered at the target).  The on-target power density then scales as
``n_tx**2`` -- ``n_tx`` from the summed power and a further ``n_tx`` from the
transmit array directivity -- i.e. ``+10 log10(n_tx)`` over DDM-MIMO and
``+20 log10(n_tx)`` over a single transmitter, for a target in the formed beam.
There is no virtual TX aperture in this mode; covering a wide field of view
requires scanning the transmit beam (more dwell/scan time), which this
per-direction budget does not amortise for you.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .protocols import ProcessingBudget, Waveform
from .units import linear_to_db


class MimoScheme(Enum):
    """How transmit channels are multiplexed."""

    NONE = "none"
    TDM = "tdm"
    DDM = "ddm"
    BPM = "bpm"


class BeamCombination(Enum):
    """How an axis of virtual channels is combined before detection."""

    COHERENT = "coherent"
    NONCOHERENT = "noncoherent"


_MULTIPLEXED = frozenset({MimoScheme.TDM, MimoScheme.DDM, MimoScheme.BPM})


@dataclass(frozen=True)
class StandardProcessing:
    """A conventional range-Doppler(-angle) processing chain.

    Parameters
    ----------
    mimo:
        Transmit multiplexing scheme.
    rx_combination, tx_combination:
        How the RX channels and the TX/subband channels are combined
        (``COHERENT`` beamforming or ``NONCOHERENT`` magnitude summation).
        Both default to coherent (full digital beamforming).
    n_doppler_subbands:
        For DDMA (``DDM``/``BPM``): total number of Doppler subbands, including
        empty guard bands.  Defaults to ``n_tx`` (no empty bands).  Only matters
        when ``tx_combination`` is non-coherent.
    transmit_coherent:
        If True, model in-phase coherent transmit (a transmit phased array)
        instead of orthogonal MIMO; the TX axis contributes ``n_tx**2`` to the
        coherent gain and there is no virtual TX aperture.
    Loss terms:
        Window / straddle / CFAR losses as before, plus ``beamforming_loss_db``
        for the angular straddle / scan loss incurred when a coherently combined
        beam does not point exactly at the target (set to 0 if the beam is
        refined onto the target, up to a few dB for a coarse beam grid).
    """

    mimo: MimoScheme = MimoScheme.NONE
    rx_combination: BeamCombination = BeamCombination.COHERENT
    tx_combination: BeamCombination = BeamCombination.COHERENT
    n_doppler_subbands: int = 0
    transmit_coherent: bool = False
    range_window_loss_db: float = 1.76
    doppler_window_loss_db: float = 1.76
    range_straddle_loss_db: float = 0.6
    doppler_straddle_loss_db: float = 0.6
    cfar_loss_db: float = 1.0
    beamforming_loss_db: float = 0.0
    mimo_loss_db: float = 0.0
    other_loss_db: float = 0.0

    def budget(self, waveform: Waveform, n_tx: int, n_rx: int) -> ProcessingBudget:
        if self.mimo is MimoScheme.TDM and not self.transmit_coherent:
            chirps_per_tx = waveform.n_chirps / n_tx
        else:
            chirps_per_tx = float(waveform.n_chirps)
        base_coherent = waveform.n_samples * chirps_per_tx

        coherent_factor = 1.0
        n_signal = 1
        n_total = 1
        angular_combination = False

        # RX axis.
        if self.rx_combination is BeamCombination.COHERENT:
            coherent_factor *= n_rx
            angular_combination = True
        else:
            n_signal *= n_rx
            n_total *= n_rx

        # TX / subband axis.
        if self.transmit_coherent:
            coherent_factor *= n_tx**2  # transmit phased-array beamforming
            angular_combination = True
        else:
            n_tx_eff = n_tx if self.mimo in _MULTIPLEXED else 1
            if self.tx_combination is BeamCombination.COHERENT:
                coherent_factor *= n_tx_eff  # resolved virtual TX, empties discarded
                if n_tx_eff > 1:
                    angular_combination = True
            else:
                if self.mimo in (MimoScheme.DDM, MimoScheme.BPM):
                    n_subbands = self.n_doppler_subbands or n_tx_eff
                else:
                    n_subbands = n_tx_eff
                n_signal *= n_tx_eff
                n_total *= n_subbands

        coherent_gain = base_coherent * coherent_factor

        losses = {
            "range_window": self.range_window_loss_db,
            "doppler_window": self.doppler_window_loss_db,
            "range_straddle": self.range_straddle_loss_db,
            "doppler_straddle": self.doppler_straddle_loss_db,
            "cfar": self.cfar_loss_db,
            "beamforming": self.beamforming_loss_db if angular_combination else 0.0,
            "mimo": self.mimo_loss_db,
            "other": self.other_loss_db,
        }
        losses = {name: value for name, value in losses.items() if value != 0.0}

        return ProcessingBudget(
            coherent_gain_db=float(linear_to_db(coherent_gain)),
            n_noncoherent=int(n_signal),
            n_collapsing=int(n_total - n_signal),
            losses_db=losses,
        )


@dataclass(frozen=True)
class CombiningStage:
    """One named channel/subband summation axis.

    ``count`` is the number of cells summed on this axis.  A *coherent* stage
    multiplies the coherent integration gain by ``count`` (in-phase summation,
    e.g. beamforming); a *non-coherent* stage instead contributes ``count``
    square-law detector cells.

    ``signal_count`` is how many of those cells carry target signal; it defaults
    to ``count`` and may be smaller for a non-coherent stage that also sums
    noise-only cells (the DDMA empty-subband / collapsing case).  A coherent
    stage must have ``signal_count == count`` -- empty cells are resolved out
    before coherent summation rather than summed.
    """

    name: str
    count: int
    mode: BeamCombination
    signal_count: int | None = None

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("count must be >= 1")
        signal = self.signal_bearing_count
        if not 0 <= signal <= self.count:
            raise ValueError("signal_count must satisfy 0 <= signal_count <= count")
        if self.mode is BeamCombination.COHERENT and signal != self.count:
            raise ValueError(
                "a coherent CombiningStage cannot have noise-only cells "
                "(signal_count must equal count)"
            )

    @property
    def signal_bearing_count(self) -> int:
        """Number of cells on this axis that carry target signal."""
        return self.count if self.signal_count is None else self.signal_count


@dataclass(frozen=True)
class StagedProcessing:
    """Processing defined by an explicit list of named combining stages.

    A flexible alternative to :class:`StandardProcessing` for combining
    topologies that do not fit the fixed RX / TX-subband axes: any number of
    named :class:`CombiningStage` axes, each coherent or non-coherent, with
    optional noise-only (collapsing) cells.

    The coherent integration gain is the range-FFT * Doppler-FFT product (over
    ``n_samples`` and ``n_chirps``) times the counts of the coherent stages.
    Non-coherent stages set the detector look counts: the signal-bearing looks
    are the product of the stages' ``signal_bearing_count`` and the collapsing
    cells are the remaining product of ``count``.

    Unlike :class:`StandardProcessing`, this model applies no MIMO-scheme /
    TDM duty-cycle bookkeeping -- ``n_samples * n_chirps`` is taken as the full
    coherent base.  For TDM, use :class:`StandardProcessing` (or set
    ``include_doppler_fft_gain=False`` and fold the integration in elsewhere).
    """

    combining_stages: tuple[CombiningStage, ...] = ()
    include_range_fft_gain: bool = True
    include_doppler_fft_gain: bool = True
    range_window_loss_db: float = 1.76
    doppler_window_loss_db: float = 1.76
    range_straddle_loss_db: float = 0.6
    doppler_straddle_loss_db: float = 0.6
    cfar_loss_db: float = 1.0
    other_loss_db: float = 0.0
    additional_gain_db: float = 0.0

    def budget(self, waveform: Waveform, n_tx: int, n_rx: int) -> ProcessingBudget:
        coherent_gain = 1.0
        if self.include_range_fft_gain:
            coherent_gain *= waveform.n_samples
        if self.include_doppler_fft_gain:
            coherent_gain *= waveform.n_chirps

        n_signal = 1
        n_total = 1
        for stage in self.combining_stages:
            if stage.mode is BeamCombination.COHERENT:
                coherent_gain *= stage.count
            else:
                n_signal *= stage.signal_bearing_count
                n_total *= stage.count

        losses = {
            "range_window": self.range_window_loss_db,
            "doppler_window": self.doppler_window_loss_db,
            "range_straddle": self.range_straddle_loss_db,
            "doppler_straddle": self.doppler_straddle_loss_db,
            "cfar": self.cfar_loss_db,
            "other": self.other_loss_db,
        }
        losses = {name: value for name, value in losses.items() if value != 0.0}

        gain_db = float(linear_to_db(coherent_gain)) + self.additional_gain_db
        return ProcessingBudget(
            coherent_gain_db=gain_db,
            n_noncoherent=int(n_signal),
            n_collapsing=int(n_total - n_signal),
            losses_db=losses,
        )
