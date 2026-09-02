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
- The presentation and table depict or label eight TX subapertures, but it is
  not yet confirmed that these groups are the actual physical MMIC-channel
  boundaries.

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
- Mutual coupling, feed-network loss, embedded element patterns, and installed
  antenna effects are not represented.

The modeled boresight array-factor contribution is approximately 17.05 dB,
giving 23.5 dBi after adding the inferred radiator gain. The principal-plane
3 dB beamwidths are approximately 12.5°.

### RX

**Source/model interpretation:**

- Each RX channel is a uniform 4 × 8 radiator subarray.
- The eight channel centroids form a 4 × 2 uniform rectangular array.
- Channel spacing is approximately 2.42 wavelengths horizontally and 4.83
  wavelengths vertically at 77 GHz.

**Current model:**

- The 4 × 8 radiator aperture supplies the element/subarray pattern.
- A steerable 4 × 2 array factor is applied on top of that pattern.
- The ideal coherent gain of the eight RX channels remains in processing.
- Effective boresight RX gain is approximately 30.5 dBi: 21.5 dBi subarray gain
  plus `10 log10(8)` coherent gain.
- Individual formed-beam 3 dB widths are approximately 5.2° in azimuth and
  elevation.

The RX channel-array steering vector is periodic in u and v. At 77 GHz the
periods implied by the supplied channel spacings are approximately:

- 0.4140 in u.
- 0.2070 in v.

The boresight-centered fundamental steering cell therefore spans approximately
`u = ±0.2070` and `v = ±0.1035`. In the principal azimuth and elevation cuts,
these edges occur at approximately ±11.9° and ±5.9°, respectively. Steering to
a point outside this cell exactly duplicates an array-factor steering vector
inside it, modulo an integer period. The complete RX gain does not repeat
exactly because the 4 × 8 subarray element pattern still weights each replica.

The current model forms 64 RX beams:

- An 8 × 4 primary grid covering one fundamental u/v cell.
- A second 8 × 4 grid offset by half a cell in both u and v.
- Exact spacings of approximately 0.0517 in both u and v, corresponding to
  2.97° at boresight. The spacing divides each array-factor period into an
  integer number of cells, so the grid wraps without a seam.

`MultiBeamUniformArrayAntenna` returns the best-gain beam at each direction.
This is an optimistic envelope: it does not yet include multiple-testing Pfa,
correlated beam noise, computational limits, or scheduling cost.

The same 64-beam set is now used for every calculation. Its periodic aliases
repeat its best array-factor sampling over the visible u/v disk. This removes
the former distinction between the product and full-visible beam sets.

The earlier 2305-beam grid was not made entirely of exact duplicates: its
`sin(3°)` spacing did not divide the array-factor periods, so reducing all its
points modulo those periods accidentally produced a much denser set of unique
steering vectors. The new 64-beam result is therefore close to, but not exactly
the same as, that near-continuous-steering result. In ±15° principal cuts, the
largest observed reduction relative to the former grid is approximately 0.51
dB RX gain / 2.9% range horizontally, 0.47 dB / 2.7% vertically, and 0.32 dB /
1.8% diagonally. Boresight is unchanged.

## Range checkpoints

All entries are boresight results for the inherited scenario. Values are
Pd=50%/90% and Pacq=50%/90% respectively.

| Model stage | Pd range | Pacq range |
|---|---:|---:|
| June config-3 placeholder model | 994 / 614 m | 1474 / 1372 m |
| Proposed TX aperture, old RX placeholder | 859 / 531 m | 1264 / 1174 m |
| Proposed TX and RX aperture models | 1114 / 688 m | 1662 / 1549 m |

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

**Result:** The 4 × 2 channel array alone cannot distinguish directions that
differ by integer multiples of 0.4140 in u or 0.2070 in v. A detection in an
outer periodic replica has an exactly equivalent steering-vector direction in
the fundamental cell in a single RX measurement.

**Interpretation:** The subarray and TX patterns change detection strength but
do not remove the channel-array ambiguity. If useful range performance is
confined to the principal region, this may be acceptable operationally. If
targets can be detected in a replicated region, resolving the direction would
require information beyond this single narrowband channel-array measurement,
such as a different physical baseline or frequency-dependent/multi-mode
diversity. The current study does not model such disambiguation.

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
  weighted by the single-subarray pattern. Its narrower vertical pattern is a
  limiting contribution.
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

## Critical open question: physical TX excitation normalization

### What the current interpretation says

Treating `abs(w)**2` as radiator power and treating the apparent eight groups in
the supplied material as the physical MMIC-channel subarrays, the supplied TX
weights allocate power as follows:

| TX subarrays | Power per subarray | Share per subarray | Relative to equal 1/8 share |
|---|---:|---:|---:|
| Outer: 1, 4, 5, 8 | 2.135 | 3.89% | -5.07 dB |
| Inner: 2, 3, 6, 7 | 11.583 | 21.11% | +2.28 dB |

The inner four subarrays therefore carry 84.4% of the modeled aperture power;
the outer four carry 15.6%. Each inner subarray has 7.34 dB more modeled power
than each outer subarray.

### Design expectation to verify

The MMIC is expected to deliver equal power to all eight TX channels, without
TX backoff. The feed was described as redistributing power within each
subarray, rather than achieving taper through attenuation.

