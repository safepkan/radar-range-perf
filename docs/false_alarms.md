# False alarms per cell

The toolbox holds the false-alarm probability per range–Doppler cell, not per
FFT bin or per beam. This page explains what that means, how the engine turns
it into a threshold when zero padding and beam sets add tests to each cell, and
what the method has been checked against. The Pfa row in
[losses.md](losses.md) and the `LinkBudget` printout refer to it.

## The convention


`Radar.default_pfa` is the false-alarm probability per range–Doppler
resolution cell: the expected number of false detections per bin of the
unpadded range and Doppler FFTs, over all beams formed in that cell. False
alarms per frame are this value times the numbers of range and Doppler cells.
A detection is a local maximum along each FFT axis (peak grouping), so a noise
peak that spreads over neighbouring bins counts once.

## Tests per cell

Each test (one FFT bin of one beam) is compared with one threshold. Zero
padding and beam sets add tests per cell, partially correlated with each
other, so the threshold must rise to hold the per-cell value.
`Radar.false_alarm_budget()` counts the effective tests per cell and returns
the per-test Pfa; the detector uses that, and `LinkBudget` prints it after
the processing losses. The convention covers `Radar` and the sweeps in
`radarperf.sweeps`. The low-level functions in `radarperf.detection`
(`probability_of_detection`, `required_snr_db`, `detection_threshold` and
the Albersheim and Shnidman approximations) take the Pfa per test; pass them
`radar.false_alarm_budget().pfa_per_test`. For the Lannik Psi study's large RX variant
(`studies/2026-09-02_lannik-psi/lannik_psi.py`, 64 receive beams):

```
Pfa per cell:        1.0e-06
  range tests           0.99
  doppler tests         0.99
  angle tests          54.38
  Pfa per test        1.9e-08
  threshold increase    1.10 dB
```

The counts come from `radarperf.false_alarms`, where the methods are
derived:

- **Range and Doppler:** the expected number of local maxima above the
  threshold per resolution cell, from the window's correlation between
  neighbouring bins and the padding.
- **Angle:** the probability that the largest beam power exceeds the
  threshold, from the beam weights (`BeamSet.beam_weights()`).
- **All axes:** the product of the per-axis factors. This is an
  approximation for small Pfa, where exceedances are nearly independent
  between axes; the checks below cover the cases the toolbox is used for.

The threshold increase is the threshold relative to testing one bin at the
per-cell Pfa. For a Swerling 1 target it is close to the SNR cost. With 54
tests the increase is 1.10 dB, against an SNR cost of 1.11 dB at Pd 90 % and
1.15 dB at Pd 50 %. A Swerling 0 target at Pd 90 % pays less, 0.92 dB
(computed with `required_snr_db`, one look).

## Zero padding

Zero padding trades straddle loss for threshold. One FFT axis of 256
samples, Pfa 10⁻⁶ per cell, one look, Swerling 1 target at Pd 90 %
(computed with `false_alarm_budget`, `required_snr_db` and
`straddle_loss_db`):

| Padding | Hann: tests per cell | Hann: SNR cost | Hann: mean straddle | Hann: sum | Rectangular: tests per cell | Rectangular: sum |
|---|---:|---:|---:|---:|---:|---:|
| 1× | 0.98 | −0.01 dB | 0.47 dB | 0.47 dB | 1.00 | 1.26 dB |
| 2× | 1.53 | +0.13 dB | 0.12 dB | 0.25 dB | 1.98 | 0.51 dB |
| 4× | 1.80 | +0.18 dB | 0.03 dB | 0.21 dB | 3.16 | 0.42 dB |
| 8× | 1.89 | +0.20 dB | 0.01 dB | 0.20 dB | 3.75 | 0.42 dB |
| 16× | 1.91 | +0.20 dB | 0.00 dB | 0.20 dB | 3.96 | 0.42 dB |

- **Up to fourfold** padding pays: for Hann, twofold saves 0.22 dB per axis
  and fourfold 0.26 dB.
