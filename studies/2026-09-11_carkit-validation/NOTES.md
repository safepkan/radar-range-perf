# CARKIT model-validation working notes

Last substantial update: 2026-09-26.

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

- [`inputs/CARKIT report.pdf`](inputs/CARKIT%20report.pdf): current 17-page
  coworker report dated 2026-09-22. It appears to supersede the six-page
  [`empirical-1km-snr-budget.pdf`](inputs/empirical-1km-snr-budget.pdf), but is
  still under review.
- [`REPORT_REVIEW.md`](REPORT_REVIEW.md): review of the current report, followed
  by the earlier report review for traceability.
- [`carkit_walk.py`](carkit_walk.py): provisional single-TX comparison using
  existing toolbox components. All numerical setup choices are visible there.

Run from the repo root:

```sh
source venv/bin/activate
venv/bin/python studies/2026-09-11_carkit-validation/carkit_walk.py
```

The script prints the setup, processing budget and a model/report-fit SNR
comparison at 15, 30, 51 and 100 m. These are evaluations of the report's
fitted curve, not individual measurements. The 100 m value is the fit's stated
normalization point; the selected observations themselves span only 15–51 m.
There is no raw data in this repo yet.
No TX/RX gain extrapolation, implementation correction, 1 km forecast or
acquisition simulation is applied.

Keep the study scriptable: represent further measured cases with ordinary
`Radar`, `FmcwWaveform`, `StandardProcessing`, target and geometry objects.
Add cases as their configurations and observations become available; no new
general configuration framework is needed now.

## First case: single-TX Hallesaker walk

| Quantity | Initial value | Status / meaning |
|---|---|---|
| Capture | Hällesåker walking reflector | Reported; exact capture identifier absent from current report |
| Hardware | CTRX8188F + FARAD-IV | User identifies the CARKIT hardware |
| TX / RX | TX1 / RX1–8 | Reported |
| TX backoff / RX gain code | 0 dB / 0 | Reported; physical settings need interpretation |
| ADC samples / chirps | 512 / 1024 | Reported |
| ADC payload / PRI | 10.24 / 15.96 microseconds | Reported |
| Sample rate | 50 MHz | Inferred from 512 / 10.24 microseconds |
| Sampled bandwidth | 100.781 MHz | Reported; confirm bandwidth definition |
| Carrier step | 0 Hz | Reported |
| RF center frequency | 76.374237 GHz | Reported, current PDF Table 6 |
| TX power | 14.5 dBm per active TX | Datasheet preset, not measured on this board |
| RX noise figure | 10.2 dB | Preset at 10 MHz; RX mode/IF dependence unverified |
| Antenna | `antenna.sencity_farad_iv()` | Digitized per-channel TX/RX pattern cuts |
| Target | 10 dBsm reflector | Report's assumed absolute RCS, not calibration |
| Direction | Boresight | Model assumption; path and heights unavailable |
| Range / Doppler windows | Blackman / Blackman | Model assumption based on earlier processing; current report does not say |
| RX combination | Mean of noise-normalized powers | Reported; no complex RX sum |
| Straddle losses | 0 dB on both FFT axes | Model assumption: enough zero-padding to neglect remaining scalloping |
| CFAR loss | 0 dB | Comparing spectral SNR, not detector sensitivity |
| Sample noise bandwidth | 50 MHz | Repo complex-sample convention; verify against capture |

**Reported:** the current fixed R^-4 fit is normalized to 36.57 dB at 100 m
for the nominal 10 dBsm reflector:

`SNR_dB = 116.57 - 40 log10(R/m)`.

Figure 10 says that it uses 33 walking observations over 15–51 m lying within
6 dB of a local R^-4-corrected peak in a +/-5 m neighborhood. Thus 36.57 dB is
an extrapolated normalization of a deliberately selected fit, not a measured
sample at 100 m. The selection rule differs from the earlier report's 24
inbound per-bin maxima.

**Result:** active integration is 10.48576 ms; CPI including chirp dead time is
16.34304 ms. The sample/chirp FFT integration gain is 57.20 dB and the two
Blackman losses total 4.74 dB. Eight RX channels are eight noncoherent looks,
not an additional coherent gain term.

