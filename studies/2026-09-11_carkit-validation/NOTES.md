# CARKIT walk: validating the range model

<!-- Figures linked from these notes are tracked through the .gitignore in this
folder, since they cannot be regenerated without the raw capture. When adding
or removing a figure link, update that list. -->

Status 2026-09-30. Results were posted in the Slack thread on 2026-09-29; the
posted text and figures are in [deliverables/2026-09-29](deliverables/2026-09-29/).
Earlier drafts, reviews and superseded numbers are in the git history of this
branch.

## Summary

Viktor Kärnstrand measured a hand-held corner reflector carried away from and
back towards a CARKIT radar (CTRX8188F + FARAD-IV, TX1 only, eight RX) and
compared it with our range model. His report found the measurement about 4 dB
better than the model. Reprocessing his raw ADC data:

- **The measured per-RX SNR is 33.9 dB at 100 m and 10 dBsm, against 32.7 dB
  from the model (+1.2 dB).** With the far-quarter noise reference instead of
  the local one it is 35.1 dB (+2.4 dB). The report's 4 dB is mostly the
  reflector's RCS (1.3 dB) and the noise reference (1.2 dB). The remaining
  difference is within the uncertainty of reflector RCS, geometry and datasheet
  values; no model correction follows.
- **On the inbound leg below 27 m, where ground multipath should matter least,
  the measurement is 32.8 ± 0.6 dB, essentially on the model.**
- **A strong return raises a Doppler pedestal at its own range that scales
  with its power times range squared.** This corresponds to a chirp-to-chirp
  phase error proportional to delay, equivalent to about 17 kHz rms frequency
  error. It agrees with the 2026-09-22 phase-noise-outdoor study on the
  `phase-noise` branch and may limit long-range coherence.
- **The background at the walk's beat frequencies is 1–1.5 dB above the far
  quarter, stable in time and uncorrelated between RX channels.** It behaves
  like receiver noise or IF gain shaping, not like phase noise from a common
  source. Which of the two decides between +1.2 and +2.4 dB.

## Inputs

| Input | Notes |
|---|---|
| [CARKIT report.pdf](inputs/CARKIT%20report.pdf) | Current report, 17 pages, 2026-09-22 |
| [empirical-1km-snr-budget.pdf](inputs/empirical-1km-snr-budget.pdf) | Earlier six-page report, superseded |
| [slack.txt](inputs/slack/slack.txt) and images | Thread up to 2026-09-28: processing details, reflector comparison |
| Raw capture | `~/Data/tmp/walk-hallesaker-tx1-1-psi`, not in the repo: 200 CPIs of real int16 ADC data [1024 chirps, 512 samples, 8 RX], offline PSI-style conversion with SHA-256 per CPI |

The capture's `provenance/configuration.json` shows `current_mode = 1`,
waveform 0 (the walk waveform), with RX `high_pass = 0` and `gain = 0`.
Viktor's analysis code and the chamber raw/calibration data were not supplied.

## Configuration and model

| Quantity | Value |
|---|---|
| Waveform | 50 MS/s real sampling; 512 samples in a 10.24 µs payload; 1024 chirps at 15.96 µs PRI |
| Sweep | 100.78 MHz sampled bandwidth, 9.84 MHz/µs; centre 76.374 GHz (start + slope × pre-payload + half the sampled bandwidth) |
| Resolution | 1.487 m range bin; 0.120 m/s Doppler bin; unambiguous range about 381 m |
| Integration | 10.49 ms sampled; 16.34 ms CPI |
| Processing | Periodic Blackman on both axes (2.37 dB ENBW loss each), fourfold padding (at most 0.07 dB scalloping), as in Viktor's processing |
| Model TX / NF | CTRX8188F datasheet: 14.5 dBm, NF 10.2 dB (low-noise mode at 10 MHz; 10.5 dB at 1 MHz; ultra-low-noise mode 0.5 dB lower) |
| Model antenna | FARAD-IV digitized boresight: 15.05 / 14.98 dBi TX / RX; the datasheet describes these as directivity |
| Model target | Nonfluctuating 10 dBsm at boresight; no straddle or CFAR loss |

The model is [walk_model.py](walk_model.py). Viktor's hand calculation gives
32.63 dB, the same as the model. The model has no terms for chip-to-antenna
transitions, antenna ohmic loss, radome or temperature derating; these would
make it more pessimistic. A review of such missing terms is pending separately.

