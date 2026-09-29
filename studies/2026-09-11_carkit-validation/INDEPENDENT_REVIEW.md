# Independent review of the CARKIT walk analysis

This file retains the sequence of technical reviews. The consolidated current
assessment and Slack summary are in [NOTES.md](NOTES.md); later sections here
qualify some earlier interpretations.

2026-09-29. This qualifies the earlier near-exact model/measurement agreement
in NOTES.md and REPORT_REVIEW.md. No hardware correction is established.

## Scope and reproducibility

Reviewed the session discussion, current report, study notes, model setup,
ADC processing and generated results. Added [audit_walk_adc.py](audit_walk_adc.py)
to independently recompute selected quantities from the supplied int16 ADC data.
It reuses the earlier CSV's target coordinates and frame selections, so this is
an independent FFT/statistics check, not an independent tracker or decoder of
the original proprietary format.

```sh
source venv/bin/activate
python studies/2026-09-11_carkit-validation/audit_walk_adc.py \
  /Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi
```

All 200 binary-file SHA256 checks pass and waveform/sample-layout metadata are
constant. Recomputed common-cell per-RX SNRs for 86 outbound/inbound CPIs match
the previous CSV exactly at stored precision. Results are in
[generated/audit/summary.json](generated/audit/summary.json). Positive physical
ranges only are used; negative Doppler is retained. Processing uses periodic
Blackman on both axes, fourfold range padding and fourfold Doppler padding for
target extraction; noise uses native Doppler bins. The original analysis code
that generated Viktor's report has still not been supplied.

## 1. Averaging order materially changes the claimed reconciliation

The earlier 32.62 dB datum averages *dB SNRs* across both frames and RXs: it is a
geometric mean. Its quoted 32.80 dB alternative first fits each RX in dB over
time, then averages those fitted intercepts in linear units. It does **not**
average the eight RX SNRs in linear units within each CPI. Frame-dependent
channel fading makes the distinction important.

For the same 37 selected CPIs, all values below are R^-4-fit normalizations at
100 m, not measurements at that distance:

| Statistic | Far-quarter background | Broad 15–51 m background | Broad background, normalized to 10 dBsm |
|---|---:|---:|---:|
| Mean dB over RXs and CPIs (earlier result) | 35.25 | 33.89 | 32.62 |
| Linear mean RX SNR per CPI, then dB fit | 36.60 | 35.16 | 33.89 |
| Linear mean over RXs and range-normalized CPIs | 37.09 | 35.66 | 34.39 |

The second row uses `q_j = mean_rx(P_jrx / N_jrx)`, then fits
`mean_j(10 log10(q_j) + 40 log10(R_j / 100 m))`.
All rows are legitimate descriptive statistics, but they answer different
questions. The model's equal-channel nominal SNR does not specify an estimator
for a fading walk. A comparison must name its spatial and temporal estimator.

Relative to the second row, the reproduced magnitude-sum statistic of 36.94 dB
is only 0.34 dB higher, not 1.69 dB. Of the earlier 1.69 dB difference, 1.35 dB
comes from changing geometric to arithmetic RX averaging. The original
three-term accounting is therefore not a unique physical explanation of 4 dB.
With the previous broad noise reference and provisional 1.27 dB RCS correction,
the second row is 1.22 dB above the model's 32.67 dB; the third is 1.72 dB above.
Neither establishes a hardware/model bias given scene and RCS uncertainties.

Selection also matters. The second-row normalized value is 33.67 dB for all
39 CPIs 89–127 and 32.93 dB for all 41 CPIs 89–129. The outbound leg (26–70)
gives 21.44 dB with the same convention: roughly 12 dB weaker after range
normalization. We cannot treat this walk as a stable known-RCS point target.
Orientation/occlusion and propagation are candidates, not identified causes.

## 2. Smooth spectral shaping is not the whole background story

The earlier "local" background averages the entire 15–51 m band, not the
target's current range. The plotted median over all CPIs can suppress a moving
target-associated background component.

