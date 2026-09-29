# Archived working notes before consolidation on 2026-09-29

This is a historical snapshot retained for traceability. It includes superseded
interpretations and recommendations. Use [NOTES.md](NOTES.md) for the current
assessment; do not apply numerical corrections from this archive without its
qualifications.

---

# CARKIT model-validation working notes

Last substantial update: 2026-09-29.

**Latest assessment:** [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md) qualifies
the earlier near-exact agreement below. Averaging order changes the corrected
anchor by more than 1 dB, and target-range background contains a target-aligned
component not captured by the broad-band noise summary. The original +4 dB is
not a justified hardware correction, but neither is sub-dB model agreement
established. The review includes reproducible ADC checks and RX Doppler cuts.

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
Raw ADC data are now available externally at
`/Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi`; the scripts and derived
results are in this study, not the raw captures.
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

**Follow-up reported on 2026-09-28:** the walking reflector is now identified
as the member measured 1.27 dB stronger than the nominal 10 dBsm chamber
reference, giving a provisional **11.27 dBsm** relative assignment. If the
reference is truly 10 dBsm, using 11.27 rather than 10 dBsm reduces the nominal
report-minus-model offset from 3.90 to **2.63 dB**. The chamber result is still
relative: the reference's 10 dBsm value has not been independently calibrated.

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

1. **Reflector RCS and the person carrying it.** The reflector was historically
   assigned 14 dBsm, then assigned 10 dBsm without an absolute RCS calibration.
   The 2026-09-28 clarification identifies it as 1.27 dB stronger than the
   nominal 10 dBsm chamber reference, suggesting 11.27 dBsm and explaining 1.27
   dB of the offset. The historical 14 dBsm value remains unsupported.
   Orientation, frequency, mounting and the pedestrian return in the same cell
   can further alter the effective return.
2. **Selection and propagation enhancement.** The 36.57 dB anchor comes from
   33 points selected to lie within 6 dB of a local R^-4-corrected peak, over a
   road measurement where ground multipath can create several-dB constructive
   and destructive structure. This preferentially retains enhanced returns.
   The quoted 100 m value is then an extrapolated fit normalization outside the
   actual 15–51 m reflector interval.
3. **Processing or SNR-definition mismatch.** Follow-up states Blackman windows
   and fourfold zero-padding on both axes, supporting the study assumptions. For
   a periodic Blackman window, fourfold padding leaves at most about 0.068 dB
   residual scalloping per axis, so this cannot explain several dB. The reported
   statistic instead needs attention: the screenshot labels an RX1–8 magnitude
   sum divided by a global RMS estimated in the farthest range quarter, excluding
   the zero-Doppler neighborhood. A magnitude sum is not automatically the same
   statistic as a mean of noise-normalized powers, and far-range IF filtering
   may give a different noise floor from the 1–3.4 MHz target-beat region.
   One-sided FFT normalization could introduce another systematic error.
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
The raw-data reproduction below identifies important statistic, noise-reference
and provisional reflector corrections. The independent review finds that the
claimed complete reconciliation depends materially on averaging and background
choices. Do not turn the original difference into a hardware correction.
The absolute reflector RCS and the transferability to another scene remain
unresolved. A second single-TX measurement with a characterized target and
documented processing would be more diagnostic than refining the 1 km
extrapolation.

### 2026-09-28 processing follow-up

The follow-up is useful but does not close the comparison:

- Blackman windows on both FFT axes and fourfold padding are now confirmed. The
  statement that padding reduced straddling loss by 0.4 dB describes a change
  relative to unpadded processing, not the remaining loss; zero-padding does not
  otherwise create SNR.
- Viktor's independent radar-equation calculation gives 32.63 dB for one RX at
  100 m, versus this study's 32.67 dB. This confirms that both calculations use
  essentially the same theoretical assumptions and arithmetic; it is not an
  independent measurement validation.
- Adding ideal 8-RX coherent gain gives 41.66 dB and the stated coherent result
  is 41.6 dB, but that agreement assumes a 10 dBsm reflector. With the new
  relative 11.27 dBsm assignment, the corresponding prediction is 42.93 dB.
  More fundamentally, `32.6 + 9.0 = 41.6 dB` mixes a theoretical single-channel
  baseline with a measured coherent output. The reported empirical channels are
  35–37 dB; ideal eight-channel coherent combination of those values would be
  44–46 dB, while 41.6 dB represents only about 4.6–6.6 dB measured gain over
  that empirical range. Imperfect calibration and correlated background may
  explain the shortfall, but the numerical equality does not validate the
  absolute link budget.
