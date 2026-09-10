# Lannik Psi MIMO ambiguity-resolution study

This note records the exploratory MIMO work for Lannik Psi. It is intentionally
separate from the [main system-design notes](NOTES.md) and the main coherent-TX
study. Refer to those notes for the product scenario, antenna baseline, TX feed
realization, general coverage results and requirements context.

MIMO-assisted ambiguity resolution is the selected broad system direction.
The results here remain early feasibility results: the detailed implementation
and achievable performance have not yet been validated. They indicate a
promising way to retain a larger RX aperture without accepting unresolved
channel-array ambiguities.

Last substantial update: 2026-09-10.

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
The supplied rectangle is therefore again the main coherent-study baseline as
of 2026-09-04; the square remains an explicit comparison candidate.

**Project status, 2026-09-04:** MIMO-assisted ambiguity resolution is now the
intended broad system direction rather than merely an optional alternative.
This is a decision to develop the concept, not a claim that the remaining
waveform, calibration, processing, tracking and confidence problems are
solved. Two antenna prototypes with different RX subarray dimensions are
planned; their exact geometries remain undecided. Once selected, both should be
run through this study and represented by clearly named Lannik Psi prototype
antenna presets.

Two provisional layouts were received on 2026-09-08. The square-subarray
candidate is now oriented as a 2 × 4 channel array and appears likely to be
fixed. The active second-prototype comparison is therefore the original 4 × 2
rectangular topology with versus without alternating two-channel columns
staggered vertically by one eighth of the subarray height. The stagger has
negligible additional benefit for the already nearly orthogonal opposite
vertical-edge MIMO pair, but can make intervening coherent-TX updates useful
for vertical disambiguation. Its horizontal aliases remain exact. The imminent
prototype choice therefore concerns combined evidence, implementation effort
and schedule risk, not only the MIMO correlation plot. See the dedicated
[`RX_LAYOUT.md`](RX_LAYOUT.md) decision note and
[`rx_layout_experiment.py`](rx_layout_experiment.py).

**Decision, 2026-09-10 meeting:** The rectangular prototype uses a two-pitch
(height/4) column stagger, which lets ordinary coherent frames resolve the
in-beam vertical alias family without MIMO in the tested events; the second
prototype is the rotated square-subarray URA, whose aliases all sit at
±11.9°. MIMO is
retained for the horizontal alias family, which remains exact in every
stagger variant, and as the fallback for the vertical family; it is used
on demand. The horizontal-edge discrimination of about -3 dB, which comes
entirely from the prescribed TX defocus, is therefore the binding TX
requirement; see [`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md).

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

### Origin of the quadrant discrimination, 2026-09-10

The TX radiator pitch equals the RX pitch, so each 8 × 8 quadrant is exactly
one RX subarray height wide and the four quadrant phase centers share the RX
alias lattice. Uniform, cophasal quadrants therefore give 0.0 dB at the
opposite vertical edges and -0.6 dB at the opposite horizontal edges: the
quadrant *geometry* contributes nothing. The supplied excitation carries a
rotationally symmetric quadratic phase, about 180° at the edge centres and
360° at the corners. It is a beam-broadening defocus (6.9° to 12.6° 3 dB
beamwidth, 5.3 dB boresight cost) and it squints each quadrant beam by 6.0°
in u and v toward the opposite corner. That squint, with the resulting
amplitude and phase differences between quadrants, is the entire source of
the table above; the supplied amplitude taper without its phase gives only
-4.7 dB at the vertical edges and -0.04 dB at the horizontal edges.

Consequences: the vertical discrimination is robust to plausible errors in
the realized taper (vertical-edge margin at least 17 dB for 0.6 to 1.4 times
the prescribed phase, at least 12.9 dB for a 30° uncalibrated upper/lower
quadrant phase error) but is tied to the prescribed TX excitation. The
horizontal-edge margin scales with the amount of defocus, from 1.8 dB at 0.6
times the prescribed phase to 4.3 dB at 1.4 times, so an under-realized
defocus weakens the MIMO-limited horizontal case. A focused long-range TX
mode, TX subarray phase steering or any re-shaped taper changes the MIMO
alias discrimination and must be re-evaluated; the supplier must realize the
phase distribution, not only the amplitude taper. (These sensitivity figures
were corrected on 2026-09-10 after a review found that the first sweep scaled
the wrapped rather than the unwrapped phase.)
See [`RX_LAYOUT.md`](RX_LAYOUT.md) and
[`rx_stagger_amount_experiment.py`](rx_stagger_amount_experiment.py).

Because the antenna supplier implements our concept, this dependence is
something to specify rather than hope for. The supplier-facing formulation,
with per-port pattern deliverables and acceptance thresholds on the
alias-pair correlations, is drafted in
[`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md).

