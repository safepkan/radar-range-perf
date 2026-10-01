# CARKIT validation: range model and phase noise

<!-- Figures linked from these notes are tracked through the .gitignore in this
folder, since they cannot be regenerated without the raw data. When adding or
removing a figure link, update that list. -->

Status 2026-10-01. The summary below gives the results and conclusions; the
sections after it describe the measurements and the analysis behind each
result.

## Summary

These notes check our range model (the radarperf toolbox's radar equation
with datasheet values), and the effect of the LO's phase noise, against
measurements with CARKIT, Infineon's evaluation radar for the
CTRX8188F MMIC (76–81 GHz, eight TX, eight RX). Lannik Psi will use the same
MMIC on our own PCB with a different antenna. All measurements use our single
CARKIT unit:

- a corner reflector carried out to about 50 m and back;
- a reflector held at 5 and 10 m;
- the static scene out of the office window to about 500 m, captured once
  with Infineon's firmware and once with our own.

**Range model**

- **The measured SNR is 1.2 dB above the model, close enough that the model
  needs no correction.** For a 10 dBsm target at 100 m the model predicts
  32.7 dB per receiver channel, from the CTRX8188F datasheet's TX power and
  noise figure, the evaluation antenna's directivity (about 15 dBi) and the
  processing's window losses. The reflector measurement, scaled to the same
  conditions, gives 33.9 dB. The difference is within the uncertainty of the
  reflector's RCS, the geometry and the datasheet values. A first analysis of
  the same data found +4 dB. Most of that came from assuming 10 dBsm for a
  reflector that measures 11.3 dBsm (1.3 dB), and from taking the noise at the
  far end of the range spectrum rather than at the target's range (1.2 dB).
- **At short range, below 27 m, where ground reflections matter least, the
  measurement is on the model:** 32.8 ± 0.6 dB. Further out, ground multipath
  spreads the points.
- **Apparent ranges are correct to about 0.2 %.** For moving vehicles, the
  change in apparent range matches the distance their Doppler speed gives,
  which depends only on the carrier frequency and the CPI timing.
- **The receiver's noise floor is about 1.2 dB higher at 1 MHz IF than at
  20 MHz, and this decides between +1.2 and +2.4 dB.** It belongs to the
  receiver: it is independent between the RX channels, unchanged with 10 dB
  less TX power and with no scene in view, and has the same shape in all
  captures. If it is the IF gain's shape, signal and noise are shaped alike
  and +1.2 dB holds. If it is extra receiver noise at low IF, the comparison
  with the model's flat noise figure gives +2.4 dB. A stationary reflector
  captured with two or three chirp slopes would decide it; turning the TX off
  would not.

**Phase noise and chirp timing**

Phase noise of the LO makes a return's phase vary from chirp to chirp. For a
return at round-trip delay τ the variation is 2πτδf, where δf is an equivalent
frequency error per chirp, the same for all returns. It raises a pedestal over
Doppler around strong returns, and costs coherent gain if it grows large at
long range.

- **With our firmware, δf is at the level the datasheet's phase noise
  predicts: 3.5 kHz rms.** That lies between the typical (2.7–3.4 kHz) and
  maximum (4.8–5.9 kHz) values computed from the CTRX8188F's CW phase-noise
  table for the same quantity, and has the same flat spectrum over Doppler.
- **With Infineon's firmware it is 4–9 times larger, 14–30 kHz, on the same
  unit and the same scene.** The error arises in the MMIC either way; the
  firmware, which runs on the radar's microcontroller, decides how the MMIC is
  programmed. The likely cause is the chirp timing. Between chirps the
  synthesizer flies back to the start frequency, may wait, and then starts the
  next ramp, whose first part (the pre-payload) is not sampled. Infineon's
  configurations use 60 ns flyback and 60 ns wait, while the datasheet allows
  the synthesizer up to 1 µs just to come within ±500 kHz of the start
  frequency. Ours use 2 µs flyback and at least 3 µs wait. With Infineon's
  firmware, δf falls as the pre-payload grows: 30, 21 and 14–19 kHz at 3.5,
  4.2 and 5.5 µs. Ours gives 3.5 kHz at 4.0 µs. Which setting matters
  (flyback, wait, or another synthesizer setting) has not been tested yet.
- **It behaves as an LO error.** The same δf holds at every return from
  about 20 m to at least 270 m (within ±0.1 kHz beyond 60 m); it is common to
  all receiver channels, and pure phase. It does not depend on the chirp
  slope, so it is not timing jitter. A longer sampled ramp averages it down,
  as it does ordinary phase noise: with a 41 µs ramp it is at most 0.56 kHz,
  where 0.43–0.51 kHz is predicted.
- **It does not affect a weak target's own sensitivity,** but it sets the
  pedestal around strong returns. At 1 km the per-chirp phase is at most
  0.15 rad with our timing, about 0.1 dB of coherent loss. With Infineon's
  timing it would be 0.6–1.3 rad, or 1.5–7 dB.

**Conclusions**

- The range model matches CARKIT to within 1.2–2.4 dB, the measurement being
  the better, depending on the noise-floor question above; no correction
  follows.
- The toolbox's phase-noise model, built on the datasheet's CW table, describes
  the per-chirp error with well-timed chirps; no separate empirical term is
  needed.
- The time between chirps (flyback, wait, pre-payload) is a waveform-design
  parameter for Psi. Until it is known which part matters, keep within the
  datasheet's settling times, as our firmware does.
- This withdraws a conclusion posted on 2026-09-29: that the LO's per-chirp
  error is 8–12 dB above the datasheet and could reach 0.7 rad at 1 km. That
  held only for Infineon's chirp timing.

Still open: which timing setting matters (captures with different timings, our
firmware, the office window), and whether the low-IF noise floor is gain shape
or noise (a stationary reflector at several ranges with two chirp slopes).

## Measurements

