# Building intuition for radar phase noise

The tutorial changes one ingredient at a time to show why phase noise can look
like a broad pedestal, a localized patch, or a stripe across Doppler. Some
lessons use deliberately simple synthetic spectra. They explain mechanisms;
they are not additional Infineon specifications or predictions for the chamber.

```sh
source venv/bin/activate
MPLBACKEND=Agg venv/bin/python examples/phase_noise_tutorial.py \
    --output-dir local/phase_noise_tutorial
```

Open `local/phase_noise_tutorial/index.html` for the gallery. Each figure has a
question and takeaway, and a companion NPZ with numeric arrays and settings.
Without `MPLBACKEND=Agg`, the figures also open interactively. To run one lesson:

```sh
venv/bin/python examples/phase_noise_tutorial.py --lesson doppler
```

The lesson choices are `delay`, `mapping`, `windows`, `doppler`, `sampling`,
`visibility`, and `all`. A run's gallery contains the selected lessons only;
existing artifacts from previous runs are retained. The default output folder
is `radarperf_phase_noise_tutorial` under the platform temporary directory.

The chamber diagnostic is `examples/phase_noise.py`, with configurable waveform
settings and `phase_noise.png` / `phase_noise.npz` outputs. Its defaults are
illustrative. The tutorial's sixth lesson uses `--visibility-*` controls to
set the reflector range and return levels relative to thermal noise.

## Before the plots: what is fluctuating?

A perfect return is a tone with steadily advancing phase. Phase noise adds a
small random departure from that phase. A constant phase error merely rotates
the tone; a time-varying error introduces spectral energy away from it.

For small phase error, `A * exp(j*epsilon)` is approximately
`A + j*A*epsilon`. The first term is the carrier, and the second is its
phase-noise contribution. Both scale with the return amplitude. That is why
the phase-noise/carrier ratio can stay fixed while the absolute noise floor
rises with a stronger reflector.

FMCW adds a useful twist: the return and receiver LO can share the same source.
The receiver compares its phase now with its phase at the earlier transmit
time. If the source hardly changes during that delay, much of its noise cancels.
Noise introduced independently after the paths separate does not get this
cancellation. These are two separate correlations: sharing a source between TX
and RX, and retaining correlation between chirps in a CPI.

Throughout the tutorial:

* **Offset frequency** means offset from the return's beat tone, not the beat
  frequency or RF carrier frequency itself.
* **dBc/Hz** is spectral density; **dBc/bin** includes the FFT window bandwidth.
* Curves and maps are **expected powers**, not individual noisy measurements.
* Phase-noise-only plots omit the deterministic carrier, its window leakage,
  and thermal noise unless explicitly labeled otherwise.
* Small-phase errors, ideal IF filtering and no range migration are assumed.
  MIMO, channel combining, actual IF responses and saturation are not modeled.

