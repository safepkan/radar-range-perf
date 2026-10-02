# CARKIT validation: range model and phase noise

<!-- Figures linked from these notes are tracked through the .gitignore in this
folder, since they cannot be regenerated without the raw data. When adding or
removing a figure link, update that list. -->

Status 2026-10-02. The summary below gives the results and conclusions; the
sections after it describe the measurements and the analysis behind each
result. What is open, which answers and captures we are waiting for, and which
measurements would close the open points are listed at the end
([Open questions and next measurements](#open-questions-and-next-measurements)).

## Summary

These notes check our range model (the radarperf toolbox's radar equation
with datasheet values), and the effect of the LO's phase noise, against
measurements with CARKIT, Infineon's evaluation radar for the
CTRX8188F MMIC (76–81 GHz, eight TX, eight RX), which carries HUBER+SUHNER's
SENCITY FARAD-IV waveguide antenna. Lannik Psi will use the same
MMIC on our own PCB with a different antenna. All measurements use our single
CARKIT unit:

- a corner reflector carried out to about 50 m and back;
- the same reflector on a tripod at six distances from 4 to 90 m on a grass
  field, each captured with two chirp slopes, and captures with the
  transmitter off;
- a reflector held at 5 and 10 m;
- the static scene out of the office window to about 500 m, captured once
  with Infineon's firmware and twice with our own, the second time with the
  radar on a fixed mount;
- traffic on a motorway seen from a bridge, to 1.2 km.

**Range model**

- **Two sessions with the same reflector disagree by 4.4 dB, so the absolute
  check is open.** With the reflector carried towards the radar, the measured
  SNR per receiver channel is 1.2 dB above the model with datasheet values
  and no hardware losses: 33.9 against 32.7 dB for a 10 dBsm target at 100 m.
  That model uses the CTRX8188F datasheet's TX power and noise figure, the
  FARAD-IV antenna's directivity (about 15 dBi) and the processing's window
  losses. With the reflector on a tripod, and our firmware instead of
  Infineon's, it is 4.3–4.5 dB weaker at 16 and 34 m than when carried at
  15–27 m, which puts the measurement 3–4 dB below the model. The receiver
  noise is the same in both sessions to 0.12 dB, so the difference is on the
  signal side. The reflector's azimuth is ruled out; the radar's elevation
  pointing, the reflector's aim and the TX power as each firmware programs
  it are not.
- **A first analysis of the carried session found +4 dB.** Most of that came
  from assuming 10 dBsm for a reflector that measures 11.3 dBsm (1.3 dB), and
  from taking the noise at the far end of the range spectrum, where the
  receiver is quieter than at the target's range (1.2 dB).
- **The hardware losses left out of the model would widen the carried
  session's gap, not close it.** By its data sheet, the antenna's realized
  gain is up to 0.9 dB below its directivity on each pass, and the loss of
  CARKIT's housing cover in front of the antenna is not known. CARKIT is a
  closed unit whose cover cannot easily be removed, so every measurement here
  includes that loss and none can measure it. In the
  other direction, the datasheet's noise figure at the RX gain setting used is
  0.3–0.5 dB lower than the model's. With these terms the model gives
  31.1–33.1 dB before the cover. Terms of this size are smaller than the
  4.4 dB between the sessions and comparable to the datasheet's range of TX
  power between units (±1.5 dB), so these measurements cannot check them.
- **Apparent ranges are correct to about 0.2 %.** For moving vehicles, the
  change in apparent range matches the distance their Doppler speed gives,
  which depends only on the carrier frequency and the CPI timing.
- **The receiver's background rises by about 1.2 dB from 20 MHz IF down to
  1 MHz, and between 1 and 5 MHz that rise is noise, not the IF gain's
  shape.** It belongs to the receiver: it is the same with the transmitter
  off, with 10 dB less TX power and with no scene in view, and independent
  between the RX channels. A reflector held still and captured with two chirp
  slopes, in the same RF band, moves to twice the beat frequency with nothing
  else changed. From 1.25 to 5.3 MHz its SNR rises by 0.8 dB, about the
  background's fall (0.7 dB); gain shape would leave the SNR unchanged. From
  7 to 14 MHz it does not rise (−0.3 ± 0.2 dB). So the carried session's
  +1.2 dB is the SNR at its own beat frequencies (1–3 MHz); a target at
  5–14 MHz gets up to about 0.5 dB more, about +1.7 dB. Taking the noise at
  20 MHz, which gives +2.4 dB, overstates it.
- **10 dB less TX power lowers the scene by 10.0 dB, and the calibrated
  eight-TX beam adds 17.5 dB at the strongest return,** against 18.1 dB at
  the beam's peak if ideal (radar on a fixed mount).

**Phase noise and chirp timing**

Phase noise of the LO makes a return's phase vary from chirp to chirp. For a
return at round-trip delay τ the variation is 2πτδf, where δf is an equivalent
frequency error per chirp, the same for all returns. It raises a pedestal over
Doppler around strong returns, and costs coherent gain if it grows large at
long range.

- **With our firmware, δf is at the level the datasheet's phase noise
  predicts: 3.1–3.6 kHz rms.** That lies around the typical (2.7–3.4 kHz) and
  below the maximum (4.8–5.9 kHz) values computed from the CTRX8188F's CW
  phase-noise table for the same quantity, and has the same flat spectrum
  over Doppler. It is the same with the radar hand-held and on a fixed mount.
- **With Infineon's firmware it is 4–9 times larger, 14–30 kHz, on the same
  unit and the same scene.** The error arises in the MMIC either way; the
  firmware, which runs on the radar's microcontroller, decides how the MMIC is
  programmed. The likely cause is the chirp timing. Between chirps the
  synthesizer flies back to the start frequency, may wait, and then starts the
  next ramp, whose first part (the pre-payload) is not sampled. Infineon's
  configurations use 60 ns flyback and 60 ns wait, while the datasheet allows
  the synthesizer up to 1 µs just to come within ±500 kHz of the start
  frequency. Ours use 2 µs flyback and at least 3 µs wait. With Infineon's
  firmware, δf falls as the pre-payload grows: 30, 22 and 14–19 kHz at 3.5,
  4.2 and 5.5 µs. Ours gives 3.1–3.6 kHz at 4.0 µs. Which setting matters
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

- The absolute comparison is open. One session puts CARKIT 1.2–1.7 dB above
  the model without hardware losses, the other, with the same reflector and
  the same receiver noise, 3–4 dB below. Until the 4.4 dB between them is
  explained, these measurements place CARKIT only within −4 to +2 dB of the
  model. The losses themselves have to come from their sources (data sheets;
  the cover's loss stays unknown unless a figure turns up); these
  measurements are not precise enough to calibrate them.
- Between 1 and 5 MHz IF the receiver is noisier than at higher IF, by up to
  about 1 dB, and a target's SNR there is correspondingly lower. Long-range
  targets sit at higher IF, where a model with a flat noise figure needs no
  such term.
- The toolbox's phase-noise model, built on the datasheet's CW table, describes
  the per-chirp error with well-timed chirps; no separate empirical term is
  needed.
- The time between chirps (flyback, wait, pre-payload) is a waveform-design
  parameter for Psi. Until it is known which part matters, keep within the
  datasheet's settling times, as our firmware does.
- This withdraws a conclusion posted on 2026-09-29: that the LO's per-chirp
  error is 8–12 dB above the datasheet and could reach 0.7 rad at 1 km. That
  held only for Infineon's chirp timing.
- Near traffic, other radars interfere in up to 14 % of CPIs; the steps
  here drop those CPIs. Handling interference is a separate topic.

## Measurements

Seven sets of captures, all with our single CARKIT unit: the walk
(2026-09-11), the outdoor reflector captures of 2026-09-22 (formerly the
phase-noise-outdoor study), three sets of captures out of the office window,
on 2026-08-27 with Infineon's firmware and on 2026-09-30 and 2026-10-02 with
our own, and, on 2026-10-01, the field captures with the walk's reflector on a
tripod and the highway captures of traffic from a bridge. The
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

| | Field captures | Highway captures | Window, 2026-10-02 |
|---|---|---|---|
| Date | 2026-10-01, 10:38–11:08 UTC | 2026-10-01, 09:57–10:05 UTC | 2026-10-02, 10:17–10:21 UTC |
| Aurix firmware | Ours (`remove-lannik-embedded-276-g66e0e0dc-dirty`, as on 2026-09-30 from 12:53) | Same | Ours (`release/mifu2025-rc1_20260930-52-g6b9c8871-dirty`) |
| MMIC RAM firmware | Revision 2836676, as on 2026-09-30 | Same | Same |
| Scene | Lindevi, a grass football pitch with about 100 m to its end; goals, buildings, trees and power lines in view (photos); reflector at nominal 5, 10, 20, 40, 60 and 100 m | A bridge over the E6 at Sandsjöbacka, pointed along a straight stretch of about 1.2 km; traffic | Office window, as on 2026-09-30 |
| Mounting | Radar on a tripod; the walk's reflector on a small tripod at about 1 m, about the radar's height (photos) | Radar on a tripod on the bridge (photos), about 7 m above the road: the deck about 6 m (±0.5 m; public sources found by a web search, not measured) and the radar about 1 m above it | Not recorded; the scene's phase drifts 0.03–0.09 Hz rms against 1.4–3.3 Hz hand-held on 2026-09-30, so evidently fixed |
| Sweep, sampling, chirp timing | Short and medium, as on 2026-09-30 | Long, as on 2026-09-30, 256 chirps (400 in one capture) | Short and medium, as on 2026-09-30 |
| TX / RX | TX1 at 0 dB backoff; one capture with no TX enabled; RX gain +3 dB. The sky and run 8TX captures have no calibration record and all TX phases at 0 | TX1, or 8TX coherently phased with the 2026-09-30 calibration; RX gain +3 dB | TX1 at 0 or 10 dB backoff, 8TX coherently phased (medium); RX gain +3 dB |
| Raw data (not in the repo) | `~/Data/carkit/2026-10-01_reflector_lindevi`: 12 placements and 2 empty scenes of 9–10 CPIs, no TX (97 CPIs), sky (67, 59), 5 runs (313–370); a README and photos | `~/Data/carkit/2026-10-01_highway_sandsjobacka`: 4 cases of 152–516 CPIs, about half of each run's CPIs not recorded; photos and a map | `~/Data/carkit/2026-10-02_out_the_window`: 5 cases of 9–10 CPIs |
| Windows in this study | As outdoors | As outdoors | As outdoors |

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

TX power: the host tool sends `Configure_TX_Power` with all four power levels
of the enabled TX at 0 dB back-off from the maximum setting and the default PA
switching slope (user manual Table 48, l2-sp `board.go`). The Aurix firmware
then runs the TX power calibration of power level 1 for each enabled TX at the
start of every run (`Execute_Calibration`, sub-function 0x2d, whose bit 0 is
the TX power calibration; Table 52, l2-sp
`projects/psi/firmware/drivers/radar/RadarRun.c`). The same sub-function also
sets bit 5, which the user manual marks as reserved. Infineon's application's
TX power settings are not recorded, so the two cannot be compared from the
code; nothing in ours suggests less than maximum power.

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
  from 12:53. The board was restarted around 12:32. The field and highway
  captures of 2026-10-01 use the newer build; the window captures of
  2026-10-02 another one, built from a release branch with uncommitted
  changes.

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
by 7–15 dB (median 13 dB in the medium waveform, 11–12 dB in the short). With
the radar held by hand, neither is a finding about the hardware; the
fixed-mount captures of 2026-10-02 settle both (below).

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

**2026-10-02, our firmware, fixed mount** ([window_scene.py](window_scene.py)
and [window_phase.py](window_phase.py) run on this recording; outputs in
`generated/window/2026-10-02/`). Five cases: `medium-0dB`, `medium-10dB`,
`short-0dB` and `short-10dB` with TX1, and `medium-8TX`, coherent with the
calibration. They were meant as the chirp-timing test but repeat the
2026-09-30 timing (4.0 µs pre-payload, 2.0 µs flyback, 83.72 µs wait, 100 µs
PRI), so that test is still to be done. The radar was evidently on a fixed
mount: the strongest returns' common phase drifts 0.03–0.09 Hz rms within a
CPI, against 1.4–3.3 Hz hand-held on 2026-09-30, except in `medium-8TX`
(12 Hz rms), where something moved. No CPI is flagged as interfered.

- 10 dB backoff lowers matched static returns by a median of 9.93 dB in the
  medium waveform (10 returns) and 9.98 dB in the short (14), all within
  8.7–11.1 dB but for one weak medium return near the noise. The datasheet
  allows ±2 dB for a reduction of 6–12 dB at constant junction temperature
  (Table 24). The 7–15 dB of 2026-09-30 came from the hand-held pointing.
- The calibrated 8TX beam adds 17.5 dB at the strongest return (27 m) and
  15.2 dB at 34 m, against 18.1 dB at the beam's peak for eight equal,
  perfectly phased TX; at the other returns, presumably off the beam, it adds
  2–11 dB (median 8.9 dB over all 10).
- δf is 3.09 kHz in the medium waveform and 3.61 kHz in the short (see
  [Window: the MMIC programming sets the error](#window-the-mmic-programming-sets-the-error)).

### Field captures

([field_if.py](field_if.py), [field_level.py](field_level.py).) The README
names the cases `<waveform>-<distance>` for the reflector "stationary at" a
distance, with the short and medium waveforms of 2026-09-30, TX1 unless named
otherwise; `empty-<waveform>` for the scene without the reflector; `notx`, with
no TX enabled (medium waveform); `sky-1tx` and `sky-8tx` pointed at the sky
(the README says medium, the sidecars short); and runs with the reflector
carried towards the radar. The photos show the walk's reflector, 100 mm
triangular trihedral, on a small tripod at about 1 m, with the radar at about
the same height; on the pitch its opening faces the radar. In two photos taken
earlier it stands beside the radar with one plate flat on the tripod head,
which would put the radar in the plane of that plate.

Order, UTC: the empty scenes at 10:38–10:39; at each distance the short and
then the medium waveform, 15–28 s apart, from 10:42 to 10:50; the runs
10:51–10:59; `notx` 11:01; the sky 11:04–11:05; `run-8tx` 11:08.

The reflector is the static peak that rose most over the empty scene. Its
apparent ranges are 3.76, 7.33, 16.03, 34.05, 52.24 and 90.45 m for the
nominal 5–100 m, the same in both waveforms within 0.15 m. The range scale is
right to 0.2 % (range scale, above), so the nominal distances were
indicative. Its level is steady: 0.01–0.16 dB rms from CPI to CPI, as for
fixed mounts, and within −1.5 to +1.0 dB of the RX mean in every channel.
After the 2026-09-30 calibration's RX phases, its per-RX amplitudes fit a
plane wave with coherence 0.98–1.00, so that calibration still holds a day
later. No CPI of the stationary or reference
captures is flagged as interfered.

The runs and the 8TX captures, which have no calibration record and all TX
phases at 0, are not analysed. Hand-carried in the runs, the reflector came
out 11–13 dB below the walk's inbound level at the same ranges, close to the
walk's outbound leg (a one-off check).

### Highway captures

([highway_traffic.py](highway_traffic.py),
[range_time.png](generated/highway/range_time.png).) Four captures with the
long waveform: TX1 (516 CPIs) and 8TX coherent (189, 487 and 152 CPIs; the
last with 400 chirps). About half of each run's CPIs were not recorded; the
CPI indices span 300–979. Vehicles are visible to the end of the straight in
both modes: passes beyond 900 m reach 16–32 dB per RX with TX1 and 15–51 dB
with 8TX. The model without hardware losses gives a 10 dBsm target −7.4 dB per
RX at 1 km with TX1, so those vehicles return 23–39 dB more: trucks' rear
faces at grazing incidence, over asphalt.

Along a pass the SNR hardly changes with range. Fitting SNR ∝ R⁻ⁿ to each
pass gives medians of n = −0.05 (TX1, 6 passes) and 0.12–0.16 (8TX, 21–33
passes per capture), against 4 for a target of fixed RCS in free space. From
a bridge about 7 m above the road (a depression angle of 4.0° at 100 m and
0.4° at 1 km), the depression angle, the vehicle's aspect and the multipath
change with range more than R⁻⁴ does, so these captures say nothing about the
range model.

Other radars interfere: 39 of 516 CPIs with TX1 and 70 of 487 in the busiest
8TX capture are flagged, none in the other two. The steps drop them. A
one-off run of window_phase on the busiest 8TX capture gives δf 0.50 kHz
(p5–p95 0–0.80 kHz) from 17 clean static returns at 35–385 m. That is no
better a bound than the window captures' 0.56 kHz: the bridge moves (common
phase 11.8 Hz rms, up to 193 Hz), which the fit has to absorb.

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
| Model TX / NF | CTRX8188F datasheet headline: 14.5 dBm, NF 10.2 dB (low-noise mode at 10 MHz IF; 10.5 dB at 1 MHz). The walk's RX gain setting has a lower NF ([Loss terms](#loss-terms)) |
| Model antenna | FARAD-IV digitized boresight: 15.05 / 14.98 dBi TX / RX; the datasheet describes these as directivity |
| Model target | Nonfluctuating 10 dBsm at boresight; no straddle or CFAR loss |
| Processing | The walk's Blackman windows (2.37 dB ENBW loss each); fourfold padding leaves at most 0.07 dB scalloping |

The model is [walk_model.py](walk_model.py). Viktor's hand calculation gives
32.63 dB, the same as the model. This reference model has no hardware losses;
[Loss terms](#loss-terms) adds them.

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
| Model with the CARKIT loss terms, before the cover | | 31.10–33.13 dB |

The report's selection keeps CPIs within 6 dB of the local R⁻⁴-corrected
maximum within ±5 m, over 15–51 m; all selected CPIs are inbound. The exact
33 CPIs could not be reproduced without Viktor's code.

### Loss terms

The model above has no hardware losses: the datasheet's TX power and noise
figure act directly on the antenna's directivity. That was the toolbox's
implicit choice when this study started. The toolbox now names each term
between them (`SystemLosses`; catalogue and sources in
[docs/losses.md](../../docs/losses.md)). For CARKIT in the walk
([walk_model.py](walk_model.py),
[summary.json](generated/walk/model/summary.json)):

| Term | The walk | Effect on the model |
|---|---|---:|
| Noise figure | RX gain code 0, +3 dB (CARKIT user manual; CTRX8188F user manual Table 120). At that gain the datasheet gives 9.9 dB at 1 MHz IF and 9.7 dB at 10 MHz, typical; the walk's 15–51 m are at 1.0–3.3 MHz. The model uses the headline 10.2 dB, specified at 0 dB gain | +0.3 to +0.5 dB |
| TX power | TX1 at 0 dB backoff, the maximum setting, for which the datasheet's 14.5 dBm typical holds, as modelled (Table 22) | 0 |
| Feed | CARKIT's PCB carries the package's waveguide ports through to the antenna (quick start guide v17, 2.2): the arrangement for which the datasheet defines its RF reference plane, at the far side of a 1.2 mm reference PCB (datasheet Section 5, Figure 5). Whether CARKIT's PCB matches that reference design is not documented | 0 |
| Antenna | 15 dBi stated as directivity. Radiation efficiency ≥ 90 % (≤ 0.46 dB) and reflection coefficient ≤ −10 dB (mismatch ≤ 0.46 dB) put realized gain 0–0.92 dB below it on each pass (FARAD-IV data sheet) | 0 to −1.83 dB |
| Housing cover | CARKIT's closed housing covers the antenna (quick start guide, 1.3). Its loss is not documented, and the FARAD-IV figures are without a radome. The cover cannot easily be removed, so every CARKIT measurement includes it | not known |
| Straddle | Fourfold padding on both axes: 0.02 dB per axis, the toolbox's mean over target position (`straddle_loss_db`) | −0.05 dB |
| Atmosphere | ITU-R P.676-13 standard atmosphere at 76.37 GHz, 0.35 dB/km (`Atmosphere.itu_p676`), two-way at 15–51 m | −0.01 to −0.04 dB |
| Per-chirp frequency error | 19.0 kHz rms ([The per-chirp frequency error](#the-per-chirp-frequency-error)), at 15–51 m (`coherence_loss_db`) | −0.00 to −0.01 dB |
| Multipath | Not modelled ([Range structure and geometry](#range-structure-and-geometry)) | |

The measurement is scaled to 100 m by R⁻⁴ alone, so the range-dependent terms
apply at the walk's own ranges, where they are negligible. With the other terms
the model is 31.10–33.13 dB before the cover. The headline measurement is then
0.74–2.77 dB above it, and 1.96–3.99 dB with the noise from the far quarter,
which overstates it ([Field captures: two slopes](#field-captures-two-slopes)).
Any loss in the cover adds to both.

Notes on the terms:

- **The antenna's figures are for a bare antenna.** The FARAD-IV data sheet
  (1377.99.0744, PIM-P62799, 2026-01-20) gives its figures for the antenna on
  a PCB without a radome. The CARKIT user manual's patterns peak at about
  15 dB (p. 9), but it does not say whether they are directivity or gain, or
  whether the cover was on.
- **The noise figure follows the RX gain.** The datasheet specifies its "ultra
  low noise operation mode" rows (noise figure and conversion gain) at RX gain
  step +3 dB and its "low noise" rows at 0 dB, with conversion gains 3 dB apart
  (Table 30). The user manual has no other noise-mode setting than the RX gain
  select. We therefore read the modes as gain steps
  ([docs/losses.md](../../docs/losses.md) gives the evidence); Infineon has not
  confirmed this yet. The datasheet gives no minimum noise figure. Its figures are
  specified with all TX off, and with a source reflection of −15 dB or better
  at the reference plane, while the antenna is specified only to −10 dB. Noise
  from the TX that scales with its power would have changed the receiver
  background with 10 dB less TX power, and it did not
  ([The receiver background](#the-receiver-background)). What the antenna's
  reflection costs is not specified.
- **Units differ.** The datasheet's minimum and maximum TX power, 13.0 and
  16.0 dBm (Table 22), are ±1.5 dB around the typical value. Over a ramp in
  76–77 GHz it may vary by up to 1.5 dB, and over temperature by up to 1 dB
  with closed-loop power control (Table 24). The maximum noise figure at the
  walk's gain is 3.0 dB above typical (Table 30). These limits hold over
  junction temperatures from −40 to 135 °C; the datasheet does not state the
  conditions of its typical values. They say how far one unit may be from the
  typical part, not where ours is, so they are not in the model.

The terms widen the gap: only the noise figure acts in the measurement's
favour, while the antenna, the cover and anything not modelled lower the
model. The walk cannot resolve terms of this size. The averaging convention
alone moves the measured value over 32.53–34.49 dB, the noise reference by
1.2 dB, and the reflector's RCS comes from a near-field comparison at 2.5 m.
The same reflector on a tripod in the field captures gives a level 4.4 dB
lower ([The reflector on a tripod](#the-reflector-on-a-tripod)).
A unit with TX power near the datasheet's maximum would also explain up to
1.5 dB. So the terms are taken from their sources, not fitted to the walk. A
reflector on a fixed mount, calibrated against the chamber reflector, would
narrow the measured side. The cover's loss cannot be measured on this unit,
since its cover cannot easily be removed; it remains an unknown loss in every
comparison with the model.

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

### The reflector on a tripod

[field_level.py](field_level.py), [levels.png](generated/field/level/levels.png).
The field captures put the walk's reflector on a tripod at six distances, each
with two waveforms (see [Field captures](#field-captures)). Its zero-Doppler
power per RX, averaged over RX and CPIs in ADC counts squared with
sum-normalized windows, is scaled to 16 m by R⁻⁴ at its apparent range. That
is independent of window and padding, so it compares directly with the walk's
per-RX powers, scaled the same way. Two corrections follow: the receiver's IF
response at the reflector's beat frequency, relative to 2.5 MHz, from the
two-slope ratios ([The receiver background](#the-receiver-background)); and the
reflector's near-field loss ([Reflector](#reflector)).

| Apparent range | Beat, medium / short | Medium: measured → corrected | Short: measured → corrected | Azimuth |
|---:|---|---|---|---:|
| 3.76 m | 0.29 / 0.59 MHz | 21.4 → 26.8 dB | 25.0 → 26.8 dB | −1.5° |
| 7.33 m | 0.57 / 1.14 MHz | 24.3 → 25.9 dB | 25.7 → 25.9 dB | −0.5° |
| 16.0 m | 1.25 / 2.51 MHz | 28.7 → 28.9 dB | 29.0 → 29.1 dB | −1.3° |
| 34.0 m | 2.65 / 5.33 MHz | 29.1 → 29.1 dB | 29.0 → 29.0 dB | +3.6° |
| 52.2 m | 4.07 / 8.17 MHz | 31.1 dB | 29.2 dB | +6.1° |
| 90.4 m | 7.04 / 14.1 MHz | 33.5 dB | 32.9 dB | +9.0° |

dB ADC-count² at 16 m. The IF response is known from 0.29 to 5.3 MHz, where
the octave ratios chain (neighbouring frequencies within 10 % are taken as
equal); it is −5.1 dB at 0.29 MHz, −1.6 dB at 0.57–0.59 MHz and −0.1 dB at
1.1–1.25 MHz. Beyond 5.3 MHz the 4–8 MHz pair is unusable and the 7–14 MHz
pair does not join the chain, so 52 and 90 m stay uncorrected; the 7–14 MHz
ratio puts the response there within about 0.6 dB. The near-field loss is
0.23 dB at 3.76 m and 0.06 dB at 7.3 m.

After correction the two waveforms agree within 0.2 dB at every distance to
34 m. At 16 and 34 m the level is 28.9–29.1 dB; at 3.8 and 7.3 m 2–3 dB lower;
at 52 and 90 m higher, 29.2–33.5 dB, where the ground is seen at 2.2° and 1.3°
and multipath can add. The walk's inbound level also rises with range: 33.3,
34.0 and 35.2 dB in its 15–27, 27–38 and 38–52 m bands
([Range structure and geometry](#range-structure-and-geometry)).

**Against the walk.** At 15–27 m the walk gives 33.3 ± 0.6 dB (14 CPIs). The
tripod session is 4.3–4.5 dB lower at 16 and 34 m. The receiver is not the
difference: its noise density at 18–24 MHz is 18.59 dB ADC-count² per sample
with the TX off in the field, and 18.47 dB in the walk's far quarter, after
each dataset's windows are taken out. Against the model without hardware
losses, with the walking reflector's 11.27 dBsm and the noise at the
reflector's beat frequency, the tripod session is 3.3–4.3 dB low at 16 and
34 m (2.8–3.1 dB with the noise at 18–24 MHz), and 1.0–1.3 dB high at 90 m.

What could cause 4.4 dB:

- **Azimuth: ruled out.** From the per-RX phases, the reflector was within
  −1.5 to +3.6° of boresight to 34 m (two-way pattern loss 0.1 dB at most in
  the FARAD-IV preset) and at +6° and +9° at 52 and 90 m (0.5 dB at most).
- **The radar's elevation pointing: possible.** The FARAD-IV preset's two-way
  elevation pattern is 3.8 dB down at 6° and 6.8 dB at 8°, so a tilt of 6–7°
  would explain it. The RX array is horizontal, so the data cannot show it.
- **The reflector's aim or state: possible.** On the pitch its opening faces
  the radar (photo). A trihedral's response falls only slowly off its axis: a
  one-off geometric-optics ray trace of a triangular trihedral gives 0.7, 1.8
  and 3.3 dB at 10, 15 and 20° off the axis, and no triple-bounce return at
  all for a radar in the plane of one plate. Plates glued onto absorber may
  have moved since the walk.
- **TX power as each firmware programs it: possible.** Ours programs the
  maximum and calibrates it at every run ([Firmware](#firmware));
  Infineon's settings are not recorded.

The walk's averaging and selection conventions move its value by at most
2 dB ([Method](#method)), and its short-range points have a 0.6 dB spread, so
they do not explain it either. A session with both firmwares on the same
fixed setup, with the radar tilted in steps, settles the first and last
candidates (see the open questions).

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
On the walk itself (15–51 m) the near-field loss is below 0.05 dB; in the
field captures it is 0.23 dB at 3.76 m and 0.06 dB at 7.3 m
(`field_common.near_field_loss_db`, which reproduces the two lab values above
to 0.01 dB).

The field captures use the same walking reflector (photos). The scripts keep
11.27 dBsm (`walk_common.py`). With 11.5 dBsm, the walk's +1.2 dB over the
model becomes +0.9 dB. That is within the stated uncertainty, and the
correction is not applied yet. A side-by-side comparison at 10 m or more would
settle both this and how much the two home-made reflectors differ (see the
open questions).

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

Two explanations were open. If it is IF gain shape, signal and noise are
shaped alike, and the SNR at a given range does not depend on the beat
frequency: the local reference is right (+1.2 dB). If it is receiver noise
that rises at low IF, a target's SNR improves as its beat frequency rises,
and the far quarter is the better reference for high IF (+2.4 dB). The
datasheet NF changes only 0.3 dB between 1 and 10 MHz. A TX-off capture cannot
decide, since both remain with TX off; what decides is a signal of known level
at different beat frequencies. The field captures provide it
([Field captures: two slopes](#field-captures-two-slopes)): between 1.25 and
5.3 MHz the excess is noise, and from 7 to 14 MHz it is not, within the
precision available. For the walk this gives +1.2 dB at its own beat
frequencies and about +1.7 dB for a target at 5–14 MHz.

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

**Field captures: the background.** The same estimator on the field
captures ([field_if.py](field_if.py),
[if_test.png](generated/field/if/if_test.png), left), relative to 18–24 MHz,
and the level there per cell:

| Capture | TX | 0.7 MHz | 1 MHz | 2 MHz | 3.3 MHz | 6.6 MHz | 13 MHz | 18–24 MHz [dB ADC-count²/cell] |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| notx | none | 1.13 | 1.19 | 1.00 | 0.74 | 0.43 | 0.13 | −30.83 |
| empty-medium | TX1 | 1.17 | 1.24 | 1.07 | 0.77 | 0.43 | 0.15 | −30.94 |
| empty-short | TX1 | 1.15 | 1.23 | 0.94 | 0.67 | 0.39 | 0.09 | −30.90 |
| sky-1tx | TX1 | 1.26 | 1.34 | 1.04 | 0.73 | 0.43 | 0.10 | −31.17 |
| sky-8tx | 8TX, uncalibrated | 1.59 | 1.63 | 1.15 | 0.84 | 0.47 | 0.13 | −30.97 |

With no TX at all, the background has the same shape and level as with TX1,
within 0.1 dB, and the window captures' shape. With all eight TX on, pointed
at the sky, it rises 0.3–0.5 dB below 1 MHz, and a component common to the RX
channels lifts the total remote-Doppler power 0.27 dB above the independent
floor at 1–10 MHz (0.03 dB or less in the others), as in the window capture
without scene.

### Field captures: two slopes

([field_if.py](field_if.py), [if_test.png](generated/field/if/if_test.png),
right.) The short ramp sweeps twice the medium ramp's bandwidth in the same
10.24 µs at the same 50 MS/s. Its samples 129–383 sweep the medium ramp's
76.94–77.06 GHz, at twice the slope. In those samples the reflector is in the
same RF band and range cell, behind the same multipath, at twice the beat
frequency. The two captures at each distance were taken 15–28 s apart with
nothing touched, so the change of the reflector's zero-Doppler power from the
medium ramp to the short ramp's samples, dS, is the change of the IF response
over that octave. The change of the TX-off background over the same octave,
dN, holds only the receiver. Their difference T = dS − dN is the SNR change
for equal processing: 0 if the background's shape is gain shape, −dN if its
excess is noise entering before the high-pass filter. A synthetic check
([test_field_common.py](test_field_common.py)) recovers an imposed gain ratio
to 0.05 dB with 255 against 512 samples.

| Distance | f → 2f | dS | dN | T | Spread over RX | Spread over CPIs |
|---:|---|---:|---:|---:|---:|---:|
| 3.8 m | 0.29 → 0.59 MHz | +3.59 dB | +2.22 dB | +1.37 dB | 0.37 dB | 0.15 dB |
| 7.3 m | 0.57 → 1.15 MHz | +1.41 dB | +0.35 dB | +1.06 dB | 0.20 dB | 0.03 dB |
| 16 m | 1.25 → 2.51 MHz | +0.14 dB | −0.33 dB | **+0.47 dB** | 0.10 dB | 0.01 dB |
| 34 m | 2.65 → 5.33 MHz | +0.00 dB | −0.36 dB | **+0.36 dB** | 0.44 dB | 0.08 dB |
| 52 m | 4.07 → 8.17 MHz | −1.76 dB | −0.34 dB | (−1.42 dB) | 1.43 dB | 0.14 dB |
| 90 m | 7.04 → 14.1 MHz | −0.63 dB | −0.29 dB | −0.34 dB | 0.64 dB | 0.20 dB |

The spread over RX is the standard deviation of the per-RX dS. At 52 m it is
1.4 dB: something in the scene changed between the two captures, which a CPI
spread of 0.14 dB within each rules out for the reflector itself, and the pair
is not used. The full short ramp gives dS within 0.16 dB of its 255 samples,
so the band difference does not matter.

- **1.25–5.3 MHz:** T sums to +0.83 dB over the two clean pairs; noise
  predicts +0.68 dB, gain shape 0. Here the background's excess is noise.
- **7–14 MHz:** T is −0.34 ± 0.23 dB (spread over RX / √8), against
  +0.29 dB for noise and 0 for gain shape. The reflector's power falls 0.6 dB
  over this octave, more than the background does. Within the precision
  available, the background's fall here is gain shape, or noise added after
  a filter that also cuts the signal.
- **Below 1 MHz:** the high-pass filter cuts the reflector by 1.4–3.6 dB per
  octave but the background by only 0.35–2.2 dB, so T is about +1 dB. Part of
  the background there is not shaped like a signal.

From 1.25 to 14 MHz, T sums to +0.49 dB over the three usable pairs (+0.98 dB
for noise). So a target at 5–14 MHz gets up to about 0.5 dB more SNR than one
at 1.25 MHz. Below 1 MHz, a target at 0.3 MHz has about 2.4 dB less SNR,
relative to one at 1.15 MHz, than the background's shape alone would suggest
(T summed over the two lowest pairs). For the walk (1.0–3.3 MHz) the local
reference is the SNR the reflector actually had; for long-range targets the
model is about 0.5 dB further below the measurement, not the 1.2 dB the far
quarter suggests.

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
| Window 08-27, mode 1 | Infineon | 3.54 µs; 0.12 µs | 16.71 MHz/µs | 29.8 kHz | 0.5–36 kHz | Shared by clean static returns, 21–175 m |
| Window 08-27, mode 0 | Infineon | 4.2 µs; 0.12 µs | 8.35 MHz/µs | 21.7 kHz | 0.5–34 kHz | Shared by static returns, 70–280 m (only one clean) |
| Window 09-30, medium | Ours | 4.0 µs; 85.7 µs | 11.67 MHz/µs | 3.45 kHz | 0.5–5 kHz | Shared by clean static returns, 14–267 m |
| Window 09-30, short | Ours | 4.0 µs; 85.7 µs | 23.46 MHz/µs | 3.53 kHz | 0.5–5 kHz | Shared by clean static returns, 24–139 m |
| Window 10-02, medium | Ours | Same | 11.67 MHz/µs | 3.09 kHz | 0.5–5 kHz | Same, fixed mount |
| Window 10-02, short | Ours | Same | 23.46 MHz/µs | 3.61 kHz | 0.5–5 kHz | Same, fixed mount |
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
| medium-8TX-0dB-highway | 8 of 16, 14–217 m | 26 | 2.63 kHz (2.30–2.90); all returns 3.31 kHz | 0 |
| short-1TX-0dB | 3, 28–110 m | 2 | 3.0 kHz (2.1–3.8), pair mean | |
| short-8TX-0dB | 10, 24–129 m | 37 | 4.11 kHz (3.91–4.28) | 0 |
| short-8TX-0dB-2 | 13 of 24, 31–139 m | 63 | 3.29 kHz (3.18–3.50) | 6 mrad |
| long-1TX-0dB | 5, 14–273 m | 8 | ≤ 0.56 kHz (p95) | |
| Both 10 dB backoff cases | none above 8 dB per chirp | | | |
| **medium, pooled** | | 246 | **3.45 kHz (3.39–3.50)** | |
| **short, pooled** | | 102 | **3.53 kHz (3.43–3.65)** | |
| infineon-mode1 | 7 of 9, 21–175 m | 20 | **29.8 kHz (29.5–30.1)** | 0 |
| infineon-mode0 | 1 of 7 | 20, all returns | **21.7 kHz (20.8–22.4)**, pair mean | |
| 2026-10-02, medium (3 cases) | 5–13 per case, 27–284 m | 128 | **3.09 kHz (3.01–3.18)** | |
| 2026-10-02, short (2 cases) | 5–12 per case, 24–129 m | 67 | **3.61 kHz (3.49–3.70)** | |

CPIs that window_scene.py flags as interfered are dropped: 3 of 10 in
medium-8TX-0dB-highway, 8 of 42 in Infineon mode 0 and 15 of 89 in mode 1,
raised by 1.1–3.0 dB over all ranges (the other CPIs within 0.56 dB at the
90th percentile). Keeping them changes the pooled and Infineon values by at
most 0.5 kHz (earlier 3.47, 30.0 and 21.2 kHz). The 2026-10-02 captures, with
the radar on a fixed mount, have none.

The captures spread over 3.1–4.1 kHz, more than the bootstrap intervals, since
scene and returns differ between them. 1TX and 8TX coherent agree within that
spread, as a shared LO requires; independent errors in the eight TX paths
would be averaged down by the coherent sum. The highway capture is dominated
by traffic (8 of 16 returns fail the clean test) and is not used for
conclusions. In Infineon mode 0 all returns but one fail the clean test at the
coarser 1.75 m cells; its pair mean over all returns stands in. Its pairs give
15–30 kHz, 21–29 kHz where the two returns correlate well. The common phase of
6 mrad rms above 500 Hz in one of the late captures (1.8 µm) fits the
hand-held radar; it does not enter δf. On the fixed mount of 2026-10-02 the
fit finds none.

**Against the CW table.** The prediction for these waveforms (as outdoors,
now `carkit_common.per_chirp_frequency_psd`) is 2.69–2.71 kHz typical with the
76–77 GHz table and 3.35–3.38 kHz with the 77–81 GHz table, and 4.78–4.82 and
5.88–5.93 kHz maximum. Our sweeps are centred at 77.00 GHz, the boundary
between the tables. The measured 3.45–3.53 kHz is 2.2–2.4 dB above the
lower-band typical, 0.3–0.5 dB above the upper-band typical and 2.7–4.6 dB
below the maxima. For the Infineon recording (76.2–76.7 GHz, lower table) the
typical is 2.8 kHz, so 29.8 kHz is 20.4 dB above it and 21.7 kHz 17.8 dB.

**Spectrum.** Our firmware's δf PSD is flat at 30.9–32.4 dB Hz²/Hz over
0.5–5 kHz; the typical tables give a flat 29.0 and 31.0 dB Hz²/Hz. Infineon's
mode 1 rises from 23.4 dB Hz²/Hz at 0.5–2 kHz to 42.7 dB Hz²/Hz at 20–36 kHz,
against a flat 20.6 dB Hz²/Hz from the typical table at its 71.6 kHz PRF:
3 dB above at the lowest slow-time frequencies, 22 dB at the highest. An error
concentrated near PRF/2 alternates from chirp to chirp, as it would if the
synthesizer had not settled from the previous ramp when the next payload
begins. That is a working hypothesis, not tested.

**Delay law.** Medium, pooled, by the pair's farther return, with each
capture's common phase removed:

| Farther return | Pairs | δf rms |
|---|---:|---:|
| 10–60 m | 5 | 2.69 kHz |
| 60–130 m | 66 | 3.51 kHz |
| 130–200 m | 63 | 3.56 kHz |
| 200–290 m | 112 | 3.42 kHz |

δf is the same within ±0.1 kHz from 60 to 290 m, τ up to 1.9 µs. With a free
exponent γ = +0.10 (0.07–0.14), phase power goes as τ^2.2 rather than τ². The
CW model's own saturation at 270 m is 0.5 dB for a return's own δf; for pairs
with one far return it is about half of that, in line with the 0.35 dB drop
from 130–200 to 200–290 m. Infineon's mode 1 gives γ = +0.08 (0.072–0.096) over
21–175 m. Where the returns span less than a decade of delay, as in the short
waveform (γ = +0.27, 0.09–0.46), the exponent trades off against the common
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
  pre-payload. Their δf falls as the pre-payload grows: 30 and 22 kHz at 3.54
  and 4.2 µs, in alternating frames of one recording, and 14–19 kHz at
  5.54 µs, in other captures with other sweeps.
- Ours has 2 µs flyback, 84 µs wait (43 µs in the long waveform) and 4.0 µs
  pre-payload, and gives 3.1–3.6 kHz.

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
Here it holds to 270 m. That is about 0.1 dB of coherent loss (the toolbox's
`SystemLosses.chirp_frequency_error_rms_hz` term, which uses this law), and in
fact less, since for phase noise the delay-squared law is the small-fτ limit of
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

Status 2026-10-02. Three lists: what we are waiting for, the open questions,
and the measurements that would close them.

### Waiting for

1. **Chirp-timing captures** (Viktor). The 2026-10-02 window captures meant for
   this kept the old timing, by a misunderstanding. What is needed is in
   measurement 2 below.
2. **Viktor's answers, forwarded 2026-10-02:**
   - Field captures: was the radar level in elevation, and was the reflector
     oriented as in the photo on the pitch at every distance? How were the
     distances set? (They were indicative: apparent 3.8–90.4 m for nominal
     5–100 m.)
   - Window, 2026-10-02: how was the radar mounted, and did anything move
     during `medium-8TX` (12 Hz rms drift, against below 0.1 Hz in the others)?
3. **Not yet asked:**
   - Why the field captures' 8TX runs have no calibration record and all TX
     phases at 0, when the highway captures earlier that day have the
     calibration.
   - Our firmware's run-start `Execute_Calibration` (sub-function 0x2d) sets
     bit 5, which the user manual marks as reserved.
4. **Still open from 2026-10-01** (asked, not answered):
   - What `long-8TX-0dB` of 2026-09-30 was: another firmware build
     (2026-09-24), TX1 only, no scene beyond 10 m.
   - How our firmware's MMIC programming differs from Infineon's apart from
     the ramp timing (DPLL and loop settings, ramp and flyback options), and
     which MMIC RAM firmware Infineon's CARKIT application loads.
   - Whether the MMIC configuration is fully determined by the sidecar
     together with the host code's version (not recorded; the RX noise mode
     is in neither; the firmware version ends in `-dirty`).
   - Where the ramp timing constants in `waveform.go` come from, and whether
     Viktor's version makes them configurable.
   - When we switched to our firmware; whether the walk and outdoor captures
     used Infineon's application with Viktor's host tool; which firmware the
     report's lab measurements used.
5. **Infineon,** asked by email on 2026-10-02: whether the datasheet's
   ultra-low-noise rows are the +3 dB RX gain setting
   ([Loss terms](#loss-terms)).
6. **Slack:** a figure for the housing cover's loss, if anyone has one.

Answered since 2026-10-01: 10 dB backoff gives 10.0 dB, and the calibrated
8TX beam 17.5 of an ideal 18.1 dB (window, 2026-10-02); the reflector in the
field is the walk's (photos); the field's low-IF background is the receiver's
(TX off); the cover was on in every measurement, since CARKIT is a closed unit
whose cover cannot easily be removed; the radar on the bridge was about 7 m
above the road (deck height from public sources, ±0.5 m).

### Open questions

1. **Why the two reflector sessions differ by 4.4 dB**
   ([The reflector on a tripod](#the-reflector-on-a-tripod)). Candidates: the
   radar's elevation pointing, the reflector's aim or state, the TX power as
   each firmware programs it. Until it is settled, the measurements place
   CARKIT within −4 to +2 dB of the model. Viktor's answer on elevation may
   narrow it; measurement 1 decides it.
2. **Which part of the chirp timing sets δf** (flyback, wait, or another
   synthesizer setting), and why Infineon's δf spectrum rises towards PRF/2.
   Measurement 2.
3. **The receiver's IF response above 5 MHz.** One pair, less clean, says the
   background's fall from 7 to 14 MHz is gain shape, not noise. It changes a
   long-range budget by at most about 0.5 dB. Measurement 3.
4. **The housing cover's loss.** The same in every measurement and not
   measurable on this unit. Unless a figure turns up (item 6), it stays an
   unknown loss in every comparison with the model.
5. **The walking reflector's RCS** (11.27 or 11.5 dBsm) and how the two
   home-made reflectors differ. Measurement 1.
6. **Minor:** a component common to the RX channels in the remote-Doppler
   background with nothing in view: 2.2 dB in `long-8TX-0dB` (which ran TX1)
   and 0.27 dB in `sky-8tx` (all eight TX) at 1–10 MHz, probably the skirt of
   the strong return within 10 m.

### Measurements to close them, in order of priority

1. **Reflector and firmware session** (questions 1 and 5). One fixed radar
   mount, levelled, and a marked spot at 10–20 m on open ground with nothing
   moving nearby; heights, distances (tape or laser), photos and the capture
   order logged next to the data.
   - The chamber reflector (Microwave Factory, 10 dBsm specified) and both
     home-made ones in turn on the same mount, each at a few roll and tilt
     settings, with the empty mount captured for coherent subtraction.
   - Without touching radar or reflector: the same captures with Infineon's
     firmware and with ours, TX1, waveforms as close as the two allow. This
     measures any TX power difference directly.
   - A tilt scan of the radar in elevation, about −10 to +10° in 2° steps with
     the reflector fixed: finds the radar's boresight and checks the
     FARAD-IV elevation pattern.
2. **Chirp-timing test** (question 2). The window scene from a fixed mount,
   TX1, the medium waveform, alternating captures of ten CPIs in one session.
   With Infineon's application, lengthen the flyback to the datasheet's 1 µs,
   then also the wait. With ours, a flyback and wait below about 1 µs need the
   constants in `waveform.go` changed; shortening the PRI alone keeps both
   beyond 1 µs and should leave δf at about 3.5 kHz. Either way this decides
   what the Psi waveform must respect.
3. **Two slopes at higher IF** (question 3). The field method with the
   reflector at 60–150 m, or the long and medium waveforms at one distance:
   fixed mounts, several placements, nobody moving in the scene between the
   two captures of a pair (at 52 m in the field captures something did).
4. **Selected reflector distances at another height,** to separate multipath
   from the rise of level with range seen in both sessions.
5. **Bench measurement of the CW phase noise** at the TX port, only if
   measurement 2 leaves an excess unexplained.

New captures should have the radar and any reflector on fixed mounts, with the
setup logged next to the raw data, and away from traffic where interference
would cost CPIs.

**Open in the analysis:** none beyond the questions above. The runs and the
uncalibrated 8TX captures of the field session are not analysed.

## Reproducing

```sh
make study_260911_carkit_validation      # about 7 minutes
make study_260911_carkit_validation CARKIT_WALK_DATA=/path CARKIT_OUTDOOR_DATA=/path \
    CARKIT_WINDOW_DATA=/path CARKIT_WINDOW_INFINEON_DATA=/path \
    CARKIT_WINDOW_1002_DATA=/path CARKIT_FIELD_DATA=/path CARKIT_HIGHWAY_DATA=/path
```

This runs the study's synthetic tests, then the walk, outdoor, window, field
and highway steps in order, and finally the window steps on the 2026-10-02
recording (with its own level pairs, into `generated/window/2026-10-02/`). Each step writes `summary.json` (and, for some walk steps, a
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
| [walk_model.py](walk_model.py) | Model, CARKIT loss terms and comparison |
| [outdoor_common.py](outdoor_common.py) | Outdoor capture loading and checks, Blackman–Harris/Hann spectra, cases |
| [outdoor_scene.py](outdoor_scene.py) | Capture validation, reflector and scene returns, levels, RX coherence, window check |
| [outdoor_phase.py](outdoor_phase.py) | Per-return phase and amplitude spectra, common δf, cross-return correlation, drift |
| [outdoor_model.py](outdoor_model.py) | CW datasheet predictions of the per-chirp δf and the remote-Doppler range cut |
| [window_convert_infineon.m](window_convert_infineon.m) | One-time MATLAB conversion of the 2026-08-27 recording (l2-sp CARKIT decoder) |
| [window_common.py](window_common.py) | Loading and checks for our firmware's format (any recording) and the converted Infineon recording, TX/DDMA configuration, case discovery, static peaks |
| [window_scene.py](window_scene.py) | Checksums, ADC levels, static profiles, channel-independent background, interference CPIs, matched levels (`--level-pairs`), drift |
| [window_phase.py](window_phase.py) | Per-chirp δf from clean static returns (interfered CPIs dropped), delay law, common phase, CW prediction, slow-time spectra |
| [window_range_scale.py](window_range_scale.py) | Range scale from moving vehicles: apparent range change against Doppler-integrated distance |
| [field_common.py](field_common.py) | Field capture loading, zero-Doppler tone estimator, reflector search, matching samples of two sweeps, near-field loss, azimuth, interference levels, reference model |
| [field_if.py](field_if.py) | Receiver backgrounds (TX off, empty scene, sky) and the two-slope IF test at the reflector |
| [field_level.py](field_level.py) | Reflector levels with IF and near-field corrections, azimuth, comparison with the walk and the model |
| [highway_traffic.py](highway_traffic.py) | Moving-target range–time maps, interference CPIs, vehicle passes and their range exponents |
| [test_carkit_common.py](test_carkit_common.py) | Synthetic checks of the normalizations and estimators |
| [test_field_common.py](test_field_common.py) | Synthetic checks of the field estimators (two-slope ratio, matching samples, near-field loss, azimuth, interference flags) |