- Weak walking observations were deliberately removed on the assumption that
  the reflector was mispointed. This can be reasonable for estimating boresight
  reflector performance, but without measured orientation it also selects
  constructive multipath and other high-return conditions. The fitted anchor is
  therefore not an unbiased per-scan performance statistic.
- The original questions about extracted channel group delays, the covariance
  cell mask/positive-range restriction, and the interpretation of the
  signal-dependent chamber background remain unanswered.

The screenshot's 36.7 dB fit is also based on an RX1–8 *magnitude sum*. For
equal high-SNR channels and independent complex Gaussian noise, summing eight
magnitudes and dividing by the RMS of that summed-magnitude background is about
0.9 dB more favourable than a representative single-channel amplitude/RMS
ratio. The exact correction changes with channel normalization and noise
correlation, so it must be computed from the actual code rather than applied as
a fixed adjustment.

### 2026-09-29 raw-ADC reproduction

The 200 JSON/bin pairs under the external, untracked directory
`/Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi` have now been processed
independently by `analyze_walk_adc.py`. Each binary is little-endian `int16`
with shape `[1024 chirps, 512 fast-time samples, 8 RX]`. The processing is:

- a real-input positive-range FFT and a full Doppler FFT;
- periodic Blackman windows and fourfold zero-padding on both axes, with each
  FFT normalized by the corresponding window sum;
- one common target cell selected from the mean of the eight per-RX powers,
  after normalizing each RX by its own noise power;
- per-RX signal powers read at that same cell, with no complex RX combination
  or channel calibration;
- per-RX far-noise power from the farthest range quarter and native Doppler
  cells with `|v| >= 1 m/s`; and
- a separate local-noise estimate over 15–51 m and `|v| >= 10 m/s`, which
  excludes the walking reflector's Doppler and exposes the IF noise shape.

The walking trajectory is clean through about CPI 160. The stable inbound
reflector segment is approximately CPIs 89–127. All 39 of those CPIs give an
RX-magnitude-sum `R^-4` intercept of **36.71 dB at 100 m**, effectively
reproducing the 36.7 dB plot without observation rejection. Applying the
stated 15–51 m, +/-5 m, within-6 dB local-peak rule selects 37 CPIs rather than
the report's 33 and gives **36.94 dB**. The small selection mismatch therefore
does not matter to the present accounting; the exact original code would only
be needed to reproduce the 33 observations precisely.

On the 37 independently selected CPIs, the per-RX 100 m intercepts using the
same far-quarter noise reference are:

| RX | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | Mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Far-noise SNR [dB] | 33.49 | 35.66 | 35.92 | 36.75 | 36.72 | 34.70 | 35.36 | 33.38 | 35.25 |
| Local-noise SNR [dB] | 32.09 | 34.38 | 34.66 | 35.45 | 35.48 | 33.14 | 33.76 | 32.17 | 33.89 |
| Local SNR, normalized from 11.27 to 10 dBsm [dB] | 30.82 | 33.11 | 33.39 | 34.18 | 34.21 | 31.87 | 32.49 | 30.90 | 32.62 |

The initial reconciliation was as follows. **The averaging interpretation in
item 4 is superseded by the independent review; these figures describe the
geometric-mean statistic, not a uniquely established sensitivity datum.**

1. The RX-magnitude-sum statistic is 36.94 dB, **1.69 dB above** the mean of
   the individually measured RX SNRs on the same cells and with the same far
   noise reference. It must not be treated as a representative one-RX SNR.
2. Noise power in the reflector's beat-frequency interval is about **1.36 dB
   above** the far-quarter reference when the correction is applied per CPI
   and per RX. The median spectral curve independently shows about 1–1.5 dB of
   elevation throughout this interval. Using far-range RMS therefore inflates
   the target-band SNR.
3. Normalizing the provisional 11.27 dBsm walking reflector back to 10 dBsm
   subtracts another **1.27 dB**.
4. The resulting geometric-mean per-RX datum is **32.62 dB**, versus the model's
   **32.67 dB**. The previously quoted 32.80 dB linear alternative averages
   fitted per-RX intercepts, after dB averaging over time. Instead averaging
   linear RX SNRs within each CPI and then fitting in dB gives **33.89 dB**,
   1.22 dB above the model. Averaging range-normalized powers over time as well
   gives **34.39 dB**. The near-exact match is therefore estimator-dependent.

This agreement should not be overinterpreted. The 11.27 dBsm value is still
relative to a nominal chamber reference rather than an absolute RCS
calibration; the per-channel corrected intercepts span 3.39 dB; multipath and
reflector pointing remain present; and the current channel-average model is
not a prediction of those individual gain differences. The useful conclusion
is that the original +4 dB is not an established favourable hardware/model
offset; neither is precise agreement established by this dataset.

