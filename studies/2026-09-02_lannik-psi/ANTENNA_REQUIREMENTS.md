# Lannik Psi antenna: requirements and deliverables for the supplier

Draft, 2026-09-10. This is the supplier-facing formulation of what the
Lannik Psi ambiguity-resolution concept needs from the antenna, written so
that it can be worked into the supplier's detailed design and checked
before production release. The engineering rationale is in
[NOTES.md](NOTES.md), [MIMO.md](MIMO.md) and [RX_LAYOUT.md](RX_LAYOUT.md);
this document states requirements, not reasoning. The RX geometries were
fixed at the 2026-09-10 meeting; the open item is the TX-side formulation
(sections 2 and 4), which must ensure the properties relied on without
over-specifying the detailed design.

## 1. Concept summary for the supplier

- One TX aperture of 16 × 16 radiators, fed from eight MMIC ports as four
  independently driven quadrants of two ports each.
- One RX aperture of eight channels, each a uniform rectangular subarray.
  Two first prototypes are ordered with different RX apertures (section 3);
  the TX aperture is the same for both.
- Normal operation transmits the same waveform from all eight TX ports (a
  single sum beam). For ambiguity resolution the radar occasionally transmits
  four mutually orthogonal waveforms, one per TX quadrant, and separates them
  at each RX channel. The angular information in that mode comes from the
  differences between the four quadrant far-field patterns, not from the
  quadrant positions. **The four individual quadrant patterns are therefore
  design requirements, not by-products of the sum beam.**
- The RX channel phase-centre layout is also a requirement in its own right,
  because it determines which directions the eight channels can distinguish.

## 2. TX requirements

### 2.1 Aperture excitation

1. The supplied complex excitation (`antenna_arr_77_TX_rev_A.mat`, amplitude
   **and** phase over the full 16 × 16 aperture) is the reference design to
   aim for. Its phase is a rotationally symmetric quadratic distribution of
   approximately 180° at the edge centres and 360° at the corners. That
   defocus is what produces the 12.6° sum-beam width, and it also squints
   each quadrant pattern by about 6° in both principal planes toward the
   diagonally opposite corner. The squint is required for the MIMO mode.
2. A specification in terms of peak gain, 3 dB beamwidth and sidelobe level
   alone is therefore not sufficient: amplitude-only shaping or a smaller
   focused aperture can meet such a specification and give quadrant
   patterns with no usable difference. The binding requirement is the set of
   quadrant-pattern metrics in section 4.2; the reference excitation is one
   known way to meet them. Any alternative mechanism for the beam width
   (a different phase law, a different aperture size) shall be agreed with
   us before design freeze on the basis of those metrics.
3. All eight ports operate at equal full power; the excitation shall be
   realized by the passive feed geometry without dissipative attenuation.

### 2.2 Port partition

1. The four quadrants are bounded by the aperture's horizontal and vertical
   centre lines (8 × 8 radiators each).
2. Each quadrant is fed by two MMIC ports that are combined coherently by the
   MMIC's amplitude and phase settings. The supplier shall state the nominal
   relative amplitude and phase of the two ports of each quadrant that realize
   the quadrant excitation, and the sensitivity of the quadrant pattern to
   errors in those settings.
3. Port-to-aperture boundaries and the resulting phase centres shall be
   documented.

## 3. RX requirements

### 3.1 Prototype 1: staggered rectangular subarrays (decided 2026-09-10)

1. Eight identical uniform rectangular subarrays of 4 radiators horizontally
   by 8 radiators vertically (9.41 × 18.81 mm at the 2.351 mm pitch),
   arranged as four columns of two channels, densely packed.
2. Adjacent columns are displaced vertically by two radiator pitches
   (s = 4.70 mm), alternating (+s/2, -s/2, +s/2, -s/2), so the aperture is
   37.6 mm wide and 42.3 mm tall. Nominal channel phase centres, x to the
   right and y up, origin at the aperture centre:

| Channel | x [mm] | y [mm] |
|---|---:|---:|
| 1 | -14.11 | -7.05 |
| 2 | -14.11 | +11.76 |
| 3 | -4.70 | -11.76 |
| 4 | -4.70 | +7.05 |
| 5 | +4.70 | -7.05 |
| 6 | +4.70 | +11.76 |
| 7 | +14.11 | -11.76 |
| 8 | +14.11 | +7.05 |

3. Phase-centre position tolerance: ±0.2 mm is sufficient. Inter-channel
   static amplitude and phase offsets are calibrated in the radar and need
   no tight tolerance, but their stability is required (section 5); the
   relative phase between the two column groups in particular must be
   calibratable to about ±15°.

### 3.2 Prototype 2: square subarrays, rotated (decided 2026-09-10)

1. Eight identical uniform square subarrays of 4 × 4 radiators
   (9.41 × 9.41 mm), arranged as two columns of four channels, densely
   packed and unstaggered: the aperture is 18.8 mm wide and 37.6 mm tall,
   for a more compact package. Nominal channel phase centres:

| Channel | x [mm] | y [mm] |
|---|---:|---:|
| 1 | -4.70 | -14.11 |
| 2 | -4.70 | -4.70 |
| 3 | -4.70 | +4.70 |
| 4 | -4.70 | +14.11 |
| 5 | +4.70 | -14.11 |
| 6 | +4.70 | -4.70 |
| 7 | +4.70 | +4.70 |
| 8 | +4.70 | +14.11 |

2. The same tolerance and stability statements as for prototype 1 apply.

### 3.3 Layout options considered (record)

