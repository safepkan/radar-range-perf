# Lannik Psi system-design working notes

These notes keep the Lannik Psi design study on track. The study is doing
groundwork for the system design; additions to the general `radarperf` toolbox
are supporting work, not the main subject of this document.

This is a living engineering notebook and possible source for a later report or
design document. It is deliberately not a transcript. Numerical configuration
in [`lannik_psi.py`](lannik_psi.py) is authoritative when this document and the
code differ.

Last substantial update: 2026-09-03.

## Status labels

The following labels are used to keep different kinds of information separate:

- **Source fact** — directly present in supplied data or controlled product
  information.
- **Design expectation** — believed to describe the intended implementation,
  but still worth confirming.
- **Model assumption** — chosen for the present analysis; not necessarily a
  product fact.
- **Result** — produced by the current model under its stated assumptions.
- **Open question** — needs clarification, a requirement, or further analysis.
- **Design idea** — a possible direction, not a decision.

## Purpose and current phase

The immediate goals are to:

1. Establish a reproducible range-performance baseline carried forward from
   config 3 of the 2026-06-22 comparison.
2. Replace placeholder antenna gains with models that represent the proposed TX
   and RX apertures and their directional behavior.
3. Understand what limits useful coverage before optimizing antenna weights,
   waveforms, beam schedules, or tracking behavior.
4. Determine whether track-directed MIMO can resolve RX channel-array aliases
   well enough to retain the larger RX aperture and its gain.

The study is still exploratory. Requirements, operating modes, angular coverage
objectives, and acquisition-versus-tracking use cases are not yet sufficiently
defined to select an antenna or scheduling architecture.

## Sources and reproduction

Supplied antenna material is archived in [`inputs/`](inputs/):

- `Lannik_Psi_Large_MP_antenna_and_SP.pdf`
- `antenna_arr_77_TX_rev_A.mat`
- `antenna_arr_77_RX_rev_A.mat`
- `main_read.m`

Run the complete study from the repository root:

```text
venv/bin/python studies/2026-09-02_lannik-psi/lannik_psi.py
```

Run the separate idealized four-quadrant MIMO ambiguity experiment with:

```text
venv/bin/python studies/2026-09-02_lannik-psi/quadrant_mimo.py
```

Its architectural rationale, results and follow-up questions are maintained in
the dedicated [`MIMO.md`](MIMO.md) note.

Working figures are written to [`generated/`](generated/) and are intentionally
not treated as reviewed deliverables.

## Current evaluation baseline

### Scenario

**Model assumptions** inherited from the June comparison:

- Target: 1 m² RCS, Swerling 1.
- Initial boresight study: radial approach closing at 15 m/s.
- Frame rate: 20 Hz.
- Confirmation: sliding 2-of-3.
- Pfa: `1e-6`.
- Free-space propagation.
- No clutter or phase noise.

### Front end and waveform

**Current model:**

- CTRX8188F, 8 TX and 8 RX channels.
- 14.5 dBm nominal power per active TX channel.
- 10.2 dB RX noise figure.
- Center frequency: 77 GHz.
- 1024 samples × 512 chirps at 50 MHz.
- Assumed chirp slope: 2 MHz/µs.
- Range resolution: approximately 3.66 m.
- Maximum unambiguous range: approximately 1874 m.

The chirp slope was not supplied by the source comparison. It is currently
chosen only to keep the unambiguous range beyond the relevant detection range;
boresight SNR is independent of it in this model.

## Current antenna model

### TX

**Source representation:**

- The supplied data describes 256 radiators on a 16 × 16 rectangular grid.
- The table supplies a complex excitation for every radiator.
- The excitation is now understood primarily as the desired distribution over
  the complete aperture for the antenna supplier. The presentation's apparent
  eight equal subapertures and the table's group labels should not be treated as
  authoritative physical MMIC-port boundaries.

**Result:** The modeled pattern agrees visually with the TX plots in the
presentation.

**Current model assumptions:**

- The complete 16 × 16 aperture is represented by
  `RectangularArrayAntenna`.
