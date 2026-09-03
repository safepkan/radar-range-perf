# Lannik Psi MIMO ambiguity-resolution study

This note records the exploratory MIMO work for Lannik Psi. It is intentionally
separate from the [main system-design notes](NOTES.md) and the main coherent-TX
study. Refer to those notes for the product scenario, antenna baseline, TX feed
realization, general coverage results and requirements context.

The results here are early feasibility results, not a selected architecture.
They nevertheless indicate that interlaced MIMO is a promising way to retain a
larger RX aperture without accepting unresolved channel-array ambiguities.

Last substantial update: 2026-09-03.

## Motivation and current conclusion

The eight RX channel phase centers form a sparse URA. Its steering vector is
periodic in direction cosines, so a coherent-TX measurement cannot distinguish
directions separated by integer array-factor periods. Shrinking each RX
subarray enlarges the fundamental region, but reducing a square subarray from
2.42λ to approximately 1.71λ costs another 3 dB of boresight RX gain.

The proposed alternative is to retain the coherent mode for sensitivity and
occasionally transmit distinguishable MIMO waveforms. Their complex TX
responses provide information that is absent from the periodic RX steering
vector. A tracker can retain several ambiguity-cell hypotheses, accumulate
MIMO evidence and apply the resolved cell to intervening coherent measurements.

**Preliminary conclusion:** Ideal four-quadrant MIMO appears capable of
resolving the relevant aliases for the 2.42λ square RX candidate. More
surprisingly, the nominal results also make the original 2.42λ × 4.83λ RX
rectangle viable: its troublesome vertical boundary has particularly strong
TX-quadrant discrimination and retains 3 dB more RX gain. This result needs a
pattern/calibration tolerance study before it can drive the physical design.

## Mode and virtual-array model

### Four-quadrant MIMO

The current ideal experiment geometrically divides the prescribed 16 × 16 TX
aperture into four 8 × 8 quadrants. The intended product implementation would
feed each quadrant from two equal-power MMIC ports. Those two ports remain
coherent within a quadrant, while the four quadrants transmit mutually
orthogonal signals. Four matched TX outputs across eight RX channels provide 32
complex virtual measurements.

The supplied aperture happens to divide into four groups with equal integrated
excitation power, equal boresight magnitude and equal boresight phase. The
experiment assumes that the desired complex quadrant patterns can be realized
exactly. The eventual physical two-port partition inside each quadrant is not
yet known.

### Pattern-aware steering manifold

For TX group `q`, RX channel `r` and direction `(u,v)`, the ideal point-target
response is

```text
a[q,r](u,v) = sqrt(P[q]) * E_TX[q](u,v) * E_RX[r](u,v).
```

For a uniform array of identical TX elements, each `E_TX[q]` is a common
element pattern times a phase-center term. After removing unknown target
amplitude, only the virtual geometry remains. That simplification does not
apply here: `E_TX[q]` is the full complex voltage pattern of one quadrant and
contains direction-dependent amplitude and phase. Angle processing therefore
needs a calibrated pattern dictionary rather than only a uniform-array FFT.

The current RX subarrays are identical in the model, so their common complex
subarray pattern changes SNR but cancels from normalized hypothesis
correlation. At an exact RX-period translation, the eight phase-center terms
repeat as well. Discrimination between such aliases therefore comes entirely
from the four-component TX-quadrant response vector.

### Sensitivity accounting

For four equal-power quadrants, orthogonal MIMO is nominally 6.02 dB below the
fully coherent four-quadrant sum at boresight. With free-space `R^-4` scaling,
that is a range factor of approximately 0.707. Away from boresight the loss is
not constant:

```text
G_coherent(u,v) proportional to abs(sum_q E_TX[q](u,v))**2
G_MIMO(u,v)     proportional to sum_q abs(E_TX[q](u,v))**2.
```

The MIMO envelope is wider and fills some nulls of the coherent sum. It can
therefore outperform the coherent mode locally near a principal-region edge
despite its lower boresight gain.

## Alias-discrimination metric

The first experiment compares two virtual steering vectors using squared
normalized correlation:

```text
rho = abs(a1^H * a2)**2 / (norm(a1)**2 * norm(a2)**2).
```

