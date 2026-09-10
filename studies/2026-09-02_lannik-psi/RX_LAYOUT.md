# Lannik Psi RX-layout decision notes

Working decision brief, 2026-09-09, extended 2026-09-10 before the meeting.
The internal meeting on 2026-09-10 is expected to choose the rectangular
prototype geometry; ordering may not allow further deferral. This is a recommendation under uncertainty, not a finalized
antenna specification or a demonstrated ambiguity-resolution capability.

See [NOTES.md](NOTES.md) for system context and [MIMO.md](MIMO.md) for the
track-directed MIMO architecture. The corresponding experimental script is
[rx_layout_experiment.py](rx_layout_experiment.py). Keep geometry-specific
reasoning and the eventual decision here rather than duplicating those notes.

## Decision and current direction

Two prototypes are planned. The rotated, square-subarray 2 × 4 layout is likely
fixed. The active choice is the rectangular prototype's RX phase-centre
layout: an unstaggered 4 × 2 URA, or the same subarrays with alternating
two-channel columns displaced vertically. Neither rectangular alternative is an
official prototype preset yet.

**Current direction, 2026-09-10: a two-pitch (height/4) alternating column
stagger, as option C (eight rows, 42.3 mm tall) or option D (seven rows,
37.6 mm tall, -0.6 dB) in [ANTENNA_REQUIREMENTS.md](ANTENNA_REQUIREMENTS.md).
The unstaggered URA is the fallback.** This supersedes the 2026-09-09
preference for the URA, which rested on the modest benefit of the one-pitch
(height/8) internal sketch; see the decision record. The choice is ours to
make from a product and project perspective; the supplier is asked only for
early feedback on obvious feasibility, PCB, feed, coupling or schedule issues.

### Why staggering is the main direction

1. **The vertical alias is the one that matters operationally.** The
   rectangle's vertical alias period puts opposite-edge pairs at ±5.9°,
   inside the TX 3 dB beam, so it affects targets at long range. The
   horizontal aliases sit at ±11.9°, outside the beam, and only matter within
   roughly 550 m for a 1 m² target.
2. **For a URA, coherent frames carry no information about that alias, and
   gain plausibility protects less of the beam than the exact-alias
   calculation suggests.** With a +10 dBsm RCS ceiling only a band of about
   ±2° around the horizontal plane is free of a near-exact competitor,
   because the skirt of the alias lobe becomes admissible before the exact
   alias does. Everything else relies on MIMO.
3. **The MIMO discrimination is a property of the TX defocus, not of the
   antenna geometry.** Untapered quadrants alias exactly with the RX lattice.
   The nominal -29 dB vertical-edge value comes from the quadrant squint that
   the prescribed quadratic phase produces. It is robust to plausible taper
   and static phase errors, but it depends on the supplier realizing that
   phase, on TX quadrant calibration and on waveform orthogonality, and it
   changes with any future TX mode.
4. **A two-pitch stagger gives coherent frames real vertical-alias
   information at no gain cost.** Alternating columns differ by 90° at the
   old alias, so each ordinary frame carries `1 - rho = 0.5` of the
   separation of an unambiguous measurement; the one-pitch sketch gives only
   0.146. In the fixed-RCS event model, height/4 reaches 1% wrong-lobe with
   coherent frames alone within one frame at 632 m and four frames at 893 m,
   also under a 10° random phase stress; with a +15° systematic column-group
   error it needs two frames at 632 m and a 1.0 CPI burst after four frames
   at 893 m. Height/8 needs a burst at 893 m in every case and is nearly
   disabled by the systematic error. These are promising event results, not
   resolution-time guarantees.
5. **It leaves no near-exact competitor anywhere in the beam.** The in-beam
   map caps the worst coherent-mode competitor at -2.2 dB across the TX 3 dB
   region for height/4, against 0 dB for the URA; the worst MIMO competitor,
   searched separately, is about -10 to -11 dB in that region for every
   layout.
6. **The evidence is independent of the TX realization.** The stagger's
   information is RX geometry only. It reduces reliance on MIMO for the
   long-range family and removes a single point of dependence on the
   supplier's TX pattern for that family.

### What it costs and what stays

- No change to subarray area, gain, beamwidth or the coherent sensitivity
  envelope. Option C adds 4.7 mm of RX height; option D keeps 37.6 mm at
  -0.6 dB.
- Steering vectors are non-separable. The cost per directly formed beam is
  unchanged at eight channels; the required beam-bank size, search and
  per-lobe likelihood updates have not been budgeted and are likely
  manageable rather than established. The design bookkeeping is real: lobes
  on a sheared lattice with near-aliases at -2 to -3 dB instead of exact
  aliases and nulls, 2-D validation, and per-lobe coherent likelihoods in
  the tracker. That is the same machinery the URA-plus-MIMO plan needs,
  applied to more updates.
