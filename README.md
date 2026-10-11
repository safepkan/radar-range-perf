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
    AntennaPair, GaussianBeamAntenna, Geometry, frontend, target,
)

waveform = FmcwWaveform(
    center_frequency_hz=77e9, bandwidth_hz=1.0e9, sample_rate_hz=20e6,
    n_samples=256, n_chirps=128,
)
element = GaussianBeamAntenna(boresight_gain_dbi=11.0,
                              beamwidth_az_deg=80.0, beamwidth_el_deg=20.0)

radar = Radar(
    frontend=frontend.awr2243(),                 # datasheet preset
    waveform=waveform,
    processing=StandardProcessing(mimo=MimoScheme.TDM),
    antenna=AntennaPair.from_element(element),
    default_pfa=1e-6,                            # per range-Doppler cell
)

budget = radar.link_budget(target.car(), Geometry(range_m=120.0))
print(budget)                                    # full dB breakdown
print(radar.probability_of_detection(target.car(), Geometry(range_m=120.0)))
```

See `examples/basic_link_budget.py` and `examples/pd_vs_range.py` for sweeps,
coverage and track acquisition.

## Documentation

* [docs/link_budget.md](docs/link_budget.md) — how the toolbox gets from its
  inputs to SNR and Pd, with derivations: the energy form of the range
  equation, the system temperature, MIMO and channel combination, collapsing,
  in-phase transmit and detection.
* [docs/losses.md](docs/losses.md) — every term between the inputs and the
  detector: where it lives, its default, what sets its value, and a checklist
  for studies.
* [docs/false_alarms.md](docs/false_alarms.md) — the Pfa per range–Doppler
  cell, and how zero padding and beam sets raise the threshold.
* [docs/phase_noise.md](docs/phase_noise.md) — how LO phase noise affects an
  FMCW radar, with derivations: the delay filter, the per-chirp frequency
  error and its Doppler integration loss, chirp timing, skirts.
* [docs/phase_noise_prediction.md](docs/phase_noise_prediction.md) — predicting
  a strong return's phase noise in range and Doppler with `phase_noise_fft`.
* [docs/hardware/](docs/hardware/) — what is known about particular parts:
  datasheet figures, how to read them, measurements. So far the
  [CTRX8188F](docs/hardware/ctrx8188f.md) and the
  [SENCITY antennas](docs/hardware/sencity.md).
* [studies/](studies/README.md) — dated studies that used the toolbox, kept as
  records of what was done.

## How the SNR is computed

The engine uses the energy form of the FMCW radar equation, a single-sample SNR
times a dimensionless coherent gain:

```
snr_sample = Pt * Gt * Gr * lambda^2 * sigma
             / ( (4*pi)^3 * R^4 * k * Tsys * Bn * L_path * L_system )