The delay transfer follows Eq. 10 in
[Siddiq et al., *Phase Noise in FMCW Radar Systems*](https://purehost.bath.ac.uk/ws/files/186750499/Phase_Noise_in_FMCW_Radar_Systems.pdf).
The [model guide](phase_noise.md) explains the numerical method and conventions.

## 1. Delay: common noise can cancel

**Question:** How can the same oscillator yield different residual noise at
different target ranges?

`01_delay.png` holds the source spectrum and received carrier power fixed,
changing only the return delay. It uses the Infineon lower-band typical CW TX
spectrum, provisionally assigned entirely to the shared source. Constant
extrapolation below the first 10 kHz data point is shaded gray.

Panel A compares 2.3, 25 and 150 m. In the short-delay/low-offset region, the
transfer is approximately `(2*pi*f*delay)**2`. Doubling delay then raises the
residual by about 6 dB at fixed received carrier power. This does **not** mean
a physical reflector becomes noisier in absolute terms when moved farther
away: its received power would generally change too, which is held fixed here.

Panel B applies the transfer to the same source spectrum. At 2.3 m the result
is almost flat over part of the spectrum. At 150 m, periodic nulls become
visible. The first null is near 1 MHz because the delay is approximately
1 µs: phase fluctuations at that offset complete one cycle over the delay.
The transfer is not monotonic with range at a fixed offset. Its peaks can
reach +6 dB; that is the difference of two correlated phase contributions,
not additive thermal noise being amplified by a passive path.

Panel C adds a **synthetic** independent residual of -130 dBc/Hz. It fills
the delay nulls. Deep ideal nulls should therefore not be read as guaranteed
low-noise bins in a real device. Finite FFT windows would also smooth them.

**Takeaway:** Both the spectrum and the path relationship matter. One TX
phase-noise number cannot by itself predict the noise around a measured return.

## 2. Slope: the same frequency offset lands at a different range

**Question:** What changes if we program a steeper chirp?

`02_mapping.png` keeps a 10 m return, carrier power, source spectrum, sample
rate and observation duration fixed. Only slope changes: 5 versus 20 MHz/µs.
The relation is `range_offset = c * frequency_offset / (2*slope)`.

Panel A relabels the same continuous residual spectrum in range-offset
coordinates. A four-times steeper slope compresses the structure into
one-quarter the distance. The ordinate remains **per Hz**, not per metre;
this is a change of horizontal coordinate, not a density-unit conversion.

Panel B performs the actual single-chirp range FFT with the same 512 samples
at 10 MS/s and Blackman–Harris window. The low-noise region near the return
narrows in metres as slope increases. The carrier is omitted. Powers are
referenced to an ideal unit carrier to avoid a change in peak-bin straddle
becoming another apparent noise-level change.

The two waveforms also have different sampled bandwidth and range resolution,
as they must when slope changes at fixed sampling duration. The displayed
range-offset interval lies inside both IF passbands. Complex IF is used to
isolate the mapping from the conjugate-lobe effect of real sampling.

**Takeaway:** Range structure is a waveform-dependent view of frequency
structure. Changing slope does not simply make the source quieter or noisier.

## 3. Windows: a deterministic skirt can look like noise

**Question:** Are we looking at oscillator noise or FFT leakage from the target?

`03_windows.png` processes the same off-bin 25 m return with rectangular
(`boxcar`), Hann and Blackman–Harris range windows. The source, delay, waveform
and sampling mode remain fixed. Only the window changes.

The rectangular window leaves prominent deterministic sidelobes, which mask
the random phase-noise floor over the displayed region. Hann reduces that
leakage, while Blackman–Harris reveals the floor much closer to the main lobe.
The main lobe also broadens; a lower-sidelobe window is not a free improvement
in target separation or noise bandwidth.

Window equivalent noise bandwidths are approximately 1.00, 1.50 and 2.00 FFT
bins respectively. Their phase-noise-per-bin levels can therefore differ,
even with unchanged source noise. Each plot references that window's own
sampled carrier peak; off-bin peak losses also contribute to level differences.
The saved peak powers allow conversion to a common ideal-carrier reference.

**Takeaway:** Window experiments help distinguish deterministic leakage from
random noise, but compare the window bandwidth and peak normalization too.
A single plot shape alone does not prove phase noise.

## 4. Doppler: a pedestal, a patch, and a stripe

**Question:** Why does phase noise sometimes fill Doppler and sometimes stay
near the target?

`04_doppler.png` uses three **synthetic independent-path residual** cases, not
the Infineon TX table. This removes delay cancellation as a changing variable
and avoids inventing missing close-in chipset data. The broad and slow spectra
are normalized to the same two-sided integrated phase variance, `1e-4 rad²`
(0.01 rad RMS), over 1 Hz to 1 MHz before IF filtering.

The waveform is 2 MHz/µs, 2 MS/s, 128 samples, 128 chirps, 100 µs spacing, with
Blackman–Harris/Hann windows. The return is on a range bin at about 37.47 m
and at zero Doppler. All three maps use identical color limits and complex IF.

1. **Broad residual, stationary:** noise power is spread broadly over range
   and Doppler. There is no special zero-Doppler concentration in the shown
   region, even though the reflector itself is stationary.
2. **Slow residual, stationary:** most phase fluctuations are at low offset
   frequencies (roughly a few hundred Hz). They change little within a chirp
   and remain correlated across successive chirps. Noise is concentrated
   around the target's range and Doppler, forming a localized patch.
3. **The same slow residual, independent chirps:** the within-chirp spectrum,
   variance, target and windows are unchanged. Only cross-chirp covariance is
   set to zero. The narrow range structure remains but now stretches across
   Doppler, forming a vertical stripe. The lower panel shows its flat Doppler
   profile at the target range bin.

The center and right maps have the same total noise power when summed over
Doppler at each range bin, up to numerical error. Their different appearance
comes from redistribution across Doppler, not adding noise. The two input
spectra have equal variance before IF filtering, but do not necessarily retain
identical total power after IF filtering and finite-window processing.

Independent chirps are a controlled modeling assumption, not a prediction of
any particular PLL reset behavior. Actual settling errors require another model.

**Takeaway:** Coherent chirp integration does not give every phase-noise
component the same rejection. Correlation determines where its power ends up.

## 5. Real sampling: the other carrier lobe contributes

**Question:** Is changing real/complex sampling just a display convention?

`05_sampling.png` compares complex IF with phase-averaged real sampling at
the same sample rate, using the same window and an on-bin return at about
4.684 m. A real signal has conjugate carrier lobes; noise from both contributes
to the positive-frequency spectrum.

The left column uses a synthetic flat residual. The other lobe contributes
equally, giving the familiar 3.01 dB increase. The right column uses a shaped
residual. Its other-lobe contribution is much smaller near the positive
carrier but matters more elsewhere, so the increase varies with range.
The bottom row plots the real-minus-complex difference directly.

These are synthetic residual spectra, not chipset data. The real mode averages
over the unknown reflector phase; near overlapping lobes it is an ensemble
prediction, not an exact fixed-phase real-ADC realization. The comparison
keeps source PSD and carrier reference fixed; it does not assert a universal
3 dB system-SNR advantage for a particular complex-sampling device.

**Takeaway:** Include the conjugate lobe when matching real ADC measurements;
a blanket 3 dB correction is insufficient for a shaped spectrum.

## 6. Visibility: return power against a fixed thermal floor

**Question:** When does a phase-noise contribution become visible?

`06_visibility.png` shows a stationary return at 25 m.
It uses the Infineon typical CW spectrum as shared noise, real sampling,
10 MHz/µs slope, 10 MS/s, 512 samples, 128 chirps and 64 µs chirp spacing.
The window pair is Blackman–Harris/Hann. Spectra outside the datasheet offsets
are held constant; the integrated offset band is 1 Hz to 10 MHz.

The stronger carrier peak is supplied as 75 dB above thermal power per
range–Doppler bin. The weaker return is 10 dB lower, at the same delay.
These are illustrative **processed peak ratios**, not input SNR, ADC headroom,
TX-backoff settings or an RCS-based prediction of a particular object.

| Case | Maximum PN/thermal | Maximum combined noise floor rise |
|---|---:|---:|
| Stronger return | +3.90 dB | 5.39 dB |
| Return 10 dB weaker | -6.10 dB | 0.95 dB |

Panel A includes the carrier, window leakage, phase noise and thermal noise.
Panel B isolates thermal plus phase noise. C and D show that floor rise over
range and Doppler on the same color scale. Phase-noise-only plots exclude
the main lobe; its absence is deliberate, not target suppression.

The floor rise is `10*log10(1 + phase_noise_power/thermal_power)`. Phase noise
equal to thermal therefore raises the combined floor by 3.01 dB. Noise below
thermal is still present, and can be measurable after sufficient averaging.

```sh
venv/bin/python examples/phase_noise_tutorial.py --lesson visibility \
    --visibility-range-m 25 \
    --visibility-peak-snr-db 75 \
    --visibility-drop-db 10
```

**Takeaway:** A constant dBc skirt can move above or below thermal as return
strength changes. Keep the thermal reference fixed to make this visible.

## What to try next

Read the lessons in order initially. Then use `--lesson` to revisit a single
comparison. The functions in `examples/phase_noise_tutorial.py` keep the
waveforms and synthetic spectra close to their plots, so changing one parameter
is straightforward. Try a different delay in lesson 1, move the return onto a
bin in lesson 3, or change the close-in bandwidth in lesson 4. Avoid changing
several ingredients together before checking the individual effects.

Increase `--integration-oversample` to check numerical convergence; lesson 4
uses at least 8 because its close-in spectrum needs finer resolution. Window
bandwidth, FFT-bin power, and sample timing should remain explicit when
comparing with measured data. Use the separate chamber script for that work.
