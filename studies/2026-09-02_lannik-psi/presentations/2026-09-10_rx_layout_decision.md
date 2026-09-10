---
marp: true
paginate: true
theme: default
title: Lannik Psi RX layout decision
style: |
  section { font-size: 24px; }
  table { font-size: 19px; }
  h1 { font-size: 36px; }
---

# Lannik Psi rectangular RX prototype: staggered or not?

Decision brief, 2026-09-10

Patrik Andersson
SafeRadar Research AB

Sources: `studies/2026-09-02_lannik-psi/` (`RX_LAYOUT.md`, `MIMO.md`, `NOTES.md`, `ANTENNA_REQUIREMENTS.md`)

---

# What has to be decided

- Two antenna prototypes planned; the square-subarray 2 × 4 layout is likely fixed
- The rectangular prototype (2.42λ × 4.83λ subarrays, 4 × 2 channels) needs its RX phase-centre layout fixed before ordering:
  - unstaggered URA, or
  - alternating columns displaced vertically ("stagger"), and by how much
- The rectangle keeps 3 dB more RX gain than the square but has closer vertical aliases
- This is a recommendation under uncertainty from an idealized model: fixed 1 m² target, nominal patterns, no tracker, no measured latency

---

# The ambiguity problem

- Eight channel phase centres form a sparse array; the steering vector repeats every 0.414 in u (±11.9°) and 0.207 in v (±5.9°)
- The vertical alias pair sits **inside** the TX 3 dB beam (±6.25°): it affects targets at long range (1 m² detectable beyond 900 m at the edge)
- The horizontal pair sits outside the beam: for a 1 m² target it is a short-range problem (about 550 m at the 10 dB SNR reference); low-Pd tracking and stronger targets extend that region
- A coherent-TX measurement cannot tell a target from its alias by the steering vector at all
- Gain plausibility (RCS ceiling +10 dBsm) protects less than expected: only about ±2° around the horizontal plane, because the *skirt* of the alias lobe becomes admissible before the exact alias does

---

# What MIMO actually does on this antenna

- TX radiator pitch equals RX pitch, so an 8 × 8 TX quadrant is exactly one RX subarray height: **quadrant geometry gives no discrimination**
- The supplied excitation has a quadratic phase (about 180° at edge centres): a defocus that widens the beam from 6.9° to 12.6° (5.3 dB directivity cost) and squints each quadrant beam 6° toward the opposite corner
- That squint is the entire source of the MIMO alias discrimination

| TX quadrant excitation | Vertical edges | Horizontal edges |
|---|---:|---:|
| Nominal (amplitude and phase) | -29.3 dB | -3.1 dB |
| Amplitude taper only | -4.7 dB | -0.04 dB |
| Uniform quadrants | 0.0 dB | -0.6 dB |

MIMO here is a four-squinted-beam comparison, and a property of the TX excitation.

---

# MIMO robustness: fine if the defocus is built, fragile to a different design

| Realized defocus (× prescribed phase) | Vertical margin | Horizontal margin | Beamwidth |
|---:|---:|---:|---:|
| 0.0 (focused) | 6.1 dB | 0.0 dB | 6.9° |
| 0.6 | 17.8 dB | 1.8 dB | 8.2° |
| 1.0 | 29.3 dB | 3.1 dB | 12.6° |
| 1.4 | 17.4 dB | 4.3 dB | 17.6° |

- (Corrected after review: the first sweep scaled wrapped phase; unwrapped now)
- Scaling the amplitude taper between the 0.5 and 2 power keeps the vertical-edge correlation below -18 dB; an uncalibrated 30° upper/lower quadrant phase error still leaves 13 dB vertical margin
- The horizontal edge is the MIMO-limited case, and its margin **scales with the amount of defocus**: an under-realized defocus weakens it
- A spec of gain, beamwidth and sidelobes alone can be met by amplitude-only shaping or a smaller focused aperture, which would leave MIMO with nothing

---

# What a stagger does

- Alternating columns differ by phase 2π·s/H at the old vertical alias; the two column groups give `rho = cos²(π s/H)`
- Our sketch used one radiator pitch (H/8), chosen without analysis