## Method

**Target cell.** For each CPI, one common range–Doppler cell is found from the
mean of per-RX powers normalized by far-quarter noise; every RX value is read
at that cell. RX channels are never combined coherently. The analyzed legs are
outbound CPIs 26–70 (15–50 m) and inbound CPIs 89–127 (17–51 m).

**Background.** For each target cell, the same RX's power within ±1 range bin
and ±1 m/s of the target's range and velocity, pooled over control CPIs where
the reflector is elsewhere (more than 8 m away while tracked, CPIs 26–160, or
any CPI after 160). The estimator is the median over about 19 000–21 000
powers divided by ln 2. The post-walk CPIs contain passing traffic, which the
median rejects; a trimmed mean or plain mean changes the result by −0.01 and
−0.10 dB.

**Headline convention.** Average the RX SNRs linearly within each CPI, scale
each CPI by R⁻⁴ to 100 m and by −1.27 dB from the walking reflector to 10 dBsm,
then average in dB over CPIs. This is a fixed-slope fit like the report's. The
target fluctuates, so other conventions give different numbers for the
inbound leg:

| Convention | Inbound, 39 CPIs |
|---|---:|
| Linear over RX, dB over CPIs (headline) | 33.86 dB |
| Linear over RX, median over CPIs | 33.28 dB |
| Linear over RX and CPIs | 34.49 dB |
| dB over RX and CPIs | 32.53 dB |

Per-CPI standard deviation is 2.2 dB. Per-RX dB means range from 30.8 to 34.2 dB.

## Results

### Reconciling the report

| Step | Change | Value |
|---|---:|---:|
| Report, 33 selected CPIs | | 36.57 dB |
| Reproduction with the report's selection rule, 37 CPIs | +0.37 | 36.94 dB |
| RX magnitude sum → linear mean of RX power | −0.34 | 36.60 dB |
| Far-quarter noise → target-free local noise | −1.23 | 35.37 dB |
| Reflector RCS 10 → 11.27 dBsm | −1.27 | 34.10 dB |
| All 39 inbound CPIs | −0.23 | **33.86 dB** |
| Model | | 32.67 dB |

The report's selection keeps CPIs within 6 dB of the local R⁻⁴-corrected
maximum within ±5 m, over 15–51 m; all selected CPIs are inbound. The exact
33 CPIs could not be reproduced without Viktor's code.

### Noise reference

The background at |v| ≥ 10 m/s relative to the far quarter
([background.png](generated/background/background.png)):

| Range | 15 m | 30 m | 50 m | 100 m | 200 m | 300 m |
|---|---:|---:|---:|---:|---:|---:|
| Beat frequency | 1.0 MHz | 2.0 MHz | 3.3 MHz | 6.6 MHz | 13 MHz | 20 MHz |
| Excess | 1.5 dB | 1.2 dB | 0.9 dB | 0.5 dB | 0.2 dB | 0.0 dB |

Below about 10 m it falls steeply, the high-pass filter. The excess above
the HPF corner is the same in every CPI and differs by up to 0.6 dB between
RX channels (RX1, 6 and 7 highest). Over the walk ranges it is uncorrelated
between channels: mean pairwise |coherence|² is 0.0005, against 0.0004 in the
far quarter and 0.05 expected if the excess were common to all channels.
Phase noise on leakage or nearby returns would be common, because the channels
share the LO, so that explanation is ruled out.

Two explanations remain. If it is IF gain shape, signal and noise are shaped
alike and the local reference is right (+1.2 dB). If it is receiver noise that
rises at low IF, the far quarter is the better thermal reference (+2.4 dB).
The datasheet NF changes only 0.3 dB between 1 and 10 MHz, which favours gain
shape. A TX-off capture would decide: gain shape remains with TX off.

### Range structure and geometry

| Inbound band | CPIs | Mean | Median | Std |
|---|---:|---:|---:|---:|
| 15–27 m | 14 | 32.8 dB | 32.9 dB | 0.6 dB |
| 27–38 m | 11 | 33.7 dB | 33.1 dB | 2.1 dB |
| 38–52 m | 14 | 35.0 dB | 34.6 dB | 2.7 dB |

