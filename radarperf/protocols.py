"""Structural interfaces for the pluggable pieces of a radar model.

Every ingredient of the range equation -- front-end, antenna, waveform, signal
processing, target, environment -- is defined here as a :class:`typing.Protocol`.
That is deliberate: it means a user can drop in *anything* that exposes the
right attributes (a one-line generic model, a datasheet-backed class, a wrapper
around measured data, a lookup table) without subclassing or registering
anything.  ``mypy`` checks the structural match.

The concrete first-version models live in their own modules
(:mod:`radarperf.frontend`, :mod:`radarperf.antenna`, ...).  The
:class:`~radarperf.engine.Radar` composes objects satisfying these protocols.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, runtime_checkable

from .geometry import Geometry
from .units import FloatOrArray


@dataclass(frozen=True)
class ProcessingBudget:
    """What the signal processing contributes to a single detection look.

    The detection statistics in :mod:`radarperf.detection` model an integration
    of ``n_noncoherent`` looks, each of which has already been coherently
    integrated.  This split lets one object describe both fully coherent
    digital beamforming (``n_noncoherent == 1``) and non-coherent beam/scan
    summation (``n_noncoherent > 1``) cleanly.

    Attributes
    ----------
    coherent_gain_db:
        Per-look coherent integration gain: range-FFT * Doppler-FFT * any
        coherently combined channels, expressed in dB.
    n_noncoherent:
        Number of *signal-bearing* looks the detector integrates non-coherently
        (1 for a single coherent range-Doppler-angle cell).
    n_collapsing:
        Number of additional noise-only cells integrated alongside the signal
        looks (e.g. empty DDMA Doppler subbands).  These raise the detection
        threshold without adding signal -- the classic collapsing loss.
    losses_db:
        Named processing losses, each a positive number of dB of loss
        (windowing, straddle, CFAR, beamforming/angle straddle, ...).  Kept
        itemised so the link budget can show where SNR went.
    """

    coherent_gain_db: float
    n_noncoherent: int = 1
    n_collapsing: int = 0
    losses_db: Mapping[str, float] = field(default_factory=dict)

    @property
    def total_loss_db(self) -> float:
        """Sum of all itemised processing losses [dB]."""
        return float(sum(self.losses_db.values()))


@runtime_checkable
class Frontend(Protocol):
    """A transceiver MMIC or cascade of them (e.g. AWR2243, CTRX8188F)."""

    @property
    def n_tx(self) -> int:
        """Number of transmit channels available."""

    @property
    def n_rx(self) -> int:
        """Number of receive channels available."""

    @property
    def tx_power_w(self) -> float:
        """Transmit power per active TX channel [W]."""

    @property
    def noise_figure_db(self) -> float:
        """Receiver noise figure referenced to the antenna port [dB]."""


@runtime_checkable
class Antenna(Protocol):
    """A transmit or receive antenna (single element of the array).

    Gain here is the *element* gain.  Coherent array / beamforming gain is
    accounted for by the processing model, not folded into the pattern, to
    avoid double counting.
    """

    @property
    def boresight_gain_dbi(self) -> float:
        """Peak (boresight) gain [dBi]."""

    @property
    def beamwidth_az_deg(self) -> float:
        """Azimuth 3 dB beamwidth [deg] (used for clutter cell sizing)."""

    @property
    def beamwidth_el_deg(self) -> float:
        """Elevation 3 dB beamwidth [deg]."""

    def gain_dbi(
        self, azimuth_deg: FloatOrArray, elevation_deg: FloatOrArray
    ) -> FloatOrArray:
        """Gain toward ``(azimuth, elevation)`` [dBi].

        Must accept scalar or broadcastable-array angles and return a matching
        shape, so a single :class:`~radarperf.geometry.Geometry` batch can be
        evaluated in one vectorised pass.
        """


@runtime_checkable
class Waveform(Protocol):
    """An FMCW waveform / mode reduced to the quantities the engine needs."""

    @property
    def center_frequency_hz(self) -> float:
        """RF centre frequency [Hz]."""

    @property
    def wavelength_m(self) -> float:
        """Wavelength at the centre frequency [m]."""

    @property
    def bandwidth_hz(self) -> float:
        """Swept bandwidth [Hz]."""

    @property
    def sample_rate_hz(self) -> float:
        """ADC sample rate of the dechirped beat signal [Hz]."""

    @property
    def n_samples(self) -> int:
        """ADC samples per chirp (range-FFT length)."""

    @property
    def n_chirps(self) -> int:
        """Chirps per coherent processing interval (Doppler-FFT length)."""

    @property
    def dwell_time_s(self) -> float:
        """Coherent dwell (active sampling) time [s]."""


@runtime_checkable
class Processing(Protocol):
    """Signal-processing chain: integration gains and detection losses."""

    def budget(self, waveform: Waveform, n_tx: int, n_rx: int) -> ProcessingBudget:
        """Return the processing budget for this waveform and array size."""


@runtime_checkable
class Target(Protocol):
    """A target's radar cross section and fluctuation behaviour."""

    @property
    def swerling(self) -> int:
        """Swerling case (0/5 non-fluctuating, 1-4 fluctuating)."""

    def rcs_m2(self, geometry: Geometry) -> FloatOrArray:
        """Radar cross section toward the radar at this geometry [m^2].

        Returns a scalar for a scalar geometry, or a matching-shape array for a
        batch geometry.
        """


@runtime_checkable
class Environment(Protocol):
    """Propagation and volume-clutter effects between radar and target."""

    def two_way_loss_db(self, geometry: Geometry, waveform: Waveform) -> FloatOrArray:
        """Two-way excess path loss (atmosphere + rain) [dB, >= 0].

        Returns a matching shape for a batch geometry.
        """

    def clutter_rcs_m2(
        self, geometry: Geometry, waveform: Waveform, antenna: Antenna
    ) -> FloatOrArray:
        """Effective clutter RCS competing with the target in its cell [m^2].

        Returns a matching shape for a batch geometry.
        """
