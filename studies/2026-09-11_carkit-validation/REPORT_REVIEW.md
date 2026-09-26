# CARKIT measurement report: current assessment

2026-09-26. Review of [`inputs/CARKIT report.pdf`](inputs/CARKIT%20report.pdf),
17 pages, dated 2026-09-22. The report is still under review and appears to
supersede the six-page report assessed later in this file. No raw ADC data or
analysis code accompanied it, so all measurements remain reported rather than
independently reproduced.

**Assessment:** the useful validation datum is the single-TX field fit for the
nominal 10 dBsm reflector: 36.57 dB at the fit's 100 m normalization point.
Under the explicit provisional assumptions in `carkit_walk.py`, the toolbox
predicts 32.67 dB, giving a report-minus-model offset of +3.90 dB. Keep that as
a scoped empirical correction and reality check. The laboratory coherent-array
results and the report's 1 km/Pd extrapolation should not be used as inputs to
our range model.

## Comments already raised and supported by this review

- The nearly linear calibration phase versus frequency in Figures 1–2 is the
  expected signature of approximately constant relative group delay. Fit a
  line for every channel, report the delay and fit residual, and state the sign
  convention explicitly: the slope of the plotted *correction* phase has the
  opposite interpretation from the slope of the uncorrected channel response.
  Per-RX reflector-range estimates, using a zero-padded range FFT plus quadratic
  peak interpolation, provide a direct cross-check.
- Section 1.4 must say exactly which range–Doppler cells and frames formed the
  covariance. For real ADC samples, the negative-frequency half is conjugate-
  related to the positive half (with both FFT coordinates reflected). Treating
  both halves as independent observations symmetrizes and can distort the
  spatial covariance and its eigenmodes. Use only the physical range half.
- The growing spatially correlated background is consistent with a
  signal-dependent multiplicative impairment such as phase noise: to first
  order its perturbation is proportional to `j S delta_phi`, so it follows the
  target steering vector and scales with target signal. In this strong-reflector
  chamber setup it prevents a meaningful receiver-noise-limited assessment of
  coherent SNR gain.
- Consequently, the measured 7.14 dB coherent-RX gain from the chamber must not
  be transferred into a field range budget. The impairment depends on the
  strength and spectrum of strong nearby returns, not on the distant target
  alone. A model of phase noise acting on clutter and other strong reflectors is
  the relevant eventual range-analysis extension, but is outside this report's
  scope.
- Section 3.1 should reduce the field result to one clearly defined reference
  point, preferably per RX channel, with the exact signal and noise estimators.
  The theoretical scaling can then be done separately and compared afterward.
- The zero-mean circular complex Gaussian target model in Section 3.2 is the
  usual Swerling-1 model (assuming one realization is held during a scan and is
  independent between scans).

## Additional substantive comments

**The 36.57 dB anchor is a selected fit, not a measurement at 100 m.** Figure 10
says the fit uses 33 observations between 15 and 51 m that lie within 6 dB of a
local R^-4-corrected peak in a +/-5 m neighborhood. The fit is then normalized
at 100 m. This is an upper-tail selection whose result depends on the 6 dB and
5 m choices. The report should state this wherever 36.57 dB is introduced and
show the result's sensitivity to the selection, or preferably provide ordinary
per-frame values and a robust all-point summary alongside it. It should also
make clear whether both walking directions were eligible.

**The signal/noise definition is still missing.** For both Table 5 and the field
anchor, specify the FFT normalization, target-cell or peak-search definition,
noise mask and estimator, channel normalization, whether `S` means total
target-cell power or noise-subtracted signal power, and whether the reported
ratio is `S/N`, `(S-N)/N`, or another statistic. Supply per-channel values. A
normalized mean of eight RX powers has the same mean SNR as a representative
single channel when channel SNRs are equal; calling it an eight-channel gain
invites confusion.

**Windowing and zero-padding must be quantified.** Table 6 does not state the
range or Doppler windows, and Figure 10 only says that zero-padding was used.
Window choice determines the two noise-equivalent-bandwidth losses; zero-padding
only reduces residual sampled-bin scalloping and does not remove window loss.
State both padding factors. Pending clarification, this study assumes Blackman
on both axes and enough padding for zero residual straddling loss.