- The supplied complex excitations are treated as relative radiator weights.
- Array-factor power is normalized globally by `sum(abs(w)**2)`, so global
  scaling of all weights has no effect and the taper redistributes a fixed
  total aperture power.
- A constant 6.45 dBi radiator gain is inferred so that the supplied taper gives
  approximately 23.5 dBi boresight gain.
- Processing adds `10 log10(8)` for the total power of eight active TX channels,
  but does not add another ideal TX-array directivity term.
- The model assumes all eight ports contribute equal full power, but does not
  represent the intended two-equal-power-feeds-per-quadrant partition.
- Mutual coupling, feed-network loss, embedded element patterns, and installed
  antenna effects are not represented.

The modeled boresight array-factor contribution is approximately 17.05 dB,
giving 23.5 dBi after adding the inferred radiator gain. The principal-plane
3 dB beamwidths are approximately 12.5°.

### RX

**Supplied reference geometry:**

- Each RX channel is a uniform 4 × 8 radiator subarray.
- The eight channel centroids form a 4 × 2 uniform rectangular array.
- The corresponding subarray extents and densely packed channel spacings are
  approximately 2.42 wavelengths horizontally and 4.83 wavelengths vertically
  at 77 GHz.

**Current computational baseline:**

- Each channel is an analytical, uniformly illuminated rectangular aperture.
- The subarray width remains 9.41 mm (2.42 wavelengths), while its height is
  reduced from 18.81 mm to 9.41 mm, making the subarray square.
- The default 4 × 2 channel layout is packed without gaps, giving a complete RX
  extent of 37.62 × 18.81 mm. The layout is parametrized and can instead be
  changed to 2 × 4 or given explicit larger channel spacings. With square,
  densely packed subarrays, 2 × 4 would rotate the RX footprint to 18.81 ×
  37.62 mm and may reduce the required width of the combined TX/RX package.
- The analytical aperture efficiency is 0.963. This is calibrated so that the
  original 9.41 × 18.81 mm aperture reproduces the previous 21.50 dBi
  32-radiator model; it is a modeling calibration, not a measured efficiency.
- The ideal coherent gain of the eight RX channels remains in processing.
- The square subarray gain is approximately 18.5 dBi. Effective boresight RX
  gain is approximately 27.5 dBi after `10 log10(8)` coherent gain.
- With the 4 × 2 layout, an individual formed beam is approximately 5.2° wide
  in azimuth and 10.5° in elevation.

This square layout remains the configuration used by `lannik_psi.py`; it is no
longer the only leading physical-design candidate. Preliminary interlaced-MIMO
results make the supplied 2.42λ × 4.83λ rectangle and intermediate heights
viable again because their aliases may be resolved in signal processing while
retaining more RX aperture gain.

Swapping 4 × 2 to 2 × 4 does not change the principal-cell extents or the
square-subarray envelope. It rotates the individual channel-array beamwidths
and the small residual finite-grid scalloping between u and v; with sufficiently
dense best-beam coverage, the resulting coverage envelope is effectively the
same apart from that ripple.

The RX channel-array steering vector is periodic in u and v. At 77 GHz the
periods with the square, densely packed subarrays are approximately:

- 0.4140 in u.
- 0.4140 in v.

The boresight-centered fundamental steering cell therefore spans approximately
`u = ±0.2070` and `v = ±0.2070`. In both principal cuts these edges occur at
approximately ±11.9°, outside the TX half-power points at approximately ±6.25°.
The TX principal-cut gain is about 11 dB below boresight at the new RX cell
edges. Steering outside this cell duplicates an array-factor steering vector
inside it, modulo an integer period. The complete RX gain does not repeat
exactly because the subarray pattern still weights each replica.

The current model forms 128 RX beams:

- An 8 × 8 primary grid covering one fundamental u/v cell.
- A second 8 × 8 grid offset by half a cell in both u and v.
- Exact spacings of approximately 0.0517 in both u and v, corresponding to
  2.97° at boresight. The spacing divides each array-factor period into an
  integer number of cells, so the grid wraps without a seam.