- The stagger's evidence needs RX inter-channel phase calibration, as any
  angle estimate does, but with less nominal margin than MIMO has: at the
  vertical alias the true-versus-alias margin is 3.0 dB nominally, 1.9 dB
  with a systematic +15° error between the two column groups, 1.0 dB at
  +30°, and zero at +45° (errors of the opposite sign increase it). A
  ±15° calibration of relative RX channel phase is therefore a proposed
  target that is part of the design, not demonstrated production robustness;
  in the event simulation a +15° systematic error costs H/4 one extra frame
  at 632 m and a 1.0 CPI burst at 893 m. MIMO's equivalent sensitivity is the TX
  inter-quadrant phase, where 30° still leaves 13 dB because the nominal
  vertical margin is 29 dB; but MIMO also depends on pattern realization
  and waveform orthogonality, which the stagger does not.
- MIMO stays. The horizontal aliases remain exact in every stagger variant,
  and MIMO is the fallback for the vertical family. Its main job moves to
  the short-range horizontal family, which strengthens the on-demand
  scheduling choice: no illumination is spent on less sensitive MIMO frames
  when coherent frames resolve the vertical family. The horizontal-edge MIMO
  discrimination of about -3 dB, entirely from the TX defocus, is therefore
  the binding TX requirement.
- Not yet shown: slow RCS fluctuation across frames, multi-target
  association, a tracker decision rule with abstention, and supplier
  feedback on the layout. These gaps apply equally to the URA-plus-MIMO plan.

**What would change the direction:** supplier feedback that a two-pitch
offset has a real PCB, feed or schedule cost; a fluctuation or calibration
result that removes most of the multi-frame benefit; or a requirement that
makes the short-range horizontal family, rather than the long-range vertical
family, the driver.

### Updated operating assumption: on-demand MIMO

Assume a sparse scene with few tracks. For a confirmed track with sufficiently
narrow prediction/association gates, coherent measurements can be unwrapped
without routine MIMO updates. The likely path is a tracker-requested burst for
an unresolved new track or lost ambiguity confidence, not every-Nth-frame
interlacing. Shared Aurix TC457 control/SP/tracking and sequencer flexibility
are taken as feasible design assumptions; actual latency is not yet measured.
See [MIMO.md](MIMO.md) for the detailed scope of this assumption.

This changes the geometry trade: staggering might avoid or shorten an
occasional burst, rather than continuously saving scheduled MIMO resources.
The comparison must allow a targeted gate and additional MIMO illumination;
a fixed per-CPI SNR disadvantage is not a permanent system range penalty.
Periodic-interlace examples below remain illustrative, not the decision metric.

## What is established in the current model

*Written 2026-09-09 for the one-pitch (height/8) internal sketch. The
two-pitch variants are analysed in the 2026-09-10 section further down.*

Let `W = 9.405 mm`, `H = 18.811 mm` and `lambda = 3.893 mm` at 77 GHz.
The proposed stagger shifts alternating complete two-channel columns by
`+H/16` and `-H/16`: adjacent columns differ by `s = H/8 = 2.351 mm`.
This matches our interpretation of the internal sketch. The offset was not
chosen by analysis, and it has not necessarily been discussed with the
supplier.

| Property | Unstaggered rectangle | Proposed stagger |
|---|---|---|
| Subarray area and uniform pattern | Reference | Unchanged |
| Ideal matched RX peak gain | Reference | Unchanged |
| Pure horizontal alias period | `lambda/W = 0.4140` in u | Unchanged, still exact |
| Old vertical alias at `Delta v = lambda/H = 0.2070` | Squared correlation 1 | 0.8536, or -0.69 dB |
| Complete RX aperture height | `2H` | `2H + H/8`, 6.25% larger |
| Exact steering periodicity | Independent u/v periods | Skew reciprocal lattice |

One exact reciprocal basis for the stagger is `(0.4140, 0)` and
`(0.2070, 0.8279)`. Its cell has four times the old cell's area, but that does
not mean four times the practically unambiguous coverage: strong near-aliases
remain. The nearby vertical-cut peak is -0.68 dB; the stronger nearby 2-D peak
is approximately -0.54 dB at `(Delta u, Delta v) = (0.0104, 0.2044)`.

Staggering does not broaden the common TX or single-RX-subarray pattern. With
ideal continuously matched RX steering, the sensitivity envelope is unchanged.
A particular finite beam bank can have different straddling losses. The
principal-cell boundary is an alias bookkeeping boundary, not a physical
boundary between safe and unsafe detections; hypotheses on both sides matter.

## The benefit we must not overlook

*2026-09-09, height/8 numbers. The two-pitch results supersede the magnitudes
but the reasoning stands.*

For two normalized, noise-whitened steering vectors, define squared correlation
`rho = abs(a1^H a2)^2`. For a fixed signal in white noise, a useful pairwise
separation diagnostic is

```text
D = matched_signal_SNR * (1 - rho).
```

This is the signal energy outside the wrong hypothesis's subspace, in noise
units, after fitting an unknown complex amplitude. It is not a correct-cell
probability, an exact likelihood for every fluctuation model, or a general
multi-hypothesis performance guarantee.

For the opposite vertical-edge pair, `u = 0`, `v = +/-0.10349`:

- URA coherent TX has `rho = 1`, so no normalized-signature discrimination.
- Staggered coherent TX has `1-rho = 0.1464`: real information, not simply a
  negligible 0.69 dB gain change. The alias causes a 45-degree relative phase
  change between the two alternating column groups, up to common phase.
