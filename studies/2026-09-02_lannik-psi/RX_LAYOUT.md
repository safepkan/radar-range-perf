# Lannik Psi RX-layout decision notes

Working decision brief, 2026-09-09. The internal meeting on 2026-09-10 is
expected to choose the rectangular prototype geometry; ordering may not allow
further deferral. This is a recommendation under uncertainty, not a finalized
antenna specification or a demonstrated ambiguity-resolution capability.

See [NOTES.md](NOTES.md) for system context and [MIMO.md](MIMO.md) for the
track-directed MIMO architecture. The corresponding experimental script is
[rx_layout_experiment.py](rx_layout_experiment.py). Keep geometry-specific
reasoning and the eventual decision here rather than duplicating those notes.

## Decision and current recommendation

Two prototypes are planned. The rotated, square-subarray 2 × 4 layout is likely
fixed. The active choice is between otherwise identical rectangular RX
subarrays in an unstaggered or vertically staggered 4 × 2 channel arrangement.
Neither rectangular alternative is an official prototype preset yet.

**Current recommendation:** Prefer the unstaggered URA, given the tight project
schedule, its simple periodic processing, and the existing commitment to
MIMO-assisted ambiguity resolution. The nominal study supports this direction
but does not yet establish production-level reliability or resolution latency.

The reason is not that staggering provides no useful information. It can make
ordinary coherent-TX updates informative about the troublesome vertical alias.
Its value would be reduced ambiguity-resolution latency, reduced MIMO demand,
or additional robustness. It does not remove the horizontal aliases, so it is
not a substitute for the planned ambiguity-resolution architecture.

**What would change the recommendation:** A small, fair comparison showing a
material benefit over URA plus MIMO for plausible targets and imperfect
calibration, together with an acceptable implementation and supplier cost.
If that evidence cannot be obtained before ordering, retain the URA as a
deliberate schedule-risk choice, recording the possible benefit being forgone.

## What is established in the current model

Let `W = 9.405 mm`, `H = 18.811 mm` and `lambda = 3.893 mm` at 77 GHz.
The proposed stagger shifts alternating complete two-channel columns by
`+H/16` and `-H/16`: adjacent columns differ by `s = H/8 = 2.351 mm`.
This matches our interpretation of the supplied image; confirm with the
supplier before turning it into a specification.

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

The objective is to test whether the potential stagger benefit changes the
choice, not to complete the radar or tracker design. Keep the baseline and
prototype presets unchanged. Extend the study-local experiment only.

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

For the surviving difficult cases, compare URA and stagger with the same
three-coherent/one-MIMO schedule. Use one block (0.2 s) and, if useful, four
blocks (0.8 s). Retain the eight complex RX channels; do not reduce the
coherent-mode input to a winning-beam index or scalar detection.

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

### Stop rule and meeting questions

If the small comparison finds no material, robust benefit, stop and recommend
URA. If it reveals a clear benefit, weigh it against actual supplier and
processing constraints. An inconclusive result is not evidence that staggering
is ineffective; under the stated schedule preference it still favors the
simpler baseline, with the unresolved risk recorded.

Ask the supplier to confirm the intended offset, any feed/PCB/schedule cost,
and whether the delivered complex patterns and calibration approach differ.
Ask internally whether saving ambiguity-resolution time or MIMO resource is
currently important enough to accept additional development work. No numerical
benefit threshold has yet been agreed.

## Reproduction and decision record

```text
source venv/bin/activate
python studies/2026-09-02_lannik-psi/rx_layout_experiment.py
```

Figures are under `generated/experimental/`: geometry, 2-D channel factors,
principal cuts with TX/RX gain overlays, and the existing fixed-fold MIMO alias
comparison. The two investigations above are proposed work, not implemented
results. Review-only diagnostics should be made reproducible in the experiment
if they are used as quantitative decision evidence.

- **2026-09-08:** Added both provisional layouts and the initial array-factor
  and fixed-fold MIMO comparisons. Initial interpretation emphasized the small
  change in grating-lobe height.
- **2026-09-09:** Recorded the review correction: coherent updates can gain
  useful vertical-alias information even when the extra MIMO benefit is tiny.
  Established the schedule-driven URA preference and the bounded checks above.
- **Decision pending, 2026-09-10 meeting:** Record the selected geometry, reasons,
  dissenting considerations, accepted uncertainties and follow-up owners here.
