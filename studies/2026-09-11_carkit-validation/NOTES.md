# CARKIT validation: range model and phase noise

<!-- Figures linked from these notes are tracked through the .gitignore in this
folder, since they cannot be regenerated without the raw data. When adding or
removing a figure link, update that list. -->

Status 2026-09-30. This study combines the CARKIT walk (captured 2026-09-11)
and the outdoor reflector captures of 2026-09-22, formerly the
phase-noise-outdoor study. The walk results were posted in the Slack thread on
2026-09-29; the posted text and figures are in
[deliverables/2026-09-29](deliverables/2026-09-29/). Earlier versions of both
studies are in the git history of the branches `carkit-validation-study` and
`phase-noise`.

## Summary

Viktor Kärnstrand made two sets of measurements with a CARKIT radar
(CTRX8188F, TX1, eight RX): a corner reflector carried away from and back
towards the radar (the walk), and a corner reflector held at nominal 5 and 10 m
outdoors with 400 and 800 MHz sweeps (the outdoor captures). Together they
validate the range model against thermal noise and show a phase disturbance
that the CW phase-noise data do not predict.

**Range performance**

- **The measured per-RX SNR is 33.9 dB at 100 m and 10 dBsm, against 32.7 dB
  from the model (+1.2 dB).** With the far-quarter noise reference instead of
  the local one it is 35.1 dB (+2.4 dB). The report's 4 dB is mostly the
  reflector's RCS (1.3 dB) and the noise reference (1.2 dB). The remaining
  difference is within the uncertainty of reflector RCS, geometry and datasheet
  values; no model correction follows.
- **On the inbound leg below 27 m, where ground multipath should matter least,
  the measurement is 32.8 ± 0.6 dB, essentially on the model.**
- **The receiver background is independent between RX channels in both
  datasets.** In the walk it is 1–1.5 dB above the far quarter at the walk's
  beat frequencies and stable in time: IF gain shape or receiver noise, which
  decides between +1.2 and +2.4 dB. Outdoors it is the same within 1 dB in all
  four captures, while the reflector changes by 17 dB.

**The per-chirp frequency error**

- **Every strong return carries the same per-chirp frequency error δf, as a
  phase error 2πτδf.** Outdoors, the δf series at the reflector and at scene
  returns out to 42 m correlate 0.96–1.03 with each other, with additive noise
  removed; it is common to all eight RX channels and pure phase. In the walk,
  the Doppler pedestal it raises scales as target power^1.02 × range^2.00.
- **The delay law holds to at least 170 m.** Vehicles passing after the walk
  carry the δf of a static return at 39 m: beyond 80 m they share 0.88 of it
  (p5–p95 0.72–1.08), and 0.96 at 130–230 m, where τ is about 1.1 µs. If
  every return had the same phase error, the share would be about 0.3.
- **It is 14–19 kHz rms over 5–31 kHz and does not depend on chirp slope:**
  17–19 kHz at 9.84 MHz/µs in the walk, 16.8–16.9 kHz at 39 MHz/µs and
  13.8–14.1 kHz at 78 MHz/µs outdoors. Timing jitter between ramp and ADC
  would scale with slope.
- **It is 12.5–17 dB above what the CTRX8188F CW phase-noise table predicts for
  the same quantity**, and 7.6–9.3 dB above the table's maximum outdoors. The
  excess is at low frequency offsets only: the skirt that high offsets spread
  across range is at or below the table's prediction.
- **For a weak target's own sensitivity it is negligible.** It matters around
  strong returns, whose pedestal it sets, and possibly for coherence at long
  range: if the delay law holds beyond 170 m, the phase error reaches about
  0.7 rad at 1 km.

For the toolbox, the phase-noise model on `main` stays as a model of standard
phase noise, with the sourced CW tables. A separate empirical per-chirp
frequency-error term, fitted to the measured slow-time spectrum, is justified
by these data; whether the 2πτδf law saturates beyond 170 m is open.

## Measurements

