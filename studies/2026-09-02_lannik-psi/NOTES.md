# Lannik Psi system-design working notes

These notes kept the Lannik Psi design study on track. The study did
groundwork for the system design; additions to the general `radarperf` toolbox
were supporting work, not the main subject of this document.

This is a living engineering notebook and possible source for a later report or
design document. It is deliberately not a transcript. Numerical configuration
in [`lannik_psi.py`](lannik_psi.py) is authoritative when this document and the
code differ.

Last substantial update: 2026-10-01, when the study concluded. Start with the
[README](README.md) for the outcome, current numbers and open items; this
notebook holds the range and antenna models and the reasoning behind them.
Sections and status entries are dated. Ranges quoted before 2026-10-01 were
computed in free space without system losses and with `Pfa=1e-6` per beam
test; [Range checkpoints](#range-checkpoints) shows the step to the current
assumptions.

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
4. Develop the interlaced-MIMO approach needed to resolve RX channel-array
   aliases while retaining as much RX aperture and gain as practical.

The study was exploratory throughout: requirements, operating modes and
acquisition-versus-tracking use cases were not defined well enough to finish
the antenna or scheduling architecture. It established the broad direction:
the system design relies on interlaced MIMO measurements to resolve the
coherent-mode angular ambiguities. It concluded on 2026-10-01 after the
antenna RFQ led to an order; the decision log at the end records the steps.

### Status history, 2026-09-04 to 2026-09-11

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
specification; see [technical description for RFQ](deliverables/2026-09-17_rfq/TECHNICAL_DESCRIPTION.md) and
the decision record in [RX_LAYOUT.md](RX_LAYOUT.md).

**Source fact, 2026-09-10:** The same supplier has already produced a separate
prototype antenna with four-quadrant tapered TX and RX apertures for the
existing 4TX/4RX radars, primarily as a supplier evaluation and for
narrow-beam long-range demonstrations. Its measurements are under review;
nothing worrying has been seen so far. If per-port patterns were measured,
they are the first available check of the supplier's ability to realize a
prescribed amplitude and phase distribution, and of the quadrant-squint
metrics in [technical description for RFQ](deliverables/2026-09-17_rfq/TECHNICAL_DESCRIPTION.md).

**Scheduling decision, 2026-09-11:** Use periodically interlaced MIMO as the
initial operating direction, scheduling both left/right-half MIMO for the
horizontal alias family and up/down-half MIMO for the vertical family. Their
cadence, relative rates, ordering and grouping remain open. This is simpler
than relying on tracker-triggered scheduling from the outset and guarantees
that initial test recordings routinely contain both MIMO configurations, so
waveform use, processing and realized antenna signatures can be verified. Some
coherent-TX CPIs will be displaced and additional ambiguity-resolution latency
is accepted as an explicit trade. Pure on-demand operation remains a possible
future extension and is not pursued for the initial release.

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

The scripts, what each one computes and how to run them are listed in the
[README](README.md#scripts). Working figures are written to
[`generated/`](generated/) and are not treated as reviewed deliverables. Only
reviewed or delivered outputs are copied to [`deliverables/`](deliverables/);
see its README for the archiving rule and the record of what was published.

## Current evaluation baseline

### Scenario

**Model assumptions** inherited from the June comparison:

- Target: 1 m² RCS, Swerling 1.
- Initial boresight study: radial approach closing at 15 m/s.
- Frame rate: 20 Hz.
- Confirmation: sliding 2-of-3.
- Pfa: `1e-6` per range–Doppler cell over all RX beams (since 2026-10-01;
  before, `1e-6` per beam test). See
  [False alarms over the RX beams](#false-alarms-over-the-rx-beams).
- No clutter.

Since 2026-10-01 the propagation is the ITU-R reference atmosphere at 1000 m
rather than free space, and named system losses are included; both are listed
under [Loss and environment assumptions](#loss-and-environment-assumptions).

### Front end and waveform

**Current model:**

- CTRX8188F, 8 TX and 8 RX channels.
- 14.5 dBm nominal power per active TX channel.
- 10.2 dB RX noise figure.
- Center frequency: 76.5 GHz, the centre of the confirmed 76–77 GHz band
  (77 GHz until 2026-10-01). The supplied antenna data refer to 77 GHz; the
  model keeps their physical apertures, so directivities scale with frequency
  squared (−0.06 dB each) and angles in u/v scale by 77/76.5.
- 1024 samples × 512 chirps at 50 MHz.
- Assumed chirp slope: 2 MHz/µs.
- Range resolution: approximately 3.66 m.
- Maximum unambiguous range: approximately 1874 m.

The chirp slope was not supplied by the source comparison. It is currently
chosen only to keep the unambiguous range beyond the relevant detection range.
Boresight SNR is independent of it, except that it sets the IF at which the
noise figure applies. The chirp repetition interval is not set; with 512
chirps in a 20 Hz frame it must stay below 97.6 µs, before any MIMO CPIs are
interlaced. The waveform is to be designed later; its choices should avoid
avoidable losses, in particular ramp timing that raises the per-chirp
frequency error (see below).

### Loss and environment assumptions

**Model assumptions, 2026-10-01**, following the checklist in
[`docs/losses.md`](../../docs/losses.md). Each value has a source; a zero is a
stated choice. The values are in `LOSSES` and `ENVIRONMENT` in
[`lannik_psi.py`](lannik_psi.py).

| Term | Value | Basis |
|---|---|---|
| TX power | 14.5 dBm per port, no derating | CTRX8188F typical output power (datasheet Table 22). Up to 1 dB lower over temperature with closed-loop power control (Table 24): see sensitivities |
| Noise figure | 10.2 dB, no derating | Low-noise mode at 10 MHz IF (Table 30). With the assumed slope the IF is 10 MHz at 750 m and 1 MHz at 75 m, where the datasheet gives 0.3 dB more; nothing in between. Our firmware runs RX gain +3 dB, which by our reading of the noise modes (not yet confirmed by Infineon) gives 9.7 dB |
| Feed | 0 dB | The datasheet RF figures are at the waveguide port of its reference PCB. The antenna's own feed network is inside its radiation efficiency. The Lannik Psi PCB-to-antenna transition is not characterised |
| Antenna | 1.01 dB each, TX and RX | The TX and RX patterns are directivities. RFQ targets: radiation efficiency ≥ 80 % including feed dissipation (0.97 dB) and return loss ≥ 20 dB (0.04 dB mismatch). A target, not a supplier figure; replace it with the supplier's prediction when the design feedback arrives |
| Radome | 0 dB | Bare antenna; no radome or housing is defined for Lannik Psi |
| Propagation | 0.22 dB/km one way | ITU-R P.676-13 at 76.5 GHz in the ITU-R P.835-7 reference atmosphere at 1000 m (8.5 °C, 898.8 hPa, 4.55 g/m³ water vapour; `Atmosphere.itu_reference(1000)`), for a horizontal path. The customer use cases put the platform at 1000–5000 m (l2-sp, `requirements/05-external_customer_requirements/FMV/track_2/Use-cases Interceptor Radar.sdoc`), and attenuation falls with height, so the floor is the conservative case. Sea level would give 0.35 dB/km. No rain |
| Per-chirp frequency error | 3.5 kHz rms | Measured on CARKIT (same MMIC) with the ramp timing our firmware programs (2 µs flyback, 83.7 µs wait, 4.0 µs pre-payload): 0.02 dB at 500 m, 0.09 dB at 1 km. Lannik Psi's ramp timing is not set; the CARKIT study measured 14–30 kHz with tighter timing. The value assumes the waveform design keeps the well-timed ramps |
| Phase noise within a chirp | not modelled | At most 0.06 dB at 300 m–1 km with the datasheet's maximum phase-noise table (`docs/losses.md`) |
| Windows, straddle, CFAR | 1.76 + 1.76 dB, 0.47 + 0.47 dB, 1.0 dB | Hann range and Doppler windows without padding, computed by the toolbox; CFAR is the toolbox default (cell averaging with 32 reference cells) |
| RX angle straddle | in the antenna model | The best-of-beams RX envelope already contains it, so `beamforming_loss_db` stays 0 |
| Channel phase errors | 0 dB | CTRX8188F TX phase setting accuracy ≤ 4° and RX channel-to-channel drift ≤ 3.5° (Tables 24, 30); 4° rms would cost 0.02 dB |

With these terms the system loss at the baseline's Pd=90% range (572 m, large
variant) is 2.05 dB and the two-way atmospheric loss 0.25 dB; `lannik_psi.py`
prints the itemised link budget.

**Sensitivities** on the large-RX baseline, each changing one term:

| Change | Pd range | Pd=90% range |
|---|---:|---:|
| Baseline | 913 / 572 m | |
| TX power 1 dB lower (temperature, Table 24) | 863 / 540 m | −5.5% |
| NF 9.7 dB (RX gain +3 dB, our reading) | 938 / 588 m | +2.9% |
| NF 13.2 dB (datasheet maximum) | 772 / 482 m | −15.6% |
| Radome 0.8 dB one way | 835 / 522 m | −8.7% |
| Sea-level standard atmosphere (0.35 dB/km) | 901 / 566 m | −0.9% |
| Light rain, 1 mm/h (P.838-3 attenuation added) | 823 / 534 m | −6.6% |
| Per-chirp frequency error 21 kHz | 809 / 541 m | −5.4% |
| Pfa `1e-6` per beam test (multiple testing ignored) | 974 / 608 m | +6.4% |

The small variant's sensitivities are similar. Rain and the chirp error cost it
1–1.5 percentage points less, because its ranges are shorter.

The radome value is the upper end of the one published radome example in
`docs/losses.md` (1.2–1.6 dB two way); it is an example, not a typical value.
The use cases place the radar behind a radome, but none is defined yet, so the
baseline keeps 0 dB. The light-rain case adds only ITU-R P.838-3 rain
attenuation (1.1 dB/km one way at 1 mm/h); the toolbox's rain clutter is not
validated at 77 GHz, and fog and cloud are not modelled. The 21 kHz error was
measured on CARKIT with 60 ns flyback and wait and 4.2 µs pre-payload. Rain and
the chirp error cost relatively more at longer ranges, because they grow with
range.

### False alarms over the RX beams

**Model assumption, 2026-10-01:** The false-alarm probability is `1e-6` per
range–Doppler cell for the best-of-beams detector as a whole, not per beam.
In each cell the detector compares the largest beam power with one threshold.
The beams are formed from only eight channels, but at a threshold this high,
partially correlated beams exceed it almost independently. The large
variant's 64 beams act as about 56 independent tests and the small variant's
128 as about 80, not 8. Each beam must be tested at `1.8e-8` or `1.2e-8`,
which costs 1.1–1.2 dB of SNR at Pd=90%, about 6–7% of range.
`per_beam_pfa()` in `lannik_psi.py` computes this for each product's own beam
set. It writes the noise vector as a Gamma-distributed power times a
uniformly distributed direction, so the rare exceedances themselves need not
be simulated.

**Why correlated beams count as separate tests:** "Eight independent beams"
describes how the noise *energy* is shared. It is the right count for
averages, for the coherent gain and for low thresholds. A false alarm at
`Pfa=1e-6` is a rare *extreme*. For two beams whose complex outputs have
correlation coefficient `|r| < 1`, both exceeding a threshold `T` (in units
of the noise power) has probability of order `exp(-2T/(1 + |r|))`, against
`exp(-T)` for one. The ratio, `exp(-T (1 - |r|)/(1 + |r|))` up to a slowly
varying factor, vanishes as `T` grows: Gaussian extremes are asymptotically
independent. Two beams therefore act as one test only if `1 - |r|` is small
compared with `2/T`. At `T` ≈ 14–18 that means a power correlation `|r|^2`
well above 0.9, that is, beams within a small fraction of a beamwidth.
Neighbouring beams on a half-beamwidth grid are not that close, so most of
them count fully.

For a continuous scan the count saturates. The Euler-characteristic formula
for the maximum of a smooth random field, applied to one periodic u/v cell,
gives about `N_h N_v sqrt(λ_h λ_v) (2T - 1)/(2π)` tests, with
`λ = (π²/3)(1 - 1/N²)` per axis of `N` channels. For eight channels in two
dimensions this is 128 tests (`continuum_effective_tests()`). It grows
roughly as `T` per channel for a two-dimensional scan and as `sqrt(T)` per
channel for a one-dimensional one. The same applies to anything that tests
the maximum over finely sampled, correlated hypotheses, such as zero-padded
range or Doppler FFTs.

The effective number of tests grows with beam density, but the
multiple-testing cost and the straddle loss trade almost exactly. For the
large variant (`lannik_psi.py` prints this table for both variants):

| Beam spacing | Beams | Effective tests | Per-beam Pfa | SNR cost | Straddle worst / mean | Cost + mean straddle |
|---:|---:|---:|---:|---:|---:|---:|
| 6.0° | 16 | 16 | 6.2e-8 | 0.80 dB | 3.02 / 1.04 dB | 1.84 dB |
| 4.5° | 36 | 35 | 2.9e-8 | 1.00 dB | 1.26 / 0.45 dB | 1.45 dB |
| 3.0° (model) | 64 | 56 | 1.8e-8 | 1.12 dB | 0.69 / 0.25 dB | 1.37 dB |
| 2.0° | 144 | 85 | 1.2e-8 | 1.22 dB | 0.30 / 0.11 dB | 1.33 dB |
| 1.5° | 256 | 101 | 9.9e-9 | 1.26 dB | 0.17 / 0.06 dB | 1.32 dB |

The small variant, with twice as many beams per spacing, has 80 tests and
1.33 dB at 3°, and 32 tests and 1.47 dB at 6°. Beyond about half-beamwidth
spacing, a sparser grid saves processing at little average cost, though its
worst-case straddle grows. `1e-6` per cell is a placeholder: the false-alarm
rate the tracker and platform can accept is still to be set. With 512 range
bins (the real-sampled 1024-sample chirp) and 512 Doppler bins, `1e-6` per
cell gives about 0.26 false alarms per frame, or 5 per second at 20 Hz.

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
  approximately 23.5 dBi boresight gain at 77 GHz, the frequency of the
  supplied data. At the 76.5 GHz model frequency the same radiator area gives
  6.39 dBi.
- Mutual coupling, feed-network loss, embedded element patterns, and installed
  antenna effects are not represented; the antenna loss in the loss table
  stands in for efficiency and mismatch.
- Processing adds `10 log10(8)` for the total power of eight active TX channels,
  but does not add another ideal TX-array directivity term.
- The model assumes all eight ports contribute equal full power, but does not
  represent the intended two-equal-power-feeds-per-quadrant partition.

The modeled boresight array-factor contribution is approximately 17.05 dB,
giving 23.4 dBi at 76.5 GHz after adding the radiator gain. The principal-plane
3 dB beamwidths are approximately 12.6° (12.5° at 77 GHz).

### RX

**Supplied reference geometry:**

- Each RX channel is a uniform 4 × 8 radiator subarray.
- The eight channel centroids form a 4 × 2 uniform rectangular array.
- The corresponding subarray extents and densely packed channel spacings are
  approximately 2.42 wavelengths horizontally and 4.83 wavelengths vertically
  at 77 GHz.

**Current computational baseline:**

- Each channel is an analytical, uniformly illuminated rectangular aperture.
- The analytical aperture efficiency is 0.963. This is calibrated so that the
  original 9.41 × 18.81 mm aperture reproduces the previous 21.50 dBi
  32-radiator model; it is a modeling calibration, not a measured efficiency.
  The antenna loss above comes on top of it.
- Channels are packed without gaps; the layout is parametrized and can be
  given explicit larger channel spacings.
- The ideal coherent gain of the eight RX channels remains in processing.

The two prototype variants as modelled (the large variant without its H/4
column stagger, which changes neither gain nor beamwidth):

| | Small variant (first prototype) | Large variant (baseline) |
|---|---|---|
| Subarray | 9.41 × 9.41 mm (2.40λ square) | 9.41 × 18.81 mm (2.40 × 4.80λ) |
| Channel layout | 2 × 4, 18.81 × 37.62 mm | 4 × 2, 37.62 × 37.62 mm |
| Subarray gain | 18.4 dBi | 21.4 dBi |
| Effective RX gain | 27.5 dBi | 30.5 dBi |
| Formed-beam 3 dB width, az × el | 10.5° × 5.2° | 5.2° × 5.2° |
| Array-factor periods, u × v | 0.417 × 0.417 | 0.417 × 0.208 |
| Principal region | ±12.0° az × ±12.0° el | ±12.0° az × ±6.0° el |
| RX beams formed | 128 (8 × 8 + offset copy) | 64 (8 × 4 + offset copy) |
| Effective false-alarm tests per cell | 80 | 56 |
| Worst / mean beam-straddle loss | 0.30 / 0.12 dB | 0.70 dB worst |

Values are at 76.5 GHz. The large rectangle, without its stagger, has been the
plotted product and computational baseline since 2026-09-04; ordering the
small variant first was a project choice. The text below on periods and the
beam grid was written for the large variant at 77 GHz. At 76.5 GHz its periods are 0.4167 and 0.2083
and its principal edges ±12.0° and ±6.0°. The small variant's square periods
put both principal edges at ±12.0°, outside the TX 3 dB beam; its beam grid
follows the same construction.

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
This is an optimistic envelope: it does not include computational limits or
scheduling cost. Since 2026-10-01 the multiple-testing Pfa, including the
correlation between beams, is accounted for (see
[False alarms over the RX beams](#false-alarms-over-the-rx-beams)).

The same 64-beam set is used for every calculation. Its periodic aliases
repeat its best array-factor sampling over the visible u/v disk. This removes
the former distinction between the product and full-visible beam sets.

The earlier 2305-beam experiment remains useful historical context: because its
`sin(3°)` spacing did not divide the array-factor periods, it accidentally
provided a much denser set of unique steering vectors when reduced modulo the
periods. It should not be compared numerically with the present result without
also accounting for the changed subarray geometry.

## Range checkpoints

Boresight single-scan Pd = 50% / 90% ranges for the inherited scenario.
Since 2026-10-01 the study reports single-scan Pd only. Acquisition
probability with a confirmation rule (Pacq) depends strongly on the assumed
trajectory, frame rate and acquisition criterion. In the June comparison it
mainly showed that acquisition ranges come out well beyond single-scan Pd
ranges, with a sharper transition from 0 to 100%; `lannik_psi.py` keeps an
illustration of that (see the [README](README.md)).

**Result, 2026-10-01:** step by step from config 3 of the June comparison to
the current large-RX baseline; `lannik_psi.py` prints this table. Each row
adds one change to the row above.

| Step | Pd range | Change in Pd 90% range |
|---|---:|---:|
| June config 3, as published (17 dBi placeholders, coherent TX and RX, free space) | 994 / 614 m | |
| Same model, current toolbox (window straddle computed: 0.47 instead of 0.6 dB per axis) | 1009 / 623 m | +1.5% |
| Proposed TX aperture instead of the TX placeholder | 872 / 538 m | −13.6% |
| Large RX subarrays and 64 RX beams instead of the RX placeholder | 1131 / 698 m | +29.7% |
| 76.5 GHz instead of 77 GHz | 1127 / 696 m | −0.3% |
| Atmosphere at 1000 m, 0.22 dB/km | 1096 / 684 m | −1.7% |
| Antenna loss, 1.01 dB each side | 978 / 610 m | −10.9% |
| Per-chirp frequency error, 3.5 kHz | 974 / 608 m | −0.2% |
| **Pfa per cell over all beams: large-RX baseline** | **913 / 572 m** | −6.0% |
| Small RX instead, same assumptions | 767 / 479 m | −16.1% |

The steps through "large RX subarrays" correspond to the September
checkpoints quoted elsewhere in these notes, which used 0.6 dB straddle per
axis: 1114 / 688 m for the September baseline, 859 / 531 m with the TX
aperture alone. The square
first-cut candidate, now the small variant, was 937 / 578 m in September. The
loss and false-alarm terms added on 2026-10-01 cost 18% of the large
variant's Pd 90% range; the baseline ends 7% below the June estimate.

At boresight and at 6° off boresight (`lannik_psi.py` prints this table):

| Direction (az, el) | Large RX | Small RX |
|---|---:|---:|
| (0°, 0°) | 913 / 572 m | 767 / 479 m |
| (6°, 0°) | 744 / 465 m | 625 / 390 m |
| (0°, 6°) | 628 / 392 m | 625 / 390 m |

Six degrees is about the TX 3 dB half-width (6.3°) and the large variant's
vertical principal edge (6.0°). The customer use cases' ±8° field of view is
indicative, and the design deliberately trades beamwidth for gain. The large
variant's taller subarrays narrow its vertical coverage to that of the small
variant at 6° elevation.

## Main results and current conclusions

### RX beam spacing

**Result:** Within one fundamental steering cell, the large variant's 64-beam
interleaved RX grid has a worst sampled beam-straddling loss of approximately
0.70 dB. In a free-space radar equation this corresponds to approximately 3.9%
range loss. The small variant's 128-beam grid loses at most 0.30 dB (1.7%);
along the principal cuts its range ripple is at most 1.7% in elevation and
1.0% in azimuth. Beam density also sets the multiple-testing cost; the two
trade almost exactly (see
[False alarms over the RX beams](#false-alarms-over-the-rx-beams)).

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

**Selected broad system direction:** Retain coherent TX for sensitivity and
periodically interlace split-aperture MIMO measurements to resolve the discrete
RX ambiguity cell. The tracker can maintain several hypotheses, accumulate
evidence over MIMO updates and apply the resolved cell to intervening coherent
measurements. The detailed waveform, cadence, processing and achievable
performance remain to be validated.

**Working architecture, 2026-09-11:** Begin with fixed periodic interlacing of
both left/right- and up/down-half MIMO for simplicity and dependable test-data
collection. Their exact fractions and grouping are not decided. Evaluate the
loss from displaced coherent frames and the time from target appearance to
sufficient evidence in the required axis as schedule-level tradeoffs. The
earlier 2026-09-09 assumption of tracker-requested bursts is superseded.
Triggered or adaptive scheduling is outside the initial-release scope, though
it may be useful as a future extension. See [MIMO.md](MIMO.md) for the
architecture and [RX_LAYOUT.md](RX_LAYOUT.md) for the geometry comparison.

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
approximately 226/363/481 m after one/two/four MIMO updates with the
2026-10-01 assumptions (253/407/541 m in the September model). With the
supplied 2.42λ × 4.83λ rectangle, the corresponding nominal vertical-edge
ranges are approximately 374/594/776 m (421/673/884 m), while retaining 3 dB
more RX gain. Binary resolution does not involve the false-alarm threshold, so
these moved only with the losses and atmosphere. For comparison, the small
variant's single-scan Pd=90% range at its ±12.0° principal edges is 205 m. In
September this result reopened the supplied-height rectangle as the main
candidate; the order now starts with the square.

The experiment began by treating MIMO as an independent `Pfa=1e-6` detector
with the existing waveform. Gated soft cell likelihoods remain a more natural
way to use each scheduled MIMO measurement than requiring it to pass a second
independent full-search threshold. Pattern/calibration tolerance, the complete
set of aliases and the eventual schedule remain to be studied.

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

For a constant-RCS, free-space, noise-limited model, a fixed-Pd range boundary
follows

```text
R_Pd(theta) = R_Pd(0) * 10**(
    (G_two_way(theta) - G_two_way(0)) / 40
)
```

With gaseous attenuation and the coherence loss this is no longer exact,
because both grow with range. SINR still separates into a boresight range curve
plus the direction-only two-way gain difference; since 2026-10-01 the coverage
maps and every SNR-to-range conversion in the study scripts use that curve
(`BoresightSinr` in `lannik_psi.py`).

**Small variant, 2026-10-01** (`lannik_psi(RX_SQUARE_LAYOUT)`; the plotted
coverage maps show the large baseline): horizontal and vertical coverage are
practically identical, because both the TX aperture and the small RX
subarrays are square. At the ±12.0° principal edges the two-way gain is
14.9 dB below boresight, and a 1 m² target reaches Pd=90% at 205 m and Pd=50%
at 330 m (computed from the boresight curve and the best-beam two-way gain).
Detections outside the principal region beyond those ranges need targets
well above 1 m². The bullets below describe the large rectangle.

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
   [technical description for RFQ](deliverables/2026-09-17_rfq/TECHNICAL_DESCRIPTION.md).

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
- The initial direction periodically interlaces both left/right- and
  up/down-half MIMO. Their relative cadence, ordering and grouping remain open;
  triggered bursts or a temporary track-directed mode are possible
  post-release extensions, not initial work.
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
  calibrated from the earlier discrete model; edge effects and embedded
  radiator behavior are not modeled.
- Antenna efficiency and mismatch are a single loss per side taken from the
  RFQ targets, not from a supplier design. No mutual coupling, radome, PCB
  transition or installed element patterns.
- Phase noise only as the per-chirp frequency error's coherence loss, measured
  on CARKIT with a different ramp timing from the one Lannik Psi will use. No
  clutter, so no phase-noise skirts of strong returns.
- The model runs at the 76.5 GHz centre frequency only; nothing is evaluated
  across the 76–77 GHz band.
- Best-over-RX-beams detection takes the best beam's SNR and holds the
  false-alarm probability per cell; it ignores detections in neighbouring
  beams and assumes white noise of equal power in every channel.
- RX angle estimates remain ambiguous between periodic channel-array replicas;
  the supplied rectangle's vertical principal edges lie near the TX 3 dB
  mainlobe boundary. The main coherent-TX script does not resolve these aliases.
- The separate MIMO experiment remains idealized and binary. Its assumptions
  and limitations are maintained in [`MIMO.md`](MIMO.md).
- Pacq is no longer reported. The acquisition illustration covers radial
  approaches at 15 and 50 m/s on boresight with a 2-of-3 rule.
- Static directional coverage shows Pd only; Pacq requires an
  explicit trajectory and revisit schedule.
- No TX-mode timing, waveform switching, scheduler, or tracker model.
- Far-out sidelobe and grating-lobe coverage should not be interpreted as a
  complete physical prediction.

## Candidate next steps

The study's open items and handover list are in the [README](README.md#open-items-and-handover).
The list kept here until 2026-10-01 is in the repository history; its RFQ and
prototype-decision items are done, and the rest are folded into the README.

## Key generated figures

- `coverage_summary.png` — Cartesian single-scan Pd coverage of both RX
  variants in the horizontal and vertical planes; the README's headline
  figure, archived with the large-RX polar/Cartesian maps in
  `deliverables/2026-10-01_conclusion/`.
- `pd_pacq_vs_range.png` — boresight Pd, with the illustrative 2-of-3 Pacq.
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
- `generated/experimental/on_demand/stagger_in_beam_competitors.png` —
  strongest gain-admissible alias competitor for every in-beam true
  direction, coherent and MIMO, for the same three layouts.

The main-script figures show the large RX baseline.

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
  [technical description for RFQ](deliverables/2026-09-17_rfq/TECHNICAL_DESCRIPTION.md).
- **2026-09-10, review:** Corrected a phase-wrapping bug in the defocus
  sensitivity sweep and the in-beam MIMO competitor search; added the
  diagonal competitor family and a systematic RX column-group phase error to
  the multi-frame experiment. The direction stands; frame counts, processing
  cost, calibration tolerance and option D are recorded as validation items.
- **2026-09-10, meeting:** Decided the two first prototypes: the rectangular
  subarrays with a two-pitch (height/4) alternating column stagger, eight
  rows, and the rotated 2 × 4 square-subarray URA. The TX-side specification
  is the main remaining item. This branch is snapshotted to `main` at this
  point; the presentation is kept as presented under
  `deliverables/2026-09-10_presentation/`.
- **2026-09-11:** Replaced purely on-demand MIMO with periodic interlacing of
  both left/right- and up/down-half measurements as the initial scheduling
  direction. The simpler fixed schedule guarantees routine operation and
  useful recorded data from both MIMO configurations. Its coherent-frame cost
  and ambiguity-resolution latency are accepted; the cadence remains to be
  selected.
- **2026-09-17:** Completed the RFQ technical description, with 76–77 GHz
  (76.5 GHz centre) confirmed and the polarization left open. It is archived
  as issued in [deliverables/2026-09-17_rfq/](deliverables/2026-09-17_rfq/README.md).
- **2026-10-01:** The RFQ led to an order. The first prototype is the small RX
  variant (2 × 4 square subarrays), for a smaller initial scope and package;
  the large staggered variant follows. Supplier design feedback is expected in
  one to two weeks, first delivery about six weeks later.
- **2026-10-01:** Kept the large variant as the computational baseline;
  ordering the small one first is a project choice. Added explicit
  model assumptions: the ITU-R reference atmosphere at the use cases' 1000 m
  altitude floor, the RFQ-target antenna loss, and the measured per-chirp
  frequency error. The remaining loss terms are stated as zero; the radome
  stays at zero until one is defined. Moved the model to 76.5 GHz. Held
  `Pfa=1e-6` per range–Doppler cell over all RX beams instead of per beam;
  the computation showed about 56 effective tests for the large variant's 64
  beams and 80 for the small variant's 128, not the eight first assumed.
  Noise figure and waveform unchanged. Boresight Pd=90% range: large 696 to
  572 m, small 585 to 479 m. The study scripts now derive ranges from
  the boresight SINR curve instead of an R^-4 law.
- **2026-10-01:** Concluded the study. Wrote the [README](README.md) summary
  and handover list and archived the RFQ as issued. Continued work, starting
  with the supplier's design data, belongs in a new study.
- **2026-10-01, review:** Report single-scan Pd only. Pacq depends too much on
  trajectory, frame rate and acquisition criterion; one illustration is kept.
  Compare with the June study, which has archived results, rather than the
  RFQ, which has none, and break the change down step by step. Quote
  off-boresight ranges at 6°, about the TX 3 dB half-width, rather than the
  use cases' indicative ±8°. Make the Pd coverage figure the README's
  headline, archived in `deliverables/2026-10-01_conclusion/`.