Zero decibels means the directions differ only by an unknown complex target
amplitude and cannot be distinguished. More-negative values mean better ideal
separation. Correlation is not itself a probability: resolution performance
also depends on MIMO SNR, competing hypotheses and accumulated updates.

Representative exact-alias correlations are:

| RX geometry and alias pair | Squared correlation |
|---|---:|
| 2.42λ square: opposite horizontal edges | -3.14 dB |
| 2.42λ square: opposite vertical edges | -3.14 dB |
| 2.42λ square: opposite corners | -6.27 dB |
| 2.42λ square: boresight to one-period replica | -21.87 dB |
| 2.42λ × 4.83λ rectangle: opposite horizontal edges | -3.14 dB |
| 2.42λ × 4.83λ rectangle: opposite vertical edges | -29.32 dB |
| 2.42λ × 4.83λ rectangle: boresight to vertical replica | -8.20 dB |

The strong variation demonstrates why neither one phase-center spacing nor one
boresight-replica number characterizes the problem. The full complex patterns
must be evaluated over all relevant hypothesis pairs.

## Single-CPI detection results

The first range calculation deliberately treated MIMO as a second independent
detector. It uses the main study's 1 m² Swerling-1 target, `Pfa=1e-6`, the same
full-length 1024-sample × 512-chirp CPI, unchanged total eight-port TX power,
ideal coherent RX and resolved-TX processing, and no MIMO implementation loss.

For the current square RX baseline at boresight:

| Mode | Pd=50% | Pd=90% |
|---|---:|---:|
| Coherent TX | 937 m | 579 m |
| Four-quadrant MIMO | 663 m | 409 m |

At the square RX horizontal or vertical principal edge, approximately ±11.9°:

| Mode | Pd=50% | Pd=90% |
|---|---:|---:|
| Coherent TX | 397 m | 245 m |
| Four-quadrant MIMO | 450 m | 278 m |

The MIMO range is higher locally because its quadrant-power sum is broader than
the coherent TX pattern.

## Repeated binary ambiguity resolution

The preliminary resolution model compares the true direction with the RX alias
folded into the principal cell. The two hypotheses have unrelated unknown
complex target amplitudes. Noise and Swerling-1 amplitude are independent
between MIMO updates; projection-energy evidence is accumulated without
coherent phase integration between CPIs.

For the current 2.42λ square RX boundary, where `rho` is approximately -3.14
dB, the modeled ranges for a 99% correct binary decision are:

| MIMO updates | 99% resolution range |
|---:|---:|
| 1 | 253 m |
| 2 | 407 m |
| 4 | 541 m |

For the supplied 2.42λ × 4.83λ rectangle at its vertical boundary, approximately
±5.9°, the nominal signatures are nearly orthogonal:

| Metric | Range |
|---|---:|
| Coherent TX Pd=50% | 760 m |
| MIMO Pd=50% | 634 m |
| MIMO Pd=90% | 392 m |
| 99% resolution, 1 update | 421 m |
| 99% resolution, 2 updates | 673 m |
| 99% resolution, 4 updates | 884 m |

At that edge and 500 m, the separate ideal metrics are approximately 76% MIMO
Pd and 98.0%, 99.9% and effectively 100% correct-cell probability after one,
two and four updates. At 600 m they are approximately 57% Pd and 96.1%, 99.6%
and 99.99% correct-cell probability.

These are not joint detection-and-resolution probabilities. In particular, a
tracker can accumulate useful gated MIMO evidence below the global standalone
detection threshold.

## RX-height trade

Keeping the width at 2.42λ and varying height between the square and supplied
design gives the following nominal vertical-edge results:

| RX height | Edge | Correlation | Coherent Pd=50% | MIMO Pd=50% | 99% resolution: 1 / 2 / 4 updates |
|---:|---:|---:|---:|---:|---:|
| 2.42λ | 11.9° | -3.1 dB | 397 m | 450 m | 253 / 407 / 541 m |
| 3.00λ | 9.6° | -5.7 dB | 516 m | 521 m | 320 / 513 / 678 m |
| 3.42λ | 8.4° | -8.8 dB | 595 m | 561 m | 359 / 576 / 759 m |
| 4.00λ | 7.2° | -15.1 dB | 660 m | 583 m | 384 / 614 / 807 m |
| 4.83λ | 5.9° | -29.3 dB | 760 m | 634 m | 421 / 673 / 884 m |