| | Walk | Outdoor captures |
|---|---|---|
| Date | 2026-09-11 | 2026-09-22 |
| Scene | Hallesaker; reflector carried out to about 50 m and back | Outdoors; reflector at nominal 5 and 10 m |
| Mounting | Radar on a tripod; reflector hand-carried | Viktor held the radar, Haik held the reflector (all tripods were in use) |
| Sweep | 100.78 MHz sampled, 9.84 MHz/µs, centre 76.374 GHz | 399.6 MHz at 39.02 MHz/µs (77.80–78.20 GHz) and 800.4 MHz at 78.16 MHz/µs (77.60–78.40 GHz) |
| Sampling | Real, 50 MS/s, 512 samples in a 10.24 µs payload, 1024 chirps at 15.96 µs PRI | Same |
| TX / RX | TX1; RX high-pass code 0, gain code 0 | TX1 at 0 dB backoff; RX high-pass code 0, gain +3 dB (code 0) |
| Raw data (not in the repo) | `~/Data/tmp/walk-hallesaker-tx1-1-psi`: 200 CPIs, offline PSI-style conversion | `~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector`: 4 × 10 CPIs, manifest and sidecars |
| Windows in this study | Periodic Blackman on both axes, fourfold padding, as in Viktor's processing | Periodic Blackman–Harris in range (also for per-chirp amplitudes), periodic Hann in Doppler, no padding |

Both datasets are real int16 ADC data [1024 chirps, 512 samples, 8 RX] with
SHA-256 checksums, which the pipelines verify. The payload starts 5.54 µs into
the ramp. The windows differ because the walk reproduces Viktor's processing
for the SNR comparison, while the outdoor analysis favours low range
sidelobes; results that combine the two datasets say which they use.

### Walk

Inputs besides the raw capture:

| Input | Notes |
|---|---|
| [CARKIT report.pdf](inputs/CARKIT%20report.pdf) | Current report, 17 pages, 2026-09-22 |
| [empirical-1km-snr-budget.pdf](inputs/empirical-1km-snr-budget.pdf) | Earlier six-page report, superseded |
| [slack.txt](inputs/slack/slack.txt) and images | Thread up to 2026-09-28: processing details, reflector comparison |

The capture's `provenance/configuration.json` shows `current_mode = 1`,
waveform 0 (the walk waveform). Resolution is 1.487 m per range bin and
0.120 m/s per Doppler bin; unambiguous range is about 381 m. The integration is
10.49 ms sampled in a 16.34 ms CPI.

### Outdoor captures

| Case | Reflector, apparent range | Reflector peak, RX1 |
|---|---:|---:|
| 400MHz-5m | 5.72 m | 46.9 dB |
| 400MHz-10m | 12.00 m | 31.6 dB |
| 800MHz-5m | 6.27 m | 48.7 dB |
| 800MHz-10m | 12.06 m | 37.8 dB |

Peaks are in dB ADC-count² per native range–Doppler bin. The ADC extremes are
−1180 and +1074 of ±2048, with no samples at the rails. There are no timestamps
and no reflector-absent captures. At 10 m the two sweeps place the reflector
within 6 cm of each other; at 5 m they differ by 0.55 m. The reflector peak
varies by 1.4–4.6 dB over the ten CPIs of each capture. With both ends
hand-held, neither is surprising; the results use each capture's own delays and
per-chirp phases, so they are unaffected.

The [static scene](generated/outdoor/scene/scene.png) has strong returns around
24, 29, 35 and 42 m; in 400MHz-10m the 29 m return is stronger than the
reflector. In 800MHz-10m something moved at 0–10 m at about 1 kHz Doppler
(2 m/s), below the Doppler band used here.

### Chamber

Viktor's report also uses a chamber measurement: a reflector at 2.3 m, a
400 MHz payload from a stated 76.58 GHz start, the same sampling and PRI as
above, one dummy chirp, a 300 kHz analog high-pass setting, RX gain −3 dB, and
either a single TX or TX1 + TX6 + TX7 + TX8. Its raw and calibration data were
not supplied, so it is not analysed here.

## Range performance against thermal noise

### Model

| Quantity | Value |
|---|---|
| Model TX / NF | CTRX8188F datasheet: 14.5 dBm, NF 10.2 dB (low-noise mode at 10 MHz; 10.5 dB at 1 MHz; ultra-low-noise mode 0.5 dB lower) |
| Model antenna | FARAD-IV digitized boresight: 15.05 / 14.98 dBi TX / RX; the datasheet describes these as directivity |
| Model target | Nonfluctuating 10 dBsm at boresight; no straddle or CFAR loss |
| Processing | The walk's Blackman windows (2.37 dB ENBW loss each); fourfold padding leaves at most 0.07 dB scalloping |