- **Beyond fourfold** nothing is gained.
- **The limit** for fine sampling is Rice's level-crossing rate of the
  envelope, `sqrt(λ T / π)` tests per cell for one look at threshold `T`,
  where `λ` is (2π)² times the variance of the sample index (in window
  lengths) weighted by the squared window: 1.91 for Hann and 3.99 for
  rectangular at 10⁻⁶.
- **Rectangular windows** gain more from padding, because their straddle
  loss without padding is larger (1.26 dB). Their floor is higher, because
  their larger `λ` gives more tests per cell (3.29 against 0.79 for Hann).
- **Without padding** the count is within 2 % of one test per bin at 10⁻⁶.
  At higher Pfa, neighbouring Hann bins cross the threshold together more
  often, and the count falls: 0.94 at 10⁻⁴ and 0.90 at 10⁻³ per cell.
- **A window with a single nonzero sample**, such as a two-point Hann window
  (two chirps per transmitter), gives every bin of the axis the same power.
  A detector with peak grouping then reports one detection along the axis,
  which is 1/length per cell; windows that approach this case tend to the
  same count.

## Beams

Beams work the same way. In the printout above, 64 beams formed from eight
channels act as 54 independent tests, not 8. Correlated beams exceed a high
threshold almost independently (`studies/2026-09-02_lannik-psi/NOTES.md`,
"False alarms over the RX beams"). Holding the Pfa per cell instead of per
beam shortens the study's Pd 50 % range by 6.4 % (1.15 dB), as its range
breakdown in `lannik_psi.py` prints.

## What the method has been checked against

The tests in `tests/test_false_alarms.py` check these computations:

- **Range and Doppler:** against simulated FFTs, padded and unpadded, with
  one and four non-coherent looks.
- **Beams:** against a simulated detector on correlated beams, with one and
  four looks.
- **The fine-sampling limit:** against the Rice formula.
- **Range and Doppler together:** the product of the 1-D factors lies up to
  6 % above a direct count of peaks over all eight neighbours (Hann, fourfold
  on both axes: 3.13 against 3.02 tests). That shifts the threshold by under
  0.02 dB, with twofold to eightfold padding of Hann or rectangular windows.
- **Range and angle together:** against a simulated search over range of the
  best-beam power.

The checks cover Pfa from 10⁻⁶ to 10⁻² per test, Hann and rectangular
windows (and one window close to a single nonzero sample), up to sixteenfold
padding, one or four looks, and uniform-array beam grids. They support those
operating cases; they are not error bounds for arbitrary windows, look
counts or Pfa values.

## Limitations

- **Fixed threshold against known noise.** CFAR enters as the separate,
  fixed allowance in the CFAR row; it does not change with the per-test Pfa.
- **Peak grouping is assumed.** A detector that reports every bin above
  threshold has `P` times as many false alarms per cell at `P`-fold padding.
- **Pd is evaluated in the strongest beam.** With a beam set, the detector
  reports a detection in any beam, but Pd is computed in the beam with the
  strongest expected signal. Where several beams receive comparable signal,
  as between beams, that is conservative. With an equal response in two
  orthogonal beams and a shared Swerling 1 fluctuation, Pd 0.50 in the
  strongest beam is 0.57 in either, about 1 dB of SNR at Pd 50 % (computed in
  `tests/test_false_alarms.py`). Neighbouring beams of a denser grid share
  more of their noise, so their gain is smaller.
- **Small Pfa only.** At high Pfa the product of the axis factors stops being
  a false-detection rate and has a largest value (about 0.1 per cell for a
  four-point Hann window on both axes with four looks); larger values raise
  an error. The threshold is solved on the branch where false detections
  fall as the threshold rises.
- **Collapsing cells** count as looks in the noise statistics, like every
  non-coherently summed cell.
- **Transmit beams** formed one after another are separate dwells, not tests
  within one cell; the engine counts only receive beam sets.
