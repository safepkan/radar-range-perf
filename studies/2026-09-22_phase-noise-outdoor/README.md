# Outdoor reflector captures, 22 September 2026

The captures show a broad background plus additional, predominantly phase-like
fluctuations localized at strong-return ranges. A substantial part of the latter
is shared between RX channels and scales almost exactly with apparent delay.
The data supports a common phase/frequency disturbance. It does **not** yet
identify its hardware origin or establish that the CW datasheet spectrum alone
explains it.

The [static scene](../../local/phase_noise_outdoor/01_static.png),
[range–Doppler maps](../../local/phase_noise_outdoor/02_maps.png),
[range cuts](../../local/phase_noise_outdoor/03_cuts.png) and
[delay scaling](../../local/phase_noise_outdoor/08_delay_scaling.png)
are the most useful starting points. Generated files are local artifacts;
the scripts and this report are the reproducible study.

The [figure gallery](../../local/phase_noise_outdoor/index.html) collects all
12 figures with links to the full-resolution images.

## Summary: conclusions and next decisions

**The data establishes a return-associated, broadband fluctuation with a
substantial shared phase component. It does not yet establish which hardware
mechanism produces it.** The current CW-datasheet calculation does not explain
its level and range structure on its own.

| Observation | Supported conclusion | Remaining limitation |
|---|---|---|
| Broad Doppler ridges coincide with several strong-return ranges. Changing the Doppler window changes high-Doppler power by less than 0.04 dB after noise-bandwidth correction; fitted smooth-drift leakage is over 70 dB lower. | The distant ridge is caused by actual fast fluctuations, not ordinary leakage of the carrier or its smooth drift. | This does not prove randomness or identify oscillator phase noise. The bins near zero Doppler contain drift and the windowed carrier. |
| Detrended phase power exceeds fractional-amplitude power by 2.6–9.4 dB at the reflector, and fluctuations are correlated between RX channels. | A substantial part is phase-like and shared, rather than independent receiver noise or pure amplitude modulation. | The spectra also contain additive noise. Weaker returns make the distinction less clear. |
| Shared phase power scales closely with apparent delay squared between ranges for both waveforms. Doubling slope does not produce a comparable increase after delay normalization. | Delay-dependent phase/frequency disturbance is a useful working hypothesis. | Apparent and physical ranges are not independently reconciled; this is not a unique source identification. |
| Absolute broad background changes by only about 1 dB, while reflector levels change substantially. | Much of the higher long-range dBc background comes from the weaker reference peak. | Without paired empty-scene captures, it cannot be labeled a calibrated thermal floor. |
| Slow phase drift dominates much of the mean-removed covariance. | The initial low-rank structure is not independent proof of the broadband ridge mechanism. | Drift may involve motion, hardware, or both. |

The fast phase spectrum rises toward high absolute Doppler; it is not accurately
described as white phase noise. The phase/amplitude classification above uses
the detrended fast component, not the much larger smooth trends in the
complex-gain plots.

For the next session, prioritize a repeatable **two-range × two-slope** experiment
on a rigid mount, with matched reflector-absent references and a TX-backoff
comparison. This should establish whether the shared phase spectrum and delay
scaling persist in a simpler scene, and whether the excess scales with return
power. The detailed capture matrix and interpretation are below. A new empty
parking-lot capture on another day would not be a matched reference for these
data; take the new reference and reflector measurements together on the lawn.

For the toolbox, retain the sourced CW preset and current model as a baseline.
Do not raise its spectrum by 8–12 dB to fit these measurements: both the
mechanism and the shape of the excess remain unresolved. A separate empirical
chirp-to-chirp phase/frequency term is a candidate for later validation, not a
calibrated chipset property established by this study.

## Inputs and interpretation

Input root: `~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector`.
There are four directories, each containing ten CPIs. All 40 binary files match
their sidecar and manifest byte counts and SHA-256 checksums. The sidecars
explicitly specify little-endian signed int16, real sampling, and shape
`[1024 chirps, 512 samples, 8 RX]`. No layout inference is needed. Each CPI is
8 MiB. The declared ADC resolution is 12 bits; the observed extrema across all
captures are -1180 and +1074, with no samples at the signed 12-bit rails. This
checks ADC clipping, not compression elsewhere in the analog chain.