SNR        = snr_sample * coherent_gain / processing_losses
```

The noise is `k * Tsys * Bn` per complex sample, with the noise bandwidth `Bn`
equal to the sample rate by default, so the SNR comes out as the received
energy over the noise density. Signal and noise are referred to the
front-end's RF reference plane, where the datasheet TX power and noise figure
apply. The coherent gain (range FFT × Doppler FFT × coherently combined
channels) and the named processing losses come from the processing model.
Antenna gains are element gains; array gain lives in the coherent gain. The
reported SNR is per detector look: channels combined non-coherently reach the
detector as looks. [docs/link_budget.md](docs/link_budget.md) derives all of
this: the system temperature, the MIMO bookkeeping, coherent and non-coherent
combination with DDMA collapsing, in-phase transmit and the detector.

### Losses

`L_system` collects the terms that lie outside the datasheet front-end, the
antenna pattern and the processing model: TX power and noise-figure derating,
TX/RX feed losses from the MMIC reference plane to the antenna, antenna
efficiency relative to directivity, a radome (applied on both passes), and a
range-dependent coherence loss from per-chirp frequency errors. They are the
fields of `SystemLosses`, passed as `Radar(losses=...)`, and all default to
zero. Printing a `LinkBudget` lists every processing and system term with its
value, zeros included, so an omitted term shows as an explicit zero.
[docs/losses.md](docs/losses.md) catalogues all terms, including those in other
components (`Atmosphere`, `Rain`, processing losses) and those not modelled,
with their defaults, what sets their values and a checklist for studies. Values
for particular parts (the CTRX8188F, the SENCITY antennas) are on the pages
under [docs/hardware/](docs/hardware/).

`chirp_repetition_time_s` is optional for range/SNR/Pd calculations. Leave it
unset for range-only budgets; set it when you need CPI duration, velocity
resolution or unambiguous velocity figures.

### MIMO, channel combination and detection

`StandardProcessing` takes the MIMO scheme (`NONE`, `TDM`, `DDM`, `BPM`) and,
for each of the RX axis and the TX (DDMA subband) axis, whether its channels
are combined coherently, by beamforming into the coherent gain, or
non-coherently, as detector looks. TDM buys virtual aperture but not SNR;
DDM and BPM gain a factor `n_tx`, because every transmitter sends on every
chirp. Empty DDMA subbands summed non-coherently add noise but no signal; the
link budget reports them as `n_collapsing` and the detector integrates them
exactly. `transmit_coherent=True` models all transmitters sending in phase, a
transmit phased array. `StagedProcessing` takes an explicit list of combining
stages for other topologies. `examples/ddma_combinations.py` compares the
paths for a DDMA part.

Range and Doppler window and straddle losses are computed from the windows
(`range_window`, `doppler_window`, any SciPy window name; Hann by default) and
the FFT sizes (`range_fft_size`, `doppler_fft_size`; no zero-padding by
default): the window loss from its equivalent noise bandwidth, the straddle
loss averaged over a target position uniform between FFT bins. Hann without
padding gives 1.76 dB and 0.47 dB per axis. Each value can be overridden;
`window_loss_db` and `straddle_loss_db` (with `statistic="max"` for the worst
case) compute them directly, and `WINDOW_LOSS_*` constants are exported for
common windows.

The false-alarm probability given to `Radar` (`default_pfa`, and the `pfa`
argument of `Radar.link_budget`, `Radar.probability_of_detection` and the
sweeps in `radarperf.sweeps`) is per range–Doppler resolution cell: false
detections per bin of the unpadded FFTs, over all beams formed in that cell.
Zero padding and receive beam sets add tests per cell, so the engine counts
them (`radarperf.false_alarms`) and tests each bin at a lower Pfa. Padding therefore lowers straddle loss but
raises the threshold: Hann with fourfold padding saves 0.44 dB of straddle
and costs 0.18 dB of threshold per axis. The link budget prints the tests per
axis, the per-test Pfa and the threshold increase. See
[docs/false_alarms.md](docs/false_alarms.md); `Radar(pfa_reference="test")`
restores the earlier per-test convention.

`radarperf.detection` models a square-law detector that sums non-coherent
looks, for Swerling cases 0–4 (5 is treated as 0), checked against Monte Carlo
simulation. `required_snr_db` inverts the exact Pd, and
`albersheim_required_snr_db` and `shnidman_required_snr_db` are the usual
approximations. Looks over channels within one CPI share one RCS draw, so
model such targets as Swerling 1 or 3, not 2 or 4.

The low-level functions in `radarperf.detection` (`probability_of_detection`,
`required_snr_db`, `detection_threshold`, `albersheim_required_snr_db`,
`shnidman_required_snr_db`) take the Pfa per test and apply no correction.
To evaluate a radar at its per-cell Pfa with them, pass
`radar.false_alarm_budget().pfa_per_test`.

## Architecture

Every ingredient is a `typing.Protocol`, so any object exposing the right
attributes plugs in — no subclassing or registration; `mypy` checks the
structural match. The protocols are `Frontend`, `Antenna`, `Waveform`,
`Processing`, `Target` and `Environment` (in `radarperf.protocols`).

* **Front-end** — `GenericFrontend` plus `cascade()` and datasheet-sourced presets
  (`awr1243`, `awr2243`, `awr2e44p`, `ctrx8188f`; see
  [docs/hardware/ctrx8188f.md](docs/hardware/ctrx8188f.md) for the last).
* **Antenna** — models `ConstantGainAntenna` → `GaussianBeamAntenna` →
  `PatternCutAntenna` (separable az/el cuts) → `PatternUVAntenna` (full
  pattern), plus `UniformRectangularApertureAntenna` for an analytical uniform
  rectangular-aperture sinc pattern, `RectangularArrayAntenna` for FFT patterns
  from arbitrary complex aperture excitations and `UniformArrayAntenna` for a
  steerable ULA/URA factor layered over any element/subarray pattern.
  `MultiBeamUniformArrayAntenna` supplies the best-beam envelope and exposes
  every individual beam for a set of u/v steering points; the engine counts
  its beams as false-alarm tests. The engine takes a
  transmit/receive `AntennaPair` (`AntennaPair.from_element` when the two
  coincide); `load_pattern_cut_csv` / `load_antenna_pair_csv` build elements
  from measured/datasheet az/el tables, with packaged Huber+Suhner presets
  (`sencity_this_ii`, `sencity_farad_iv`).
* **Waveform** — `FmcwWaveform` with derived resolution and ambiguity figures.
* **Processing** — `StandardProcessing` (MIMO scheme, per-axis combination, DDMA
  subbands/collapsing, in-phase coherent transmit, window / straddle / CFAR /
  beamforming / MIMO losses). `StagedProcessing` is a generic alternative: an
  explicit list of named coherent/non-coherent `CombiningStage` axes for
  combining topologies beyond the fixed RX/TX axes.
* **Target** — `ConstantRcsTarget`, `AspectRcsTarget`, `RcsTableTarget`, presets.
* **Environment** — `FreeSpace`, `Atmosphere` (constant, or `Atmosphere.itu_p676`
  for given conditions), `Rain` (ITU-R P.838-3), `CompositeEnvironment`.
* **System losses** — `SystemLosses`: derating, feeds, antenna efficiency, radome
  and per-chirp coherence (see [docs/losses.md](docs/losses.md)).
* **Phase noise** — `radarperf.phase_noise`: the per-chirp frequency error behind
  the coherence loss, from a CW spectrum (`chirp_frequency_error_rms_hz`) or the
  chirp timing (`ChirpSettling`), and a prediction of a strong return's skirt and
  pedestal in range and Doppler (`phase_noise_fft`). [docs/phase_noise.md](docs/phase_noise.md)
  explains how phase noise affects an FMCW radar, with derivations;
  [docs/phase_noise_prediction.md](docs/phase_noise_prediction.md) covers the
  prediction.

Sweeps (`radarperf.sweeps`) wrap the per-point link budget into the arrays you
plot: `range_sweep`, `map_2d` (with `range_azimuth_geometry`,
`range_elevation_geometry`, `xy_geometry`, `xz_geometry` builders),
`coverage_range` and `coverage_vs_azimuth`. `acquisition_sweep` extends this to
multiple scans: a `radarperf.trajectory.Trajectory` (currently `RadialApproach`,
a target approaching the radar straight on) is sampled at the radar's frame /
revisit cadence and the per-scan, cumulative and sliding M-of-N detection
probabilities are returned together. The frame time defaults to the waveform's
CPI duration (a staring radar) and is otherwise the scan schedule's revisit
interval; it is a scheduling input to the sweep, deliberately kept out of the
single-CPI `FmcwWaveform`. More general trajectories (crossing, waypoint,
numerically integrated) are future work — each need only implement `geometry_at`.

Optional Matplotlib helpers (`radarperf.plotting`, requires the `plot` extra)
turn those into figures: `plot_snr_vs_range`, `plot_pd_vs_range`,
`plot_acquisition`, `plot_pd_map` (with Pd contours) and `plot_coverage`
(polar); `plot_pattern_cut` / `plot_pattern_cuts` draw an antenna's az/el gain
cuts (TX vs RX), and `plot_pattern_uv` draws its full direction-cosine pattern.
Each takes an optional `ax` and returns it, so they compose and overlay; see
`examples/plotting_demo.py` and `examples/antenna_pattern.py`.

## Assumptions and caveats

* **Chipset presets use datasheet figures** (TI parts: public headline values
  from ti.com; Infineon CTRX8188F: controlled-datasheet typical) — verify against
  the exact revision or your own measurements. **RCS presets are illustrative.**
  Copy a preset and override the fields with controlled or measured numbers.
  [docs/hardware/](docs/hardware/) collects what is known about a part beyond
  its preset.
* **Rain clutter is approximate.** Attenuation uses ITU-R P.838-3 and clear-air
  absorption ITU-R P.676-13 (`radarperf.itu`, checked against ITU-published
  values); the volume-clutter reflectivity uses a Marshall-Palmer Z-R relation with a
  Rayleigh assumption (at 77 GHz raindrops are in the Mie regime), so calibrate
  `dielectric_factor` and the Z-R coefficients before trusting absolute numbers.
* **Losses default to zero.** `SystemLosses` terms, the environment
  (`FreeSpace` unless one is passed) and the beamforming/MIMO/other processing
  losses all start at zero; choose them per study (see
  [docs/losses.md](docs/losses.md)).
* Antenna pattern separability (`PatternCutAntenna`) is exact on the cuts and a
  reasonable engineering approximation off them. **The SENCITY presets are
  digitised** from preliminary datasheet charts (PCB mount, no radome) — verify
  against the controlled datasheet for your revision.

## Development

```bash
make pre_commit   # black (reformats) + flake8 + mypy --strict
make check        # same, check-only (no reformat) -- what CI runs
make test         # pytest tests
make smoke        # run example scripts headless as a smoke check
```

mypy runs in **strict** mode here; keep the tree type-clean. flake8 is
configured in `pyproject.toml` (line length 88) via `Flake8-pyproject`. CI runs
the same checks across Python 3.12 and 3.14.

## Possible next steps

The phase-noise skirts and pedestals of strong returns are predicted separately
(`phase_noise_fft`, [docs/phase_noise_prediction.md](docs/phase_noise_prediction.md)).
Bringing them into the link budget, as a floor that can exceed the thermal noise
near strong returns, with channel combining, remains future work.

Longer-term extensions: short-range effects (receiver saturation / near-field,
TX-to-RX leakage, ADC dynamic range), eclipsing, ADC quantisation noise,
range/Doppler-cell clutter for ground / guardrail / multipath, waveform validity
checks (max beat frequency, range / velocity ambiguity, duty cycle, EIRP),
computing the angular beamforming / straddle loss from the actual array geometry
rather than a configurable scalar, and a direction-dependent antenna/scene noise
temperature (`T_ant` is one value per `Radar`; looking straight up rather than
along the horizon gains a few tenths of a dB with these noise figures, see
[docs/link_budget.md](docs/link_budget.md#a-cold-sky)).