The spread beyond 30 m has the signature of ground multipath: most points
above the short-range level, with occasional deep dips. Random-phase two-ray
interference averages to zero in dB, though not in linear units. So
multipath explains the spread but not the 2.3 dB rise of the dB mean; that
needs something else, for example how the reflector was held. With a 30°
10-dB elevation beamwidth, a modest height difference between radar and
reflector costs little gain at 17 m. The reflector was probably carried at
about 1 m; the radar height is unknown. Free fits of mean-RX target power give
−35 dB/decade inbound and −30 dB/decade outbound, against −40.

The outbound return is about 12 dB weaker after range correction and much more
variable, probably because of how the reflector was carried; it is excluded
from the reference.

### RX differences

The strongest-to-weakest RX power span at the target cell has a median of
9 dB outbound and 11 dB inbound, up to 28 dB. In CPI 100, RX8 is 28 dB below
the strongest channel at the common cell but 16 dB below over a surrounding
patch ([rx_null_example.png](generated/dynamics/rx_null_example.png)). These are
spatial and temporal nulls from a composite reflector-plus-person return, not
fixed calibration differences. They also explain why Viktor's coherent RX sum
(41.6 dB, about 39 dB after the same noise and RCS corrections) gains only
about 5 dB over the per-RX level rather than 9 dB. This is a rough estimate,
not computed here.

### CPI length

Reprocessing each CPI as 128–1024-chirp segments
([cpi_length.png](generated/dynamics/cpi_length.png)):

| Leg | Deficit against ideal at 1024 chirps | p10–p90 | Single-tone fraction | Power outside ±0.5 m/s |
|---|---:|---:|---:|---:|
| Inbound | 0.20 dB | −0.13 to 0.49 dB | 0.93 | 0.9 % |
| Outbound | 1.41 dB | 0.26 to 4.5 dB | 0.53 | 11.7 % |

The inbound return integrates nearly ideally over the full CPI. The outbound
return is spread in Doppler by the carrier's motion. A synthetic tone through
the same processing gave 3.06 / 6.01 / 9.09 dB against the ideal 3.01 / 6.02 /
9.03 dB (a one-off check, not part of the scripts).

### Doppler pedestal

A strong return raises the remote-Doppler background at its own range; ±12 m
away there is no change. At |v| ≥ 20 m/s the median excess over same-range
controls is 1.2 dB inbound and 0.05 dB outbound. Fitting
`excess = 10 log10(1 + k S^a (R/30 m)^b)` to both legs
([walk_pedestal.py](walk_pedestal.py),
[pedestal_scaling.png](generated/pedestal/pedestal_scaling.png)):

| Doppler band | a (p5–p95) | b (p5–p95) | RMS: free / a=1, b=2 / a=1, b=0 | Equivalent frequency error |
|---|---|---|---|---:|
| ≥10 m/s (5.1–31.3 kHz) | 1.02 (0.96–1.09) | 2.00 (1.78–2.20) | 0.10 / 0.10 / 0.35 dB | 16.9 kHz rms |
| ≥20 m/s (10.2–31.3 kHz) | 1.02 (0.95–1.09) | 1.98 (1.76–2.20) | 0.11 / 0.11 / 0.39 dB | 16.2 kHz rms |
| ≥30 m/s (15.3–31.3 kHz) | 0.97 (0.91–1.05) | 1.86 (1.63–2.10) | 0.13 / 0.13 / 0.42 dB | 14.6 kHz rms |

The legs separate power from range, because outbound is 12 dB weaker at the
same ranges. With R² normalization the spread of excess-to-peak falls from
2.7 to 0.6 dB. At 30 m the excess is −62 dB per Doppler bin relative to the
peak when averaged over ±1 range bin, or −60 dB at the peak's range bin. The
frame bootstrap ignores correlation between consecutive CPIs.

Power ∝ S·R² means a per-chirp phase error proportional to delay,
δφ = 2πτδf, with δφ ≈ 0.021 rad rms at 30 m. The equivalent frequency error
treats the whole excess as small phase errors, corrected for the range
averaging (1.57 dB). The 2026-09-22 phase-noise-outdoor study found the same
delay-squared scaling for a stationary reflector at 39 and 78 MHz/µs, no
beat-frequency scaling when the slope doubled (arguing against ADC timing
jitter), a phase-dominated disturbance common to the RX channels, 13.8–16.9
kHz equivalent rms over 5–31 kHz, and a level 8–12 dB above the CW datasheet
phase noise. The walk adds a third slope, another day and carrier, and the
power scaling. Strong returns at 55–75 m and 150–165 m in the post-walk CPIs
likewise show a remote-Doppler excess fully correlated between RX channels.
Viktor's chamber component along the target steering vector is probably the
same effect.