The model is [walk_model.py](walk_model.py). Viktor's hand calculation gives
32.63 dB, the same as the model. The model has no terms for chip-to-antenna
transitions, antenna ohmic loss, radome or temperature derating; these would
make it more pessimistic. A review of such missing terms is pending separately.

### Method

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
patch ([rx_null_example.png](generated/walk/dynamics/rx_null_example.png)).
These are spatial and temporal nulls from a composite reflector-plus-person
return, not fixed calibration differences. They also explain why Viktor's
coherent RX sum (41.6 dB, about 39 dB after the same noise and RCS corrections)
gains only about 5 dB over the per-RX level rather than 9 dB. This is a rough
estimate, not computed here.

### CPI length

Reprocessing each CPI as 128–1024-chirp segments
([cpi_length.png](generated/walk/dynamics/cpi_length.png)):

| Leg | Deficit against ideal at 1024 chirps | p10–p90 | Single-tone fraction | Power outside ±0.5 m/s |
|---|---:|---:|---:|---:|
| Inbound | 0.20 dB | −0.13 to 0.49 dB | 0.93 | 0.9 % |
| Outbound | 1.41 dB | 0.26 to 4.5 dB | 0.53 | 11.7 % |

The inbound return integrates nearly ideally over the full CPI. The outbound
return is spread in Doppler by the carrier's motion. A synthetic tone through
the same processing gave 3.06 / 6.01 / 9.09 dB against the ideal 3.01 / 6.02 /
9.03 dB (a one-off check, not part of the scripts).

### Reflector

The walking reflector measured 1.27 dB stronger than the nominal 10 dBsm lab
reflector; neither is absolutely calibrated. A 10 dBsm triangular trihedral at
76 GHz has about 7.8 cm inner edge from the vertex (about 11 cm opening). Its
on-axis near-field loss, |sinc(A_eff/λR)|², is 0.2–0.3 dB at the lab's
2.2–2.5 m and negligible on the walk, so the lab comparison is not affected
by near field. See `pa_260916_antenna_centers.md` in l2-sp for the
finite-aperture treatment.

## The receiver background

**Walk.** The background at |v| ≥ 10 m/s relative to the far quarter
([background.png](generated/walk/background/background.png)):

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

**Outdoor captures.** RX1, mean power over |Doppler| > 5 kHz per native bin; the
background is the median over 2–15 m, excluding ±1.5 m around the reflector
([scene](generated/outdoor/scene/scene.png),
[range–Doppler maps](generated/outdoor/scene/maps.png)):

| Case | Background [dBc/bin] | At reflector [dBc/bin] | Background [dB ADC-count²/bin] |
|---|---:|---:|---:|
| 400MHz-5m | −79.1 | −74.0 | −32.2 |
| 400MHz-10m | −64.4 | −63.4 | −32.8 |
| 800MHz-5m | −80.7 | −75.0 | −32.1 |
| 800MHz-10m | −70.9 | −67.8 | −33.1 |