Four sets of captures, all with our single CARKIT unit: the walk
(2026-09-11), the outdoor reflector captures of 2026-09-22 (formerly the
phase-noise-outdoor study), and two sets of captures out of the office window,
on 2026-08-27 with Infineon's firmware and on 2026-09-30 with our own. The
walk results were posted in the Slack thread on 2026-09-29; the posted text and
figures are in [deliverables/2026-09-29](deliverables/2026-09-29/). Its
paragraph on the Doppler pedestal is superseded (see the summary). Earlier
versions of the walk and outdoor analyses are in the git history of the
branches `carkit-validation-study` and `phase-noise`.

| | Walk | Outdoor captures | Window, 2026-08-27 | Window, 2026-09-30 |
|---|---|---|---|---|
| Date | 2026-09-11 | 2026-09-22 | 2026-08-27 | 2026-09-30 |
| Aurix firmware | Infineon's CARKIT application, recorded with Viktor's own host tool (inferred from the format) | Same (inferred) | Infineon's CARKIT application, recorded with RadarGUI | Ours (`remove-lannik-embedded-276-g66e0e0dc-dirty`) |
| MMIC RAM firmware | Not recorded | Not recorded | Not recorded | Infineon's `8188_release_1.0.0_rc3` (revision 2836676, from Strata 3.6.0) |
| Scene | Hallesaker; reflector carried out to about 50 m and back | Outdoors; reflector at nominal 5 and 10 m | Office window; the same far returns as on 2026-09-30 | Office window over the E6 towards an urban area; static returns to about 500 m, traffic |
| Mounting | Radar on a tripod; reflector hand-carried | Viktor held the radar, Haik held the reflector (all tripods were in use) | Not recorded | Viktor held the radar out through the open window (the bracket was away) |
| Sweep | 100.78 MHz sampled, 9.84 MHz/µs, centre 76.374 GHz | 399.6 MHz at 39.02 MHz/µs (77.80–78.20 GHz) and 800.4 MHz at 78.16 MHz/µs (77.60–78.40 GHz) | Two modes, alternating: 85.5 MHz at 8.35 MHz/µs and 171 MHz at 16.7 MHz/µs, from 76.20 GHz, carrier stepped 302 kHz per chirp | Short 240 MHz at 23.5 MHz/µs, medium 120 MHz at 11.7 MHz/µs, long 122 MHz at 2.98 MHz/µs, all centred at 77.00 GHz |
| Sampling | Real, 50 MS/s, 512 samples in a 10.24 µs payload, 1024 chirps | Same | Same | Short and medium: 512 samples in 10.24 µs, 512 chirps. Long: 2048 samples in 40.96 µs, 256 chirps |
| Chirp timing: PRI; pre-payload; flyback + wait | 15.96 µs; 5.54 µs; 60 + 60 ns | Same | 14.62 and 13.96 µs; 4.2 and 3.54 µs; 60 + 60 ns | 100 µs (long 90 µs); 4.0 µs; 2 µs + 83.7 µs (long 43 µs) |
| TX / RX | TX1; RX high-pass code 0, gain code 0 | TX1 at 0 dB backoff; RX high-pass code 0, gain +3 dB (code 0) | 8TX DDMA (8 of 16 slots) at 0 dB backoff; RX high-pass code 4, gain code 1 | TX1 or 8TX coherently phased, 0 or 10 dB backoff; RX gain +3 dB; high-pass 300 kHz (in the host code, not the sidecar) |
| Raw data (not in the repo) | `~/Data/tmp/walk-hallesaker-tx1-1-psi`: 200 CPIs, offline PSI-style conversion | `~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector`: 4 × 10 CPIs, manifest and sidecars | `~/Data/carkit/2026-08-27_test_out_of_office_window`: 131 frames in Infineon's format, converted once to `converted_adc/` | `~/Data/carkit/2026-09-30_out-the_window`: 11 cases of 6–10 CPIs, a sidecar per CPI |
| Windows in this study | Periodic Blackman on both axes, fourfold padding, as in Viktor's processing | Periodic Blackman–Harris in range (also for per-chirp amplitudes), periodic Hann in Doppler, no padding | As outdoors | As outdoors |

All datasets are real int16 ADC data [chirp, sample, RX] with SHA-256
checksums, which the pipelines verify. The windows differ because the walk
reproduces Viktor's processing for the SNR comparison, while the outdoor and
window analyses favour low range sidelobes; results that combine datasets say
which they use.

### Firmware

"Infineon's firmware" and "our firmware" in these notes label the two setups.
Three layers decide what the radar does, and the RF behaviour comes from the
last two:

1. **The Aurix firmware,** Infineon's CARKIT application or ours. It does
   nothing on the RF side itself: it programs the MMIC and moves the data.
2. **The MMIC's own RAM firmware,** which the Aurix downloads into the
   CTRX8188F at start-up. Ours loads Infineon's `8188_release_1.0.0_rc3`
   (from Strata 3.6.0), which the 2026-09-30 sidecars record as `mmic_version`
   2836676. Which one Infineon's CARKIT application loads is not recorded: its
   status messages carry no version.
3. **The MMIC configuration:** the ramp program (segment times, slope, DPLL
   band) and the TX and RX settings.

With Infineon's application, the configuration consists of the modes and
waveforms that RadarGUI or a host tool sends. Viktor edited these: the walk's
100 MHz TX1 waveform without carrier step, the 400 and 800 MHz outdoor sweeps,
and the report's 2.5 GHz and calibration profiles are his. The ramp timing
stayed at 60 ns flyback and 60 ns wait in every Infineon-era configuration
found: the walk, the outdoor captures, the report's calibration table and
2026-08-27. The format allows other values; other waveforms in the 2026-08-27
configuration have 0.99 µs wait and 120 ns flyback.