`MultiBeamUniformArrayAntenna` returns the best-gain beam at each direction.
This is an optimistic envelope: it does not yet include multiple-testing Pfa,
correlated beam noise, computational limits, or scheduling cost.

The same 128-beam set is used for every calculation. Its periodic aliases
repeat its best array-factor sampling over the visible u/v disk. This removes
the former distinction between the product and full-visible beam sets.

The earlier 2305-beam experiment remains useful historical context: because its
`sin(3°)` spacing did not divide the array-factor periods, it accidentally
provided a much denser set of unique steering vectors when reduced modulo the
periods. It should not be compared numerically with the present result without
also accounting for the changed subarray geometry.

## Range checkpoints

All entries are boresight results for the inherited scenario. Values are
Pd=50%/90% and Pacq=50%/90% respectively.

| Model stage | Pd range | Pacq range |
|---|---:|---:|
| June config-3 placeholder model | 994 / 614 m | 1474 / 1372 m |
| Proposed TX aperture, old RX placeholder | 859 / 531 m | 1264 / 1174 m |
| Proposed TX and supplied-size RX aperture | 1114 / 688 m | 1662 / 1549 m |
| Square RX subarray first-cut candidate | 937 / 578 m | 1384 / 1288 m |

Adding multiple RX look directions does not change the boresight checkpoints;
it changes off-boresight coverage.

## Main results and current conclusions

### RX beam spacing

**Result:** Within one fundamental steering cell, the 128-beam interleaved RX
grid has a worst sampled beam-straddling loss of approximately 0.30 dB. In a
free-space radar equation this corresponds to approximately 1.7% range loss.

**Interpretation:** The chosen grid samples every distinct array-factor
steering vector at the desired density. Adding nominal beam directions in
neighboring cells would only duplicate these weights; 128 beams are sufficient
to reproduce the same periodic best-beam array-factor envelope over all visible
directions.

### RX angular ambiguity

**Requirement:** RX ambiguities within the useful detection region must either
be prevented by antenna geometry or resolved with sufficient confidence before
an unambiguous angle is published.

**Result:** The square-subarray channel array alone cannot distinguish
directions that differ by integer multiples of 0.4140 in either u or v. In a
single RX measurement, a detection in an outer periodic replica has an exactly
equivalent steering-vector direction in the fundamental cell.

**Geometry-only option:** Reducing the subarray height from 4.83 to 2.42
wavelengths moves the vertical principal-region edge from ±5.9° to ±11.9°.
The current square candidate therefore puts both u and v edges well outside the
TX 3 dB region. The subarray and TX patterns reduce detection strength in
replicated regions but do not mathematically remove the channel-array
ambiguity. Residual sidelobe detections at sufficiently short range remain a
later problem.

**Signal-processing option:** Interlaced MIMO can distinguish periodic RX
aliases through the complex TX-subaperture signatures. Gain/RCS plausibility,
tracker priors and a guard-channel response may supply additional evidence.
This option may permit the larger supplied-height RX subarrays to be retained.

### MIMO-assisted ambiguity resolution

**Current architectural option:** Retain coherent TX for sensitivity and use
occasional four-quadrant MIMO measurements to resolve the discrete RX ambiguity
cell. The tracker can maintain several hypotheses, accumulate evidence over
multiple MIMO updates and apply the resolved cell to intervening coherent
measurements.

The initial ideal experiment is promising for both RX candidates. With the
2.42λ square subarrays, 99% binary resolution at a principal edge reaches
approximately 253/407/541 m after one/two/four MIMO updates. With the supplied
2.42λ × 4.83λ rectangle, the corresponding nominal vertical-edge ranges are
approximately 421/673/884 m, while retaining 3 dB more RX gain. The square is
therefore still the main script's computational baseline, not a selected
physical design; MIMO has reopened the supplied-height rectangle and
intermediate heights as viable candidates.

The experiment began by treating MIMO as an independent `Pfa=1e-6` detector
with the existing waveform. A more natural product use is a track-directed
ambiguity measurement with range/Doppler gating, soft cell likelihoods,
adaptive scheduling and potentially a different waveform. Pattern/calibration
tolerance and the complete set of aliases remain to be studied.