- Four-quadrant MIMO with the URA has `rho = 0.001171` (-29.3 dB).
- Coherent TX has approximately 3.16 dB more directional SNR than MIMO here
  at equal CPI duration and total TX power; the boresight 6.02 dB difference
  must not be substituted at this off-boresight point.

Consequently, one staggered coherent update provides approximately **0.303
times** the `D` of one URA MIMO update for this pair. In a schedule with three
coherent updates per MIMO update, those coherent updates could contribute
roughly another 0.91 times the MIMO separation energy if their signal levels
are comparable. This makes the possible benefit worth acknowledging, but it
does not establish a latency improvement or justify a direct range conversion.

Adding the stagger to the MIMO measurement itself changes this pair's required
SNR by less than 0.001 dB in the existing binary model. MIMO already separates
it very well. The main opportunity is therefore evidence from coherent updates
between MIMO measurements, not improving this particular MIMO signature.

MUSIC cannot resolve proportional steering vectors. For a single source with
the true covariance and white noise, its normalized pseudospectrum is
proportional to `1/(1-rho)`. It can exploit the stagger's nonzero separation,
but a sharper spectrum is not evidence of a reliable decision with finite
data or calibration error. An algorithm change does not replace this evaluation.

## Costs: distinguish real changes from unquantified risks

- Independent coordinate-wise folding into the old URA cell is no longer an
  exact representation of all staggered steering vectors. Beam dictionaries,
  hypothesis generation and validation need the actual phase-center geometry.
- The response couples u and v. One-dimensional cuts are insufficient for
  finding the strongest competing direction; 2-D searches must distinguish
  wrong lobes from ordinary local angle-estimation error.
- Exact enumeration over the larger reciprocal cell can require more steering
  samples. **Four times the cell area is not proof of four times the product
  processing cost.** Detection beams and track-gated hypothesis evaluation
  need not use the same sampling. The alternating columns also form two regular
  subarrays, so structured processing remains possible.
- Extra ambiguity information depends on calibrated relative RX responses,
  particularly between alternating column groups. A systematic group phase
  error is worth testing alongside independent channel errors. URA plus MIMO
  also needs calibration; an incremental calibration burden has not been
  quantified, and full per-unit pattern measurement is not proven necessary.
- The modeled RX height increases 6.25%. Actual PCB, feed, cost, coupling and
  supplier schedule implications require supplier input, not inference from
  the point-array model.

There is no modeled aperture-area or coherent peak-gain penalty for staggering.
Do not justify the URA by inventing such a penalty or by treating its software
advantage as a measured development-time estimate.

## Gain/RCS plausibility and fluctuation uncertainty

**User input, 2026-09-09:** The 1 m² (0 dBsm) target is the working reference;
the intended targets are not expected to be tens of dB stronger. Gain/RCS
plausibility will be used to discard most remote ambiguities. An exact maximum
RCS and its statistical interpretation are not yet specified.

For a noiseless reference measurement, the RCS required by an alternative is
`sigma_alternative = sigma_reference * G_reference / G_alternative`, using the
complete two-way gain at the same range and mode. A vertical-edge example has
another exact RX alias at `v = -0.3105`: its MIMO correlation is relatively high
(about -1.28 dB), but its coherent two-way gain is approximately 29 dB lower.
Explaining a 1 m² reference target there would require roughly 800 m². That is
a credible candidate for rejection using the stated target knowledge.

Near equal-gain opposite edges, that argument does not help: signature evidence
is still needed. Actual rejection must include noise, pattern uncertainty and
the distinction between mean RCS and an instantaneous fluctuating return.
Use an explicit conservative RCS envelope or prior rather than silently
assuming exactly 1 m² or rejecting candidates solely from normalized patterns.

The temporal fluctuation statistics are unknown. The existing independent
Swerling-1 updates should remain an illustrative case, not a latency guarantee.
A review-only Monte Carlo check of the same four-update binary energy decision
gave about 527 m instead of 884 m at 99% correctness when one RCS draw was held
across all four updates. This was an unconditional comparison, not performance
conditioned on an established track, and is not yet a persistent study output.

Likewise, the review's ideal staggered-coherent binary ranges of 313 m for one
update and 681 m for four use independent fluctuations and exact hypotheses.
Do not promote them to product coverage or compare equal update counts without
accounting for their different rates. These examples demonstrate sensitivity
and potential benefit, not validated operational performance.

## Smallest useful investigation before the meeting

*Plan written 2026-09-09. Items 1 and 2 have since been carried out; see the
sections that follow.*

The objective is to test whether the potential stagger benefit changes the
choice, not to complete the radar or tracker design. Keep the baseline and
prototype presets unchanged. Extend the study-local experiment only. The first
bounded implementation below does not complete this broader investigation plan.

### 1. Identify the decision-relevant competing directions

Start with both sides of the vertical edge, a horizontal-edge control, and
mixed u/v edge or corner cases. Search the visible manifold for competing
lobes and refine their positions in 2-D; do not only evaluate the exact old
folded alias. Include true directions inside the old principal cell.