The following options were compared before the decision; option C was
chosen for prototype 1. With W = 9.41 mm subarray width, 2.351 mm radiator
pitch and H = 18.81 mm for eight rows:

| Option | Subarray height | Stagger `s` | Total RX height | Own vertical alias edge | Coherent-mode separation of that alias, `1 - rho` | Subarray gain change |
|---|---:|---:|---:|---:|---:|---:|
| A. Unstaggered URA | 18.81 mm (8 rows) | 0 | 37.6 mm | ±5.9° | 0.00 | 0 dB |
| B. One-pitch stagger (internal sketch) | 18.81 mm (8 rows) | 2.35 mm (H/8) | 40.0 mm | ±5.9° | 0.15 | 0 dB |
| C. Two-pitch stagger | 18.81 mm (8 rows) | 4.70 mm (H/4) | 42.3 mm | ±5.9° | 0.50 | 0 dB |
| D. Two-pitch stagger, 7 rows | 16.46 mm (7 rows) | 4.70 mm (2H/7) | 37.6 mm | ±6.8° | 0.61 | -0.58 dB |

Option C was chosen because the margin to the edge accommodates its height,
which makes option D (seven rows, same total height, -0.6 dB) unnecessary.
B is our own earlier sketch, kept for reference; it gives too little
separation to be worth its complexity. A horizontal row offset of one pitch
(W/4) on top of the column stagger would give the same 0.50 separation for
the horizontal aliases; it is not requested now but may be raised later.

## 4. Deliverables and acceptance metrics

### 4.1 Pattern deliverables

For the design review and again for the measured prototype:

1. Complex embedded far-field voltage patterns (amplitude and phase, with a
   common phase reference across all ports) for each of the eight TX ports
   individually and each of the eight RX channels individually, with the
   other ports terminated or driven as in operation and, where possible,
   including the radome.
2. Grid: direction cosines (u, v) covering at least |u|, |v| ≤ 0.6 at a
   spacing no coarser than 0.005, or the equivalent angular grid.
3. Frequencies: the centre frequency and the extremes of the intended
   operating band.
4. The coherent sum-beam pattern with all eight ports at nominal drive.
5. A tolerance analysis of the metrics in 4.2 over expected manufacturing
   variation (for example a Monte Carlo over feed-line and radiator
   tolerances), and expected variation over temperature.

### 4.2 Acceptance metrics computed from the delivered patterns

Let `E_q(u, v)` be the complex pattern of quadrant `q` (its two ports at
nominal drive) and `rho(d1, d2)` the squared normalized correlation of the
four-component vectors `[E_1 .. E_4]` at directions `d1` and `d2`:

```text
rho(d1, d2) = |sum_q conj(E_q(d1)) E_q(d2)|^2 / (sum_q |E_q(d1)|^2 sum_q |E_q(d2)|^2)
```

Zero decibels means the two directions cannot be told apart in the MIMO
mode. Requirements at 77 GHz, RX-layout independent:

| Direction pair | Requirement | Nominal design value |
|---|---:|---:|
| Opposite vertical edges, (0, +0.1035) and (0, -0.1035) | ≤ -10 dB | -29 dB |
| Opposite horizontal edges, (+0.207, 0) and (-0.207, 0) | ≤ -2.5 dB | -3.1 dB |
| Boresight and first vertical replica, (0, 0) and (0, ±0.207) | ≤ -6 dB | -8.2 dB |

Equivalent descriptive check for the antenna designer: each quadrant's
pattern magnitude peaks about 6° (±1.5°) off boresight in both u and v
toward the diagonally opposite corner; at (0, ±6°) the upper and lower
quadrant responses differ by roughly 7 dB in magnitude and 85° to 90° in
phase.

We will also recompute the complete alias-correlation map over
|u|, |v| ≤ 0.55 with the delivered patterns using our own scripts before
release; the supplier is not asked to compute it.

For the RX channels: the eight embedded subarray patterns shall agree with
each other to within 1 dB and 10° over |u|, |v| ≤ 0.3 after removing the
phase-centre term, so that one common subarray pattern can be assumed.

## 5. Stability

Static per-port and per-channel amplitude and phase offsets are calibrated in
the radar. What must hold without calibration is the pattern shape and the
relative phase between TX quadrants and between RX channels over
temperature, frequency and life. Guidance from the sensitivity analysis: a
systematic uncalibrated phase error of 30° between the upper and lower TX
quadrants still leaves about 13 dB margin at the vertical alias, and a
realized defocus between 0.6 and 1.4 times the prescribed phase leaves more
than 17 dB there. The horizontal-edge margin, however, scales with the
amount of defocus (about 1.8 dB at 0.6 times, 4.3 dB at 1.4 times), which is
why the horizontal-edge metric in section 4.2 must be met rather than only
the beamwidth. For the RX channels, the staggered layout's ambiguity information relies on
the relative phase between the two column groups being known to about ±15°
after calibration; a 45° systematic error would remove it. The supplier is
asked to state the expected inter-quadrant and inter-channel phase variation
over the operating temperature range so that we can confirm it stays well
inside these figures.

## 6. Process

0. Where available, measured per-port patterns of the existing four-quadrant
   prototype antenna (built for the 4TX/4RX radars) are evaluated with the
   metrics of section 4.2 as a first check of realizability.
1. Supplier proposes the detailed design and delivers simulated patterns
   per section 4.1.
2. We evaluate the metrics in section 4.2 and the alias map and either
   accept or request changes.
3. Prototype measurement in the same format; re-evaluation before
   production release.
