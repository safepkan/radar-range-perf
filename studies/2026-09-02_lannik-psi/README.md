# Lannik Psi antenna-concept study

2026-09-02 to 2026-10-01 · concluded

Lannik Psi is a 76–77 GHz FMCW radar for drone interceptors, built on the
Infineon CTRX8188F MMIC with eight transmit (TX) and eight receive (RX)
channels. This study took it from a generic range estimate to an antenna
concept that could go out for quotation. The study ended when the antenna RFQ
was issued and the first prototype ordered. This page summarises the outcome.
The linked notes hold the reasoning and the dated history.

## Summary

### Antenna concept

- **TX:** one aperture of about 37.6 × 37.6 mm, 16 × 16 radiators in the
  reference design. Its amplitude is tapered and its phase is a smooth
  quadratic ("defocus") that widens the coherent beam to about 12.6° at the
  3 dB points, with 23.4 dBi directivity. The aperture is split into four
  quadrants. Two MMIC ports feed each quadrant, all eight at equal full power,
  with no intentional attenuation.
- **RX:** each channel has its own subarray. Large subarrays give gain, but
  they put the channel phase centres several wavelengths apart. The channel
  array then cannot distinguish directions whose direction cosines differ by a
  whole array period, a grating-lobe ambiguity. One RX measurement is
  unambiguous only inside the *principal region* around boresight.
- **Two RX prototypes:**
  - *Small variant, ordered first:* 2 × 4 channels of 9.4 × 9.4 mm square
    subarrays. Principal region ±12.0° in both planes; 27.5 dBi effective RX
    gain after combining the eight channels.
  - *Large variant, second prototype:* 4 × 2 channels of 9.4 × 18.8 mm
    subarrays. Alternate columns are offset vertically by a quarter of the
    subarray height. Principal region ±12.0° horizontally and ±6.0°
    vertically; 3 dB more RX gain.
- **Ambiguity resolution:** the radar periodically interlaces two MIMO modes,
  in which the left and right TX halves, or the upper and lower halves,
  transmit separable waveforms. The defocus phase makes the two halves'
  responses differ with direction. That distinguishes directions the RX
  array alone cannot. In an ideal four-quadrant MIMO model, with the target
  fluctuating independently between updates, a 1 m² target at the small
  variant's ±12° principal edges is resolved with 99% probability after one,
  two or four MIMO updates out to 226, 363 and 481 m. For the large variant,
  the column offset also let ordinary coherent frames resolve the vertical
  ambiguity in the cases tested.

The antenna RFQ (technical description dated 2026-09-17) is archived as
issued in [deliverables/2026-09-17_rfq/](deliverables/2026-09-17_rfq/README.md).
Supplier design feedback is expected one to two weeks after 2026-10-01, and
the first prototype about six weeks after that.

### Range performance

The computational baseline for range performance is the large variant,
modelled without its column stagger. Ordering the small variant first was a
project choice, so both are given. Scenario: a 1 m² Swerling-1 target
closing at 15 m/s, 20 Hz frames. Single-scan Pd is per frame. Pacq is the
probability of a 2-of-3 confirmed acquisition by that range. False alarms are
held at 1e-6 per range–Doppler cell over all RX beams: 1.8e-8 per beam for
the large variant's 64 beams, 1.2e-8 for the small variant's 128.

| Direction (azimuth, elevation) | Large RX: Pd 50/90% | Large RX: Pacq 50/90% | Small RX: Pd 50/90% | Small RX: Pacq 50/90% |
|---|---:|---:|---:|---:|
| Boresight | 913 / 572 m | 1302 / 1219 m | 767 / 479 m | 1088 / 1015 m |
| 8° horizontally | 623 / 388 m | 878 / 817 m | 532 / 331 m | 742 / 689 m |
| 8° vertically | 444 / 276 m | 616 / 570 m | 526 / 327 m | 734 / 682 m |
| (8°, 8°) | 313 / 194 m | 425 / 392 m | 370 / 230 m | 508 / 469 m |

The large variant's taller subarrays narrow its vertical coverage. At 8°
elevation it falls below the small variant, and that direction lies outside
its ±6.0° vertical principal region, so a detection there also needs its
ambiguity resolved.

These numbers assume:
- typical CTRX8188F TX power (14.5 dBm per port) and noise figure (10.2 dB);
- ideal antenna-pattern models, which give directivity, with 1.0 dB loss on
  each side from the RFQ targets (≥ 80% radiation efficiency, ≥ 20 dB return
  loss);
- the ITU-R reference atmosphere at 1000 m, 0.22 dB/km one way, the floor of
  the customer's 1000–5000 m altitude band;
- a per-chirp RF frequency error of 3.5 kHz rms, measured on Infineon's CARKIT
  evaluation board (same MMIC) with our firmware's ramp timing;
- no radome, rain or clutter.

Together with the per-cell false-alarm accounting, these terms cost 18–23% of
the range quoted at the RFQ. Those earlier figures assumed free space, no
system losses and 1e-6 per beam.

Largest sensitivities for the large variant, as change in single-scan
Pd = 90% range (Pacq 90% in brackets):

| Change | Pd 90% | (Pacq 90%) |
|---|---:|---:|
| Noise figure at the datasheet maximum, 13.2 dB | −16% | (−16%) |
| Radome, 0.8 dB one way | −9% | (−9%) |
| Light rain, 1 mm/h | −7% | (−14%) |
| TX power 1 dB lower (temperature) | −6% | (−6%) |
| Per-chirp frequency error of 21 kHz (tight ramp timing) | −5% | (−19%) |

