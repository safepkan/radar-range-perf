# CARKIT model-validation working notes

Consolidated 2026-09-29. This is the current study assessment and handoff.
The summary below is also available as a
[paste-ready Slack update](deliverables/2026-09-29/SLACK_SUMMARY.md).
[Figure captions](deliverables/2026-09-29/FIGURES.md) accompany the optional attachments.

Earlier calculations and changing interpretations are retained in
[NOTES_HISTORY.md](NOTES_HISTORY.md),
[REPORT_REVIEW.md](REPORT_REVIEW.md) and
[INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md). Read the current assessment here
before using an older numerical result.

## Summary from Codex — 2026-09-29

We have independently reprocessed the walking-reflector recording, including per-RX signal/noise estimates, different CPI lengths and checks of the background around the target. Processing uses Blackman windows and fourfold FFT padding on both axes, consistent with Viktor's clarification.

**The measurements and radar-equation model are reasonably close, but this recording does not establish a transferable implementation gain or loss.** The initial apparent 4 dB advantage compared different SNR statistics and references. Our current comparison leaves roughly 1.2–1.4 dB in favour of the measurement, with substantial uncertainty from the target and scene.

**The current reference point**

Using the complete contiguous inbound interval—39 CPIs over approximately 17–51 m—we obtain **33.9 dB, normalized to 100 m and 10 dBsm**, against the model's **32.7 dB**. A 37-CPI amplitude-selected subset gives 34.1 dB. These are R⁻⁴ fit normalizations, not measurements at 100 m.

We measure signal and background power separately per RX, average the channel SNRs in linear units, and then fit the range-normalized values in dB over time. There is no coherent RX combination or additional 9 dB RX credit. The background reference comes from the same range and near the same Doppler, in other CPIs when the reflector is away from that range.

The walking reflector is provisionally assigned **11.27 dBsm**, based on its reported 1.27 dB excess over the nominal 10 dBsm reference; we subtract that excess to report the 10 dBsm result above. The relative comparison is useful, but the absolute RCS remains uncalibrated. Viktor's hand calculation of 32.63 dB and the model's 32.67 dB agree closely.

**What happened to the original discrepancy?**

We approximately reproduce the magnitude-sum plot's 36.7 dB normalization. A magnitude sum is a valid statistic, but it is not the conventional signal-power/noise-power SNR. Channel averaging, the background reference and the RCS assumption all matter. They do not provide three unique, independent corrections that add up to exactly 4 dB.

Averaging in linear units versus dB changes the answer appreciably because this target fluctuates. For all 39 inbound CPIs, the chosen 33.9 dB summary becomes 34.5 dB with fully linear averaging over time, or 32.5 dB with dB averaging across both channels and time. These describe different properties of the same data; near-exact agreement under one convention is not precise model validation.

The noise estimate is much less sensitive: changing the control times, reflector exclusion distance or averaging region changes the reference by less than about 0.1 dB. Different background estimators agree within about 0.1 dB too.

**The target varies much more than the noise estimate**

**Only the inbound leg is used for the sensitivity benchmark.** The outbound peak-cell signal power is approximately 12.5 dB weaker after range correction. It is not treated as a calibrated reflector measurement; we retain it for diagnostic comparisons and use target-free regions as background controls. Maintaining reflector alignment or avoiding obscuration while walking away may be harder, but the cause of the difference is not established.

The stronger inbound return does not establish that the reflector achieves its assumed RCS. Even within that interval, observations below and above 30 m give normalized averages differing by about 1.3 dB. Reflector pointing, the person carrying it and propagation remain plausible contributors.

There are also large, changing RX differences, including deep nulls. Fixed amplitude calibration cannot explain the whole effect. In one example, a channel is 28 dB below the strongest channel at the selected cell, but 16 dB below when power is integrated over a surrounding patch. Composite returns and motion are plausible; the mechanism is not identified.

**Two distinct background effects**

First, the relatively stable additive background varies with range/beat frequency: it falls roughly 0.6 dB over 15–50 m and is higher there than in the far quarter used by the original estimator. We do not know why. Filtering is a candidate, but the noise curve does not establish that the signal receives the same filtering.