For a weak target the own pedestal is negligible, so the sensitivity
reference is unaffected. If the scaling holds to long range, the phase error
reaches about 0.7 rad at 1 km, which would mean up to about 2 dB coherent loss
and a large pedestal around strong returns. For phase noise the delay-squared
law is the small-fτ limit of 4 sin²(πfτ); at 1 km it is reduced by 0.6, 1.7
and 3.9 dB at 30, 50 and 75 kHz, so 0.7 rad is an upper estimate. A frequency
offset that is constant over each chirp would not saturate.

### Reflector

The walking reflector measured 1.27 dB stronger than the nominal 10 dBsm lab
reflector; neither is absolutely calibrated. A 10 dBsm triangular trihedral at
76 GHz has about 7.8 cm inner edge from the vertex (about 11 cm opening). Its
on-axis near-field loss, |sinc(A_eff/λR)|², is 0.2–0.3 dB at the lab's
2.2–2.5 m and negligible on the walk, so the lab comparison is not affected
by near field. See `pa_260916_antenna_centers.md` in l2-sp for the
finite-aperture treatment.

## The report

Points raised in the thread or found in review:

- The 36.57 dB anchor is a selected fixed-R⁻⁴ fit of an RX magnitude sum over
  far-quarter noise, not a per-RX SNR and not a measurement at 100 m.
- Viktor's clarifications: Blackman windows and fourfold padding on both axes;
  the "0.4 dB" is the improvement from padding, not a remaining straddle loss.
- Calibration phase varying linearly with frequency is expected from channel
  group delays; extracting them per RX (range peak with interpolation) is
  still open and needs the chamber data.
- Covariance estimates must use only the physical half of the real-sampled
  range spectrum.
- The chamber is phase-noise limited, so its coherent RX gain (7.14 dB) says
  nothing about gain against thermal noise and must not enter range budgets.
- Minor: Section 1.4 says 7.19 dB where Table 5 gives 7.14 dB; Table 3's
  "ADC-bandbredd" is the sampled RF sweep; 120 ms is the frame period, not a CPI.
- Section 3.2: the 13 dB threshold corresponds to Pfa ≈ 2.2e-9; its 950 m is
  consistent with that. The earlier 994 m came from an early Psi configuration
  with 17 dBi antennas and Pfa = 1e-6, so the two are not comparable. A
  zero-mean complex Gaussian target is Swerling 1.

## Open questions and next measurements

For Viktor: radar height and how the reflector was carried (especially
outbound); low-noise or ultra-low-noise RX mode; the reflector's dimensions.

Measurements, in rough order of cost:

1. **The building about 300 m from the office window.** Captures with the walk
   waveform (reaches about 380 m) and with half the slope. If the S·R² law
   holds, the pedestal relative to the peak is 20 dB higher than at 30 m. The
   400/800 MHz waveforms of 22 September would alias at that range. Check for
   ADC clipping from the window frame.
2. **A combined session with the phase-noise lawn plan:** stationary reflector
   on a tripod at measured ranges and heights; the same position with two chirp
   slopes; TX power steps; reflector-absent references; a TX-off capture.
3. Repeat selected points at another height to separate multipath.

## Reproducing

```sh
make study_260911_carkit_validation                     # about 2 minutes
make study_260911_carkit_validation CARKIT_WALK_DATA=/path/to/capture
```

The steps run in order and write `summary.json` (plus per-frame CSV) and
figures under `generated/<step>/`. The JSON/CSV files and the figures linked
from these notes are tracked, so they are available without the raw capture;
the other figures are only generated locally.

| Script | Content |
|---|---|
| [carkit_common.py](carkit_common.py) | Capture loading and checks, spectra, legs, controls, constants |
| [walk_extract.py](walk_extract.py) | Target tracking, per-RX cell values, the report's statistic and selection |
| [walk_background.py](walk_background.py) | Background spectrum, traffic CPIs, cross-RX coherence |
| [walk_reference_snr.py](walk_reference_snr.py) | Target-free reference, averaging conventions, the breakdown |
| [walk_dynamics.py](walk_dynamics.py) | CPI length, Doppler structure, RX nulls, pedestal ratios |
| [walk_pedestal.py](walk_pedestal.py) | Pedestal power/range fit and equivalent frequency error |
| [walk_model.py](walk_model.py) | Model and comparison |
