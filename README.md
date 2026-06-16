# radarperf

A small, scriptable toolbox for **range-performance analysis of 77 GHz FMCW
radars** (with or without MIMO), built around the FMCW radar range equation.
It computes SNR / SCR / SINR link budgets and single-scan probability of
detection, and extends those into range/angle sweeps, coverage contours and
multi-scan track-acquisition probability.

There is no GUI. Everything is a plain Python object you compose and call from a
script or notebook, which keeps it easy to drive from your own analyses.

## Install

Pure-Python, depending only on NumPy and SciPy (plus Matplotlib for the optional
`plot` extra). Create the development environment with the Makefile:

```bash
make setup_venv                                   # builds ./venv from requirements.txt
# or pick a Python version:
make setup_venv ENV=venv312
make setup_venv VENV_PYTHON=$(command -v python3.12)
```

`requirements.txt` is just `-e .[dev]`; runtime and tool dependencies live in
`pyproject.toml`.

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
    frontend=frontend.awr2243(),                 # datasheet preset
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
             / ( (4*pi)^3 * R^4 * k * Tsys * Bn * L_path )

SNR        = snr_sample * coherent_gain / processing_losses
```

The noise power per complex baseband sample is `k * Tsys * Bn`, with system
temperature `Tsys = Tant + (F - 1) * T0` (`Tant` the antenna/scene noise
temperature, default `T0 = 290 K`; `F` the receiver noise factor) and noise
bandwidth `Bn` (the waveform's effective noise bandwidth, defaulting to the ADC
sample rate `fs`). With the defaults `Tant = T0` and `Bn = fs` this reduces to
`k * T0 * F * fs`. Set `Radar(antenna_noise_temperature_k=...)` and
`FmcwWaveform(noise_bandwidth_hz=...)` to refine either. The coherent integration gain
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
by the detector. When the TX axis is combined coherently the transmitters are
resolved first, so the empty subbands are discarded and there is no collapsing.
`examples/ddma_combinations.py` prints all of these side by side.

A note on fluctuation: the cells integrated across the array in one CPI share a
single RCS realisation, so spatial non-coherent integration is correctly
modelled with Swerling 1 (Rayleigh) or 3 (chi-4), not the independent-per-look
Swerling 2/4 -- which is why collapsing is supported for cases 0/1/3 and the
independent cases 2/4 raise an explanatory error.

### In-phase (coherent) transmit

As an alternative to orthogonal MIMO, `transmit_coherent=True` models all `n_tx`
transmitters radiating the same waveform in phase -- a transmit phased array
steered at the target. On-target power density is `n_tx**2` over a single
transmitter (`n_tx` from the summed power, `n_tx` from transmit directivity), so
for a target in the formed beam the integrated SNR is `+20 log10(n_tx)` over one
TX.

The comparison with DDM/DDMA MIMO is best made in **post-combination SNR**, not
in instantaneous on-target power density -- which for orthogonal MIMO isn't even
a single number, since it varies chirp to chirp with the relative TX phases.
After TX combining the signal power is the same in both (`n_tx**2`): coherent
transmit builds it up on the target, before the receiver, while MIMO resolves the
`n_tx` transmitters and recombines them digitally. The noise is what differs --
the MIMO path sums `n_tx` independently noisy per-transmitter estimates (receiver
noise enters `n_tx` times), whereas coherent transmit incurs receiver noise only
once. So in a receiver-noise-limited model coherent transmit has a further
`+10 log10(n_tx)` SNR over DDM-MIMO: an `n_tx**2` transmit contribution to the
SNR versus `n_tx` for the virtual array.

There is no virtual TX aperture in this mode, so covering a wide field of view
means scanning the transmit beam (more dwell/scan time) -- which this
per-direction budget does not amortise for you.

### Detection

`radarperf.detection` implements a square-law detector integrating `n_pulses`
non-coherent looks, for Swerling cases 0-4 (5 is treated as 0). The closed forms
were cross-checked against Monte-Carlo simulation. It also accepts an
`n_collapsing` count of noise-only cells (the DDMA empty-subband case).
`required_snr_db` inverts the exact Pd; `albersheim_required_snr_db` and
`shnidman_required_snr_db` provide the usual fast approximations.

## Architecture

Every ingredient is a `typing.Protocol`, so any object exposing the right
attributes plugs in -- no subclassing or registration; `mypy` checks the
structural match. The protocols are `Frontend`, `Antenna`, `Waveform`,
`Processing`, `Target` and `Environment` (in `radarperf.protocols`).

* **Front-end** — `GenericFrontend` plus `cascade()` and datasheet-sourced presets
  (`awr1243`, `awr2243`, `awr2e44p`, `ctrx8188f`).
* **Antenna** — `ConstantGainAntenna` -> `GaussianBeamAntenna` ->
  `PatternCutAntenna` (separable az/el cuts) -> `PatternUVAntenna` (full pattern).
* **Waveform** — `FmcwWaveform` with derived resolution and ambiguity figures.
* **Processing** — `StandardProcessing` (MIMO scheme, per-axis combination, DDMA
  subbands/collapsing, in-phase coherent transmit, window / straddle / CFAR /
  beamforming / MIMO losses). `StagedProcessing` is a generic alternative: an
  explicit list of named coherent/non-coherent `CombiningStage` axes for
  combining topologies beyond the fixed RX/TX axes.
* **Target** — `ConstantRcsTarget`, `AspectRcsTarget`, `RcsTableTarget`, presets.
* **Environment** — `FreeSpace`, `Atmosphere`, `Rain`, `CompositeEnvironment`.

Sweeps (`radarperf.sweeps`) wrap the per-point link budget into the arrays you
plot: `range_sweep`, `map_2d` (with `range_azimuth_geometry`,
`range_elevation_geometry`, `xy_geometry`, `xz_geometry` builders),
`coverage_range` and `coverage_vs_azimuth`.

Optional Matplotlib helpers (`radarperf.plotting`, requires the `plot` extra)
turn those into figures: `plot_snr_vs_range`, `plot_pd_vs_range`, `plot_pd_map`
(with Pd contours) and `plot_coverage` (polar). Each takes an optional `ax` and
returns it, so they compose and overlay; see `examples/plotting_demo.py`.

## Assumptions and caveats

* **Chipset presets use datasheet figures** (TI parts: public headline values
  from ti.com; Infineon CTRX8188F: controlled-datasheet typical) — verify against
  the exact revision or your own measurements. **RCS presets are illustrative.**
  Copy a preset and override the fields with controlled or measured numbers.
* **Rain clutter is approximate.** Attenuation uses the ITU-R P.838 power law;
  the volume-clutter reflectivity uses a Marshall-Palmer Z-R relation with a
  Rayleigh assumption (at 77 GHz raindrops are in the Mie regime), so calibrate
  `dielectric_factor` and the Z-R coefficients before trusting absolute numbers.
* Antenna pattern separability (`PatternCutAntenna`) is exact on the cuts and a
  reasonable engineering approximation off them.

## Development

```bash
make pre_commit   # black (reformats) + flake8 + mypy --strict
make check        # same, check-only (no reformat) -- what CI runs
make test         # pytest tests
make examples     # run example scripts as a smoke check
```

mypy runs in **strict** mode here; keep the tree type-clean. flake8 is
configured in `pyproject.toml` (line length 88) via `Flake8-pyproject`. CI runs
the same checks across Python 3.12 and 3.14.

## Possible next steps

Longer-term extensions: short-range effects (receiver saturation / near-field,
TX-to-RX leakage, ADC dynamic range, phase-noise / reciprocal-mixing skirts that
limit SCR against strong nearby reflectors), eclipsing, ADC quantisation noise,
range/Doppler-cell clutter for ground / guardrail / multipath, waveform validity
checks (max beat frequency, range / velocity ambiguity, duty cycle, EIRP),
computing the angular beamforming / straddle loss from the actual array geometry
rather than a configurable scalar, and a direction-dependent antenna/scene noise
temperature (the current `T_ant` is a single scalar per `Radar`; likely a minor
effect at these frequencies and noise figures, where receiver noise dominates).