**The covariance result needs a more precise name and construction.** If the
cell set includes target mainlobe/sidelobe energy, phase-noise skirts, leakage,
clutter, or heterogeneous noise variance, the matrix is a covariance of the
selected *background/residual*, not necessarily receiver noise. Mean removal
does not remove deterministic structure that varies between cells. State the
mask relative to the target, any power normalization, and whether samples from
multiple frames were pooled. Hann overlap/correlation reduces effective sample
count, as the report notes, but the more important issue is whether those
samples can reasonably be treated as draws from one stationary distribution.

**Normalized eigenvalue fractions alone do not demonstrate growth.** Figures
6–9 should be accompanied by absolute eigenvalues or mode powers versus target
signal power/TX count, including 1 TX and 2 TX if available. Repeating at more
than one TX backoff or reflector strength would test the expected multiplicative
scaling directly. Alignment with the target steering vector and disappearance
toward absorber are evidence for a target-path-related component, but they do
not establish that a mode "comes from the target"; leakage, phase noise,
multipath and other signal-dependent mechanisms remain possible.

**The field car and reflector fits are not equivalent estimators.** Figure 10
compares a median of 41 per-track car intercepts with the reflector's locally
selected upper-tail observations; the candidate cars are not ground-truth
classifications. Their 0.90 dB proximity is descriptive, not evidence that the
car population has approximately 10 dBsm RCS. This comparison is not needed for
the single-point model validation.

**There are two numerical/terminological inconsistencies to fix.** Section 1.4
quotes 7.19 dB measured coherent-RX noise reduction, whereas Table 5 and Section
3.1 imply 78.47 - 71.33 = 7.14 dB. Table 3's "ADC-bandbredd" of 200.391 MHz is
the sampled RF chirp bandwidth, not ADC bandwidth for a 25 MS/s ADC. In Table 6,
16.34 ms is the 1024-ramp coherent processing interval; 120 ms appears to be the
frame period, not a second definition of CPI. These labels matter when the
result is scaled by integration time.

**Calibration uncertainty should be visible.** Figures 1–2 average ten CPIs but
show neither scatter nor fit residuals. Add phase standard deviation/error bars
or a compact table. The linear-delay fit residual is especially useful: it
separates ordinary channel delay from any genuinely frequency-dependent
dispersive behavior. The target's finite-range geometry and the fact that these
are correction weights, not raw channel phase, should be included in the delay
interpretation.

## Provisional point-model comparison

The current comparison uses:

- 10 dBsm, nonfluctuating reflector;
- one TX at the controlled-datasheet preset 14.5 dBm;
- FARAD-IV boresight gains, 15.045 dBi TX and 14.984 dBi RX;
- 76.374237 GHz, 50 MS/s, 512 samples and 1024 chirps;
- controlled-datasheet 10.2 dB RX noise figure;
- Blackman range and Doppler losses, 2.37 dB each;
- zero residual range/Doppler straddling and no CFAR loss; and
- the toolbox `B_n = f_s` matched-filter/complex-sample convention.

It predicts 32.67 dB at 100 m. The difference to 36.57 dB is +3.90 dB. The
sign is worth emphasizing: interpreted as an additive model correction it is
positive; interpreted as a conventional loss subtracted from the model it would
be -3.90 dB. It therefore should be called an empirical SNR offset, not an
implementation loss. RCS, installed gains, target angle/orientation,
propagation, peak selection and noise conventions are all entangled in it.
Prior measurement characterizations reportedly found the reflector stand
negligible, with additional suppression from its position in the elevation
sidelobes. Stand scattering is therefore not a leading explanation for the
offset; absorber over its exposed parts remains a useful low-cost control in a
new reference measurement.

## Secondary observations on Section 3.2

The 13 dB power threshold corresponds, under the report's known-noise
single-complex-cell model, to `Pfa = exp(-10^(13/10))`, approximately 2.16e-9.
That is a threshold choice rather than an SNR requirement. It does not include
noise-estimation/CFAR loss or the multiple-testing effect of a range–Doppler
search. The report acknowledges the latter and the mismatch between its
peak-selected anchor and fixed-cell probability model. Given those caveats and
the invalid transfer of chamber RX gain, reproducing the report's Pd curves is
not a priority for this validation study.

