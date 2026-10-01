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
| Noise figure | `Frontend.noise_figure_db` | datasheet typical | CTRX8188F, 10 MHz IF: low-noise mode 10.2 dB typical, 13.2 dB maximum (the preset); ultra-low-noise mode 9.7 dB typical, 12.7 dB maximum. We read the modes as RX gain 0 dB and +3 dB (below) | [1] Table 30 |
| NF derating | `SystemLosses.noise_figure_derating_db` | 0 | CTRX8188F: up to 3 dB from typical to maximum; for a negative RX gain step, up to the step's magnitude; 0.3 dB (low-noise) or 0.2 dB (ultra-low-noise) higher at 1 MHz IF than at 10 MHz | [1] Table 30 |
| Noise bandwidth | `FmcwWaveform.noise_bandwidth_hz` | the sample rate (ideal anti-alias filter) | none | |
| ADC quantisation, IF gain shape | not modelled | | none | |

The CTRX8188F datasheet quotes RF parameters at the waveguide port on the far
side of a 1.2 mm reference PCB, so the package-to-PCB transition is inside its
figures for the reference footprint and stack-up ([1] Section 5, Figure 5). A
different PCB, or anything between that plane and the antenna, is a feed loss.

The datasheet gives the noise figure for a "low noise operation mode" and an
"ultra low noise operation mode" ([1] Table 30). We read the two modes as the
RX gain steps 0 dB and +3 dB, not as a separate setting:

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

Infineon has not confirmed this reading yet. If it holds, a receiver at +3 dB
gain has the ultra-low-noise figures, 0.5 dB below the preset at 10 MHz IF:
use `frontend.ctrx8188f(noise_figure_db=9.7)`.

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
| Range and Doppler straddle | computed from the window and `range_fft_size`, `doppler_fft_size` (zero-padding); override with `range_straddle_loss_db`, `doppler_straddle_loss_db` | Hann, no padding: 0.47 dB each | computed (`straddle_loss_db`): the peak-bin loss averaged in dB over a target position uniform between FFT bins. Hann: 0.47 dB without padding, 0.12 dB with twofold and 0.03 dB with fourfold padding; the worst case (midway between bins, `statistic="max"`) is 1.42 dB without padding, as in [10] Table 1 |
| CFAR | `cfar_loss_db` | 1.0 dB | derived: cell-averaging CFAR with 32 reference cells costs 0.97 dB (16 cells: 2.0 dB; 64 cells: 0.48 dB) for a Swerling 1 target, square-law detection, Pfa 10⁻⁶, from Pfa = (1 + T/N)⁻ᴺ and Pd = (1 + T/(N(1 + SNR)))⁻ᴺ against the fixed-threshold case |
| Beamforming or angle straddle | `beamforming_loss_db` | 0 | applied only with coherent angular combination |
| MIMO | `mimo_loss_db` | 0 | e.g. DDMA or BPM orthogonality |
| Collapsing | computed | | empty DDMA subbands, handled by the detector |
| Other | `other_loss_db` | 0 | catch-all; say what it holds |

### Detection, target and scene

| Term | Where | Default | Notes |
|---|---|---|---|
| Pfa per test | `Radar.default_pfa` | 10⁻⁶ | testing several beams per range–Doppler cell raises the false-alarm rate; lower the per-test Pfa to compensate |
| Fluctuation | `Target.swerling` | 1 for the presets | |
| RCS | target model | illustrative presets | |
| Antenna noise temperature | `Radar.antenna_noise_temperature_k` | 290 K (the noise-figure reference temperature) | |

### Not covered

Interference from other radars, receiver compression and TX-to-RX leakage at
short range, and clutter other than rain (ground, guardrails).

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
8. Anything in `other_loss_db`, itemised in the text.

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