Second, the strong reflector has a **broad Doppler pedestal localized around its range**. On the inbound leg, background at that range is elevated by about 1.2 dB even at absolute velocities beyond 20 m/s. The excess tracks target strength; displaced ranges show little corresponding elevation. This supports a signal-dependent disturbance, possibly phase/amplitude modulation, but does not identify oscillator phase noise.

For the radar-equation comparison we use the additive background without that target-associated elevation. If the pedestal scales with target power, a weak target's own pedestal should become negligible near detection threshold. Strong other returns can still create a dynamic-range problem. The pedestal's range extent and physical cause remain open.

**CPI duration is not the main issue in the inbound benchmark**

Reprocessing 128–1024 chirps gives nearly the expected integration gain inbound: the median additional deficit from 128 to 1024 chirps is about **0.2 dB**. Outbound it is about **1.4 dB**, with much broader Doppler structure. Pedestrian/hand-held-reflector motion can contribute, especially outbound. These results argue against several dB of additional CPI loss in the inbound benchmark; they do not measure total hardware coherence loss.

**What next?**

A controlled measurement should now be more informative than further refinement of this walk: a stationary tripod reflector at several ranges, a TX-power sweep at each range with unchanged RX settings, and reflector-absent background captures. Repeat selected points at another height or a small displacement to assess multipath. Measure the reflector's physical dimensions and, ideally, make an independent RCS comparison. Covering exposed stand parts with absorber is a useful control, although earlier characterization suggests a small stand contribution.

Sensitivity validation and phase-noise/dynamic-range work can share a measurement session while retaining separate objectives. The earlier chamber questions about channel group delays and the covariance cell selection remain unresolved by this walk.

For now, retain this as a useful radar-equation reality check without applying a general hardware correction or transferring the chamber's measured coherent-summing gain into a range budget. Pd/range comparisons should follow separately with consistent target, Pfa, antenna and waveform assumptions.

## Scope and decisions

The immediate objective is a measured single-TX, per-RX SNR reference for the
radar equation. The study is separate from the
[Lannik Psi design study](../2026-09-02_lannik-psi/NOTES.md). We will scale
antenna, waveform, array and detection assumptions with our own models once
the empirical reference is understood.

- Use the complete 39-CPI inbound interval as the main descriptive reference,
  with the selected37 result for comparison. Choosing the inbound leg is itself
  a choice of target presentation; it is not an unbiased sample of the full walk.
- Exclude outbound from the absolute-RCS sensitivity benchmark. Retain it for
  diagnostics and target-free background controls; its weaker return does not
  invalidate noise samples away from the reflector. Inbound being stronger does
  not validate its assumed RCS either.
- Estimate additive background at the target's range and Doppler from control
  CPIs. Keep the strong target's pedestal as a separate dynamic-range observation.
- Preserve per-RX results and state both spatial and temporal averaging.
- No general implementation correction, chipset/antenna preset change or
  validated 1 km forecast follows from this dataset.
- Keep sensitivity and phase-noise investigations separate in objective.
  They can share a measurement session and identified raw captures.
- Prioritize a controlled stationary-reflector measurement over further
  refinement of the current walk fit.

The repo's default branch is `main`. This study started on
`carkit-validation-study` from local `main` at `526d2b9`.

## Evidence and reproducibility

| Input / artifact | Role and limits |
|---|---|
| [Current report](inputs/CARKIT%20report.pdf) | 17 pages, dated 2026-09-22; supersedes the earlier report provisionally, still under review |
| [Earlier report](inputs/empirical-1km-snr-budget.pdf) | Historical source; its fit and extrapolations are not the current reference |
| [Copied Slack thread](inputs/slack/slack.txt) | Source for processing clarification and the relative reflector assignment |
| [Latest reflector plot](inputs/slack/reflectors-angle-aligned.png) | Explicitly identifies walking reflector as +1.27 dB versus nominal reference; no absolute calibration |
| `/Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi` | External raw recording; 200 CPI JSON/bin pairs, not stored in this repo |
| [Model setup](carkit_walk.py) | Nominal model is useful; printed +3.90 dB comparison remains historical and is **not** an approved correction |
| [Raw-data analysis](analyze_walk_adc.py) | Original independent tracker, per-RX extraction, report-statistic reproduction and slope checks |
| [Independent audit](audit_walk_adc.py) | Averaging order, local covariance and RX spectral-null checks |
| [Dynamics analysis](analyze_walk_dynamics.py) | CPI length, Doppler structure and target-conditioned background |
| [Current reference calculation](analyze_walk_reference_snr.py) | Same-range, near-Doppler target-free background and explicit averaging alternatives |
| [Detailed independent review](INDEPENDENT_REVIEW.md) | Methods, numerical checks, controls and qualifications, including second-review diagnostics |