The audit instead averages within +/-1.487 m of the current target range,
excluding |velocity| < 10 m/s. A spatial second-moment matrix of those complex
background samples shows a target-aligned component in several inbound CPIs:

| CPI | Largest eigenvalue / trace | Squared alignment with target vector | Target-range background over nearby ranges |
|---|---:|---:|---:|
| 89 | 0.213 | 0.971 | 0.46 dB |
| 100 | 0.246 | 0.982 | 0.54 dB |
| 105 | 0.399 | 0.996 | 1.21 dB |
| 127 | 0.454 | 0.996 | 1.65 dB |

Nearby comparison ranges are 4–8 m away, with the same Doppler mask. Alignment
means `|u^H s|^2 / ||s||^2`, with unit dominant eigenvector u and common-cell
target vector s. For reference, eight equal independent background channels
have population eigenvalue fractions of 1/8. Padded range samples and windowed
Doppler bins are correlated, so these are descriptive diagnostics, not an
independent-sample significance test. The matrix is uncentered `E[x x^H]`.

This is evidence for a target-associated correlated background, compatible with
phase/amplitude modulation or other signal-dependent artifacts. It does not
identify oscillator phase noise or establish the background at the detection
cell. Using this target-range background yields 32.82 dB for the selected37
statistic (linear RX average, dB fit, 10 dBsm normalization). Changing the
Doppler cutoff to 20 or 30 m/s gives 32.68 or 32.59 dB. Those near matches must
not become a new claim of precise thermal-sensitivity validation: the
denominator now includes target-associated excess background.

A common transfer function multiplying signal and upstream noise remains a
possible explanation of the *smooth* noise slope, not a demonstrated fact.
Frequency-dependent input-referred noise is another possibility; the preset
10.2 dB NF is specified at 10 MHz, outside the walk's roughly 1–3.4 MHz beat
band. Separate the receiver floor from signal-dependent background before
using either as a hardware calibration datum.

