# CARKIT validation: range model and phase noise

<!-- Figures linked from these notes are tracked through the .gitignore in this
folder, since they cannot be regenerated without the raw data. When adding or
removing a figure link, update that list. -->

The analysis behind the study's report, [README.md](README.md), which gives the
results and what follows from them. These notes hold the detail:

- [Measurements](#measurements): what was captured, when, with which firmware
  and how the radar and reflectors were mounted.
- [Sensitivity against the model](#sensitivity-against-the-model): the radar
  equation against the reference reflector in the chamber and the home-made
  reflector carried and on a tripod, the loss terms, what a reflector's aim
  costs and what its size does at short range.
- [The receiver background](#the-receiver-background): its rise towards low
  IF, whether that is noise or the IF gain's shape, and the high-pass filter.
- [The per-chirp frequency error](#the-per-chirp-frequency-error): the LO's
  chirp-to-chirp error, its level against the datasheet and what sets it.
- [A strong return's phase-noise skirt](#a-strong-returns-phase-noise-skirt):
  how a strong return raises the background at all ranges, against the
  datasheet, and what that does to coherent channel summation in a chamber.
- [Scale, gain and interference](#scale-gain-and-interference): the range
  scale, TX backoff, the eight-TX beam, the channels' calibration and delays,
  and interference from other radars.
- [Open questions and next measurements](#open-questions-and-next-measurements):
  what is open, which measurements would close it, and what the firmware, host
  tool and capture format might change.
- [Reproducing](#reproducing): commands, raw data and scripts.

## Measurements

Ten sets of captures, all with our single CARKIT unit. The names in the first
column are used in the rest of these notes; the walk is the reflector carried
towards the radar and back, the field captures' placements the reflector on a
tripod and their runs the later carried runs.

| Name | Date | Firmware | What was captured | Used for |
|---|---|---|---|---|
| Walk | 2026-09-11 | Infineon's | A corner reflector carried out to about 50 m and back; radar on a tripod | Sensitivity against the model; receiver background; per-chirp error from the pedestal and passing vehicles |
| Outdoor captures | 2026-09-22 | Infineon's | A reflector at nominal 5 and 10 m with two sweeps; radar and reflector hand-held | Per-chirp error: pure phase, one δf at every return, against the CW datasheet |
| Window, 2026-08-27 | 2026-08-27 | Infineon's | The static scene out of the office window to about 500 m, eight TX in DDMA | Per-chirp error with Infineon's chirp timing |
| Window, 2026-09-30 | 2026-09-30 | Ours | The same scene with three waveforms, TX1 and the eight-TX beam; radar hand-held | Per-chirp error with our firmware and long gaps between chirps, its delay law and the payload length; receiver background; range scale |
| Window, 2026-10-02 | 2026-10-02 | Ours | The same scene from a fixed mount | TX backoff and the eight-TX beam; per-chirp error on a fixed mount |
| Window, 2026-10-06 | 2026-10-06 | Ours | The same scene from a fixed mount with ten chirp timings | Per-chirp error against the chirp timing |
| Field captures | 2026-10-01 | Ours | The walk's reflector on a tripod at six distances, two chirp slopes each, then carried towards the radar in five runs; TX off; the sky | Sensitivity with the reflector on a tripod; the carried reflector against it; receiver background with TX off; noise or gain shape |
| Highway captures | 2026-10-01 | Ours | Traffic seen from a bridge over the E6, to 1.2 km | Interference; vehicles to 1.2 km (no check of the range model) |
| Chamber, 2026-09-29 | 2026-09-29 | Ours | Our host tool's calibration routine in the measurement chamber: the 10 dBsm reference reflector at about 2.5 m, with all eight TX in DDMA, TX1 alone, and the calibrated eight-TX beam; 20 dB TX backoff, RX gain 0 dB | Receiver noise at the 0 dB gain step; a strong return's phase-noise skirt and coherent channel summation against it; TX powers, the eight-TX beam, calibration and channel delays (no absolute check: the backoff is outside the chip's specified range) |
| Chamber, 2026-10-09 | 2026-10-09 | Ours | The same reflector at about 2.2 m: TX1 alone at RX gain +3 dB, at 0 and 10 dB backoff and with a steep chirp; TX off; the calibration routine at 10 dB backoff | The absolute check; the backoff step and the high-pass filter measured on the reflector; receiver noise; the skirt, TX powers, beam and calibration again |

Besides the captures, these notes use two inputs:

| Input | Notes |
|---|---|
| [CARKIT report.pdf](inputs/CARKIT%20report.pdf) | Viktor's report of 2026-09-22, 17 pages: the walk, and lab measurements of the TX powers, the channels' calibration phases and the two reflectors. These notes cite it for the lab measurements; their own analysis of the walk replaces the report's |
| [rcs-comparison.png](inputs/rcs-comparison.png), [reflectors-angle-aligned.png](inputs/reflectors-angle-aligned.png) | Viktor's figures of the lab comparison of the walking reflector with the chamber reflector |

What was posted outside the repository is in [deliverables/](deliverables/):
the walk's results on 2026-09-29, whose paragraph on the Doppler pedestal held
only for Infineon's chirp timing, and the report on 2026-10-09.

### Capture parameters

| | Walk | Outdoor captures | Window, 2026-08-27 | Window, 2026-09-30 |
|---|---|---|---|---|
| Date | 2026-09-11 | 2026-09-22 | 2026-08-27 | 2026-09-30 |
| Aurix firmware | Infineon's CARKIT application: Infineon's configuration format (`config.bin`, saved 2026-09-09), recorded before our firmware supported CARKIT ([Firmware](#firmware)) | Infineon's CARKIT application: imported from a legacy CARKIT recording, per its sidecars | Infineon's CARKIT application, recorded with RadarGUI | Ours (`archive/remove-lannik-embedded-276-g66e0e0dc-dirty`; one capture `archive/remove-lannik-embedded-220-gde2d009b`) |
| MMIC RAM firmware | Not recorded | Not recorded | Not recorded | Infineon's `8188_release_1.0.0_rc3` (revision 2836676, from Strata 3.6.0) |
| Scene | Hallesaker; reflector carried out to about 50 m and back | Outdoors; reflector at nominal 5 and 10 m | Office window; the same far returns as on 2026-09-30 | Office window over the E6 towards an urban area; static returns to about 500 m, traffic |
| Mounting | Radar on a tripod; reflector hand-carried | Viktor held the radar, Haik held the reflector (all tripods were in use) | Not recorded | Viktor held the radar out through the open window (the bracket was away) |
| Sweep | 100.78 MHz sampled, 9.84 MHz/µs, centre 76.374 GHz | 399.6 MHz at 39.02 MHz/µs (77.80–78.20 GHz) and 800.4 MHz at 78.16 MHz/µs (77.60–78.40 GHz) | Two modes, alternating: 85.5 MHz at 8.35 MHz/µs and 171 MHz at 16.7 MHz/µs, from 76.20 GHz, carrier stepped 302 kHz per chirp | Short 240 MHz at 23.5 MHz/µs, medium 120 MHz at 11.7 MHz/µs, long 122 MHz at 2.98 MHz/µs, all centred at 77.00 GHz |
| Sampling | Real, 50 MS/s, 512 samples in a 10.24 µs payload, 1024 chirps | Same | Same | Short and medium: 512 samples in 10.24 µs, 512 chirps. Long: 2048 samples in 40.96 µs, 256 chirps |
| Chirp timing: PRI; pre-payload; flyback + wait | 15.96 µs; 5.54 µs; 60 + 60 ns | Same | 14.62 and 13.96 µs; 4.2 and 3.54 µs; 60 + 60 ns | 100 µs (long 90 µs); 4.0 µs; 2 µs + 83.7 µs (long 43 µs) |
| TX / RX high-pass | TX1; high-pass code 0 | TX1 at 0 dB backoff; high-pass code 0 | 8TX DDMA (8 of 16 slots) at 0 dB backoff; high-pass code 4 | TX1 or 8TX coherently phased, 0 or 10 dB backoff; high-pass 300 kHz (in the host code, not the sidecar) |
| RX gain step (metadata) and typical noise figure at 10 / 1 MHz IF | +3 dB: gain code 0 for all receivers of the recorded mode (`provenance/configuration.json`); 9.7 / 9.9 dB | +3 dB: `gain_code` 0, `gain_db` 3.0 per RX (frame sidecars); 9.7 / 9.9 dB | 0 dB, the chip's default: `gainSelection` 1 (`rx_config` in the converted sidecars); 10.2 / 10.5 dB. The receiver noise at the ADC does not fit it ([Out-of-window captures](#out-of-window-captures)) | +3 dB: `rx_gain_db` 3 (sidecars); 9.7 / 9.9 dB |
| Windows in this study | Periodic Blackman on both axes, fourfold padding, as in Viktor's processing | Periodic Blackman–Harris in range (also for per-chirp amplitudes), periodic Hann in Doppler, no padding | As outdoors | As outdoors |

| | Field captures | Highway captures | Window, 2026-10-02 | Window, 2026-10-06 |
|---|---|---|---|---|
| Date | 2026-10-01, 10:38–11:08 UTC | 2026-10-01, 09:57–10:05 UTC | 2026-10-02, 10:17–10:21 UTC | 2026-10-06, 13:09–13:21 UTC |
| Aurix firmware | Ours (`archive/remove-lannik-embedded-276-g66e0e0dc-dirty`, as on 2026-09-30 from 12:53) | Same | Ours (`release/mifu2025-rc1_20260930-52-g6b9c8871-dirty`) | Ours (`release/mifu2025-rc1_20260930-62-g1115e763`, without uncommitted changes); the host tool that set the timing was modified locally and its version is not recorded ([Firmware](#firmware)) |
| MMIC RAM firmware | Revision 2836676, as on 2026-09-30 | Same | Same | Same |
| Scene | Lindevi, a grass football pitch with about 100 m to its end; goals, buildings, trees and power lines in view (photos); reflector at nominal 5, 10, 20, 40, 60 and 100 m | A bridge over the E6 at Sandsjöbacka, pointed along a straight stretch of about 1.2 km; traffic | Office window, as on 2026-09-30 | Office window, pointed differently from 2026-09-30: a return at 27 m, 36 dB per chirp, dominates |
| Mounting | Radar on a tripod; the walk's reflector on a small tripod at about 1 m, about the radar's height (photos) | Radar on a tripod on the bridge (photos), about 7 m above the road: the deck about 6 m (±0.5 m; public sources found by a web search, not measured) and the radar about 1 m above it | Not recorded; the scene's phase drifts 0.03–0.09 Hz rms against 1.4–3.3 Hz hand-held on 2026-09-30, so evidently fixed | Not recorded; evidently fixed: the strongest returns stay within 0.5 dB of the first capture and the scene's phase drifts 0.07–0.6 Hz rms (3.4 Hz in one case) |
| Sweep, sampling, chirp timing | Short and medium, as on 2026-09-30 | Long, as on 2026-09-30, 256 chirps (400 in one capture) | Short and medium, as on 2026-09-30 | Medium sweep and sampling, as on 2026-09-30; ten chirp timings: PRI 25.5–100 µs, pre-payload 0.02–6 µs, flyback 0.02–2 µs, wait 8.2–83.7 µs ([Window: the chirp timing sets the error](#window-the-chirp-timing-sets-the-error)) |
| TX | TX1 at 0 dB backoff; one capture with no TX enabled. The sky and run 8TX captures have no calibration record and all TX phases at 0 | TX1, or 8TX coherently phased with the 2026-09-30 calibration | TX1 at 0 or 10 dB backoff, 8TX coherently phased (medium) | TX1 at 0 dB backoff |
| RX gain step (metadata) and typical noise figure at 10 / 1 MHz IF | +3 dB: `rx_gain_db` 3 (sidecars); 9.7 / 9.9 dB | Same | Same | Same |
| Windows in this study | As outdoors | As outdoors | As outdoors | As outdoors |

| | Chamber captures |
|---|---|
| Date | 2026-09-29, 09:28:16–09:28:32 UTC |
| Aurix firmware | Ours (`archive/remove-lannik-embedded-220-gde2d009b`, the build of `long-8TX-0dB` on 2026-09-30) |
| MMIC RAM firmware | Revision 2836676, as on 2026-09-30 |
| Scene | The measurement chamber; the 10 dBsm reference reflector (Microwave Factory MTR76P10-T5DW-100) at an apparent 2.46 m. A second return, 15 dB weaker, at 4.82 m, close to twice that: the double bounce between the reflector and the radar's front |
| Mounting | The chamber's fixed mounts: the reflector's level varies 0.002–0.008 dB rms from CPI to CPI, its phase by 0.6–1.4° within a case |
| Sweep, sampling, chirp timing | 900 MHz at 10.99 MHz/µs, 76.55–77.45 GHz; real, 25 MS/s, 2048 samples in an 81.92 µs payload, 256 chirps; PRI 500 µs; 4.0 µs pre-payload; 2 µs flyback + 412 µs wait. The reflector's beat frequency is 181 kHz, below the high-pass corner |
| TX | `01-ddma`: all eight, TX t stepping its phase by (t − 1) × 45° per chirp. `02-single-tx`: TX1. `03-coherent`: all eight with the phases of the calibration the routine derived from the DDMA CPIs at 09:28:19 (in the sidecars). 20 dB backoff, outside the 0–15 dB the datasheet specifies (Table 24). High-pass 300 kHz as in the host code (not recorded) |
| RX gain step (metadata) and typical noise figure at 10 / 1 MHz IF | 0 dB, the chip's default: `rx_gain_db` 0 (sidecars); 10.2 / 10.5 dB |
| Windows in this study | Blackman–Harris in range and in Doppler: the eight-TX beam's reflector lies about 85 dB above the noise per range–Doppler cell (93 dB on 2026-10-09), where Hann's sidelobes would still leak into remote Doppler |

| | Chamber, 2026-10-09 |
|---|---|
| Date | 2026-10-09, 11:17–11:38 UTC; by its packet clock the board had been running since about 10:39 |
| Aurix firmware | Ours (`release/omega/mifu2025-rc2_20261006-77-g7349c1fa`, without uncommitted changes); a new sidecar format (`schema_version` 1, which also records the board's `device_id`); the host tool's version is not recorded |
| MMIC RAM firmware | Revision 2836676 |
| Scene | The measurement chamber; the same reference reflector at an apparent 2.21 m, where the 2026-09-30 calibration had found it (both routines measured 2.2068 m) |
| Mounting | The chamber's fixed mounts: the reflector's level varies by at most 0.02 dB rms from CPI to CPI in the TX1 captures |
| Cases, in order | `notx-1` (11:17), `mode-1` (11:18), `mode-2` (11:19), `notx-2` (11:19), `mode-3` (11:31), `notx-3` (11:32), the calibration routine `01-ddma`, `02-single-tx`, `03-coherent` (11:37–11:38) |
| Sweep, sampling, chirp timing | `mode-1` and `notx-*`: 900 MHz at 87.9 MHz/µs, 76.55–77.45 GHz sampled; real, 50 MS/s, 512 samples in 10.24 µs, 256 chirps; PRI 500 µs; 4.0 µs pre-payload, 2 µs flyback + 484 µs wait; the reflector at 1.29 MHz. The others as on 2026-09-29, the reflector at 162 kHz |
| TX | `mode-1`: TX1, 10 dB backoff. `mode-2`: TX1, 0 dB. `mode-3`: TX1, 10 dB. `notx-*`: none. The routine: as on 2026-09-29, at 10 dB backoff; its TX1-alone stage failed (the reflector 25–30 dB below TX1's line in DDMA and varying by several dB from CPI to CPI), while the TX1 captures above are steady |
| RX gain step (metadata) and typical noise figure at 10 / 1 MHz IF | `mode-*`, `notx-*`: +3 dB; 9.7 / 9.9 dB. The routine: 0 dB; 10.2 / 10.5 dB |
| Windows in this study | As on 2026-09-29 |

All datasets are real int16 ADC data [chirp, sample, RX] with SHA-256
checksums, which the pipelines verify; where they are kept is listed under
[Raw data](#raw-data). The noise figures are the CTRX8188F
datasheet's typical values for the RX gain step (Table 30; the
"ultra low noise" rows at +3 dB and the "low noise" rows at 0 dB, which
Infineon confirmed are the gain steps), as `carkit_common.noise_figure_db`
gives them. Every model in these notes uses the 10 MHz value for the gain
recorded with the capture. The windows differ because the walk
reproduces Viktor's processing for the SNR comparison, while the outdoor and
window analyses favour low range sidelobes; results that combine datasets say
which they use.

### Firmware

"Infineon's firmware" and "our firmware" in these notes label the two setups.
Three layers decide what the radar does, and the RF behaviour comes from the
last two:

1. **The Aurix firmware,** Infineon's CARKIT application or ours. It programs
   the MMIC and moves the data, and does nothing on the RF side itself.
2. **The MMIC's own RAM firmware,** which the Aurix downloads into the
   CTRX8188F at start-up. Ours loads Infineon's `8188_release_1.0.0_rc3`
   (Strata 3.6.0), which the sidecars record as `mmic_version` 2836676. Which
   one Infineon's application loads is not recorded.
3. **The MMIC configuration:** the ramp program (segment times, slope, DPLL
   band) and the TX and RX settings.

**Which captures used which.** The walk, the outdoor captures and 2026-08-27
used Infineon's firmware: they are in Infineon's recording formats, and the
walk's and outdoor captures' ramp timing, 60 ns flyback and wait, is one our
tooling has never produced. Every capture from 2026-09-29 on records our build
in its sidecars (`fw_version`, git describe of l2-sp; the capture tables give
them), several of them built with uncommitted changes (`-dirty`). Infineon's
firmware can be put back on the unit. A comparison out of the office window,
not documented here, showed no significant difference in SNR between the
firmwares or between 76.5 and 77.0 GHz.

**Infineon's configurations.** RadarGUI or a host tool sends the modes and
waveforms; Viktor set up the walk's and the outdoor captures'. Every
configuration found keeps 60 ns flyback and 60 ns wait, although the format
allows other values (unused waveforms of 2026-08-27 have 0.99 µs wait and
120 ns flyback). The TX power settings are not recorded.

**Ours.** The host tool that builds the MMIC program (l2-sp
`projects/psi/host/cmd/psi-streamer/waveform.go`) runs on the host, and its
version is not recorded. Its minimum segments are 4.0 µs pre-payload, 0.04 µs
post-payload, 2.0 µs flyback and 3 µs wait. The time outside the payload must
also hold the chirp's CSI-2 transfer plus 5 µs: 10.24 + 5 µs for 512 samples at
the default lane rate of 1200 Mbit/s (400 and 800 Mbit/s can be set). That
limits the PRI to 25.5 µs or more at 512 samples, where the transfer may fill
the whole gap between payloads. The 2026-10-06 timing captures went below the
minima, down to 20 ns, with a locally modified host tool whose other changes
are not recorded. The DPLL band equals the ramp in every capture from
2026-09-30 on; the chamber captures of 2026-09-29 used a fixed 1 GHz band,
76.5–77.5 GHz. The segment settings follow the user manual: the DPLL in linear
mode from pre-payload to post-payload and in fast-settling mode during flyback
and wait; the RX high-pass at 300 kHz during the payload and at its maximum,
4.8 MHz, during the flyback ([The high-pass filter](#the-high-pass-filter));
HP boost and a digital filter reset in the pre-payload. The sidecars do not
record these, but the code fixes them. The RX gain is 0 dB, the chip's
default, unless the waveform sets `rx_gain_db` to 3, and the sidecars record
it.

**TX power.** The host tool sends `Configure_TX_Power` with all four power
levels of the enabled TX at 0 dB backoff from the maximum and the default PA
switching slope (user manual Table 48, l2-sp `board.go`); it accepts backoffs
up to 20 dB, beyond the chip's specified 0–15 dB. The Aurix firmware runs the
TX power calibration of power level 1 for each enabled TX at the start of
every run (`Execute_Calibration`, sub-function 0x2d, whose bit 0 is the TX
power calibration; Table 52, l2-sp
`projects/psi/firmware/drivers/radar/RadarRun.c`). The same sub-function also
sets bit 5, which the user manual marks as reserved. Nothing in our
configuration suggests less than maximum power.

The per-chirp error arises in the MMIC's synthesizer in both setups. The Aurix
software can affect it only through layers 2 and 3.

### Walk

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

**2026-09-30, our firmware** ([window_scene.py](window_scene.py),
[scene.png](generated/window/scene/scene.png)). Eleven folders named
`<waveform>-<TX>-<backoff>[-suffix]`, with no other description; the times are
the first CPI's, UTC:

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

The ADC is far from full scale: 16–19 counts rms of ±2048 with TX1, extremes
within ±1049 counts even with 8TX; offsets are −42 to −94 counts. No
capture clips, so the window frame is not a problem.

The long waveform (unambiguous to 1.26 km) sees static returns to about
500 m; beyond that only isolated weak peaks. The strongest distant returns are
at 169 and 273 m (20 and 19 dB per chirp with TX1), with others at 231 and
265 m. The 2026-08-27 recording has similar features at 174–175 and
270–280 m. Which one is the large building needs a map. The difference is
not a range-scale error. Our range scale is right to within 1 %
([Range scale](#range-scale)), and
Infineon's apparent ranges agree with the delay implied by its carrier step
to within 1 % (0.05 % at the strongest returns). So the two recordings saw
different scatterers, as their different pointing allows.

The strongest returns drift in phase by the same number of Hz within each
51 ms CPI: 1.4–3.3 Hz rms, or 2.7–6.4 mm/s: the hand-held radar moving. Two
of the late captures also carry a small fast phase common to all returns
([Window: method and results](#window-method-and-results)).

The sidecars record the ramp timing, the ramp and ADC frequencies, the TX
channels, backoff and phases, the RX gain, the calibration and the firmware
version. They do not record the per-segment settings (DPLL mode, RX
high-pass), which the host code fixes (see [Firmware](#firmware)), and the
firmware version ends in `-dirty` (built with uncommitted changes).

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

Its receiver noise does not fit the recorded RX gain. At 18–24 MHz in mode 0
it is 23.3 dB ADC-count² per sample after the windows are taken out (the same
beyond the scene), 4.7 dB above the 18.5–18.6 dB of the captures at +3 dB RX
gain with either firmware (the walk and the field captures). The recorded gain
code 1, the 0 dB step, would put it about 2.5 dB below them: 3 dB less
conversion gain, 0.5 dB more noise figure. The per-RX ADC offsets are those of
the other captures (−85 to −50 counts), so the converted samples are not
scaled differently. Either the gain code is read wrongly or the IF chain was
set up differently; its high-pass code is one the user manual does not allow
during the payload ([The datasheet's ramp timing](#the-datasheets-ramp-timing)).
No result here depends on it, since this recording is used only for
quantities relative within it.

**2026-10-02, our firmware, fixed mount** ([window_scene.py](window_scene.py)
and [window_phase.py](window_phase.py) run on this recording; outputs in
`generated/window/2026-10-02/`). Five cases: `medium-0dB`, `medium-10dB`,
`short-0dB` and `short-10dB` with TX1, and `medium-8TX`, coherent with the
calibration. They were meant as the chirp-timing test but repeat the
2026-09-30 timing (4.0 µs pre-payload, 2.0 µs flyback, 83.72 µs wait, 100 µs
PRI); the test followed on 2026-10-06. The radar was evidently on a fixed
mount: the strongest returns' common phase drifts 0.03–0.09 Hz rms within a
CPI, against 1.4–3.3 Hz hand-held on 2026-09-30, except in `medium-8TX`
(12 Hz rms), where something moved. No CPI is flagged as interfered.

On this mount, 10 dB backoff lowers matched static returns by 9.9–10.0 dB and
the calibrated eight-TX beam adds 17.5 dB at the strongest return ([TX backoff
and the coherent eight-TX beam](#tx-backoff-and-the-coherent-eight-tx-beam)),
and δf is 3.09 kHz in the medium waveform and 3.61 kHz in the short ([Window:
method and results](#window-method-and-results)).

**2026-10-06, our firmware, fixed mount, chirp timing**
([window_scene.py](window_scene.py), [window_phase.py](window_phase.py) and
[window_timing.py](window_timing.py) run on this recording; outputs in
`generated/window/2026-10-06/`). Viktor's chirp-timing test: ten cases of the
medium waveform with TX1, named `medium-<setting>`, where "ramp" stands for
the pre-payload; the `medium-ramp<n>ns` cases also have a 1 µs flyback. The
timing is the sidecars'; times are the first CPI's, UTC:

| Case | Time | CPIs | PRI | Pre-payload | Flyback | Wait |
|---|---|---:|---:|---:|---:|---:|
| medium-PRI100 | 13:09:39 | 10 | 100 µs | 4.0 µs | 2.0 µs | 83.72 µs |
| medium-PRI50 | 13:10:39 | 9 of 10 | 50 | 4.0 | 2.0 | 33.72 |
| medium-PRI30 | 13:11:21 | 10 | 30 | 4.0 | 2.0 | 13.72 |
| medium-PRI25 | 13:12:02 | 10 | 25.5 | 4.0 | 2.0 | 9.22 |
| medium-PRI25-ramp20ns | 13:13:46 | 10 | 25.5 | 0.02 | 2.0 | 13.20 |
| medium-PRI25-flyback20ns | 13:14:51 | 9 of 10 | 25.5 | 4.0 | 0.02 | 11.20 |
| medium-PRI25-ramp20ns-flyback20ns | 13:16:32 | 10 | 25.5 | 0.02 | 0.02 | 15.18 |
| medium-ramp6000ns | 13:20:41 | 10 | 25.5 | 6.0 | 1.0 | 8.22 |
| medium-ramp4000ns | 13:20:55 | 10 | 25.5 | 4.0 | 1.0 | 10.22 |
| medium-ramp2000ns | 13:21:08 | 10 | 25.5 | 2.0 | 1.0 | 12.22 |

The payload (10.24 µs) and post-payload (40 ns) are the same throughout, so
at 25.5 µs every case has 15.2 µs between payloads, split differently. The
firmware build has no uncommitted changes, but the host tool that set these
timings was modified ([Firmware](#firmware)). No CPI is flagged as
interfered.

The radar was evidently on a fixed mount: the strongest returns, at 27 and
33 m, stay within 0.5 dB of the first capture, the median matched return
within 0.4 dB, and the scene's phase drifts 0.07–0.6 Hz rms within a CPI. The
exception, 3.4 Hz in `medium-PRI25-ramp20ns-flyback20ns`, is the same at all
returns to 0.3 Hz, so it is not an LO frequency drift, which would grow with
the delay; it is not explained, and it lies below the band in which δf is
measured. The scene is stronger than on 2026-09-30 (65–76 counts rms at the
ADC against 16–19, a return at 27 m at 36 dB per chirp), so the radar pointed
differently. The two cases with a 20 ns pre-payload reach −878 and +1170
counts, against at most 352 counts in magnitude in the others, and 1 dB more
rms, presumably the start of the ramp falling into the sampled payload; no
capture clips.

### Field captures

([field_if.py](field_if.py), [field_level.py](field_level.py).) The README
names the cases `<waveform>-<distance>` for the reflector "stationary at" a
distance, with the short and medium waveforms of 2026-09-30, TX1 unless named
otherwise; `empty-<waveform>` for the scene without the reflector; `notx`, with
no TX enabled (medium waveform); `sky-1tx` and `sky-8tx` pointed at the sky
(the README says medium, the sidecars short); and runs with the reflector
carried towards the radar. The photos show a home-made 100 mm triangular
trihedral like the walk's, on a small tripod at about 1 m, with the radar at
about the same height; on the pitch its opening faces the radar. In two photos taken
earlier it stands beside the radar with one plate flat on the tripod head,
which would put the radar in the plane of that plate.

Order, UTC: the empty scenes at 10:38–10:39; at each distance the short and
then the medium waveform, 15–28 s apart, from 10:42 to 10:50; the runs
10:51–10:59; `notx` 11:01; the sky 11:04–11:05; `run-8tx` 11:08.

The reflector is the static peak that rose most over the empty scene. Its
apparent ranges are 3.76, 7.33, 16.03, 34.05, 52.24 and 90.45 m for the
nominal 5–100 m, the same in both waveforms within 0.15 m. The range scale is
right to within 1 % ([Range scale](#range-scale)), so the nominal distances were
indicative. Its level is steady: 0.01–0.16 dB rms from CPI to CPI, as for
fixed mounts, and within −1.5 to +1.0 dB of the RX mean in every channel.
After the 2026-09-30 calibration's RX phases, its per-RX amplitudes fit a
plane wave with coherence 0.98–1.00, so that calibration still holds a day
later. No CPI of the stationary or reference
captures is flagged as interfered.

The runs, with the reflector carried from beyond 60 m towards the radar
"pointed towards the radar with the best of our ability" (README), are in
[The reflector carried in the field](#the-reflector-carried-in-the-field).
The sky captures enter only [The receiver background](#the-receiver-background);
`sky-8tx`, like `run-8tx`, has no calibration record and all TX phases at 0.

**The radar's pointing** ([field_runs.py](field_runs.py)). The static returns
of the pitch, measured in 10-CPI coherent means of every capture, show where
the radar pointed. Between the empty-scene captures (10:38–10:39) and the
first placement (10:42) the radar was turned: every return's azimuth moved by
about 5.5° together, with their levels. The empty scenes serve only to find
the reflector and for the receiver background, which this does not affect.
Through the placements and the first run with each waveform (to 10:54) the
scene stays the same: the median azimuth shift of its returns is within 0.3°
and the median level change within −0.8 to +1.4 dB. Before the second runs
(10:56) the radar was moved again: the scene's levels fell by 4–11 dB, and
the one return per run coherent enough to measure moved by 10–12°.

### Highway captures

([highway_traffic.py](highway_traffic.py),
[range_time.png](generated/highway/range_time.png).) Four captures with the
long waveform: TX1 (516 CPIs) and 8TX coherent (189, 487 and 152 CPIs; the
last with 400 chirps). About half of each run's CPIs were not recorded; the
CPI indices span 300–979. Vehicles are visible to the end of the straight in
both modes: passes beyond 900 m reach 16–32 dB per RX with TX1 and 15–51 dB
with 8TX. The model without hardware losses gives a 10 dBsm target −6.9 dB per
RX at 1 km with TX1, so those vehicles return 23–39 dB more: presumably large
vehicles near grazing incidence, with multipath over the road.

Along a pass the SNR hardly changes with range. Fitting SNR ∝ R⁻ⁿ to each
pass gives medians of n = −0.05 (TX1, 6 passes) and 0.12–0.16 (8TX, 21–33
passes per capture), against 4 for a target of fixed RCS in free space. From
a bridge about 7 m above the road (a depression angle of 4.0° at 100 m and
0.4° at 1 km), the depression angle, the vehicle's aspect and the multipath
change with range more than R⁻⁴ does, so these captures say nothing about the
range model. It is the vehicles' power that hardly changes: the moving-target
background changes by about 1 dB from 30 m to 1.2 km (a one-off check on the
TX1 capture).

Other radars interfere in 39 of 516 CPIs with TX1 and 70 of 487 in the busiest
8TX capture, none in the other two ([Interference from other
radars](#interference-from-other-radars)); the steps drop them. A one-off run
of window_phase on the busiest 8TX capture gives δf 0.50 kHz (p5–p95
0–0.80 kHz) from 17 clean static returns at 35–385 m. That is no better a bound
than the window captures' 0.56 kHz: the bridge moves (common phase 11.8 Hz rms,
up to 193 Hz), which the fit has to absorb.

### Chamber captures

([chamber_tx1.py](chamber_tx1.py),
[chamber_background.py](chamber_background.py),
[chamber_channels.py](chamber_channels.py),
[chamber_level.py](chamber_level.py).) Viktor ran our host tool's calibration
routine in the measurement chamber on 2026-09-29 with the chamber's 10 dBsm
reference reflector. The routine captures ten CPIs with all eight TX in DDMA,
derives the TX and RX phases from them, then captures TX1 alone and the
eight-TX beam with those phases: three folders, 16 s in all, with the
calibration record in the beam's sidecars. Three hours later the same chamber
gave the calibration Viktor committed to l2-sp
(`projects/psi/firmware/host/calibrations/lab-77ghz-20260929.json`, with a
200 MHz waveform); its raw data are not here.

The reflector is the strongest static return, at an apparent 2.457 m (TX1 and
DDMA) and 2.467 m (the beam); other radars see it at about 2.3 m. Its exact
distance does not matter here, only that the analysis looks at its range
cell. Its beat frequency, 181 kHz, lies below the high-pass corner, which
cuts it by about 11 dB ([The high-pass
filter](#the-high-pass-filter)). The ADC samples
reach −636 and +492 counts of ±2048 with the beam, so nothing clips. Beyond a
few metres the chamber holds nothing, so the background there is the
receiver's, plus whatever the reflector itself spreads into it.

**2026-10-09.** A second session avoids the first one's two limits, the TX
backoff outside the specified range and the reflector inside the high-pass. TX1 alone, at the
+3 dB RX gain of the field captures: a steep chirp (900 MHz in 10.24 µs) at
10 dB backoff, which puts the reflector at 1.29 MHz, above the high-pass, and
the first session's waveform at 0 and 10 dB backoff, with the reflector at
162 kHz. Between them, three captures with no TX enabled; last, the
calibration routine at 10 dB backoff. The reflector stood at an apparent
2.21 m, where the 2026-09-30 calibration had also found it. The routine's
TX1-alone stage failed this time: its reflector is 25–30 dB below TX1's line
in DDMA and varies by several dB from CPI to CPI, while the dedicated TX1
captures are steady to 0.02 dB; the analysis uses TX1's DDMA line where it
needs TX1 from the routine. The largest ADC sample is 1213 counts, in the
steep chirp.
Viktor's report describes earlier measurements in the same chamber, whose raw
data were not supplied: a DDMA phase calibration with the reflector at about
2.2 m and 400 MHz sweeps at seven centre frequencies from 76.5 to 78.0 GHz,
with Infineon's 60 ns flyback and wait (its Table 1), and captures with one,
two, four, six and eight TX at 20 dB backoff and RX gain −18 dB, 200 MHz at
25 MS/s, 256 samples and 64 chirps at 100 µs (its Table 3). Its TX powers and
calibration phases enter [TX backoff and the coherent eight-TX
beam](#tx-backoff-and-the-coherent-eight-tx-beam) and [Channel calibration
and delays](#channel-calibration-and-delays).

## Sensitivity against the model

The radar equation with datasheet values against the chamber's reference
reflector on a fixed mount, the best absolute check, and against the home-made
reflector, carried on the walk and on a tripod and carried in the field
captures; with the loss terms, what a reflector's aim costs and what its
finite size does at short range.

### Model

| Quantity | Value |
|---|---|
| Model TX / NF | CTRX8188F datasheet typical: 14.5 dBm; NF 9.7 dB, the ultra-low-noise row at 10 MHz IF, which is the walk's RX gain step +3 dB (9.9 dB at 1 MHz; the toolbox preset's 10.2 dB is the 0 dB step). Infineon confirmed that the noise modes are the gain steps ([Loss terms](#loss-terms)) |
| Model antenna | FARAD-IV digitized boresight: 15.05 / 14.98 dBi TX / RX; the datasheet describes these as directivity |
| Model target | Nonfluctuating 10 dBsm at boresight; no straddle or CFAR loss |
| Processing | The walk's Blackman windows (2.37 dB ENBW loss each); fourfold padding leaves at most 0.07 dB scalloping |

The model is [walk_model.py](walk_model.py): 33.17 dB per RX for a 10 dBsm
target at 100 m with the walk's waveform. This reference model has no hardware
losses; [Loss terms](#loss-terms) adds them.

### Reflector

| | Chamber reflector | Walking reflector |
|---|---|---|
| Type | Microwave Factory [MTR76P10-T5DW-100](https://www.mwf.co.jp/en/products/rf_accessories/mtr.html), triangular trihedral | Home-made: reflecting plates glued onto a trihedral of 1 cm absorber; we have two |
| Size | 77.8 mm inner edge if ideal (not measured) | 100 mm inner edge, from the vertex along a seam (measured 2026-10-01) |
| RCS | 10 dBsm at 76.5 GHz, as specified, without a tolerance | 14.3 dBsm if ideal (at 76.4 GHz); measured against the chamber reflector, 11.3 dBsm at 2.5 m, about 12.1 dBsm with the short-range effect taken out |

A triangular trihedral with inner edge a has ideal RCS σ = 4πa⁴/(3λ²).

The lab comparison put the chamber reflector at 2.22 m and the walking one at
2.51 m, aligned their angle responses and compared P × R⁴: the walking
reflector came out 1.27 dB stronger. The reflectors stayed fixed while the
radar turned on the turntable
([reflectors-angle-aligned.png](inputs/reflectors-angle-aligned.png)),
so the angle responses are the radar's two-way azimuth pattern, not the
reflectors' response to aim: 0.9, 2.5 and 4.7 dB down at 10, 15 and 20°,
read off the figure, against 0.8, 2.5 and 4.5 dB on one side of the FARAD-IV
preset. What aim costs is in [The reflector's aim](#the-reflectors-aim).
The first-order on-axis near-field loss,
|sinc(A/λR)|² with A = a²/√3 (see `pa_260916_antenna_centers.md` in l2-sp), is
0.24 dB for the chamber reflector and 0.51 dB for the larger walking one at
their distances, so it does not cancel between reflectors of different size;
nor is it the whole short-range effect. With TX1 transmitting, the receivers
sit 5–7 cm from the centre of the returned beam, which is narrower for the
larger reflector ([A reflector at short range](#a-reflector-at-short-range)).
Taken together, TX1's return over the eight RX is 2.18 dB below the far-field
monostatic level for the chamber reflector at 2.22 m and 3.03 dB for the
walking reflector at 2.51 m, so the far-field difference is 0.85 dB larger
than measured, and the walking reflector is about 12.1 dBsm
([chamber_tx1.py](chamber_tx1.py)). The walking reflector stood about 15° to
the side of the chamber reflector (Viktor's figure,
[rcs-comparison.png](inputs/rcs-comparison.png)), and the radar was
turned towards each. If the reflector itself faced along the chamber rather
than at the radar, it was 15° off its axis, which for an ideal trihedral costs
1.6 dB ([The reflector's aim](#the-reflectors-aim)), and its RCS would be
higher still; how it was aimed is not recorded.

That is 2.2 dB below an ideal 100 mm trihedral, plausible for plates glued onto
absorber. A trihedral tolerates being pointed a few degrees off, but its
returned beam is only about 2° wide for a 100 mm aperture at a 3.9 mm
wavelength. Plate-angle errors of a few tenths of a degree steer that beam
partly away from the radar. The walking reflector's metal stand, which the
report noted, may have added to the comparison, which would make the reflector
itself weaker still. On the walk itself (15–51 m) the near-field loss is below
0.05 dB; in the field captures it is 0.23 dB at 3.76 m and 0.06 dB at 7.3 m
(`field_common.near_field_loss_db`, which reproduces the two lab values above
to 0.01 dB).

We have two home-made reflectors. They look identical, are not marked, and
should have close to the same RCS; one of them, presumably the walk's, was
compared with the chamber reflector in the lab on 2026-09-11. Which one the
field captures used is not known, and the photos cannot tell them apart. These
notes call the field captures' reflector the walk's, as the measurements
assume. Calibrating both against the chamber reflector, and marking them,
settles it (measurement 1). The steps use the lab comparison's 11.27 dBsm at
face value (`walk_common.py`); the report and its levels figure use 12.1 dBsm
([report_figures.py](report_figures.py)). With 12.1 dBsm the walk's +0.7 dB
over the model becomes −0.2 dB as measured and +0.3 dB at 5 MHz, and the
field tripod's 3.8–4.8 dB below it becomes 4.7–5.7 dB.
A side-by-side comparison at 10 m or more, where the short-range effect is
negligible, would settle both this and how much the two home-made reflectors
differ (see the open questions).

**The carrier's own return is negligible.** On the walk the person carrying
the reflector is in its range cell, and the trunk moves with the reflector, so
its return shares the reflector's Doppler cell too. Averaged over aspect, a
person measures −6.1 to −7.4 dBsm at 76–81 GHz, −1 to +1 dBsm at the
strongest aspect
([Schubert et al., IRS 2013](https://mwt-www.e-technik.uni-ulm.de/downloads/papers/2013/2013_IRS_Human-RCS-Measurements_Schubert_.pdf)),
and −8.1 dBsm at 76 GHz, with front and back about 5 dB above the side
([Yamada, R&D Review of Toyota CRDL 39(4)](https://www.tytlabs.co.jp/en/english/review/rev394epdf/e394_046yamada.pdf)).
The walk agrees: the power within 2 m/s of the reflector's Doppler but outside
±0.5 m/s, mostly the swinging legs, is 0.9 % of the reflector's inbound
(about −9 dBsm) and at about the same absolute level outbound
([CPI length](#cpi-length)). So the trunk, part of a body of about −7 dBsm, is
at least 18 dB below the reflector's 11.3 dBsm. With a relative phase that
changes between CPIs, it moves a CPI's level by about ±1 dB, in line with the
walk's 0.6 dB rms at 15–27 m, and the averaged level by less than 0.1 dB.

### The reflector's aim

A corner reflector returns the most when the radar lies on its symmetry axis,
the direction out of its opening along which all three plates look alike. In
geometric optics its return is the triple bounce: a ray that enters the
opening at one point leaves at the point mirrored through the vertex. The
effective area A is therefore the overlap of the opening, projected towards
the radar, with its own mirror image through the vertex, and σ = 4πA²/λ². For
a triangular trihedral with inner edge a, and θ the angle between the
direction to the radar and the axis, this has a closed form:

σ(θ) / σ₀ = ((3 cos²θ − 2) / cos θ)²,  σ₀ = 4πa⁴ / (3λ²).

It is 3 (s − 2/s)² with s = l + m + n = √3 cos θ, the sum of the direction
cosines of the radar's direction against the three edges
(`field_common.trihedral_aim_loss_db`). The shape does not depend on the size
or the wavelength; a sets only the peak, 14.4 dBsm for an ideal 100 mm
reflector at 77 GHz. The formula holds for every direction of tilt up to
about 22°, and towards a plate up to 35.26° (arcsin 1/√3), where the radar
lies in that plate's plane and no triple bounce returns. Towards an edge the
loss beyond 22° is smaller. A one-off computation of the overlap for any
direction and a brute-force ray trace, counting the rays that leave after
exactly three bounces, agree within 0.1 dB, and with the formula where it
holds.

| Off the axis | 5° | 10° | 15° | 20° | 25° | 30° | 35° |
|---|---:|---:|---:|---:|---:|---:|---:|
| Loss, tilted towards a plate | 0.2 dB | 0.7 dB | 1.6 dB | 3.2 dB | 5.8 dB | 10.8 dB | 36 dB |
| Loss, tilted towards an edge | 0.2 dB | 0.7 dB | 1.6 dB | 3.2 dB | 5.3 dB | 7.9 dB | 11.1 dB |
| The tilt over the 100 mm edge | 9 mm | 17 mm | 26 mm | 34 mm | 42 mm | 50 mm | 57 mm |

The last row is how far one end of the walking reflector's edge moves
sideways against the other when the reflector turns by that angle
(100 mm × sin θ). An aim that wanders around the axis costs little: within
±10° it costs at most 0.7 dB at any moment. The losses in these notes need a
large error held throughout: 4.4 dB is 23° off the axis, 7 dB 27–28° and
12 dB 31–36°, the first value of each towards a plate and the second towards
an edge (from the overlap computation). The height difference between radar and
reflector adds little: 0.5 m is 1.9° at 15 m.

One natural way of holding the reflector loses that much. With one plate
horizontal, as it stands on a table, the axis points 35° above the horizontal
and a radar at the reflector's height lies in that plate's plane; tilting the
opening 5–10° down from there leaves the radar 25–30° off the axis, a loss of
6–11 dB. How the reflector was held in the carried runs is not known.

In practice an aim set by eye has nothing to sight along, carried or on a
tripod head, and how far it can be off has not been measured. Carried at
waist height, the reflector is also below the carrier's line of sight to the
radar; held at eye height on that line, the carrier can at least judge the
aim. A sight along the axis (a tube or two pins on its back, or a laser
pointer) makes the aim checkable, on a mount as well.

These figures are for an ideal reflector. The walking reflector is 2.2 dB
below an ideal 100 mm trihedral, plausibly from plate-angle errors (above),
which may also change its response off the axis. Measurement 1 includes an
aim scan of it.

### A reflector at short range

([chamber_common.py](chamber_common.py) `trihedral_factor`,
[chamber_tx1.py](chamber_tx1.py), [chamber_channels.py](chamber_channels.py),
[tx1.png](generated/chamber/2026-10-09/tx1/tx1.png), right.) The radar
equation treats the reflector as a point seen by a transmitter and a receiver
at the same place. At 2–3 m neither holds for CARKIT. A triangular trihedral
images the transmitter through its vertex and sends the return back through
its aperture, a hexagon of area a²/√3, in a beam centred on the transmitter.
In the paraxial form used in l2-sp for the antenna's phase centres
(`matlab/Users/patrik/pa_260916_antenna_centers.md`, "Finite-aperture
approximation"), a TX–RX pair at baseline 2d sees

  F(d) = (1/A) ∫_A exp(−jk|p − d|²/R) d²p,

relative to the far-field monostatic return. At d = 0, |F|² is the on-axis
near-field loss of [Reflector](#reflector) (0.25 against 0.24 dB for the
chamber reflector at 2.22 m: hexagon against disk). Off the centre the return
falls: for the chamber reflector at 2.21 m the beam is 13.4 cm wide to half
power at the radar, and CARKIT's receivers sit 5–7 cm from TX1, 48 mm below
the TX row. TX1's pairs come out 1.8–3.3 dB below the far-field monostatic
level, 2.20 dB in mean power over the eight RX, and 1.77 dB at 2.46 m. At
16 m the same offsets cost 0.03–0.06 dB, so the walk, field and window
captures are unaffected. The implementation reproduces the l2-sp model's
predicted 3.26 dB spread over all 64 CARKIT pairs at 2.3 m
(`test_chamber_common.py`).

The chamber data bear it out where they can tell:

- **TX powers.** Each TX sees the receivers from a different place, so the
  apparent TX powers from DDMA carry a geometric pattern: TX5 and TX8, nearest
  the RX row, come out strongest. Taking it out halves the spread of TX2–TX8
  relative to TX1: 0.55 to 0.25 dB rms on 2026-10-09, 0.55 to 0.30 dB on
  2026-09-29, and 0.52 to 0.35 dB in the report's Table 2 (at 2.2 m).
- **Receivers.** RX7, farthest from TX1, is predicted 1.09 dB below the RX mean
  at 2.21 m and measured 1.07 dB below. Otherwise the per-RX levels are
  dominated by a pattern the model does not predict (RX1 and RX2 about 0.8 dB
  low, RX6 0.7 dB high), the same on both days to 0.16 dB rms: channel gains,
  most likely.

So the radar equation needs this factor for any reflector measurement at a few
metres, and a reflector comparison there needs it for each reflector's size
and distance. It does not cover the plates' angle-dependent truncation,
element patterns or polarization.

### The chamber reflector

([chamber_tx1.py](chamber_tx1.py), [chamber_level.py](chamber_level.py).)
The 10 dBsm reference reflector on a fixed mount in an empty chamber is the
best absolute check we have. The first session cannot serve as one: our host
tool's calibration routine sets 20 dB of TX backoff, and the CTRX8188F is
specified for an output power reduction of 0–15 dB (target datasheet rev.
0.20, Table 24: accurate to ±1.5, ±2 and ±3 dB over 0–6, 6–12 and 12–15 dB);
its user manual says the power levels must not leave that range (Table 48,
`Configure_TX_Power`). The second session, on 2026-10-09, was made for it
([Chamber captures](#chamber-captures)):

- TX1 at 10 dB backoff, which the same session measures as 9.73 dB on the
  reflector (0 against 10 dB with the first session's waveform), and TX1
  alone, as in the walk and the field captures.
- RX gain +3 dB, the field captures' step, so the model uses the same typical
  noise figure (9.7 dB) as theirs.
- A chirp steep enough to put the reflector at 1.29 MHz, where the high-pass
  measured on the reflector cuts it by 0.44 dB ([The high-pass
  filter](#the-high-pass-filter)).

The model is the walk's reference model with this capture's waveform, the TX
power lowered by the measured step and TX1's finite-aperture factor at the
reflector's apparent 2.21 m, −2.20 dB ([A reflector at short
range](#a-reflector-at-short-range)):

| Capture, noise reference | Measured − model | Without the finite-aperture factor |
|---|---:|---:|
| Steep chirp, 10 dB backoff, noise at 4–7 MHz (centred on 5.3 MHz) | −0.65 dB | −2.85 dB |
| The same, noise at its own 1.29 MHz | −1.32 dB | −3.53 dB |
| The same with the nominal 10 dB instead of the measured step, noise at 4–7 MHz | −0.38 dB | −2.58 dB |
| First session's waveform at full power, the high-pass at 162 kHz measured, noise at 4–7 MHz | −0.75 dB | −2.94 dB |
| First session (20 dB backoff, outside the specified range), noise at 4–7 MHz, at face value | −0.79 dB | −2.56 dB |

The two routes on 2026-10-09 agree to 0.1 dB, and the first session's face
value lands on them as well, so on TX1 the 20 dB backoff evidently gave
20 dB. The apparent range moves the model by 0.08 dB per centimetre; the
reflector's true distance is not known to better than about 10 cm, and the
reference reflector's 10 dBsm comes without a stated tolerance.

Against the other sessions, with the noise near 5 MHz and the home-made
reflector's RCS as the scripts assume (11.27 dBsm) or corrected for the
lab comparison's geometry (12.1 dBsm, [Reflector](#reflector)):

| Session | Measured − model, 11.27 dBsm | With 12.1 dBsm |
|---|---:|---:|
| Carried reflector (walk, Infineon's firmware), 5.3 MHz | +1.2 dB | +0.3 dB |
| Reflector on a tripod (field, ours), 34 m at 5.3 MHz | −3.8 dB | −4.7 dB |
| Chamber, reference reflector (ours) | −0.4 to −0.7 dB | |

The chamber puts the radar with our firmware within 1 dB of the model; with
the corrected RCS the carried reflector agrees with it to 1 dB, and the tripod
is the outlier.

### The carried reflector

([walk_extract.py](walk_extract.py),
[walk_reference_snr.py](walk_reference_snr.py).) The walk's reflector,
carried towards the radar, gives the main comparison with the model.

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

Per-CPI standard deviation is 2.2 dB. Per-RX dB means range from 30.8 to
34.2 dB.

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
from the reference. Carried towards the radar in the field session, the
reflector came out about as low ([The reflector carried in the
field](#the-reflector-carried-in-the-field)).

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

### RX differences

The strongest-to-weakest RX power span at the target cell has a median of
9 dB outbound and 11 dB inbound, up to 28 dB. In CPI 100, RX8 is 28 dB below
the strongest channel at the common cell but 16 dB below over a surrounding
patch ([rx_null_example.png](generated/walk/dynamics/rx_null_example.png)).
The spans change from CPI to CPI, so they are not fixed calibration
differences. Nulls this deep need a second return of comparable strength from
another direction; the carrier's own is far too weak ([Reflector](#reflector)),
so their cause is not known. They also keep a coherent sum over the RX well
below the 9 dB that eight equal channels would give.

### Loss terms

The reference model ([Model](#model)) has no hardware losses: the datasheet's
TX power and noise figure act directly on the antenna's directivity. The
toolbox names each term between them (`SystemLosses`; catalogue and sources in
[docs/losses.md](../../docs/losses.md)). For CARKIT in the walk
([walk_model.py](walk_model.py),
[summary.json](generated/walk/model/summary.json)):

| Term | The walk | Effect on the model |
|---|---|---:|
| Noise figure at low IF | RX gain code 0, +3 dB (the recorded mode in `provenance/configuration.json`; CTRX8188F user manual Table 120). At that gain the datasheet gives 9.7 dB at 10 MHz IF, which the model uses, and 9.9 dB at 1 MHz, typical; the walk's 15–51 m are at 1.0–3.3 MHz | 0 to −0.2 dB |
| TX power | TX1 at 0 dB backoff, the maximum setting, for which the datasheet's 14.5 dBm typical holds, as modelled (Table 22) | 0 |
| Feed | CARKIT's PCB carries the package's waveguide ports through to the antenna (quick start guide v17, 2.2): the arrangement for which the datasheet defines its RF reference plane, at the far side of a 1.2 mm reference PCB (datasheet Section 5, Figure 5). Whether CARKIT's PCB matches that reference design is not documented | 0 |
| Antenna | 15 dBi stated as directivity. Radiation efficiency ≥ 90 % (≤ 0.46 dB) and reflection coefficient ≤ −10 dB (mismatch ≤ 0.46 dB) put realized gain 0–0.92 dB below it on each pass (FARAD-IV data sheet), taking the efficiency to exclude mismatch (below) | 0 to −1.83 dB |
| Radome | CARKIT's closed housing covers the antenna (quick start guide, 1.3). Its loss is not documented, and the FARAD-IV figures are without a radome. It cannot easily be removed, so every CARKIT measurement includes it | not known |
| Straddle | Fourfold padding on both axes: 0.02 dB per axis, the toolbox's mean over target position (`straddle_loss_db`) | −0.05 dB |
| Atmosphere | ITU-R P.676-13 standard atmosphere at 76.37 GHz, 0.35 dB/km (`Atmosphere.itu_p676`), two-way at 15–51 m | −0.01 to −0.04 dB |
| Per-chirp frequency error | 19.0 kHz rms ([The per-chirp frequency error](#the-per-chirp-frequency-error)), at 15–51 m (`coherence_loss_db`) | −0.00 to −0.01 dB |
| Multipath | Not modelled ([Range structure and geometry](#range-structure-and-geometry)) | |

The measurement is scaled to 100 m by R⁻⁴ alone, so the range-dependent terms
apply at the walk's own ranges, where they are negligible. With the other terms
the model is 31.10–33.13 dB before the radome. The headline measurement is then
0.74–2.77 dB above it, and 1.96–3.99 dB with the noise from the far quarter,
which overstates it ([Noise or gain shape: two
slopes](#noise-or-gain-shape-two-slopes)). Any loss in the radome adds to both.
Where the receiver's noise is flat, the difference is larger: 0.9–3.0 dB at
5–14 MHz ([The baseline difference](#the-baseline-difference)).

Notes on the terms:

- **The antenna's figures are for a bare antenna.** The FARAD-IV data sheet
  (1377.99.0744, PIM-P62799, 2026-01-20) gives its figures for the antenna on
  a PCB without a radome. The CARKIT user manual's patterns peak at about
  15 dB (p. 9), but it does not say whether they are directivity or gain, or
  whether the radome was on.
- **The antenna's efficiency may already include its mismatch.** The data
  sheet does not define radiation efficiency. IEEE Std 145 leaves mismatch out
  of it, which is how the table reads it. HUBER+SUHNER's own papers on the
  technology use the term for total efficiency, mismatch included. Read that
  way, realized gain is at most 0.46 dB below directivity on each pass,
  0.92 dB both ways. Their 76–81 GHz prototypes, not the FARAD-IV, report
  total efficiencies above 90 % and up to 94 %, 0.27–0.46 dB per pass
  ([docs/losses.md](../../docs/losses.md) gives the sources).
- **The noise figure follows the RX gain.** The datasheet specifies its "ultra
  low noise operation mode" rows (noise figure and conversion gain) at RX gain
  step +3 dB and its "low noise" rows at 0 dB, with conversion gains 3 dB apart
  (Table 30). The user manual has no other noise-mode setting than the RX gain
  select. We therefore read the modes as gain steps
  ([docs/losses.md](../../docs/losses.md) gives the evidence), and Infineon
  has confirmed it (email, 2026-10-02): there is no noise-mode setting; the
  integrator sets the RX gain with `Configure_RX()` or in the ramp design
  tool, and the default is 0 dB. CARKIT ran at +3 dB in every capture here
  except 2026-08-27, which ran at the default. The datasheet gives no minimum
  noise figure. Its figures are
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
  walk's gain is 3.0 dB above typical (Table 30). Minimum and maximum hold
  over the whole functional range, junction temperatures from −40 to 135 °C
  and 76–81 GHz, unless a row states a narrower condition, and the
  noise-figure rows do not; typical values are for a nominal part at nominal
  supply voltage and room temperature (Infineon, same email). The limits say
  how far one unit may be from the typical part, not where ours is, so they
  are not in the model.

The terms widen the gap: the antenna, the noise figure's rise towards low IF,
the radome and anything not modelled all lower the model. The walk cannot
resolve terms of this size. The averaging convention alone moves the measured
value over 32.53–34.49 dB, the noise reference by 1.2 dB, and the reflector's
RCS comes from a near-field comparison at 2.5 m. The same reflector on a tripod
in the field captures gives a level 4.4 dB lower ([The reflector on a
tripod](#the-reflector-on-a-tripod)). A unit with TX power near the datasheet's
maximum would also explain up to 1.5 dB. So the terms are taken from their
sources, not fitted to the walk. A reflector on a fixed mount, calibrated
against the chamber reflector, would narrow the measured side. The radome's
loss cannot be measured on this unit, since the radome cannot easily be
removed; it remains an unknown loss in every comparison with the model.

### The baseline difference

The carried reflector's +0.7 dB holds at its own beat frequencies, 1.1–3.3 MHz
on the inbound leg (17–51 m). There the receiver is noisier than at the IFs of
long-range targets, and the model leaves that out: it uses the datasheet's
noise figure at 10 MHz, and the datasheet's 1 MHz row is only 0.2 dB higher.
The two-slope test measures the effect directly, as the SNR change of a fixed
reflector between beat frequencies ([Noise or gain shape: two
slopes](#noise-or-gain-shape-two-slopes)): +0.47 dB from 1.25 to 2.5 MHz,
+0.83 dB from 1.25 to 5.3 MHz and +0.49 dB from 1.25 to 14 MHz, the last if
nothing changes between 5.3 and 7 MHz. The inbound CPIs are spread about evenly
in range, so their mean log beat frequency is 2.1 MHz, 0.77 octave above
1.25 MHz. Taking the first pair's change as even over its octave, the carried
reflector sat 0.36 dB above the 1.25 MHz level, so a target at 5.3 MHz gets
0.47 dB more than it and one at 14 MHz 0.13 dB more.

| Measurement over the model | As measured, 1.1–3.3 MHz | At 5.3 MHz | At 14 MHz |
|---|---:|---:|---:|
| Reference model, no hardware losses | +0.7 dB | +1.2 dB | +0.8 dB |
| With the loss terms, before the radome | +0.7 to +2.8 dB | +1.2 to +3.0 dB | +0.9 to +2.7 dB |

At 5.3 and 14 MHz the loss terms leave out the noise figure's rise towards low
IF, which applies only at the reflector's own beat frequencies.

So the best current estimate of the baseline difference, where the receiver's
noise is flat as the model assumes, is about +1 dB, the measurement above the
model. At the ranges where the reflector was carried, the receiver's extra
low-IF noise hides about half a dB of it. The uncertainty is larger than the
difference: the averaging convention alone moves the measurement by −0.6 to
+1.3 dB, the datasheet allows ±1.5 dB of TX power between units, the RCS of
about 12.1 dBsm that the lab comparison gives once its short-range geometry is
taken out ([Reflector](#reflector)) would take 0.85 dB off, and the reflector
on a tripod, below, came out 4.4 dB lower. The chamber, with the reference
reflector, puts the radar 0.4–0.7 dB below the model ([The chamber
reflector](#the-chamber-reflector)). Above 14 MHz the receiver's response is
not measured.

### The reflector on a tripod

[field_level.py](field_level.py),
[levels.png](generated/field/level/levels.png). The field captures put the
walk's reflector on a tripod at six distances, each with two waveforms (see
[Field captures](#field-captures)). Its zero-Doppler power per RX, averaged
over RX and CPIs in ADC counts squared with sum-normalized windows, is scaled
to 16 m by R⁻⁴ at its apparent range. That is independent of window and
padding, so it compares directly with the walk's per-RX powers, scaled the same
way. Two corrections follow: the receiver's IF response at the reflector's beat
frequency, relative to 2.5 MHz, from the two-slope ratios ([The receiver
background](#the-receiver-background)); and the reflector's near-field loss
([Reflector](#reflector)).

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
tripod session is 4.3–4.5 dB lower at 16 and 34 m; at 34 m against the
walk's 27–38 m band (34.0 ± 2.1 dB, 11 CPIs) it is 4.9–5.0 dB lower, since the
walk's level rises with range and the tripod's does not between 16 and 34 m.
The receiver's noise
density at 18–24 MHz is 18.59 dB ADC-count² per sample with the TX off in the
field, and 18.47 dB in the walk's far quarter, after each dataset's windows
are taken out. A change of gain behind the receiver's first stages would show
there. A loss in front of them would not: it lowers the signal, while the
noise it adds makes up for the noise it removes, so the noise at the ADC stays
the same. Against the model without hardware losses, with the walking
reflector's 11.27 dBsm and the noise at the reflector's beat frequency, the
tripod session is 3.8–4.8 dB low at 16 and 34 m (3.3–3.6 dB with the noise at
18–24 MHz), and 0.5–0.8 dB high at 90 m.

What could cause 4.4 dB:

- **Azimuth: ruled out.** From the per-RX phases, the reflector was within
  −1.5 to +3.6° of boresight to 34 m (two-way pattern loss 0.1 dB at most in
  the FARAD-IV preset) and at +6° and +9° at 52 and 90 m (0.5 dB at most).
- **The radar's elevation pointing: possible.** The FARAD-IV preset's two-way
  elevation pattern is 3.8 dB down at 6° and 6.8 dB at 8°, so a tilt of 6–7°
  would explain it. The RX array is horizontal, so the data cannot show it.
  The static scene shows that the radar was turned in azimuth just before the
  placements ([Field captures](#field-captures)), so it was handled then; how
  it was left in elevation is not recorded.
- **The reflector's aim or state: possible.** On the pitch its opening faces
  the radar (photo), set by eye on the tripod head. An ideal trihedral loses
  0.7, 1.6 and 3.2 dB at 10, 15 and 20° off its axis, and 4.4 dB at 23°
  ([The reflector's aim](#the-reflectors-aim)), which nothing in the set-up
  rules out. A fixed tilt of the reflector on the tripod head would cost the
  same at every placement, as at 16 and 34 m. Plates glued onto absorber may
  also have moved since the walk, and the field session may have used the
  other of the two home-made reflectors, whose RCS has not been measured
  ([Reflector](#reflector)). Neither of these explains the further 7 dB of
  the later runs in the same session.
- **TX power as configured: possible, but nothing points to it.** Firmware
  matters only through the MMIC configuration it programs. Ours programs the
  maximum and calibrates it at every run ([Firmware](#firmware)); every chirp
  segment selects that calibrated power setting (`TX1_PA_POWER_SEL` 0 in
  CONFIG1, user manual Table 121). Infineon's settings are not recorded, but
  a comparison of the firmwares out of the office window showed no
  significant difference in SNR ([Firmware](#firmware)).
- **TX power over frequency and temperature: possible in part.** The walk
  sampled 76.32–76.43 GHz, the tripod session 76.88–77.12 GHz. The datasheet
  allows the TX power to vary by up to 1.5 dB over a ramp in 76–77 GHz, and by
  up to 1 dB over temperature with closed-loop power control (Table 24).
  The same comparison showed no significant difference between 76.5 and
  77.0 GHz. Neither session recorded the temperature.
- **A loss in front of the antenna: possible.** A film of water or dirt on
  the radome would cost the signal on both passes without changing the noise
  at the ADC. Nothing records the radome's state in either session.

A loss is easy to come by and a gain is not: the walk's level at 15–27 m is
steady (0.6 dB rms over 14 CPIs at different ranges), and a reflector held by
hand cannot return more than its aligned RCS (the carrier's own return adds
less than 0.1 dB; [Reflector](#reflector)). The later runs show how easily:
carried in the same session, the reflector lost another 7 dB ([The reflector
carried in the field](#the-reflector-carried-in-the-field)). So the tripod
session most likely lost 4.4 dB to something that does not change with range
between 16 and 34 m. Of the candidates, only the elevation pointing would
also explain the extra 2–3 dB at 3.8 and 7.3 m, where a small height
difference adds to the angle. A one-off fit of the FARAD-IV preset's elevation pattern, anchored to
the walk's level, gives a tilt of 6–7.5° and a height offset of 12–16 cm with
1.0 dB rms over 3.8–52 m (7.3 m 1.9 dB low), against 1.6 dB rms for a constant
loss at a free level. It predicts 29.3 dB at 90 m, where 33 dB is measured, so
it needs about 4 dB of constructive multipath there. Suggestive, not
decisive; the tilt scan in measurement 1 settles it.

The walk's averaging and selection conventions move its value by at most 2 dB
([The carried reflector](#the-carried-reflector)), and its short-range points
have a 0.6 dB spread, so they do not explain it either. Measurement 1 in the
open questions addresses the candidates: the reflector on a fixed mount,
aimed along a sight and re-aimed to measure the spread, an elevation tilt scan
of the radar, an aim scan of the reflector, the chamber reflector and, if the
equipment is at hand, CARKIT's radiated power measured directly. The chamber
has since put the radar, with our firmware, within 1 dB of the model ([The
chamber reflector](#the-chamber-reflector)), about 4 dB above this session,
which points at the session's setup rather than the radar.

### The reflector carried in the field

[field_runs.py](field_runs.py), [runs.png](generated/field/runs/runs.png).
After the tripod placements, the walk's reflector was carried from beyond 60 m
towards the radar, "pointed towards the radar with the best of our ability"
(README): two runs with each waveform with TX1, then one short run with eight
TX at zero phase, 10:51–11:08 UTC. In every CPI the reflector is the strongest
return approaching at 0.4–4 m/s within 3–60 m, found and read with the walk's
processing (periodic Blackman windows normalized by their sums, fourfold
padding on both axes). Its level is therefore in the units of the tripod
placements and the walk, and does not depend on the number of chirps. The
track is the CPIs whose peak stands 15 dB above the search region's median and
approaches faster than 1 m/s: 182–211 CPIs per run over 3–60 m, at a median
2.9–3.4 m/s (the track's range rate agrees), against 3.5 m/s on the walk's way
back and 3.3 m/s on its way out. Both sessions' carriers were running, at about
5 min/km; the walk's speeds are Doppler, and its range track agrees for
240–270 ms between recorded CPIs on both legs (the recording has no
timestamps). Every run approaches only: each recording
starts with the reflector beyond 60 m and ends near the radar, and at most two
CPIs per run show a receding return 15 dB above the background. One CPI of
`medium-run-2` and ten of `run-8tx` are dropped as interfered. The level is the mean RX power scaled to
16 m by R⁻⁴, in the walk's range bands. Like the walk's, it has no IF
correction; from 1.1 to 5.3 MHz that is within about 0.2 dB, and the short
runs reach 8 MHz at 52 m.

| dB ADC-count² at 16 m, mean ± std (CPIs) | 15–27 m | 27–38 m | 38–52 m |
|---|---:|---:|---:|
| The later runs, four with TX1 | 22.1 ± 1.9 (151) | 22.0 ± 2.7 (137) | 21.4 ± 3.8 (172) |
| The run with eight TX at zero phase | 36.0 ± 2.1 (39) | 35.8 ± 1.7 (33) | 35.1 ± 3.3 (45) |
| Walk, on its way back | 33.3 ± 0.6 (14) | 34.0 ± 2.1 (11) | 35.2 ± 2.7 (14) |
| Walk, on its way out | 19.8 ± 3.5 (15) | 20.9 ± 4.3 (14) | 24.1 ± 3.5 (16) |
| On the tripod, 16 and 34 m, both waveforms (corrected) | 29.0 | 29.0 | |
| TX1 runs against the tripod's 29.0 dB | −6.8 | −7.0 | −7.6 |
| TX1 runs against the walk's way back | −11.2 | −12.0 | −13.8 |
| TX1 runs against the walk's way out | +2.4 | +1.1 | −2.7 |

The four TX1 runs' band means lie within 20.1–23.3 dB, with no difference
between the waveforms beyond that. The eight TX at zero phase add
13.7–13.9 dB, against 17.5 dB measured with the calibrated phases and 18.1 dB
for an ideal beam ([TX backoff and the coherent eight-TX
beam](#tx-backoff-and-the-coherent-eight-tx-beam)).

**CPI length.** The later runs' CPI is 51 ms (512 chirps at 100 µs), the
walk's 16 ms. Split into 256- and 128-chirp segments, the mean segment peak
lies 0.5–0.8 and 0.8–1.2 dB above the full CPI's at 15–52 m. Noise can only
raise the segment peaks, so the reflector's motion costs the full CPI at most
about 1 dB against 13 ms, where the walk's way back lost 0.2 dB in its 16 ms
([CPI length](#cpi-length)). A reflector on a tripod loses nothing to it.

**The radar pointed the same way.** In the first run with each waveform,
directly after the placements, the radar's static scene is that of the
placements ([Field captures](#field-captures)): at the start and at the end of
each run, the median azimuth of its returns is within 0.3° and their median
level within 0.2 dB of the placements'. These two runs alone are 6.7–8.9 dB
below the tripod in the three bands. Before the second runs the radar was moved;
their reflector levels, 20.6–23.3 dB, are nevertheless close to the first
runs' 20.1–22.3 dB.

**How it was carried.** In the field runs the reflector stayed on its small
tripod, which the carrier held by a handle while running, aiming the
reflector at the radar as well as they could. Two carriers each ran with it,
and the four runs' band means lie within 20.1–23.3 dB. On the walk the
reflector was held in the hand, which may have given better control of its
aim.

**Reading.** With the same radar, pointed the same way, the same firmware,
waveforms and reflector, and within half an hour, carrying cost the reflector
7 dB against the tripod. On the walk, its way out was 11–14 dB below its way
back. Both sessions' runs went at about the same speed, the longer CPI costs
at most about 1 dB, and in the first runs the radar pointed as for the
tripod, which leaves the aim. An aim held 27–31° off the axis would do it
([The reflector's aim](#the-reflectors-aim)), for instance with one plate near
horizontal. That two carriers lost about the same points to the way it was
carried rather than to unsteady hands: carried by the tripod's handle, the
reflector's tilt follows how the tripod hangs. That it was the aim is the most
likely reading, not a measurement. Whatever the cause, a carried reflector's
level varies by more than the differences these notes look for, so carried
runs are no reference for absolute sensitivity. The walk's way back remains
the highest level of all, and since aim can only lose, it is the best-aimed
measurement we have; that it was well aimed is an inference, not a record.

## The receiver background

Away from strong returns, the remote-Doppler background holds the receiver's
noise. In the walk, window and field captures it rises towards low IF, by about
1.2 dB from 20 MHz down to 1 MHz. Two explanations were open. If it is IF gain
shape, signal and noise are shaped alike, and the SNR at a given range does not
depend on the beat frequency: for the walk, the local noise reference is right
(+0.7 dB over the model). If it is receiver noise that rises at low IF, a
target's SNR improves as its beat frequency rises, and noise taken from the far
quarter of the range spectrum is the better reference for high IF (+1.9 dB).
The datasheet's noise figure changes only 0.2 dB between 1 and 10 MHz at the
walk's RX gain.

A TX-off capture cannot decide, since both remain with TX off; what decides is
a signal of known level at different beat frequencies. The field captures
provide it ([Noise or gain shape: two
slopes](#noise-or-gain-shape-two-slopes)): between 1.25 and 5.3 MHz the excess
is noise, and from 7 to 14 MHz it is not, within the precision available. For
the walk this gives +0.7 dB at its own beat frequencies, +1.2 dB at 5.3 MHz and
+0.8 dB at 14 MHz ([The baseline difference](#the-baseline-difference)).

### Its shape and origin

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

**Window and field captures.** The channel-independent remote-Doppler floor
(|f_D| > 1 kHz), from the middle four eigenvalues of the 8×8 RX covariance in
each range bin, relative to its median over 18–24 MHz
([background.png](generated/window/scene/background.png),
[field_if.py](field_if.py), [if_test.png](generated/field/if/if_test.png),
left; the window rows are from 2026-09-30). A disturbance with one spatial
signature, such as a scene return, its pedestal or a vehicle, takes the
largest eigenvalue whatever its angle, which products between RX pairs would
not separate:

| Capture | TX | 0.7 MHz | 1 MHz | 2 MHz | 3.3 MHz | 6.6 MHz | 13 MHz | 18–24 MHz [dB ADC-count²/cell] |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Window: short-1TX-0dB | TX1 | 1.13 | 1.18 | 0.95 | 0.71 | 0.45 | 0.14 | −30.77 |
| Window: short-1TX-10dB | TX1, 10 dB backoff | 1.18 | 1.25 | 0.95 | 0.73 | 0.40 | 0.15 | −30.90 |
| Window: medium-1TX-0dB | TX1 | 1.14 | 1.26 | 1.01 | 0.76 | 0.53 | 0.21 | −30.84 |
| Window: medium-1TX-10dB | TX1, 10 dB backoff | 1.11 | 1.24 | 1.02 | 0.76 | 0.44 | 0.15 | −30.88 |
| Window: long-1TX-0dB | TX1 | 1.14 | 1.20 | 1.01 | 0.98 | 0.38 | 0.15 | −33.52 |
| Window: long-8TX-0dB (no scene) | TX1, as configured | 1.28 | 1.31 | 0.94 | 0.78 | 0.45 | 0.17 | −33.51 |
| Field: notx | none | 1.13 | 1.19 | 1.00 | 0.74 | 0.43 | 0.13 | −30.83 |
| Field: empty-medium | TX1 | 1.17 | 1.24 | 1.07 | 0.77 | 0.43 | 0.15 | −30.94 |
| Field: empty-short | TX1 | 1.15 | 1.23 | 0.94 | 0.67 | 0.39 | 0.09 | −30.90 |
| Field: sky-1tx | TX1 | 1.26 | 1.34 | 1.04 | 0.73 | 0.43 | 0.10 | −31.17 |
| Field: sky-8tx | 8TX, uncalibrated | 1.59 | 1.63 | 1.15 | 0.84 | 0.47 | 0.13 | −30.97 |
| Walk, over its far quarter | TX1 | | 1.5 | 1.2 | 0.9 | 0.5 | 0.2 | |

With no TX at all, the background has the same shape and level as with TX1,
within 0.1 dB. 10 dB less TX power changes the floor by at most 0.13 dB and
its shape by at most 0.1 dB, and a capture with no scene beyond 10 m has the
same floor as the one with the full scene. So the excess at low IF comes from
the receiver, not from the TX or anything reflected, and it has the walk's
shape, 0.2–0.3 dB lower at 1–2 MHz (with a different reference). The long
waveform's cells are 3 dB lower for the same noise (four times the samples,
half the chirps). Below about 0.5 MHz the high-pass filter takes over (6 m in
the medium waveform).

With all eight TX on, pointed at the sky, the background rises 0.3–0.5 dB
below 1 MHz, and a component common to the RX channels lifts the total
remote-Doppler power 0.27 dB above the independent floor at 1–10 MHz
(0.03 dB or less in the other field captures). In the window capture without
scene such a component lifts it 2.2 dB at all ranges. The chamber captures
show the mechanism: a strong return's high-offset phase-noise skirt, spread
over all ranges with the return's spatial signature, which for the window
capture's object within about 2 m predicts a lift of the right size ([A
strong return's phase-noise skirt](#a-strong-returns-phase-noise-skirt)).
The sky capture's 0.27 dB has not been examined further.

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
[Outdoor: against the CW datasheet](#outdoor-against-the-cw-datasheet)).

**Chamber captures, RX gain 0 dB** ([chamber_background.py](chamber_background.py),
[background.png](generated/chamber/background/background.png), left). The
same channel-independent floor, here over remote-Doppler cells at least 60 Hz
from every TX's line, as a density (`chamber_common.cell_to_density`), so
that captures with different sample rates, lengths and windows compare
directly; the other rows are the stored floors of the window and field steps:

| Capture | RX gain | 0.10–0.15 MHz | 0.3–0.5 | 0.8–1.2 | 1.8–2.2 | 4–7 | 7–10 | 10–12 MHz [dB ADC-count²/Hz] |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Chamber: TX1 | 0 dB | −62.36 | −57.45 | −56.68 | −57.01 | −57.47 | −57.66 | −57.76 |
| Chamber: eight TX in DDMA | 0 dB | −62.26 | −57.39 | −56.54 | −56.88 | −57.32 | −57.48 | −57.60 |
| Chamber: eight-TX beam | 0 dB | −62.10 | −57.33 | −56.49 | −56.78 | −57.24 | −57.44 | −57.53 |
| Window: long-8TX-0dB (the same firmware build) | +3 dB | −60.70 | −54.54 | −53.77 | −54.17 | −54.55 | −54.74 | −54.85 |
| Window: long-1TX-0dB | +3 dB | −60.95 | −55.05 | −53.88 | −54.06 | −54.51 | −54.79 | −54.89 |
| Window: medium-1TX-0dB | +3 dB | | −55.19 | −54.16 | −54.41 | −54.78 | −54.87 | −55.18 |
| Field: notx | +3 dB | | −55.19 | −54.22 | −54.41 | −54.92 | −55.10 | −55.21 |

From 0.3 to 12 MHz the chamber's floor lies 2.3–2.9 dB below that of the
+3 dB captures (mean 2.6 dB), 2.9 dB below the long waveform's with the same
firmware build. The datasheet's steps predict 2.5 dB: 3 dB less gain and a
typical noise figure 0.5 dB higher (Table 30). The rise towards low IF has the
same size at both gain steps, 1.0 dB from 7–10 MHz to 0.8–1.2 MHz, so the
excess scales with the gain step like the flat floor: it enters ahead of the
stage the step acts on. Below 0.3 MHz the chamber's floor falls less than the
others' and lies only 1.4–1.7 dB below them at 0.10–0.15 MHz: part of the
background there does not scale with the RX gain, as the two slopes found part
of it not shaped like a signal ([Noise or gain shape: two
slopes](#noise-or-gain-shape-two-slopes)). With all eight TX on, in DDMA or
as the beam, the floor is 0.1–0.3 dB higher than with TX1.

**Chamber, 2026-10-09, RX gain +3 dB** ([chamber_tx1.py](chamber_tx1.py)).
Three captures with no TX, over 15 minutes, have the same floor to 0.05 dB,
and it equals the field's TX-off capture of 2026-10-01 to 0.03–0.04 dB from 4
to 12 MHz (−54.9 dB ADC-count²/Hz at 4–7 MHz), so the receiver's noise did
not change in eight days. TX1 at 10 dB backoff, with the reflector 58 dB above
it per chirp and range bin, raises the channel-independent floor by 0.2 dB,
a little more than in the field. The two sample rates give the same floor with TX1 on, to
0.04 dB at 4–12 MHz. The board had been running for about 38 minutes when
the first capture began, so the series says nothing about warm-up.

The 2026-08-27 recording, the only other capture at the 0 dB step, lies 4.7 dB
above the +3 dB captures instead ([Out-of-window
captures](#out-of-window-captures)). With our firmware the 0 dB step does
what the datasheet says, so that recording's level does not come from the
gain step.

### Noise or gain shape: two slopes

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
for noise). So, relative to a target at 1.25 MHz, one at 5.3 MHz gets 0.8 dB
more SNR and one at 14 MHz about 0.5 dB more, if nothing changes between 5.3
and 7 MHz, where no pair is usable; relative to the walk's reflector, 0.47 and
0.13 dB more ([The baseline difference](#the-baseline-difference)). Below
1 MHz, a target at 0.3 MHz has about 2.4 dB less SNR, relative to one at
1.15 MHz, than the background's shape alone would suggest (T summed over the
two lowest pairs). For the walk (1.0–3.3 MHz) the local reference is the SNR
the reflector actually had; for long-range targets the model is up to about
0.5 dB further below the measurement, not the 1.2 dB the far quarter suggests.

### The high-pass filter

([chamber_tx1.py](chamber_tx1.py),
[tx1.png](generated/chamber/2026-10-09/tx1/tx1.png), left.) The CTRX8188F's
analog high-pass is of second order, specified at its −6 dB point: 300 kHz in
our host code's payload setting, ±10 % (target datasheet rev. 0.20,
Table 31). Two coincident first-order poles have their −6 dB point at the
poles' frequency (`chamber_common.high_pass_db`).

- **On the reflector in the chamber.** The same RF band, TX power and RX gain
  with two slopes put the reflector at 162 kHz and at 1.29 MHz; the first is
  12.25 dB weaker. The two sample rates involved (25 and 50 MS/s) give the
  same receiver noise to 0.04 dB, so the ratio is the filter's. Two poles at
  294 kHz reproduce it, inside the datasheet's tolerance. At the first
  chamber session's 181 kHz they give −11.3 dB.
- **From the two slopes in the field.** Chained over the clean pairs, the
  reflector's power changes give the IF response from 0.29 to 5.3 MHz
  relative to 2.5 MHz: −5.15 dB at 0.29 MHz, −1.56 dB at 0.57–0.59 MHz,
  −0.14 dB at 1.15–1.25 MHz and 0.00 dB at 2.65 and 5.3 MHz (`field_if.py`).
  Fitted alone (`chamber_common.fit_high_pass_corner`) they put the poles at
  265 kHz, with 0.10 dB rms. With 294 kHz the point at 0.29 MHz lies 0.8 dB
  above the curve, the others within 0.4 dB.

The chamber point is the direct measurement, so these notes use 294 kHz
wherever the filter's response is needed below 1 MHz.

**How it is set.** The cut-off is chosen per ramp segment from five discrete
values, `RX_HP_FC` 0–4 for 300, 600, 1200, 2400 and 4800 kHz; 4.8 MHz is not
allowed in payload segments and is recommended for the flyback (user manual
rev. 0.20, Table 120). `RX_HP_BOOST` shortens the filter's settling, and
according to the manual only in the segment where the cut-off switches from
its maximum back to the target. The manual models the filter's phase as
180° − 2 atan(f/f_c) (section 2.3.8.1), which is the two coincident poles
used here. `Get_RX_TF_Parameters()` returns each RX channel's deviation of
the cut-off from its nominal value, in percent, at two temperatures (Table
64); our firmware does not read it.

Our host tool (l2-sp `projects/psi/host/cmd/psi-streamer/waveform.go`, as of
2026-10-08) sets 300 kHz in the pre-payload, payload and wait and 4.8 MHz in
the flyback, with the boost in the pre-payload. The cut-off switches back to
300 kHz at the start of the wait, so by the manual's note the boost may have
no effect there; with waits of 3 µs or more, against the datasheet's settling
of up to 1.4 µs at 300 kHz ([The datasheet's ramp
timing](#the-datasheets-ramp-timing)), that should not matter. None of this is
in the sidecars, in either format: they record the RX gain step, not the
high-pass, so the settings come from the host code alone.

### Against the datasheet

**Concluded.** The CTRX8188F datasheet (Table 30) gives a typical total RX
SSB noise figure of 9.9 dB at 1 MHz and 9.7 dB at 10 MHz IF at the +3 dB RX
gain step (10.5 and 10.2 dB at 0 dB; the maximum rows differ by the same 0.2
and 0.3 dB). It specifies all TX off, no blocker and a 300 kHz high-pass:
the conditions of the field's TX-off capture and of our firmware. The two
slopes measure 0.83 dB of noise from 5.3 down to 1.25 MHz (T summed over the
two clean pairs, ±0.16 dB from their spreads over RX). That interval lies
inside the datasheet's 1–10 MHz, so if the noise figure falls steadily with
IF, no shape between the datasheet's two rows reconciles them: this unit's
noise figure rises at least about 0.6 dB more from 10 to 1 MHz than the
typical values say.

**Ruled out** as the cause of the rise:

- The transmitter and the scene. TX off, 10 dB backoff and no scene give the
  same floor ([Its shape and origin](#its-shape-and-origin)).
- A source common to the RX channels, such as phase noise on LO leakage or
  pickup from supplies and digital circuits. The excess lies in the
  channel-independent floor of the window and field captures, and in the walk
  it is uncorrelated between channels (|coherence|² 0.0005, against 0.05 if it
  were common).
- A transient at the start of each payload, such as the high-pass or the
  synthesizer still settling after the flyback. A transient over within the
  payload has the same energy per range cell whatever the payload's length,
  while the noise per cell grows with it, so a 41 µs payload would show a
  quarter of the excess: about 0.35 dB at 1 MHz where the 10.24 µs payloads
  show 1.18–1.26 dB. The two long-waveform captures, with the same 4 µs
  pre-payload, show 1.20 and 1.31 dB.

**What remains** is stationary noise from each receiver chain that rises
towards low IF: in effect a higher noise figure there.

**Open: this unit or the datasheet.** Infineon's typical values are for a
nominal part at room temperature ([Loss terms](#loss-terms)), and rev 0.20
is a target datasheet, whose values may be design targets rather than
characterisation. A receiver's rise towards low IF usually comes from
flicker-type noise in the mixer and baseband, which tends to vary more
between parts and with temperature than the flat floor. We have one unit,
and its die temperature in the closed housing is not known. The difference
matters only for targets at low IF; the Lannik Psi use cases lie at
6.7–10.7 MHz. Question 5 and measurement 4.

## The per-chirp frequency error

A strong return raises the remote-Doppler background at its own range: a ridge
along Doppler in the range–Doppler map. Every dataset here shows that it is a
phase error per chirp, proportional to the return's round-trip delay τ:
δφ = 2πτδf, with one frequency error δf per chirp shared by all returns and RX
channels. A return's phase in the range spectrum is the weighted mean of its
phase over the sampled payload, with the range window as weights, so δf is the
LO's frequency error averaged in the same way. Values of δf are rms over chirps
in the slow-time band given.

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
| Window 10-06, ten timings | Ours | 0.02–6 µs; 9.2–85.7 µs | 11.67 MHz/µs | 3.23–10.0 kHz | 0.5 kHz to 5–19.6 kHz | Same, fixed mount |

Over 0.5 kHz to PRF/2, each band covers nearly all of the per-chirp variance.
The 5–31 kHz values of the earlier captures are 1–2 % below their 0.5–31 kHz
values (a one-off check). Within a firmware the slope changes by a factor of 8
(Infineon's, at 5.54 µs) or 2 (ours) without a matching change in δf. Timing
jitter between ramp and ADC, or ADC sampling jitter, would make the error scale
with slope (or with beat frequency), so neither fits. Between the firmwares, δf
differs by 16 dB at nearly the same pre-payload, 4.2 and 4.0 µs ([Window: the
MMIC programming sets the error](#window-the-mmic-programming-sets-the-error)),
and the time between ramps accounts for it ([Window: the chirp timing sets the
error](#window-the-chirp-timing-sets-the-error)).

The walk and the outdoor captures, both with Infineon's firmware, show what
kind of error it is: an LO error, pure phase and shared by all returns, here
at 14–19 kHz, 12–17 dB above what the CW datasheet predicts. The window
captures show that the MMIC's programming sets its size: with our firmware it
is at the CW level, it follows the delay law to 270 m, and a longer payload
averages it down. The timing test shows that the time between ramps sets it,
and that too little of it explains the error with Infineon's firmware. The
last two subsections relate this to the datasheet's ramp timing and give the
consequences at long range.

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
remote-Doppler excess fully correlated between RX channels. The component
along the reflector's steering vector in the chamber is a different effect:
the reflector's high-offset skirt, at every range rather than its own ([A
strong return's phase-noise skirt](#a-strong-returns-phase-noise-skirt)).

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
2.4 dB. The window captures extend the law to 270 m with our firmware ([Window:
the delay law and the payload
length](#window-the-delay-law-and-the-payload-length)), where the per-chirp
quantity, averaged over the payload, saturates by only about 0.5 dB.

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

### Outdoor: against the CW datasheet

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
19.0 kHz against 2.64 kHz, a one-off calculation). The CW prediction's spectrum
is flat over slow-time frequency; the measured one rises.

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
firmware; with ours the per-chirp error is at the table's level ([Window:
against the CW table](#window-against-the-cw-table)).

### Window: method and results

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
| 2026-10-02, medium (3 cases) | 5–13 per case, 27–284 m | 128 | **3.09 kHz (3.01–3.18)** | 2.0–4.1 mrad |
| 2026-10-02, short (2 cases) | 5–12 per case, 24–129 m | 67 | **3.61 kHz (3.49–3.70)** | 2.8–5.0 mrad |
| 2026-10-06, PRI 100 µs | 9 of 11, 27–236 m | 33 | 3.35 kHz (3.20–3.51) | 3.0 mrad |
| 2026-10-06, PRI 50 µs | 9 of 10, 27–236 m | 34 | 3.23 kHz (3.13–3.33) | 3.6 mrad |
| 2026-10-06, eight shorter timings | 8–11 per case | 28–53 per case | 4.2–10.0 kHz | 0–3.1 mrad; see [Window: the chirp timing sets the error](#window-the-chirp-timing-sets-the-error) |

CPIs flagged as interfered are dropped
([Interference from other radars](#interference-from-other-radars)): 3 in
medium-8TX-0dB-highway and 23 in the Infineon recording. Keeping them changes
the pooled and Infineon values by at most 0.5 kHz, to 3.47, 30.0 and
21.2 kHz.

The captures spread over 3.1–4.1 kHz, more than the bootstrap intervals, since
scene and returns differ between them. 1TX and 8TX coherent agree within that
spread, as a shared LO requires; independent errors in the eight TX paths
would be averaged down by the coherent sum. The highway capture is dominated
by traffic (8 of 16 returns fail the clean test) and is not used for
conclusions. In Infineon mode 0 all returns but one fail the clean test at the
coarser 1.75 m cells; its pair mean over all returns stands in. Its pairs give
15–30 kHz, 21–29 kHz where the two returns correlate well.

One of the late hand-held captures carries a common phase of 6 mrad rms above
500 Hz (1.8 µm). The fixed mount of 2026-10-02 does not remove it: its cases
give 2.0–5.0 mrad (0.6–1.6 µm), with p5–p95 above zero in four of five. So it
is not only the radar moving in the hand; vibration of the mount or the
building, or a phase added to the TX or RX path after the LO is split off,
would give the same. It does not enter δf, and at a few mrad it costs no
sensitivity.

### Window: against the CW table

The prediction for these waveforms (as outdoors, now
`carkit_common.per_chirp_frequency_psd`) is 2.69–2.71 kHz typical with the
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
begins. The timing test with our firmware shows the same rise wherever a short
gap raises δf ([Window: the chirp timing sets the
error](#window-the-chirp-timing-sets-the-error)).

### Window: the delay law and the payload length

**Delay law.** Medium, pooled, by the pair's farther return, with each
capture's common phase removed:

| Farther return | Pairs, 2026-09-30 | δf rms | Pairs, 2026-10-02 | δf rms |
|---|---:|---:|---:|---:|
| 10–60 m | 5 | 2.69 kHz | 3 | 3.32 kHz |
| 60–130 m | 66 | 3.51 kHz | 34 | 3.32 kHz |
| 130–200 m | 63 | 3.56 kHz | 21 | 3.28 kHz |
| 200–290 m | 112 | 3.42 kHz | 70 | 3.04 kHz |

δf is the same within ±0.1 kHz from 60 to 290 m on 2026-09-30, τ up to
1.9 µs, and within 0.3 kHz on the fixed mount of 2026-10-02. Its drop beyond
200 m, 0.35 and 0.7 dB, is about what the CW model's own saturation gives:
0.5 dB at 270 m for a return's own δf, about half of that for pairs with one
far return. The few pairs within 60 m give less on 2026-09-30 but not on
2026-10-02 (short waveform: 2.14 and 3.07 kHz from 9 and 6 pairs).

A free exponent comes out slightly positive: γ = +0.10 (0.07–0.14) here,
+0.09 (0.05–0.10) on 2026-10-02 and +0.08 (0.072–0.096) for Infineon's mode 1
over 21–175 m, which would make phase power grow as τ^2.2 at most. Saturation
would make it negative, so it does not come from there. The exponent trades
off against the common phase, which weighs most at short delay, and where the
returns span less than a decade of delay, as in the short waveform, it is not
determined (+0.27, 0.09–0.46; −0.03 on 2026-10-02). The binned table is
therefore the delay-law result.

**Payload length.** The long waveform (41 µs payload, PRI 90 µs) gives at
most 0.56 kHz (p95) over 8 pairs at 14–273 m. The typical tables predict
0.43–0.51 kHz and the maxima 0.82–0.91 kHz. Averaging over the longer payload
removes more of the LO's frequency noise; an error that is constant over each
chirp would not be reduced.

### Window: the MMIC programming sets the error

Same unit, same window, same 10.24 µs payload (short and medium) and 50 MS/s
sampling. The MMIC is programmed differently (see [Firmware](#firmware)):

- Infineon's configurations follow each ramp with 60 ns flyback and 60 ns
  wait, so the next ramp starts almost at once, with 3.54–5.54 µs of
  pre-payload. Their δf falls as the pre-payload grows: 30 and 22 kHz at 3.54
  and 4.2 µs, in alternating frames of one recording, and 14–19 kHz at
  5.54 µs, in other captures with other sweeps.
- Ours has 2 µs flyback, 84 µs wait (43 µs in the long waveform) and 4.0 µs
  pre-payload, and gives 3.1–3.6 kHz.

The pre-payload alone therefore does not set δf. The flyback, the wait, the
DPLL settings or the MMIC's RAM firmware might; DDMA is not the cause, since
the walk and outdoor captures used TX1 alone. The timing test (next
subsection) shows that the time between ramps does, and that it accounts for
Infineon's δf without the other candidates.

### Window: the chirp timing sets the error

**Method** ([window_timing.py](window_timing.py),
[timing.png](generated/window/2026-10-06/timing/timing.png)). The ten cases of
2026-10-06 ([Out-of-window captures](#out-of-window-captures)) go through
window_scene.py and window_phase.py like any recording. window_timing.py adds
the cross-return slow-time spectrum at full resolution, over the same clean
returns and pairs with the same weights (its sum over the band reproduces
window_phase.py's pair mean exactly), and a fit of δf against the timing. Two
times describe a case: T_fast, the flyback and wait, which the synthesizer
spends in fast-settling mode between payloads, and T_pre, the pre-payload, the
unsampled start of the next ramp in linear mode. The spectrum's tilt is its
mean density from PRF/4 to PRF/2 over that from 500 Hz to PRF/4: 0 dB for a
white sequence, such as the CW phase noise gives, positive where successive
chirps' errors partly cancel.

| Case | Pre-payload | Flyback + wait | PRI | Clean returns, pairs | δf rms (p5–p95) | Fit | Spectrum tilt | Coherence loss at 1 km |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| medium-PRI100 | 4 µs | 2 + 83.72 µs | 100 µs | 9, 33 | 3.35 kHz (3.20–3.51) | 3.28 kHz | −0.1 dB | 0.09 dB |
| medium-PRI50 | 4 µs | 2 + 33.72 µs | 50 µs | 9, 34 | 3.23 kHz (3.13–3.33) | 3.29 kHz | +0.2 dB | 0.08 dB |
| medium-PRI30 | 4 µs | 2 + 13.72 µs | 30 µs | 10, 43 | 4.20 kHz (4.05–4.36) | 4.20 kHz | +1.1 dB | 0.13 dB |
| medium-PRI25 | 4 µs | 2 + 9.22 µs | 25.5 µs | 10, 43 | 5.89 kHz (5.70–6.10) | 6.01 kHz | +2.6 dB | 0.26 dB |
| medium-PRI25-flyback20ns | 4 µs | 0.02 + 11.2 µs | 25.5 µs | 11, 52 | 5.86 kHz (5.76–5.97) | 6.01 kHz | +2.8 dB | 0.26 dB |
| medium-ramp4000ns | 4 µs | 1 + 10.22 µs | 25.5 µs | 11, 53 | 6.18 kHz (6.04–6.31) | 6.01 kHz | +2.7 dB | 0.29 dB |
| medium-ramp6000ns | 6 µs | 1 + 8.22 µs | 25.5 µs | 8, 28 | 5.11 kHz (4.91–5.27) | 4.95 kHz | +1.8 dB | 0.20 dB |
| medium-ramp2000ns | 2 µs | 1 + 12.22 µs | 25.5 µs | 9, 34 | 7.42 kHz (7.22–7.63) | 7.57 kHz | +3.2 dB | 0.42 dB |
| medium-PRI25-ramp20ns | 0.02 µs | 2 + 13.2 µs | 25.5 µs | 9, 34 | 9.77 kHz (9.54–9.98) | 9.79 kHz | +3.5 dB | 0.73 dB |
| medium-PRI25-ramp20ns-flyback20ns | 0.02 µs | 0.02 + 15.18 µs | 25.5 µs | 11, 52 | 10.00 kHz (9.71–10.31) | 9.79 kHz | +3.5 dB | 0.76 dB |

The CW prediction changes by only 4 % between these PRIs (2.70–2.81 kHz
typical with the 76–77 GHz table, 3.36–3.50 kHz with the 77–81 GHz table).
The coherence loss is the toolbox's `SystemLosses.coherence_loss_db` for each
case's δf.

- **The flyback's own length does not matter.** At 4 µs pre-payload and
  11.2 µs of flyback and wait, a 2 µs, 20 ns or 1 µs flyback gives 5.89, 5.86
  and 6.18 kHz, and at 20 ns pre-payload a 2 µs or 20 ns flyback gives 9.77
  and 10.00 kHz. The spread within these groups, 2.6 % pooled, is larger than
  the bootstrap intervals and is what a repeated capture differs by here.
- **The time in fast-settling mode does.** At 4 µs pre-payload, 85.7, 35.7,
  15.7 and 11.2 µs of flyback and wait give 3.35, 3.23, 4.20 and 5.89 kHz. The
  rise begins between 36 and 16 µs, far beyond the datasheet's 1 µs.
- **So does the pre-payload.** At 25.5 µs, where every case has 15.2 µs
  between payloads, pre-payloads of 0.02, 2, 4 and 6 µs give 9.8–10.0, 7.4,
  5.9–6.2 and 5.1 kHz, although each microsecond of pre-payload is taken from
  the wait.
- **It is the same kind of error as with long gaps and with Infineon's
  firmware.** Pairs whose farther return lies at 60–130 m and at 200–290 m give
  the same δf within 5 % in every case (γ = 0.01–0.25), so the delay law holds
  for the excess too. The spectrum is white with long gaps (tilt −0.1 and
  +0.2 dB) and tilts towards PRF/2 as δf grows (+1.1 to +3.5 dB), as
  Infineon's does ([Window: against the CW table](#window-against-the-cw-table));
  no line stands out ([timing.png](generated/window/2026-10-06/timing/timing.png),
  right).

**Fit.** carkit_common.SettlingFit, weighted by each case's bootstrap interval
combined with the 2.6 % repeatability:

  δf² = δf₀² + A exp(−T_fast/τ_fast − T_pre/τ_pre)

gives δf₀ = 3.28 kHz (p5–p95 3.15–3.42), τ_fast = 3.4 µs (2.7–4.4),
τ_pre = 1.68 µs (1.48–1.89) and √A = 85 kHz, with a reduced χ² of 0.71. The
excess variance therefore halves with every 2.4 µs of flyback and wait, or
every 1.2 µs of pre-payload: a microsecond of pre-payload is worth about two
in fast-settling mode. The floor lies between the CW typical values of the
two tables. The exponential is the simplest form that fits all ten cases; the
data do not test it below 9.2 µs of flyback and wait or beyond 6 µs of
pre-payload. Within that range, δf comes within 10 % of the floor at 23.6,
19.5 and 15.4 µs of flyback and wait (p5–p95 21.0–26.1, 17.3–21.5 and
13.7–16.9 µs) for pre-payloads of 2, 4 and 6 µs, chirp periods of 35.9, 33.8
and 31.7 µs with this payload.

**Extrapolated to Infineon's timing.** Infineon's configurations have 0.12 µs
of flyback and wait, 9 µs less than any case here:

| Capture with Infineon's firmware | Pre-payload | Measured δf | Fit, extrapolated (p5–p95) |
|---|---:|---:|---:|
| Window 2026-08-27, mode 1 | 3.54 µs | 29.8 kHz (29.5–30.1) | 29.2 kHz (19.5–43.0) |
| Window 2026-08-27, mode 0 | 4.2 µs | 21.7 kHz (20.8–22.4) | 24.1 kHz (16.4–34.5) |
| Outdoor captures, reflector | 5.54 µs | 13.8–16.9 kHz (four captures) | 16.3 kHz (11.7–22.3) |

The walk, at the outdoor captures' timing, gave 16.9 and 19.0 kHz. No
Infineon data enter the fit, yet every measured value falls inside its
interval, near the middle. Infineon's captures differ in more than the
timing: chirp periods of 14–16 µs, 76.2–76.7 GHz, other slopes, DDMA on
2026-08-27, and DPLL settings and MMIC RAM firmware that are not recorded. So
the time between ramps suffices to explain Infineon's δf, without ruling out
contributions from the rest. By the same fit (`predictions` in the step's
summary), lengthening Infineon's flyback to the datasheet's 1 µs would barely
help (21 kHz at 4.2 µs pre-payload), while 10 µs of wait would bring it to
6.5 kHz and 20 µs to 3.5 kHz.

**Not separated.** At a fixed payload the chirp period and the time in
fast-settling mode change together, and the host tool's CSI-2 rule places the
transfer of each chirp's data in the gap between payloads, which it may fill
at 25.5 µs ([Firmware](#firmware)). If that transfer disturbed the
synthesizer while it settles, a short period would also be worse. It cannot
explain the pre-payload series, where the gap is the same in every case, nor
Infineon's δf, but it may add to the chirp-period series; a different CSI-2
lane rate at fixed timing would show it (measurement 2). The sampled ramp was
10.24 µs throughout; whether a longer one settles in the same time is not
measured.

### The datasheet's ramp timing

The CTRX8188F target datasheet (rev. 0.20, 2025-06-17) and user manual
(rev. 0.20, 2025-11-10) give limits for the ramp segments. Both are
NDA-restricted and kept outside the repo (`~/Git/docs/Infineon/CTRX8188F`).
The toolbox's phase-noise table is the datasheet's Table 22, which is
specified in CW mode.

| Segment | Datasheet or user manual | Infineon's configurations | Ours |
|---|---|---|---|
| Flyback | Up to 1 µs until the frequency is within ±500 kHz of the next start frequency, for a 4 GHz step; up to 15 MHz overshoot or undershoot with a 1 µs flyback (datasheet Table 23) | 60 ns | 2.0 µs; 20 ns–2 µs in the timing test |
| Wait | DPLL in fast-settling mode during flyback and wait, linear mode from pre-payload to post-payload (user manual Table 120) | 60 ns | 84 µs before the timing test, 8.2–84 µs in it; at least 3 µs |
| Pre-payload | TX settling up to 1.5 µs from the start of the chirp until the ramp meets its linearity requirement (Table 23); RX settling between ramps up to 1.4 µs at a 300 kHz high-pass | 3.54–5.54 µs | 4.0 µs; 0.02–6 µs in the timing test |
| High-pass during the payload | 300–2400 kHz; 4.8 MHz is not allowed during payloads and is recommended during the flyback (Table 120) | Code 0 (walk, outdoor); code 4 on 2026-08-27 | 300 kHz |

Infineon's configurations leave the synthesizer about 120 ns in
fast-settling mode before it switches to linear mode for the next ramp. The
datasheet allows up to 1 µs just to come within ±500 kHz of the start
frequency. The timing test shows that what matters settles far more slowly:
the excess error halves only every 2.4 µs of flyback and wait, or every 1.2 µs
of pre-payload, and reaches the CW level after about 15–25 µs ([Window: the
chirp timing sets the error](#window-the-chirp-timing-sets-the-error)). That
is not what the datasheet's flyback specification describes, and the
datasheet says nothing about variation from chirp to chirp.

The size of the frequency step matters less than the time. At a 5.54 µs
pre-payload with Infineon's firmware, δf is 17–19, 17 and 14 kHz for steps of
0.16 GHz (walk) and 0.6 and 1.2 GHz (outdoors). In the timing test the step
grows with the pre-payload, from 120 to 190 MHz, while δf falls.

If RadarGUI's high-pass codes are the user manual's `RX_HP_FC` values, the
2026-08-27 configuration used the 4.8 MHz setting during the payload, which the
manual does not allow. The steep fall of those captures' floor below about
40 m in mode 1 and 90 m in mode 0 fits it. It does not explain the per-chirp
error, which the walk and outdoor captures show at 300 kHz.

### Consequences at long range

For a weak target its own pedestal is negligible against the noise; what the
error costs it is coherent gain. With enough time between ramps, δf ≈ 3.5 kHz
gives a per-chirp phase of 0.15 rad rms at 1 km (τ = 6.7 µs) if the delay law
holds that far. Here it holds to 270 m. That is about 0.1 dB of coherent loss
(the toolbox's `SystemLosses.chirp_frequency_error_rms_hz` term, which uses
this law), and in fact less, since for phase noise the delay-squared law is
the small-fτ limit of 4 sin²(πfτ); at 1 km it is reduced by 0.6, 1.7 and
3.9 dB at 30, 50 and 75 kHz. A longer payload lowers it further: the long
waveform's 0.5 kHz gives 0.02 rad at 1 km. At the shortest chirp period our
firmware allows for the medium waveform, 25.5 µs, δf = 5.9 kHz gives 0.25 rad
and 0.26 dB, and raises the pedestal around strong returns by 5 dB; with a 20 ns
pre-payload there, 10 kHz gives 0.75 dB. With Infineon's timing (14–30 kHz) it
would be 0.6–1.3 rad at 1 km, up to 1.5–7 dB of coherent loss and a large
pedestal around strong returns. For Psi, the time between ramps (flyback,
wait, pre-payload) is therefore part of the waveform design: with a 10 µs
payload, 15–25 µs of flyback and wait, depending on the pre-payload, keep δf
at the CW level ([Window: the chirp timing sets the
error](#window-the-chirp-timing-sets-the-error)).

## A strong return's phase-noise skirt

([chamber_background.py](chamber_background.py),
[background.png](generated/chamber/background/background.png), middle and
right.) Within a chirp a return's beat signal carries the LO's phase noise
filtered by its delay τ: 4 sin²(πfτ) times the LO's spectrum at offset f.
The per-chirp error of the previous section is the low-offset part, averaged
over the payload. The part more than a range cell from the carrier lands in
other range cells, at every range, and is independent from chirp to chirp:
a floor, white over Doppler, that carries the return's spatial signature in
the RX channels, since they share the LO. A weak target's skirt is far below
the noise. A strong return near the radar can raise the floor everywhere.

### The chamber reflector's skirt

Beyond a few metres the chamber holds nothing, so the background there is the
receiver's noise and what the reflector adds. Per range bin, the 8×8 RX
covariance over remote-Doppler cells splits into the channel-independent floor
(the middle four eigenvalues, as in [Its shape and
origin](#its-shape-and-origin)) and a common part above it
(`chamber_common.background_split`). By offset from the reflector's beat
frequency, in both sessions (the second at 10 dB more TX power; its
TX1-alone stage failed and is left out):

| Offset [MHz] | 0.3–0.5 | 0.5–1 | 1–2 | 2–4 | 4–7 | 7–10 | 10–12 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Common part over the independent floor [dB], 2026-09-29: TX1 (reflector 27.2 dB ADC-count² per chirp) | 0.02 | 0.01 | 0.01 | 0.01 | 0.03 | 0.02 | 0.02 |
| Eight TX in DDMA (37.1 dB) | 0.62 | 0.36 | 0.20 | 0.18 | 0.17 | 0.18 | 0.20 |
| Eight-TX beam (46.1 dB) | 4.00 | 2.86 | 2.13 | 1.90 | 1.85 | 1.95 | 2.01 |
| 2026-10-09: eight TX in DDMA (46.6 dB) | 4.45 | 3.20 | 2.48 | 2.14 | 2.15 | 2.26 | 2.33 |
| Eight-TX beam (55.7 dB) | 12.04 | 10.13 | 8.70 | 8.19 | 8.21 | 8.41 | 8.60 |
| Alignment of its top eigenvector with the reflector's per-RX amplitudes (1: the same), beam, 2026-09-29 | 0.95 | 0.89 | 0.81 | 0.78 | 0.77 | 0.76 | 0.76 |
| The same, 2026-10-09 | 0.96 | 0.86 | 0.77 | 0.72 | 0.71 | 0.71 | 0.71 |

The common part grows with the reflector's power and has its signature.
From TX1 to the beam on 2026-09-29 the reflector gains 19 dB, and its common
part rises from about 23 dB below the receiver noise to 2.5 dB below it; with
the beam 10 dB stronger on 2026-10-09 it stands 7.6 dB above it. Under DDMA
the reflector's per-chirp power is the sum of the eight TX's, and the skirt
follows that sum from chirp to chirp. With TX1 the common part is too small
for its alignment to mean anything (0.14–0.51). The alignment is highest near
the reflector, possibly because the channels' IF responses at the
reflector's low beat frequency, inside the high-pass, differ slightly from
those at several MHz.

**Against the CW table.** Relative to the reflector's power per chirp and per
hertz of the range bin's noise bandwidth (24.5 kHz), the common part is the
skirt's density. The high-pass cuts the reflector by 11.3 dB (181 kHz) and
12.7 dB (162 kHz) but not the skirt beyond 1 MHz ([The high-pass
filter](#the-high-pass-filter)), so the ratio is corrected for both; with the
nominal 300 kHz instead of the measured 294 kHz the values below are 0.2–0.3 dB
lower. The prediction is the toolbox's CTRX8188F CW table (target datasheet
rev. 0.20, Table 22, TX port), the mean of its two RF bands, since the sweep
spans 76.55–77.45 GHz, delay-filtered for the reflector's range, with both
sidebands of the real beat signal, which land at the same IF
(`chamber_common.real_tone_skirt`):

| Offset [MHz] | 0.3–0.5 | 0.5–1 | 1–2 | 2–4 | 4–7 | 7–10 | 10–12 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-09-29, beam [dBc/Hz] | −113.2 | −116.3 | −118.7 | −119.9 | −120.3 | −120.2 | −120.2 |
| 2026-09-29, DDMA | −114.2 | −117.7 | −121.0 | −122.2 | −122.6 | −122.5 | −122.3 |
| CW table at 2.46 m, typical | −115.6 | −115.7 | −116.3 | −117.1 | −117.7 | −117.6 | −117.6 |
| CW table at 2.46 m, maximum | −112.1 | −112.5 | −112.6 | −112.7 | −112.5 | −111.8 | −111.5 |
| 2026-10-09, beam | −113.8 | −117.0 | −119.6 | −120.7 | −121.0 | −121.0 | −120.8 |
| 2026-10-09, DDMA | −114.1 | −117.4 | −119.9 | −121.1 | −121.4 | −121.3 | −121.3 |
| CW table at 2.21 m, typical | −116.6 | −116.6 | −117.2 | −118.0 | −118.6 | −118.5 | −118.5 |
| CW table at 2.21 m, maximum | −113.0 | −113.5 | −113.6 | −113.6 | −113.4 | −112.7 | −112.3 |

- **It is the LO's phase noise.** Relative to the reflector, the skirt is the
  same within 0.5 dB in the second session for DDMA and the beam, whose
  reflector differs by 9 dB, and within 0.9 dB between the sessions' beams.
  The first session's DDMA, where the common part lies only 0.2 dB above the
  receiver noise, comes out 2 dB lower; TX1's is at the noise of the estimate.
  The skirt is flat from 1 to 12 MHz, which is what the delay filter, rising
  as f², makes of an LO spectrum falling as 1/f². Noise that the TX and RX do
  not share, and so is not delay-filtered, would follow the table itself,
  which falls by about 18 dB from 1–2 to 10–12 MHz.
- **At the datasheet's level.** From 2 to 12 MHz it lies 2.3–3.1 dB below the
  typical CW values in the second session and with the first session's beam.
  At 0.3–0.5 MHz it lies between the typical and maximum values. There the
  table has no point between 0.1 and 1 MHz, and its log interpolation need
  not follow the synthesizer's loop. This agrees with the per-chirp error,
  which is at the CW level with enough time between chirps.
- **The per-chirp error plays no part here.** It grows with the delay: at
  2.46 m even Infineon's 30 kHz would give 3 mrad per chirp. The reflector's
  phase drifts slowly, by 0.6–1.4° over the ten CPIs of a case, which the
  remote-Doppler cells leave out.

### Coherent channel summation against it

Summing the eight RX coherently, with equal-gain phases towards the reflector
(`chamber_common.coherent_rx_gain_db`), gains against this background:

| Offset [MHz] | 0.3–0.5 | 0.5–1 | 1–2 | 2–4 | 4–7 | 7–10 | 10–12 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-09-29: TX1 [dB] | 8.6 | 8.8 | 8.9 | 8.9 | 8.9 | 8.8 | 8.9 |
| Eight TX in DDMA | 6.3 | 7.2 | 7.7 | 7.9 | 7.9 | 7.8 | 7.8 |
| Eight-TX beam | 2.7 | 3.7 | 4.6 | 4.9 | 5.0 | 4.9 | 4.8 |
| 2026-10-09: eight TX in DDMA | 2.8 | 3.8 | 4.7 | 5.0 | 5.1 | 5.0 | 4.9 |
| Eight-TX beam | 1.5 | 2.2 | 2.7 | 3.0 | 3.0 | 3.0 | 3.0 |

Against independent noise eight RX gain 9.0 dB, against a background with the
reflector's own signature 0 dB, and with a common part c per RX relative to
the independent noise, 8(1 + c) / (1 + 8c) (`test_chamber_common.py`). The
same reflector thus gives anything from 1.5 to 8.9 dB, depending only on how
strong its return is against the receiver's noise. The 7.1 dB in Viktor's
report, from the same chamber with a background whose dominant mode had the
reflector's signature, lies in this range. A channel-summation gain measured
in a chamber therefore says nothing about the gain against thermal noise, the
one that matters for range; there, eight RX give 9.0 dB.

The calibration routine's own check runs into the same thing. The record of
the same chamber on 2026-09-29 at 12:19 (l2-sp
`projects/psi/firmware/host/calibrations/lab-77ghz-20260929.json`) passed its
phase check but failed its SNR-gain check: 6.4 dB from TX1 and one RX to the
eight-TX beam and eight RX combined, against 28.9 dB expected. Its noise is
the chirp-to-chirp fluctuation at the reflector's own range (the host tool's
description), which the reflector's own skirt and slow drift dominate once the
reflector is strong, so the check measures the reflector rather than the
receiver.

### Near returns out of the window

The window capture with no scene beyond 10 m, `long-8TX-0dB` (which ran
TX1), has a common part 2.2 dB above its independent floor at 1–10 MHz, where
`long-1TX-0dB` has 0.04 dB ([Its shape and origin](#its-shape-and-origin)).
Its static profile shows one strong near return: 26.7 dB ADC-count² per chirp
at 1.54 m, against 10.8 dB at 3.38 m, the strongest within 0.5–10 m in
`long-1TX-0dB`. Taken as one return, with its level before the high-pass from
the measured corner and the typical CW table, its skirt predicts:

| Assumed range (± half a 1.23 m range bin) | 0.92 m | 1.54 m | 2.15 m |
|---|---:|---:|---:|
| Beat frequency | 18 kHz | 31 kHz | 43 kHz |
| High-pass at it | −48.3 dB | −39.5 dB | −33.7 dB |
| Predicted common part, `long-8TX-0dB` (measured 2.2 dB) | 7.6 dB | 4.3 dB | 2.7 dB |

For `long-1TX-0dB` the same gives 0.03–0.06 dB (measured 0.04 dB). The
mechanism accounts for the difference between the two captures and for the
size of the lift. The number itself depends on where in its range bin the
near object sits, and on the high-pass far below the lowest point measured.

## Scale, gain and interference

### Range scale

([window_range_scale.py](window_range_scale.py),
[range_scale.png](generated/window/range_scale/range_scale.png).) Range comes
from the beat frequency, so an error in slope or sample rate scales it. A
vehicle's Doppler speed depends only on the carrier frequency, and the board
starts the CPIs every 100 ms. Moving targets are tracked by range over the CPIs
of the 2026-09-30 captures, their Doppler is unwrapped against the range rate,
and the apparent range is fitted against the Doppler-integrated distance; the
slope of that fit is the range scale. The 16 tracks with at least five CPIs,
beyond 60 m and within 15 cm rms give a median of 1.002, and the 13 of them
within 0.1 of it a weighted mean of 1.002 (p5–p95 0.997–1.010 from resampling
the tracks). Nearer vehicles are excluded, since they turn and their strongest
scatterer moves along the body. Our host code's slope, frequency, timing and
decimation encodings follow the user manual's equations exactly, so a correct
scale is what the code predicts.

### TX backoff and the coherent eight-TX beam

"8TX" is all eight transmitters with the calibration's phases and no phase
step: a TX beam towards boresight. On 2026-09-30, with the radar held by hand,
8TX was −6 to +12.7 dB relative to TX1 at matched static returns (ideally up
to +18 dB at the beam's peak), and 10 dB backoff lowered them by 7–15 dB
(median 13 dB in the medium waveform, 11–12 dB in the short). With the
pointing changing between captures, neither is a finding about the hardware.
The fixed mount of 2026-10-02 settles both ([window_scene.py](window_scene.py)
with `--level-pairs`):

- 10 dB backoff lowers matched static returns by a median of 9.93 dB in the
  medium waveform (10 returns) and 9.98 dB in the short (14), all within
  8.7–11.1 dB but for one weak medium return near the noise. The datasheet
  allows ±2 dB for a reduction of 6–12 dB at constant junction temperature
  (Table 24).
- The calibrated 8TX beam adds 17.5 dB at the strongest return (27 m) and
  15.2 dB at 34 m, against 18.1 dB at the beam's peak for eight equal,
  perfectly phased TX; at the other returns, presumably off the beam, it adds
  2–11 dB (median 8.9 dB over all 10).

The chamber captures check the backoff and the beam on the reflector the beam
was calibrated on ([chamber_tx1.py](chamber_tx1.py),
[chamber_channels.py](chamber_channels.py),
[channels.png](generated/chamber/2026-10-09/channels/channels.png), left):

- **Backoff.** On 2026-10-09, TX1 at 0 and 10 dB backoff with the same
  waveform gives the reflector 9.73 dB apart.
- **TX powers.** Under DDMA each TX's return is separated by its phase step
  (`chamber_common.per_tx_amplitudes`; the phase a TX's shifter adds shows
  with the opposite sign in our range bins, as the host tool's sub-band order
  in the new sidecars confirms). At 10 dB backoff, TX2–TX8 relative to TX1
  match the report's Table 2 (the same chamber, Infineon's firmware, 20 dB) to
  0.20 dB rms with a mean offset of −0.18 dB. At 20 dB, on 2026-09-29, they
  matched it as closely relative to each other but stood 1.25 dB higher
  against TX1: the backoff outside the specified range, or that session,
  moved TX1 against the rest. These are powers at the reflector, so they
  include each TX's geometry towards the receivers at short range, about half
  of their spread ([A reflector at short range](#a-reflector-at-short-range)),
  and each TX's antenna pattern; they say nothing about the TX powers at full
  power.
- **Beam.** Over TX1's line in DDMA the beam adds 19.14 dB on 2026-09-29 and
  17.90 dB on 2026-10-09; the DDMA amplitudes with the phases applied predict
  19.11 and 17.83 dB, the most these amplitudes can give in phase. On
  2026-09-29 TX1 alone was 0.24 dB stronger than its line in DDMA, and the
  beam 18.90 dB above it. On 2026-10-09 the routine's TX1-alone stage failed
  ([Chamber captures](#chamber-captures)).

### Channel calibration and delays

([chamber_channels.py](chamber_channels.py),
[channels.png](generated/chamber/2026-10-09/channels/channels.png), middle
and right.) The calibration record lists a phase per TX and per RX, relative
to TX1 and RX1. A rank-one fit to the DDMA amplitudes, TX by RX (99.87 % and
99.46 % of their power in the two sessions), reproduces it to 0.6° and 0.9°
for the TX and 0.1° and 0.3° for the RX. Compared as received RF phases (the
record's RX phases are those; its TX phases are their opposite, which the
shifters apply), each difference between two records is fitted as a
plane-wave change of the reflector's direction over the element positions of
the H+S drawing (`chamber_common.plane_wave_fit`). The RX array is horizontal
and shows only azimuth; the TX positions span both axes. The signs of the
changes are not established.

| Records compared | RX: azimuth change, residual | TX: azimuth and elevation change, residual |
|---|---|---|
| 2026-09-29, chamber, and the same chamber three hours later (200 MHz waveform, l2-sp record) | 0.0°, 0.16° rms | 0.0° and 0.0°, 0.6° rms |
| 2026-09-29, chamber, and 2026-09-30 (reflector at 2.2 m) | 0.54°, 0.7° rms | 0.41° and 1.94°, 4.6° rms (TX1 10.5°) |
| 2026-10-09, chamber, and 2026-09-30 (the reflector in the same place) | 0.07°, 0.25° rms | 0.11° and 0.74°, 2.8° rms (TX1 6.4°) |
| 2026-10-09 and 2026-09-29, both chamber | 0.62°, 0.7° rms | 0.52° and 2.68°, 1.9° rms (TX1 4.0°) |
| Viktor's report at 77.0 GHz (Figure 2, Infineon's firmware) and 2026-09-30 | 0.06°, 0.6° rms | |
| The report and 2026-10-09 | 0.01°, 0.8° rms | |

So the RX calibration is the same over ten days and between firmwares, up to
the reflector's direction (0.2–0.8° rms left over). The TX calibration is the
same within the day, to 0.6°, and between days to 2–5° rms beyond a change of
direction; TX1, the reference, moves most. The report's TX corrections are not
compared.

The calibration also depends on the RF frequency, as the report found. In
eight sub-bands of 112.5 MHz across the 900 MHz sweep, the received RF phase
of each TX and each RX from the DDMA case, relative to TX1 and RX1, follows a
straight line in frequency to 0.4–2.2° rms (`chamber_common.delay_fit`):
fixed delays between the channels, of up to 76 ps between RX and 210 ps
between TX. Their slopes match those of Viktor's calibrations at seven centre
frequencies, digitized from the report's Figures 1 and 2 over the
76.5–77.5 GHz this sweep spans, to 1.5 (RX) and 2.6° per GHz (TX) rms on
2026-09-29, and 2.6 and 4.2° per GHz on 2026-10-09:

| Slope [°/GHz] | TX2 | TX3 | TX4 | TX5 | TX6 | TX7 | TX8 | RX2 | RX3 | RX4 | RX5 | RX6 | RX7 | RX8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Chamber, 2026-09-29 | −6.4 | +8.4 | −5.4 | +5.8 | −46.2 | −67.8 | −29.9 | +23.7 | +27.3 | +27.1 | +13.3 | +10.2 | −18.9 | −6.4 |
| Chamber, 2026-10-09 | −8.9 | +2.9 | −10.1 | +3.8 | −52.9 | −75.3 | −34.9 | +22.4 | +25.5 | +23.6 | +12.1 | +8.5 | −23.5 | −9.9 |
| Report, Figures 1–2 | −9.4 | +9.1 | −8.3 | +7.0 | −50.5 | −67.8 | −32.6 | +22.7 | +25.9 | +26.4 | +15.8 | +11.8 | −20.2 | −7.6 |

Between the two chamber sessions every TX's slope moved by −2 to −8° per GHz
against TX1, about 14 ps of delay: TX1's own path, the reference, changed
relative to the others, as its calibration phase did. A calibration made at
one frequency is therefore off by up to 38° half a gigahertz away (TX7), and
by up to ±11° across a 300 MHz chirp. Lannik-2's calibration estimates each
channel's range and stores the resulting group delays in its calibration
files; these delays are the same quantity.

### Interference from other radars

Another radar's chirps crossing ours raise the background at all ranges at
once, unlike a target or its pedestal. The steps flag a CPI whose median
remote-Doppler power over 2–20 MHz of beat frequency exceeds the capture's
median by more than 1 dB (`carkit_common.interference_flags`), and drop it. In
the window captures the flagged CPIs are raised by 1.1–3.0 dB, the others are
within 0.56 dB at the 90th percentile.

| Capture | Flagged CPIs |
|---|---|
| Window, 2026-08-27 | 8 of 42 in mode 0, 15 of 89 in mode 1 |
| Window, 2026-09-30 | 3 of 10 in `medium-8TX-0dB-highway`, none in the other cases |
| Window, 2026-10-02 | None |
| Field captures | None in the stationary, empty, TX-off and sky captures |
| Highway captures | 39 of 516 with TX1, 70 of 487 in the busiest 8TX capture, none in the other two |

Handling interference is a separate topic; here it only costs CPIs.

## Open questions and next measurements

Three lists: the open questions, the measurements that would close them, and
what the firmware, host tool and capture format might change.

### Open questions

1. **Why the reflector on a tripod came out 4.4 dB below the carried
   reflector** ([The reflector on a tripod](#the-reflector-on-a-tripod)), and
   about 4 dB below the chamber ([The chamber reflector](#the-chamber-reflector)).
   In the chamber the radar, with two builds of our firmware, is within 1 dB of
   the model, so the radar side (TX power, configuration, a loss in front of
   the antenna) is unlikely to account for it. That leaves the session's
   setup: the radar's elevation pointing (which would also explain the extra
   loss at short range), the reflector's aim (23° off its axis would do it),
   and which of the two home-made reflectors it was. How the radar was
   levelled, how the reflector was oriented at each distance and how the
   distances were set are not recorded. Measurement 1 decides it.
2. **Why carrying cost 7 dB in the field session,** against the reflector on a
   tripod in the same half hour, and why the walk's way out was 11–14 dB below
   its way back
   ([The reflector carried in the field](#the-reflector-carried-in-the-field)).
   In the first runs the radar pointed as for the tripod, so it lies with the
   reflector and how it was carried: on its tripod, held by a handle while
   running. An aim held 27–31° off the axis would do it. It matters only for
   judging the walk's way back, the one carried leg that came out high; with
   reflectors on fixed mounts, carried runs are not needed for levels.
3. **What the timing test leaves open** ([Window: the chirp timing sets the
   error](#window-the-chirp-timing-sets-the-error)). Whether the transfer of
   each chirp's data adds to the effect of a short chirp period; whether
   Infineon's δf follows from its timing alone, as the extrapolation
   suggests; and how the settling scales with a longer sampled ramp, such as
   Psi's 20 µs. The host tool that set the 2026-10-06 timings was modified
   locally, and what else it changed is not recorded. Measurement 2.
4. **The receiver's IF response above 5 MHz.** One pair, less clean, says the
   background's fall from 7 to 14 MHz is gain shape, not noise. Up to 14 MHz
   it changes a budget by at most about 0.5 dB; above that, where a 3 MHz/µs
   slope puts 1 km (20 MHz), it is not measured. Measurement 3.
5. **Why the receiver's noise rises more towards low IF than the datasheet's
   noise figure** ([Against the datasheet](#against-the-datasheet)): about
   0.8 dB from 5.3 to 1.25 MHz, against 0.2 dB from 10 to 1 MHz in the
   datasheet under the same conditions. The transmitter, sources common to
   the RX channels and per-chirp transients are ruled out; this unit's
   spread or temperature and optimistic typical values are not. It matters
   only for targets at low IF. Infineon could answer it (the noise figure
   against IF beyond Table 30's 1 and 10 MHz rows, its spread between parts
   and with temperature, and whether the rev 0.20 values are measured), or
   measurement 4.
6. **The radome's loss.** The same in every measurement and not measurable
   on this unit. Unless a figure for it turns up, it stays an unknown loss in
   every comparison with the model.
7. **The walking reflector's RCS**, about 12.1 dBsm once the short-range
   geometry of its lab comparison is taken out (11.27 dBsm in the scripts;
   [Reflector](#reflector)), more if it faced along the chamber rather than at
   the radar; and how the two home-made reflectors differ. They look identical
   and should be close, but which one each session used is not known, since
   they are not marked. Measurement 1, at 10 m or more.
8. **Minor:** a component common to the RX channels in the remote-Doppler
   background with nothing in view: 2.2 dB in `long-8TX-0dB` (which ran TX1)
   and 0.27 dB in `sky-8tx` (all eight TX) at 1–10 MHz. For `long-8TX-0dB`,
   the skirt of its return within about 2 m predicts 2.7–7.6 dB, depending on
   where in its 1.23 m range bin it sits ([Near returns out of the
   window](#near-returns-out-of-the-window)): the mechanism, though not the
   exact number. `sky-8tx` is not examined.
9. **Minor:** a phase common to all returns, 2–5 mrad rms above 500 Hz, with
   the radar on a fixed mount
   ([Window: method and results](#window-method-and-results)).
   It does not enter δf and costs no sensitivity.
10. **Minor:** the 2026-08-27 recording's receiver noise is 4.7 dB above the
   other captures', where its recorded 0 dB RX gain step would put it about
   2.5 dB below ([Out-of-window captures](#out-of-window-captures)). Our
   firmware's chamber captures at the same step are 2.3–2.9 dB below them, as
   the datasheet predicts, so the gain step is not the cause. No result
   depends on it.

### Measurements to close them, in order of priority

1. **The reflector comparison repeated with the setup under control**
   (questions 1, 2 and 7). One radar mount, levelled, at a known height, and
   marked spots at 15–35 m on open ground with nothing moving nearby; heights,
   distances (tape or laser), photos, the radome's state and the capture order
   logged next to the data.
   - Both home-made reflectors, marked first so they can be told apart, and
     the chamber reflector (Microwave Factory, 10 dBsm specified) in turn on
     one fixed mount at the radar's height,
     each aimed along a sight on its axis (a tube or two pins on its back, or
     a laser pointer), at a few of those distances, with the empty mount
     captured for coherent subtraction. At one distance, each re-aimed and
     re-placed several times, so the spread that aiming adds is measured. If
     a home-made reflector reproduces the walk's level (33.3 dB ADC-count²
     scaled to 16 m at 15–27 m), the field session's aim, unit or setup was
     the cause; if neither does, the cause lies with the radar, which the
     steps below separate.
   - An aim scan of each home-made reflector, about ±30° in 5° steps in
     azimuth and in elevation with the radar fixed: checks [The reflector's
     aim](#the-reflectors-aim) for reflectors with imperfect plates.
   - A tilt scan of the radar in elevation, about −10 to +10° in 2° steps
     with the reflector fixed: finds the radar's boresight and checks the
     FARAD-IV elevation pattern.
   - A careful walk: at a slow, steady pace, the
     reflector held at eye height on the line to the radar, against the same
     reflector on the mount in the same session. It shows whether careful
     carrying reaches the mounted level, and so how far the walk's way back
     can be trusted.
   - If a spectrum analyser with a 77 GHz harmonic mixer is at hand,
     CARKIT's radiated power measured directly, which tests the TX side
     whatever the firmware (the same set-up as measurement 6). Whether our
     firmware can read the MMIC's TX power monitor is not checked yet.
2. **Follow-ups to the chirp-timing test** (question 3). The window scene
   from a fixed mount, TX1, the medium waveform, ten CPIs per case in one
   session, as on 2026-10-06, with the host tool's version recorded. In order
   of value:
   - The chirp data's transfer: PRI 50 µs with the CSI-2 lane rate at 400
     against 1200 Mbit/s. By the host tool's rule, the transfer and its
     overhead then take 36 µs of the 40 µs between payloads instead of 15 µs.
     The fit predicts 3.3 kHz for both; a rise points at the transfer.
   - Infineon's firmware at its own timing and with the wait lengthened: at
     4.2 µs pre-payload, 60 ns flyback and 60 ns, 10 µs and 40 µs of wait.
     The fit predicts 24, 6.5 and 3.3 kHz. This tests the extrapolation
     directly, with everything else Infineon's.
   - Time moved into the pre-payload at a short period: 25.5 µs with 12 µs
     pre-payload, 20 ns flyback and 3.2 µs of wait. If the pre-payload's
     effect continues beyond the 6 µs tested, the fit predicts 3.6 kHz, which
     would make short periods usable.
   - A longer payload: 512 samples at 25 MS/s, a 20.48 µs payload as in the
     Lannik Psi study, at its shortest chirp period (35.7 µs, the same 11.2 µs
     of flyback and wait and 4 µs pre-payload as `medium-PRI25`) and at
     100 µs. Says whether a Psi-like ramp settles in the same time; the long
     waveform cannot, since its 2048 samples need 46 µs outside the payload.
3. **Two slopes at higher IF** (question 4). The field method with the
   reflector at 60–150 m, or the long and medium waveforms at one distance:
   fixed mounts, several placements, nobody moving in the scene between the
   two captures of a pair (at 52 m in the field captures something did).
4. **Low-IF noise: unit and temperature** (question 5). In order of effort:
   - TX-off captures from a cold start through warm-up, every few minutes,
     with the MMIC's temperature sensor read if the firmware allows. Needs no
     reflector or setup. The background alone does not separate noise from
     gain shape, but from 1 to 5 MHz the two slopes showed its excess to be
     noise, so a change there with temperature is a change of noise.
   - The same TX-off captures on a second unit with the same MMIC, such as
     the first Lannik Psi hardware, at the same settings.
   - On that unit, the two-slope test, or the chip's RX test signal (user
     manual 2.3.7.4, RX RF monitoring) at several IFs, if our firmware can
     set its frequency and capture its raw samples: a tone of known level
     separates noise from gain shape without reflectors and at any IF, which
     would also serve question 4.
5. **Selected reflector distances at another height,** to separate multipath
   from the rise of level with range seen in both sessions.
6. **Bench measurement of the CW phase noise** at the TX port, only if
   measurement 2 leaves an excess unexplained.
7. **A sphere under a drone, later** (question 1). A metal-clad sphere hanging
   on a string a few metres below a drone, flown straight up over the radar
   pointed upwards. A sphere's RCS, πr² for a radius well
   above the 3.9 mm wavelength, is the same from every direction, so there is
   no aim to get wrong, and the sky behind it is empty; its uncertainty lies in
   the sphere's shape and surface. A 300 mm sphere is −11.5 dBsm, which by the
   reference model gives about 12 dB per RX at 100 m with TX1 and the walk's
   waveform, more with the eight-TX beam and the RX channels combined. The
   string puts the sphere several range cells (0.6–1.25 m each) closer than
   the drone. The drone's drift across the radar's narrow elevation plane,
   which the horizontal RX array cannot measure, costs 0.3 dB at 3.5 m and
   1.5 dB at 7 m off the vertical at 100 m (two-way, FARAD-IV preset), so its
   position should be logged. Not before a larger drone, which carries more
   and holds its position better, is available.

New captures should have the radar and any reflector on fixed mounts, the
reflectors aimed along a sight, with the setup logged next to the raw data,
and away from traffic where interference would cost CPIs.

**Open in the analysis:** none beyond the questions above.

### For the firmware, host tool and capture format

What these notes found that the radar's firmware, our host tool
(`psi-streamer` in l2-sp) or the capture format might change. Details are in
the sections linked.

**To adjust or check:**

1. **TX backoff beyond 15 dB.** The host tool accepts 0–20 dB and its
   calibration waveforms use 20 dB, while the CTRX8188F is specified for
   0–15 dB and the user manual says not to leave that range. On CARKIT 20 dB
   gave TX1 about the expected level but moved the other seven TX by 1.25 dB
   against it ([The chamber reflector](#the-chamber-reflector), [TX backoff
   and the coherent eight-TX beam](#tx-backoff-and-the-coherent-eight-tx-beam)).
2. **RX gain default.** The host tool defaults to 0 dB, the chip's default,
   whose typical noise figure is 0.5 dB worse than at +3 dB; the calibration
   routine ran at 0 dB ([Firmware](#firmware)).
3. **`RX_HP_BOOST` placement.** Set in the pre-payload, where the cut-off does
   not change; the user manual says it acts where the cut-off switches back
   from 4.8 MHz, which is the wait segment ([The high-pass
   filter](#the-high-pass-filter)).
4. **The calibration routine's TX1-alone stage** failed on 2026-10-09 (build
   `7349c1fa`): its reflector 25–30 dB below TX1's line in DDMA and varying by
   several dB from CPI to CPI, while separate TX1 captures were fine
   ([Chamber captures](#chamber-captures)).
5. **The calibration routine's SNR-gain check** uses the fluctuation at the
   reflector's own range as noise, which the reflector's own phase-noise skirt
   and drift dominate, so it fails whenever the reflector is strong. Noise
   taken well away from the reflector would test the receivers ([Coherent
   channel summation against it](#coherent-channel-summation-against-it)).
6. **Calibration over frequency.** The channels differ by fixed delays of up
   to 0.2 ns, so a calibration at one centre frequency is off by up to 38° at
   ±0.5 GHz. The routine's 900 MHz chirp already holds what is needed to
   estimate each channel's delay from sub-bands; Lannik-2 stores such delays
   ([Channel calibration and delays](#channel-calibration-and-delays)).
7. **Channel amplitudes from a reflector at 2–3 m** include the reflector's
   finite-aperture taper (1.8–3.3 dB across TX1's pairs on CARKIT, about half
   of the TX powers' spread under DDMA); they should not be taken as channel
   gains ([A reflector at short range](#a-reflector-at-short-range)).
8. **Chirp timing.** The host tool's minimum segments allow chirp periods at
   which the per-chirp frequency error rises well above the CW level (5.9 kHz
   at 25.5 µs against 3.3 kHz); with a 10 µs payload, 15–25 µs of flyback and
   wait keep it there ([Window: the chirp timing sets the
   error](#window-the-chirp-timing-sets-the-error)).
9. **`Execute_Calibration` sub-function 0x2d** sets bit 5, which the user
   manual marks as reserved ([Firmware](#firmware)).

**To record with every capture** (for the review of the Psi capture format):

- The host tool's version (git describe, with a flag for uncommitted
  changes), and builds made only from committed code; several builds here
  ended in `-dirty`, and the 2026-10-06 timing captures ran a locally
  modified host tool ([Firmware](#firmware)).
- The MMIC's segment settings: high-pass cut-off and boost per segment, DPLL
  mode, digital filter reset; the TX power levels as programmed. None of these
  is in either sidecar format ([The high-pass
  filter](#the-high-pass-filter)).
- What the chip reports about itself: each RX's high-pass and baseband-delay
  deviations (`Get_RX_TF_Parameters()`), the temperature (`Get_Temperature()`),
  and the TX power monitor if the firmware can read it.
- The calibration record whenever TX phases are applied; the field captures'
  eight-TX runs had none and all phases at 0 ([Field
  captures](#field-captures)).
- What a case was meant to be, beside what was configured, and a setup log:
  mounting, distances, heights, which reflector, photos, order. Case names
  were often the only description, and `long-8TX-0dB` ran TX1.
- All requested CPIs, or why some are missing; the highway runs lost about
  half ([Highway captures](#highway-captures)).

## Reproducing

```sh
make study_260911_carkit_validation      # about 10 minutes
make study_260911_carkit_validation CARKIT_DATA_ROOT=/path/to/carkit
make study_260911_carkit_validation CARKIT_FIELD_DATA=/path   # one recording elsewhere
```

This runs the study's synthetic tests, then the walk, outdoor, window, field,
highway and chamber steps in order (the chamber steps use the window and
field steps' stored backgrounds and IF response, and the 2026-10-09 TX1 step's
high-pass corner), the chamber background and channel steps once more on the
2026-10-09 recording (into `generated/chamber/2026-10-09/`), and finally the window steps on the 2026-10-02
recording (with its own level pairs, into `generated/window/2026-10-02/`) and
on the 2026-10-06 chirp-timing recording, followed by window_timing.py (into
`generated/window/2026-10-06/`). Each
step writes `summary.json` (and, for some walk steps, a per-frame CSV) and
figures under `generated/<dataset>/<step>/`. The JSON/CSV files and the figures
linked from these notes are tracked, so they are available without the raw
data; the `.npz` arrays passed between steps and the other figures are only
generated locally.

### Raw data

The raw captures are not in the repo. They are on the shared drive, one
folder per recording, with each of its subfolders stored as a zip file. Unzipped
in place, side by side in one folder, they form the data root. The scripts take
that folder from `CARKIT_DATA_ROOT` (default `~/Data/carkit`, as a make
variable or in the environment) and each recording from its folder below. A
recording's own make variable (environment variable for the scripts, or
`--data`) overrides its location:

| Dataset | Folder under the data root | Make variable | Content |
|---|---|---|---|
| Walk | `2026-09-11_walk_hallesaker` | `CARKIT_WALK_DATA` | 200 CPIs in `tx1-1/`, an offline PSI-style conversion of the recording (samples reordered only, with its configuration and provenance) |
| Outdoor captures | `2026-09-22_phase_noise_outdoor_reflector` | `CARKIT_OUTDOOR_DATA` | 4 × 10 CPIs, manifest and sidecars |
| Window, 2026-08-27 | `2026-08-27_test_out_of_office_window` | `CARKIT_WINDOW_INFINEON_DATA`, its `converted_adc/` | 131 frames in Infineon's format, and their conversion in `converted_adc/` |
| Window, 2026-09-30 | `2026-09-30_out-the_window` | `CARKIT_WINDOW_DATA` | 11 cases of 6–10 CPIs, a sidecar per CPI |
| Window, 2026-10-02 | `2026-10-02_out_the_window` | `CARKIT_WINDOW_1002_DATA` | 5 cases of 9–10 CPIs |
| Window, 2026-10-06 | `2026-10-06_out_the_window` | `CARKIT_WINDOW_1006_DATA` | 10 cases of 9–10 CPIs, one chirp timing each |
| Field captures | `2026-10-01_reflector_lindevi` | `CARKIT_FIELD_DATA` | 12 placements and 2 empty scenes of 9–10 CPIs, no TX (97 CPIs), sky (67, 59), 5 runs (313–370); a README and photos |
| Highway captures | `2026-10-01_highway_sandsjobacka` | `CARKIT_HIGHWAY_DATA` | 4 cases of 152–516 CPIs, about half of each run's CPIs not recorded; photos and a map |
| Chamber, 2026-09-29 | `2026-09-29_calibration` | `CARKIT_CHAMBER_DATA` | 3 cases of 10 CPIs (`01-ddma`, `02-single-tx`, `03-coherent`), the calibration record in `03-coherent`'s sidecars |
| Chamber, 2026-10-09 | `2026-10-09_lab_reflector` | `CARKIT_CHAMBER_1009_DATA` | 9 cases of 10 CPIs (`mode-1`..`mode-3`, `notx-1`..`notx-3` and the routine's three), new sidecar format |

The window steps also run on any new recording in our firmware's format,
with the case directories discovered (`--cases auto`) or listed, and the outputs
in their own folder:

```sh
venv/bin/python studies/2026-09-11_carkit-validation/window_scene.py --data DIR \
    --cases auto --output OUT/scene
venv/bin/python studies/2026-09-11_carkit-validation/window_phase.py --data DIR \
    --cases auto --scene OUT/scene --output OUT/phase
```

The 2026-08-27 recording's conversion, `converted_adc/`, is on the drive with
it. It was made once, outside `make`, in MATLAB with l2-sp's code on the
path:

```matlab
run('~/Git/l2-sp/matlab/addL2SpMatlabPath.m')
cd studies/2026-09-11_carkit-validation
window_convert_infineon   % writes converted_adc/ beside the recording
```

### Scripts

| Script | Content |
|---|---|
| [carkit_common.py](carkit_common.py) | Shared paths, I/O and estimators (per-chirp amplitudes, detrending, unwrap-free phase, multi-line model errors, cross-RX and cross-return power and spectrum, CW per-chirp prediction, the settling fit) |
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
| [window_common.py](window_common.py) | Loading and checks for our firmware's formats (any recording; the sidecar format of 2026-10-09 mapped onto the first) and the converted Infineon recording, TX/DDMA configuration, case discovery, static peaks |
| [window_scene.py](window_scene.py) | Checksums, ADC levels, static profiles, channel-independent background, interference CPIs, matched levels (`--level-pairs`), drift |
| [window_phase.py](window_phase.py) | Per-chirp δf from clean static returns (interfered CPIs dropped), delay law, common phase, CW prediction, slow-time spectra |
| [window_timing.py](window_timing.py) | The per-chirp error against the chirp timing: full-resolution cross-return spectrum and its tilt, the settling fit, its extrapolation to Infineon's timing, the flyback and wait needed |
| [window_range_scale.py](window_range_scale.py) | Range scale from moving vehicles: apparent range change against Doppler-integrated distance |
| [field_common.py](field_common.py) | Field capture loading, zero-Doppler tone estimator, reflector search, matching samples of two sweeps, near-field loss, a trihedral's loss off its axis, azimuth, interference levels, reference model |
| [field_if.py](field_if.py) | Receiver backgrounds (TX off, empty scene, sky) and the two-slope IF test at the reflector |
| [field_level.py](field_level.py) | Reflector levels with IF and near-field corrections, azimuth, comparison with the walk and the model |
| [field_runs.py](field_runs.py) | The reflector carried in the field runs: track, levels in the walk's bands against the tripod and both walk legs, CPI-length check |
| [highway_traffic.py](highway_traffic.py) | Moving-target range–time maps, interference CPIs, vehicle passes and their range exponents |
| [chamber_common.py](chamber_common.py) | Chamber capture loading, the reflector's beat frequency and per-chirp amplitudes (also in sub-bands), DDMA demodulation, remote-Doppler covariance and floor density, background split, alignment and the coherent channel-summation gain against a background, the two-pole high-pass and its fit, a real return's two-sideband skirt, a trihedral's finite-aperture factor, delay and plane-wave fits; FARAD-IV TX positions, calibration records and the report's digitized values |
| [chamber_background.py](chamber_background.py) | Receiver noise at RX gain 0 dB against the other captures, the reflector's skirt against the CW table, the coherent channel-summation gain against the background, near returns in the window captures |
| [chamber_channels.py](chamber_channels.py) | TX powers and phases from DDMA against the calibration record and the report, the eight-TX beam against its prediction, stability, calibration records compared, channel delays, the double bounce |
| [chamber_tx1.py](chamber_tx1.py) | 2026-10-09: the backoff step and the high-pass measured on the reflector, receiver noise and sample rates, TX1's return per RX against the finite reflector, the absolute level, the home-made reflector's RCS |
| [chamber_level.py](chamber_level.py) | 2026-09-29: the reference reflector's level against the model at face value |
| [report_figures.py](report_figures.py) | The report's figures (README.md) from the tracked summaries: each set-up's SNR against the model on one basis, and the per-chirp error against the chirp timing |
| [test_carkit_common.py](test_carkit_common.py) | Synthetic checks of the normalizations and estimators, including the per-bin cross-spectrum against the band sum and the settling fit's recovery and extrapolation |
| [test_field_common.py](test_field_common.py) | Synthetic checks of the field estimators (two-slope ratio, matching samples, near-field loss, loss off the axis, azimuth, interference flags) |
| [test_chamber_common.py](test_chamber_common.py) | Synthetic checks of the chamber estimators (DDMA sign, background split, coherent channel-summation gain, high-pass fit, two-sideband skirt, density conversion, delay and plane-wave fits) and of the finite-aperture factor (the near-field formula, the l2-sp model's CARKIT taper) |