dBc is relative to the reflector's own zero-Doppler bin. The background spans
1.0 dB in absolute terms while the reflector spans 17 dB, so the higher dBc
background at 10 m is only the weaker reference. Its median squared coherence
between RX channels is 0.0005–0.028, against 0.03–0.50 in the reflector's range
bin. The 5 m captures are 0.7 dB (400 MHz) and 1.0 dB (800 MHz) above the 10 m
captures, most visibly at 2–10 m: the reflector's own high-offset skirt (see
[Comparison with the CW datasheet](#comparison-with-the-cw-datasheet)).

## The per-chirp frequency error

A strong return raises the remote-Doppler background at its own range: a ridge
along Doppler in the range–Doppler map. Both datasets show that it is a phase
error per chirp, proportional to the return's round-trip delay τ:
δφ = 2πτδf, with one frequency error δf per chirp shared by all returns and RX
channels.

| Dataset | Slope | δf rms, 5–31 kHz | Estimator |
|---|---:|---:|---|
| Walk | 9.84 MHz/µs | 16.9 kHz | Pedestal excess over same-range controls, all of it treated as phase |
| Walk | 9.84 MHz/µs | 19.0 kHz | Phase of a static return at 39 m common to all RX, after the walk |
| Outdoor 400 MHz | 39.02 MHz/µs | 16.8–16.9 kHz | Reflector phase common to all RX |
| Outdoor 800 MHz | 78.16 MHz/µs | 13.8–14.1 kHz | Reflector phase common to all RX |

The slope changes by a factor of 8 without a matching change in δf. Timing
jitter between ramp and ADC, or ADC sampling jitter, would make the error scale
with slope (or with beat frequency), so neither fits.

### Walk: the pedestal scales with power and range squared

A strong return raises the remote-Doppler background at its own range; ±12 m
away there is no change. At |v| ≥ 20 m/s the median excess over same-range
controls is 1.2 dB inbound and 0.05 dB outbound. Fitting
`excess = 10 log10(1 + k S^a (R/30 m)^b)` to both legs
([walk_pedestal.py](walk_pedestal.py),
[pedestal_scaling.png](generated/walk/pedestal/pedestal_scaling.png)):

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

Power ∝ S·R² means a per-chirp phase error proportional to delay, with
δφ ≈ 0.021 rad rms at 30 m. The equivalent frequency error treats the whole
excess as small phase errors, corrected for the range averaging (1.57 dB).
Strong returns at 55–75 m and 150–165 m in the post-walk CPIs likewise show a
remote-Doppler excess fully correlated between RX channels. Viktor's chamber
component along the target steering vector is probably the same effect.

### Walk: passing vehicles extend the delay law to 170 m

After the walk, two vehicles approach at about 22 m/s from beyond 190 m
([walk_long_range.py](walk_long_range.py),
[long_range.png](generated/walk/long_range/long_range.png)). They are strong
enough for a per-chirp phase (at least 10 dB above the per-chirp noise), but
they fluctuate on their own: micro-Doppler and aspect changes. So each vehicle
is compared with the strongest static return, at 39.4 m, in the same CPI.
Cross-RX products remove additive noise, and the vehicle's own fluctuations are
uncorrelated with the reference, so

  β = C(reference, vehicle) / C(reference, reference)

in δf units is the part of the reference's frequency error that the vehicle
carries: 1 if the phase error is 2πτδf at both delays, τ_ref/τ_vehicle if every
return had the same phase error. The reference's δf is stationary, so its
power is pooled over the 67 post-walk CPIs without a moving return within 5 m
of it; five CPIs where the vehicles pass it are excluded. The reference is only
about 4 dB above the per-chirp noise, where phase unwrapping slips, so both
phases come from an unwrap-free estimator: derotate each return by its Doppler,
fit a complex cubic per CPI, and take Im(z/fit). Blackman windows and
|v| ≥ 10 m/s, as in the pedestal step.

| Vehicle range | CPIs | Mean range | β (p5–p95) | Correlation | Vehicle δf rms | Vehicle amplitude / phase |
|---|---:|---:|---|---:|---:|---:|
| 45–80 m | 13 | 63 m | 0.82 (0.65–1.03) | 0.42 | 37.5 kHz | −1.7 dB |
| 80–130 m | 9 | 102 m | 0.81 (0.65–1.02) | 0.82 | 18.9 kHz | −9.3 dB |
| 130–230 m | 8 | 167 m | 0.96 (0.80–1.18) | 0.94 | 19.4 kHz | −13.4 dB |
| Beyond 80 m | 17 | 133 m | 0.88 (0.72–1.08) | 0.88 | 19.1 kHz | −11.8 dB |

The reference's δf is 19.0 kHz rms. Beyond 80 m, β is 0.85–0.90 for vehicle
SNR thresholds of 6–12 dB. Near 60 m the vehicles' own fluctuations dominate:
their amplitude fluctuates almost as much as their phase, and the correlation
drops to 0.42. At 130–230 m they are small (amplitude 13 dB below phase), and
the vehicle's own δf, 19.4 kHz, matches the reference's: its phase power is
the 12.6 dB higher that the delay law predicts for 167 m against 39 m.

The law therefore holds to τ ≈ 1.1 µs. This does not yet test saturation: for
phase noise, 4 sin²(πfτ) falls below (2πfτ)² by only 0.2 dB at 100 kHz and
0.7 dB at 200 kHz at 167 m, whereas at 300 m the shortfall reaches 0.6 and
2.4 dB.

### Outdoor: method

For each strong return (the reflector and the three strongest scene returns
within 45 m), each chirp is projected onto a Blackman–Harris-weighted tone at
the return's exact beat frequency, giving one complex amplitude per chirp and
RX. Its unwrapped phase and fractional amplitude have a cubic removed per CPI
before their Hann-windowed slow-time spectra are taken; a linear fit gives the
drift. The detrended phase of a return is expressed as δf = φ/(2πτ). All
returns are at least 25 dB above the per-chirp noise, where unwrapping is
safe.

τ comes from the apparent, beat-derived range. The beat frequency measures the
delay between the received signal and the LO at the mixer, which is exactly the
delay over which LO phase noise decorrelates, so no range calibration is
needed.

Products between distinct RX pairs (28 pairs) estimate the part of a spectrum
common to all channels, rejecting channel-independent noise in expectation.
The same estimator between two returns gives their common cross-power, and the
ratio

  ρ = C(reflector, k) / √(C(reflector, reflector) · C(k, k))

is the correlation of the δf series at return k with the reflector's, free of
additive noise. If every return's phase error is 2πτₖδf with one δf, then ρ = 1
and all returns give the same δf rms.
[test_carkit_common.py](test_carkit_common.py) checks the normalizations and
both estimators on synthetic data, including a negative case with independent
errors per return (ρ ≈ 0).

Replacing the Hann Doppler window by Blackman–Harris, corrected for noise
bandwidth, changes the remote-Doppler power at the reflector and the scene
returns by at most 0.04 dB. The ridges are therefore broadband, not leakage from
the carrier.

### Outdoor: phase, not amplitude

At the reflector, mean over remote Doppler, RX1
([phase and amplitude spectra](generated/outdoor/phase/phase_amplitude.png)),
in dB rad² or dBc per Doppler bin:

| Case | Phase | Amplitude | Half the background | Phase − amplitude | Common to all RX |
|---|---:|---:|---:|---:|---:|
| 400MHz-5m | −74.7 | −82.1 | −82.4 | −75.6 | −75.5 |
| 400MHz-10m | −65.1 | −67.7 | −67.6 | −68.6 | −69.0 |
| 800MHz-5m | −75.9 | −85.3 | −84.7 | −76.4 | −76.4 |
| 800MHz-10m | −69.1 | −75.1 | −74.5 | −70.4 | −70.5 |

Additive noise splits equally between phase and amplitude, so amplitude at half
the background means no amplitude excess. The phase excess over that floor
equals the common phase, so all of it is shared by the RX channels. Half the
background is referenced to the mean per-chirp amplitude at the exact beat
frequency, like the fluctuations; the dBc levels of the background table use
the nearest native bin instead.

### Outdoor: one frequency error at every return

Equivalent δf rms over remote Doppler, and correlation with the reflector's δf
series ([delay scaling](generated/outdoor/phase/delay_scaling.png)):

| Case | Returns [m] | δf rms [kHz] | ρ with reflector |
|---|---|---|---|
| 400MHz-5m | **5.72**, 23.58, 28.84, 42.06 | **16.8**, 14.4, 18.3, 17.3 | 1.02, 1.03, 0.99 |
| 400MHz-10m | **12.00**, 23.68, 29.16, 34.46 | **16.9**, 19.3, 21.4, 17.5 | 0.96, 0.96, 0.99 |
| 800MHz-5m | **6.27**, 23.83, 28.68, 34.67 | **13.8**, 13.0, 14.7, 14.1 | 1.02, 1.00, 0.98 |
| 800MHz-10m | **12.06**, 23.90, 34.69, 42.30 | **14.1**, 15.9, 14.4, 15.4 | 0.99, 0.99, 0.98 |

The reflector is in bold. ρ is a ratio of estimates, so it can exceed 1. The
phase power at these returns spans 17 dB (delay ratio up to 7.4), while δf
stays within about 2 dB of the reflector's. Per CPI the reflector gives
15.8–17.9 kHz at 400 MHz and 12.8–15.2 kHz at 800 MHz. Between captures, the
reflector's common phase rises 6.51 dB from 5 to 10 m at 400 MHz, against
6.44 dB for delay squared, and 5.88 against 5.67 dB at 800 MHz.

Motion does not fit this pattern. Moving the radar gives every return the same
phase, so δf would scale as 1/τ, a 17 dB spread across these returns; moving the
reflector would leave the scene returns unaffected. Motion is also far slower
than the 5–31 kHz band (next section), and fast pointing changes would show up
in amplitude, which stays at the noise floor. The walk, with the radar on a
tripod, shows the same δf.

The δf spectrum is smooth, with no lines (for example at PRF/16 from the
16-step phase-modulation setting). It rises from about 28 dB Hz²/Hz at 1–3 kHz
to about 38 dB Hz²/Hz above 20 kHz, and is 1–2 dB lower at 800 MHz than at
400 MHz.

### Outdoor: slow drift is motion

Drift is the linear phase rate within each CPI, in Hz (10 Hz is 1.9 cm/s):

| Case | Scene returns, rms of their mean | Spread among scene returns, median | Reflector minus scene, rms |
|---|---:|---:|---:|
| 400MHz-5m | 2.7 | 0.5 | 7.0 |
| 400MHz-10m | 3.7 | 0.7 | 6.2 |
| 800MHz-5m | 3.6 | 0.3 | 7.6 |
| 800MHz-10m | 14.6 | 0.4 | 15.5 |

The scene returns at 23–42 m drift by the same number of Hz; an LO frequency
drift would give drift proportional to delay, which differs by up to 1.8 times
between them. So the radar moved, and the reflector moved on its own, as
expected with both hand-held. The analysis removes the drift with the per-CPI
cubic, and the remote-Doppler band excludes it. A rigid mount would remove the
drift and the peak variation, not the fast component.

### Comparison with the CW datasheet

[outdoor_model.py](outdoor_model.py) predicts the measured quantity from the
toolbox's CTRX8188F CW table (upper band, 77–81 GHz; TX-port data treated as
shared by TX and RX, delay-filtered by 4 sin²(πfτ), 1 Hz–20 MHz, constant
extrapolation outside 10 kHz–10 MHz). The per-chirp phase is the
Blackman–Harris-weighted mean of the phase difference over the payload, sampled
once per chirp, so its slow-time PSD is the delay-filtered phase PSD times the
weighting's response, folded at the PRF
([comparison](generated/outdoor/model/model.png)):