The magnitude sum is not mathematically invalid: it is a possible nonlinear
detection statistic. It is, however, not the conventional signal-power to
noise-power SNR. Its noise-only value has a positive mean because magnitudes
are nonnegative, and its scale with RX count differs from both coherent complex
combination and an ordinary sum of powers. For eight equal independent complex
Gaussian noise channels, the high-SNR magnitude-sum-to-noise-RMS ratio is
already about 0.90 dB above a single-channel amplitude/RMS ratio. Unequal
channel SNRs and correlated noise make that offset data-dependent. Here it is
1.69 dB relative to the geometric RX mean, but only 0.34 dB relative to the
linear RX mean with the same subsequent dB fit. It is therefore acceptable if
named and calibrated as its own detector
statistic, but misleading when labelled simply SNR and compared with a one-RX
radar equation.

The noise-versus-range curve is equivalently a noise-versus-beat-frequency
curve. It is about 1–1.5 dB higher at the reflector's 1–3.4 MHz beat frequencies
than in the 18.7–25 MHz far-quarter region. A likely contributor is the analog
IF/anti-alias transfer function, though ADC or digital filtering, frequency-
dependent receiver noise and residual scene-dependent interference can also
contribute. The noise curve alone does not determine target SNR versus beat
frequency. If one common transfer function multiplies both a target tone and
all dominant upstream receiver noise, both powers receive the same gain and
their ratio is unchanged; a far-range target does not gain SNR merely because
the plotted noise is lower. If important noise is added after that filtering,
or if the background includes clutter/phase-noise terms that do not track the
target transfer, SNR can vary with beat frequency. Establish this with a known
injected tone/delay sweep or a controlled target measurement across beat
frequency. Until then, use noise local to a target cell rather than a remote
far-range region when reporting empirical SNR.

The reflector itself is traceable over approximately 3–55 m. The report fit is
restricted to 15–51 m; the clean contiguous intervals used for a free-slope
check are CPIs 26–70 outbound (15.25–50.20 m) and CPIs 89–127 inbound
(16.73–50.57 m). This check uses absolute target-bin power rather than SNR, so
the choice of far-noise reference cannot create its slope. Pure `R^-4` power
loss is -40 dB/decade. The mean of the eight RX powers instead fits -30.02
dB/decade outbound and -35.31 dB/decade inbound. On the inbound interval the
measured noise spectrum fits about -1.20 dB/decade, so a common transfer
function acting on signal and upstream noise would predict approximately
-41.20 dB/decade signal slope. Across 16.73–50.57 m these correspond to:

- measured inbound signal loss: 16.96 dB;
- pure `R^-4` loss: 19.21 dB; and
- `R^-4` plus the measured noise spectral shape: 19.79 dB.

The signal trend is therefore in the opposite direction from the proposed
common-filter signature: after `R^4` correction it rises toward longer range,
especially outbound. This does not disprove common filtering. The expected
filter signature is only about 0.58 dB across the interval, while the fitted
target has roughly 2.1 dB RMS scatter and differs substantially between travel
directions and RX channels; pointing, the pedestrian return and ground
multipath dominate. The walk consequently supplies no positive evidence that
signal and noise share the measured spectral shaping. A controlled delay or
injected-tone sweep is needed to test that hypothesis.

The large instantaneous RX amplitude spread is not thermal-noise-induced. In
the clean intervals, the target data have median SNRs of about 43 dB outbound
and 55 dB inbound; even the weakest inbound RX observation is about 27 dB. The
far-noise estimates themselves vary by only 0.06–0.07 dB over time. Relative to
the per-frame channel mean, the time-averaged RX target powers span about 3.0
dB, while the far-noise channel means span 0.85 dB. A few dB of fixed offset is
plausible because the supplied captures contain unchanged raw ADC counts and no
RX amplitude-calibration coefficients accompanied them; the installed RF
chains/port patterns also need not be identical. The current report explicitly
documents RX *phase* calibration in Figure 2. Its modest measured amplitude
span of -0.69 to +0.76 dB in Table 2 applies to TX, not RX. The report does not
tabulate RX amplitudes or state clearly whether fixed RX magnitude equalization
was applied to the field statistic. Such calibration may exist in the original
processing code or calibration files, which have not been supplied.

Fixed channel gain does not explain the full effect. The median per-frame
strongest-to-weakest target-power span is 8.9 dB outbound and 10.7 dB inbound;
the 90th percentiles are about 17 dB and maxima exceed 27 dB. After removing
the common per-frame level, individual RX fluctuations still have 3–5 dB
standard deviations, and the mean channel ordering changes between outbound
and inbound legs. There is no ADC clipping, and the extracted RX range-peak
offsets are far too small to cause these amplitude losses at the common cell.
Normalizing every channel by its own far-noise power leaves median per-frame
spans of 8.7 dB outbound and 10.9 dB inbound. Even an artificial fixed
equalization that forces the mean target level of every RX to agree over each
leg leaves median spans around 10 dB. A chamber-derived fixed amplitude
calibration can therefore remove mean hardware imbalance but cannot explain or
remove the observed frame-dependent nulls.

