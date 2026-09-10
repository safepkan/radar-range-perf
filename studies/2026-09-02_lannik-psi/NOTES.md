# Lannik Psi system-design working notes

These notes keep the Lannik Psi design study on track. The study is doing
groundwork for the system design; additions to the general `radarperf` toolbox
are supporting work, not the main subject of this document.

This is a living engineering notebook and possible source for a later report or
design document. It is deliberately not a transcript. Numerical configuration
in [`lannik_psi.py`](lannik_psi.py) is authoritative when this document and the
code differ.

Last substantial update: 2026-09-10.

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
4. Develop the track-directed MIMO approach needed to resolve RX channel-array
   aliases while retaining as much RX aperture and gain as practical.

The study is still exploratory. Requirements, operating modes, angular coverage
objectives, and acquisition-versus-tracking use cases are not yet sufficiently
defined to finish the antenna or scheduling architecture. The broad direction
is nevertheless established: the system design will rely on MIMO measurements
to resolve the coherent-mode angular ambiguities.

### End-of-week project status

**Design direction, 2026-09-04:** The project is proceeding on the assumption
that RX ambiguities will be resolved using the MIMO approach developed here.
The present analysis establishes the broad feasibility and identifies the
required architecture, but the waveform, calibration, processing, tracker,
scheduling and confidence details remain design work rather than demonstrated
product performance.

Two antenna prototypes with different RX subarray dimensions are planned.
Candidate square and staggered-rectangle layouts were sketched on 2026-09-08.
The 2026-09-10 meeting decided both: the supplied-size 2.42λ × 4.83λ
rectangular subarrays with a two-pitch (height/4) alternating column stagger,
and the 2.42λ square subarrays rotated to 2 × 4 channels as an unstaggered
URA in a smaller package. The main script's unstaggered rectangular baseline
remains a computational reference for range performance; the staggered
geometry does not change gain or beamwidth.

Once the dimensions are known, the study should gain a simple two-variant
runner that produces directly comparable versions of the existing plots. The
two selected antennas should also be promoted to toolbox-level presets with
names that clearly identify them as the first Lannik Psi prototype antennas.
There is no need to build that infrastructure before the choices are known.

**Decision preparation, 2026-09-09:** The 2026-09-10 meeting is expected to
choose staggered versus unstaggered geometry for the rectangular prototype.
The 2026-09-09 recommendation favored URA for schedule and implementation
simplicity, not because staggering has no useful information. The dedicated
[RX-layout decision note](RX_LAYOUT.md) records costs, potential benefits,
uncertainties and the smallest useful pre-decision checks.

**Pre-meeting update, 2026-09-10:** Two findings qualify that recommendation.
The ideal MIMO alias discrimination is entirely a property of the prescribed
TX defocus phase and the quadrant squint it produces; it is robust to
plausible taper and static phase errors but not to a change of TX excitation.
And the stagger amount dominates the geometry trade: the sketched height/8
offset gives a coherent frame only 0.146 of an unambiguous measurement's
separation at the vertical alias, whereas height/4 gives 0.500 and resolves
the tested vertical-edge events without a MIMO burst within one to four
frames. **Decision, 2026-09-10 meeting:** The rectangular prototype uses the
two-pitch (height/4) stagger with eight-row subarrays (42.3 mm tall; the
margin to the edge allows it). The second prototype is the rotated 2 × 4 square-subarray
URA, whose vertical aliases sit at ±11.9° like its horizontal ones and are a
mid-to-short-range matter. The main remaining work is the TX-side
specification; see [ANTENNA_REQUIREMENTS.md](ANTENNA_REQUIREMENTS.md) and
the decision record in [RX_LAYOUT.md](RX_LAYOUT.md).