Nor is comparing field and chamber R^-4 echo levels enough to exclude phase
noise. Shared-LO residual phase is `phi(t-tau)-phi(t)`, giving the factor
`4 sin^2(pi f tau)` in its PSD; cancellation changes with delay and offset.
[TI's engineering explanation](https://e2e.ti.com/support/sensors-group/sensors/f/sensors-forum/796887/awr1642-awr1642-s-phase-noise)
confirms this delay/offset dependence, not its magnitude on CARKIT. Chamber TX
backoff was also 20 dB versus 0 dB here, with different RX gain and waveform.
Keep this observation available to the separate phase-noise study without
claiming that branch explains it.

## 3. RX differences include spectral nulls, not just fixed gain imbalance

[CPI 100 Doppler cuts](generated/audit/cpi100_doppler.png) show RX8 has a deep
notch at the common target cell. It is 28.1 dB below the strongest RX there,
but only 15.8 dB below after summing power over a +/-2 m, +/-1 m/s patch. Its
own strongest cell in that patch is 10.8 dB above its common-cell value.
Likewise, CPI 40 RX5 changes from -27.4 dB at the common cell to -9.9 dB in
integrated patch power.

Patch power is a diagnostic, not a replacement matched-filter SNR: it includes
different scatterers and background and has a different processing gain.
Nevertheless, the channel differences are not well described by one fixed
amplitude-calibration coefficient per RX. A fixed digital scaling multiplies
signal and noise equally and cannot change an individual RX's SNR. Common-cell
measurements can exaggerate channel differences when returns are composite.

Multiple scattering paths/centers or time-varying channel response remain
candidates. Do not jump specifically to ordinary ground two-ray interference:
for an equal-height horizontal array and a flat ground plane, direct and
specular ground-reflected paths have the same horizontal direction, so large
RX-dependent fading requires checking the actual geometry. The report's modest
Table 2 amplitude spread is for TX, not RX; it cannot resolve this question.

## 4. Small bookkeeping correction

The apparent center-frequency discrepancy in the original analysis is explained
by including ADC-start delay: start + slope * pre_payload + sampled_BW/2 is
approximately 76.374237 GHz, matching the report. Start + sampled_BW/2 alone
omits about 54.5 MHz. This is not a material SNR discrepancy.

## Practical next steps

- Keep the report-reproduction statistic separate from any calibrated one-RX
  sensitivity estimate. Do not fit a transferable correction from the current
  near-match. `carkit_walk.py` still prints the historical naive report/model
  offset; it is not an approved hardware correction.
- With existing data, compare target-conditioned background matrices to nearby
  ranges and to the same range in CPIs without the reflector. Inspect slow-time
  amplitude/phase residuals and stationary scene returns to distinguish shared
  modulation from moving-scatterer structure. No full phase-noise model is needed
  for this first discrimination.
- For a reference measurement, use a stationary, characterized reflector and
  record geometry, pointing and per-RX outputs. A power/backoff sweep helps
  separate a receiver floor from signal-dependent background; avoid clipping.
  Include independent reflector dimensions/RCS checks and the optional stand
  absorber control discussed in the session.
- Preserve both all-frame and explicitly selected results. Prefer a reference
  distance actually measured; retain 100 m only as an explicitly extrapolated
  R^-4 normalization.

Validation: audit run against raw ADC data completed; repository black, flake8
and strict mypy checks passed via `python pre_commit.py --no-dirty`. No shared
radar-performance model, original analysis output or raw capture was changed.

## Follow-up: pedestrian motion, CPI length and measurement scope

Discussion and results recorded 2026-09-29. The reproducible analysis is in
[analyze_walk_dynamics.py](analyze_walk_dynamics.py), with numerical output in
[generated/dynamics/summary.json](generated/dynamics/summary.json).

Pedestrian limbs and movement of a hand-held reflector can broaden or split
the target Doppler spectrum; see the primary
[walking-limb micro-Doppler study](https://arxiv.org/abs/1711.09175).
Such structure can contaminate a target patch and interfere coherently at a
common cell. It need not imply hardware incoherence. Conversely, ordinary
walking micro-Doppler does not readily explain the background in masks beyond
|20–30| m/s; spectral leakage, signal-dependent artifacts and phase/amplitude
modulation remain distinct candidates there. Target-aligned spatial covariance
alone does not distinguish these mechanisms.

From capture metadata, 1024 chirps span 16.343 ms, whereas the accumulated ADC
sampling time used in the sensitivity budget is 10.486 ms. Native Doppler-bin
spacing is 0.1201 m/s, before Blackman mainlobe broadening. Motion at 4 m/s
traverses only 0.065 m during the CPI versus the 1.487 m native range cell:
gross range migration is small, but this does not establish phase coherence.
Constant radial velocity is handled by Doppler processing; acceleration,
orientation changes and multiple scattering centers are separate effects.

### Coherent concentration versus CPI length

Every 1024-chirp CPI in the two clean walk legs was divided into all
non-overlapping 128/256/512-chirp segments. Each segment gets its own Blackman
window, far-quarter background estimate and common-RX peak search within +/-2 m
and +/-2 m/s of the full-CPI target. Linear RX SNRs and subsegments are averaged
before taking the ratio to the 128-chirp result. Fourfold padding has at most
0.068 dB residual tone scalloping and cannot explain the result.

| Leg | 256-chirp deficit | 512-chirp deficit | 1024-chirp deficit | 1024 p10--p90 |
|---|---:|---:|---:|---:|
| Outbound, CPIs 26--70 | -0.29 dB | -1.05 dB | **-1.41 dB** | -4.52 to -0.26 dB |
| Inbound, CPIs 89--127 | -0.07 dB | -0.07 dB | **-0.20 dB** | -0.49 to +0.13 dB |

Deficit is relative to the ideal 3.010 dB per doubling. The report benchmark is
drawn from the inbound interval; it is therefore nearly fully concentrated by
the 1024-chirp constant-velocity FFT. CPI decorrelation is not a credible source
of several dB in that selected benchmark. The outbound target is qualitatively
different and loses appreciable peak SNR as the aperture grows. This measures
mismatch to one constant-velocity tone, not radar oscillator coherence alone.
Peak search and differing Blackman weighting of a time-varying return remain
small estimator qualifications.

[Coherent-gain plot](generated/dynamics/coherent_gain.png).

### Doppler and slow-time structure

The fraction of power within +/-2 m/s of the target but outside a +/-0.5 m/s
core has median **11.7% outbound** and **0.88% inbound**. A worst-grid constant
Blackman-windowed tone gives 0.00011%, so this is real target/scene structure,
not its nominal FFT mainlobe. The fraction and the best-tone coherence are
strongly anticorrelated, especially outbound (Spearman -0.76).

A complementary normalized projection asks how much weighted range-bin power
is represented by each RX's best constant tone. The median is 0.53 outbound and
0.93 inbound. This quantity includes every return and noise in that range bin;
it is a structure metric rather than a direct coherent-integration loss.

[Median Doppler profiles](generated/dynamics/target_centered_doppler.png) and
[example slow-time residuals](generated/dynamics/slow_time_examples.png) make
the difference visible. CPI 40 has rapid channel-dependent amplitude nulls and
large nonlinear phase changes. CPI 100 is substantially more orderly, but RX8
passes through a deep null near 7 ms and RX7 changes strongly over the CPI.
This supports pedestrian/hand-held-reflector micro-motion and composite returns
as explanations of the near-target spread and common-cell RX differences.

### Target-conditioned remote-Doppler background

For each range and RX, the analysis averages native Doppler power at identical
absolute masks `|v| >= 10, 20, 30 m/s`. At the current target range it compares
that power with a per-range median from other CPIs, excluding the two stable
walk legs unless their tracked target is more than 8 m away. Offsets of +/-12 m
in the same CPI are pseudo-target controls. Thus the smooth fixed range response
and the Doppler mask are shared by observation and control.

At `|v| >= 20 m/s`, the median target-range excess is **0.05 dB outbound** and
**1.21 dB inbound**; the pseudo-range median is -0.01 dB. Within the inbound
leg, target-cell power and the background ratio have Spearman **0.92**. Results
remain similar at 10 and 30 m/s: inbound excess 1.12 and 1.34 dB, with
correlations 0.93 and 0.92. The positive excess power is roughly -60 dB per
averaged remote-Doppler cell relative to target peak, but that number is only a
diagnostic PSD-like ratio under these masks, not a phase-noise specification.

[Background-versus-signal plot](generated/dynamics/background_vs_signal.png).
The same data also couple signal strength to range, and CPI/range samples are
not statistically independent, so formal correlation p-values do not establish
causality. Nevertheless, the same-range and pseudo-range controls make the
association harder to explain as a fixed IF response. Ordinary limb velocities
can explain near-target spreading but not energy at absolute 20--30 m/s. A
signal-dependent wide Doppler pedestal is supported. Hardware phase noise,
amplitude/phase modulation, short-time target variation and other artifacts are
not separated by this capture.

The useful conclusion from the existing data is asymmetric: the inbound data
used for the report have little constant-velocity CPI loss, yet the strong
inbound return raises a remote-Doppler, target-associated background. The weak,
broad outbound return shows much more target-motion/scene mismatch but almost
no measurable remote-background elevation.

### Radar-equation reference using target-free background

[analyze_walk_reference_snr.py](analyze_walk_reference_snr.py) recomputes the
additive reference at each observation's range and near its Doppler. Controls
start at CPI 26; a control through CPI 160 is excluded whenever the tracked
reflector is within 8 m of the requested range. Later CPIs are treated as
post-walk controls. Each estimate pools approximately 19,000--21,000 powers
from 128--139 control CPIs, within +/-1.487 m and +/-1 m/s of the requested
cell, using the same periodic Blackman windows.

The primary estimator is `median(power) / ln(2)`, which estimates mean complex
Gaussian noise power while rejecting intermittent moving returns. Two checks
give nearly the same selected-frame anchor: an exponential-corrected upper-10%
trim gives -0.01 dB relative to it and the untrimmed arithmetic mean gives
-0.11 dB. Control-estimator choice is consequently not material here.

With linear RX averaging within each CPI followed by the report-like dB-domain
fixed-R^-4 fit, and applying the provisional 1.27 dB RCS correction:

| Frames | Target-free reference SNR at 100 m | Model residual |
|---|---:|---:|
| Selected 37 inbound | **34.09 dB** | +1.42 dB |
| All 39 contiguous inbound | **33.86 dB** | +1.19 dB |

This is the most directly comparable current reference: spatial power is
averaged linearly and the temporal fit is in dB. It remains an extrapolated
100 m normalization of a changing hand-held target, not a calibrated 100 m
measurement. The all-inbound per-frame values have median 33.27 dB, standard
deviation 2.27 dB and p10--p90 31.74--37.49 dB. Fully linear temporal averaging
instead gives 34.49 dB; averaging all RX/frame values in dB gives 32.53 dB.
These alternatives describe the same fading data but answer different
statistical questions.

The selected per-RX dB-fit anchors span 30.92--34.33 dB and average 32.73 dB,
almost exactly the 32.67 dB model. This agreement is not preferred as a power
comparison because geometric RX averaging weights deep spatial nulls differently
from the model's equal-channel power, but it shows why an apparently precise
answer can be manufactured by changing averaging order.

[Reference-SNR plot](generated/reference_snr/reference_snr.png) also confirms
that the target-free baseline itself falls by roughly 0.6 dB from 15 to 50 m
(beat frequency increases with range). Its origin remains unresolved. Using the
same-range baseline accounts for it empirically without assuming that it is a
common signal/noise transfer function.

Excluding the pedestal therefore changes the prior broad-local result by only
about +0.2 dB under the comparable spatial-linear/time-dB convention. The main
remaining uncertainty is target presentation, absolute RCS and averaging—not
the numerical estimation of the target-free noise floor. There is no support
for the original +4 dB hardware correction; a provisional residual near
+1.2--1.4 dB remains under the most comparable convention.

Keep future sensitivity and phase-noise investigations separate in purpose,
analysis and acceptance criteria, but share captures/configuration identifiers
where useful. They can be acquired consecutively in one session. Sensitivity
needs a known stationary reflector and demonstrably receiver-floor-limited
background; phase-noise/dynamic-range work examines excess background versus
strong return, delay and offset. Neither study should depend on completing the
other to produce its first useful result.

For both, record unchanged RX gain/filter settings, TX backoff, geometry,
reflector pointing and raw ADC. At each tripod range, use a TX-power sweep with
repeats and a reflector-absent control; a TX-off control is useful if supported
without changing receiver operating conditions. With a stationary reflector,
do not remove its signal by slow-time mean subtraction/DC rejection. Background
clutter at zero Doppler needs controls, not an automatic exclusion of that bin.
Range-dependent multipath remains even with a tripod; repeat selected points
at a different height or small displacement to assess it. Background scaling
with TX power alone cannot identify phase noise: passive clutter and other
signal-dependent effects can scale similarly.

## Second review of dynamics and target-free SNR implementation

2026-09-29. Reviewed the code, outputs and follow-up discussion, then ran
read-only sensitivity checks against the raw capture. The implementation's
same-range reference is appropriate for the requested additive-background
radar-equation comparison. The following checks support the reported numbers
while qualifying their interpretation; existing analysis outputs were retained.

### Control selection and background robustness

Recomputed the primary exponential-corrected median reference for all 39 inbound
CPIs, changing one choice at a time. All values use linear RX SNR averaging,
the dB-domain R^-4 fit, and provisional 10 dBsm normalization at 100 m.

| Control variant | Anchor [dB] |
|---|---:|
| Original settings, independently reproduced | 33.8630 |
| Only CPIs 26--160, excluding tracked target within 8 m | 33.8970 |
| Only CPIs 161--199 | 33.7875 |
| Increase tracked-target exclusion from 8 to 16 m | 33.8767 |
| Reduce Doppler half-width from 1 to 0.5 m/s | 33.8606 |
| Use the exact target range bin instead of +/-1.487 m | 33.8622 |
| Same-range controls at absolute velocity >= 20 m/s, Doppler bins subsampled by 8 | 33.9461 |

The late-CPIs-as-controls assumption does not materially determine the answer.
The sensitivity to these choices is below 0.1 dB relative to the original
estimate, supporting a stable additive baseline near the relevant cells. This
does not identify that baseline as pure thermal receiver noise: persistent
scene background would also be included. The 19,000--21,000 pooled powers are
correlated through windowing/padding and must not be described as that many
independent samples or used directly for a confidence interval.

Strictly, the script averages `P_rx/N_rx`, not `sum(P_rx)/sum(N_rx)`. The latter
changes the all-inbound dB-fit anchor by only -0.055 dB here. The code also uses
`P/N0` rather than `(P-N0)/N0`. Applying the subtraction changes the all-inbound
anchor by -0.000028 dB, so this is immaterial for the measured strong target.

### CPI test validation and interpretation

A synthetic real ADC cube with a constant tone at 30.123 m and -3.456 m/s,
eight fixed channel phases, amplitude 20 and independent unit-variance Gaussian
sample noise (NumPy seed 526) was passed through the existing range transform
and `segment_measurement` functions. Gains relative to 128 chirps were
0, 3.059, 6.013 and 9.090 dB for 128/256/512/1024 chirps, consistent with
the ideal 0, 3.010, 6.021 and 9.031 dB plus finite noise/scalloping variation.
The full-length best-tone projection was approximately 0.9992 in every RX.

The measured inbound -0.20 dB result is an **incremental** deficit between
128 and 1024 chirps, not an upper bound on total coherence loss. The windows
weight different parts of the CPI, and peak searches can follow different
components. The separate 0.93 full-CPI tone-projection statistic supports a
mostly tone-like inbound return, but is itself a weighted-power concentration
measure rather than a hardware phase-noise loss estimate.

As a check on stationary contamination in the slow-time examples, zeroing
unwindowed Doppler bins with |v| < 0.75 m/s changes median per-RX tone projection
from 0.533 to 0.577 outbound and from 0.928 to 0.936 inbound. The example CPI 40
and CPI 100 RX nulls are therefore not primarily explained by zero-Doppler
content. Phase traces close to amplitude nulls remain unreliable as estimates
of physical oscillator phase; multiple coherent returns can produce both the
nulls and apparent phase jumps.

### What remains uncertain

The conditional additive-background SNR is the useful quantity for weak-target
sensitivity, provided the target's own pedestal vanishes with its power and
other strong scene returns do not impose a floor at that cell. This choice of
denominator does not undo any signal energy already spread away from the peak
by target motion or radar impairments. Good coherent peak gain and a detectable
remote pedestal can coexist when the carrier is sufficiently strong.

Do not interpret -60 dB per averaged remote-Doppler cell relative to the peak
as dBc/Hz or as a transferable phase-noise parameter. The measurement includes
FFT/window bandwidth and range averaging, and its frequency structure and
cause remain unresolved. The power-sweep interpretation is conditional on the
disturbance law, receiver settings and scene remaining comparable.

Within the 39 inbound CPIs, the 17 observations below 30 m give a mean
R^-4-normalized anchor of 33.14 dB, whereas the 22 at 30--51 m give 34.42 dB.
That difference can reflect target/scene variation; this walk cannot isolate
receiver filtering from it. It matters more than the remaining numerical noise
estimator choices. The 33.86 dB whole-leg result is a useful descriptive anchor,
not a uniquely measured intrinsic sensitivity. Mean power, typical dB level
and median are different estimands; none should be selected because it happens
to match the nominal model. The +1.2 dB fitted residual is not an independently
identified implementation gain or loss.
