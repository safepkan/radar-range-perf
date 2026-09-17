<!--
PDF export from this Markdown (Pandoc + Typst), using the shared RFQ style:
Run from the repository root:

cd studies/2026-09-02_lannik-psi/rfq/internal
pandoc REVIEW.md --from=markdown --pdf-engine=typst \
    --template=../tools/document.typst --lua-filter=../tools/pagebreak.lua \
    --metadata=internal-review:true --output=REVIEW.pdf

To regenerate the figures and both PDFs, run from the repository root instead:
sh studies/2026-09-02_lannik-psi/rfq/tools/build.sh

The metadata flag selects the internal-review PDF title and running header.
This comment is omitted from the rendered document.
-->

# Lannik Psi antenna RFQ — internal review

Revised 2026-09-17. Internal rationale and follow-ups; do not include this note
in the supplier package. This note connects the old presentation to the new
technical description, explains the changes, and identifies decisions for
RFQ issue and subsequent design reviews. The supplier brief is
[technical description for RFQ](../TECHNICAL_DESCRIPTION.md).

## Document and scope update, 2026-09-17

The supplier attachment now starts with the operating concept and four figures
generated from the study: TX waveform groups, both selected RX layouts, the
reference amplitude/phase distribution and half-aperture beam behavior.
Coordinates, discrimination metrics and the data contract are in appendices.
The main text distinguishes quotation information, early design evidence and
the as-built/measured data needed for system models and signal processing.

The user confirmed 76–77 GHz with a nominal 76.5 GHz centre. Either horizontal
or vertical linear polarization is acceptable in principle; selection is still
open. Exact TX/RX dimensions originate in the supplied reference layout and
are an analysis baseline, with justified adjustments open to joint evaluation.
TX/RX aperture dimensions, subarray sizes and spacing remain in scope. Exact
mechanical interfaces have already been defined by others and are covered
separately; only approximate overall antenna dimensions are given here.

Previous reading/test PDFs were removed at the user's request. The current
eight-page PDF is regenerated from the supplier Markdown and vector figures;
see [the folder guide](../README.md). No radar model was changed.

## Recommended approach

Send one coherent technical brief with the reference TX excitation and an
agreed port/coordinate drawing. Use the first supplier response to establish
feasibility, expected loss, measurement capability and the expensive tradeoffs.
Then freeze quantitative acceptance criteria against the preliminary complex
patterns. The current brief is suitable for this feasibility/RFQ conversation;
it is not a completed production acceptance specification.

The presentation should not accompany the brief as a second specification.
It contains useful starting values, but their authority is uncertain and some
entries contradict each other. The user confirmed that its numbers should
mostly be treated as feedback targets, while noting that some may turn out to
be firm. The brief therefore identifies the 76–77 GHz band (76.5 GHz centre)
as confirmed, the choice of horizontal or vertical linear polarization as
open, and other inherited numbers as proposed targets or indicative dimensions.
Their status needs an owner, not inference from how a slide is worded.

## Changes and technical judgments

- **TX radiator count:** 16 × 16 is the supplied reference implementation.
  There is no demonstrated system need for that count itself. Preserve the
  equal-power eight-port/four-group architecture and evaluate the complete
  patterns for any alternative. This is design freedom, not evidence that a
  smaller or differently shaped aperture will perform equally well.
- **Selected RX geometry:** retained the H/4 staggered rectangle and the 2 × 4
  square-channel arrangement. Removed rejected layouts and meeting history.
  Radiator construction is negotiable, but centres, effective dimensions and
  illumination cannot change without updating the ambiguity assessment.
- **Operating modes:** the brief now specifies the selected interlaced
  left/right and up/down half-aperture modes. Four-quadrant measurements remain
  useful study evidence, but are not the initial operational definition.
- **Feed partition:** two full-power ports feed separate regions within each
  quadrant. Removed language that could be read as specifying a physical PA
  output combiner or relying on amplitude backoff. The supplier must show the
  actual equal-power partition; neither table labels nor equal-area sketches
  establish it.
- **Performance quantities:** separated directivity, realized gain, feed loss,
  input match and digital RX combination. A directivity target alone does not
  protect the range budget. The 23.5 dBi study result uses inferred radiator
  gain; it is not a verified realized-gain target at an MMIC reference plane.
- **Taper and sidelobes:** removed the implication that a 35 dB Taylor parameter
  guarantees 35 dB sidelobes after phase shaping. An eventual sidelobe mask
  needs an angular domain and main-beam exclusion, evaluated with RX gain.