---

# Earlier six-page report: initial assessment

The initial broad review is retained for traceability. The study's current
scope and priorities are in [`NOTES.md`](NOTES.md): match measured setups,
starting with single TX and noncoherent RX. The report's coherent-TX
extrapolation and 15 dB requirement are not adopted as study objectives.

2026-09-11. Review of
[`inputs/empirical-1km-snr-budget.pdf`](inputs/empirical-1km-snr-budget.pdf),
all six pages, including plots. The underlying ADC recordings, configurations,
calibration files and analysis scripts referenced by the report are not supplied
here. Measurements below are reported results, not independently reproduced
measurements. Arithmetic and comparisons with this repository were checked.

**Assessment:** useful evidence for validating the CARKIT implementation and
eventually calibrating the Psi link budget. The headline 9.46 dB is the gap
between a constructed performance scenario and a chosen requirement. It is not
a measured discrepancy against our chipset model. Do not change the chipset
power, noise figure or global implementation loss from this report alone.

## What was done

1. **Relative reflector comparison, p. 2.** Two stationary reflectors at
   2.215 and 2.507 m were illuminated with TX1 while the radar rotated through
   -30 to +30 degrees. The initial 400 MHz profile could not separate returns
   only 0.292 m apart. A 2.4996 GHz profile with 0.0600 m bin spacing could.
   Thirty received frames were collected per angle after 0.5 s settling.
   After range correction by R^4 and horizontal alignment, the left target
   was 1.27 dB stronger, with a fitted -8.95 degree shift and 0.32 dB RMS
   residual. This establishes similar *apparent relative* RCS in that setup.
   The walking reflector was assigned 10 dBsm instead of the previous 14 dBsm;
   that absolute value remains an assumption. No measured stand correction
   was subtracted.
2. **Single-TX walk, p. 3.** A pedestrian carried the reflector out and back,
   approximately 4.5–55 m. There were 200 raw ADC frames and 137 saved track
   observations: 63 outbound and 74 inbound. TX1 was enabled with no TX
   backoff, all eight RX channels were recorded, and RX gain code was zero.
   Each frame had 512 samples by 1024 ramps, a 10.24 microsecond sampling
   payload, 15.96 microsecond PRI and 100.781 MHz sampled bandwidth.
   Processing used Blackman windows in range and Doppler, per-channel noise
   normalization and an average of RX powers. It did not sum complex RX
   signals. The full Doppler FFT was retained; this was not an eight-TX MIMO
   measurement.
3. **Fit to selected walk samples, p. 3.** Within 15–51 m on the inbound leg,
   the maximum SNR in each occupied range bin was selected, giving 24 samples.
   The range exponent was fixed, not estimated:
   `SNR_dB = 115.746526 - 40 log10(R/m)`, with 1.885 dB scatter.
   Subtracting the assumed 10 dBsm gives the unit-RCS constant
   `C = 105.746526 dB`. The plot time was inferred from range slope and Doppler,
   rather than trusted capture timestamps.
4. **Separate TX subset experiment, pp. 4–5.** Lab angle sweeps compared TX1,
   TX1+6, TX1+6+7+8, and all eight. They used 399.61 MHz bandwidth, 20 dB
   backoff per active TX, RX gain code two and identical zero phase-code
   increments. Earlier DDMA phase estimates informed subset selection but
   were neither reverified for this configuration nor applied as fixed TX
   corrections. Twenty received frames were collected per angle. Firmware
   peak SNR was averaged in linear units. Reported boresight gains over TX1
   were 4.50, 7.15 and 7.86 dB for two, four and eight TX respectively.
   The report instead selected `4.4974 log2(N)` as its prospective gain law,
   yielding 13.4922 dB at eight TX.