See the dedicated [MIMO ambiguity-resolution note](MIMO.md) for the model,
results, waveform and tracker ideas, calibration questions, eight-TX extension,
figures and next steps.

### Static directional Pd coverage

Single-scan Pd is plotted in horizontal, vertical, and 45° diagonal planes. Each
figure contains:

- A polar slant-range/signed-angle view.
- A Cartesian downrange/transverse-offset view.
- Filled Pd plus 50% and 90% contours.

The diagonal plane is defined by `u = v = sin(theta) / sqrt(2)`.

For the current constant-RCS, free-space, noise-limited model, a fixed-Pd range
boundary follows

```text
R_Pd(theta) = R_Pd(0) * 10**(
    (G_two_way(theta) - G_two_way(0)) / 40
)
```

**Results:**

- The 128-beam grid leaves visible but modest inter-beam scalloping, repeated
  periodically across visible u/v space.
- Explicitly steering additional beams outside the fundamental cell would not
  improve this envelope because those steering vectors are duplicates.
- The effective best-beam RX envelope is the periodic array-factor ripple
  weighted by the square single-subarray pattern. The former narrow vertical
  subarray limitation has been removed in this first-cut candidate.
- The remaining angular coverage restriction follows the TX and RX subarray
  patterns. Some close-range horizontal/vertical fine structure follows TX
  sidelobes.
- At fixed transverse offset, TX/two-way gain can fall by more than the `R^-4`
  improvement obtained by approaching the radar. The useful short-range
  coverage therefore resembles a geometrically transformed two-way beamshape.

**Conclusion:** Under the current assumptions, additional RX beam coverage is
not the main lever for increasing short-range angular coverage. TX illumination
is the dominant limitation.

Far-out sidelobes should not be treated as installed-antenna predictions because
the TX radiator pattern is constant and coupling, radome, vehicle installation,
polarization, clutter, and phase noise are absent.

## TX feed realization and remaining uncertainty

### Current design direction

**Design expectation:** All eight MMIC TX ports operate at equal full power;
there is no port backoff and the desired aperture taper must not be produced by
dissipative attenuation. The antenna supplier will receive a specification of
the desired excitation over the complete aperture and will perform the detailed
feed and radiator design.

The main implementation direction is now:

- Divide the TX aperture into four quadrants.
- Partition each quadrant's prescribed excitation into two parts with equal
  integrated power.
- Feed those two parts from two independent full-power MMIC TX ports.
- Use the passive antenna/feed geometry to distribute each port's power into
  the required aperture field.

The supplied excitation table should therefore be treated as the desired
whole-aperture distribution, not as authoritative physical eight-port
subarray boundaries. In particular, the last column and the illustrated equal
subapertures remain misleading if interpreted as the final feed partition.

The current TX model is compatible with the intended total-power accounting:
it normalizes the complete excitation pattern to fixed total aperture power and
processing adds the power of eight equal active TX ports. It does not yet prove
that the desired field can be partitioned into eight equal-power, independently
fed, physically realizable regions without material feed loss or pattern error.

### Alternative: combine pairs of MMIC ports

Combining two TX outputs and then feeding one quadrant was discussed with
Infineon. The reported response was that they knew of no other implementation
doing this, but expected that it would probably work. This is useful evidence
that the idea is not obviously invalid, but it is not yet a sufficiently firm
device-level commitment to make it a low-risk product direction.

This alternative also introduces substantial implementation work around port
isolation, phase/amplitude balance, mismatch behavior, startup/shutdown states,
load-pull/stability, thermal behavior, and qualification. It is therefore not
the main direction at present, though the original correspondence and chipset
documentation may still be worth reviewing if the split-quadrant solution
proves impractical.

### Remaining questions

1. Can the antenna supplier partition each desired quadrant distribution into
   two equal-power feeds while preserving the required complete-aperture field?
2. What realized gain, feed loss, amplitude/phase tolerance, and pattern error
   follow from that implementation?