Correlation is not monotonic with height and has a deep minimum near the
supplied design. This favorable result follows from the exact prescribed
quadrant patterns, not a general geometrical guarantee. Intermediate heights
remain useful if coverage balance, packaging or robustness favors them, but an
intermediate height is not required merely to make ideal MIMO resolution viable.

## From independent detector to track-directed measurement

The independent-detector calculation was a useful conservative starting point:
it produced promising results using the existing waveform and `Pfa=1e-6`.
Operationally, however, the MIMO mode is more naturally an auxiliary
track-directed ambiguity measurement.

The coherent mode can first provide target-existence evidence, range, Doppler
and a folded angle. The tracker then maintains discrete ambiguity indices
`(k_u,k_v)` and a probability for each plausible cell. MIMO updates change
those probabilities; coherent updates retain sensitivity between them. Angle
should be published as unambiguous only when the correct-cell posterior meets a
defined confidence requirement.

Two kinds of evidence should be combined:

1. **Gain plausibility.** TX and RX patterns predict different received powers
   under different aliases. An RCS estimate or prior turns large gain
   differences into hypothesis evidence.
2. **Normalized MIMO signature.** Complex quadrant-response differences remain
   after unknown target amplitude is removed and are essential near equal-gain
   cell boundaries.

For densely packed uniform RX subarrays, a boresight replica one full period
away coincides with the ideal subarray's first null. Such aliases should often
be rejectable from gain plausibility alone, subject to a realistic null floor.
Near opposite principal-cell edges, RX gain is equal and the coherent TX gains
can also be similar; this is where MIMO signature information matters most.

If target existence and range/Doppler are already gated, MIMO need not cross a
global detection threshold. The processor can extract complex measurements
from the small track gate and update hypothesis likelihoods directly. The
relevant false-alarm quantity becomes false association or wrong-cell
publication probability per track, rather than full-search per-cell Pfa.

## Waveform and scheduling degrees of freedom

The current figures use one unchanged full-length MIMO CPI every fourth 20 Hz
frame: a 5 Hz MIMO update and 15 coherent updates per second. The corresponding
worst-case times from appearance to one, two and four scheduled MIMO updates
are approximately 0.2, 0.4 and 0.8 seconds.

This is illustrative, not a recommendation. Candidate strategies include:

- Fixed sparse interlacing.
- A triggered burst after an ambiguous coherent detection.
- Adaptive MIMO rate based on ambiguity entropy or publication urgency.
- A clean mode switch during ambiguity resolution.
- Longer MIMO CPIs for track-directed targets with known range/Doppler.
- Separate policies for track initiation and maintenance.

Doubling coherent MIMO illumination time adds 3 dB if the target remains
coherent, increasing free-space range by approximately 19%. For example, the
square-edge MIMO Pd=50% range would scale from approximately 450 to 535 m, and
the supplied-rectangle edge from approximately 634 to 754 m.

Track gating can also permit a much higher threshold Pfa if a thresholded
detector is retained. For the present Swerling-1 model, changing `Pfa` from
`1e-6` to `1e-3` reduces the required SNR by roughly 3 dB. This improves a
standalone Pd boundary but does not create more ambiguity information at a
given physical SNR; direct likelihood processing is the cleaner formulation.

The final comparison should account for displaced coherent updates, target
decorrelation, range/Doppler migration, acceleration, phase noise, waveform
orthogonality, velocity ambiguity, thermal duty and processing capacity.

## Future eight-TX MIMO

The physical subdivision of each quadrant into two equal-power TX subapertures
is not yet defined. Once the eight complex embedded patterns are available, the
same experiment can use an eight-component TX response vector.

Eight independent TX waveforms are nominally 9.03 dB below fully coherent
eight-port transmission at boresight, another 3.01 dB below four-quadrant MIMO.
They may buy lower alias correlations, more multi-hypothesis information and
better calibration robustness. If the two subapertures inside a quadrant have
nearly proportional patterns, however, they add little angular information.