Under an uncoupled, identical-radiator model, a lossless feed confined to one
subarray can redistribute its radiator amplitudes but cannot change that
subarray's total `sum(abs(w)**2)`. With the apparent grouping in column 6, the
supplied globally tapered weights are therefore not directly compatible with
eight independent, equal-power, lossless subarray feeds. If those labels are
only conceptual and the physical partitions instead contain approximately
equal integrated aperture power, this apparent incompatibility may disappear.

Possible explanations—not conclusions—include:

- The illustrated subaperture boundaries and/or grouping column are conceptual
  rather than the actual feed geometry. The physical inner subapertures could be
  narrower than the outer ones, with a boundary chosen near the 50% excitation
  level so that equal channel powers produce the desired whole-aperture taper.
- The excitation table was intended as a desired continuous distribution over
  the complete TX aperture for the antenna supplier, not as a definition of the
  physical subaperture geometry or channel mapping.
- The outer subarray networks attenuate, dissipate, or reflect excess power.
- Excess power is radiated into other directions, modes, or polarization.
- Power can cross nominal subarray boundaries.
- The table contains desired aperture-field weights rather than literal
  radiator currents or feed voltages.
- Mutual coupling or embedded element behavior invalidates the simple
  `sum(abs(w)**2)` channel-power interpretation.
- A per-subarray normalization factor is omitted from the table.

If the inner channels define full available power and the outer channels follow
the supplied relative levels, the desired aperture field uses the equivalent of
approximately 4.74 full-power channels. Relative to eight full-power channels,
that is a 2.28 dB implementation loss and approximately 12% range loss. This is
only a diagnostic interpretation, not a product result.

Separately normalizing every subarray to equal power while retaining its
internal relative weights gives an illustrative model with approximately:

- 22.83 dBi boresight gain using the same inferred radiator gain.
- 14.95° horizontal 3 dB beamwidth.
- 12.55° vertical 3 dB beamwidth.

That aperture no longer has the globally supplied Taylor excitation, and the
inferred radiator gain may not remain appropriate.

### Questions for the antenna designer

1. What exactly is column 5 of the `.mat` table: port voltage, radiator current,
   field contribution, or a normalized desired excitation?
2. Does the last column (column 6) represent the actual physical mapping from
   radiators to MMIC channels, or only a conceptual subaperture grouping?
3. Do the illustrated subaperture boundaries represent the actual physical
   mapping from radiators to the eight MMIC channels?
4. Are the inner physical subapertures narrower than the outer ones, perhaps
   with boundaries chosen near the 50% excitation level?
5. Was the table primarily intended to specify a desired excitation distribution
   over the whole antenna to the antenna supplier rather than the physical feed
   geometry?
6. Are weights normalized globally or independently within each TX subarray?
7. Is equal power delivered to and accepted by all eight subarray feed networks?
8. Can power move between subarrays, or only within one subarray?
9. How is the within-subarray amplitude taper physically produced?
10. What happens to power that does not appear in the desired outer-subarray
   aperture field?
11. Does the antenna analysis include mutual coupling, feed loss, mismatch, and
   radiation efficiency?
12. Is the presentation's approximately 23.5 dBi value directivity, gain, or
   realized gain, and what input-power reference was used?

The actual radiator-to-channel geometry is required before TX-channel phase
offsets can be modeled credibly for steering or defocusing. The apparent groups
in the current files should not be used for that purpose without confirmation.

No TX normalization change should be treated as authoritative until these
questions are resolved.

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

This decomposition cannot be finalized until the physical meaning and
normalization of the supplied TX excitations are clarified.

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
- Acceptable angular-alias region and whether detections outside the RX
  principal steering cell must be suppressed or disambiguated.
- Acceptable loss of long-range boresight performance in exchange for angular
  coverage.
- Practical number of RX beams and TX modes supported by signal processing.

## Known model limitations

- TX gain is calibrated using an inferred constant radiator gain rather than a
  controlled realized-gain model.
- TX power normalization does not enforce independent equal-power subarrays.
- No mutual coupling, feed-network efficiency, mismatch, radome, or installed
  element patterns.
- No phase noise or clutter.
- Best-over-RX-beams detection ignores beam correlation and multiple-testing
  Pfa.
- RX angle estimates are ambiguous between periodic channel-array replicas;
  no disambiguation mechanism is modeled.
- Current Pacq is evaluated only for the inherited boresight radial approach.
- Static directional coverage currently shows Pd only; Pacq requires an
  explicit trajectory and revisit schedule.
- No TX-mode timing, waveform switching, scheduler, or tracker model.
- Far-out sidelobe and grating-lobe coverage should not be interpreted as a
  complete physical prediction.

## Candidate next steps

No order is implied; requirements and the TX clarification should drive the
choice.

1. Clarify TX excitation normalization, feed topology, and the meaning of the
   presentation gain with the antenna designer.
2. Write a small set of acquisition and track-maintenance use cases and coverage
   objectives.
3. Decide whether the next analysis should focus on physical antenna tapering,
   TX phase-mode feasibility, waveform/resource trades, or tracking metrics.
4. If justified, introduce an explicit per-subarray TX model with independently
   represented internal weights, channel powers, and phase offsets.
5. Derive an ideal TX pattern from one or more desired Cartesian coverage
   boundaries before optimizing physical weights.
6. Evaluate optimistic envelopes of a few TX phase modes before adding schedule
   and revisit penalties.
7. Add Pacq or track-maintenance coverage only after the relevant trajectory and
   scheduling assumptions are defined.

## Key generated figures

- `pd_pacq_vs_range.png` — inherited boresight Pd/Pacq baseline.
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