5. **Raw TX checks, p. 5.** Ten ADC frames per condition were checked at
   boresight using Blackman FFTs and mean RX power. Noise came from the
   farthest 20% of range excluding the specified near-zero-Doppler region.
   At 20 dB backoff the pair gave 5.64 dB more signal, 0.14 dB more noise and
   thus 5.50 dB more raw SNR. Firmware angle-sweep SNR gain was only 4.50 dB.
   At 10 dB backoff the corresponding raw gains were 5.79, 1.16 and 4.63 dB.
   These were sequential checks; they do not resolve the raw/firmware
   discrepancy. ADC clipping was not observed.
6. **RX reprocessing of the walk, p. 6.** The same 137 saved target cells
   were evaluated with and without a calibrated complex RX sum. The sum's
   measured noise included cross-channel covariance, which is the appropriate
   comparison. The inbound 15–51 m median improvement was 6.28 dB; both legs
   gave 6.29 dB. The selected credit was 6.3 dB. On the original 24 fit
   samples, however, mean gain was 4.82 dB. Of 39 inbound interval samples,
   35 improved and one lost 14.48 dB. A 3-by-3 patch check gave a similar
   6.20 dB median. This is a paired processing comparison on tracked returns,
   not a detection-rate experiment.

## Arithmetic and the meaning of the headline

For a 0 dBsm target the report uses `SNR_dB = C - 40 log10(R/m)`.
At 1000 m the range term is 120 dB. A chosen 15 dB criterion therefore needs
`C = 135 dB`.

| Scenario | TX credit | RX credit | C | SNR at 1 km | Range at 15 dB |
|---|---:|---:|---:|---:|---:|
| Selected report scenario | 13.49 dB | 6.30 dB | 125.54 dB | 5.54 dB | 580 m |
| Measured lab eight-TX credit | 7.86 dB | 6.30 dB | 119.91 dB | -0.09 dB | 419 m |
| Selected TX, original-fit-sample RX mean | 13.49 dB | 4.82 dB | 124.06 dB | 4.06 dB | 533 m |
| Ideal equal-channel coherent TX and RX | 18.06 dB | 9.03 dB | 132.84 dB | 12.84 dB | 883 m |

Every row is an extrapolation. Even the second row combines a lab TX gain with
the single-TX walk and its RX reprocessing; no combined eight-TX/eight-RX walk
was reported. The final row is a theoretical comparison using the same
uncertain walk constant, not a prediction of achievable calibrated hardware.
Using the rounded 7.86 dB gives 15.09 dB missing; the PDF's 15.10 dB is
consistent with rounding of its underlying measurements.

The selected 9.46 dB gap and 580 m crossing are arithmetically correct.
They do not establish either a 1 km detection or a 9.46 dB hardware loss.

## What needs care

**TX extrapolation is a scenario choice.** With equal per-channel power and
signals aligned at the target, the ideal gain is `20 log10(N)`: 6.02 dB for
two TX, 12.04 dB for four and 18.06 dB for eight. The pair's raw signal gain
of 5.64 dB is encouraging and close to ideal. There is no established physical
reason that its firmware SNR improvement must recur at every doubling. In
particular, the actual four- and eight-TX measurements do not follow that law.
Array geometry, target direction, individual amplitudes, actual RF phases,
noise and firmware processing need separate treatment.

The quoted TX1/6/7/8 phase cluster alone cannot explain the four-TX result.
If those phases applied at the measurement target and amplitudes were equal,
`|sum(exp(j*phase))|^2` would give 11.94 dB, only 0.10 dB below ideal,
versus 7.15 dB firmware SNR gain. This is conditional because the phase
calibration was taken earlier under other conditions. The badly phased
TX2/3 could contribute to the all-eight result, but cannot explain the
four-TX subset that excludes them. Identical phase-code increments do not
establish aligned RF phases.

