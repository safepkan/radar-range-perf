# Losses and other terms in the range equation

The toolbox computes SNR from datasheet front-end figures, an antenna pattern,
a processing model, a target and an environment. This page lists every term
between those inputs and the detector: where it lives in the toolbox, its
default, and the sourced values available for it. Many terms default to zero. A
zero is a modelling choice, so a study or one-off calculation should state it
as one. Printing a `LinkBudget` lists each named term with its value, zeros
included.

Every number below is taken from a cited source, derived on this page, or
computed with the toolbox (and says so). Where no source is available the page
says that instead of giving a typical value. References are listed at the end.

## The equation with all terms

```
SNR = Pt Gt Gr λ² σ G_coh / ((4π)³ R⁴ k T_sys B_n L_path L_system L_proc)

L_system = D_tx L_tx,feed L_tx,ant · L_radome² · L_rx,ant L_rx,feed · L_coh(R)
T_sys    = T_ant / L_rx + T0 (1 − 1/L_rx) + (F D_nf − 1) T0
L_rx     = L_radome L_rx,ant L_rx,feed
```

`Pt` and `F` are the front-end's datasheet figures at its RF reference plane,
`Gt` and `Gr` come from the antenna pattern (usually a directivity), `L_path`
from the environment, and `G_coh` and `L_proc` from the processing model.
`L_system` and the derating factors `D_tx` and `D_nf` are the fields of
`SystemLosses`, passed as `Radar(losses=...)`. Signal and noise are referred to
the front-end reference plane. The receive-side losses are passive parts at
`T0 = 290 K`, so they also emit noise. With the default `T_ant = T0` the
expression reduces to `F D_nf T0`, so a receive-side loss lowers SNR by exactly
its value; a colder scene makes it cost slightly more.

```python
from radarperf import Atmosphere, Radar, SystemLosses

losses = SystemLosses(
    tx_power_derating_db=1.0,  # CTRX8188F, over temperature [1, Table 24]
    tx_antenna_loss_db=0.92,  # SENCITY FARAD-IV bound [2]
    rx_antenna_loss_db=0.92,
    chirp_frequency_error_rms_hz=3.5e3,  # measured, well-timed ramps [8]
)
radar = Radar(..., losses=losses)
budget = radar.link_budget(target, geometry, Atmosphere())  # P.676-13 standard [4]
print(budget)
```

## Catalogue

### Front-end

| Term | Where | Default | Sourced values | Source |
|---|---|---|---|---|
| TX power | `Frontend.tx_power_w` | datasheet typical | CTRX8188F: 14.5 dBm typical, 13.0 dBm minimum per channel | [1] Table 22 |
| TX power derating | `SystemLosses.tx_power_derating_db` | 0 | CTRX8188F: up to 1 dB over temperature with closed-loop power control; up to 1.5 dB variation over a ramp in 76–77 GHz; 1.5 dB from typical to minimum | [1] Tables 22, 24 |
| Noise figure | `Frontend.noise_figure_db` | datasheet typical | CTRX8188F, 10 MHz IF: low-noise mode 10.2 dB typical, 13.2 dB maximum (the preset); ultra-low-noise mode 9.7 dB typical, 12.7 dB maximum. The modes are the RX gain steps 0 dB and +3 dB (below) | [1] Table 30; [13] |
| NF derating | `SystemLosses.noise_figure_derating_db` | 0 | CTRX8188F: up to 3 dB from typical to maximum; for a negative RX gain step, up to the step's magnitude (a worst-case bound); 0.3 dB (low-noise) or 0.2 dB (ultra-low-noise) higher at 1 MHz IF than at 10 MHz | [1] Table 30; [13] |
| Noise bandwidth | `FmcwWaveform.noise_bandwidth_hz` | the sample rate (ideal anti-alias filter) | none | |
| ADC quantisation, IF gain shape | not modelled | | none | |

The CTRX8188F datasheet quotes RF parameters at the waveguide port on the far
side of a 1.2 mm reference PCB, so the package-to-PCB transition is inside its
figures for the reference footprint and stack-up ([1] Section 5, Figure 5). A
different PCB, or anything between that plane and the antenna, is a feed loss.

