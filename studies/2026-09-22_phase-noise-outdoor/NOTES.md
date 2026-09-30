# Outdoor reflector captures: phase noise at strong returns

<!-- Figures linked from these notes are tracked through the .gitignore in this
folder, since they cannot be regenerated without the raw data. When adding or
removing a figure link, update that list. -->

Status 2026-09-30. Consolidated after a review; the earlier README and scripts
are in the git history of this branch. The toolbox phase-noise model on this
branch ([phase_noise.py](../../radarperf/phase_noise.py)) gets its own review.
After that, the plan is to merge the model to `main` and combine this study with
the CARKIT walk study (`studies/2026-09-11_carkit-validation`, branch
`carkit-validation-study`) into one study validating CARKIT against the models.

## Summary

Viktor Kärnstrand captured a CARKIT radar (CTRX8188F, TX1, eight RX) looking
at a corner reflector outdoors at nominal 5 and 10 m, with 400 and 800 MHz
sweeps. Strong returns raise the range–Doppler background at their own range
over the whole Doppler axis. The CW datasheet phase noise predicts a much weaker
effect.

- **Every strong return carries the same per-chirp frequency error δf, as a
  phase error 2πτδf.** The δf series recovered from the reflector and from three
  scene returns out to 42 m (delays up to 7.4 times the reflector's) correlate
  0.96–1.03 with each other, with additive noise removed, and give 13–21 kHz
  rms. It is common to all eight RX channels.
- **It is 12.5–14.2 dB above what the CW datasheet table predicts for the same
  quantity, and 7.6–9.3 dB above the table's maximum.** Measured 13.8–16.9 kHz
  rms over 5–31 kHz slow-time frequency; the CTRX8188F typical table gives
  3.3 kHz, the maximum table 5.8 kHz.
- **The excess is at low frequency offsets only.** The skirt that high offsets
  spread across range is at or below the CW table's prediction. Raising the
  whole table to match the per-chirp error would put that skirt 10 dB above the
  measured background at 5 m. The excess sits where the table is flat, inside
  the synthesizer's loop bandwidth.
- **It is pure phase.** The reflector's amplitude fluctuations sit at half the
  additive background (within 0.7 dB), and its phase fluctuations minus its
  amplitude fluctuations equal the phase common to all RX (within 0.4 dB).
- **It does not depend on chirp slope.** 16.8–16.9 kHz at 39 MHz/µs,
  13.8–14.1 kHz at 78 MHz/µs, and 16.9 kHz at 9.84 MHz/µs in the CARKIT walk.
  Timing jitter between ramp and ADC would scale with slope.
- **The slow phase drift within each CPI is motion, and the setup was not
  rigid.** Scene returns drift together in Hz, so the radar moved; the reflector
  moves on its own. Both were hand-held (Viktor, 2026-09-30). Motion
  cannot produce the fast component: radar motion gives every return the same
  phase, not the same δf, and reflector motion affects only the reflector.
- **The remote-Doppler background away from strong returns is independent of
  the reflector.** It is −32 to −33 dB ADC-count² per bin in all four captures,
  while the reflector changes by 17 dB, and it is uncorrelated between RX
  channels.

For the toolbox, the sourced CW table stays as it is. A separate per-chirp
frequency-error term, fitted to the measured slow-time spectrum, is justified
by these data and the CARKIT walk; how far the 2πτδf law extends in range is
open (see [Open questions](#open-questions)).

## Captures

Raw data: `~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector`, not in the
repo. Four directories of ten CPIs each, real int16 ADC data [1024 chirps,
512 samples, 8 RX] with a JSON sidecar per CPI and a manifest with SHA-256.

| Case | Sampled bandwidth | Slope | RF span | Reflector, apparent range | Reflector peak, RX1 |
|---|---:|---:|---|---:|---:|
| 400MHz-5m | 399.6 MHz | 39.02 MHz/µs | 77.80–78.20 GHz | 5.72 m | 46.9 dB |
| 400MHz-10m | 399.6 MHz | 39.02 MHz/µs | 77.80–78.20 GHz | 12.00 m | 31.6 dB |
| 800MHz-5m | 800.4 MHz | 78.16 MHz/µs | 77.60–78.40 GHz | 6.27 m | 48.7 dB |
| 800MHz-10m | 800.4 MHz | 78.16 MHz/µs | 77.60–78.40 GHz | 12.06 m | 37.8 dB |

Peaks are in dB ADC-count² per native range–Doppler bin. All cases: TX1 at
0 dB backoff, 50 MS/s, 512 samples in a 10.24 µs payload that starts 5.54 µs
into the ramp, 15.96 µs PRI, 1024 chirps. The sidecars give RX gain +3 dB (code
0) and high-pass code 0. The ADC extremes are −1180 and +1074 of ±2048, with no
samples at the rails. There are no timestamps and no reflector-absent captures.

The setup was not rigid: all tripods were in use, so Viktor held the radar and
Haik, a coworker, held the reflector (Viktor, 2026-09-30). At 10 m
the two sweeps place the reflector within 6 cm of each other; at 5 m they
differ by 0.55 m. The reflector peak varies by 1.4–4.6 dB over the ten CPIs of
each capture. Neither affects the results, which use each capture's own delays
and per-chirp phases; the motion itself is quantified under
[Slow drift is motion](#slow-drift-is-motion).

The [static scene](generated/scene/scene.png) has strong returns around 24,
29, 35 and 42 m; in 400MHz-10m the 29 m return is stronger than the reflector.
In 800MHz-10m something moved at 0–10 m at about 1 kHz Doppler (2 m/s), below
the Doppler band used here.

## Method

**Levels.** One RX (RX1), periodic Blackman–Harris range window, periodic Hann
Doppler window, native 512 × 1024 FFTs normalized by the window sums, averaged
in power over the ten CPIs. Levels are per native range–Doppler bin, in
absolute dB ADC-count² or in dBc relative to the reflector's own zero-Doppler
bin. **Remote Doppler** means |f_D| > 5 kHz, up to the 31.3 kHz Nyquist
frequency; this excludes the carrier, its window response and slow drift. The
**background** is the median over 2–15 m, excluding ±1.5 m around the
reflector.

**Per-chirp phase.** For each return, each chirp is projected onto a
Blackman–Harris-weighted tone at the return's exact beat frequency, giving one
complex amplitude per chirp and RX. Its unwrapped phase and fractional
amplitude have a cubic removed per CPI before their Hann-windowed slow-time
spectra are taken; a linear fit gives the drift. The detrended phase of a return
at round-trip delay τ is expressed as an equivalent frequency error
δf = φ/(2πτ).

τ comes from the apparent, beat-derived range. The beat frequency measures the
delay between the received signal and the LO at the mixer, which is exactly the
delay over which LO phase noise decorrelates, so no range calibration is
needed.

**Common component.** Products between distinct RX pairs (28 pairs) estimate
the part of a spectrum common to all channels, rejecting channel-independent
noise in expectation. The same estimator between two returns gives their
common cross-power, and the ratio

  ρ = C(reflector, k) / √(C(reflector, reflector) · C(k, k))

is the correlation of the δf series at return k with the reflector's, free of
additive noise. If every return's phase error is 2πτₖδf with one δf, then ρ = 1
and all returns give the same δf rms.
[test_outdoor_common.py](test_outdoor_common.py) checks the normalizations and
both estimators on synthetic data, including a negative case with independent
errors per return (ρ ≈ 0).

## Results

### Background and ridges

The remote-Doppler level at the reflector's range sits above a background that
does not depend on the reflector
([scene](generated/scene/scene.png), [range–Doppler maps](generated/scene/maps.png)):

| Case | Background [dBc/bin] | At reflector [dBc/bin] | Background [dB ADC-count²/bin] |
|---|---:|---:|---:|
| 400MHz-5m | −79.1 | −74.0 | −32.2 |
| 400MHz-10m | −64.4 | −63.4 | −32.8 |
| 800MHz-5m | −80.7 | −75.0 | −32.1 |
| 800MHz-10m | −70.9 | −67.8 | −33.1 |

The background spans 1.0 dB in absolute terms while the reflector spans 17 dB,
so the higher dBc background at 10 m is only the weaker reference. Its median
squared coherence between RX channels is 0.0005–0.028, against 0.03–0.50 in the
reflector's range bin. The 5 m captures are 0.7 dB (400 MHz) and 1.0 dB
(800 MHz) above the 10 m captures, most visibly at 2–10 m: the reflector's own
high-offset skirt (see
[Comparison with the CW datasheet](#comparison-with-the-cw-datasheet)).

Replacing the Hann Doppler window by Blackman–Harris, corrected for noise
bandwidth, changes the remote-Doppler power at the reflector and the scene
returns by at most 0.04 dB. The ridges are therefore broadband, not leakage from
the carrier.

### Phase, not amplitude

At the reflector, mean over remote Doppler, RX1
([phase and amplitude spectra](generated/phase/phase_amplitude.png)), in
dB rad² or dBc per Doppler bin:

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
frequency, like the fluctuations; the dBc levels in the previous table use the
nearest native bin instead.

### One frequency error at every return

Equivalent δf rms over remote Doppler, and correlation with the reflector's δf
series ([delay scaling](generated/phase/delay_scaling.png)):

| Case | Returns [m] | δf rms [kHz] | ρ with reflector |
|---|---|---|---|
| 400MHz-5m | **5.72**, 23.58, 28.84, 42.06 | **16.8**, 14.4, 18.3, 17.3 | 1.02, 1.03, 0.99 |
| 400MHz-10m | **12.00**, 23.68, 29.16, 34.46 | **16.9**, 19.3, 21.4, 17.5 | 0.96, 0.96, 0.99 |
| 800MHz-5m | **6.27**, 23.83, 28.68, 34.67 | **13.8**, 13.0, 14.7, 14.1 | 1.02, 1.00, 0.98 |
| 800MHz-10m | **12.06**, 23.90, 34.69, 42.30 | **14.1**, 15.9, 14.4, 15.4 | 0.99, 0.99, 0.98 |

The reflector is in bold. ρ is a ratio of estimates, so it can exceed 1.
Motion does not fit this pattern. Moving the radar gives every return the same
phase, so δf would scale as 1/τ, a 17 dB spread across these returns; moving the
reflector would leave the scene returns unaffected. Motion is also far slower
than the 5–31 kHz band (see the next section), and fast pointing changes would
show up in amplitude, which stays at the noise floor. The
phase power at these returns spans 17 dB (delay ratio up to 7.4), while δf stays
within about 2 dB of the reflector's. Per CPI the reflector gives 15.8–17.9 kHz at
400 MHz and 12.8–15.2 kHz at 800 MHz.

Between captures, the reflector's common phase rises 6.51 dB from 5 to 10 m at
400 MHz, against 6.44 dB for delay squared, and 5.88 against 5.67 dB at 800 MHz.

The δf spectrum is smooth, with no lines (for example at PRF/16 from the
16-step phase-modulation setting). It rises from about 28 dB Hz²/Hz at 1–3 kHz to
about 38 dB Hz²/Hz above 20 kHz, and is 1–2 dB lower at 800 MHz than at
400 MHz.

### Slow drift is motion

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
expected with both hand-held (see [Captures](#captures)). The analysis removes the
drift with the per-CPI cubic, and the remote-Doppler band excludes it. A rigid
mount would remove the drift and the peak variation, not the fast component.

### Comparison with the CW datasheet

[outdoor_model.py](outdoor_model.py) predicts the measured quantity from the
toolbox's CTRX8188F CW table (upper band, 77–81 GHz; TX-port data treated as
shared by TX and RX, delay-filtered by 4 sin²(πfτ), 1 Hz–20 MHz,
constant extrapolation outside 10 kHz–10 MHz). The per-chirp phase is the
Blackman–Harris-weighted mean of the phase difference over the payload, sampled
once per chirp, so its slow-time PSD is the delay-filtered phase PSD times the
weighting's response, folded at the PRF
([comparison](generated/model/model.png)):

| Case | Measured δf rms | CW typical | CW maximum | Excess over typical | Excess over maximum |
|---|---:|---:|---:|---:|---:|
| 400MHz-5m | 16.8 kHz | 3.29 kHz | 5.77 kHz | 14.2 dB | 9.3 dB |
| 400MHz-10m | 16.9 kHz | 3.29 kHz | 5.77 kHz | 14.2 dB | 9.3 dB |
| 800MHz-5m | 13.8 kHz | 3.29 kHz | 5.77 kHz | 12.5 dB | 7.6 dB |
| 800MHz-10m | 14.1 kHz | 3.29 kHz | 5.77 kHz | 12.7 dB | 7.8 dB |

A separate small-delay calculation with a direct transform of the weighting
also gives 3.29 kHz for the typical table. The CARKIT walk, at 76.37 GHz with
the same sampling and PRI, is 16 dB above the lower-band typical table
(2.64 kHz). The CW prediction's spectrum is flat over slow-time frequency; the
measured one rises.

The full range–Doppler prediction (`phase_noise_fft`) averaged over remote
Doppler gives a skirt of −83.6 and −83.4 dBc/bin at 2–15 m in the two 5 m
captures. Raised by the per-chirp excess, it would be 9.6 and 9.8 dB above the
measured background. If the receiver background is the same in all captures,
the 0.7 and 1.0 dB by which the 5 m captures exceed the 10 m captures put the
measured skirt at −87.5 dBc/bin for both sweeps, 4 dB below the CW typical
prediction. The per-chirp phase only sees
offsets that the 10.24 µs payload average passes, up to a few hundred kHz,
while range bins beyond the reflector's mainlobe see higher offsets. So the
excess is confined to low offsets, where the table is flat (−78 dBc/Hz up to
100 kHz), inside the synthesizer loop bandwidth.

## Relation to the CARKIT walk

The CARKIT walk study (branch `carkit-validation-study`, NOTES "Doppler
pedestal") found the same effect independently, on another day, carrier and
sweep, with the radar on a tripod and a hand-carried reflector. Its pedestal
scales as target power^1.02 × range^2.00 over 15–51 m, appears only at the
reflector's range (not at the same range when the reflector is elsewhere, nor
±12 m away), and corresponds to 16.9 kHz rms in the same 5–31 kHz band at
9.84 MHz/µs. Strong returns at 55–75 m and 150–165 m in its post-walk CPIs show
a remote-Doppler excess fully correlated between RX channels.

Together they settle what the earlier version of these notes proposed to
measure on the lawn: the disturbance is multiplicative, tied to the return,
scales with delay squared, and follows delay rather than beat frequency. The
cross-return test here does this within a single capture, without the
placement uncertainty of comparing captures.

## Open questions

1. **Why the low-offset frequency noise is 12–14 dB above the CW table.**
   Candidates: the synthesizer's behaviour while ramping (the table is CW), this
   board's reference clock, or settling after the ramp starts (5.54 µs before
   the payload). Bench tests: CW phase noise at the TX port with a spectrum
   analyser and harmonic mixer, compared with the flat −78 dBc/Hz; reference
   clock phase noise; varying the pre-payload time and the PRI.
2. **Whether the 2πτδf law holds at long range.** It is the small-delay limit;
   components that vary within a few µs saturate. A strong return near the
   radar's unambiguous range tests it: for example the building about 300 m
   from the office window, with the walk waveform (unambiguous to about 381 m).
   The pedestal relative to the peak should then be about 20 dB higher than at
   30 m. The 400/800 MHz waveforms alias there.
3. **The rising slow-time spectrum.** Neither the CW model nor white per-chirp
   noise gives it; it sets how the pedestal is distributed over Doppler.
4. **The identity of the background.** A TX-off capture would show whether the
   channel-independent background is receiver noise; the CARKIT walk needs the
   same capture for its noise reference.

New captures should have the radar and any reflector on fixed mounts, with the
setup (mounting, distances, heights, a photo) and capture order logged next to
the raw data.

## Reproduction

```sh
make study_260922_phase_noise_outdoor
```

This runs the synthetic tests and then, reading the raw data from
`$PHASE_NOISE_OUTDOOR_DATA` (default above), three steps of a few seconds each:

| Step | Output in `generated/` | Content |
|---|---|---|
| [outdoor_scene.py](outdoor_scene.py) | `scene/` | Capture validation (sizes, SHA-256), reflector and scene returns, levels, RX coherence, window check |
| [outdoor_phase.py](outdoor_phase.py) | `phase/` | Per-return phase and amplitude spectra, common δf, cross-return correlation, drift |
| [outdoor_model.py](outdoor_model.py) | `model/` | CW datasheet predictions of the per-chirp δf and the remote-Doppler range cut |

Shared loading and spectra are in [outdoor_common.py](outdoor_common.py). Each
step writes a `summary.json` (tracked) and figures (tracked when linked from
these notes); the `.npz` arrays passed between steps are not tracked.