## Single-CPI detection results

The first range calculation deliberately treated MIMO as a second independent
detector. It uses the main study's 1 m² Swerling-1 target, `Pfa=1e-6`, the same
full-length 1024-sample × 512-chirp CPI, unchanged total eight-port TX power,
ideal coherent RX and resolved-TX processing, and no MIMO implementation loss.

For the current supplied rectangular RX baseline at boresight:

| Mode | Pd=50% | Pd=90% |
|---|---:|---:|
| Coherent TX | 1115 m | 688 m |
| Four-quadrant MIMO | 788 m | 487 m |

For the 2.42λ square RX comparison at boresight:

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

**Review qualification, 2026-09-09:** The physical RCS fluctuation timescale is
unknown. The multi-update ranges below are conditional on the stated
independence assumption, not validated latency guarantees. A block-constant
RCS sensitivity check gave materially shorter unconditional resolution range;
conditioning on an existing track also needs separate treatment. See
[`RX_LAYOUT.md`](RX_LAYOUT.md) for the review result and the proposed
fixed-SNR, equal-time comparison that avoids relying on a guessed fluctuation
timescale for the geometry decision.

For the 2.42λ square RX boundary, where `rho` is approximately -3.14
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

### Likely path: tracker-requested MIMO bursts

**Working direction, 2026-09-09:** Use on-demand MIMO in sparse scenarios with
few simultaneous tracks. Once a track's uncertainty and association gate are
narrow enough not to overlap their alias-shifted copies, its prediction can
unwrap subsequent coherent measurements. Request additional MIMO evidence for
new unresolved tracks, reacquisition or deteriorating ambiguity confidence.
The request rate is governed by such events, not just the number of tracks.

**User-supplied implementation expectation:** Radar control, SP and tracking
will share the Aurix TC457. Treat tracker requests and the required sequencer
flexibility as feasible design assumptions. Sparse-target association and
filtering are expected to be relatively cheap; there are no platform timing or
compute measurements yet. Much SP must await the received CPI, and request,
processing, sequencer-boundary, switching and illumination delays remain real.
Do not equate active illumination time with end-to-end resolution latency.

The on-demand burst can use a different waveform, longer coherent illumination
or repeated CPIs, and a small range/Doppler gate. It need not pass an independent
full-search detection threshold: soft complex measurements can update the
remaining hypotheses directly. A relaxed gated Pfa can help thresholded
extraction, but does not create extra signature information at fixed SNR.

Compare time/energy to a sufficiently reliable unambiguous result, rather than
assuming the fixed-CPI coherent-to-MIMO SNR difference is a permanent range
penalty. Longer illumination is useful only within target-coherence and
range/Doppler-motion constraints; confirmed-track revisit requirements still
apply while the burst runs. These details remain architecture work.

### Historical reference and remaining alternatives

The new [rx_resolution_experiment.py](rx_resolution_experiment.py) evaluates
one coherent observation followed by variable on-demand MIMO illumination,
with local angular searches within multiple candidate lobes and a phase-error
stress case. The fixed-RCS model and preliminary geometry comparison are
documented in [RX_LAYOUT.md](RX_LAYOUT.md); its plots are under
`generated/experimental/on_demand/`. These results quantify illumination
energy for selected events, not scheduling latency or full coverage.

The existing `quadrant_mimo.py` figures use one unchanged full-length MIMO CPI every fourth 20 Hz
frame: a 5 Hz MIMO update and 15 coherent updates per second. The corresponding
worst-case times from appearance to one, two and four scheduled MIMO updates
are approximately 0.2, 0.4 and 0.8 seconds.

This remains an illustrative reference/fallback, not the likely product
schedule. Candidate strategies include:

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

## Fallbacks if MIMO underperforms, 2026-09-10

**Design ideas**, recorded because the remaining MIMO risk sits on the TX
side (pattern realization, intra- and inter-quadrant calibration, waveform
orthogonality and its Doppler cost) and because a single-target application
tolerates slower resolution:

1. **TX sequential lobing with the coherent waveform.** The per-port MMIC
   phase settings can steer or re-shape the coherent sum beam between CPIs
   (for example a small upward or sideways squint). The received amplitude
   ratio between two such CPIs differs between the true direction and its
   alias because the TX patterns are not periodic in the RX lattice. This
   uses the same quadrant-pattern squint as MIMO but at full coherent power
   and with no orthogonal waveform or MIMO processing. Its weakness is that
   the two measurements are in different CPIs, so target RCS fluctuation
   enters the ratio; MIMO measures all four quadrant responses in one CPI and
   cancels the unknown amplitude exactly. The TX pattern requirement in
   [`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md) is unchanged.
2. **Gain-trajectory evidence in the tracker.** As a target or the platform
   moves, the received amplitude follows the two-way gain pattern at the
   true direction; the alias hypothesis predicts a different profile. This is
   free information for targets crossing the beam and for any platform
   motion, and nothing for a radially approaching target at constant angle.
3. **Surface the ambiguity upward.** Publish the hypothesis set and its
   probabilities as a first-class output state rather than hiding it, so
   higher layers can wait, accept, or act. As a last resort in a
   single-target use case, an operator or platform controller can be asked
   to rotate the platform by a few degrees: the alias sits at a different
   place in the fixed TX and subarray patterns, so the amplitude change on
   rotation has opposite sign under the two hypotheses. It is the mechanical
   version of item 1 and inherits the same RCS-fluctuation caveat, but it
   needs no change to the radar at all.

Items 1 and 2 are cheap to model with the existing quadrant patterns and
should be quantified before they are relied on. None of them removes the
need for calibrated patterns; they remove the need for orthogonal waveforms.

## Design idea: two-way TX splits instead of quadrants, 2026-09-10

With the vertical alias family handled by the staggered RX, the MIMO burst
only has to separate the horizontal family. A **left/right half split** (two
orthogonal waveforms, four coherent ports each) gives exactly the same
horizontal discrimination as the quadrant split and is 3 dB more sensitive:

| Alias pair | Quadrant MIMO | Left/right halves | Up/down halves |
|---|---:|---:|---:|
| Horizontal edges (±0.207, 0), also at v = 0.05 and 0.1035 | -3.1 dB | -3.1 dB | 0.0 dB |
| Vertical edges (0, ±0.1035) | -29.3 dB | 0.0 dB | -29.3 dB |
| Diagonal corners (±0.207, ±0.1035) | -32.5 dB | -3.1 dB | -29.3 dB |
| Square-cell vertical edges (0, ±0.207) | -3.1 dB | 0.0 dB | -3.1 dB |

MIMO gain relative to the coherent sum: halves -3.0 dB at boresight and along
the vertical axis (quadrants -6.0 dB); at the horizontal edge +5.2 dB
(quadrants +2.2 dB). At a given elevation the two quadrants on one side
respond alike, so the quadrant split adds nothing to the horizontal pair; what
the halves lose is the vertical family, which the H/4 stagger covers in the
coherent frames and in the RX part of the MIMO measurement.

Consequences: burst energies for the horizontal events should roughly halve
(to be run, not assumed); two orthogonal waveforms are the simplest MIMO
scheme (a two-chirp phase alternation, or a two-channel Doppler division that
halves rather than quarters the unambiguous velocity); and the antenna is
unchanged, so left/right, up/down and quadrant splits are per-event waveform
and MMIC-phase choices on the same eight ports. The square prototype would use
up/down halves for its vertical pairs at the same -3.1 dB, and left/right
and up/down splits one CPI at a time when both families are ambiguous: two
half-split CPIs give each family a measurement at twice the SNR of the
quadrant CPI over twice the time, so the evidence per unit illumination is
the same, each measurement cancels the unknown amplitude within its own CPI,
and only the burst latency grows. The quadrant mode remains the shorter
"both at once" option at -6 dB. The TX requirement is unchanged:
the left/right discrimination is the same defocus-squint effect with the same
sensitivity to an under-realized defocus.

The nominal radiator-grid split is illustrated by
`left_right_half_tx_beams.png`. Coherently joining the two quadrants on each
side cancels their opposite vertical squints while retaining the horizontal
squint: the physical left half peaks at about -6.0° azimuth and the physical
right half at about +6.0°. Thus the two half-aperture beams point inward across
boresight rather than straight ahead. The plotted one-waveform curves include
each half's 1/2 share of the unchanged total TX power; their noncoherent power
sum is 3.0 dB below the full coherent aperture at boresight. This remains a
geometric illustration using the prescribed radiator excitations, not a model
of finalized four-port embedded patterns.

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

- `left_right_half_tx_beams.png` — individual left/right half-aperture beams,
  their horizontal cut and the two-waveform power sum.
- `quadrant_mimo_alias_correlation.png` — folded-alias correlation for the
  square and supplied-height RX geometries.
- `mimo_detection_range_cuts.png` — coherent and four-quadrant MIMO Pd range
  for the supplied rectangular RX baseline.
- `mimo_ambiguity_resolution_range_cuts.png` — supplied-rectangle detection
  and 99% binary resolution after one, two and four MIMO updates.
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
- The alias discrimination is a property of the prescribed TX defocus phase;
  it does not transfer to other TX excitations or modes without re-evaluation.