The datasheet gives the noise figure for a "low noise operation mode" and an
"ultra low noise operation mode" ([1] Table 30). The two modes are the RX gain
steps 0 dB and +3 dB, not a separate setting. The documents point that way:

- Every Table 30 row for either mode (nominal conversion gain, noise figure at
  1 MHz and at 10 MHz IF) is specified at one gain step: 0 dB for low-noise,
  +3 dB for ultra-low-noise.
- The two modes' nominal conversion gains are 3 dB apart, the size of that
  step, at minimum, typical and maximum: 38, 41.5 and 45 dB FS/mW against 41.0,
  44.5 and 48.0 dB FS/mW.
- The datasheet does not mention the modes outside Table 30, and the user
  manual [11] has no noise-mode setting. Its receiver configuration offers a
  gain select with steps +3, 0, −3, −6, −12 and −18 dB, in `Configure_RX()`
  (Table 46) and per ramp segment (`RX_GAINSET_SEL`, Table 120).

Infineon has confirmed it [13]: there is no noise-mode setting; the system
integrator sets the RX gain with `Configure_RX()` or in Infineon's ramp design
tool, and the default is 0 dB. A receiver at +3 dB gain therefore has the
ultra-low-noise figures, 0.5 dB below the preset at 10 MHz IF: use
`frontend.ctrx8188f(noise_figure_db=9.7)`. For a negative gain step, the
datasheet's allowance of at most the step's magnitude in extra noise figure is
a worst-case bound, the theoretical limit for a gain reduction; Infineon did
not say which row and column it is counted from, so the safe reading is the
0 dB row's maximum plus the step's magnitude.

Infineon also states [13] that the datasheet's minimum and maximum values hold
over the whole functional range (junction temperature −40 to 135 °C,
76–81 GHz) unless a row states a narrower condition, and that typical values
are for a nominal part at nominal supply voltage and room temperature. So a
typical value is a starting point for a unit at room temperature, not a bound;
derating terms cover temperature and part spread.

### Feed and antenna

| Term | Where | Default | Sourced values | Source |
|---|---|---|---|---|
| TX and RX feed | `SystemLosses.tx_feed_loss_db`, `rx_feed_loss_db` | 0 | none yet; from the MMIC reference plane to the antenna port | |
| Antenna efficiency and mismatch | `SystemLosses.tx_antenna_loss_db`, `rx_antenna_loss_db` | 0 | SENCITY FARAD-IV and THIS-II: radiation efficiency ≥ 90 % (≤ 0.46 dB) and reflection coefficient ≤ −10 dB (mismatch ≤ 0.46 dB), so realized gain is at most 0.92 dB below the stated directivity, mounted on a PCB without a radome | [2], [3] |
| Aperture taper | antenna model | | `aperture_efficiency` and array weights already reduce the directivity; do not count it again | |
| Channel amplitude and phase errors | not a field | 0 | random phase errors of rms σ reduce coherent gain by exp(−σ²), i.e. 10 log10(e) σ² dB: 0.13 dB at 10°, 0.53 dB at 20°. CTRX8188F: RX channel-to-channel phase drift ≤ 3.5°, TX phase setting accuracy ≤ 4° | [7]; [1] Tables 24, 30 |
| Angular straddle | `StandardProcessing.beamforming_loss_db`, or a multi-beam antenna model | 0 | | do not use both |

Channel errors apply to coherent TX or RX combining; put them in
`beamforming_loss_db` or `other_loss_db`. The SENCITY presets and the
analytical aperture and array models are directivities, so they need the
antenna loss.

### Radome and installation

| Term | Where | Default | Sourced values | Source |
|---|---|---|---|---|
| Radome | `SystemLosses.radome_one_way_loss_db`, applied on both passes | 0 | no typical value; published single examples: a radome measured at 1.2–1.6 dB two-way at three points, and an emblem at 0.64 dB one-way | [5] Fig. 1; [6] |
| Water film, ice, snow, dirt | the same field | 0 | none | |
| Pattern change from radome, bumper and vehicle | antenna model | | not modelled | |

A single-layer radome's loss is smallest when its wall is an integer number of
half wavelengths thick in the material; paint and coatings shift that optimum
([5] Section 4.1). Measure the installed configuration.