**The walk fit and the RX credit summarize different samples differently.**
Maxima per range bin intentionally select an upper envelope. Ground multipath
can enhance selected maxima as well as produce fades, and reflector attitude,
pedestrian scattering, elevation and range/Doppler bin offsets can vary.
The fixed R^-4 exponent was imposed over 15–51 m; the fit does not test that
law over hundreds of metres. The 1.885 dB residual is not uncertainty on the
1 km prediction or on absolute RCS. For background, see MathWorks'
[two-ray propagation model](https://www.mathworks.com/help/radar/ref/tworaychannel-system-object.html).

Adding a median RX gain to this envelope does not produce a fitted coherent
envelope or an average coherent curve. For an equally weighted least-squares
intercept in dB on the same 24 samples, the appropriate additive change is
their mean dB gain: 4.82 dB. Refitting coherent data while reselecting maxima
would be a different operation. The 6.3 dB median remains a useful descriptive
RX result, but not a universal loss correction or protection against the
observed coherent null.

**The reflector comparison is relative.** The 1.27 dB offset is not zero,
and which object was the 10 dBsm reference needs to be explicit. If the left
object were exactly 10 dBsm and all other factors matched, the original
would be 8.73 dBsm. That conditional deduction is not a calibration because
stand scattering, elevation and other systematic terms are unresolved.
The 0.32 dB curve residual measures fit consistency, not absolute accuracy.
Moving the assigned RCS from 14 to 10 dBsm increases the inferred unit-target
performance by 4 dB, or about 26% in predicted range, without changing any
observed signal. Reflector dimensions, orientation, frequency and mounting
are needed, including a check that the lab distances are appropriate for
far-field comparison. The conventional boundary is `2 D^2 / wavelength`;
see [MathWorks field analysis](https://www.mathworks.com/help/antenna/ug/field-analysis.html).

**15 dB is a requirement choice, not a Pd result.** Our June and Psi scenarios
use a 1 m² Swerling-1 target and Pfa=1e-6. For one coherent detection cell,
this repository gives Pd=0.655 at 15 dB and requires 21.14 dB for Pd=0.9.
A nonfluctuating target instead gives Pd=0.997 at 15 dB. These calculations
use known-noise square-law detection without additional detector loss.
Neither should be applied directly to the selected reflector envelope.
Noncoherent RX power averaging also changes detection statistics; it is not
an extra 9.03 dB mean signal/noise-ratio gain. See
[MathWorks on integration and fluctuation](https://www.mathworks.com/help/radar/ug/introduction-to-integration-and-fluctuation-losses-in-radar.html).

**The measured waveform is not a 1 km operating mode.** Assuming the quoted
100.781 MHz is swept during the 10.24 microsecond sampled payload, the sample
rate is 50 MHz and slope is 9.842 MHz/microsecond. At 1 km the beat frequency
would be 65.66 MHz. Under this repo's fs/2 beat-frequency limit, unambiguous
range is about 381 m. Even a full 50 MHz usable beat interval would not
reach 1 km with that slope. A suitable longer-range waveform needs a lower
slope, appropriate IF passband and valid echo/ADC timing. The 1 km round-trip
delay is 6.67 microseconds, so prepayload/ADC start timing deserves checking
too. A lower slope can preserve ideal thermal SNR at unchanged active
integration time, but transfer of real noise and calibration behavior must
be verified. See [FMCW range-to-beat relation](https://www.mathworks.com/help/phased/ref/range2beat.html).

## Comparison with the existing model

June [`config_3()`](../2026-06-22_config-comparison/config_comparison.py)
uses 14.5 dBm per TX, NF=10.2 dB, flat 17 dBi TX and RX antenna elements,
eight ideal coherent TX, eight coherent RX, 1024 samples by 512 chirps at
50 MHz, and default Hann/straddle/CFAR losses. Its 1 m² boresight SNR at
1 km is approximately 12.7 dB.

The actual [`sencity_farad_iv()`](../../radarperf/antenna.py) preset is not used
by that June configuration. Its digitized boresight TX/RX values are
15.045/14.984 dBi: about 3.97 dB less two-way antenna gain than the flat
17+17 dBi assumption. The manufacturer's
[2026 catalogue](https://www.hubersuhner.com/Asset/eyJpZGVudGlmaWVyIjoxMzE3OTAsInR5cGUiOiJhc3NldCJ9/855bJVYf6-WluRKp/Automotive_Data_transmission.pdf)
also gives 15 dBi per-channel boresight directivity. These pattern values
should not be confused with a measured installed realized-gain calibration.

The walk's `512*1024/50e6` and June's `1024*512/50e6` both give 10.48576 ms
active integration time. The walk CPI including dead time is 16.34304 ms;
the configured frame repetition time is not coherent integration time.

A first comparison isolates TX1 and noncoherent RX power averaging, keeps
77 GHz, 14.5 dBm, NF=10.2 dB and the repo's default 50 MHz complex-sample
noise bandwidth, substitutes Blackman loss of 2.37 dB on each FFT axis,
and removes the CFAR allowance for a raw spectral-SNR comparison:

| Single-TX comparison | Predicted C | Report C minus prediction |
|---|---:|---:|
| Flat 17 dBi each side, centered FFT bins | 106.57 dB | -0.82 dB |
| FARAD-IV boresight patterns, centered FFT bins | 102.60 dB | +3.15 dB |
| FARAD-IV with default 0.6+0.6 dB bin-straddle allowances | 101.40 dB | +4.35 dB |

These are diagnostic calculations, not validated predictions of the capture.
Exact RF frequency, active TX power, RX mode/noise bandwidth, real-versus-complex
ADC/SNR convention, antenna direction and per-channel gains remain to be
matched. In particular, the short-range walk probes beat frequencies around
1–3.35 MHz over the fitted interval, while the preset's 10.2 dB noise figure
is quoted at 10 MHz. A remote noise-estimation region may not represent
noise at the target's IF frequency.

The useful conclusion is that the report does not demonstrate a large
single-channel sensitivity deficit relative to the existing model.
The apparent positive residual using FARAD-IV could include upper-envelope
selection, RCS uncertainty, propagation enhancement or normalization
differences. It must not become a negative implementation loss or revised NF.
A target measurement constrains a product of TX power, antenna gains,
processing efficiency and inverse noise; it cannot identify those separately.

## Clarifications to request

1. Supply the referenced ADC recordings, config.bin files, both calibration
   TOMLs, analysis scripts and summary JSON/text files, including capture
   timestamps/frame counters. Explain selection of 137 track frames from 200;
   the remaining 63 are not automatically missed detections.
2. Define the raw and firmware SNR equations: target peak versus patch power,
   signal-only versus signal-plus-noise, noise cells, mean versus median,
   per-RX scaling, FFT normalization, real/complex ADC convention and actual
   sample rate/IF filtering. Recompute both metrics from the same frames.
3. Identify each reflector and the evidence for 10 dBsm at the operating
   frequency. Give dimensions, mounting, radar/reflector heights, tilt and
   the walk path; explain whether the reflector remained pointed at the radar
   on both legs. A pedestrian-only/background reference would help separate
   reflector and carrier scattering within the broad range/Doppler cell.
4. Explain calibration geometry and weights: did TX phase estimates remove
   geometric phase, are TX amplitudes known, were fixed RF corrections
   actually programmable/applied, and do RX weights include steering toward
   the calibration target? Recheck TX phases and raw gain for all four subsets
   at the same target, waveform and backoff, then at walking settings.
5. Provide per-frame walk SNR, RX gain, range, Doppler and preferably angle
   and noise estimates for both legs. Fit coherent data directly on documented
   samples, inspect fades and show ordinary sample statistics alongside the
   selected maximum envelope. Investigate the -14.48 dB RX event.
6. State the intended long-range waveform and performance criterion: 15 dB
   under which detector/Pfa/target fluctuation assumptions, single-frame Pd
   or multi-frame acquisition, with what frame cadence and margins?

## How to use this work

The review and supplied PDF now live in the separate dated **CARKIT validation
study**, following the 2026-09-11 scope decision. Its subject is a measured
hardware/configuration/scene combination; Psi is a changing product design.
Historical model assumptions remain unchanged. See [`NOTES.md`](NOTES.md)
for the active plan; reproducing the report's TX extrapolation is secondary.

The first validation milestone should reproduce the TX1 walk with matching
waveform, antenna, processing and SNR definition. Then validate calibrated TX
and RX combining in matched conditions. Only after separating those terms
should a bounded implementation correction be carried into Psi. Retain
scene-dependent fades and target uncertainty separately from hardware loss.

Reviewed all six rendered PDF pages and independently recalculated the budget,
waveform limits, phase-cluster benchmark and repository comparisons. No model
parameters were changed and no raw-measurement replication is claimed.
