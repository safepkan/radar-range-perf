# radarperf

A small, scriptable toolbox for **range-performance analysis of 77 GHz FMCW
radars** (with or without MIMO), built around the FMCW radar range equation.
It computes SNR / SCR / SINR link budgets and single-scan probability of
detection, and extends those into range/angle sweeps, coverage contours and
multi-scan track-acquisition probability.

There is no GUI. Everything is a plain Python object you compose and call from a
script or notebook, which keeps it easy to drop into a monorepo and to drive
from your own analyses.

## Install

It's a pure-Python package depending only on NumPy and SciPy:

```bash
pip install -e .
```

## Quickstart

```python
from radarperf import (
    Radar, FmcwWaveform, StandardProcessing, MimoScheme,
    GaussianBeamAntenna, Geometry, frontend, target,
)

waveform = FmcwWaveform(
    center_frequency_hz=77e9, bandwidth_hz=1.0e9, sample_rate_hz=20e6,
    n_samples=256, n_chirps=128, chirp_repetition_time_s=50e-6,
)
element = GaussianBeamAntenna(boresight_gain_dbi=11.0,
                              beamwidth_az_deg=80.0, beamwidth_el_deg=20.0)

radar = Radar(
    frontend=frontend.awr2243(),                 # illustrative preset
    waveform=waveform,
    processing=StandardProcessing(mimo=MimoScheme.TDM),
    tx_antenna=element, rx_antenna=element,
    default_pfa=1e-6,
)

budget = radar.link_budget(target.car(), Geometry(range_m=120.0))
print(budget)                                    # full dB breakdown
print(radar.probability_of_detection(target.car(), Geometry(range_m=120.0)))
```

See `examples/basic_link_budget.py` and `examples/pd_vs_range.py` for sweeps,
coverage and track acquisition.

## How the SNR is computed

The engine uses the energy form of the FMCW radar equation, written as a
single-sample SNR times a dimensionless integration gain:

```
snr_sample = Pt * Gt * Gr * lambda^2 * sigma
             / ( (4*pi)^3 * R^4 * k * T0 * F * fs * L_path )

SNR        = snr_sample * coherent_gain / processing_losses
```

The noise power per complex baseband sample is `k * T0 * F * fs` (noise
bandwidth equal to the ADC sample rate, with all receiver noise lumped into the
noise figure `F` referenced to `T0 = 290 K`). The coherent integration gain
(range-FFT x Doppler-FFT x coherently combined channels) and the named
processing losses come from the processing model, so the range equation itself
stays free of FFT-length bookkeeping. Antenna gains are **element** gains;
coherent array/beamforming gain lives in the integration gain to avoid double
counting.

### MIMO and channel combination

The processing model centralises the MIMO accounting and lets you choose, *per
axis*, whether the RX channels and the TX/subband channels are combined
coherently (beamforming -> coherent gain) or non-coherently (magnitude
summation -> detector looks). For `N_s` samples, `N_c` chirps, `n_tx`
transmitters and `n_rx` receivers, the per-virtual-channel coherent gain is
`N_s * N_c` (`N_c / n_tx` for TDM); coherently combined axes multiply it,
non-coherently combined axes become looks:

| Scheme      | coherent gain (full DBF)     |
|-------------|------------------------------|
| `NONE`      | `N_s * N_c * n_rx`           |
| `TDM`       | `N_s * N_c * n_rx`           |
| `DDM`/`BPM` | `N_s * N_c * n_tx * n_rx`   |

TDM matches a single-TX / `n_rx`-receiver system in SNR while buying the
`n_tx`-fold virtual aperture; DDM/BPM keep every transmitter on every chirp and
gain a further `n_tx` in coherent combination at the cost of Doppler ambiguity
(set `mimo_loss_db` for the orthogonality loss).

`StandardProcessing(rx_combination=..., tx_combination=...)` (each
`BeamCombination.COHERENT` or `NONCOHERENT`) expresses the practical DDMA paths.
For example, on a 4 TX / 4 RX DDMA part with 6 Doppler subbands:

| Path                                      | coherent gain        | signal looks | empty cells |
|-------------------------------------------|----------------------|--------------|-------------|
| non-coh RX + non-coh subband (detect)     | `N_s N_c`            | 16           | 8           |
| coherent RX, non-coh subband              | `N_s N_c n_rx`       | 4            | 2           |
| coherent RX + coherent TX (virtual array) | `N_s N_c n_rx n_tx`  | 1            | 0           |

The first row is the TI DDMA detection path: detect on the magnitude sum over
all RX x all subbands, then resolve TX and estimate DOA. The two empty guard
subbands (`n_doppler_subbands=6` for 4 TX) add noise but no signal -- a
**collapsing loss**, reported as `LinkBudget.n_collapsing` and handled exactly
by the detector (the threshold uses all integrated cells while only the signal
cells contribute energy). When the TX axis is combined coherently the
transmitters are resolved first, so the empty subbands are discarded and there
is no collapsing. `examples/ddma_combinations.py` prints all of these side by
side.

A note on fluctuation: the cells integrated across the array in one CPI share a
single RCS realisation, so spatial non-coherent integration is correctly
modelled with Swerling 1 (Rayleigh) or 3 (chi-4), not the independent-per-look
Swerling 2/4 -- which is why collapsing is supported for cases 0/1/3 and the
independent cases 2/4 raise an explanatory error.

### In-phase (coherent) transmit