**Result:** with the table's assumptions, the model predicts 32.67 dB at 100 m
versus the report fit's 36.57 dB. The provisional empirical offset, defined as
report minus model, is therefore **+3.90 dB** throughout the R^-4 comparison.
It may be added to model SNR as a scoped reality-check correction. It is not a
physical implementation loss—the selected measurement fit is stronger than the
nominal model—and cannot be allocated among MMIC performance, installed antenna
gain, reflector RCS, target direction, propagation, fit selection or the SNR
estimator. Do not put it into a global chipset or antenna preset.

The calculation uses the toolbox's `B_n = f_s` matched-filter/complex-sample
convention. Although the ADC data are real, changing to `B_n = f_s/2` while
retaining the complex-tone FFT gain would introduce an inconsistent 3 dB
credit. The report's actual one-sided signal/noise normalization still needs to
be checked against the model convention.

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

## Real versus complex sampling

**Result:** no general real/complex sampling mode exists in the current toolbox.
`FmcwWaveform` has no sampling-type field. The link-budget engine uses the
documented complex-baseband convention `B_n = f_s` by default and processing
uses coherent gain `n_samples * n_chirps`. `noise_bandwidth_hz` is only a scalar
noise-ENBW override; it does not turn the calculation into a real-sampling
model or describe an IF filter and its sample correlation.

For a scalar matched-filter SNR such as the present reflector comparison, the
real/complex distinction can be ignored if received signal power, noise power
and FFT normalization are defined consistently. A real tone has half its power
in each conjugate FFT lobe, which cancels the apparent 3 dB reduction obtained
by replacing `B_n = f_s` with `f_s/2` while inspecting only one target lobe.
Therefore do **not** apply a blanket 3 dB correction or set `B_n = f_s/2` solely
because CARKIT uses real ADC samples.

The distinction cannot be ignored for positive/negative-range covariance,
phase-noise or interference skirts, aliasing/IF-filter models, or any estimator
whose one-sided/two-sided normalization is unclear. For real ADC data, form
spatial covariance from only the physical range half rather than counting the
conjugate half as separate observations.

The unmerged `phase-noise` branch has explicit `complex` and
`real_phase_averaged` choices in its standalone phase-noise FFT diagnostic. Its
real mode includes the conjugate carrier lobe and can approach a 3 dB increase
for a flat phase-noise skirt, but the effect is range-dependent for shaped
spectra. That branch deliberately does not add sampling type to the waveform or
change the ordinary thermal-noise link budget, ambiguity or detection models.

## Interpreting the +3.90 dB empirical offset

The sign deserves scrutiny. A datasheet-based model that omits implementation
losses would ordinarily be expected to overpredict measured performance. Here
the selected empirical fit is instead 3.90 dB stronger. This does not prove a
model error, because the datum is not an absolute controlled calibration and
several scene and estimator effects are entangled. The leading candidates are:

1. **Reflector RCS and the person carrying it.** The reflector was previously
   assigned 14 dBsm and is now assigned a nominal 10 dBsm without an absolute
   RCS calibration. A 4 dB higher effective RCS would explain the entire offset,
   although the numerical match must not be mistaken for evidence. Orientation,
   frequency, mounting and the pedestrian return in the same cell can all alter
   the effective return.
2. **Selection and propagation enhancement.** The 36.57 dB anchor comes from
   33 points selected to lie within 6 dB of a local R^-4-corrected peak, over a
   road measurement where ground multipath can create several-dB constructive
   and destructive structure. This preferentially retains enhanced returns.
   The quoted 100 m value is then an extrapolated fit normalization outside the
   actual 15–51 m reflector interval.
3. **Processing or SNR-definition mismatch.** Field windows are unstated. Using
   Hann instead of Blackman on both axes would recover about 1.22 dB relative to
   the provisional model; omitting one Blackman window loss would recover 2.37
   dB. The noise region may also sample a different IF noise floor from the
   target, and RX averaging or one-sided FFT normalization could introduce a
   larger systematic error. Zero-padding itself must not create SNR.
4. **Actual component values.** TX1 output power may exceed the 14.5 dBm typical
   value, the active RX mode may have a lower NF than the 10.2 dB preset, and
   per-port installed antenna gains may differ from the average digitized cuts.
   These could plausibly contribute a dB or two in combination, but a full 4 dB
   favourable shift should be measured rather than assumed. Raising both TX and
   RX gains from about 15 to 17 dBi would also add about 4 dB two-way, but the
   available FARAD-IV data do not currently justify that choice.