- **Calibration:** removed unsupported blanket 1 dB/10° angular agreement and
  the assertion that ±0.2 mm is sufficient. Phase is ill-conditioned near a
  null, and stable channel-specific patterns can be modeled. The ±15° RX
  column-group figure remains a provisional residual system calibration budget.
- **Coordinate convention:** replaced undefined viewing direction and `x`
  right/`y` up with the repository's forward/left/up axes. The tabulated numbers
  match the study's H/4 layout; the brief explicitly defines the front view.
  Check handedness and numbering against the mechanical drawing before release.

## Are direction-pair correlations the right metric?

Yes, as a normalized spatial-discrimination metric. The unknown complex target
amplitude means that two proportional response vectors are indistinguishable.
Squared normalized correlation measures that relationship directly. It is easy
to reproduce from complex port patterns and avoids specifying an implementation
such as a particular phase law.

It is not sufficient by itself. Use three complementary views:

1. **Supplier design diagnostics:** a small set of physically meaningful pairs,
   tested using the actual half-aperture modes. Include the square prototype's
   vertical pair, which the previous draft omitted. Report directional power
   with every correlation.
2. **System pattern assessment:** gain and normalized correlation over the
   full TX × RX response, searching competing lobes in 2-D for each selected
   RX layout. Search both signs, off-axis pairs and displaced near-alias peaks.
   A maximum over *all* direction pairs is meaningless without excluding local
   angle neighbors, whose correlation approaches one. Similarly, a gain cutoff
   or RCS ceiling is an explicit system assumption, not a supplier loophole.
3. **Robustness and eventual acceptance:** measurements or perturbed truth
   processed with the planned calibrated dictionary, with the waveform,
   schedule, SNR and target assumptions stated. Final wrong-cell probability
   and resolution latency belong to the system validation.

For a fixed single-target signal in whitened noise, fitting out complex
amplitude under the wrong direction leaves residual signal energy
`D = SNR * (1-rho)`. This explains why an increasingly deep correlation minimum
has diminishing value. At -10 dB, `1-rho = 0.90`; at -29.3 dB it is about
0.999. The difference is only about 0.45 dB of separation energy at equal SNR.
By comparison, the proposed -2.5 dB horizontal threshold allows about 0.70 dB
less separation energy than the -3.14 dB reference. Neither allowance has yet
been allocated from a validated system error/latency budget.

`D` is a useful engineering diagnostic, not an exact error probability or a
universal Fisher-information metric. It must be evaluated in both directions
because SNR differs. Detection gain, global ambiguity and local angular
precision are separate properties.

A further pitfall: a common direction-independent phase offset applied to each
separated channel leaves its *self-consistent* normalized correlations unchanged
(the diagonal transformation is unitary in white noise). It can still break a
processor using the old dictionary. Within a coherent TX group, individual
port phase offsets can additionally change the group pattern and its gain.
Consequently neither correlation alone nor one raw phase tolerance proves
calibration robustness.

The former boresight-to-vertical-replica check was removed from the compact
supplier target table. At the exact replica the ideal uniform RX subarray has
a null, so TX-only correlation is not by itself a compelling requirement.
That region still needs to be included in the full pattern/gain review with
realistic null filling. It has not been declared harmless.

## Presentation reconciliation

Reviewed both input PDFs, including text extraction and the revised deck's
layout/requirement illustrations. The revised deck is
`../../inputs/Lannik_Psi_antenna_thpe_260916.pdf` (PA3, nine pages).

| Item | Observation | Treatment in the brief |
|---|---|---|
| Band | Slides specify 76–77 GHz / 76.5 GHz; study calculations use 77 GHz | Band confirmed by system owner on 2026-09-17; frequency-dependent alias coordinates, with 77 GHz results labeled explicitly |
| Large RX stagger, p. 2 | Text says wavelength pitch; selected study geometry is two radiator pitches, approximately 4.70 mm, not the 3.9 mm free-space wavelength | Explicit millimetres, ratio H/4 and coordinates |
| TX width, pp. 4, 8, 9 | Broadened pattern slides say approximately ±6.5°; small requirements slide says >±3° | Common broad TX concept, approximately 13° full width as discussion target |
| Small RX gain, pp. 7 and 9 | Pattern slide carries >28 dBi sum / ~21 dBi channel; requirement slide says >25 / >18 | 18 dBi per-channel discussion target; combined response explicitly defined |
| Small TX taper, p. 9 | Central-channel prescription differs from the common broadened TX concept | Supplier proposes physical partition; no inherited channel-specific taper mandate |
| Return loss, pp. 5 and 9 | “Return loss <-20 dB” mixes signed reflection and positive return loss | Explicit S-parameter magnitude ≤ -20 dB / return loss ≥ 20 dB |
| “No power loss” | Passive redistribution can avoid intentional attenuation; it does not eliminate feed loss or broadening/taper directivity cost | Explicit loss and realized-gain accounting |
| MIMO | No operational split definition or complex-pattern acceptance method | Both half-aperture modes and per-port deliverables included |

