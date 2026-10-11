# Losses and other terms in the range equation

The toolbox computes SNR from datasheet front-end figures, an antenna pattern,
a processing model, a target and an environment. This page lists every term
between those inputs and the detector: where it lives in the toolbox, its
default, and what sets its value. Many terms default to zero. A zero is a
modelling choice, so a study or one-off calculation should state it as one.
Printing a `LinkBudget` lists each named term with its value, zeros included.

Values that belong to a particular part, such as a front-end's datasheet
figures or an antenna's efficiency, are on that part's
[hardware page](#hardware-pages). Every number on this page is taken from a
cited source, derived here, or computed with the toolbox (and says so). Where
no source is available the page says that instead of giving a typical value.
References are listed at the end.

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
    tx_power_derating_db=1.0,  # CTRX8188F over temperature (hardware/ctrx8188f.md)
    tx_antenna_loss_db=0.92,  # SENCITY FARAD-IV bound (hardware/sencity.md)
    rx_antenna_loss_db=0.92,
    chirp_frequency_error_rms_hz=3.5e3,  # CTRX8188F, well-timed ramps (hardware/ctrx8188f.md)
)
radar = Radar(..., losses=losses)
budget = radar.link_budget(target, geometry, Atmosphere())  # P.676-13 standard [1]
print(budget)
```

## Hardware pages

| Part | Presets | Page |
|---|---|---|
| Infineon CTRX8188F | `frontend.ctrx8188f()`, `phase_noise.ctrx8188f_phase_noise()`, `phase_noise.ctrx8188f_chirp_settling()` | [hardware/ctrx8188f.md](hardware/ctrx8188f.md) |
| TI AWR1243, AWR2243, AWR2E44P | `frontend.awr1243()`, `awr2243()`, `awr2e44p()` | none yet; the presets' docstrings give the public datasheets' headline TX power and noise figure |
| HUBER+SUHNER SENCITY FARAD-IV, THIS-II | `antenna.sencity_farad_iv()`, `antenna.sencity_this_ii()` | [hardware/sencity.md](hardware/sencity.md) |

A hardware page collects a part's datasheet figures with their table numbers,
how to read them, and what measurements have shown. Its preset's docstring
stays short and points to it. A part gets a page once there is more to say
than its preset's docstring holds.

## Catalogue

### Front-end

| Term | Where | Default | Values | Source |
|---|---|---|---|---|
| TX power | `Frontend.tx_power_w` | the preset's datasheet typical | the datasheet's output power per channel at its RF reference plane | the part's datasheet |
| TX power derating | `SystemLosses.tx_power_derating_db` | 0 | the spread from typical to minimum, the variation over temperature and over a ramp, and any power reduction setting | the part's datasheet |
| Noise figure | `Frontend.noise_figure_db` | the preset's datasheet typical | the datasheet's noise figure at the RX gain the firmware sets, at an IF where the targets of interest lie | the part's datasheet |
| NF derating | `SystemLosses.noise_figure_derating_db` | 0 | the spread from typical to maximum, a lower RX gain step, a rise towards low IF | the part's datasheet; measurements |
| Noise bandwidth | `FmcwWaveform.noise_bandwidth_hz` | the sample rate (ideal anti-alias filter) | none | |
| RX high-pass filter | not modelled | | cuts a return at low IF but not the noise above the filter's corner | the part's datasheet |
| ADC quantisation, IF gain shape | not modelled | | none | |

A datasheet quotes its RF figures at a reference plane; check where it lies.
Anything between that plane and the antenna is a feed loss (below).

A typical value describes a nominal part, usually at nominal supply and room
temperature, and the minimum and maximum hold over the operating range; check
the datasheet's conditions. Infineon has confirmed this reading for the
CTRX8188F ([hardware/ctrx8188f.md](hardware/ctrx8188f.md#typical-minimum-and-maximum)).
A typical value is therefore a starting point for a unit at room temperature,
not a bound; the derating terms cover temperature and part spread.

The noise figure depends on the receiver's gain setting and on IF. Use the
figure for the gain the firmware actually sets; the CTRX8188F's datasheet calls
its two highest gain steps noise modes, and the chip defaults to the noisier
one ([hardware/ctrx8188f.md](hardware/ctrx8188f.md#the-noise-modes-are-rx-gain-steps)). Use it at the IF where the targets of interest lie, and take a measured
noise floor at the same IF.

### Feed and antenna

| Term | Where | Default | Values | Source |
|---|---|---|---|---|
| TX and RX feed | `SystemLosses.tx_feed_loss_db`, `rx_feed_loss_db` | 0 | none yet; from the front-end's reference plane to the antenna port | |
| Antenna efficiency and mismatch | `SystemLosses.tx_antenna_loss_db`, `rx_antenna_loss_db` | 0 | directivity to realized gain: radiation efficiency and port mismatch, zero when the pattern already is a realized gain. Per antenna on its hardware page | [2]; the antenna's data sheet |
| Aperture taper | antenna model | | `aperture_efficiency` and array weights already reduce the directivity; do not count it again | |
| Channel amplitude and phase errors | not a field | 0 | random phase errors of rms σ reduce coherent gain by exp(−σ²), i.e. 10 log10(e) σ² dB: 0.13 dB at 10°, 0.53 dB at 20°. The front-end's datasheet bounds the channels' drift | [3]; the part's datasheet |
| Angular straddle | `StandardProcessing.beamforming_loss_db`, or a multi-beam antenna model | 0 | | do not use both |

Channel errors apply to coherent TX or RX combining; put them in
`beamforming_loss_db` or `other_loss_db`. The SENCITY presets and the
analytical aperture and array models are directivities, so they need the
antenna loss.

IEEE Std 145 [2] defines radiation efficiency as the radiated power over the
power the antenna accepts, which leaves mismatch out. Realized gain is then the
directivity times the radiation efficiency times 1 − |Γ|², with Γ the port's
reflection coefficient. A data sheet that does not define its efficiency may
mean total efficiency, mismatch included
([hardware/sencity.md: “Efficiency and mismatch”](hardware/sencity.md#efficiency-and-mismatch)).

### Radome and installation

| Term | Where | Default | Values | Source |
|---|---|---|---|---|
| Radome | `SystemLosses.radome_one_way_loss_db`, applied on both passes | 0 | no typical value; published single examples: a radome measured at 1.2–1.6 dB two-way at three points, and an emblem at 0.64 dB one-way | [4] Fig. 1; [5] |
| Water film, ice, snow, dirt | the same field | 0 | none | |
| Pattern change from radome, bumper and vehicle | antenna model | | not modelled | |

A single-layer radome's loss is smallest when its wall is an integer number of
half wavelengths thick in the material; paint and coatings shift that optimum
([4] Section 4.1). Measure the installed configuration.

### Propagation

| Term | Where | Default | Values | Source |
|---|---|---|---|---|
| Gaseous absorption | `Atmosphere(specific_attenuation_db_per_km)`, `Atmosphere.itu_p676(...)` or `Atmosphere.itu_reference(height_m)` | the engine's default environment is `FreeSpace()`, i.e. 0; `Atmosphere()` uses 0.35 dB/km | see the table below | [1] |
| Rain attenuation | `Rain(rain_rate_mm_per_hr, polarization_tilt_deg)` | off | `k R^α` with `k`, `α` from ITU-R P.838-3 at the waveform's centre frequency; see the table below | [6] |
| Rain clutter | `Rain` | off | Marshall–Palmer Z–R relation, Rayleigh reflectivity and Probert-Jones beam filling; not validated at 77 GHz, where raindrops are Mie scatterers | see `radarperf.environment` |
| Fog, snow, dust | not modelled | | | |
| Multipath (ground reflection) | not modelled | 0 | derived: the two-way propagation factor is at most (1 + \|Γ\|)⁴, +12 dB for \|Γ\| = 1, with nulls in between | |

`Atmosphere` is one constant one-way specific attenuation γ; the two-way loss
is `2 γ R`, independent of frequency and altitude. Choose γ for the conditions
of the study, or compute it with `Atmosphere.itu_p676(frequency_hz,
temperature_c=..., pressure_hpa=..., water_vapour_density_g_m3=...)`, which
implements the line-by-line method of ITU-R P.676-13 Annex 1 [1] (in
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
method in the ITU-R reference atmosphere of P.835-7 Annex 1 [7]: temperature
and total pressure of the U.S. Standard Atmosphere 1976, and water vapour
7.5 g/m³ at sea level falling with a 2 km scale height. It assumes a
horizontal path at that height. At 76.5 GHz:

| Height | Temperature, total pressure, water vapour density | One-way [dB/km] |
|---:|---|---:|
| 0 m | 15.0 °C, 1013.25 hPa, 7.5 g/m³ | 0.35 |
| 1000 m | 8.5 °C, 898.8 hPa, 4.55 g/m³ | 0.22 |
| 2000 m | 2.0 °C, 795.0 hPa, 2.76 g/m³ | 0.15 |
| 5000 m | −17.5 °C, 540.5 hPa, 0.62 g/m³ | 0.056 |

Rain attenuation at 77 GHz from ITU-R P.838-3 [6] (its Table 5 lists
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

| Term | Where | Default | Values | Source |
|---|---|---|---|---|
| Per-chirp frequency error | `SystemLosses.chirp_frequency_error_rms_hz` | 0 | from a CW phase-noise spectrum with `phase_noise.chirp_frequency_error_rms_hz`, or from the chirp timing with a `phase_noise.ChirpSettling` fit; per part on its hardware page | [phase_noise.md](phase_noise.md) |
| Phase noise within a chirp | not a field | | the residual that the range window keeps out of the per-chirp error lowers the range peak instead. The window sets the split, not the total: with the Doppler part, the peak keeps exp(−σ²_tot), from `SingleReturnPhaseNoise.residual_variance_rad2` | [phase_noise.md: “The total loss of the peak”](phase_noise.md#the-total-loss-of-the-peak) |
| Phase-noise skirts of strong returns | `phase_noise_fft`, a separate prediction ([phase_noise_prediction.md](phase_noise_prediction.md)) | | an SINR term near strong clutter, not in the link budget | |
| Chirp nonlinearity | not modelled | | | |
| Range migration during the CPI | not modelled | | negligible while \|v\| T_CPI is small against the range resolution | |
| Doppler spread of the target | not modelled | | | |

The per-chirp frequency error `δf` is the LO's frequency error averaged over
each chirp's sampled ramp with the range window's weights, quoted as its rms
over chirps. It gives a beat phase error of rms `σ = 2π δf · 2R/c`, the same
`δf` for every return. For Gaussian errors the Doppler peak keeps `exp(−σ²)`
of its power and the rest spreads into a pedestal, so the loss is
`10 log10(e) σ²` dB, growing as `R²`. It is a loss of the Doppler integration
over chirps, the same in every channel, not a loss in combining channels.
[phase_noise.md](phase_noise.md) derives these steps and tabulates the loss.
`δf` depends on the MMIC, the sampled ramp and window, and the time the
synthesizer gets between ramps; the hardware pages give computed and measured
values.

### Processing

These were explicit before `SystemLosses`; they are listed for completeness.

| Term | Where | Default | Basis |
|---|---|---|---|
| Range and Doppler windows | `range_window`, `doppler_window` (SciPy window names); override with `range_window_loss_db`, `doppler_window_loss_db` | Hann: 1.76 dB each | computed (`window_loss_db`): 10 log10 of the periodic window's equivalent noise bandwidth in bins; matches [8] Table 1 |
| Range and Doppler straddle | computed from the window and `range_fft_size`, `doppler_fft_size` (zero-padding); override with `range_straddle_loss_db`, `doppler_straddle_loss_db` | Hann, no padding: 0.47 dB each | computed (`straddle_loss_db`): the peak-bin loss averaged in dB over a target position uniform between FFT bins. Hann: 0.47 dB without padding, 0.12 dB with twofold and 0.03 dB with fourfold padding; the worst case (midway between bins, `statistic="max"`) is 1.42 dB without padding, as in [8] Table 1. Padding also adds tests per cell; see the next row |
| Multiple testing in range and Doppler | computed from the same windows and FFT sizes; acts on the threshold, not the SNR (`LinkBudget.false_alarms`) | Hann, no padding: 0.98 tests per cell each, −0.01 dB | computed (`radarperf.false_alarms`); see [false_alarms.md](false_alarms.md). Hann: +0.13 dB of threshold with twofold and +0.18 dB with fourfold padding per axis |
| CFAR | `cfar_loss_db` | 1.0 dB | an allowance for a CFAR not yet chosen, held fixed when other assumptions change. For scale: cell-averaging CFAR with 32 reference cells costs 0.97 dB (16 cells: 2.0 dB; 64 cells: 0.48 dB) for a Swerling 1 target, square-law detection, Pfa 10⁻⁶ per test, from Pfa = (1 + T/N)⁻ᴺ and Pd = (1 + T/(N(1 + SNR)))⁻ᴺ against the fixed-threshold case |
| Beamforming or angle straddle | `beamforming_loss_db` | 0 | applied only with coherent angular combination |
| Multiple testing over beams | computed when the receive antenna is a beam set (`MultiBeamUniformArrayAntenna`); acts on the threshold | 1 test (no beam set) | computed (`radarperf.false_alarms`); see [false_alarms.md](false_alarms.md) |
| MIMO | `mimo_loss_db` | 0 | e.g. DDMA or BPM orthogonality |
| Collapsing | computed | | empty DDMA subbands, handled by the detector |
| Other | `other_loss_db` | 0 | catch-all; say what it holds |

### Detection, target and scene

| Term | Where | Default | Notes |
|---|---|---|---|
| Pfa per range–Doppler cell | `Radar.default_pfa` and the `pfa` arguments of `Radar` and `radarperf.sweeps` | 10⁻⁶ | false detections per unpadded range–Doppler cell, over all beams; the detector tests each bin at the lower per-test Pfa that holds it ([false_alarms.md](false_alarms.md)). `Radar(pfa_reference="test")` applies the value per test, the convention before 2026-10-01. The functions in `radarperf.detection` take the Pfa per test |
| Fluctuation | `Target.swerling` | 1 for the presets | |
| RCS | target model | illustrative presets | |
| Antenna noise temperature | `Radar.antenna_noise_temperature_k` | 290 K (the noise-figure reference temperature) | |

### Not covered

Interference from other radars, receiver compression and TX-to-RX leakage at
short range, and clutter other than rain (ground, guardrails).

## Checklist for a study

For each study or one-off calculation, state:

1. Front-end: datasheet typical, or a derated case (temperature, part spread,
   RX gain step).
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
   the beam set, if any ([false_alarms.md](false_alarms.md)).
9. Anything in `other_loss_db`, itemised in the text.

## References

1. ITU-R P.676-13 (08/2022), *Attenuation by atmospheric gases and related
   effects*, Annex 1, equations (1)–(9) and Tables 1–2,
   <https://www.itu.int/rec/R-REC-P.676>. Implemented in `radarperf.itu`; the
   tests reproduce the ITU's validation examples (CG-3M3J-13-ValEx, rev. 8.3.0).
2. IEEE Std 145-2013, *IEEE Standard for Definitions of Terms for Antennas*:
   radiation efficiency, realized gain.
3. J. Ruze, "Antenna tolerance theory — a review", *Proc. IEEE*, vol. 54,
   no. 4, 1966.
4. Rohde & Schwarz, *Fundamentals of radome and bumper measurements using the
   R&S QAR*, white paper PD 3608.0833.52, version 01.00, March 2020.
5. S. Heuel, T. Köppel and S. Ahmed, "Evaluating 77 to 79 GHz automotive radar
   radome emblems", *Microwave Journal*, January 2018.
6. ITU-R P.838-3 (03/2005), *Specific attenuation model for rain for use in
   prediction methods*, equations (1)–(5), Tables 1–5,
   <https://www.itu.int/rec/R-REC-P.838>.
7. ITU-R P.835-7 (08/2024), *Reference atmospheres*, Annex 1, equations
   (1a), (2a), (3a) and (6), <https://www.itu.int/rec/R-REC-P.835>.
   Implemented in `radarperf.itu.reference_atmosphere`; the tests compare it
   with the U.S. Standard Atmosphere 1976.
8. F. J. Harris, "On the use of windows for harmonic analysis with the
   discrete Fourier transform", *Proc. IEEE*, vol. 66, no. 1, 1978, Table 1.