Report each competitor's correlation and required RCS/gain penalty together.
Try +6 and +10 dBsm ceilings as **sensitivity choices, not established target
bounds**, retaining margin for model uncertainty. Prefer a broad 2-D screen if
cheap enough; a few selected cases are not a full coverage guarantee.

**Deliverable:** A small table or map identifying which plausible pairs URA
MIMO struggles with, and whether the stagger helps those same pairs. Check the
horizontal control: a remaining horizontal bottleneck limits any system-wide
benefit claimed from improving vertical discrimination.

### 2. Compare evidence at equal time and energy

For the surviving difficult cases, start both layouts with the same nominal
coherent observation and allow an on-demand MIMO burst with variable
illumination. Include coherent-only processing to show whether staggering can
avoid the burst. Retain the eight complex RX channels; do not reduce the
coherent-mode input to a winning-beam index or scalar detection. Compare equal
additional energy, and treat switching/SP delay separately from illumination.

First hold instantaneous target RCS/SNR fixed, allow an unknown complex amplitude
per update, and vary SNR. This answers the conditional noise-limited question
without having to guess the physical fluctuation timescale. Use the complete
mode-dependent SNR and compare wrong-cell probability, or required SNR for an
illustrative 1% error rate, for the same candidate set and decision rule.

Then add a small mismatch stress test: simulate perturbed true channels while
processing with the nominal dictionary. Illustrative 5/10-degree phase and
0.5/1 dB amplitude cases, including systematic alternating-group error, are
not supplier tolerances or pass/fail specifications. If time permits, repeat
with block-constant and independent Swerling amplitudes as sensitivity cases;
neither is a universal bound on real targets.

**Deliverable:** One compact comparison of nominal and perturbed performance.
Ask whether the extra evidence remains useful, whether fewer MIMO updates could
achieve a comparable result, and whether it changes the system's worst case.
No full trajectory tracker, MUSIC implementation or waveform optimization is
needed for this decision aid.

### First on-demand resolution-event experiment, 2026-09-09

Implemented in [rx_resolution_experiment.py](rx_resolution_experiment.py),
separately from the geometry-illustration script. The result supports retaining
URA as the default, while showing a genuine but modest vertical benefit from
staggering in the tested events. It is not a full-field reliability demonstration.

**Model:**

- One baseline coherent observation followed by one ideal four-quadrant MIMO
  measurement with variable illumination. Fixed 1 m² target, known to exist
  in a range/Doppler gate; trials are not conditioned on detector threshold
  crossing. Zero added energy means no MIMO measurement or noise statistic.
- True directions: positive vertical edge `(0, 0.10349)`, horizontal edge
  `(0.20698, 0)`, and corner `(0.20698, 0.10349)`. These are deliberately
  ambiguous events, not a distribution of arrivals or scene-average overhead.
- Nominal coherent matched SNR is 10 or 16 dB. Directional MIMO/coherent SNR
  differences are -3.16, +2.17 and +5.04 dB respectively. A constant boresight
  -6.02 dB penalty would be wrong for these directions.
- Old-URA aliases across the visible disk seed local 17 × 17 angle grids.
  Each neighborhood extends +/-0.75 times period/channel-count per axis,
  about +/-0.0776 in u and v. Each layout uses its actual RX phase centers.
- Candidate angles must explain the noiseless nominal coherent signal with
  RCS no greater than +10 dBsm. This leaves 2, 6 and 4 candidate lobes for the
  three events. Screening is not a noisy RCS estimator or a posterior.
- Sum the whitened projection energies from both modes, fitting unrelated
  unknown complex amplitudes but the same angle. Maximize over angles per
  lobe, then choose the highest-scoring lobe. Exact ties are randomized.
- The phase stress applies independent zero-mean Gaussian 10-degree RMS
  offsets to every RX channel and TX quadrant, fixed throughout an event.
  TX offsets also perturb the coherent sum. The processor uses nominal
  patterns. This is an illustrative stress distribution, not a hard tolerance.
- 20,000 trials per configuration, recorded seed, common raw draws across
  layouts and RCS screens. The metric is forced-choice wrong-lobe probability,
  not the confidence of a publication decision with an abstention option.

**Results:** First *sampled* extra MIMO energy whose pointwise 95% binomial
upper error bound is at most 1%. These are not finely estimated minimum energies
or simultaneous confidence guarantees across the entire experiment.

| Event | Coherent SNR | 1 m² reference range | Nominal: URA / stagger | 10-degree stress: URA / stagger |
|---|---:|---:|---:|---:|
| Vertical edge | 10 dB | 893 m | 2 / 2 | 3 / 3 |
| Vertical edge | 16 dB | 632 m | 0.5 / 0.375 | 0.5 / 0.5 |
| Horizontal edge | 10 dB | 554 m | 1.5 / 1.5 | 1.5 / 1.5 |
| Horizontal edge | 16 dB | 392 m | 0.375 / 0.375 | 0.375 / 0.375 |
| Corner | 10 dB | 379 m | 0.75 / 0.75 | 0.75 / 0.75 |
| Corner | 16 dB | 268 m | 0.25 / 0.25 | 0.25 / 0.25 |