Both variants use TX1, zero TX backoff, 50 MS/s and approximately 15.96 µs PRI.
The dummy count is one in the configuration; it is not part of the 1024-sample
chirp axis. The sidecars report RX gain **+3 dB**, rather than the earlier verbal
-3 dB. The gain-code interpretation should be confirmed before an absolute
receiver calibration; the present ADC-unit and measured dBc results do not
depend on interpreting that code. All high-pass codes are zero. The analysis
does not independently decode the legacy configuration or verify its HPF mapping.

| Folder bandwidth | Actual payload bandwidth | Actual slope | Payload RF span |
|---|---:|---:|---|
| 400 MHz | 399.609376 MHz | 39.024353 MHz/µs | 77.8000–78.1996 GHz |
| 800 MHz | 800.390656 MHz | 78.163150 MHz/µs | 77.6000–78.4004 GHz |

The centre frequency is approximately 78 GHz, so model overlays use the **upper
77–81 GHz** Infineon table. Actual metadata slopes determine all measured range
axes. Capture timestamps are unavailable; CPIs are analyzed independently and
averaged in power, never concatenated into a supposedly continuous time series.
There are no reflector-absent captures in the supplied directories.

## Stationary scene and the reflector reference

The presumed reflector is the strong nearby peak that moves from roughly 6 m
to roughly 12 m between the nominal distance settings. The short-range region
is relatively clean away from this peak and the DC response. The environment
beyond about 16 m has substantial returns, especially around 24, 29 and 35 m.
In `400MHz-10m`, the approximately 29 m return is stronger than the presumed
reflector. Normalizing by the global map maximum would therefore use the wrong
reference.

| Capture label | Apparent reflector range | RX1 reflector peak [dB ADC-count²] |
|---|---:|---:|
| 400MHz-5m | 5.72 m | 46.93 |
| 800MHz-5m | 6.27 m | 48.70 |
| 400MHz-10m | 12.00 m | 31.61 |
| 800MHz-10m | 12.06 m | 37.84 |

These are **apparent beat-derived ranges**, not surveyed positions. The folder
labels should not be treated as precise target ranges, and the two short-range
captures are not at the same apparent range. Possible placement/calibration
differences remain unresolved. The 400 MHz short-range peak also varies by about
4 dB across the ten CPIs. RX1 reflector strength at the long range differs by
about 6 dB between waveforms. That precludes interpreting their raw dBc floor
difference as a slope effect without accounting for the carrier reference.

The static profile uses an eight-times-zero-padded range FFT of each CPI's
chirp mean, then averages power across CPIs. Padding only locates peaks more
closely; it does not improve physical range resolution.

## Single-RX range–Doppler levels

The primary results use **RX1 alone**, a periodic Blackman–Harris range window,
a periodic Hann Doppler window, and native 512 × 1024 FFT sizes. Positive real-ADC
range bins are retained. FFT amplitudes are divided by the window sums; dBc is
relative to the mean power of the strongest native zero-Doppler bin in the
presumed reflector gate. No array integration gain is applied.

To avoid stationary leakage and slow motion/drift, the following numbers average
**power** over `|Doppler| > 5 kHz`, out to the approximately 31.33 kHz Nyquist limit.
They are power **per processed FFT bin**, not per Hz or integrated Doppler power.
The background is a median across range bins from 2–15 m, excluding ±1.5 m about
the reflector. It is a background proxy, not an independent thermal calibration.

| Capture | Background [dBc/bin] | At reflector range [dBc/bin] | At reflector above background |
|---|---:|---:|---:|
| 400MHz-5m | -79.09 | -73.96 | 5.13 dB |
| 800MHz-5m | -80.75 | -74.95 | 5.80 dB |
| 400MHz-10m | -64.44 | -63.36 | 1.08 dB |
| 800MHz-10m | -70.91 | -67.80 | 3.11 dB |

The absolute background stays within about **1 dB**: -33.07 to -32.05 dB
ADC-count²/bin. Much of the higher long-range dBc floor is simply a weaker
reflector above a similar absolute background. Typical squared RX-to-RX
coherence in the background is 0.0005–0.028, versus 0.033–0.50 at the reflector
range bin. This supports a largely channel-independent background plus a
correlated, return-associated excess; it does not prove the background is purely
thermal. It can include receiver/ADC noise and signal-dependent contributions.

The excess appears as narrow vertical structures around strong-return ranges,
not just as a uniform raised floor. It occupies much of the Doppler interval,
with higher phase fluctuation power toward high absolute Doppler. Comparisons
at 0.5–3 kHz are also saved in the range-cut figure. Low-Doppler maps contain
scene returns and slow variations and should not be interpreted wholesale as
random phase noise.