**Source fact, 2026-09-10:** The same supplier has already produced a separate
prototype antenna with four-quadrant tapered TX and RX apertures for the
existing 4TX/4RX radars, primarily as a supplier evaluation and for
narrow-beam long-range demonstrations. Its measurements are under review;
nothing worrying has been seen so far. If per-port patterns were measured,
they are the first available check of the supplier's ability to realize a
prescribed amplitude and phase distribution, and of the quadrant-squint
metrics in [ANTENNA_REQUIREMENTS.md](ANTENNA_REQUIREMENTS.md).

## Sources and reproduction

Supplied antenna material is archived in [`inputs/`](inputs/):

- `Lannik_Psi_Large_MP_antenna_and_SP.pdf`
- `antenna_arr_77_TX_rev_A.mat`
- `antenna_arr_77_RX_rev_A.mat`
- `main_read.m`
- `new_aperture_IFX_rot_small_RX.png` — provisional square-subarray layout,
  rotated to a 2 × 4 RX channel arrangement for a more compact PCB.
- `Aperture_large_staggeredered_IFX.png` — internal sketch of the
  supplied-size rectangular layout with alternating vertical channel-pair
  offsets; the one-pitch offset was not chosen by analysis.

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

Run the provisional RX geometry and channel-array-factor comparison with:

```text
venv/bin/python studies/2026-09-02_lannik-psi/rx_layout_experiment.py
```