Energy is in baseline-CPI equivalents at unchanged total TX power. One unit
is approximately 10.49 ms of active sampling/illumination in the current budget,
**not** a 50 ms frame or measured wall-clock latency. Scaling assumes a single
coherent MIMO integration and unchanged processing losses; no longer waveform
or sequence of independent CPIs has been implemented.

At the 16 dB vertical edge, coherent-only error falls from about 50% for URA
to 6.7% for nominal stagger, or 9.5% with phase stress. This is useful evidence,
but does not eliminate the burst at a 1% objective in this case. MIMO reduces
the difference between layouts; horizontal and corner results nearly coincide.

**Checks:** A 9 × 9 rather than 17 × 17 local grid changed probabilities by at
most 0.25 percentage points without changing the sampled energy thresholds.
A +6 rather than +10 dBsm ceiling changed probabilities by at most 0.5 points;
one near-threshold vertical stress case moved from 3 to 2 sampled energy units
for stagger. Such threshold-grid changes are not precise percentage savings.

**Limits:** The approximate folded-angle seeds are centered on the true folded
angle. Local angle uncertainty is searched, but no initial angle estimator is
simulated. The old-alias neighborhoods are not a complete global search for
staggered near-aliases, and only three positive edge/corner directions are tested.
There is no RCS fluctuation, motion, interference, multi-target association,
waveform orthogonality loss, systematic group-phase stress, amplitude error,
embedded-pattern distortion or measured processing/switching latency.

The projection rule is not an optimal gated Bayesian tracker. At very low MIMO
energy, adding its noisy statistic can slightly worsen a decision; RCS and
existence evidence are not jointly modeled. The next useful extensions are
off-edge/mixed-sign directions and structured calibration stress, or a more
realistic gated likelihood if a concrete decision-relevant question warrants it.

### Stagger amount and TX-taper dependence, 2026-09-10

Implemented in
[rx_stagger_amount_experiment.py](rx_stagger_amount_experiment.py) with
study-local tests. Three questions were checked before the meeting.

**Where the MIMO discrimination comes from.** The TX radiator pitch equals the
RX pitch (2.351 mm, 0.604λ), so an 8 × 8 TX quadrant is exactly one RX
subarray height wide. The quadrant phase centers therefore share the RX
lattice, and untapered quadrants alias exactly where the RX array does:

| TX quadrant excitation | Opposite vertical edges | Opposite horizontal edges | Boresight to vertical replica |
|---|---:|---:|---:|
| Nominal supplied (amplitude and phase) | -29.3 dB | -3.1 dB | -8.2 dB |
| Supplied amplitude only, phase removed | -4.7 dB | -0.04 dB | -26.2 dB |
| Uniform quadrants | 0.0 dB | -0.6 dB | -0.02 dB |

The supplied excitation carries a smooth, rotationally symmetric quadratic
phase of about 180° at the edge centres and 360° at the corners. It is a
defocus: it widens the coherent 3 dB beamwidth from 6.9° to 12.6° at a
boresight cost of 5.3 dB (28.8 versus 23.5 dBi). Its linear component across
each quadrant squints every quadrant beam by 6.0° in u and v toward the
opposite corner, and this squint is essentially the entire source of the
MIMO alias discrimination. **The nominal -29 dB vertical-edge result is a
property of the prescribed TX defocus, not of the antenna geometry.**

Sensitivity to that dependence (perturbed true patterns, nominal dictionary;
margin is how much better the nominal true-direction signature fits than the
nominal alias signature):

| Realized defocus, fraction of prescribed phase | Vertical-edge margin | Horizontal-edge margin | Coherent beamwidth |
|---:|---:|---:|---:|
| 0.0 (focused) | 6.1 dB | 0.0 dB | 6.9° |
| 0.6 | 17.8 dB | 1.8 dB | 8.2° |
| 0.8 | 28.1 dB | 2.5 dB | 9.8° |
| 1.0 | 29.3 dB | 3.1 dB | 12.6° |
| 1.2 | 20.8 dB | 3.7 dB | 15.4° |
| 1.4 | 17.4 dB | 4.3 dB | 17.6° |

*Corrected 2026-09-10 after review: the first version scaled the wrapped
`np.angle` phase, which introduced discontinuities for non-integer scales.
The unwrapped surface is scaled now; the 0.6 row changed from 11.5/3.0 to
17.8/1.8 dB.*

| Uncalibrated systematic upper/lower quadrant phase error | Vertical-edge margin |
|---:|---:|
| 10° | 20.2 dB |
| 20° | 15.8 dB |
| 30° | 12.9 dB |
| 45° | 9.8 dB |

Scaling the amplitude taper alone between the 0.5 and 2 power keeps the
vertical-edge correlation below -18 dB. So the vertical MIMO discrimination
is robust as long as the broadened beam is what gets built and the quadrant
phases are calibrated to a few tens of degrees. It is *not* robust to a
change of TX excitation: a focused long-range mode, TX subarray phase
steering or any re-shaped taper (see the ideas in [NOTES.md](NOTES.md)) would
change these numbers and must be re-evaluated for MIMO discrimination. The
horizontal-edge margin scales with the amount of defocus, from 1.8 dB at 0.6
times the prescribed phase to 4.3 dB at 1.4 times: an under-realized defocus
weakens the MIMO-limited horizontal case, which is why the horizontal-edge
metric in [ANTENNA_REQUIREMENTS.md](ANTENNA_REQUIREMENTS.md) matters. The
stagger's vertical information is purely RX geometry and does not depend on
any of this.