| Case | Measured δf rms | CW typical | CW maximum | Excess over typical | Excess over maximum |
|---|---:|---:|---:|---:|---:|
| 400MHz-5m | 16.8 kHz | 3.29 kHz | 5.77 kHz | 14.2 dB | 9.3 dB |
| 400MHz-10m | 16.9 kHz | 3.29 kHz | 5.77 kHz | 14.2 dB | 9.3 dB |
| 800MHz-5m | 13.8 kHz | 3.29 kHz | 5.77 kHz | 12.5 dB | 7.6 dB |
| 800MHz-10m | 14.1 kHz | 3.29 kHz | 5.77 kHz | 12.7 dB | 7.8 dB |

A separate small-delay calculation with a direct transform of the weighting
also gives 3.29 kHz for the typical table. The walk, at 76.37 GHz with the same
sampling and PRI, is 16–17 dB above the lower-band typical table (16.9 and
19.0 kHz against 2.64 kHz, a one-off calculation). The CW prediction's spectrum is flat over slow-time
frequency; the measured one rises.

The full range–Doppler prediction (`phase_noise_fft`) averaged over remote
Doppler gives a skirt of −83.6 and −83.4 dBc/bin at 2–15 m in the two 5 m
captures. Raised by the per-chirp excess, it would be 9.6 and 9.8 dB above the
measured background. If the receiver background is the same in all captures,
the 0.7 and 1.0 dB by which the 5 m captures exceed the 10 m captures put the
measured skirt at −87.5 dBc/bin for both sweeps, 4 dB below the CW typical
prediction. The per-chirp phase only sees offsets that the 10.24 µs payload
average passes, up to a few hundred kHz, while range bins beyond the
reflector's mainlobe see higher offsets. So the excess is confined to low
offsets, where the table is flat (−78 dBc/Hz up to 100 kHz), inside the
synthesizer loop bandwidth.