With ours, the host tool that builds the MMIC program (l2-sp
`projects/psi/host/cmd/psi-streamer/waveform.go`) fixes the pre-payload at
4.0 µs, the flyback at 2.0 µs and the DPLL band at 1 GHz. It requires at least
3 µs of wait and enough of the chirp period for the chirp's CSI-2 transfer,
which limits the PRI to about 25.5 µs or more at 512 samples. Its segment
settings follow the user manual: the DPLL in linear mode from pre-payload to
post-payload and in fast-settling mode during flyback and wait; the RX
high-pass at 300 kHz during the payload and at its maximum, 4.8 MHz, during
the flyback; HP boost and a digital filter reset in the pre-payload; RX gain
+3 dB. The sidecars do not record these, but the code fixes them.

The per-chirp error arises in the MMIC's synthesizer in both setups. The Aurix
software can affect it only through layers 2 and 3, or, in principle, through
what the board does during the ramps.

When we switched firmware is not recorded directly:

- 2026-08-27 is a RadarGUI recording.
- The walk and outdoor captures are in Infineon's CARKIT data format, with its
  configuration structure (modes, waveforms, DDMA indices, lock frequency),
  written by Viktor's own tooling. None of these three records a firmware
  version.
- The 2026-09-30 sidecars record ours: an older build at 11:40 and a newer one
  from 12:53. The board was restarted around 12:32.

So the switch came between 2026-09-22 and 2026-09-30, if the outdoor
recordings are as old as their folder name. Viktor can confirm.

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

### Out-of-window captures

**2026-09-30, our firmware**
([window_scene.py](window_scene.py), [scene.png](generated/window/scene/scene.png)).
Eleven folders named `<waveform>-<TX>-<backoff>[-suffix]`, with no other
description; the times are the first CPI's, UTC:

| Case | Time | CPIs | Configured TX | Notes |
|---|---|---:|---|---|
| long-8TX-0dB | 11:40:12 | 6 of 10 | TX1 only | Other firmware build (`...-220-gde2d009b`), no calibration record; no scene beyond 10 m |
| medium-1TX-0dB | 12:53:37 | 10 | TX1 | |
| medium-1TX-10dB | 12:55:00 | 10 | TX1, 10 dB backoff | |
| medium-8TX-0dB | 12:56:38 | 10 | 8TX coherent | |
| short-1TX-0dB | 12:57:30 | 10 | TX1 | |
| short-1TX-10dB | 12:58:29 | 10 | TX1, 10 dB backoff | |
| short-8TX-0dB | 12:59:27 | 9 of 10 | 8TX coherent | |
| long-1TX-0dB | 13:03:03 | 6 of 10 | TX1 | Near returns at 4 and 14 m as in `-highway`: probably already pointed along the motorway |
| medium-8TX-0dB-highway | 13:04:50 | 10 | 8TX coherent | Pointed along the motorway instead of straight ahead; matched returns −25 to +15 dB against medium-8TX-0dB |
| medium-8TX-0dB-2 | 13:06:16 | 9 of 10 | 8TX coherent | Settings unchanged, pointed straight ahead again by hand; matched returns −13 to +13 dB against medium-8TX-0dB |
| short-8TX-0dB-2 | 13:07:44 | 10 | 8TX coherent | As above; matched returns −3 to +20 dB against short-8TX-0dB |

"8TX" is all eight transmitters with the calibration's phases and no phase
step (`coherent: true`): a TX beam towards boresight, not DDMA.

Viktor held the radar by hand out through the open window; the bracket was
away. For `-highway` he pointed it along the motorway instead of straight
ahead. `long-1TX-0dB`, two minutes earlier, shares its near returns at 4 and
14 m, so it was probably pointed the same way. Nothing was changed for the
`-2` captures, but their matched returns differ by up to ±13 dB (medium) and
−3 to +20 dB (short) from the first ones: aiming by hand did not reproduce the
pointing, and the 8TX beam is narrow.

The 11:40 capture `long-8TX-0dB` ran a different build of our firmware. The
sidecars' `fw_version`, which the host tool reads from the board, is
`git describe` of l2-sp at build time. At 11:40 it was `de2d009b` of
2026-09-24; from 12:53 on, `66e0e0dc` of 2026-09-30 with uncommitted changes.
The board's uptime shows a restart at about 12:32. The host code at
`de2d009b` had no coherent 8TX, which fits this capture's TX1 setting, and its
sidecars have no calibration record.