For one far-field point scatterer, one propagation path and identical RX
elements/chains, the channels should indeed have equal magnitudes and differ
only in steering phase. The observed behavior therefore indicates violations
of that idealization. The leading explanation is coherent spatial fading from
ground/scene multipath and unresolved returns from the reflector, carrier and
possibly other scattering centers, superimposed on smaller fixed channel and
element-pattern differences. Phase noise shared through a common LO would more
naturally create a correlated background aligned with the steering vector; it
is not a good primary explanation for deep, channel-dependent target-amplitude
nulls. A stationary reflector in a controlled single-path setup, processed per
RX before and after amplitude calibration, is the appropriate diagnostic.

As an exploratory group-delay check, each RX range peak was also found near the
common target cell and quadratically interpolated on the fourfold-padded grid.
The median relative delays (zeroed by the per-CPI channel mean) are RX1–8 =
`[+94, -2, -43, -12, +30, -8, +134, -67] ps`. Per-CPI MAD values are
96–161 ps, comparable to the offsets themselves. This walking, approximately
100 MHz-bandwidth measurement therefore does not provide a precise validation
of the calibration-phase slopes. A stationary reflector with the calibration
frequency sweep remains the appropriate dataset for that check.

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

The raw ADC walk has now been received and independently reproduced. The
original analysis code would still resolve the minor 33-versus-37 observation
selection difference and document Viktor's exact DC exclusion, but neither is
needed for the main link-budget accounting. Saved configuration and calibration
files would be useful if they contain settings not represented in the JSON.

The higher-value next step is now a controlled reflector measurement rather
than further refinement of the selected walk fit:

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
- **2026-09-28:** Recorded the Slack processing follow-up: Blackman/Blackman with
  fourfold padding, far-quarter global RMS noise, amplitude-based observation
  selection, an RX1–8 magnitude-sum plot, and a provisional 11.27 dBsm relative
  reflector assignment. These reduce but do not resolve the model discrepancy;
  raw data and the exact generating code remain the next step.
- **2026-09-29:** Independently processed all 200 raw ADC CPIs. Reproduced the
  plotted magnitude-sum fit at 36.71–36.94 dB, measured 35.25 dB mean per-RX
  SNR with its far-noise reference, and found the reflector-band noise about
  1.36 dB higher. After that noise correction and the provisional 1.27 dB RCS
  correction, the mean per-RX datum is 32.62 dB versus the 32.67 dB model.
  Initially interpreted as explaining the original +3.90 dB; the independent
  review below qualifies this interpretation. No hardware correction retained.
- **2026-09-29, independent review:** Added `INDEPENDENT_REVIEW.md` and
  `audit_walk_adc.py`. Verified all 200 capture hashes and recomputed 86 CPIs.
  Found material RX/time averaging-order sensitivity, a target-aligned
  high-Doppler background component at the target range, and RX spectral nulls
  that cannot be explained by fixed amplitude calibration alone. Updated the
  headline assessment: neither a +4 dB hardware advantage nor sub-dB validation
  is established. Shared performance models and previous generated outputs
  were not changed; new diagnostics are under `generated/audit/`.
- **2026-09-29, dynamics follow-up:** Reprocessed 128--1024 chirps with
  `analyze_walk_dynamics.py`. The report's inbound interval is within 0.20 dB
  median of ideal 1024-chirp concentration; outbound loses 1.41 dB and has much
  broader, less tone-like returns. At the target range, background beyond
  |20| m/s is 1.21 dB above same-range controls inbound and strongly tracks
  target power, while pseudo ranges and the weak outbound leg are near zero.
  This supports a signal-dependent wide-Doppler pedestal but does not identify
  phase noise as its cause. Results and plots are under `generated/dynamics/`.
- **2026-09-29, target-free SNR reference:** Added
  `analyze_walk_reference_snr.py`. Same-range, near-target-Doppler controls give
  34.09 dB at 100 m for the selected37 or 33.86 dB for all inbound39 after the
  provisional 10 dBsm normalization, using linear RX power and a dB-domain
  temporal fit. These are +1.42 and +1.19 dB above the model. Three robust/raw
  background estimators agree within 0.11 dB; target variation and averaging
  dominate. The target-free baseline still falls about 0.6 dB over 15--50 m.