At the square boundary, improving correlation from `rho=0.485` to nearly zero
would improve the approximate discrimination factor `1-rho` by about 2.9 dB,
nearly balancing the additional 3 dB sensitivity loss. At the already
near-orthogonal rectangular vertical edge there is little nominal binary
separation left to gain; eight-TX value would instead be robustness and
discrimination among other aliases. A longer eight-TX waveform could recover
the extra sensitivity at the cost of time.

Coherent TX, four-quadrant MIMO and eight-TX MIMO may all be useful selectable
modes rather than mutually exclusive antenna architectures.

## Calibration and manufacturing variation

The current model assumes exact pattern knowledge. Full far-field measurement
of every production unit is likely too expensive, so sensitivity and the
dimensionality of unit variation must be established.

Separate error classes should include:

- Constant complex gain and phase per TX/RX channel.
- Residual error after a simple boresight or internal calibration.
- Phase-center and geometry displacement.
- Smooth angle-dependent embedded-pattern distortion.
- Null and sidelobe filling.
- Common radome, housing, installation and temperature effects.
- Correlated errors produced by shared antenna construction.

The correct robustness experiment generates measurements with perturbed true
patterns while processing them with the nominal dictionary. Results should be
reported at manufacturing and temperature percentiles, not only for the mean
unit. The deep nominal -29 dB rectangular-edge correlation is particularly
important to stress: it may remain entirely adequate if degraded to -15 or -10
dB, but should not be treated as a guaranteed null.

A plausible production approach is extensive pattern measurement on a smaller
population, identification of a low-dimensional variation model, and sparse
per-unit calibration of its dominant parameters.

## Metrics for the next phase

Single-scan reasoning remains useful for pruning the design space. The eventual
trajectory/tracker study should distinguish:

- Probability that a track is initiated.
- Probability that it is maintained.
- Probability that the ambiguity cell is resolved.
- Probability and latency of publishing a correct unambiguous angle.
- Probability of publishing the wrong cell.
- Unresolved-hypothesis count or entropy over time.
- MIMO time/resource use and coherent-update displacement.

Missed detections are also evidence when their probabilities differ by
hypothesis. A high-gain hypothesis repeatedly producing no measurement should
lose probability. Conversely, a strong track prior can greatly reduce the
number of credible aliases.

The next calculations should proceed in increasing complexity:

1. Enumerate every physically visible alias and add gain/RCS plausibility.
2. Combine target-existence, detection and cell-association likelihoods.
3. Apply structured calibration and pattern perturbations.
4. Compare fixed interlacing with triggered/adaptive MIMO scheduling.
5. Simulate radial approaches from horizontal, vertical and diagonal cuts.
6. Add a small multiple-hypothesis tracker and time-to-publish metric.
7. Repeat with the final eight TX subaperture patterns.

## Reproduction and figures

Run from the repository root:

```text
venv/bin/python studies/2026-09-02_lannik-psi/quadrant_mimo.py
```

MIMO figures are written under [`generated/mimo/`](generated/mimo/):

- `quadrant_mimo_alias_correlation.png` — folded-alias correlation for the
  square and supplied-height RX geometries.
- `mimo_detection_range_cuts.png` — coherent and four-quadrant MIMO Pd range.
- `mimo_ambiguity_resolution_range_cuts.png` — square-RX detection and 99%
  binary resolution after one, two and four MIMO updates.
- `mimo_rx_height_trade.png` — vertical-edge performance from square to
  supplied RX height.

## Present limitations

- Ideal orthogonal waveforms with no implementation loss.
- Exact complex TX patterns and calibration.
- Binary true-direction versus principal-cell-folded hypothesis.
- No simultaneous targets, multipath or target angular extent.
- No complete enumeration of aliases within the visible disk.
- No gain/RCS likelihood or realistic antenna null floor.
- Independent Swerling-1 amplitude and noise between accumulated updates.
- No joint conditioning on detection or target-existence probability.
- No tracker, publication logic or adaptive scheduler.
- No multiple-hypothesis Pfa/resource cost.
- The four-quadrant split is conceptual until the physical eight-port design is
  available.