At matched static returns, 8TX coherent is −6 to +12.7 dB relative to
TX1 (ideally up to +18 dB at the beam's peak), and 10 dB backoff lowers them
by 7–15 dB (median 13 dB in the medium waveform, 11–12 dB in the short). The
returns' angles are unknown, so neither is a finding about the hardware yet.

The ADC is far from full scale: 16–19 counts rms of ±2048 with TX1, extremes
within ±1049 counts even with 8TX; offsets are −42 to −94 counts. No
capture clips, so the window frame is not a problem.

The long waveform (unambiguous to 1.26 km) sees static returns to about
500 m; beyond that only isolated weak peaks. The strongest distant returns are
at 169 and 273 m (20 and 19 dB per chirp with TX1), with others at 231 and
265 m. The 2026-08-27 recording has similar features at 174–175 and
270–280 m. Which one is the large building needs a map. The difference is
not a range-scale error. Our range scale is right to 0.2 % (below), and
Infineon's apparent ranges agree with the delay implied by its carrier step
to within 1 % (0.05 % at the strongest returns). So the two recordings saw
different scatterers, as their different pointing allows.

**Range scale** ([window_range_scale.py](window_range_scale.py),
[range_scale.png](generated/window/range_scale/range_scale.png)). Range comes
from the beat frequency, so an error in slope or sample rate scales it. A
vehicle's Doppler speed depends only on the carrier frequency, and the board
starts the CPIs every 100 ms. Moving targets are tracked by range over the CPIs
of the 2026-09-30 captures, their Doppler is unwrapped against the range rate,
and the apparent range is fitted against the Doppler-integrated distance; the
slope of that fit is the range scale. The 16 tracks with at least five CPIs,
beyond 60 m and within 15 cm rms give a median of 1.002, and the 13 of them
within 0.1 of it a weighted mean of 1.002 (p5–p95 0.997–1.010). Nearer
vehicles are excluded, since they turn and their strongest scatterer moves
along the body. Our host code's slope, frequency, timing and decimation
encodings follow the user manual's equations exactly, so a correct scale is
what the code predicts.

The strongest returns drift in phase by the same number of Hz within each
51 ms CPI: 1.4–3.3 Hz rms, or 2.7–6.4 mm/s: the hand-held radar moving. Two
of the late captures also carry a small fast phase common to all returns (see
below).

The sidecars record the ramp timing, the ramp and ADC frequencies, the TX
channels, backoff and phases, the RX gain, the calibration and the firmware
version. They do not record the per-segment settings (DPLL mode, RX
high-pass), which the host code fixes (see [Firmware](#firmware)), nor the RX
noise mode, and the firmware version ends in `-dirty` (built with uncommitted
changes).

**2026-08-27, Infineon's firmware.** Recorded with RadarGUI in Infineon's
packet format and converted once with
[window_convert_infineon.m](window_convert_infineon.m), which reads it with
the CARKIT decoder in l2-sp (commit `26638ae4`) and writes one int16 file and
sidecar per frame to `converted_adc/`; the ADC integers are recovered
exactly. There are 131 frames, alternating between mode 0 (42 frames) and
mode 1 (89). All eight TX run in DDMA in slots 2, 5, 8 and 11–15 of 16, and
the carrier steps 302 kHz from chirp to chirp, which moves a static return's
lines by step × delay (0.35 cycles per chirp at 175 m). The data confirm both
signs; weaker spurious lines appear in unused slots 7 and 10. The noise floor
per cell is taken from mode 0 beyond its scene (300–449 m).

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

| | Chamber reflector | Walking reflector |
|---|---|---|
| Type | Microwave Factory [MTR76P10-T5DW-100](https://www.mwf.co.jp/en/products/rf_accessories/mtr.html), triangular trihedral | Home-made: reflecting plates glued onto a trihedral of 1 cm absorber; we have two |
| Size | 77.8 mm inner edge if ideal (not measured) | 100 mm inner edge, from the vertex along a seam (measured 2026-10-01) |
| RCS | 10 dBsm at 76.5 GHz, as specified | 14.3 dBsm if ideal (at 76.4 GHz); measured against the chamber reflector, 11.3 dBsm at 2.5 m, about 11.5 dBsm in the far field |

A triangular trihedral with inner edge a has ideal RCS σ = 4πa⁴/(3λ²).

The lab comparison put the chamber reflector at 2.22 m and the walking one at
2.51 m, aligned their angle responses and compared P × R⁴: the walking
reflector came out 1.27 dB stronger. The first-order on-axis near-field loss,
|sinc(A/λR)|² with A = a²/√3 (see `pa_260916_antenna_centers.md` in l2-sp), is
0.24 dB for the chamber reflector and 0.51 dB for the larger walking one at
their distances. These notes earlier said the loss cancels between the two;
that holds only for reflectors of the same size. So the far-field difference
is about 0.27 dB larger, and the walking reflector is about 11.5 dBsm.

That is 2.8 dB below an ideal 100 mm trihedral, plausible for plates glued
onto absorber. A trihedral tolerates being pointed a few degrees off, but its
returned beam is only about 2° wide for a 100 mm aperture at a 3.9 mm
wavelength. Plate-angle errors of a few tenths of a degree steer that beam
partly away from the radar. The walking reflector's metal stand, which the report noted, may have
added to the comparison, which would make the reflector itself weaker still.
On the walk itself (15–51 m) the near-field loss is below 0.05 dB.

The scripts keep 11.27 dBsm (`walk_common.py`). With 11.5 dBsm, the walk's
+1.2 dB over the model becomes +0.9 dB (+2.2 dB with the far-quarter
reference). That is within the stated uncertainty, and the correction is not
applied yet. A side-by-side comparison at 10 m or more would settle both this
and how much the two home-made reflectors differ (see the open questions).

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
shape. These notes earlier said that a TX-off capture would decide; it would
not, since both remain with TX off. It can only show that the background is
the receiver's, which the window captures now show. What decides is a signal
of known level at different IFs: a reflector on a fixed mount at one range,
captured with two or three chirp slopes. Its beat frequency moves while
nothing else changes, and a point target's peak power in the window-normalized
range spectrum does not depend on slope. With gain shape its power follows the
background's shape, about 0.8 dB more at 1 MHz than at 6.6 MHz; with receiver
noise it stays put.

**Window captures.** The channel-independent remote-Doppler floor
(|f_D| > 1 kHz), from the middle four eigenvalues of the 8×8 RX covariance in
each range bin, relative to its median over 18–24 MHz
([background.png](generated/window/scene/background.png)). A disturbance with
one spatial signature, such as a scene return, its pedestal or a vehicle,
takes the largest eigenvalue whatever its angle, which products between RX
pairs would not separate:

| Capture | 0.7 MHz | 1 MHz | 2 MHz | 3.3 MHz | 6.6 MHz | 13 MHz | 18–24 MHz [dB ADC-count²/cell] |
|---|---:|---:|---:|---:|---:|---:|---:|
| short-1TX-0dB | 1.13 | 1.18 | 0.95 | 0.71 | 0.45 | 0.14 | −30.77 |
| short-1TX-10dB | 1.18 | 1.25 | 0.95 | 0.73 | 0.40 | 0.15 | −30.90 |
| medium-1TX-0dB | 1.14 | 1.26 | 1.01 | 0.76 | 0.53 | 0.21 | −30.84 |
| medium-1TX-10dB | 1.11 | 1.24 | 1.02 | 0.76 | 0.44 | 0.15 | −30.88 |
| long-1TX-0dB | 1.14 | 1.20 | 1.01 | 0.98 | 0.38 | 0.15 | −33.52 |
| long-8TX-0dB (no scene) | 1.28 | 1.31 | 0.94 | 0.78 | 0.45 | 0.17 | −33.51 |
| Walk, over its far quarter | | 1.5 | 1.2 | 0.9 | 0.5 | 0.2 | |

10 dB less TX power changes the floor by at most 0.13 dB and its shape by at
most 0.1 dB, and a capture with no scene beyond 10 m has the same floor as the
one with the full scene. So the excess at low IF comes from the receiver, not
from the TX or anything reflected, and it has the walk's shape, 0.2–0.3 dB
lower at 1–2 MHz (with a different reference). The long waveform's cells are
3 dB lower for the same noise (four times the samples, half the chirps). Below
about 0.5 MHz the high-pass filter takes over (6 m in the medium waveform). In
the no-scene capture a component common to the RX channels lifts the total
remote-Doppler power 2.2 dB above the independent floor at all ranges,
probably the high-offset skirt of the strong return within 10 m; it has not
been examined further.

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

| Dataset | Firmware | Pre-payload; flyback + wait | Slope | δf rms | Slow-time band | Estimator |
|---|---|---|---:|---:|---|---|
| Walk | Infineon | 5.54 µs; 0.12 µs | 9.84 MHz/µs | 16.9 kHz | 5–31 kHz | Pedestal excess over same-range controls, all of it treated as phase |
| Walk | Infineon | 5.54 µs; 0.12 µs | 9.84 MHz/µs | 19.0 kHz | 5–31 kHz | Phase of a static return at 39 m common to all RX, after the walk |
| Outdoor 400 MHz | Infineon | 5.54 µs; 0.12 µs | 39.02 MHz/µs | 16.8–16.9 kHz | 5–31 kHz | Reflector phase common to all RX |
| Outdoor 800 MHz | Infineon | 5.54 µs; 0.12 µs | 78.16 MHz/µs | 13.8–14.1 kHz | 5–31 kHz | Reflector phase common to all RX |
| Window 08-27, mode 1 | Infineon | 3.54 µs; 0.12 µs | 16.71 MHz/µs | 30.0 kHz | 0.5–36 kHz | Shared by clean static returns, 21–175 m |
| Window 08-27, mode 0 | Infineon | 4.2 µs; 0.12 µs | 8.35 MHz/µs | 21.2 kHz | 0.5–34 kHz | Shared by static returns, 70–280 m (only one clean) |
| Window 09-30, medium | Ours | 4.0 µs; 85.7 µs | 11.67 MHz/µs | 3.47 kHz | 0.5–5 kHz | Shared by clean static returns, 27–267 m |
| Window 09-30, short | Ours | 4.0 µs; 85.7 µs | 23.46 MHz/µs | 3.53 kHz | 0.5–5 kHz | Shared by clean static returns, 24–139 m |
| Window 09-30, long | Ours | 4.0 µs; 45 µs | 2.98 MHz/µs | ≤ 0.56 kHz | 0.5–5.6 kHz | Same; 41 µs payload |

Over 0.5 kHz to PRF/2, each band covers nearly all of the per-chirp variance.
The 5–31 kHz values of the earlier captures are 1–2 % below their 0.5–31 kHz
values (a one-off check). Within a firmware the slope changes by a factor of 8
(Infineon's, at 5.54 µs) or 2 (ours) without a matching change in δf. Timing
jitter between ramp and ADC, or ADC sampling jitter, would make the error scale
with slope (or with beat frequency), so neither fits. Between the firmwares, δf
differs by 16 dB at nearly the same pre-payload, 4.2 and 4.0 µs
([Window: the MMIC programming sets the error](#window-the-mmic-programming-sets-the-error)).

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
2.4 dB. The window captures extend the law to 270 m with our firmware
([Window: the MMIC programming sets the error](#window-the-mmic-programming-sets-the-error)),
where the per-chirp quantity, averaged over the payload, saturates by only
about 0.5 dB.

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
synthesizer loop bandwidth. All these captures were made with Infineon's
firmware; with ours the per-chirp error is at the table's level (next
section).

### Window: the MMIC programming sets the error

**Method** ([window_phase.py](window_phase.py)). The returns of each case are
the local maxima of its static profile, at least 8 dB above the per-chirp
noise, 10 m out and four range cells apart. Each return's per-chirp complex
amplitude is compared with a smooth model
(`carkit_common.tone_model_errors`), a cubic per slow-time line:

- For our firmware, one line at zero Doppler; 8TX coherent is one tone too.
- For Infineon's DDMA, eight lines at the slots plus the skew step × delay,
  refined per return on the data, since the apparent delay is off by up to
  about 1 %.

The model error, summed over RX with the model as weight, gives a per-chirp
phase and amplitude. The band is |f_D| ≥ 500 Hz, which at our firmware's
10 kHz PRF is the whole per-chirp variance apart from slow motion. Under DDMA,
bins within four of a multiple of PRF/16 are left out, where the weighting and
the spurious slot lines put deterministic content, and the variance is scaled
by the fraction left out.

Moving clutter in a return's range cell, such as traffic or vegetation, moves
amplitude and phase alike, whereas an LO error is pure phase. A return
therefore counts as clean if its amplitude fluctuation is within a factor of
two of the additive noise, or its excess is at least ten times smaller than the
phase's. Two clean returns at least 10 m apart share only the LO error in their
δf series φ/(2πτ), since noise and clutter in different range cells are
independent. Their cross-powers are fitted, weighted by the inverse product of
the two returns' own powers, as

  C_ij = δf² (√(τ_i τ_j) / τ₀)^(2γ) + b_c / (τ_i τ_j):

one δf at every delay, plus a phase common to all returns of capture c, of rms
2π√b_c, as the radar's motion gives. δf is the fit at γ = 0, with p5–p95 from
resampling CPIs. [test_carkit_common.py](test_carkit_common.py) checks the
estimator on synthetic data, for one line and under DDMA, with shared and with
independent errors.

**Results** ([phase.png](generated/window/phase/phase.png)):

| Case | Clean returns | Pairs | δf rms (p5–p95) | Common phase |
|---|---|---:|---:|---:|
| medium-1TX-0dB | 7, 27–169 m | 19 | 3.15 kHz (2.77–3.44) | 1 mrad |
| medium-8TX-0dB | 14, 28–267 m | 87 | 3.57 kHz (3.48–3.65) | 0 |
| medium-8TX-0dB-2 | 16 of 17, 27–251 m | 114 | 3.42 kHz (3.34–3.48) | 0 |
| medium-8TX-0dB-highway | 6 of 16, 53–217 m | 14 | 1.9 kHz (0–2.9); all returns 3.38 kHz | 14 mrad |
| short-1TX-0dB | 3, 28–110 m | 2 | 3.0 kHz (2.1–3.8), pair mean | |
| short-8TX-0dB | 10, 24–129 m | 37 | 4.11 kHz (3.91–4.28) | 0 |
| short-8TX-0dB-2 | 13 of 24, 31–139 m | 63 | 3.29 kHz (3.17–3.52) | 6 mrad |
| long-1TX-0dB | 5, 14–273 m | 8 | ≤ 0.56 kHz (p95) | |
| Both 10 dB backoff cases | none above 8 dB per chirp | | | |
| **medium, pooled** | | 234 | **3.47 kHz (3.40–3.52)** | |
| **short, pooled** | | 102 | **3.53 kHz (3.44–3.66)** | |
| infineon-mode1 | 7 of 9, 21–175 m | 20 | **30.0 kHz (29.6–30.3)** | 0 |
| infineon-mode0 | 1 of 7 | 20, all returns | **21.2 kHz (20.4–21.9)**, pair mean | |

The captures spread over 3.2–4.1 kHz, more than the bootstrap intervals, since
scene and returns differ between them. 1TX and 8TX coherent agree within that
spread, as a shared LO requires; independent errors in the eight TX paths
would be averaged down by the coherent sum. The highway capture is dominated
by traffic (10 of 16 returns fail the clean test) and is not used for
conclusions. In Infineon mode 0 all returns but one fail the clean test at the
coarser 1.75 m cells; its pair mean over all returns stands in. Its pairs give
15–30 kHz, 21–29 kHz where the two returns correlate well. The common phase of
6 and 14 mrad rms above 500 Hz in two of the late captures (1.8 and 4.5 µm)
fits the hand-held radar; it does not enter δf.

**Against the CW table.** The prediction for these waveforms (as outdoors,
now `carkit_common.per_chirp_frequency_psd`) is 2.69–2.71 kHz typical with the
76–77 GHz table and 3.35–3.38 kHz with the 77–81 GHz table, and 4.78–4.82 and
5.88–5.93 kHz maximum. Our sweeps are centred at 77.00 GHz, the boundary
between the tables. The measured 3.47–3.53 kHz is 2.2–2.3 dB above the
lower-band typical, 0.3–0.4 dB above the upper-band typical and 2.8–4.6 dB
below the maxima. For the Infineon recording (76.2–76.7 GHz, lower table) the
typical is 2.8 kHz, so 30.0 kHz is 20.5 dB above it and 21.2 kHz 17.6 dB.

**Spectrum.** Our firmware's δf PSD is flat at 30.9–32.4 dB Hz²/Hz over
0.5–5 kHz; the typical tables give a flat 29.0 and 31.0 dB Hz²/Hz. Infineon's
mode 1 rises from 25.0 dB Hz²/Hz at 0.5–2 kHz to 42.8 dB Hz²/Hz at 20–36 kHz,
against a flat 20.6 dB Hz²/Hz from the typical table at its 71.6 kHz PRF:
4 dB above at the lowest slow-time frequencies, 22 dB at the highest. An error
concentrated near PRF/2 alternates from chirp to chirp, as it would if the
synthesizer had not settled from the previous ramp when the next payload
begins. That is a working hypothesis, not tested.

**Delay law.** Medium, pooled, by the pair's farther return, with each
capture's common phase removed:

| Farther return | Pairs | δf rms |
|---|---:|---:|
| 10–60 m | 4 | 3.06 kHz |
| 60–130 m | 64 | 3.52 kHz |
| 130–200 m | 58 | 3.58 kHz |
| 200–290 m | 108 | 3.43 kHz |

δf is the same within ±0.1 kHz from 60 to 290 m, τ up to 1.9 µs. With a free
exponent γ = +0.08 (0.05–0.12), phase power goes as τ^2.2 rather than τ². The
CW model's own saturation at 270 m is 0.5 dB for a return's own δf; for pairs
with one far return it is about half of that, in line with the 0.37 dB drop
from 130–200 to 200–290 m. Infineon's mode 1 gives γ = +0.08 (0.075–0.095) over
21–175 m. Where the returns span less than a decade of delay, as in the short
waveform (γ = +0.27, 0.08–0.44), the exponent trades off against the common
phase, so the medium table is the delay-law result.

**Payload length.** The long waveform (41 µs payload, PRI 90 µs) gives at
most 0.56 kHz (p95) over 8 pairs at 14–273 m. The typical tables predict
0.43–0.51 kHz and the maxima 0.82–0.91 kHz. Averaging over the longer payload
removes more of the LO's frequency noise; an error that is constant over each
chirp would not be reduced.

**What differs.** Same unit, same window, same 10.24 µs payload (short and
medium) and 50 MS/s sampling. The MMIC is programmed differently (see
[Firmware](#firmware)):

- Infineon's configurations follow each ramp with 60 ns flyback and 60 ns
  wait, so the next ramp starts almost at once, with 3.54–5.54 µs of
  pre-payload. Their δf falls as the pre-payload grows: 30 and 21 kHz at 3.54
  and 4.2 µs, in alternating frames of one recording, and 14–19 kHz at
  5.54 µs, in other captures with other sweeps.
- Ours has 2 µs flyback, 84 µs wait (43 µs in the long waveform) and 4.0 µs
  pre-payload, and gives 3.5 kHz.

The pre-payload alone therefore does not set δf. The flyback, the wait, the
DPLL settings or the MMIC's RAM firmware may; the datasheet's ramp timing
points at the first two (next section). DDMA is not the cause, since the
walk and outdoor captures used TX1 alone. These data do not say which it is;
the test is the first measurement in the open questions.

### The datasheet's ramp timing

The CTRX8188F target datasheet (rev. 0.20, 2025-06-17) and user manual
(rev. 0.20, 2025-11-10) give limits for the ramp segments. Both are
NDA-restricted and kept outside the repo (`~/Git/docs/Infineon/CTRX8188F`).
The toolbox's phase-noise table is the datasheet's Table 22, which is
specified in CW mode.

| Segment | Datasheet or user manual | Infineon's configurations | Ours |
|---|---|---|---|
| Flyback | Up to 1 µs until the frequency is within ±500 kHz of the next start frequency, for a 4 GHz step; up to 15 MHz overshoot or undershoot with a 1 µs flyback (datasheet Table 23) | 60 ns | 2.0 µs |
| Wait | DPLL in fast-settling mode during flyback and wait, linear mode from pre-payload to post-payload (user manual Table 120) | 60 ns | 84 µs here, at least 3 µs |
| Pre-payload | TX settling up to 1.5 µs from the start of the chirp until the ramp meets its linearity requirement (Table 23); RX settling between ramps up to 1.4 µs at a 300 kHz high-pass | 3.54–5.54 µs | 4.0 µs |
| High-pass during the payload | 300–2400 kHz; 4.8 MHz is not allowed during payloads and is recommended during the flyback (Table 120) | Code 0 (walk, outdoor); code 4 on 2026-08-27 | 300 kHz |

Infineon's configurations leave the synthesizer about 120 ns in
fast-settling mode before it switches to linear mode for the next ramp. The
datasheet allows up to 1 µs just to come within ±500 kHz of the start
frequency, so the pre-payload has to absorb the rest of the settling. That
fits what the captures show: an LO error common to all returns, varying from
chirp to chirp, falling as the pre-payload grows, and at the CW level when
flyback and wait meet the datasheet.

Two things it does not explain:

- The datasheet specifies the flyback only for a 4 GHz step and says nothing
  about variation from chirp to chirp.
- At a 5.54 µs pre-payload, δf does not grow with the frequency step: 17–19,
  17 and 14 kHz for steps of 0.16 GHz (walk) and 0.6 and 1.2 GHz (outdoors).
  The time in fast-settling mode, or the switch to linear mode, may matter
  more than the size of the step.

The timing test settles it.

If RadarGUI's high-pass codes are the user manual's `RX_HP_FC` values, the
2026-08-27 configuration used the 4.8 MHz setting during the payload, which the
manual does not allow. The steep fall of those captures' floor below about
40 m in mode 1 and 90 m in mode 0 fits it. It does not explain the per-chirp
error, which the walk and outdoor captures show at 300 kHz.

### Consequences at long range

For a weak target the own pedestal is negligible, so the sensitivity reference
is unaffected. With our firmware's timing, δf ≈ 3.5 kHz gives a per-chirp
phase of 0.15 rad rms at 1 km (τ = 6.7 µs) if the delay law holds that far.
Here it holds to 270 m. That is about 0.1 dB of coherent loss, and in fact
less, since for phase noise the delay-squared law is the small-fτ limit of
4 sin²(πfτ); at 1 km it is reduced by 0.6, 1.7 and 3.9 dB at 30, 50 and
75 kHz. A longer payload lowers it further: the long waveform's 0.5 kHz gives
0.02 rad at 1 km. With Infineon's timing (14–30 kHz) it would be 0.6–1.3 rad
at 1 km, up to 1.5–7 dB of coherent loss and a large pedestal around strong
returns. For Psi, the time between ramps (flyback, wait, pre-payload) is
therefore part of the waveform design. Our firmware's present timing is fine;
how short it can be made without the error returning is what the timing test
should show.

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

**For Viktor, on the window captures and the firmware:**

Answered on 2026-10-01: the radar was hand-held out through the open window,
`-highway` was pointed along the motorway, and nothing was changed for `-2`.
The sky captures are planned for 2026-10-01.

1. What was `long-8TX-0dB`? It ran a different firmware build (from
   2026-09-24), has only TX1 configured and shows no scene beyond 10 m; Viktor
   believes all captures used the same firmware. Was it the first capture
   after a reflash, and what was the radar facing?
2. How does our firmware's MMIC programming differ from Infineon's, apart
   from the ramp timing in the sidecar: DPLL and loop settings, ramp and
   flyback options? Which MMIC RAM firmware does Infineon's CARKIT application
   load?
3. Is the MMIC configuration fully determined by the sidecar together with
   the host code's version? The per-segment settings are fixed in
   `waveform.go`, but the host code's version is not recorded, the RX noise
   mode is not in either, and the firmware version ends in `-dirty`.
4. Viktor says pre-payload, post-payload, flyback and wait are configurable.
   In l2-sp master (and origin/master as of 2026-09-30 13:08) they are
   constants in `waveform.go` and not in the web GUI; does his uncommitted
   version expose them? Where do the present values come from? They are well
   inside the datasheet's limits.
5. When did we switch to our firmware? Were the walk and outdoor captures made
   with Infineon's CARKIT application and Viktor's own host tool, as their
   formats suggest? Which firmware and timing did the report's lab
   measurements use? Its calibration table has Infineon-era timing (15.96 µs,
   60 ns); its TX-count table has a 100 µs chirp period at 25 MS/s.
6. Does 10 dB backoff give 10 dB less TX power? Matched returns fell by
   7–15 dB, median 13 dB, though the scene may have changed between captures.
7. How was the 8TX calibration done (reflector at 2.2 m)? Coherent 8TX gave
   −6 to +12.7 dB over TX1 at matched returns, against up to +18 dB at the
   beam's peak. The returns' angles are unknown, so this is only a question.

**Still open from the walk:** the radar height and how the reflector was
carried (especially outbound); low-noise or ultra-low-noise RX mode. High-pass
code 0 is 300 kHz, if RadarGUI's codes are the user manual's `RX_HP_FC`
values.

**Measurements, in rough order of priority:**

1. **Chirp-timing test.** The window scene serves well: TX1, the medium
   waveform, the radar on a fixed mount, alternating captures of ten CPIs in
   one session. Two ways, which answer slightly different questions:
   - With Infineon's application, keep everything else and lengthen the
     flyback to the datasheet's 1 µs, then also the wait, which its
     configuration allows. If δf drops to about 3.5 kHz, the timing is the
     cause, not the RAM firmware or other settings.
   - With ours, shorten the PRI towards the CSI-2 limit: about 9 µs of wait
     at 512 samples, or about 4 µs at 256. A 60 ns flyback or wait, or a
     different pre-payload, needs the constants in `waveform.go` changed.

   Shortening the PRI alone keeps the flyback at 2 µs and the wait at 3 µs or
   more, both beyond the datasheet's 1 µs, so δf should stay at about
   3.5 kHz. That would be consistent with the timing explanation but no test of
   it. The decisive settings are a flyback and wait below about 1 µs, which
   Viktor was asked for. Either way, this decides what the Psi waveform must
   respect.
2. **A reflector on a fixed mount at one range, captured with two or three
   chirp slopes,** to tell IF gain shape from receiver noise (+1.2 or +2.4 dB
   for the walk). It replaces the TX-off capture proposed earlier, which cannot
   decide this.
3. **Bench measurement of the CW phase noise** at the TX port (spectrum
   analyser and harmonic mixer), only if item 1 leaves an excess unexplained.
   With our firmware the per-chirp error is already at the datasheet level.
4. **A one-time calibration of the home-made reflectors against the chamber
   reflector,** outside the office entrance at about 10 m, where the near-field
   loss is 0.03 dB for a 100 mm reflector. The walking reflector's RCS is the
   largest uncertainty in the absolute comparison with the model. The
   procedure is to be planned in detail before the session; the main points
   are a fixed radar mount, the same marked spot for each reflector, coherent
   subtraction of each empty mount, and repeated placements.
5. **Repeat selected walk points at another height** to separate multipath.

The window captures have answered the test at the building proposed earlier:
the delay law holds to 270 m, where the CW model's own saturation is 0.5 dB,
and nothing clipped.

New captures should have the radar and any reflector on fixed mounts, with the
setup (mounting, pointing, window open or closed, distances, heights, a photo)
and capture order logged next to the raw data.

**Open in the analysis:**

- Why Infineon's δf spectrum rises towards PRF/2. Item 1 should explain it if
  it is settling.
- The common component of 2.2 dB in the no-scene capture's remote-Doppler
  background, probably the skirt of the strong return within 10 m.

## Reproducing

```sh
make study_260911_carkit_validation      # about 4 minutes
make study_260911_carkit_validation CARKIT_WALK_DATA=/path CARKIT_OUTDOOR_DATA=/path \
    CARKIT_WINDOW_DATA=/path CARKIT_WINDOW_INFINEON_DATA=/path
```

This runs the study's synthetic tests, then the walk, outdoor and window steps
in order. Each step writes `summary.json` (and, for some walk steps, a
per-frame CSV) and figures under `generated/<dataset>/<step>/`. The JSON/CSV
files and the figures linked from these notes are tracked, so they are
available without the raw data; the `.npz` arrays passed between steps and the
other figures are only generated locally.

The window steps also run on any new recording in our firmware's format,
with the case directories discovered (`--cases auto`) or listed, and the outputs
in their own folder:

```sh
venv/bin/python studies/2026-09-11_carkit-validation/window_scene.py --data DIR \
    --cases auto --output OUT/scene
venv/bin/python studies/2026-09-11_carkit-validation/window_phase.py --data DIR \
    --cases auto --scene OUT/scene --output OUT/phase
```

The 2026-08-27 recording is converted once, outside `make`, in MATLAB with
l2-sp's code on the path:

```matlab
run('~/Git/l2-sp/matlab/addL2SpMatlabPath.m')
cd studies/2026-09-11_carkit-validation
window_convert_infineon   % writes converted_adc/ beside the recording
```

| Script | Content |
|---|---|
| [carkit_common.py](carkit_common.py) | Shared paths, I/O and estimators (per-chirp amplitudes, detrending, unwrap-free phase, multi-line model errors, cross-RX and cross-return power, CW per-chirp prediction) |
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
| [window_convert_infineon.m](window_convert_infineon.m) | One-time MATLAB conversion of the 2026-08-27 recording (l2-sp CARKIT decoder) |
| [window_common.py](window_common.py) | Window capture loading and checks for both recordings, TX/DDMA configuration, case discovery, static peaks |
| [window_scene.py](window_scene.py) | Checksums, ADC levels, static profiles, channel-independent background, matched levels, drift |
| [window_phase.py](window_phase.py) | Per-chirp δf from clean static returns, delay law, common phase, CW prediction, slow-time spectra |
| [window_range_scale.py](window_range_scale.py) | Range scale from moving vehicles: apparent range change against Doppler-integrated distance |
| [test_carkit_common.py](test_carkit_common.py) | Synthetic checks of the normalizations and estimators |