### Consequences at long range

For a weak target the own pedestal is negligible, so the sensitivity reference
is unaffected. The delay law is tested to 170 m. If it holds to 1 km, the
phase error reaches about 0.7 rad there, which would mean up to about 2 dB coherent loss and a
large pedestal around strong returns. For phase noise the delay-squared law is
the small-fτ limit of 4 sin²(πfτ); at 1 km it is reduced by 0.6, 1.7 and
3.9 dB at 30, 50 and 75 kHz, so 0.7 rad is an upper estimate. A frequency
offset that is constant over each chirp would not saturate.

## The report

Points raised in the thread or found in review of Viktor's walk report:

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

For Viktor: the radar height on the walk and how the reflector was carried
(especially outbound); low-noise or ultra-low-noise RX mode; the reflector's
dimensions; what high-pass code 0 corresponds to.

Measurements, in rough order of cost:

1. **A TX-off capture** with the walk and outdoor waveforms. It decides whether
   the channel-independent background is IF gain shape or receiver noise, and
   with it the +1.2 or +2.4 dB of the walk.
2. **Bench tests of the low-offset frequency noise**, which is 12–16 dB above
   the CW table. Candidates are the synthesizer's behaviour while ramping (the
   table is CW), this board's reference clock, and settling after the ramp
   starts (5.54 µs before the payload). Measure CW phase noise at the TX port
   with a spectrum analyser and harmonic mixer, compared with the flat
   −78 dBc/Hz, and the reference clock's phase noise; vary the pre-payload time
   and the PRI.