All 200 supplied binary hashes and common waveform/layout metadata passed
the audit. Recomputed common-cell SNRs for 86 CPIs matched the original
analysis CSV. This validates consistency of the supplied conversion and our
processing; it does not independently decode the original proprietary data.
Viktor's original analysis code and chamber raw/calibration data have not been
supplied here.

Run from the repository root, with the raw capture available at the stated path:

```sh
source venv/bin/activate
python studies/2026-09-11_carkit-validation/carkit_walk.py
python studies/2026-09-11_carkit-validation/analyze_walk_adc.py /Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi
python studies/2026-09-11_carkit-validation/audit_walk_adc.py /Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi
python studies/2026-09-11_carkit-validation/analyze_walk_dynamics.py /Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi
python studies/2026-09-11_carkit-validation/analyze_walk_reference_snr.py /Users/patrik/Data/tmp/walk-hallesaker-tx1-1-psi
```

Run the raw analysis first because the later scripts reuse its target coordinates
and selections. JSON/CSV outputs live under `generated/walk_adc`, `audit`,
`dynamics` and `reference_snr`. Plots are generated locally; selected shareable
copies are under `deliverables/2026-09-29`.

Analysis runs and repository Black/flake8/strict-mypy checks passed. The second
review also tested a synthetic real ADC tone through the CPI processing,
recovering 3.06/6.01/9.09 dB against ideal 3.01/6.02/9.03 dB gains.

## Measured configuration and model assumptions

| Quantity | Current value / status |
|---|---|
| Hardware | CTRX8188F + FARAD-IV, identified by user |
| Active channels | TX1 only, RX1–8; no DDMA in this capture |
| Raw layout | Little-endian real int16, [1024 chirps, 512 fast-time samples, 8 RX] |
| TX backoff / RX gain code | 0 dB / 0 reported; actual board power and NF remain unmeasured |
| Sample rate | 50 MS/s, confirmed by JSON |
| ADC payload / PRI | 10.24 / 15.96 microseconds |
| Sampled bandwidth | 100.781248 MHz; slope approximately 9.841919 MHz/microsecond |
| Carrier step / RF center | 0 Hz / approximately 76.374237 GHz |
| Windows / padding | Blackman on both axes, fourfold padding confirmed in Slack; independent analysis uses periodic Blackman |
| Sampled integration / CPI span | 10.48576 / 16.34304 ms |
| Model TX power / NF | 14.5 dBm / 10.2 dB; datasheet-based preset, NF specified at 10 MHz |
| Model TX / RX gain | FARAD-IV digitized boresight cuts, approximately 15.045 / 14.984 dBi |
| Target direction | Boresight assumed; precise geometry, heights and pointing unavailable |
| Walking reflector RCS | Provisionally 11.27 dBsm; all headline comparisons normalized to 10 dBsm |
| FFT processing gain / window losses | 57.20 dB / 4.74 dB total |
| Residual straddling / CFAR loss in model | 0 / 0 dB; matched-filter SNR comparison, not CFAR detection |
| Native range / Doppler spacing | Approximately 1.487 m / 0.1201 m/s |

Start frequency + slope × ADC pre-payload delay + half sampled bandwidth
matches 76.374237 GHz. The older raw-analysis diagnostic omitted the delay
when computing its alternative center frequency; this explains the apparent
54.5 MHz discrepancy.

The Blackman ENBW loss is about 2.37 dB per axis. Fourfold padding leaves at
most about 0.068 dB scalloping per axis for a tone. It does not remove the ENBW
loss or create integration gain.