| Offset `s` | Coherent-mode separation `1 - rho` | Horizontal aliases | RX height |
|---|---:|---:|---:|
| 0 (URA) | 0.00 | exact | 37.6 mm |
| H/8, one pitch | 0.15 | exact | 40.0 mm |
| H/4, two pitches | 0.50 | exact | 42.3 mm |
| H/2 | 1.00 | exact | 47.0 mm |

- No change to subarray area, gain, beamwidth or sensitivity envelope
- Horizontal aliases stay exact whatever the offset

---

# Resolution events: coherent frames only, vertical edge, 1 m² target

Wrong-lobe probability (fixed RCS, independent frame noise, forced choice; diagonal competitor family included):

| SNR (range) | RX error | Frames | URA | H/8 | H/4 |
|---|---|---:|---:|---:|---:|
| 10 dB (893 m) | nominal | 4 | 0.50 | 0.071 | 0.0037 |
| 10 dB | 10° random | 4 | 0.50 | 0.099 | 0.0097 |
| 10 dB | +15° column group | 4 | 0.50 | 0.31 | 0.029 |
| 16 dB (632 m) | nominal | 1 | 0.50 | 0.063 | 0.0024 |
| 16 dB | +15° column group | 2 | 0.50 | 0.23 | 0.0024 |

- Four frames are 200 ms at 20 Hz with no mode switch
- H/4 meets 1% with **no MIMO burst** in the nominal and random-error cases; with a +15° systematic column-group error it needs two frames at 632 m and a 1.0 CPI burst after four frames at 893 m. H/8 needs a burst at 893 m in every case and is nearly disabled by the systematic error
- Horizontal-edge and corner events are identical for all three layouts (MIMO needed: 1.5 CPI at 10 dB, 0.375 at 16 dB)
- Promising evidence, **not a resolution-time guarantee**: fixed RCS, forced choice, no motion, finite candidate grids

---

![w:1100](../generated/experimental/on_demand/stagger_amount_vertical_edge.png)

---

# Whole-beam check: strongest competitor per true direction

Within the TX 3 dB region, competitors outside the own lobe needing at most +10 dBsm:

| Layout | Worst coherent competitor | Directions with one ≥ -1 dB | Worst MIMO competitor (separate search) |
|---|---:|---:|---:|
| URA | 0.0 dB | 57% | -10.3 dB |
| H/8 | -0.5 dB | 51% | -10.5 dB |
| H/4 | -2.2 dB | 0% | -11.4 dB |

- H/4 leaves nothing near-exact anywhere in the beam in coherent mode
- The MIMO column is now a separate search over the same admissible competitors (corrected after review; the first version evaluated MIMO only at the strongest coherent competitor). It rises toward the beam edge, about -5 dB at |u| = 0.15; no global MIMO guarantee is claimed

---

![w:1000](../generated/experimental/on_demand/stagger_in_beam_competitors.png)

---

# Layout options (from the requirements draft)

| Option | Subarray height | Stagger | RX height | Vertical edge | `1 - rho` | RX gain |
|---|---:|---:|---:|---:|---:|---:|
| A. URA | 18.81 mm (8 rows) | 0 | 37.6 mm | ±5.9° | 0.00 | 0 dB |
| B. One pitch (our sketch) | 18.81 mm (8 rows) | 2.35 mm | 40.0 mm | ±5.9° | 0.15 | 0 dB |
| C. Two pitches | 18.81 mm (8 rows) | 4.70 mm | 42.3 mm | ±5.9° | 0.50 | 0 dB |
| D. Two pitches, 7 rows | 16.46 mm (7 rows) | 4.70 mm | 37.6 mm | ±6.8° | 0.61 | -0.58 dB |

- D keeps the original 16-row grid, pitch and total height: each column populates 14 of 16 rows, offset two rows between adjacent columns; costs about 3% range
- D is a promising extrapolation: not yet run through the event simulation, and its changed height also moves its aliases relative to the TX pattern
- B gives too little separation to be worth its complexity

---

# Recommendation

**Two-pitch alternating column stagger: option C, with D as a variant to validate. URA as fallback.**

Why:
1. The vertical alias is the operationally important one (in-beam, long range)
2. For a URA, coherent frames carry nothing about it; nearly the whole beam relies on MIMO
3. MIMO's discrimination is a property of the TX defocus, calibration and waveform, not of geometry
4. A two-pitch stagger gives every 20 Hz frame half the separation of an unambiguous measurement, at no gain cost
5. It leaves no near-exact competitor anywhere in the beam
6. Its evidence is RX geometry only, independent of the TX realization

