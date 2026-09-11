# CARKIT model-validation working notes

Last substantial update: 2026-09-11.

## Purpose and scope

Run configurations that were actually measured on CARKIT through `radarperf`
and compare equivalent quantities. Start with the simplest available case:
one TX, eight RX, noncoherent RX power averaging, and the Hallesaker reflector
walk. Establish whether the model predicts the observed sensitivity and what
uncertainty remains before fitting any implementation correction.

This study is separate from the
[Lannik Psi design study](../2026-09-02_lannik-psi/NOTES.md). Later scaling to
Psi antenna, waveform and processing choices will be done with our models.
The measurement report's TX extrapolation and combined 1 km budget are not
inputs to the validation baseline. Investigating how well the coworker's
coherent-TX calibration worked is secondary, not a prerequisite for validating
single-TX sensitivity. Practical coherent gain may fall below the nominal
model; its allowance should remain explicit when eventually applied to Psi.

The repo's default branch is `main` (there is no `master`). This study was
started on `carkit-validation-study` from local `main` at `526d2b9`.

## Status labels

- **Reported:** stated in the supplied report; not independently reproduced.
- **Model assumption:** chosen to run a comparison, awaiting measurement detail.
- **Result:** computed from the repository under stated assumptions.
- **Open question:** information needed to establish an equivalent comparison.
- **Direction:** agreed scope or working preference, not a measured result.

## Inputs and first runnable case

- [`inputs/empirical-1km-snr-budget.pdf`](inputs/empirical-1km-snr-budget.pdf):
  six-page coworker report dated 2026-09-11, moved here from the Psi inputs.
- [`REPORT_REVIEW.md`](REPORT_REVIEW.md): initial broad review, retained as
  background; these notes govern the active priorities.
- [`carkit_walk.py`](carkit_walk.py): provisional single-TX comparison using
  existing toolbox components. All numerical setup choices are visible there.

Run from the repo root:

```sh
source venv/bin/activate
venv/bin/python studies/2026-09-11_carkit-validation/carkit_walk.py
```

The script prints the setup, processing budget and a model/report-fit SNR
comparison at 15, 30 and 51 m. These are evaluations of the report's fitted
curve, not individual measurements. There is no raw data in this repo yet.
The report's fit is only compared inside its stated 15–51 m interval.
No TX/RX gain extrapolation, implementation correction, 1 km forecast or
acquisition simulation is applied.

Keep the study scriptable: represent further measured cases with ordinary
`Radar`, `FmcwWaveform`, `StandardProcessing`, target and geometry objects.
Add cases as their configurations and observations become available; no new
general configuration framework is needed now.

## First case: single-TX Hallesaker walk

| Quantity | Initial value | Status / meaning |
|---|---|---|
| Capture | `walk-hallesaker-tx1-1` | Reported, PDF p. 3 |
| Hardware | CTRX8188F + FARAD-IV | User identifies the CARKIT hardware |
| TX / RX | TX1 / RX1–8 | Reported |
| TX backoff / RX gain code | 0 dB / 0 | Reported; physical settings need interpretation |
| ADC samples / chirps | 512 / 1024 | Reported |
| ADC payload / PRI | 10.24 / 15.96 microseconds | Reported |
| Sample rate | 50 MHz | Inferred from 512 / 10.24 microseconds |
| Sampled bandwidth | 100.781 MHz | Reported; confirm bandwidth definition |
| Carrier step | 0 Hz | Reported |
| RF center frequency | 77 GHz | Model assumption; exact capture frequency absent |
| TX power | 14.5 dBm per active TX | Datasheet preset, not measured on this board |
| RX noise figure | 10.2 dB | Preset at 10 MHz; RX mode/IF dependence unverified |
| Antenna | `antenna.sencity_farad_iv()` | Digitized per-channel TX/RX pattern cuts |
| Target | 10 dBsm reflector | Report's assumed absolute RCS, not calibration |
| Direction | Boresight | Model assumption; path and heights unavailable |
| Range / Doppler windows | Blackman / Blackman | Reported; use 2.37 dB loss on each axis |
| RX combination | Mean of noise-normalized powers | Reported; no complex RX sum |
| Straddle losses | 0 dB initially on both FFT axes | Centered-bin comparison; actual offsets unknown |
| CFAR loss | 0 dB | Comparing spectral SNR, not detector sensitivity |
| Sample noise bandwidth | 50 MHz | Repo complex-sample convention; verify against capture |

**Reported:** 200 raw frames, 137 saved track observations, 63 outbound and
74 inbound. A fixed R^-4 fit used 24 inbound maxima per occupied range bin
over 15–51 m:

`SNR_dB = 115.746526 - 40 log10(R/m)` for the assumed 10 dBsm reflector.