The full reflector trajectory is approximately 3–55 m. The descriptive clean
intervals are outbound CPIs 26–70 (45 points, 15.25–50.20 m) and inbound
89–127 (39 points, 16.73–50.57 m). Initial and late tracked peaks need care;
not every detected peak in all 200 CPIs is the reflector.

## Current SNR reference: exact definition

Each RX's signal power `P[j,i]` is read at one common range–Doppler cell,
located using the mean of noise-normalized RX powers. No complex RX summation
or digital amplitude equalization is applied.

The baseline `N0[j,i]` comes from other CPIs, within +/-1.487 m and +/-1 m/s
of that target coordinate:

- Controls start at CPI 26. Through CPI 160, exclude controls whose tracked
  reflector is within 8 m of the requested range.
- CPIs 161–199 are treated as post-walk controls. This is an assumption tested
  by using only earlier or only later controls.
- Primary estimator: median of pooled cell powers divided by ln(2), the
  complex-Gaussian/exponential-power mean correction.
- There are 128–139 control CPIs and approximately 19,000–21,000 pooled powers
  per observation. Windowing and padding correlate the powers; these are not
  independent sample counts.
- Corrected upper-10% trimming and an ordinary mean change the selected-frame
  result by approximately -0.01 and -0.11 dB respectively.
- Wider reflector exclusion, different control times, a single range bin and a
  narrower Doppler interval each change the complete-inbound result by <0.1 dB.

For the headline fit, use:

```text
q[j] = mean_RX(P[j,i] / N0[j,i])
A[j] = 10 log10(q[j]) + 40 log10(R[j] / 100 m) - 1.27 dB
reference = mean_CPI(A[j])
```

This averages per-channel SNRs, not raw powers with unequal noise floors. Using
`sum(P)/sum(N0)` changes the all-inbound anchor by only -0.055 dB here.
The code uses `P/N0`; subtracting `N0` from the numerator changes the
all-inbound mean by -0.000028 dB at these high SNRs.

| Statistic, target-free reference and 10 dBsm normalization | All inbound39 | Selected37 |
|---|---:|---:|
| Linear RX average, dB temporal fit (headline) | **33.86 dB** | **34.09 dB** |
| Linear RX average, median over range-normalized frames | 33.27 dB | 33.35 dB |
| Linear RX and linear range-normalized temporal average | 34.49 dB | 34.64 dB |
| dB average across RX and frames | 32.53 dB | 32.73 dB |
| Nominal model | 32.67 dB | 32.67 dB |

These are distinct statistical summaries, not competing estimates of one
uniquely defined fading-target mean. The headline residual is +1.19 dB for
all inbound39 and +1.42 dB for selected37. No intrinsic hardware advantage or
loss is established. The all-inbound headline per-frame standard deviation
is 2.27 dB; p10–p90 is 31.74–37.49 dB, not a confidence interval on calibration.

Selected per-RX dB-fit anchors are
`[30.92, 33.32, 33.46, 34.29, 34.33, 31.99, 32.54, 31.02] dB`.
Keep the channel values available rather than hiding all variation in one scalar.

The reference assumes R^-4 scaling. Within inbound39, the normalized averages
are 33.14 dB below 30 m and 34.42 dB at 30–51 m. Free fits of absolute mean-RX
target power give -35.31 dB/decade inbound and -30.02 outbound, versus ideal
-40. The data therefore do not demonstrate common signal/noise filtering;
target and scene changes can overwhelm the small expected spectral trend.

## Background, pedestal, RX differences and CPI coherence

The additive baseline is relatively stable at fixed coordinates and decreases
roughly 0.6 dB over the measured 15–50 m band. It is around 1–1.5 dB above the
far-quarter reference, depending on mask/averaging. Possible causes include
IF/filter response and frequency-dependent receiver noise. The nominal NF at
10 MHz does not characterize the whole 1–3.4 MHz target beat band. We have not
established whether signal and noise share the same transfer function.