**Stagger amount.** Alternating columns differ in phase by `2π s/H` at the
old vertical alias, so the two four-channel groups give `rho = cos²(π s/H)`:

| Offset `s` between adjacent columns | `1 - rho` at old vertical alias | Horizontal-edge `rho` | Aperture height |
|---|---:|---:|---:|
| 0 (URA) | 0.000 | 1.000 | 37.6 mm |
| H/8 (internal sketch) | 0.146 | 1.000 | 40.0 mm |
| H/4 | 0.500 | 1.000 | 42.3 mm |
| 3H/8 | 0.854 | 1.000 | 44.7 mm |
| H/2 | 1.000 | 1.000 | 47.0 mm |

Horizontal aliases stay exact for every offset. Larger offsets move the exact
lattice aliases to `(Δu, Δv) = (λ/2W, kλ/H)`: `(0.207, 0.828)` for H/8 and
`(0.207, 0.414)` for H/4, both far outside the TX beam and gain-rejectable.
A coherent-mode competitor screen (RX correlation peaks needing at most
+12 dBsm) for the vertical edge, a half-edge direction, a beam corner and
the horizontal edge found: the old vertical alias reduced to -0.5 dB (H/8) or
-2.2 dB (H/4) with its peak displaced by up to 0.02 in u; a new diagonal
near-alias family at `(±λ/2W, ±λ/H)` offsets at -5.5 dB (H/8) or -2.2 dB (H/4)
that needed about +9 to +10 dBsm in the tested beam-corner case; and ordinary
four-element sidelobes near -10 dB that all layouts share. No new strong
competitor appeared inside the TX beam at equal gain. H/2 would instead make
`(λ/2W, λ/H)` an exact alias and is a different design, not evaluated further.
The H/4 layout is a study construct; the internal sketch used one radiator
pitch, chosen without analysis.

**In-beam competitor map (afternoon addition).** The same screen was run for
every true direction on a 33 × 33 grid over |u|, |v| ≤ 0.16, with the
strongest RX-correlation competitor outside the true direction's own
old-URA cell that needs at most +10 dBsm. Within the TX 3 dB region:

| Layout | Worst coherent competitor | Directions with a competitor ≥ -3 dB | ≥ -1 dB | Worst MIMO competitor (searched separately) |
|---|---:|---:|---:|---:|
| URA | 0.0 dB | 74% | 57% | -10.3 dB |
| H/8 | -0.5 dB | 71% | 51% | -10.5 dB |
| H/4 | -2.2 dB | 62% | 0% | -11.4 dB |

*Corrected 2026-09-10 after review: the first version reported the MIMO
correlation at the strongest coherent competitor, which is not the strongest
MIMO competitor (at (0, 0.10) the URA has about -27 dB at the former and
-12 dB at the latter). The MIMO column is now a separate search over the
same admissible set; within the TX 3 dB region the worst values happen to be
nearly the same, but no global MIMO guarantee is implied.*

Two things follow. First, gain plausibility protects the URA only in a band
of roughly ±2° around the horizontal plane, less than the exact-alias
calculation suggests: with a soft RCS ceiling, the *skirt* of the alias lobe
(a direction near the alias with correlation -0.5 to -1 dB but 5 to 10 dB
more gain) becomes admissible before the exact alias does, because the
two-element vertical factor `cos²(πΔv/0.207)` is broad. Second, H/4 caps the
worst coherent-mode competitor at -2.2 dB (`1 - rho ≥ 0.39`) everywhere in
the TX 3 dB region, with nothing near-exact left; this is the tested-sense
confirmation of the height/4 hunch. The worst MIMO competitor in the same
region is about -10 to -11 dB in all three layouts, and it rises toward the
edge of the beam (about -5 dB at |u| = 0.15, outside the 3 dB region). Figure:
`generated/experimental/on_demand/stagger_in_beam_competitors.png`.

**Equal-total-height variants.** Two ways to keep the original 37.6 mm RX
height with a two-pitch stagger, from the script's variant table:

| Variant | Subarray height | Own vertical edge | `1 - rho` | Subarray gain | Total height |
|---|---:|---:|---:|---:|---:|
| 8 rows, H/4 stagger | 18.81 mm | ±5.9° | 0.50 | 0 dB | 42.3 mm |
| 7 rows, 2-pitch stagger (2H'/7) | 16.46 mm | ±6.8° | 0.61 | -0.58 dB | 37.6 mm |
| 8 rows shrunk, H'/4 stagger | 16.72 mm | ±6.7° | 0.50 | -0.51 dB | 37.6 mm |

The 7-row variant keeps the 16-row radiator grid and pitch: each column
populates 14 of 16 rows, offset two rows between adjacent columns. It costs
0.6 dB of RX gain (about 3% range), moves the vertical edge outward by
0.9° and gives slightly more coherent-mode separation than H/4. Neither
variant has been run through the event simulation; their vertical-edge SNR
is about 1 dB lower than the 8-row case at a slightly wider angle, and the
changed height also moves their aliases relative to the TX pattern. Treat
them as promising extrapolations.

**Multi-frame resolution events.** Same model as the 2026-09-09 experiment,
extended to `K` coherent frames with independent noise and a fixed target
before one MIMO measurement, for URA, H/8 and H/4; 20,000 trials. After the
review the candidate bank is seeded at half u-periods as well, so the
diagonal near-alias family that a stagger creates is included for every
layout, and a third RX error scenario applies a systematic, uncalibrated
+15° phase to columns two and four (the unfavourable sign for H/4) in
addition to the nominal and 10° random cases.

Vertical edge, wrong-lobe probability with coherent frames only:

| Coherent SNR (1 m² range) | RX error | Frames | URA | H/8 | H/4 |
|---|---|---:|---:|---:|---:|
| 10 dB (893 m) | nominal | 1 | 0.50 | 0.26 | 0.13 |
| 10 dB | nominal | 2 | 0.50 | 0.15 | 0.038 |
| 10 dB | nominal | 4 | 0.50 | 0.071 | 0.0037 |
| 10 dB | 10° random | 4 | 0.50 | 0.099 | 0.0097 |
| 10 dB | +15° column group | 4 | 0.50 | 0.31 | 0.029 |
| 16 dB (632 m) | nominal | 1 | 0.50 | 0.063 | 0.0024 |
| 16 dB | nominal | 2 | 0.50 | 0.017 | 0.0001 |
| 16 dB | 10° random | 1 | 0.50 | 0.095 | 0.0070 |
| 16 dB | +15° column group | 1 | 0.50 | 0.31 | 0.023 |
| 16 dB | +15° column group | 2 | 0.50 | 0.23 | 0.0024 |
| 16 dB | +15° column group | 4 | 0.50 | 0.15 | 0.0000 |

First sampled MIMO energy (baseline-CPI equivalents, after the stated frames)
whose 95% upper error bound is at most 1%; zero means no burst was needed:

| Event | Coherent SNR | RX error | Frames | URA | H/8 | H/4 |
|---|---:|---|---:|---:|---:|---:|
| Vertical edge | 10 dB | nominal | 1 | 2 | 2 | 2 |
| Vertical edge | 10 dB | nominal | 4 | 2 | 1.5 | 0 |
| Vertical edge | 10 dB | 10° random | 4 | 2 | 2 | 0.25 |
| Vertical edge | 10 dB | +15° column group | 4 | 2 | 3 | 1.0 |
| Vertical edge | 16 dB | nominal | 1 | 0.5 | 0.375 | 0 |
| Vertical edge | 16 dB | 10° random | 1 | 0.5 | 0.5 | 0 |
| Vertical edge | 16 dB | +15° column group | 1 | 0.5 | 0.75 | 0.25 |
| Vertical edge | 16 dB | +15° column group | 2 | 0.5 | 0.75 | 0 |
| Horizontal edge | 10 dB | any | any | 1.5 | 1.5 | 1.5 |
| Horizontal edge | 16 dB | any | any | 0.375 | 0.375 | 0.375 |
| Corner | 10 dB | any | any | 0.75 | 0.75 | 0.75 |
| Corner | 16 dB | any | any | 0.25 | 0.25 | 0.25 |

Including the diagonal family raised the H/4 single-frame error at 893 m
from 0.088 to 0.13 and changed the four-frame results by less than a
percentage point. The systematic +15° column-group error matters more: it
leaves H/8 at 15 to 31% error even after four frames, whereas H/4 still
reaches 0.2% in two frames at 632 m but needs a 1.0 CPI burst after four
frames at 893 m. Calibration of the relative RX column phase is therefore
part of what makes the stagger useful, not a refinement.

At 20 Hz, four frames are 200 ms of ordinary operation with no mode switch.
The horizontal edge and corner sit at ±11.9° azimuth, outside the TX 3 dB
beam, where a 1 m² target reaches 10 dB SNR at roughly 550 m; the vertical
edge sits inside the TX beam at 6°, where the same target reaches it beyond
900 m. The 550 m figure is a reference range, not a cutoff: low-Pd tracking
and stronger targets extend the region where the horizontal family matters. The stagger therefore helps exactly the long-range
family and leaves the short-range family to MIMO.

**Limits.** All 2026-09-09 limits apply. Frames are noise-independent with a
fixed target: slow RCS fluctuation would make multi-frame accumulation less
effective, but equally so for repeated MIMO updates. The candidate bank now
includes the half-period seeds, but it is still a finite set of local grids
around lattice points, not a global search. A trial that hits the 1%
objective with zero MIMO energy is a forced-choice result, not a
publication-confidence rule, and none of these frame counts is a
resolution-time guarantee. Only positive edge/corner
directions and the alternating (+,-,+,-) column pattern were tested. Nothing
here measures PCB, feed, coupling, radome or supplier schedule implications
of a taller RX aperture.

### Stop rule and open questions

*The 2026-09-09 stop rule read: if the small comparison finds no material,
robust benefit, recommend URA; if it reveals a clear benefit, weigh it against
supplier and processing constraints. The comparison found a clear benefit for
a two-pitch offset, so the direction changed as recorded at the top.*

Still open after the meeting:

- Supplier: early feedback on obvious PCB, feed, coupling or schedule issues
  with options C and D (two-pitch stagger, eight or seven rows), not a full
  analysis. The one-pitch sketch was ours and may not have been discussed
  with them at all.
- Supplier: agreement that the four individual TX quadrant patterns are a
  requirement, that the beam widening comes from the prescribed quadratic
  phase or an agreed equivalent, and that per-port complex patterns are a
  deliverable; see [ANTENNA_REQUIREMENTS.md](ANTENNA_REQUIREMENTS.md).
- Internal: whether the long-range in-beam vertical family or the
  short-range off-beam horizontal family drives the requirement, and who
  owns the non-separable steering and per-lobe coherent likelihoods in the
  signal processing and tracker.
- Internal: check the measured per-port patterns of the existing
  four-quadrant prototype antenna against the same metrics as a first
  realizability test.
- No numerical benefit threshold or wrong-cell publication requirement has
  yet been agreed.

## Reproduction and decision record

```text
source venv/bin/activate
python studies/2026-09-02_lannik-psi/rx_layout_experiment.py
python studies/2026-09-02_lannik-psi/rx_resolution_experiment.py
python studies/2026-09-02_lannik-psi/rx_stagger_amount_experiment.py  # about 3 min
python -m pytest studies/2026-09-02_lannik-psi/test_rx_resolution_experiment.py \
    studies/2026-09-02_lannik-psi/test_rx_stagger_amount_experiment.py -q
```

Figures are under `generated/experimental/`: geometry, 2-D channel factors,
principal cuts with TX/RX gain overlays, and the existing fixed-fold MIMO alias
comparison. The new resolution experiment writes into `on_demand/`:
`resolution_phase_0deg.png`, `resolution_phase_10deg.png` and
`resolution_summary.json` (configuration, seed, error counts and bounds).
These are regenerable working outputs, not archived deliverables. Reproduce
the sensitivity runs using `--local-samples 9` or `--rcs-ceiling-dbsm 6` and a
separate `--output-dir`. Six study-local tests cover normalization, screening,
alias ties, analytic orthogonal-signature error probability, noise-only behavior
and error bounds. The stagger-amount script prints the TX-taper decomposition,
stagger table and competitor screen, and writes
`stagger_amount_vertical_edge.png`, `stagger_in_beam_competitors.png` and
`stagger_amount_summary.json` into the same `on_demand/` directory; its three tests cover the column-group
correlation formula, the taper-only origin of the MIMO discrimination and the
K-frame square-law error probability. The broader investigation plan remains
only partly complete.

- **2026-09-08:** Added both provisional layouts and the initial array-factor
  and fixed-fold MIMO comparisons. Initial interpretation emphasized the small
  change in grating-lobe height.
- **2026-09-09:** Recorded the review correction: coherent updates can gain
  useful vertical-alias information even when the extra MIMO benefit is tiny.
  Established the schedule-driven URA preference and the bounded checks above.
- **2026-09-09:** Adopted on-demand MIMO as the likely path and implemented the
  first fixed-RCS multi-lobe resolution-event comparison. Staggering provides
  extra vertical information but only modest MIMO-energy savings in the tested
  events; the URA preference is retained provisionally.
- **2026-09-10:** Found that the MIMO alias discrimination is entirely a
  property of the prescribed TX defocus (quadratic phase) and its quadrant
  squint, robust to plausible taper and static phase errors but not to a
  change of TX excitation. Showed that the stagger amount dominates the
  trade: height/8 gives 0.146 of an unambiguous measurement's separation per
  coherent frame, height/4 gives 0.500 and resolves the tested vertical-edge
  events without MIMO within one to four frames. Proposed preferring
  height/4 if the supplier can accommodate it, otherwise a close call
  between height/8 and URA.
- **2026-09-10, later:** Added the in-beam competitor map (H/4 caps the worst
  coherent competitor at -2.2 dB across the TX 3 dB region; URA gain
  plausibility protects only about ±2° around the horizontal plane), the
  equal-total-height variants (7 rows with a two-pitch stagger keeps
  37.6 mm at -0.6 dB) and the supplier-facing
  [`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md) draft.
- **2026-09-10, review:** A separate review found a phase-wrapping bug in
  the defocus-scale sweep (fixed; 0.6× now 17.8/1.8 dB) and that the in-beam
  map reported MIMO at the strongest coherent competitor rather than the
  strongest MIMO competitor (fixed; searched separately). Added the
  diagonal near-alias family to the event candidate bank and a systematic
  +15° RX column-group error scenario. Conclusions unchanged; qualifications
  recorded: frame counts are promising evidence, not latency guarantees;
  processing cost is likely manageable, not budgeted; ±15° is a proposed
  calibration target; option D is an extrapolation; 550 m is a 10 dB SNR
  reference, not a cutoff.
- **Decision pending, 2026-09-10 meeting:** Record the selected geometry, reasons,
  dissenting considerations, accepted uncertainties and follow-up owners here.
