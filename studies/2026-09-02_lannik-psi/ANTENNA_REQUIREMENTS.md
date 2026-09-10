# Lannik Psi antenna: requirements and deliverables for the supplier

Draft, 2026-09-10. This is the supplier-facing formulation of what the
Lannik Psi ambiguity-resolution concept needs from the antenna, written so
that it can be worked into the supplier's detailed design and checked
before production release. The engineering rationale is in
[NOTES.md](NOTES.md), [MIMO.md](MIMO.md) and [RX_LAYOUT.md](RX_LAYOUT.md);
this document states requirements, not reasoning. Values marked *TBD* are
to be fixed after the 2026-09-10 geometry decision.

## 1. Concept summary for the supplier

- One TX aperture of 16 × 16 radiators, fed from eight MMIC ports as four
  independently driven quadrants of two ports each.
- One RX aperture of eight channels, each a uniform rectangular subarray.
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

### 3.1 Subarrays and layout

1. Eight identical uniform rectangular subarrays of 4 radiators horizontally
   by *TBD* radiators vertically (nominally 8; see 3.2), arranged as four
   columns of two channels.
2. Adjacent columns are displaced vertically by a stagger *s* (*TBD*, see
   3.2), alternating (+s/2, -s/2, +s/2, -s/2). The eight channel phase-centre
   positions shall be documented as a table of (x, y) in millimetres.
3. Phase-centre position tolerance: ±0.2 mm is sufficient. Inter-channel
   static amplitude and phase offsets are calibrated in the radar and need
   no tight tolerance, but their stability is required (section 5).

### 3.2 Layout options: preliminary feedback requested

We will choose the layout ourselves from a product and project perspective.
What we ask from the supplier at this stage is early feedback on obvious
feasibility, PCB, feed, coupling or schedule issues with the shortlisted
options, not a full analysis of each.

With W = 9.41 mm subarray width, 2.351 mm radiator pitch and H = 18.81 mm
for eight rows:

| Option | Subarray height | Stagger `s` | Total RX height | Own vertical alias edge | Coherent-mode separation of that alias, `1 - rho` | Subarray gain change |
|---|---:|---:|---:|---:|---:|---:|
| A. Unstaggered URA | 18.81 mm (8 rows) | 0 | 37.6 mm | ±5.9° | 0.00 | 0 dB |
| B. One-pitch stagger (internal sketch) | 18.81 mm (8 rows) | 2.35 mm (H/8) | 40.0 mm | ±5.9° | 0.15 | 0 dB |
| C. Two-pitch stagger | 18.81 mm (8 rows) | 4.70 mm (H/4) | 42.3 mm | ±5.9° | 0.50 | 0 dB |
| D. Two-pitch stagger, 7 rows | 16.46 mm (7 rows) | 4.70 mm (2H/7) | 37.6 mm | ±6.8° | 0.61 | -0.58 dB |

Option A is the fallback. Options C and D are preferred from the
signal-processing side; B is our own earlier sketch and is included for
reference, but it gives too little separation to be worth its complexity. Option D keeps the original
16-row grid, pitch and total height: each column populates 14 of 16 rows,
offset by two rows between adjacent columns. A horizontal row offset of one
pitch (W/4) on top of the column stagger would give the same 0.50 separation
for the horizontal aliases; it is not requested now but may be raised later.

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