A second effect is excess remote-Doppler background associated with the strong
return's range. At absolute velocity >=20 m/s, inbound median elevation over
same-range controls is 1.21 dB, versus 0.05 dB outbound; displaced-range controls
are approximately unchanged. Inbound target power and the excess ratio have
Spearman correlation 0.92. In several strong frames the dominant background
spatial mode also aligns closely with the target vector. These are correlated
observations, not independent-sample proof of a particular mechanism.

The exact range extent and mechanism remain unresolved. Ordinary walking
velocities do not explain actual returns at 20–30 m/s, but modulation or
transients can spread energy there without such motion. The approximately
-60 dB excess per averaged Doppler cell relative to target peak is neither
dBc/Hz nor a validated phase-noise parameter. Shared-LO delay cancellation and
different chamber/field power/gain settings also prevent ruling out phase noise
by an R^-4 echo-strength comparison alone.

For additive-noise sensitivity, use `N0` without the target's own pedestal.
This does not reverse any peak-power loss from modulation or target motion.
Weak-target conclusions depend on pedestal scaling and on other strong scene
returns not imposing a background floor at that cell.

Median instantaneous strongest-to-weakest RX power spans are about 9 dB
outbound and 11 dB inbound, with extremes exceeding 27 dB. High SNR, fixed-gain
normalization checks and absence of ADC clipping rule out thermal fluctuations
or a single fixed gain imbalance as full explanations. CPI 100 RX8 changes
from -28.1 dB at the common cell to -15.8 dB in integrated patch power, and
shows a slow-time null near 7 ms. Patch energy is a structure diagnostic, not
an interchangeable single-cell SNR.

Composite reflector/person returns, pointing and propagation remain candidates.
Ordinary flat-ground two-ray interference does not automatically explain large
differences across an equal-height horizontal array; actual geometry matters.
The report's modest -0.69 to +0.76 dB amplitude spread in Table 2 is for TX,
not an RX amplitude characterization.

| CPI comparison, relative to 128 chirps | Inbound median deficit | Outbound median deficit |
|---|---:|---:|
| 256 chirps | 0.07 dB | 0.29 dB |
| 512 chirps | 0.07 dB | 1.05 dB |
| 1024 chirps | 0.20 dB | 1.41 dB |

The 1024-chirp inbound incremental deficit has p10–p90 -0.13 to +0.49 dB
with loss-positive sign. The full-CPI weighted best-tone fraction is approximately
0.93 inbound and 0.53 outbound. Of power within +/-2 m/s, the median fraction
outside +/-0.5 m/s is 0.88% inbound and 11.7% outbound. These support different
return structures on the two legs, without isolating oscillator coherence.
Removing low-Doppler content changes tone fractions only to 0.94 and 0.58.
Unwrapped phase near amplitude nulls is not a reliable oscillator-phase estimate.

## Reflector, calibration and sampling questions

The reflector was historically assigned 14 dBsm, then 10 dBsm. Neither is an
independent absolute calibration. The latest supplied angle-aligned comparison
explicitly identifies the walking reflector as 1.27 dB stronger than the
nominal 10 dBsm reference, supporting provisional 11.27 dBsm. Measure its actual
reflecting dimensions, geometry and orientation; use the appropriate ideal RCS
formula as an engineering benchmark and check far-field distance using the
largest dimension. An independent same-geometry comparison with a characterized
target is preferable to inferring RCS from the sensor model being validated.

Patrik reports prior evidence that stand scattering is small, with additional
suppression in the elevation sidelobes. It is a lower-priority uncertainty,
not the leading explanation for the residual. Absorber on/off remains useful
provided it does not shadow the reflector or introduce another scattering edge.

Nearly linear calibration phase versus RF frequency is consistent with relative
group delay. A fit and range-peak cross-check using a stationary reflector and
wide bandwidth remain desirable. The narrowband walk's exploratory delay
estimates have appreciable scatter and possible geometry/composite-target bias;
they do not validate chamber calibration slopes.

The report's covariance cell selection and handling of real sampling remain
open. Our analyses use positive physical range and both Doppler signs. Do not
include the conjugate range half as independent samples in spatial covariance.

