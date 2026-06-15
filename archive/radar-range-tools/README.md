# radar-range-tools

Typed Python tools for first-order 76-81 GHz FMCW radar range-performance calculations.
The package is aimed at early radar trade studies where users want to assemble hardware,
antenna, waveform, signal-processing, target, and environment models in Python scripts and
then compute SNR/SINR, single-scan Pd, and simple track-initiation probabilities.

This is an intentionally small first version. The core is the monostatic radar range
equation plus an explicit processing-gain/loss and detector-combining budget. The model
interfaces are designed so more detailed measured or datasheet-driven components can be
swapped in later.

## What is included

- RF hardware model with per-TX output power, receiver noise figure, RF losses, TX/RX counts,
  and TX/RX antenna models.
- Antenna models:
  - constant boresight gain;
  - separable azimuth/elevation pattern cuts;
  - bilinear u/v gain grid.
- FMCW waveform model with ADC samples, sample rate, bandwidth, chirps per TX, range
  resolution, approximate beat-frequency-limited max range, and noise bandwidth convention.
- Processing model with range FFT gain, Doppler FFT gain, named coherent and noncoherent
  channel/subband combining stages, empty/noise-only noncoherent bins, window/straddling/
  CFAR/implementation losses, and extra gain.
- Target models:
  - constant point-target RCS;
  - azimuth-dependent RCS table.
- Environment hooks:
  - clear environment;
  - range-proportional attenuation;
  - rain power-law attenuation helper;
  - clutter model protocol and simple constant-clutter/no-clutter implementations.
- Detection models:
  - nonfluctuating target using a noncentral chi-square detector;
  - Swerling I by Gauss-Laguerre averaging;
  - Swerling II with independent look-to-look fluctuations;
  - M-out-of-N acquisition probability.
- Range sweeps, range/azimuth grids, coverage-boundary extraction, and optional Matplotlib
  plotting helpers.
- Headline presets for common TI devices, controlled-datasheet typical values for Infineon
  CTRX8188F, an AWR2E44P DDMA processing helper, and simple Huber+Suhner boresight gains.

## Installation for development

```bash
python -m pip install -e '.[dev]'
pytest
black src tests examples
flake8 src tests examples
mypy
```

## Minimal example

```python
import numpy as np

from radar_range import (
    FmcwWaveform,
    PointTarget,
    ProcessingModel,
    RadarScenario,
    range_sweep,
)
from radar_range.presets import ti_awr2243

hardware = ti_awr2243(tx_antenna_gain_dbi=15.0, rx_antenna_gain_dbi=15.0)
waveform = FmcwWaveform(
    name="long-range mode",
    num_adc_samples=512,
    sample_rate_hz=12.5e6,
    bandwidth_hz=1.5e9,
    chirps_per_tx=64,
    num_tx=3,
)
processing = ProcessingModel(
    coherent_virtual_channels=hardware.virtual_channel_count,
    range_window_loss_db=1.5,
    doppler_window_loss_db=1.5,
    range_straddle_loss_db=1.0,
    cfar_loss_db=2.0,
)
scenario = RadarScenario(
    hardware=hardware,
    waveform=waveform,
    processing=processing,
    target=PointTarget.from_dbsm(10.0, name="nominal car"),
)

ranges_m = np.linspace(5.0, 250.0, 246)
sweep = range_sweep(scenario, ranges_m, pfa=1e-6)
print(sweep.sinr_db)
print(sweep.pd)
```

## Core convention

The received target power is computed from

```text
Pr = Pt * Gt * Gr * lambda^2 * sigma / ((4*pi)^3 * R^4 * L)
```

where `Pt` is per-transmitter output power, `Gt` and `Gr` are directional antenna
gains, `sigma` is RCS, and `L` includes configured RF losses plus two-way atmospheric
attenuation. Thermal noise uses

```text
Tsys = T_ant + (F - 1) * T0
Pn = k * Bn * Tsys
```

where `Bn` defaults to the ADC sample rate unless `adc_noise_bandwidth_hz` is set on the
waveform.

Processing is split into two ideas:

```text
coherent_gain = range FFT gain * Doppler FFT gain * coherent combining gain / losses
noncoherent_signal_gain = product of target-bearing noncoherent counts
detector_signal_gain = coherent_gain * noncoherent_signal_gain
SNR = Pr / (Pn / detector_signal_gain)
```

`detector_looks` is stored separately and passed to the Pd calculation because it controls
the square-law detector threshold and degrees of freedom. This distinction is important when
a detector includes noise-only bins. For example, summing 4 RX channels and 6 DDMA subbands
with only 4 active TX subbands gives 24 detector looks but only 16 target-bearing signal
looks.

`clutter_power` is defined by the clutter model as equivalent input clutter power in the
same detection cell. More sophisticated clutter models can choose their own interpretation
as long as they obey this interface.

## MIMO and DDMA combining convention

The package does not silently turn TX/RX counts into array gain. Use `tx_count` and
`rx_count` as metadata, then set the actual combining assumption in `ProcessingModel`.
For example, a fully coherent virtual-array idealization can still be written as:

```python
processing = ProcessingModel(coherent_virtual_channels=hardware.virtual_channel_count)
```

For explicit channel/subband modeling, use named combining stages:

```python
from radar_range import CombiningStage, ProcessingModel

processing = ProcessingModel(
    combining_stages=(
        CombiningStage("rx_channels", 4, "noncoherent"),
        CombiningStage("ddma_subbands", 6, "noncoherent", signal_count=4),
    )
)
```

For the AWR2E44P DDMA SDK-style path described by the project, the helper below models
noncoherent detection over all 4 RX channels and all 6 virtual subbands, with 4 active
TX/subbands and 2 empty subbands:

```python
from radar_range.presets import awr2e44p_ddma_processing

sdk_like = awr2e44p_ddma_processing()
rx_coherent = awr2e44p_ddma_processing(rx_mode="coherent")
rx_and_tx_coherent = awr2e44p_ddma_processing(
    rx_mode="coherent",
    subband_mode="coherent",
)
```

All three variants above have the same nominal signal-energy gain of 16 before losses, but
they have different detector statistics: 24 looks for the SDK-like noncoherent RX/subband
sum, 6 looks for coherent RX plus noncoherent subbands, and 1 look for coherent RX plus
coherent active-subband summation.

## Presets

The presets are convenience values for early setup only. For project calculations, prefer
copying a preset into your own configuration and replacing values with controlled datasheet
or measured data. The Infineon CTRX8188F helper defaults to the local controlled-datasheet
typical values supplied by the project: 14.5 dBm output power and 9.7 dB noise figure.

## Likely next extensions

- Parse measured antenna patterns from CSV/Touchstone-style exports and support full complex
  embedded-element patterns.
- Add scan-angle beamforming and explicit array-factor/virtual-array geometry.
- Add range-cell/Doppler-cell clutter models for rain, ground, guardrail, and multipath.
- Add ADC saturation, receiver compression, phase-noise skirts, close-range leakage, and
  strong-target masking models.
- Add waveform validity checks: max beat frequency, Doppler ambiguity, range migration,
  velocity ambiguity, duty cycle, and regulatory/EIRP constraints.
- Add CFAR-specific threshold/loss models, including CA/GO/SO/OS-CFAR and clutter-edge
  penalties.
- Add tracker acquisition models beyond simple M-out-of-N, including nonstationary Pd across
  scan angle and target motion.