### Relation to the customer use case

The first use case, UC-01, asks for detection of a 0 dBsm Swerling-1 target
at 500–800 m inside ±8° horizontally and vertically. It states no Pd,
false-alarm rate or latency. At boresight, single-scan Pd reaches 50% at 913 m
(large) or 767 m (small), and confirmed acquisition 90% at 1.2 km or 1.0 km.
At the ±8° edges single-scan Pd 50% falls to 440–620 m (large) or about 530 m
(small), and Pacq 90% to 570–820 m or about 690 m. The use case also puts the
radar behind a radome, which these numbers leave out, and allows relative
speeds up to 50 m/s against the 15 m/s used here. Whether the concept meets
UC-01 depends on the Pd and latency that the requirement turns out to set.

### What is not established

The antenna patterns are ideal models without coupling, feed or installation
effects, and the antenna loss is a target rather than a supplier figure. The
MIMO results assume perfectly separable waveforms and perfectly known
patterns. The best-beam detector has no processing or scheduling limits. The
waveform is an assumption, not a design. There is no tracker model.

## Open items and handover

1. **Supplier design data, expected one to two weeks after 2026-10-01:**
   - Replace the antenna-loss target with the supplier's predicted realized gain.
   - Evaluate the supplied complex patterns for both variants and both MIMO
     splits. The [internal RFQ review](deliverables/2026-09-17_rfq/internal/REVIEW.md)
     outlines a supplier-neutral evaluator.
   - Once the supplier defines the eight-port partition, model each port with
     its own weights and phase, and compare coherent, half-aperture and
     eight-TX MIMO at equal power and time.
   - Judge any proposed change to the large variant's stagger with the
     multi-frame event model and the in-beam competitor map
     ([RX_LAYOUT.md](RX_LAYOUT.md)), not only the exact-alias correlation.
2. **Radome:** the use case puts the radar behind a radome. Define it and its
   loss.
3. **Waveform and timeline:**
   - Chirp slope (assumed 2 MHz/µs).
   - Chirp repetition interval: 512 chirps in a 50 ms frame need under
     97.6 µs, before MIMO frames are interlaced.
   - MIMO cadence.
   - Ramp timing that keeps the per-chirp frequency error at the well-timed
     level. CARKIT measured 3.5 kHz with long settling and 14–30 kHz with
     tight timing.
4. **False-alarm budget:** 1e-6 per cell is a placeholder until a false-alarm
   rate is required.
5. **CARKIT validation study:** its outcome may revise the noise figure, the
   per-chirp error and the overall model-versus-measurement offset.
6. **Requirements:** Pd, false-alarm and latency targets for the three use
   cases, the closing speeds to evaluate, and the acceptable
   wrong-ambiguity-cell probability.
7. **Toolbox work for the next study:**
   - Named presets for the two prototype antennas.
   - Staggered RX phase centres in the main range model.
   - Import of measured or simulated complex patterns.
   - The per-beam Pfa computation, promoted from this study.
8. **Tracker-level ambiguity resolution:**
   - Enumerate all plausible aliases, not just the folded one, and weigh them
     with gain and RCS plausibility and pattern uncertainty.
   - Feed soft cell likelihoods to a multiple-hypothesis tracker running the
     fixed interlace.
   - This is probably signal-processing work outside this repository.
9. **Design ideas not pursued:** shaped TX illumination and TX subarray phase
   modes for short-range coverage; see "Possible TX and coverage directions"
   in [NOTES.md](NOTES.md).

## Documents

| File | Contents |
|---|---|
| [NOTES.md](NOTES.md) | Range model, antenna models, loss and environment assumptions, false alarms over the RX beams, coverage, decision log |
| [RX_LAYOUT.md](RX_LAYOUT.md) | RX layout trade and the 2026-09-10 prototype decision |
| [MIMO.md](MIMO.md) | Interlaced split-aperture MIMO for ambiguity resolution |
| [deliverables/](deliverables/README.md) | What was published outside the repository: Slack figures, the decision presentation, the RFQ as issued |
| [inputs/](inputs/) | Supplied antenna data, presentations and layout sketches |

Sections of the notes are dated. Ranges quoted before 2026-10-01 omit the
loss, atmosphere and false-alarm terms above; [MIMO.md](MIMO.md) and
[RX_LAYOUT.md](RX_LAYOUT.md) start with a table mapping them to current values.

## Scripts

| Script | Purpose |
|---|---|
| [lannik_psi.py](lannik_psi.py) | Range model and baseline product; Pd/Pacq, patterns, coverage maps, checkpoint and sensitivity tables, beam-density trade |
| [quadrant_mimo.py](quadrant_mimo.py) | Ideal four-quadrant and half-aperture MIMO: alias correlation, detection and resolution ranges, RX height trade |
| [rx_layout_experiment.py](rx_layout_experiment.py) | RX layout geometries and channel-array factors |
| [rx_resolution_experiment.py](rx_resolution_experiment.py) | Monte Carlo resolution events: one coherent frame plus MIMO illumination |
| [rx_stagger_amount_experiment.py](rx_stagger_amount_experiment.py) | Stagger amount, several coherent frames, competing lobes over the TX beam |

From the repository root, `make study_260902_lannik_psi` runs every script
headlessly and the study-local tests, in about 3.5 minutes. Figures go to
`generated/`, which is not versioned.