## Items to close, with suggested ownership

### Before issuing the RFQ

Use this as the internal readiness check for the RFQ. Establish the scope,
responsibilities and status of the inputs. Open numerical values can remain
explicit quotation assumptions or supplier discussion points; the later design
questions below do not all need answers before the RFQ can be sent.

| Owner | Decision or input |
|---|---|
| RFQ/commercial lead + system lead | Agree the scope to quote and what a first PO would cover: feasibility/design work, prototypes and characterization, with explicit review points and assumptions |
| System lead + RFQ lead | Identify the technical contact and include the system lead directly in supplier discussions; establish how technical changes and decisions are recorded |
| RF/system | Identify any firm gain, beamwidth, match, isolation or efficiency limits hidden among the proposed targets. Keep polarization explicitly open if horizontal versus vertical has not been chosen |
| Product/RF | Provide quantities, TX power/duty and relevant installation/environmental conditions, or identify them as quotation assumptions. Refer to the separately defined mechanical interfaces |
| RFQ lead + system lead | Agree the issue revision and attachments: technical description, reference TX excitation and applicable interface material; keep the old presentation and this internal review out of the supplier specification set |

### During preliminary design, before freezing targets and fabrication

These items need supplier evidence or further system work. Assign owners and
plan the review now, then resolve them through the development phase.

| Owner | Decision or evidence |
|---|---|
| Supplier + RF/system | Establish equal-power feed feasibility, proposed geometry adjustments, realized losses, port mapping and RF reference planes |
| System/processing | Define useful range/angle region, target-strength assumptions, wrong-cell publication probability, resolution latency and calibration strategy sufficiently to set acceptance targets |
| Supplier + system lead | Assess the actual TX/RX patterns for both variants and both MIMO splits; agree any target changes and the numerical verification criteria |
| Supplier + RF/system | Agree pattern-data conventions, measurement coverage/uncertainty, variation assessment and a practical production calibration/test approach |

### At prototype delivery

Review the as-built and measured data against the agreed criteria, resolve
simulation-to-measurement differences and remaining data gaps, and incorporate
the realized responses and uncertainty into the system models and SP
implementation. Section 5 and Appendix C of the technical description define
the intended handover data.

The highest-value next analysis is a mode-correct assessment of the first
supplier patterns: actual half-aperture grouping, both RX variants, off-axis
competitors and dictionary mismatch. A supplier-neutral reference evaluator
would make later iterations and acceptance reproducible. The current scripts
are useful building blocks but do not yet implement that complete evaluation.
Do not infer selected-interlace performance from the old four-quadrant CPI
results or from the main script's unstaggered rectangular baseline.

The external literature also treats transmit grouping, coherent gain and
waveform diversity jointly; see Li, Vorobyov and Koivunen,
[Ambiguity Function of the Transmit Beamspace-Based MIMO Radar](https://arxiv.org/abs/1503.06614).
The request for defined channel phase references and de-embedding is consistent
with NIST's experimental work on
[MIMO channel characterization at 75 GHz](https://www.nist.gov/publications/channel-de-embedding-and-measurement-system-characterization-mimo-75-ghz).
These support the evaluation approach, not any Lannik Psi numerical target.

## Numerical checks performed on 2026-09-16

Using `load_tx_antenna`, `split_tx_quadrants` and `quadrant_fields_uv`, summed
the appropriate quadrant fields into left/right and up/down pairs and
recomputed squared normalized correlation. At the precise 77 GHz alias edges:

| Check | Recomputed rho [dB] |
|---|---:|
| Horizontal pair, left/right mode | -3.1360 |
| Large vertical pair, up/down mode | -29.3153 |
| Small vertical pair, up/down mode | -3.1360 |
| Boresight to large vertical replica, up/down mode (diagnostic only) | -8.1951 |

Verified the H/4 coordinate table against `staggered_layout(0.25)` and the
small layout against `RX_SQUARE_LAYOUT`. Calculated alias coordinates at 76,
76.5 and 77 GHz with the supplied dimensions. Holding the excitation weights
fixed and scaling only free-space propagation phase preserves these
correlations at the corresponding frequency-scaled alias pairs; this is a
geometric check and supplies no evidence about physical feed dispersion.

The existing study-local resolution and stagger-amount tests passed: 12 tests
across `test_rx_resolution_experiment.py` and
`test_rx_stagger_amount_experiment.py`. No model or processing code was changed.