3. **The building about 300 m from the office window**, to test whether the
   delay law saturates. The passing vehicles confirm it to 170 m, where
   saturation would stay below about 0.7 dB; at 300 m it could reach 2–3 dB.
   Captures with the walk waveform (unambiguous to about 381 m) and with half
   the slope. If the law holds, the pedestal relative to the peak is 20 dB
   higher than at 30 m. The 400/800 MHz waveforms alias there. Check
   for ADC clipping from the window frame.
4. **Repeat selected walk points at another height** to separate multipath.

New captures should have the radar and any reflector on fixed mounts, with the
setup (mounting, distances, heights, a photo) and capture order logged next to
the raw data.

Open in the analysis: why the δf spectrum rises towards high Doppler. Neither
the CW model nor white per-chirp noise gives that shape, and it sets how the
pedestal is distributed over Doppler.

## Reproducing

```sh
make study_260911_carkit_validation      # about 2.5 minutes
make study_260911_carkit_validation CARKIT_WALK_DATA=/path CARKIT_OUTDOOR_DATA=/path
```

This runs the study's synthetic tests, then the walk steps and the outdoor
steps in order. Each step writes `summary.json` (and, for some walk steps, a
per-frame CSV) and figures under `generated/walk/<step>/` or
`generated/outdoor/<step>/`. The JSON/CSV files and the figures linked from
these notes are tracked, so they are available without the raw data; the
`.npz` arrays passed between outdoor steps and the other figures are only
generated locally.

| Script | Content |
|---|---|
| [carkit_common.py](carkit_common.py) | Shared paths, I/O and estimators (per-chirp amplitudes, detrending, unwrap-free phase, cross-RX common power) |
| [walk_common.py](walk_common.py) | Walk capture loading and checks, Blackman spectra, legs, controls, constants |
| [walk_extract.py](walk_extract.py) | Target tracking, per-RX cell values, the report's statistic and selection |
| [walk_background.py](walk_background.py) | Background spectrum, traffic CPIs, cross-RX coherence |
| [walk_reference_snr.py](walk_reference_snr.py) | Target-free reference, averaging conventions, the breakdown |
| [walk_dynamics.py](walk_dynamics.py) | CPI length, Doppler structure, RX nulls, pedestal ratios |
| [walk_pedestal.py](walk_pedestal.py) | Pedestal power/range fit and equivalent frequency error |
| [walk_long_range.py](walk_long_range.py) | Delay law to about 200 m: passing vehicles against a static reference |
| [walk_model.py](walk_model.py) | Model and comparison |
| [outdoor_common.py](outdoor_common.py) | Outdoor capture loading and checks, Blackman–Harris/Hann spectra, cases |
| [outdoor_scene.py](outdoor_scene.py) | Capture validation, reflector and scene returns, levels, RX coherence, window check |
| [outdoor_phase.py](outdoor_phase.py) | Per-return phase and amplitude spectra, common δf, cross-return correlation, drift |
| [outdoor_model.py](outdoor_model.py) | CW datasheet predictions of the per-chirp δf and the remote-Doppler range cut |
| [test_carkit_common.py](test_carkit_common.py) | Synthetic checks of the normalizations and estimators |