These effects are not mutually exclusive. Conversely, radome/feed loss,
polarization mismatch, calibration loss and other omitted implementation losses
would move the model in the opposite direction and hence deepen the puzzle.
Keep the +3.90 dB offset local and provisional until the processing is reproduced
per channel on unselected observations and the reflector/scene is better
controlled. A second single-TX measurement with a characterized target and
documented processing would be more diagnostic than refining the 1 km
extrapolation.

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

## Next evidence to obtain

Prioritize reproducibility of the original single-TX walk, not written
clarifications or a new coherent-TX campaign. Ask for a copy of:

1. The raw ADC captures and saved configuration/calibration files used for the
   36.57 dB result.
2. The complete analysis code at a named revision, including its environment or
   dependency specification and the exact command/configuration that reproduces
   Figure 10 and the 33 selected observations.
3. Any intermediate per-frame/per-RX range, Doppler, signal and noise exports
   needed to cross-check the result without reverse-engineering file formats.

Running and reviewing the same code is preferable to requesting window,
zero-padding, noise-mask and SNR-definition details individually: it removes
terminology ambiguity, reveals implicit normalization and selection choices,
and allows comparisons on both ordinary observations and the selected fit.

Treat reflector characterization as a separate work item:

1. Record reflector geometry, all relevant physical dimensions, material and
   construction. Photograph its orientation, mount and how it was carried.
2. Compute the ideal boresight RCS at 76.374 GHz from the formula appropriate to
   that reflector geometry. For an electrically large corner reflector this is
   a useful engineering upper benchmark, not an absolute calibration; finite
   conductivity, edge construction and pointing generally reduce the realized
   peak. Check the measurement distance against `2 D^2 / lambda`, using the
   largest reflector dimension `D`.
3. Measure it independently with CARKIT or another available sensor. Prefer a
   relative measurement against a characterized reference target at the same
   range, height, polarization and processing settings, with an angle sweep
   through boresight and background subtraction. This cancels much of the
   sensor link-budget uncertainty.
4. Earlier measurement characterizations reportedly indicate that the exposed
   stand contribution is negligible, helped by its location in the reflector's
   elevation sidelobes. Treat it as a lower-priority uncertainty rather than a
   likely explanation for the link-budget offset. For the reference measurement,
   cover exposed stand parts with suitable millimetre-wave absorber as a cheap
   control. Compare absorber on/off and place it so that it neither shadows the
   reflector nor creates a new nearby scattering edge.
5. If practical, measure reflector alone, carrier/person alone and the combined
   setup. Their returns can add coherently in the same range–Doppler cell, so the
   walking target's effective RCS need not equal the reflector-only RCS.

These are enough to refine the first comparison. A second documented single-TX
run can then establish whether the same model offset transfers to another setup.
Investigate residuals before assigning losses to the chipset, antenna or
processing. Introduce a calibration correction only with explicit scope and
uncertainty; carry it into Psi separately from theoretical array gains.

## Decision log

- **2026-09-11:** Created a separate CARKIT validation study from `main` and
  moved the supplied report and initial review here. Adopted direct measured
  setup comparisons, starting with single TX and noncoherent RX. Recorded
  Pd=50% at 1 km as an informal Psi objective, with acquisition modeling and
  fluctuation/correlation assumptions deferred. Added a provisional runnable
  walk comparison; no shared presets or Psi model parameters changed.
- **2026-09-26:** Reviewed the 17-page 2026-09-22 report and replaced the old
  walk anchor with its 36.57 dB-at-100-m selected fixed-slope fit. Adopted
  provisional Blackman windows and zero residual straddling loss. The resulting
  report-minus-model offset is +3.90 dB; it remains local to this study and is
  not treated as an attributable hardware loss.
- **2026-09-26:** Recorded that real versus complex sampling does not require a
  blanket 3 dB correction for the scalar matched-filter SNR comparison, while it
  remains essential for covariance and phase-noise modeling. Ranked the main
  candidate explanations for the unexpectedly positive +3.90 dB offset.
- **2026-09-26:** Replaced prose clarification requests with a reproducible
  raw-data/config/code handoff as the preferred next step. Added a separate
  reflector-characterization plan based on dimensions, an ideal peak-RCS
  benchmark and relative measurements against a characterized reference.
- **2026-09-26:** Recorded prior evidence that reflector-stand scattering is
  negligible and further suppressed by the elevation pattern. Retained absorber
  over exposed stand parts as an inexpensive reference-measurement control.