3. What are the actual port-to-aperture boundaries and phase centers? These are
   needed before MMIC-port phase offsets can be modeled credibly for TX steering
   or defocusing.
4. Is Infineon's position on combining TX ports strong enough to support product
   use, and under exactly what combiner, isolation, calibration, mismatch, and
   operating constraints?
5. Is the presentation's approximately 23.5 dBi value directivity, gain, or
   realized gain, and what total input-power reference was used?

The previous calculation based on the apparent eight equal geometric groups
gave very unequal group powers. That remains evidence that those labels should
not be used as the physical port mapping; it is no longer the assumed product
architecture.

## Possible TX and coverage directions

### Shaped TX illumination

**Design idea:** Redistribute some TX energy from boresight toward larger
absolute u and v to improve short-range angular coverage. The analogy is a
classical cosecant-shaped surveillance beam, but Lannik Psi would need symmetric
two-dimensional shaping rather than an asymmetric elevation-only pattern.

For a desired fixed-Pd boundary `R_des(theta)`, the ideal relative TX gain is

```text
G_TX_required(theta) =
    40*log10(R_des(theta) / R_des(0)) - G_RX_relative(theta)
```

in dB under the current free-space assumptions.

Likely tradeoffs include reduced boresight gain and long-range coverage,
increased ripple, and greater sensitivity to physical feed constraints. A
future objective may be a symmetric 2-D flat-top or shoulder-enhanced pattern,
not a literal cosecant-squared pattern.

### TX subarray phase control

**Design idea:** Multiply all radiator weights in TX subarray `c` by a
controllable phase `exp(j*phi_c)`. This preserves the supplied internal subarray
weights while adding seven independent relative phase degrees of freedom.

Potential uses include:

- A phase-only defocused or split-beam short-range mode.
- A small set of conventionally steered modes covering ±u, ±v, and possibly
  diagonal directions.
- Interlacing a long-range mode with one or more short/wide modes.
- Selecting modes cleanly according to situation or track state instead of
  interlacing them continuously.

A single phase-only defocused pattern may suffer ripple, nulls, peak-gain loss,
and grating lobes. A time sequence of efficiently steered beams may be easier to
control, but incurs scheduling and revisit costs.

An explicit future model should separate internal subarray weights, channel
power, and channel phase:

```text
w[c,n] = sqrt(P[c]) * a[c,n] * exp(j*phi[c])
sum_n abs(a[c,n])**2 = 1
```

This decomposition cannot be finalized until the antenna supplier defines the
physical two-port partition inside each quadrant and supplies the resulting
complex embedded subaperture patterns.

## Operating-mode and waveform ideas

These are open design directions, not current requirements.

- Search/acquisition may favor a long CPI and the narrow, high-gain TX mode.
- Track maintenance has a known approximate range and direction and may permit
  directed TX steering, shorter CPIs, tighter processing gates, and adaptive
  revisit.
- A clean switch between long-range and short-range modes may be preferable to
  interlacing them.
- Alternatively, cycling TX directions may trade CPI duration and coherent gain
  for angular coverage and revisit rate.
- Interlaced MIMO may be scheduled sparsely, triggered as a short burst after an
  ambiguous coherent detection, or run as a temporary track-directed mode.
- A track-directed MIMO waveform can use a higher gated Pfa, longer illumination
  and soft subthreshold likelihoods rather than acting as a second independent
  full-search detector. See [`MIMO.md`](MIMO.md).
- Halving range adds 12 dB before beamshape effects, equivalent to a factor of
  16 in coherent integration time. Some short-range margin could therefore fund
  shorter CPIs, more TX directions, faster revisit, or a broader TX pattern.
- Acquisition and track maintenance require different metrics. Track-drop
  probability, missed-update streaks, latency, and estimation covariance may be
  more meaningful than isolated per-CPI Pd for an established track.

Useful architectural separation for future modeling:

1. TX illumination mode and subarray phases.
2. Waveform and CPI configuration.
3. Mode scheduler, dwell allocation, and revisit timing.
4. Detection, acquisition, or track-maintenance objective.

## Requirements and use cases still needed

Before optimizing the antenna or schedule, clarify at least:

- Required acquisition range and angular region.
- Required track-maintenance region.
- Target/RCS cases beyond the current illustrative 1 m² target.
- Acceptable acquisition latency and confirmation behavior.
- Required track update intervals and tolerated missed updates.
- Whether short-range mode selection may assume an established track.
- Maximum number of simultaneous tracks and scheduling/resource constraints.
- Required waveform ambiguity limits and velocity coverage.
- Quantitative outer boundary beyond which RX angular aliases are acceptable,
  expressed in detection range/RCS as well as angle.
- Maximum probability of publishing the wrong ambiguity cell and acceptable
  time from first detection to a resolved angle.
- Whether provisional ambiguous tracks may be retained or published, and what
  posterior confidence is required for unambiguous publication.
- Acceptable loss of long-range boresight performance in exchange for angular
  coverage.
- Practical number of RX beams and TX modes supported by signal processing.

## Known model limitations

- TX gain is calibrated using an inferred constant radiator gain rather than a
  controlled realized-gain model.
- TX power normalization does not enforce or validate the intended partition
  into two equal-power feeds per quadrant.
- The RX subarray is an ideal continuous uniform aperture. Its efficiency is
  calibrated from the earlier discrete model; feed loss, edge effects and
  embedded radiator behavior are not modeled.
- No mutual coupling, feed-network efficiency, mismatch, radome, or installed
  element patterns.
- No phase noise or clutter.
- Best-over-RX-beams detection ignores beam correlation and multiple-testing
  Pfa.
- RX angle estimates remain ambiguous between periodic channel-array replicas;
  the main coherent-TX script moves the square baseline's principal edges
  outside the TX 3 dB mainlobe but does not resolve sidelobe aliases.
- The separate MIMO experiment remains idealized and binary. Its assumptions
  and limitations are maintained in [`MIMO.md`](MIMO.md).
- Current Pacq is evaluated only for the inherited boresight radial approach.
- Static directional coverage currently shows Pd only; Pacq requires an
  explicit trajectory and revisit schedule.
- No TX-mode timing, waveform switching, scheduler, or tracker model.
- Far-out sidelobe and grating-lobe coverage should not be interpreted as a
  complete physical prediction.

## Candidate next steps

No order is implied; requirements and the TX clarification should drive the
choice.

1. Have the antenna supplier assess an equal-power two-feed partition of each
   desired TX quadrant and provide realized-gain/pattern tolerances.
2. Select RX subarray height by comparing coherent coverage, MIMO resolution
   robustness and packaging; retain 4 × 2 versus 2 × 4 as a mechanical choice.
3. Write acquisition, track-maintenance and time-to-unambiguous-publication use
   cases with an allowable wrong-cell probability.
4. Extend the MIMO single-scan analysis to enumerate all plausible aliases and
   combine complex-signature correlation with gain/RCS plausibility and pattern
   uncertainty; see [`MIMO.md`](MIMO.md).
5. Once the physical eight-port split is available, compare coherent,
   four-quadrant MIMO and eight-TX MIMO at equal power, time and processing cost.
6. If justified, introduce an explicit per-subarray TX model with independently
   represented internal weights, channel powers, and phase offsets.
7. Derive an ideal TX pattern from one or more desired Cartesian coverage
   boundaries before optimizing physical weights.
8. Evaluate optimistic envelopes of a few TX phase modes before adding schedule
   and revisit penalties.
9. Add joint acquisition, maintenance and ambiguity-resolution coverage once
   the relevant trajectory, publication and scheduling assumptions are defined.
10. Connect soft ambiguity-cell likelihoods to a small multiple-hypothesis
    tracker model and compare fixed, triggered and adaptive MIMO scheduling.
11. Once the Lannik Psi design settles, promote it to a reusable toolbox-level
   preset while retaining this dated study as the rationale and reproducible
   design history.

## Key generated figures

- `pd_pacq_vs_range.png` — inherited boresight Pd/Pacq baseline.
- `antenna_geometry_excitations.png` — modeled TX radiator amplitudes and
  relative phases beside the RX subarray geometry and channel phase centers.