## Covariance: separate slow drift from faster fluctuations

### Reading the per-capture complex-gain plots

The panel titled “CPI 0; static mean removed” is a **slow-time trace before
the Doppler FFT**, not a selection of nonzero Doppler bins. Each chirp is
projected onto a Blackman–Harris-windowed tone at the measured reflector beat
frequency (the interpolated peak, rather than the nearest native range bin).
If the resulting complex coefficient is $z_m$, the plotted quantity is

$$
g_m = \frac{z_m-\bar z}{\bar z}.
$$

The mean and normalization are computed separately within each CPI. Division
by the complex mean aligns the real axis with the mean return: for small
fluctuations, $g_m \simeq a_m+j\phi_m$, where $a_m$ is fractional amplitude
and $\phi_m$ is phase in radians. Thus 0.01 on the real axis is approximately
1% amplitude variation; 0.01 on the imaginary axis is approximately 0.01 rad.
These are carrier-relative coordinates, not physical I/Q ADC channels.

Mean removal leaves slow drift and fast fluctuations alike. A smooth imaginary
trend indicates phase evolution through the CPI and contributes mainly near
zero Doppler. The finer fluctuations contribute at higher Doppler. Larger phase
excursions trace arcs, so phase alone also changes the real coordinate; the
“amplitude-like” label is only a small-perturbation interpretation. The scatter
panel combines all CPIs, whereas the time trace shows only the first CPI. The
separate detrended phase/amplitude spectra use angle and magnitude directly and
are better suited to classifying the fast fluctuations.

### Doppler-window leakage and other strong returns

`ridge_checks.py` checks four selected return ranges in each capture. It repeats
the Doppler calculation with a Blackman–Harris window, correcting its noise
bandwidth to the Hann reference and keeping the same carrier reference. Mean
power at $|f_D|>5$ kHz changes by less than **0.04 dB** across all 16 checks.
Reconstructing each return from cubic fits to its amplitude and unwrapped phase
gives smooth-drift leakage below -146 dBc/bin, over 70 dB below the measured
levels. This rules out ordinary window leakage from a constant or smoothly
drifting carrier as the explanation of the broad ridges. It does not prove
statistical randomness or exclude complicated deterministic hardware errors.
The central Doppler bins still contain the carrier's window response and drift.

All entries below use their **own native-bin zero-Doppler peak**, RX1, and mean
power per Hann bin over $|f_D|>5$ kHz. They include background, without subtraction.

| Capture | Reflector: range, ridge [dBc/bin] | Another strong return: range, ridge [dBc/bin] |
|---|---|---|
| 400MHz-5m | 5.72 m, -73.96 | 28.84 m, -59.29 |
| 400MHz-10m | 12.00 m, -63.36 | 29.16 m, -58.85 |
| 800MHz-5m | 6.27 m, -74.95 | 34.67 m, -59.54 |
| 800MHz-10m | 12.06 m, -67.80 | 34.69 m, -60.20 |

The farther return's detrended phase-to-fractional-amplitude power ratio is
9.68, 1.56, 7.41 and 9.61 dB, respectively. Thus the strongest farther ridges
also have phase-dominated examples, but phase dominance is not equally decisive
for every return. A clutter peak can contain multiple scatterers, and weak
returns have a larger additive-noise contribution relative to their carrier.
There is no universal ridge-to-peak dBc level established for the whole scene.

### Covariance interpretation

[Covariance plots](../../local/phase_noise_outdoor/04_covariance.png) compare
uncentered real fast-time second moments, real covariance after subtracting
each CPI's chirp mean, and complex covariance of positive fast-time FFT bins.
These are fast-time sample/range covariances with chirps as observations, not
the covariance of an RX antenna array.

For the two short-range captures, the leading positive-range eigenmode accounts
for about **95% and 97%** of the mean-removed covariance trace. The real-sample
representation has two prominent modes, particularly clearly in `800MHz-5m`.
This resembles the suggested real/positive-range rank distinction.

However, the complex reflector coefficient has substantial **smooth phase drift
within each CPI**. Its mean equivalent Doppler ranges from about -9.5 to +16 Hz
across captures. This can arise from slight motion or hardware drift; the data
alone does not distinguish them. Merely subtracting a static mean leaves this
drift, which dominates the initial covariance. A low-rank covariance by itself
is therefore insufficient evidence for the broadband phase-noise mechanism.