What stays: MIMO for the horizontal family (short range, high SNR) and as fallback, **on demand**, not interlaced. The -3 dB horizontal-edge discrimination from the TX defocus is the binding TX requirement.

Treat ambiguity-resolution latency, calibration tolerance and option D's detailed performance as **validation items, not settled specifications**.

---

# Risks and costs

Stagger:
- Non-separable steering: cost per formed beam unchanged at 8 channels; beam-bank size, search and likelihood updates not yet budgeted (likely manageable). Design bookkeeping: lobes on a sheared lattice, 2-D validation, per-lobe likelihoods in the tracker
- Relative RX channel phase: margin 3.0 dB nominal, 1.9 dB at +15°, zero at +45° systematic column-group error. In the event simulation +15° costs H/4 one extra frame at 632 m and a 1.0 CPI burst at 893 m. ±15° is a proposed calibration target, not demonstrated production robustness
- Option C adds 4.7 mm height; option D costs 0.6 dB

MIMO (unchanged by the layout, but now carrying less of the load):
- Supplier must realize the quadrant squint; intra- and inter-quadrant calibration; waveform orthogonality and its Doppler cost; pattern-dictionary processing

Not yet shown for any layout: slow RCS fluctuation across frames, multi-target association, decision rule with abstention

Fallbacks if MIMO underperforms (ideas, not analysed): quadrant-level TX sequential lobing with the coherent waveform; gain-trajectory evidence from target or platform motion; publish with explicit ambiguity and let higher layers act

---

# Antenna specification: what the supplier must be told

- The four individual TX quadrant patterns are a **requirement**, not a by-product of the sum beam
- Reference excitation to aim for: the supplied amplitude **and** quadratic phase (`antenna_arr_77_TX_rev_A.mat`); any other beam-widening mechanism must be agreed against the metrics below
- Deliverable: complex embedded patterns for each of the 8 TX ports and 8 RX channels, common phase reference, |u|,|v| ≤ 0.6 at 0.005, centre and band-edge frequencies; simulated at review, measured on the prototype
- Acceptance metrics we compute (four-quadrant correlation):

| Direction pair | Requirement | Nominal |
|---|---:|---:|
| Opposite vertical edges (0, ±0.1035) | ≤ -10 dB | -29 dB |
| Opposite horizontal edges (±0.207, 0) | ≤ -2.5 dB | -3.1 dB |
| Boresight vs first vertical replica | ≤ -6 dB | -8.2 dB |

- Stability, not tolerance: static offsets are calibrated; ask for expected inter-quadrant and inter-channel phase variation over temperature
- RX: layout option, phase-centre table, ±0.2 mm positions, identical subarray patterns to 1 dB / 10°

---

# Asks for this meeting

1. Agree the direction: two-pitch stagger (C or D), URA fallback
2. Agree to send the supplier the requirements draft and a shortlist (A, C, D) for **early feedback on obvious issues**, not a full analysis
3. Check the measured per-port patterns of the existing four-quadrant prototype against the quadrant metrics as a first realizability test
4. Confirm the TX excitation is specified deliberately: quadratic defocus or agreed equivalent, quadrant patterns as deliverables
5. Requirements still needed: which alias family drives (long-range vertical vs short-range horizontal), acceptable wrong-cell publication probability, and publishing tracks with explicit ambiguity to higher layers

---

# Backup: reproduction

```text
source venv/bin/activate
python studies/2026-09-02_lannik-psi/rx_layout_experiment.py
python studies/2026-09-02_lannik-psi/rx_resolution_experiment.py
python studies/2026-09-02_lannik-psi/rx_stagger_amount_experiment.py   # about 3 min
python -m pytest studies/2026-09-02_lannik-psi -q
```

Figures under `generated/experimental/` and `generated/experimental/on_demand/`.

Model limits: ideal orthogonal waveforms, exact nominal patterns, fixed 1 m² target known to exist in a gate, independent frame noise, no motion, no tracker, no measured latency; energies are illumination equivalents, not wall-clock time.