The ordinary toolbox uses a complex-baseband scalar convention, default noise
bandwidth `B_n = f_s` and FFT gain `n_samples * n_chirps`, with no general
sampling-mode field. A scalar `noise_bandwidth_hz` override is not a real-ADC
or IF-filter model. Consistent real-tone signal and noise definitions do not
require a blanket 3 dB correction; halving noise bandwidth without also handling
the conjugate signal power would be inconsistent. Real versus complex sampling
still matters for covariance, aliases and shaped phase-noise spectra.
At the last review, the separate unmerged `phase-noise` branch had
`complex`/`real_phase_averaged` modes in a standalone diagnostic, without
changing the ordinary link-budget API.

The report's chamber coherent gains are setup-dependent in the presence of
signal-dependent background. They are not transferable thermal-noise gain
allowances. Our walk also does not settle chamber RX calibration or coherent-TX
performance.

## Next measurement and downstream scope

A practical shared measurement session should include:

1. Characterized stationary tripod reflector at several ranges, with recorded
   heights, pointing, polarization and raw configuration/calibration data.
2. TX-power sweeps at fixed range with fixed RX gain/filter settings, checking
   saturation and repeating levels to expose drift. Collect reflector-absent
   controls and, if supported without changing RX operation, TX-off controls.
3. At selected ranges, change height or position slightly to assess multipath.
   Optional reflector/person-separated captures address the walk's composite RCS.
4. Keep the zero-Doppler reflector signal: avoid slow-time mean subtraction
   or DC rejection that would erase it. Use controls for stationary clutter.
5. For sensitivity, find a regime with clear target detection and negligible
   target-dependent background. For dynamic range, quantify background versus
   strong-return power, propagation delay and Doppler offset.
6. If feasible, compare similar received target powers at different ranges.
   This helps distinguish received-power scaling from delay dependence, but
   does not alone identify phase noise. Preserve raw data for both studies.

Pd around 50% at 1 km is an informal Psi objective, not a validated CARKIT
result or fixed requirement. The earlier 1 m² Swerling-1, Pfa=1e-6 case is a
reference scenario. For one coherent look it needs about 12.77 dB mean SNR
at Pd=50%; different detector/target assumptions change the threshold.

The report's Section 3.2 extrapolates to coherent TX/RX single-scan Pd against
a 1 m² Gaussian-amplitude target (Swerling 1 if constant within each scan).
Its approximately 950 m and the older toolbox's 994 m are not equivalent
validation points: the report's 13 dB threshold corresponds to Pfa around
2.16e-9, whereas the older toolbox example used 1e-6 plus June config-3
antenna/processing assumptions, including 17 dBi gains. Do not compare those
ranges without harmonizing assumptions.

Track acquisition/maintenance will require frame rate, fluctuations,
miss correlations and tracker behavior. Do not derive acquisition probability
from a single-scan Pd or adopt a confirmation rule at this stage.

## Historical results that must not be reused as current corrections

- **+3.90 dB:** direct comparison of report 36.57 and model 32.67. Different
  statistics, noise references and provisional RCS; not an implementation gain.
- **32.62 dB versus 32.67 dB:** early broad-band-noise/geometric-RX result.
  The claimed near-exact validation and three-term reconciliation were
  superseded by averaging and target-free-reference checks.
- **32.80 dB “linear alternative”:** linear combination of per-RX intercepts
  already averaged in dB over time. It did not average RX powers within CPIs.
- **33.89 dB:** selected37 linear-RX/dB-time result with broad 15–51 m noise,
  superseded for the current reference by target-free selected37 34.09 dB
  and complete-inbound39 33.86 dB.
- The reproduced far-reference magnitude sum gives 36.71 dB for inbound39 or
  36.94 dB for selected37. The report uses 33 selected observations and 36.57 dB;
  exact generating-code/mask equivalence has not been established.
- The early 1.69 dB magnitude-sum offset was relative to geometric RX averaging.
  It is only 0.34 dB relative to linear RX averaging under the same far-noise
  reference and dB fit; the rest is an averaging-order difference.

The detailed chronological investigation is retained in
[NOTES_HISTORY.md](NOTES_HISTORY.md). Current takeaways and the Slack draft
are dated 2026-09-29; no changes have been posted externally.