**Result:** active integration is 10.48576 ms; CPI including chirp dead time is
16.34304 ms. The sample/chirp FFT integration gain is 57.20 dB and the two
Blackman losses total 4.74 dB. Eight RX channels are eight noncoherent looks,
not an additional coherent gain term.

**Result:** with the table's assumptions, the model reflector intercept is
112.60 dB versus the report's 115.75 dB. Thus report fit minus model is
approximately +3.15 dB throughout this interval. That residual is not a fitted
hardware correction: RCS, direction, upper-envelope selection, multipath and
noise conventions are unresolved. Adding the toolbox's usual 0.6 dB straddle
allowance on each axis would lower the prediction by a further 1.2 dB.

June [Config 3](../2026-06-22_config-comparison/config_comparison.py) used
17 dBi constant antenna gains and was a future-product assumption, not a
CARKIT configuration. Here the FARAD-IV preset gives approximately 15.045 dBi
TX and 14.984 dBi RX at boresight. Its average-channel cuts are a first model
of TX1 and RX1–8, not measured per-port installed patterns.

## RX processing and the quantity being compared

**Direction:** prefer the original noncoherent RX processing for initial
validation. It avoids the narrow array beam's sensitivity to target direction.
The single-channel antenna envelope still matters, particularly elevation.

**Reported:** the original walk processing already used this approach.
After range/Doppler integration it normalized noise per RX and averaged RX
powers. The fixed-weight coherent sum was a later reprocessing experiment.

For equal per-channel SNR and consistently normalized signal and noise,
summing or averaging RX powers gives the same signal-to-mean-noise ratio.
It improves detection statistics by combining looks. Our processing model
therefore reports per-look SNR plus `n_noncoherent=8`; our detector accounts
for those eight looks. Do not add 10 log10(8) to that SNR. Exact equivalence
still requires the report's SNR formula, noise estimates and channel behavior.

If coherent RX is investigated later, steer to known target direction or
evaluate an appropriate beam bank. Taking the best beam addresses angular
mismatch but introduces selection and multiple-testing considerations when
interpreting SNR and Pfa. Neither a fixed beam nor a best-beam result should
silently replace the noncoherent baseline. Short-range lateral/height offsets
can produce appreciable angles and make fixed-beam comparisons misleading.

## Performance objectives beyond the calibration case

**Direction:** Pd around 50% at 1 km would be a satisfactory working Psi
objective; use single-scan Pd for now. This is not a CARKIT acceptance test,
and the report's 15 dB criterion is not adopted. The actual target/RCS and Pfa
still need to be stated for any product prediction. The earlier 1 m²,
Swerling-1, Pfa=1e-6 case remains a reference scenario, not a fixed requirement.

For that reference scenario with one coherent detection look, the repo gives
about 12.77 dB for Pd=50%. The threshold changes with fluctuation assumptions
and the number/type of combined looks. The reflector SNR comparison itself
does not require adopting a Swerling distribution. The script uses a constant
RCS target and does not compute Pd for the reflector walk.

Track acquisition and maintenance are the eventual objectives. Pd=50% or
lower may be useful, but frame rate, motion, target fluctuation distribution,
miss correlation and tracker behavior remain open. Do not infer acquisition
probability from single-scan Pd alone or pin a confirmation rule yet.

## Smallest next information request

Prioritize the original single-TX walk, not a new coherent-TX campaign:

1. Capture configuration and the code defining SNR, including ADC format,
   sample rate, RF center frequency, RX mode, filtering, windowing, noise
   region/estimator and power normalization. Establish whether signal power
   has the noise contribution subtracted.
2. Per-frame range, Doppler and per-RX signal/noise values (or raw ADC and
   processing code), with the sample-selection rule. Compare ordinary
   observations and their spread as well as the selected maxima. Understand
   the 63 frames without saved track observations without assuming misses.
3. Reflector dimensions and basis for its RCS, how it was carried/oriented,
   radar and reflector heights, radar tilt and approximate walk path.

These are enough to refine the first comparison. A simple export from another
single-TX run can then establish whether the same model matches a second
setup. Investigate residuals before assigning losses to the chipset, antenna
or processing. Introduce a calibration correction only with explicit scope
and uncertainty; carry it into Psi separately from theoretical array gains.

## Decision log

- **2026-09-11:** Created a separate CARKIT validation study from `main` and
  moved the supplied report and initial review here. Adopted direct measured
  setup comparisons, starting with single TX and noncoherent RX. Recorded
  Pd=50% at 1 km as an informal Psi objective, with acquisition modeling and
  fluctuation/correlation assumptions deferred. Added a provisional runnable
  walk comparison; no shared presets or Psi model parameters changed.
