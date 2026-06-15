"""Signal-processing gain, loss, and combining models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from radar_range.units import db_to_linear, linear_to_db
from radar_range.waveform import FmcwWaveform

CombiningMode = Literal["coherent", "noncoherent"]


@dataclass(frozen=True)
class CombiningStage:
    """Summation over one independent channel/subband dimension.

    ``count`` is the number of complex channels, beams, or subbands included in
    the processing operation. For a coherent stage, all ``count`` terms are
    assumed to contain the target signal with aligned phase, so the SNR gain is
    ``count``.

    For a noncoherent stage, square-law outputs are summed. ``count`` controls
    the detector threshold because all included terms contribute noise degrees
    of freedom. ``signal_count`` controls the signal energy included in that
    sum. It defaults to ``count`` but can be smaller when noise-only bins are
    included, for example four active DDMA TX subbands plus two empty guard or
    unused subbands.
    """

    name: str
    count: int
    mode: CombiningMode
    signal_count: int | None = None

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("count must be at least one")
        resolved_signal_count = self.signal_bearing_count
        if resolved_signal_count < 0 or resolved_signal_count > self.count:
            raise ValueError("signal_count must satisfy 0 <= signal_count <= count")
        if self.mode == "coherent" and resolved_signal_count != self.count:
            raise ValueError(
                "coherent CombiningStage requires signal_count to equal count"
            )
        if self.mode not in ("coherent", "noncoherent"):
            raise ValueError("mode must be 'coherent' or 'noncoherent'")

    @property
    def signal_bearing_count(self) -> int:
        """Number of terms in this stage that contain target signal."""

        return self.count if self.signal_count is None else self.signal_count


@dataclass(frozen=True)
class ProcessingModel:
    """Processing gain, implementation loss, and detector-combining budget.

    The default assumes coherent range FFT integration across ADC samples and
    coherent Doppler integration across chirps, with no MIMO/channel combining.

    MIMO/DDMA/channel combining should be represented explicitly with
    ``combining_stages``. Coherent stages multiply SNR directly. Noncoherent
    stages both add signal energy and increase the square-law detector's degrees
    of freedom. This distinction matters when, for example, a DDMA detector sums
    four active TX subbands and two empty subbands: the detector has six subband
    looks, but only four of them carry target signal.

    ``coherent_virtual_channels`` and ``noncoherent_looks`` are retained as
    convenience/backward-compatible fields. New code should prefer
    ``combining_stages`` because stage names and empty/non-signal bins are then
    explicit.
    """

    include_range_fft_gain: bool = True
    include_doppler_fft_gain: bool = True
    coherent_virtual_channels: int = 1
    noncoherent_looks: int = 1
    combining_stages: tuple[CombiningStage, ...] = ()
    range_window_loss_db: float = 0.0
    doppler_window_loss_db: float = 0.0
    range_straddle_loss_db: float = 0.0
    doppler_straddle_loss_db: float = 0.0
    cfar_loss_db: float = 0.0
    implementation_loss_db: float = 0.0
    additional_processing_gain_db: float = 0.0

    def __post_init__(self) -> None:
        if self.coherent_virtual_channels < 1:
            raise ValueError("coherent_virtual_channels must be at least one")
        if self.noncoherent_looks < 1:
            raise ValueError("noncoherent_looks must be at least one")

    @classmethod
    def with_mimo_combining(
        cls,
        *,
        rx_channels: int,
        tx_or_subband_bins: int,
        rx_mode: CombiningMode,
        tx_or_subband_mode: CombiningMode,
        signal_tx_or_subband_bins: int | None = None,
        **kwargs: Any,
    ) -> "ProcessingModel":
        """Build a processing model with RX and TX/subband combining stages.

        For DDMA-style detection over active plus empty subbands, use
        ``tx_or_subband_mode='noncoherent'``, set ``tx_or_subband_bins`` to the
        total number of subbands included in the detector, and set
        ``signal_tx_or_subband_bins`` to the number of active target-bearing
        subbands. For coherent TX/subband summation, pass only the active bins.
        """

        stages = (
            CombiningStage("rx_channels", rx_channels, rx_mode),
            CombiningStage(
                "tx_or_subband_bins",
                tx_or_subband_bins,
                tx_or_subband_mode,
                signal_count=signal_tx_or_subband_bins,
            ),
        )
        return cls(combining_stages=stages, **kwargs)

    @property
    def total_loss_db(self) -> float:
        """Total implementation and processing losses in dB."""

        return (
            self.range_window_loss_db
            + self.doppler_window_loss_db
            + self.range_straddle_loss_db
            + self.doppler_straddle_loss_db
            + self.cfar_loss_db
            + self.implementation_loss_db
        )

    @property
    def all_combining_stages(self) -> tuple[CombiningStage, ...]:
        """Configured combining stages, including legacy convenience fields."""

        stages = self.combining_stages
        if self.coherent_virtual_channels > 1:
            stages = stages + (
                CombiningStage(
                    "coherent_virtual_channels",
                    self.coherent_virtual_channels,
                    "coherent",
                ),
            )
        if self.noncoherent_looks > 1:
            stages = stages + (
                CombiningStage(
                    "noncoherent_looks",
                    self.noncoherent_looks,
                    "noncoherent",
                ),
            )
        return stages

    @property
    def coherent_combining_gain_linear(self) -> float:
        """SNR gain from coherent channel/subband/beam summation only."""

        gain = 1.0
        for stage in self.all_combining_stages:
            if stage.mode == "coherent":
                gain *= float(stage.count)
        return gain

    @property
    def detector_looks(self) -> int:
        """Noise-bearing square-law looks included in the detector statistic."""

        looks = 1
        for stage in self.all_combining_stages:
            if stage.mode == "noncoherent":
                looks *= stage.count
        return looks

    @property
    def signal_looks(self) -> int:
        """Target-bearing noncoherent looks included in the detector statistic."""

        looks = 1
        for stage in self.all_combining_stages:
            if stage.mode == "noncoherent":
                looks *= stage.signal_bearing_count
        return looks

    @property
    def noncoherent_signal_gain_linear(self) -> float:
        """Signal-energy gain from noncoherent summation."""

        return float(self.signal_looks)

    def coherent_gain_linear(self, waveform: FmcwWaveform) -> float:
        """Linear coherent processing gain after configured losses.

        This includes range/Doppler FFT integration, coherent combining stages,
        additional processing gain, and configured losses. It intentionally does
        not include noncoherent energy summation; use
        :meth:`detector_signal_gain_linear` for the total detector signal-energy
        gain used in SNR bookkeeping.
        """

        gain = 1.0
        if self.include_range_fft_gain:
            gain *= waveform.num_adc_samples
        if self.include_doppler_fft_gain:
            gain *= waveform.chirps_per_tx
        gain *= self.coherent_combining_gain_linear
        gain *= float(db_to_linear(self.additional_processing_gain_db))
        gain /= float(db_to_linear(self.total_loss_db))
        return gain

    def coherent_gain_db(self, waveform: FmcwWaveform) -> float:
        """Coherent processing gain in dB after losses."""

        return float(linear_to_db(self.coherent_gain_linear(waveform)))

    def detector_signal_gain_linear(self, waveform: FmcwWaveform) -> float:
        """Total signal-energy gain used for detector SNR bookkeeping."""

        return self.coherent_gain_linear(waveform) * self.noncoherent_signal_gain_linear

    def detector_signal_gain_db(self, waveform: FmcwWaveform) -> float:
        """Total detector signal-energy gain in dB."""

        return float(linear_to_db(self.detector_signal_gain_linear(waveform)))