[High-Doppler covariance](../../local/phase_noise_outdoor/07_high_doppler_covariance.png)
uses only `|Doppler| > 5 kHz` after Hann windowing. Several elevated modes remain
above a broad eigenvalue floor; the outdoor data are not a clean rank-one
positive-range process. Multiple scene returns, temporal variation of their
phases and possibly multiple disturbances contribute. Finite sample size and
IF filtering also mean the background eigenvalues need not be exactly flat.

## Phase versus amplitude, and a strong delay-scaling clue

For each strong return, a windowed projection onto its measured beat frequency
produces one complex coefficient per chirp. Unwrapped phase and fractional
amplitude are separately detrended with a cubic polynomial **within each CPI**.
Their Hann-windowed spectra are analyzed over the same high-Doppler band. This
removes the smooth drift from the diagnostic rather than labeling it noise.

At the reflector, the high-Doppler phase fluctuation power exceeds fractional
amplitude fluctuation power by about **7.4 and 9.4 dB** in the short-range cases,
and **2.6 and 6.0 dB** in the long-range cases. Estimator noise is included;
the weaker reflector makes the first long-range case less decisive.

The phase variations are also shared across RX channels. Real cross-spectra
averaged over distinct RX pairs estimate their common component while rejecting
uncorrelated channel noise in expectation. This uses other RX channels as a
diagnostic; it does not beamform or replace the single-RX power comparison.

| Capture | Common phase power [dB rad²/bin] | Equivalent frequency RMS, 5–31.33 kHz Doppler |
|---|---:|---:|
| 400MHz-5m | -75.48 | 16.80 kHz |
| 400MHz-10m | -68.98 | 16.94 kHz |
| 800MHz-5m | -76.40 | 13.79 kHz |
| 800MHz-10m | -70.52 | 14.12 kHz |

The equivalent frequency is defined by the diagnostic relation

$$
\delta\phi_m \simeq 2\pi\tau\,\delta f_m,
\qquad \tau=2R_{\rm apparent}/c.
$$

It is not a direct RF frequency measurement. The RMS integrates both signed
high-Doppler bands and corrects the Hann window's equivalent noise bandwidth.
It excludes fluctuations below 5 kHz and includes any aliasing into the measured
slow-time interval. Individual-CPI equivalent RMS estimates are approximately
15.8–17.9 kHz for the 400 MHz waveform and 12.8–15.2 kHz for the 800 MHz waveform.

The common phase power rises by 6.51 dB between the two 400 MHz ranges; the
measured range ratio predicts 6.44 dB. For 800 MHz, the observed rise is 5.88 dB
versus a 5.67 dB prediction. Dividing by delay squared brings each waveform's
two spectra into close agreement, as shown in the delay-scaling figure.
Strong farther scene returns also exhibit correlated phase variation, so a
disturbance confined to the reflector is not the only plausible explanation.

This is consistent with common RF frequency/chirp fluctuations converted to
return phase through delay. A fixed ADC sampling-time jitter alone would instead
make phase proportional to beat frequency, hence approximately double it when
the slope doubles at fixed range; that simple unchanged-jitter explanation
does not fit the observed scaling. Neither observation uniquely localizes the
source: chirp synthesis, timing coupled to waveform programming, LO paths,
motion and other hardware effects need controlled follow-up.

## Comparison with the current phase-noise model

The [model comparison](../../local/phase_noise_outdoor/05_model.png) uses the
measured apparent reflector ranges and matching FFT processing, upper-band
typical CW data, real sampling, all source noise provisionally shared, an ideal
IF filter, and constant extrapolation over a 1 Hz–20 MHz integration band.
The model PRI is rounded from the metadata's 15.9600003826 µs to 798 nominal
20 ns ticks (15.96 µs), avoiding an artificial fractional-clock integration.

Predicted reflector-only high-Doppler power at its range bin is approximately
-85.1 / -84.3 dBc for the short-range 400/800 MHz cases and -81.1 / -82.3 dBc
for the long-range cases. The measured total is higher, but includes the
background. Even the cross-RX common phase component is roughly 8–12 dB above
these total phase-noise predictions in the small-phase interpretation. Its
localization around strong-return ranges also differs from the model's broad
pedestal. This is evidence of a missing or underestimated effect, not evidence
that all of the measured background is oscillator phase noise.

Limitations of this comparison include assumed CW-to-chirp equivalence,
unmeasured shared/independent decomposition and extrapolated offsets. The
model does not include the other strong scene returns, actual HPF/decimation
responses, or independently calibrated propagation delay. The common-phase
coefficient spectra and the total periodogram use slightly different carrier
references (per-CPI coefficient versus mean native-bin peak); the numerical
comparison is approximate, not an exact subtraction or source specification.