### Propagation

| Term | Where | Default | Sourced values | Source |
|---|---|---|---|---|
| Gaseous absorption | `Atmosphere(specific_attenuation_db_per_km)`, `Atmosphere.itu_p676(...)` or `Atmosphere.itu_reference(height_m)` | the engine's default environment is `FreeSpace()`, i.e. 0; `Atmosphere()` uses 0.35 dB/km | see the table below | [4] |
| Rain attenuation | `Rain(rain_rate_mm_per_hr, polarization_tilt_deg)` | off | `k R^α` with `k`, `α` from ITU-R P.838-3 at the waveform's centre frequency; see the table below | [9] |
| Rain clutter | `Rain` | off | Marshall–Palmer Z–R relation, Rayleigh reflectivity and Probert-Jones beam filling; not validated at 77 GHz, where raindrops are Mie scatterers | see `radarperf.environment` |
| Fog, snow, dust | not modelled | | | |
| Multipath (ground reflection) | not modelled | 0 | derived: the two-way propagation factor is at most (1 + \|Γ\|)⁴, +12 dB for \|Γ\| = 1, with nulls in between | |

`Atmosphere` is one constant one-way specific attenuation γ; the two-way loss
is `2 γ R`, independent of frequency and altitude. Choose γ for the conditions
of the study, or compute it with `Atmosphere.itu_p676(frequency_hz,
temperature_c=..., pressure_hpa=..., water_vapour_density_g_m3=...)`, which
implements the line-by-line method of ITU-R P.676-13 Annex 1 [4] (in
`radarperf.itu`, checked against the ITU's validation examples). At 76.5 GHz
and 1013.25 hPa total pressure:

| Temperature, water vapour density | One-way [dB/km] | Two-way at 1 km [dB] |
|---|---:|---:|
| 15 °C, 0 g/m³ (dry air only) | 0.10 | 0.20 |
| −10 °C, 2 g/m³ | 0.21 | 0.43 |
| 15 °C, 7.5 g/m³ (standard atmosphere; the default, rounded) | 0.347 | 0.69 |
| 25 °C, 11.5 g/m³ | 0.45 | 0.90 |
| 30 °C, 20 g/m³ | 0.77 | 1.54 |

For the standard atmosphere the value is 0.35 dB/km at 76 GHz and 0.34 dB/km
from 77 to 81 GHz.

Gaseous attenuation falls with height, because pressure, and above all water
vapour, fall. `Atmosphere.itu_reference(height_m)` evaluates the same P.676-13
method in the ITU-R reference atmosphere of P.835-7 Annex 1 [12]: temperature
and total pressure of the U.S. Standard Atmosphere 1976, and water vapour
7.5 g/m³ at sea level falling with a 2 km scale height. It assumes a
horizontal path at that height. At 76.5 GHz:

| Height | Temperature, total pressure, water vapour density | One-way [dB/km] |
|---:|---|---:|
| 0 m | 15.0 °C, 1013.25 hPa, 7.5 g/m³ | 0.35 |
| 1000 m | 8.5 °C, 898.8 hPa, 4.55 g/m³ | 0.22 |
| 2000 m | 2.0 °C, 795.0 hPa, 2.76 g/m³ | 0.15 |
| 5000 m | −17.5 °C, 540.5 hPa, 0.62 g/m³ | 0.056 |

Rain attenuation at 77 GHz from ITU-R P.838-3 [9] (its Table 5 lists
`k_H = 1.1320`, `α_H = 0.7177`, `k_V = 1.1276`, `α_V = 0.7073`), for a
horizontal path:

| Rain rate | Horizontal [dB/km] | Vertical [dB/km] |
|---:|---:|---:|
| 1 mm/h | 1.13 | 1.13 |
| 5 mm/h | 3.59 | 3.52 |
| 10 mm/h | 5.91 | 5.75 |
| 25 mm/h | 11.4 | 11.0 |
| 50 mm/h | 18.8 | 17.9 |

### Waveform and LO coherence

| Term | Where | Default | Sourced values | Source |
|---|---|---|---|---|
| Per-chirp frequency error | `SystemLosses.chirp_frequency_error_rms_hz` | 0 | see the tables below | [8], [1] Table 22 |
| Phase noise within a chirp | not a field | | CTRX8188F, 76–77 GHz table, offsets 100 kHz–10 MHz: ≤ 0.02 dB (typical) and ≤ 0.06 dB (maximum) at 300 m–1 km; computed with `radarperf.phase_noise` | [1] Table 22 |
| Phase-noise skirts of strong returns | `radarperf.phase_noise` diagnostics only | | an SINR term near strong clutter | |
| Chirp nonlinearity | not modelled | | | |
| Range migration during the CPI | not modelled | | negligible while \|v\| T_CPI is small against the range resolution | |
| Doppler spread of the target | not modelled | | | |

A per-chirp RF frequency offset `δf`, constant within a chirp and independent
from chirp to chirp, gives a beat phase error of rms `σ = 2π δf · 2R/c`. For
Gaussian errors the Doppler peak keeps `exp(−σ²)` of its power and the rest
spreads into a pedestal, so the loss is `10 log10(e) σ²` dB, growing as `R²`.

Values of `δf` for the CTRX8188F, all from [8]:

| Case | δf rms |
|---|---:|
| Computed from the CW phase-noise table [1, Table 22], typical; for the waveforms in [8] | 2.7–3.4 kHz |
| Same, maximum table | 4.8–5.9 kHz |
| Measured: 2 µs flyback, 83.7 µs wait, 4.0 µs pre-payload | 3.5 kHz |
| Measured: 60 ns flyback, 60 ns wait; pre-payload 5.5, 4.2, 3.5 µs | 14–19, 21, 30 kHz |

The measurements in [8] confirm the `R²` law up to 270 m; beyond that it is an
extrapolation. Loss from the formula above:

| δf rms | 100 m | 300 m | 1 km |
|---:|---:|---:|---:|
| 3.5 kHz | 0.00 dB | 0.01 dB | 0.09 dB |
| 5.9 kHz | 0.00 dB | 0.02 dB | 0.27 dB |
| 14 kHz | 0.01 dB | 0.13 dB | 1.5 dB |
| 21 kHz | 0.03 dB | 0.30 dB | 3.4 dB |
| 30 kHz | 0.07 dB | 0.62 dB | 6.9 dB |

### Processing

These were explicit before `SystemLosses`; they are listed for completeness.

| Term | Where | Default | Basis |
|---|---|---|---|
| Range and Doppler windows | `range_window`, `doppler_window` (SciPy window names); override with `range_window_loss_db`, `doppler_window_loss_db` | Hann: 1.76 dB each | computed (`window_loss_db`): 10 log10 of the periodic window's equivalent noise bandwidth in bins; matches [10] Table 1 |
| Range and Doppler straddle | computed from the window and `range_fft_size`, `doppler_fft_size` (zero-padding); override with `range_straddle_loss_db`, `doppler_straddle_loss_db` | Hann, no padding: 0.47 dB each | computed (`straddle_loss_db`): the peak-bin loss averaged in dB over a target position uniform between FFT bins. Hann: 0.47 dB without padding, 0.12 dB with twofold and 0.03 dB with fourfold padding; the worst case (midway between bins, `statistic="max"`) is 1.42 dB without padding, as in [10] Table 1. Padding also adds tests per cell; see the next row |
| Multiple testing in range and Doppler | computed from the same windows and FFT sizes; acts on the threshold, not the SNR (`LinkBudget.false_alarms`) | Hann, no padding: 0.98 tests per cell each, −0.01 dB | computed (`radarperf.false_alarms`); see "False alarms per cell" below. Hann: +0.13 dB of threshold with twofold and +0.18 dB with fourfold padding per axis |
| CFAR | `cfar_loss_db` | 1.0 dB | an allowance for a CFAR not yet chosen, held fixed when other assumptions change. For scale: cell-averaging CFAR with 32 reference cells costs 0.97 dB (16 cells: 2.0 dB; 64 cells: 0.48 dB) for a Swerling 1 target, square-law detection, Pfa 10⁻⁶ per test, from Pfa = (1 + T/N)⁻ᴺ and Pd = (1 + T/(N(1 + SNR)))⁻ᴺ against the fixed-threshold case |
| Beamforming or angle straddle | `beamforming_loss_db` | 0 | applied only with coherent angular combination |
| Multiple testing over beams | computed when the receive antenna is a beam set (`MultiBeamUniformArrayAntenna`); acts on the threshold | 1 test (no beam set) | computed (`radarperf.false_alarms`); see "False alarms per cell" below |
| MIMO | `mimo_loss_db` | 0 | e.g. DDMA or BPM orthogonality |
| Collapsing | computed | | empty DDMA subbands, handled by the detector |
| Other | `other_loss_db` | 0 | catch-all; say what it holds |

### Detection, target and scene

| Term | Where | Default | Notes |
|---|---|---|---|
| Pfa per range–Doppler cell | `Radar.default_pfa` and the `pfa` arguments of `Radar` and `radarperf.sweeps` | 10⁻⁶ | false detections per unpadded range–Doppler cell, over all beams; the detector tests each bin at the lower per-test Pfa that holds it. `Radar(pfa_reference="test")` applies the value per test, the convention before 2026-10-01. The functions in `radarperf.detection` take the Pfa per test |
| Fluctuation | `Target.swerling` | 1 for the presets | |
| RCS | target model | illustrative presets | |
| Antenna noise temperature | `Radar.antenna_noise_temperature_k` | 290 K (the noise-figure reference temperature) | |

### Not covered

Interference from other radars, receiver compression and TX-to-RX leakage at
short range, and clutter other than rain (ground, guardrails).

## False alarms per cell

`Radar.default_pfa` is the false-alarm probability per range–Doppler
resolution cell: the expected number of false detections per bin of the
unpadded range and Doppler FFTs, over all beams formed in that cell. False
alarms per frame are this value times the numbers of range and Doppler cells.
A detection is a local maximum along each FFT axis (peak grouping), so a noise
peak that spreads over neighbouring bins counts once.

Each test (one FFT bin of one beam) is compared with one threshold. Zero
padding and beam sets add tests per cell, partially correlated with each
other, so the threshold must rise to hold the per-cell value.
`Radar.false_alarm_budget()` counts the effective tests per cell and returns
the per-test Pfa; the detector uses that, and `LinkBudget` prints it after
the processing losses. The convention covers `Radar` and the sweeps in
`radarperf.sweeps`. The low-level functions in `radarperf.detection`
(`probability_of_detection`, `required_snr_db`, `detection_threshold` and
the Albersheim and Shnidman approximations) take the Pfa per test; pass them
`radar.false_alarm_budget().pfa_per_test`. For the Lannik Psi study's large RX variant
(`studies/2026-09-02_lannik-psi/lannik_psi.py`, 64 receive beams):

```
Pfa per cell:        1.0e-06
  range tests           0.99
  doppler tests         0.99
  angle tests          54.38
  Pfa per test        1.9e-08
  threshold increase    1.10 dB
```

The counts come from `radarperf.false_alarms`, where the methods are
derived:

- **Range and Doppler:** the expected number of local maxima above the
  threshold per resolution cell, from the window's correlation between
  neighbouring bins and the padding.
- **Angle:** the probability that the largest beam power exceeds the
  threshold, from the beam weights (`BeamSet.beam_weights()`).
- **All axes:** the product of the per-axis factors. This is an
  approximation for small Pfa, where exceedances are nearly independent
  between axes; the checks below cover the cases the toolbox is used for.

The threshold increase is the threshold relative to testing one bin at the
per-cell Pfa. For a Swerling 1 target it is close to the SNR cost. With 54
tests the increase is 1.10 dB, against an SNR cost of 1.11 dB at Pd 90 % and
1.15 dB at Pd 50 %. A Swerling 0 target at Pd 90 % pays less, 0.92 dB
(computed with `required_snr_db`, one look).

Zero padding trades straddle loss for threshold. One FFT axis of 256
samples, Pfa 10⁻⁶ per cell, one look, Swerling 1 target at Pd 90 %
(computed with `false_alarm_budget`, `required_snr_db` and
`straddle_loss_db`):

| Padding | Hann: tests per cell | Hann: SNR cost | Hann: mean straddle | Hann: sum | Rectangular: tests per cell | Rectangular: sum |
|---|---:|---:|---:|---:|---:|---:|
| 1× | 0.98 | −0.01 dB | 0.47 dB | 0.47 dB | 1.00 | 1.26 dB |
| 2× | 1.53 | +0.13 dB | 0.12 dB | 0.25 dB | 1.98 | 0.51 dB |
| 4× | 1.80 | +0.18 dB | 0.03 dB | 0.21 dB | 3.16 | 0.42 dB |
| 8× | 1.89 | +0.20 dB | 0.01 dB | 0.20 dB | 3.75 | 0.42 dB |
| 16× | 1.91 | +0.20 dB | 0.00 dB | 0.20 dB | 3.96 | 0.42 dB |

- **Up to fourfold** padding pays: for Hann, twofold saves 0.22 dB per axis
  and fourfold 0.26 dB.
- **Beyond fourfold** nothing is gained.
- **The limit** for fine sampling is Rice's level-crossing rate of the
  envelope, `sqrt(λ T / π)` tests per cell for one look at threshold `T`,
  where `λ` is (2π)² times the variance of the sample index (in window
  lengths) weighted by the squared window: 1.91 for Hann and 3.99 for
  rectangular at 10⁻⁶.
- **Rectangular windows** gain more from padding, because their straddle
  loss without padding is larger (1.26 dB). Their floor is higher, because
  their larger `λ` gives more tests per cell (3.29 against 0.79 for Hann).
- **Without padding** the count is within 2 % of one test per bin at 10⁻⁶.
  At higher Pfa, neighbouring Hann bins cross the threshold together more
  often, and the count falls: 0.94 at 10⁻⁴ and 0.90 at 10⁻³ per cell.
- **A window with a single nonzero sample**, such as a two-point Hann window
  (two chirps per transmitter), gives every bin of the axis the same power.
  A detector with peak grouping then reports one detection along the axis,
  which is 1/length per cell; windows that approach this case tend to the
  same count.

Beams work the same way. In the printout above, 64 beams formed from eight
channels act as 54 independent tests, not 8. Correlated beams exceed a high
threshold almost independently (`studies/2026-09-02_lannik-psi/NOTES.md`,
"False alarms over the RX beams"). Holding the Pfa per cell instead of per
beam shortens the study's Pd 50 % range by 6.4 % (1.15 dB), as its range
breakdown in `lannik_psi.py` prints.

The tests in `tests/test_false_alarms.py` check these computations:

- **Range and Doppler:** against simulated FFTs, padded and unpadded, with
  one and four non-coherent looks.
- **Beams:** against a simulated detector on correlated beams, with one and
  four looks.
- **The fine-sampling limit:** against the Rice formula.
- **Range and Doppler together:** the product of the 1-D factors lies up to
  6 % above a direct count of peaks over all eight neighbours (Hann, fourfold
  on both axes: 3.13 against 3.02 tests). That shifts the threshold by under
  0.02 dB, with twofold to eightfold padding of Hann or rectangular windows.
- **Range and angle together:** against a simulated search over range of the
  best-beam power.

The checks cover Pfa from 10⁻⁶ to 10⁻² per test, Hann and rectangular
windows (and one window close to a single nonzero sample), up to sixteenfold
padding, one or four looks, and uniform-array beam grids. They support those
operating cases; they are not error bounds for arbitrary windows, look
counts or Pfa values.

Limitations:

- **Fixed threshold against known noise.** CFAR enters as the separate,
  fixed allowance in the CFAR row; it does not change with the per-test Pfa.
- **Peak grouping is assumed.** A detector that reports every bin above
  threshold has `P` times as many false alarms per cell at `P`-fold padding.
- **Pd is evaluated in the strongest beam.** With a beam set, the detector
  reports a detection in any beam, but Pd is computed in the beam with the
  strongest expected signal. Where several beams receive comparable signal,
  as between beams, that is conservative. With an equal response in two
  orthogonal beams and a shared Swerling 1 fluctuation, Pd 0.50 in the
  strongest beam is 0.57 in either, about 1 dB of SNR at Pd 50 % (computed in
  `tests/test_false_alarms.py`). Neighbouring beams of a denser grid share
  more of their noise, so their gain is smaller.
- **Small Pfa only.** At high Pfa the product of the axis factors stops being
  a false-detection rate and has a largest value (about 0.1 per cell for a
  four-point Hann window on both axes with four looks); larger values raise
  an error. The threshold is solved on the branch where false detections
  fall as the threshold rises.
- **Collapsing cells** count as looks in the noise statistics, like every
  non-coherently summed cell.
- **Transmit beams** formed one after another are separate dwells, not tests
  within one cell; the engine counts only receive beam sets.

## Checklist for a study

For each study or one-off calculation, state:

1. Front-end: datasheet typical, or a derated case (temperature, part spread,
   RX gain step, noise mode).
2. Feed: the datasheet's reference plane and the loss from there to the
   antenna port.
3. Antenna: whether the pattern is a directivity or a realized gain and, for a
   directivity, the antenna loss.
4. Radome: none, clean or contaminated.
5. Environment: `FreeSpace` only for idealised comparisons; otherwise
   `Atmosphere` for stated conditions, plus rain if relevant.
6. Coherence: the per-chirp frequency error for the MMIC programming used.
7. Processing: windows, straddle (and padding), CFAR, beamforming, MIMO.
8. False alarms: the Pfa per range–Doppler cell, what it means per frame, and
   the beam set, if any.
9. Anything in `other_loss_db`, itemised in the text.

## References

1. Infineon, CTRX8188F Target Datasheet, rev. 0.20, 2025-06-17 (restricted,
   NDA): Section 5 and Figure 5 (RF reference plane), Table 22 (transmitter),
   Table 24 (TX RF module), Table 30 (receiver).
2. HUBER+SUHNER, SENCITY FARAD-IV Radar Antenna 1377.99.0744, preliminary data
   sheet, document PIM-P62799, 2026-01-20.
3. HUBER+SUHNER, SENCITY THIS-II Radar Antenna 1377.99.0701, preliminary data
   sheet, document PIM-P50871, 2025-12-12.
4. ITU-R P.676-13 (08/2022), *Attenuation by atmospheric gases and related
   effects*, Annex 1, equations (1)–(9) and Tables 1–2,
   <https://www.itu.int/rec/R-REC-P.676>. Implemented in `radarperf.itu`; the
   tests reproduce the ITU's validation examples (CG-3M3J-13-ValEx, rev. 8.3.0).
5. Rohde & Schwarz, *Fundamentals of radome and bumper measurements using the
   R&S QAR*, white paper PD 3608.0833.52, version 01.00, March 2020.
6. S. Heuel, T. Köppel and S. Ahmed, "Evaluating 77 to 79 GHz automotive radar
   radome emblems", *Microwave Journal*, January 2018.
7. J. Ruze, "Antenna tolerance theory — a review", *Proc. IEEE*, vol. 54,
   no. 4, 1966.
8. CARKIT validation study, `studies/2026-09-11_carkit-validation/NOTES.md`
   (branch `carkit-model-validation`): summary and "The per-chirp frequency
   error".
9. ITU-R P.838-3 (03/2005), *Specific attenuation model for rain for use in
   prediction methods*, equations (1)–(5), Tables 1–5,
   <https://www.itu.int/rec/R-REC-P.838>.
10. F. J. Harris, "On the use of windows for harmonic analysis with the
    discrete Fourier transform", *Proc. IEEE*, vol. 66, no. 1, 1978, Table 1.
11. Infineon, CTRX8188F User Manual, rev. 0.20, 2025-11-10 (restricted, NDA):
    Table 46 (`Configure_RX()` request), Table 120 (ramp segment
    configuration CONFIG0).
12. ITU-R P.835-7 (08/2024), *Reference atmospheres*, Annex 1, equations
    (1a), (2a), (3a) and (6), <https://www.itu.int/rec/R-REC-P.835>.
    Implemented in `radarperf.itu.reference_atmosphere`; the tests compare it
    with the U.S. Standard Atmosphere 1976.
13. Infineon, email reply to our questions on the CTRX8188F noise modes and the
    conditions of [1] Table 30, 2026-10-02 (not public).