- `tx_sum_beam_uv.png`, `tx_sum_beam_cuts.png` — proposed TX aperture.
- `rx_boresight_beam_uv.png`, `rx_boresight_beam_cuts.png` — one RX beam.
- `rx_multibeam_grid_uv.png` — 128-beam fundamental-cell grid and straddling
  loss.
- `rx_multibeam_max_uv.png`, `rx_multibeam_max_cuts.png` — best RX beam.
- `two_way_multibeam_detail_uv.png` — detailed two-way pattern in the steering
  region.
- `two_way_multibeam_max_uv.png`, `two_way_multibeam_max_cuts.png` — complete
  best-beam two-way pattern.
- `tx_rx_multibeam_max_cuts.png` — separate TX and best-beam RX contributions
  over the central ±30° principal cuts.
- `multibeam_pd90_range_cuts.png` — range scalloping relative to ideal continuous
  RX steering.
- `pd_coverage_horizontal.png`, `pd_coverage_vertical.png`, and
  `pd_coverage_diagonal.png` — static Pd coverage using the periodic 128-beam RX
  set. Dashed red lines mark the principal-region edges.
- MIMO-specific figures are grouped under `generated/mimo/` and catalogued in
  the dedicated [`MIMO.md`](MIMO.md) note.

## Decision log

- **2026-09-02:** Named the product Lannik Psi and created a clean study based
  on config 3 of the 2026-06-22 comparison.
- **2026-09-02:** Replaced placeholder TX gain with the supplied complete
  16 × 16 complex aperture model.
- **2026-09-02:** Modeled RX as a 4 × 8 radiator subarray under a steerable 4 × 2
  channel URA.
- **2026-09-02:** Initially adopted an 85-beam interleaved RX grid as the
  best-beam baseline; this was an upper bound, not a final SP design.
- **2026-09-02:** Added static single-scan Pd coverage in horizontal, vertical,
  and diagonal planes. Pacq coverage was deferred until trajectories and
  scheduling are defined.
- **2026-09-02:** Initially used a 2305-beam full-visible RX grid for static
  coverage to isolate the TX limitation. It did not materially expand the
  useful envelope.
- **2026-09-02:** Deferred changes to TX power normalization until the physical
  meaning of the supplied excitation data and presentation gain is clarified.
- **2026-09-03:** Replaced both earlier beam sets with one 64-beam periodic
  grid: 8 × 4 samples of the fundamental steering cell plus an equally sized
  half-cell-offset grid. Added principal-region markers to multi-beam pattern,
  range, and coverage plots to expose the associated angular ambiguity.
- **2026-09-03:** Clarified the main TX feed direction: specify the desired
  whole-aperture field to the antenna supplier and split each quadrant into two
  equal-power feeds, using all available power from all eight MMIC ports without
  attenuation. Pairwise TX-port combining remains a higher-risk alternative.
- **2026-09-03:** Made RX subarray extent, channel layout and optional spacings
  explicit study parameters. Adopted a first-cut 2.42 × 2.42 wavelength square
  subarray in a densely packed 4 × 2 layout, moving both principal-region edges
  to ±11.9°. This produces a 128-beam periodic grid with the retained half-cell
  offset.
- **2026-09-03:** Added a separate ideal four-quadrant orthogonal-MIMO
  experiment. Exact prescribed quadrant patterns break many RX aliases, but
  correlation remains strongly direction-dependent and reaches -3.14 dB for
  opposite edges of the current square RX principal cell.
- **2026-09-03:** Added ideal MIMO detection and binary ambiguity-resolution
  range cuts for an illustrative one-in-four interlace. At a current-square
  principal edge, 99% binary resolution reaches approximately 253, 407 and
  541 m after one, two and four independent MIMO updates respectively.
- **2026-09-03:** Swept RX height for the interlaced-MIMO case. The supplied
  4.83λ height is highly favorable in the nominal model: its opposite vertical
  edge signatures correlate by approximately -29.3 dB and reach 99% binary
  resolution at approximately 421/673/884 m after one/two/four updates.