Its decision context and investigation plan are maintained in
[`RX_LAYOUT.md`](RX_LAYOUT.md). The supplier-facing antenna requirements
draft is [`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md).

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
- The supplied subarray width and height are retained: 9.41 × 18.81 mm, or
  approximately 2.42 × 4.83 wavelengths.
- The default 4 × 2 channel layout is packed without gaps, giving a complete RX
  extent of 37.62 × 37.62 mm. The layout is parametrized and can instead be
  changed to 2 × 4 or given explicit larger channel spacings.
- The analytical aperture efficiency is 0.963. This is calibrated so that the
  original 9.41 × 18.81 mm aperture reproduces the previous 21.50 dBi
  32-radiator model; it is a modeling calibration, not a measured efficiency.
- The ideal coherent gain of the eight RX channels remains in processing.
- The subarray gain is approximately 21.5 dBi. Effective boresight RX gain is
  approximately 30.5 dBi after `10 log10(8)` coherent gain.
- With the 4 × 2 layout, an individual formed beam is approximately 5.2° wide
  in both azimuth and elevation because the complete RX aperture is square.

The supplied rectangle is again the configuration used by `lannik_psi.py`.
Preliminary interlaced-MIMO results suggest that its closer vertical aliases
may be resolvable in signal processing, allowing the extra 3 dB of RX aperture
gain to be retained. The 2.42λ square and intermediate heights remain explicit
comparison candidates rather than discarded designs.

Swapping 4 × 2 to 2 × 4 while retaining the same subarray orientation changes
which phase-center spacing is repeated two or four times, but not the
fundamental-cell extents or the single-subarray envelope. It rotates the
individual channel-array beamwidths and residual finite-grid scalloping.

The RX channel-array steering vector is periodic in u and v. At 77 GHz the
periods with the supplied, densely packed subarrays are approximately:

- 0.4140 in u.
- 0.2070 in v.

The boresight-centered fundamental steering cell therefore spans approximately
`u = ±0.2070` and `v = ±0.1035`. The horizontal edge occurs at approximately
±11.9° and the vertical edge at approximately ±5.9°. The latter is inside the
TX half-power angle of approximately ±6.25°, which is why unresolved vertical
aliases are a concern. Steering outside this cell duplicates an array-factor
steering vector inside it, modulo an integer period. The complete RX gain does
not repeat exactly because the subarray pattern still weights each replica.

The current model forms 64 RX beams:

- An 8 × 4 primary grid covering one fundamental u/v cell.
- A second 8 × 4 grid offset by half a cell in both u and v.
- Exact spacings of approximately 0.0517 in both u and v, corresponding to
  2.97° at boresight. Each spacing divides its array-factor period into an
  integer number of cells, so the grid wraps without a seam.

`MultiBeamUniformArrayAntenna` returns the best-gain beam at each direction.
This is an optimistic envelope: it does not yet include multiple-testing Pfa,
correlated beam noise, computational limits, or scheduling cost.

The same 64-beam set is used for every calculation. Its periodic aliases
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
| Proposed TX and supplied-size RX aperture (current) | 1114 / 688 m | 1662 / 1549 m |
| Square RX subarray first-cut candidate | 937 / 578 m | 1384 / 1288 m |

Adding multiple RX look directions does not change the boresight checkpoints;
it changes off-boresight coverage.

## Main results and current conclusions

### RX beam spacing

**Result:** Within one fundamental steering cell, the 64-beam interleaved RX
grid has a worst sampled beam-straddling loss of approximately 0.70 dB. In a
free-space radar equation this corresponds to approximately 3.9% range loss.

**Interpretation:** The chosen grid samples every distinct array-factor
steering vector at the desired density. Adding nominal beam directions in
neighboring cells would only duplicate these weights; 64 beams are sufficient
to reproduce the same periodic best-beam array-factor envelope over all visible
directions.

### RX angular ambiguity

**Requirement:** RX ambiguities within the useful detection region must either
be prevented by antenna geometry or resolved with sufficient confidence before
an unambiguous angle is published.

**Result:** The supplied-rectangle channel array alone cannot distinguish
directions that differ by integer multiples of 0.4140 in u or 0.2070 in v. In
a single RX measurement, a detection in an outer periodic replica has an
exactly equivalent steering-vector direction in the fundamental cell.

**Geometry-only option:** Reducing the subarray height from 4.83 to 2.42
wavelengths moves the vertical principal-region edge from ±5.9° to ±11.9°.
That square candidate puts both u and v edges well outside the TX 3 dB region,
at the cost of 3 dB boresight RX gain. The subarray and TX patterns reduce
detection strength in replicated regions but do not mathematically remove the
channel-array ambiguity. Residual sidelobe detections at sufficiently short
range remain a later problem.

**Signal-processing option:** Interlaced MIMO can distinguish periodic RX
aliases through the complex TX-subaperture signatures. Gain/RCS plausibility,
tracker priors and a guard-channel response may supply additional evidence.
This option may permit the larger supplied-height RX subarrays to be retained.

### Provisional prototype layouts received 2026-09-08

Two provisional layout sketches have been added as experimental layouts
without changing the main range-performance baseline or promoting either to a
preset. The staggered rectangle is an internal idea whose offset was not
analysed when it was drawn.
The square design now appears likely to be fixed; the active trade for the
second prototype is the rectangular geometry with versus without stagger:

- The 2.42λ square subarrays are arranged as 2 channels horizontally by 4
  vertically. Because the subarrays and dense center spacings are square, the
  principal alias periods remain 0.4140 in both u and v. The rotation changes
  the finite-array beam shape and makes the physical RX/PCB layout narrower;
  this is now the orientation used for the square comparison.
- The 2.42λ × 4.83λ rectangles remain in a 4 × 2 arrangement. Based on the
  sketch, the current model interprets adjacent two-channel columns as
  differing in vertical position by one eighth of a subarray height, with
  symmetric ±height/16 offsets about the array center. This interpretation
  should be confirmed at the design meeting.

The stagger retains exact horizontal aliases and changes the old vertical
alias into a strong near-alias. The -0.69 dB correlation at the old vertical
period must not be interpreted as negligible information: it enables ordinary
coherent-TX updates to contribute to vertical disambiguation, even though its
additional benefit to the nominal opposite-edge MIMO measurement is tiny.
The modeled subarray patterns and ideal coherent peak gain are unchanged.

Detailed geometry, review findings, costs and the decision plan now live in
[`RX_LAYOUT.md`](RX_LAYOUT.md), alongside
[`rx_layout_experiment.py`](rx_layout_experiment.py). The experiment still uses
the old fixed-fold comparison; it does not yet evaluate complete hypothesis
sets or accumulated coherent-plus-MIMO evidence.

### MIMO-assisted ambiguity resolution

**Selected broad system direction:** Retain coherent TX for sensitivity and use
on-demand four-quadrant MIMO measurements to resolve the discrete RX ambiguity
cell. The tracker can maintain several hypotheses, accumulate evidence over
multiple MIMO updates and apply the resolved cell to intervening coherent
measurements. The detailed implementation and achievable performance remain
to be validated.

**Working architecture, 2026-09-09:** Assume sparse scenarios with few tracks.
Confirmed tracks whose prediction/association gates do not overlap their
alias-shifted copies normally need no further MIMO assistance. Request a burst
for unresolved new tracks or when ambiguity confidence is lost. Radar control,
SP and tracking are expected to share the Aurix TC457 platform; tracker requests
and flexible sequencing are assumed feasible, not demonstrated or benchmarked.
CPI reception, processing, switching and burst duration still contribute to
latency. Fixed every-Nth-frame interlacing remains a reference/fallback, not
the likely operational schedule. See [MIMO.md](MIMO.md) for the architecture
and [RX_LAYOUT.md](RX_LAYOUT.md) for the geometry comparison.

The first on-demand resolution-event experiment is now in
[`rx_resolution_experiment.py`](rx_resolution_experiment.py), with results in
[`RX_LAYOUT.md`](RX_LAYOUT.md). It compares fixed-RCS, known-target events,
not a full acquisition/tracker scenario. The tested cases show useful extra
vertical information from the height/8 stagger, but only modest additional
MIMO-energy savings. The follow-up
[`rx_stagger_amount_experiment.py`](rx_stagger_amount_experiment.py) shows
that a height/4 stagger resolves the same vertical-edge events with coherent
frames alone, and that the MIMO discrimination itself originates in the TX
defocus phase rather than the quadrant geometry; see
[`MIMO.md`](MIMO.md).

The initial ideal experiment is promising for both RX candidates. With the
2.42λ square subarrays, 99% binary resolution at a principal edge reaches
approximately 253/407/541 m after one/two/four MIMO updates. With the supplied
2.42λ × 4.83λ rectangle, the corresponding nominal vertical-edge ranges are
approximately 421/673/884 m, while retaining 3 dB more RX gain. The square is
therefore retained as a comparison rather than the main computational
baseline; MIMO has reopened the supplied-height rectangle and intermediate
heights as viable candidates.

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

- The 64-beam grid leaves visible but modest inter-beam scalloping, repeated
  periodically across visible u/v space.
- Explicitly steering additional beams outside the fundamental cell would not
  improve this envelope because those steering vectors are duplicates.
- The effective best-beam RX envelope is the periodic array-factor ripple
  weighted by the rectangular single-subarray pattern. Its narrower vertical
  pattern again limits vertical coverage relative to horizontal coverage.
- The remaining angular coverage restriction follows the TX and RX subarray
  patterns. Some close-range horizontal/vertical fine structure follows TX
  sidelobes.
- At fixed transverse offset, TX/two-way gain can fall by more than the `R^-4`
  improvement obtained by approaching the radar. The useful short-range
  coverage therefore resembles a geometrically transformed two-way beamshape.

**Conclusion:** Under the current assumptions, additional RX beam coverage is
not the main lever for increasing short-range angular coverage. TX illumination
remains the dominant horizontal limitation, while the taller rectangular RX
subarray materially narrows vertical coverage.

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
6. The MIMO ambiguity resolution depends on the four individual quadrant
   patterns, which follow from the prescribed quadratic (defocus) phase. The
   per-port pattern deliverables, acceptance metrics and stability guidance
   to give the supplier are drafted in
   [`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md).

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
  the supplied rectangle's vertical principal edges lie near the TX 3 dB
  mainlobe boundary. The main coherent-TX script does not resolve these aliases.
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
2. Formulate the TX-side specification for the supplier: which quadrant-
   pattern properties are binding, which deliverables verify them, and how
   much of the detailed design is left open; start from
   [`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md).
3. Judge any later change to the decided stagger offset with the
   multi-frame event model and the in-beam competitor map, not only the
   exact reciprocal-cell size.
4. Add a simple study runner for the two decided prototype variants (the
   height/4-staggered rectangle and the rotated square URA) and promote them
   to clearly named toolbox-level Lannik Psi prototype presets; the main
   range model must then support staggered RX phase centres.
5. Write acquisition, track-maintenance and time-to-unambiguous-publication use
   cases with an allowable wrong-cell probability.
6. Extend the MIMO single-scan analysis to enumerate all plausible aliases and
   combine complex-signature correlation with gain/RCS plausibility and pattern
   uncertainty; see [`MIMO.md`](MIMO.md).
7. Once the physical eight-port split is available, compare coherent,
   four-quadrant MIMO and eight-TX MIMO at equal power, time and processing cost.
8. If justified, introduce an explicit per-subarray TX model with independently
   represented internal weights, channel powers, and phase offsets.
9. Derive an ideal TX pattern from one or more desired Cartesian coverage
   boundaries before optimizing physical weights.
10. Evaluate optimistic envelopes of a few TX phase modes before adding schedule
    and revisit penalties.
11. Add joint acquisition, maintenance and ambiguity-resolution coverage once
    the relevant trajectory, publication and scheduling assumptions are defined.
12. Connect soft ambiguity-cell likelihoods to a small multiple-hypothesis
    tracker model and compare fixed, triggered and adaptive MIMO scheduling.
13. Once the Lannik Psi product design settles, promote the final configuration
    to a reusable toolbox-level preset while retaining this dated study as the
    rationale and reproducible design history.

## Key generated figures

- `pd_pacq_vs_range.png` — inherited boresight Pd/Pacq baseline.
- `antenna_geometry_excitations.png` — modeled TX radiator amplitudes and
  relative phases beside the RX subarray geometry and channel phase centers.
- `tx_sum_beam_uv.png`, `tx_sum_beam_cuts.png` — proposed TX aperture.
- `rx_boresight_beam_uv.png`, `rx_boresight_beam_cuts.png` — one RX beam.
- `rx_multibeam_grid_uv.png` — 64-beam fundamental-cell grid and straddling
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
  `pd_coverage_diagonal.png` — static Pd coverage using the periodic 64-beam RX
  set. Dashed red lines mark the principal-region edges.
- MIMO-specific figures are grouped under `generated/mimo/` and catalogued in
  the dedicated [`MIMO.md`](MIMO.md) note.
- `generated/experimental/rx_provisional_geometries.png` — the two provisional
  RX layouts and the unstaggered rectangular reference.
- `generated/experimental/rx_channel_array_factor_uv.png` and
  `rx_channel_array_factor_cuts.png` — channel-array-factor comparison. The cuts
  also overlay the common RX subarray and TX sum-beam gains for context.
- `generated/experimental/rx_rectangle_alias_correlation.png` — direct
  staggered-versus-unstaggered comparison of complete ideal four-quadrant-MIMO
  alias correlation, plus the RX decorrelation contributed by the stagger.
- `generated/experimental/on_demand/resolution_phase_0deg.png` and
  `resolution_phase_10deg.png` — wrong-lobe probability versus extra MIMO
  illumination after a coherent observation, nominal and phase-stress cases.
- `generated/experimental/on_demand/stagger_amount_vertical_edge.png` —
  vertical-edge wrong-lobe probability after one, two and four coherent
  frames plus MIMO illumination, for URA, height/8 and height/4 stagger.

## Decision log

- `generated/experimental/on_demand/stagger_in_beam_competitors.png` —
  strongest gain-admissible alias competitor for every in-beam true
  direction, coherent and MIMO, for the same three layouts.
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
  opposite edges of the then-current square RX principal cell.
- **2026-09-03:** Added ideal MIMO detection and binary ambiguity-resolution
  range cuts for an illustrative one-in-four interlace. At a square-RX
  principal edge, 99% binary resolution reaches approximately 253, 407 and
  541 m after one, two and four independent MIMO updates respectively.
- **2026-09-03:** Swept RX height for the interlaced-MIMO case. The supplied
  4.83λ height is highly favorable in the nominal model: its opposite vertical
  edge signatures correlate by approximately -29.3 dB and reach 99% binary
  resolution at approximately 421/673/884 m after one/two/four updates.
- **2026-09-04:** Restored the supplied 2.42 × 4.83λ rectangular RX subarray as
  the main coherent-study baseline because preliminary track-directed MIMO may
  resolve its vertical aliases while retaining 3 dB more boresight RX gain.
  The periodic beam set is consequently 8 × 4 plus its half-cell-offset copy,
  or 64 beams total. The square geometry remains an explicit comparison.
- **2026-09-04:** Adopted MIMO-assisted ambiguity resolution as the broad system
  direction. Planned two antenna prototypes with different, not-yet-selected RX
  subarray dimensions. Once chosen, both will be supported as comparable study
  variants and named toolbox-level presets for the first Lannik Psi prototype
  antennas.
- **2026-09-08:** Added the provisional rotated 2 × 4 square layout and 4 × 2
  rectangular layout with alternating height/8 vertical column stagger. Kept
  both experimental and left the main range baseline unchanged. Initial
  channel-array-factor analysis finds that the stagger shears the exact alias
  lattice but suppresses the first vertical near-alias by only about 0.69 dB.
- **2026-09-08:** Recorded that the square prototype is likely fixed and
  refocused the active evaluation on staggered versus unstaggered versions of
  the rectangular prototype. Added a direct ideal-MIMO alias-correlation
  comparison for those two geometries.
- **2026-09-09:** Created [`RX_LAYOUT.md`](RX_LAYOUT.md) for the imminent
  rectangular-prototype decision. Recorded the schedule-driven URA preference,
  potential stagger evidence in coherent updates, gain/RCS plausibility and
  fluctuation uncertainty. The geometry decision remains open.
- **2026-09-09:** Adopted on-demand MIMO as the likely scheduling direction for
  sparse scenarios. Assume tracker-to-control requests and flexible sequencing
  can be implemented on the shared platform; evaluate targeted resolution
  events rather than charging a permanent periodically interlaced MIMO cost.
- **2026-09-10:** Traced the MIMO alias discrimination to the prescribed TX
  defocus phase and quadrant squint; uniform quadrants alias exactly with the
  RX lattice. Added a stagger-amount comparison: height/4 resolves the tested
  vertical-edge events in coherent mode alone, height/8 only partly. Proposed
  preferring height/4 if the supplier can accommodate it. Decision pending.
- **2026-09-10, later:** In-beam competitor map confirmed that height/4 leaves
  no near-exact coherent-mode competitor inside the TX 3 dB region, and that
  URA gain plausibility covers only about ±2° around the horizontal plane
  once alias-lobe skirts are admitted. Added equal-total-height variants
  (7 rows, two-pitch stagger) and drafted the supplier-facing
  [`ANTENNA_REQUIREMENTS.md`](ANTENNA_REQUIREMENTS.md).
- **2026-09-10, review:** Corrected a phase-wrapping bug in the defocus
  sensitivity sweep and the in-beam MIMO competitor search; added the
  diagonal competitor family and a systematic RX column-group phase error to
  the multi-frame experiment. The direction stands; frame counts, processing
  cost, calibration tolerance and option D are recorded as validation items.
- **2026-09-10, meeting:** Decided the two first prototypes: the rectangular
  subarrays with a two-pitch (height/4) alternating column stagger, eight
  rows, and the rotated 2 × 4 square-subarray URA. The TX-side specification
  is the main remaining item. This branch is snapshotted to `main` at this
  point; the presentation under `presentations/` is kept as presented.