### What this teaches us about the model

The experiment supports retaining delay dependence, real sampling, and explicit
FFT/window normalization in the comparison. It does not validate the particular
CW spectrum, its shared/independent decomposition, or its applicability during
chirps. Delay-squared phase power alone is not a unique test of the implemented
continuous-time source-noise model; several frequency-related disturbances can
have that scaling. There is no demonstrated implementation bug from these data.

One useful candidate for a separate empirical term is an effective frequency
error $\delta f_m$ that varies between chirps but is approximately constant
during each sampled payload:

$$
z_m = z_{0,m}\exp(j\,2\pi\tau\,\delta f_m).
$$

As an effective return-phase model, this multiplies the entire range tone by
one phase factor per chirp. It produces a ridge at that return's range response,
with Doppler structure set by the slow-time fluctuation spectrum. For small
errors it gives phase power proportional to delay squared. This explains why
it is worth testing alongside the existing model; it does not assert that
chirp frequency error is the physical cause. The measured spectrum is colored,
so an independent white error per chirp would only be an initial approximation.

If the new data reproduce the effect, fit this component separately using
cross-RX phase spectra, check its predictions at a held-out range or setting,
and retain the CW-based component and additive background separately. Do not
interpret the equivalent 14–17 kHz RMS values from this study as an RF source
specification: they describe only the selected aliased slow-time band under
the assumed delay conversion. Extending the full antenna/target performance
model remains premature until this single-return comparison is resolved.

## New measurements on the lawn

The objective is to reproduce and discriminate the fast return-associated
component, rather than merely obtain a lower-looking floor. A lawn still has
ground reflection and possible moving vegetation; inspect the zero-Doppler
scene and stability before interpreting it as a single-return experiment.

Keep the radar fixed and mount the reflector rigidly. Measure and record its
physical distance and height, radar height, orientation, and a scene photo.
Use nominal 5 m and 10 m positions, checking the apparent ranges against those
positions before completing the run. Switch waveforms without moving the
reflector. Record timestamps, capture order, actual waveform settings, TX/RX
settings and filter codes; confirm the RX gain and HPF code interpretation.
Retain all eight raw RX channels for correlation diagnostics while continuing
to use a single RX for the principal dBc comparison.

### Core capture matrix

| Reflector | Waveforms | TX backoff | Number of configurations |
|---|---|---|---:|
| Fixed at 5 m | 400 and 800 MHz | 0 and 10 dB | 4 |
| Fixed at 10 m | 400 and 800 MHz | 0 and 10 dB | 4 |
| Absent, radar and scene otherwise unchanged | 400 and 800 MHz | 0 and 10 dB | 4 |

Keep the current payload duration, sample rate, chirp count, PRI, RF centre,
RX gain and processing settings fixed for these comparisons. Take at least
ten CPIs per configuration, as in this study. Acquire the empty-scene blocks
close in time to the reflector blocks; repeat references if the scene changes.
Repeat one strong-reflector baseline at the end to detect session drift.
If the 10 dB backoff data become background-limited, retain them as a bound;
use the strong 0 dB captures to compare phase-spectrum shape.

| Comparison | Diagnostic outcome |
|---|---|
| Reflector present versus absent | A ridge that appears with the reflector links the excess to that return; a persistent feature suggests another scene return or system background. The comparison does not by itself locate the hardware source. |
| 0 versus 10 dB TX backoff | With unchanged fractional disturbance, the return-associated excess should follow the measured carrier power in absolute units and stay approximately constant relative to it. An additive floor should stay approximately fixed in absolute units. Departure can indicate a TX-setting-dependent effect or nonlinearity, so use the measured peak change rather than assuming exactly 10 dB. |
| 5 versus 10 m, same waveform | Test whether shared phase spectra divided by calibrated delay squared coincide again. Compare this component separately from the total background-contaminated dBc floor. |
| 400 versus 800 MHz, same physical position | Test whether the disturbance follows propagation delay or beat frequency, and whether the spectrum changes with slope. The present data favor delay scaling, but this controlled comparison removes placement ambiguity. |

