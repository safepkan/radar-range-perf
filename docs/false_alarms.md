# False alarms per cell

The toolbox holds the false-alarm probability per range–Doppler cell, not per
FFT bin or per beam. This page explains what that means, how the engine turns
it into a threshold when zero padding and beam sets add tests to each cell, how
much range a higher Pfa buys, and what the method has been checked against.
The Pfa row in
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

## Trading false alarms for range

A lower threshold buys range with false alarms, but slowly. For a Swerling 1
target and one look, the detector's closed form (`radarperf.detection`) is

```
Pd = exp(−T / (1 + SNR)),   T = ln(1/Pfa)
```

with the Pfa per test, so

```
1 + SNR = ln(1/Pfa) / ln(1/Pd)
```

At any Pd, the required SNR is proportional to the number of decades in the
per-test Pfa, `n = log10(1/Pfa)`, as long as the SNR is well above one. That
gives a rule of thumb: going from `n₁` to `n₂` decades lowers the required
SNR by 10 log10(n₁/n₂) dB, and under the radar equation's fourth-power law
the range grows by (n₁/n₂)^(1/4).

- **Each tenfold increase in false alarms** takes one decade off `n` and buys
  10 log10(n/(n − 1)) dB: 0.6 dB, 3.4 % in range, at `n` = 8, and 0.8 dB,
  4.7 %, at `n` = 6. The false alarms grow tenfold per step, the range by a
  few percent.
- **Pd 90 % stays 8.2 dB behind Pd 50 %.** The two required values of
  1 + SNR differ by the factor ln 2 / ln(1/0.9) = 6.6 whatever the Pfa, a
  factor 1.6 in range. A lower threshold moves both ranges by the same factor
  and does not close the gap. Bringing Pd 90 % out to the Pd 50 % range takes
  `n` 6.6 times smaller: from 1.9 × 10⁻⁸ per test (7.7 decades) to 0.07,
  where noise alone crosses the threshold in one bin out of fifteen, in every
  beam. The gap comes from the target's fades; within one frame, only more
  SNR closes it.

For the Lannik Psi large RX variant's beam set (the printout above), the SNR
saved relative to 10⁻⁶ per cell, computed with `Radar.false_alarm_budget` and
`required_snr_db` for one look:

| Pfa per cell | False alarms per 512 × 512 cells | Pfa per test | Swerling 1, Pd 50 % | Swerling 1, Pd 90 % | Rule of thumb | Range, from Pd 50 % | Swerling 0, Pd 90 % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 10⁻⁷ | 0.026 | 1.8 × 10⁻⁹ | −0.56 dB | −0.54 dB | −0.54 dB | −3.2 % | −0.45 dB |
| 10⁻⁶ | 0.26 | 1.9 × 10⁻⁸ | | | | | |
| 10⁻⁵ | 2.6 | 2.0 × 10⁻⁷ | +0.65 dB | +0.62 dB | +0.62 dB | +3.8 % | +0.52 dB |
| 10⁻⁴ | 26 | 2.2 × 10⁻⁶ | +1.42 dB | +1.36 dB | +1.35 dB | +8.5 % | +1.13 dB |
| 10⁻³ | 262 | 2.5 × 10⁻⁵ | +2.38 dB | +2.27 dB | +2.25 dB | +14.7 % | +1.86 dB |
| 10⁻² | 2621 | 3.2 × 10⁻⁴ | +3.67 dB | +3.48 dB | +3.45 dB | +23.5 % | +2.82 dB |

- **The rule of thumb** matches the exact Pd 90 % column within 0.03 dB. At
  Pd 50 % the required SNR is lower (13.9 dB at 1.9 × 10⁻⁸ per test), the
  "1 +" weighs more, and the exact saving is up to 0.2 dB larger. The range
  column is the fourth root of the Pd 50 % saving; range-dependent losses,
  such as the atmosphere, make the gain slightly smaller.
- **The per-test Pfa rises a little faster** than the per-cell value: as the
  threshold drops, neighbouring beams cross it together more often, and the
  effective tests per cell fall from 56 to 31.
- **A non-fluctuating target** (Swerling 0) saves about a fifth less at
  Pd 90 % and about as much at Pd 50 %. Its Pd 90 % needs only 1.7 dB more
  SNR than its Pd 50 %, against 8.3 dB for Swerling 1 (both at 1.9 × 10⁻⁸ per
  test, computed with `required_snr_db`): the wide gap is the fluctuation's.
- **Non-coherent summation**, over channels (`BeamCombination.NONCOHERENT`)
  or collapsing cells, gives the detector several looks, and the closed form
  above no longer holds. Each decade then buys somewhat less: for a
  Swerling 1 target at Pd 90 %, raising the Pfa tenfold from 1.9 × 10⁻⁸ per
  test saves 0.61 dB with one look, 0.53 dB with four and 0.46 dB with sixteen
  (computed with `required_snr_db` and `n_pulses`). The gap between Pd 50 %
  and Pd 90 % stays at 8.3 dB, since the looks share one fluctuation. The
  tests per cell also depend on the looks, so for such a radar compute the
  trade with `Radar.false_alarm_budget` and `required_snr_db` rather than the
  rule.
- **Only receiver noise is counted.** Clutter, interference from other radars
  and strong returns near the radar also cross a lower threshold, and the
  toolbox does not count them. How many false alarms a tracker can carry is
  outside the toolbox.

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