As an alternative to orthogonal MIMO, `transmit_coherent=True` models all `n_tx`
transmitters radiating the same waveform in phase -- a transmit phased array
steered at the target. The on-target power density scales as `n_tx**2` (`n_tx`
from summed power, `n_tx` from transmit directivity), i.e. `+10 log10(n_tx)` over
DDM-MIMO and `+20 log10(n_tx)` over a single transmitter, for a target in the
formed beam. There is no virtual TX aperture in this mode, so covering a wide
field of view means scanning the transmit beam (more dwell/scan time) -- which
this per-direction budget does not amortise for you.

### Angular beamforming / straddle loss

Coherent combination of channels (RX, virtual array, or in-phase TX) points a
beam; a target away from that exact pointing direction suffers an angular
straddle / scan loss. Because the magnitude depends on array geometry and how
the beams are gridded, it is exposed as a single configurable
`beamforming_loss_db` that applies only to the coherently combined paths -- set
it to 0 if the beam is refined onto the DOA, up to a few dB for a coarse beam
grid (the worst-case crossover between adjacent beams is ~3-4 dB, the average is
typically below 1 dB). The non-coherent DDMA detection path takes no such loss,
which partly offsets its lower integration efficiency.

### Detection

`radarperf.detection` implements a square-law detector integrating `n_pulses`
non-coherent looks, for Swerling cases 0-4 (5 is treated as 0). The closed
forms were cross-checked against Monte-Carlo simulation (see
`tests/test_detection.py` and `tests/test_combination.py`): Swerling 0/1/2/4 use
exact expressions, Swerling 3 uses Gauss-Laguerre quadrature of the Swerling-0
result over the chi-square(4) RCS distribution. It also accepts an
`n_collapsing` count of noise-only cells (the DDMA empty-subband case), again
Monte-Carlo validated. For a single coherent range-Doppler-angle cell
`n_pulses = 1`. `required_snr_db` inverts the exact Pd; `albersheim_required_snr_db`
and `shnidman_required_snr_db` provide the usual fast approximations.

## Architecture

Every ingredient is a `typing.Protocol`, so any object exposing the right
attributes plugs in — no subclassing or registration. `mypy` checks the
structural match. The protocols are `Frontend`, `Antenna`, `Waveform`,
`Processing`, `Target` and `Environment` (in `radarperf.protocols`).

This is what lets a model grow from "generic" to "datasheet-detailed" by
swapping one component:

* **Front-end** — `GenericFrontend` (per-channel TX power, noise figure, channel
  counts) plus `cascade()` and illustrative presets (`awr1243`, `awr2243`,
  `awr2e44p`, `ctrx8188f`).
* **Antenna** — `ConstantGainAntenna` -> `GaussianBeamAntenna` ->
  `PatternCutAntenna` (separable az/el cuts, e.g. from a waveguide datasheet) ->
  `PatternUVAntenna` (full interpolated pattern).
* **Waveform** — `FmcwWaveform` with derived resolution and ambiguity figures.
* **Processing** — `StandardProcessing` (MIMO scheme, per-axis coherent/
  non-coherent combination, DDMA subbands/collapsing, in-phase coherent transmit,
  window / straddle / CFAR / beamforming / MIMO losses).
* **Target** — `ConstantRcsTarget`, `AspectRcsTarget` (callable),
  `RcsTableTarget` (aspect table, interpolated in dBsm), plus presets.
* **Environment** — `FreeSpace`, `Atmosphere`, `Rain`, and `CompositeEnvironment`
  to stack them.

Sweeps (`radarperf.sweeps`) wrap the per-point link budget into the arrays you
plot: `range_sweep`, `map_2d` (with `range_azimuth_geometry`,
`range_elevation_geometry`, `xy_geometry`, `xz_geometry` builders),
`coverage_range` and `coverage_vs_azimuth`.

## Assumptions and caveats

* **The chipset and RCS presets are illustrative, not authoritative.** Output
  power, noise figure and RCS depend on slope, band, temperature, EIRP back-off,
  aspect, etc. Copy a preset and override the fields, or build the generic model
  directly, using datasheet or measured numbers.
* **Rain clutter is approximate.** Attenuation uses the ITU-R P.838 power law
  with default coefficients near 77 GHz (replace with the exact P.838 values for
  your band/polarisation). The volume-clutter reflectivity uses a Marshall-Palmer
  Z-R relation with a Rayleigh assumption; at 77 GHz raindrops are in the Mie
  regime, so calibrate `dielectric_factor` and the Z-R coefficients before
  trusting absolute clutter numbers. The path is wired in and overridable.
* Antenna pattern separability (`PatternCutAntenna`) is exact on the cuts and a
  reasonable engineering approximation off them.

## Possible next steps

Things deliberately left out of this version that are natural extensions:
short-range effects (receiver saturation / near-field, transmit-to-receive
leakage and ADC dynamic range, phase-noise / reciprocal-mixing skirts that limit
SCR against strong nearby reflectors), eclipsing, ADC quantisation noise, a
refined antenna-temperature / system-temperature model instead of lumping
everything into `F`, and Doppler separation of moving targets from clutter. The
angular beamforming/straddle loss is currently a configurable scalar
(`beamforming_loss_db`); computing it from the actual array geometry and beam
grid is a natural refinement.

## Development

```bash
black .          # format (line length 88)
flake8 .         # lint (max line length 100)
mypy radarperf   # strict type-check
pytest tests/    # 37 tests incl. Monte-Carlo detection & collapsing cross-checks
```