Compare absolute ADC-unit power, own-carrier dBc, detrended phase/amplitude
spectra, and cross-RX phase spectra. Use the same processed-bin definitions
and report background-limited results as such. For empty-scene subtraction,
subtract averaged powers in linear units and retain uncertainty rather than
subtracting dB values or forcing negative estimates to a positive noise level.
Examine CPI-to-CPI repeatability before pooling all captures.
In particular, the **total** ridge-bin dBc level need not stay constant with
TX backoff: an unchanged additive floor becomes larger relative to the weaker
carrier. Apply the multiplicative-scaling test to the estimated excess or
shared phase component, not to the unseparated total.

### Targeted extensions if the core result repeats

At the strongest fixed-reflector setting, change PRI while preserving the
sampled ramp as far as hardware permits, and compare spectra in both Hz and
cycles per chirp with noise-bandwidth correction. This tests sensitivity to
chirp timing/aliasing; it does not uniquely identify the source. Separately,
vary pre-payload settling or dummy-chirp count if practical. Log any coupled
changes to PRI, RF start/centre or ramp timing so they are not mistaken for an
isolated settling test. These tests become worthwhile once a repeatable excess
has been established in the simpler scene; a large parameter sweep is not
needed for the first session.

## Handoff for the next session

Keep the phase-noise implementation and this study together on branch
`phase-noise` while awaiting the next measurement session. Revisit the model
and the longer-term organization of measurement studies after analyzing the
new captures. No empirical correction to the chipset preset, new disturbance
model, or antenna/target-performance integration has been agreed or implemented
from these measurements. The focus remains the Infineon chipset; additional
TI phase-noise data/presets are deferred.

The README and four Python scripts preserve the findings and reproducible
analysis. Raw binaries, sidecars and manifests remain outside Git at the input
path above and must be retained separately. Generated figures, the HTML gallery,
JSON summaries and NPZ arrays are in ignored `local/phase_noise_outdoor/`;
they can be regenerated from those raw inputs. A fresh checkout alone does not
contain the measurements or rendered figures.

Start a fresh session by reading this README, then:

1. Locate the new raw data and measurement log. Resolve physical versus apparent
   range, reflector mounting, gain/filter interpretation, and which reference
   and TX-backoff captures were actually acquired.
2. Create a separate dated study/output directory for the new session. The
   present scripts are specific to this capture layout: folder names encode
   range, reflector gates assume a target is present, plots assume four cases,
   and some summary discovery uses `*MHz-*m.json`. Adapt these assumptions for
   empty-scene/backoff variants rather than blindly running the new matrix
   through the existing scripts or overwriting this session's results.
3. Repeat the single-RX spectra, leakage checks, detrended phase/amplitude and
   cross-RX diagnostics before fitting a model. Test repeatability and the
   comparisons in the measurement plan above.
4. Decide whether the existing CW model suffices with better-characterized
   inputs, whether a separate empirical component is justified, or whether
   targeted hardware measurements are needed. Keep hypotheses distinct from
   sourced chipset specifications.

Related implementation and explanation: [phase_noise.py](../../radarperf/phase_noise.py),
[model documentation](../../docs/phase_noise.md),
[chamber example](../../examples/phase_noise.py), and
[tutorial](../../docs/phase_noise_tutorial.md).

## Reproduction and checks

From the repository root:

```sh
source venv/bin/activate
export MPLBACKEND=Agg
export MPLCONFIGDIR=/tmp/radarperf-mpl
export OPENBLAS_NUM_THREADS=1
venv/bin/python studies/2026-09-22_phase-noise-outdoor/analyze.py \
    ~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector
venv/bin/python studies/2026-09-22_phase-noise-outdoor/diagnostics.py \
    ~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector
venv/bin/python studies/2026-09-22_phase-noise-outdoor/ridge_checks.py \
    ~/Data/carkit/2026-09-22_phase_noise_outdoor_reflector
venv/bin/python studies/2026-09-22_phase-noise-outdoor/verify.py
```

Outputs default to `local/phase_noise_outdoor`: per-case JSON summaries, NPZ
arrays, and PNG figures. `analyze.py --rx N` selects the primary single RX;
`diagnostics.py` reads that selection from the generated summaries. Re-run
diagnostics after analysis, which regenerates the summaries. Neither script
modifies the input directory. Capture identity/shape/checksum assertions must
remain enabled; do not run the analysis with Python's `-O` option.

Synthetic real-ADC captures with known independent noise and injected common
phase noise verify both FFT normalization and the cross-RX phase estimator:
recovered powers are 0.9959 and 0.9897 times their theoretical expectations.
Repository formatting, lint and strict type checks pass.
