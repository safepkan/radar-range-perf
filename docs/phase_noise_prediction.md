# Predicting a strong return's phase noise

`radarperf.phase_noise.phase_noise_fft` predicts the expected range or
range–Doppler FFT of one return whose LO carries phase noise, relative to the
return's own peak. It needs no antenna gain, RCS, transmit power or link
budget. It serves two purposes: comparing a measured skirt or pedestal with the
prediction, and estimating the floor that a strong return sets around it, which
can exceed the thermal noise. The link budget does not include that floor
yet.

This page covers its use, conventions and numerics.
[phase_noise.md](phase_noise.md) explains the physics behind it: the delay
filter, the per-chirp error, the pedestal and the skirt.

## Quick start

```python
from radarperf import FmcwWaveform
from radarperf.phase_noise import (
    SingleReturnPhaseNoise,
    ctrx8188f_phase_noise,
    phase_noise_fft,
)
from radarperf.plotting import plot_phase_noise_cut, plot_phase_noise_map

waveform = FmcwWaveform.from_slope(
    center_frequency_hz=77e9,
    chirp_slope_hz_per_s=11.67e12,
    sample_rate_hz=50e6,
    n_samples=512,
    n_chirps=256,
    chirp_repetition_time_s=36e-6,
)
lo = ctrx8188f_phase_noise(rf_band="76-77", extrapolation="constant")
model = SingleReturnPhaseNoise.from_range(150.0, shared=lo)
result = phase_noise_fft(
    model,
    waveform,
    offset_band_hz=(1.0, 20e6),
    sampling="real_phase_averaged",
    range_window="hann",
    doppler_window="hann",
)
plot_phase_noise_map(result)
plot_phase_noise_cut(result)  # range cut at the return's Doppler
plot_phase_noise_cut(result, axis="doppler")  # Doppler cut at the return's range

# In the units of a measured peak, e.g. dBFS or dBm per cell:
measured_peak_level = -20.0  # illustrative
predicted_noise_level = measured_peak_level + result.phase_noise_dbc
```

`examples/phase_noise.py` runs a configurable version of this and saves a
six-panel figure and its arrays. Its defaults describe the worked example
below; `--help` lists the waveform, sampling, noise, window and output
options. For a range FFT of one chirp, pass `range_doppler=False`; the chirp
count and period then play no part.

## The model

**The return.** `SingleReturnPhaseNoise(delay_s, shared=..., independent=...)`
describes one return. `from_range` converts a range to the round-trip delay.
The `shared` spectrum is the LO's phase noise, which TX and RX share; it
reaches the return through the delay filter 4 sin²(πfτ). The `independent`
spectrum is the sum of any TX and RX noise that is not shared, each part
counted once, and it is added without filtering. Either may be left out.
`differential_delay_s` changes only the delay of the filter, for a hardware
path imbalance in a radar whose range is already calibrated. A negative total
is allowed, for an LO path longer than the echo's.

**First order.** `phase_noise_fft` models the return as carrier·(1 + jε), with ε
the residual phase. It predicts the noise that the jε term spreads over range
and Doppler. It does not lower the carrier by the matching $e^{-\sigma^2}$, which
[phase_noise.md: “The Doppler integration loss”](phase_noise.md#the-doppler-integration-loss)
derives. That loss is in the link budget, not here. The first-order model
needs a residual phase variance much smaller than 1 rad². The result reports
it for the integrated band as `residual_variance_rad2`, and
`SingleReturnPhaseNoise.residual_variance_rad2(band)` computes it without an
FFT prediction. Check it for steep or large spectra and long delays.

**Spectra.** `TabulatedPhaseNoise` holds SSB levels in dBc/Hz and interpolates
them linearly in dB against log offset. Each linear level is the two-sided
density at that signed offset; no further factor of two is applied. Outside
the table it raises by default (`extrapolation="error"`); `"constant"` holds
the end levels and `"slope"` extends the end segments. Neither is a
specification. Any object with an `ssb_linear_per_hz(offset_hz)` method can
serve as a spectrum.

**The offset band.** `offset_band_hz` is required. It bounds the positive
offsets from the return; both signs are included, and everything outside the
band is zero. A result is the contribution of that band only. `(1e4, 1e7)`
gives the part the CTRX8188F table supports, not the whole skirt.

## Range, Doppler and sampling

For a positive slope S the model uses

$$
f_b = S\tau + f_D, \qquad R_{\mathrm{apparent}} = \frac{c f_b}{2S}, \qquad v = \frac{\lambda f_D}{2}.
$$

Positive Doppler and velocity mean a phase that advances over the chirps in
the modelled complex signal; check the measurement's mixer and FFT sign
conventions against it. The apparent range includes the range–Doppler
coupling and is not corrected for motion. The beat frequency and Doppler must
be unambiguous. Range migration during the CPI is not modelled.

**Sampling.** The waveform does not record whether the IF is real or complex,
so `sampling` states it. The CTRX8188F samples a real IF.

- `"complex"`: one complex beat tone, with signed range frequencies.
- `"real_phase_averaged"`: both beat lobes, at +f_b and −f_b, contribute noise
  to the positive frequencies, which are all the result keeps, from DC up to
  Nyquist. Powers are normalized to the positive lobe and averaged over the
  unknown carrier phase of the reflection. Where the skirt is flat, the other
  lobe doubles it (+3 dB). Near DC, or where the lobes overlap, this is an
  ensemble prediction, not a simulation of one real ADC record.

**The IF filter** is ideal: unity within ±f_s/2 and zero outside, ahead of the
sampling. The CTRX8188F's high-pass is not modelled. Its second-order filter,
−6 dB at the 300 kHz setting, cuts a return at low IF but not its skirt
several MHz away. Scaling by a measured peak then needs the filter's gain at
the return's beat frequency, or a comparison away from the filter's edges.
`noise_bandwidth_hz` on the waveform is a scalar and does not enter here.
Aliasing of out-of-band noise in the ADC is not modelled; aliasing in slow
time, from sampling once per chirp, is.

**Correlation between chirps.** `chirp_correlation="stationary"` (the default)
samples one stationary process at the actual sample times, including the gaps
between chirps. `"independent"` keeps the correlation within each chirp and
removes it between chirps, which spreads every range cell's noise evenly over
Doppler. Neither describes a synthesizer that has not settled between ramps:
its excess, with a spectrum that rises towards half the chirp rate, is not
modelled
([phase_noise.md: “Chirp timing and settling”](phase_noise.md#chirp-timing-and-settling)).

### How folding enters the range–Doppler map

For the stationary, complex-sampled model, write f_r = 1/T_r for the chirp
rate. Sampling the residual phase once per chirp folds its spectrum:

$$
S_{\mathrm{fold}}(\nu) = \sum_{m} S_{\Delta\varphi}(\nu + m f_r), \qquad -f_r/2 \le \nu < f_r/2 .
$$

The delay filter belongs inside each term, at the original offset ν + m f_r,
not at the folded one. The spectrum must be band-limited for the sum to
converge.

The range FFT weights each original offset by where it lands in range. For
range bin k at beat frequency $f_{r,k}$, with W_r and W_d the range and Doppler
windows' responses (each normalized by its sum) and H_IF the IF filter,

$$
S_k(\nu) = \sum_m S_{\Delta\varphi}(\nu + m f_r)\,\left|H_{\mathrm{IF}}(f_b + \nu + m f_r)\right|^2 \left|W_r(f_b + \nu + m f_r - f_{r,k})\right|^2 ,
$$

and the expected noise in Doppler bin ℓ, relative to an ideal on-bin carrier,
is

$$
P_{k,\ell} = \int_{-f_r/2}^{f_r/2} S_k(\nu)\,\left|W_d(f_D + \nu - f_{d,\ell})\right|^2 d\nu .
$$

Offsets one chirp rate apart share a Doppler cell, but they land at
different ranges: at a 10 kHz chirp rate, a +12 kHz offset folds to +2 kHz in
Doppler but sits c·(12 kHz)/(2S) away in range. Summing the source spectrum
without the range weighting would miss that. `phase_noise_fft` computes all
of this through the covariance at the actual sample times, so its output needs
no further folding.

## Normalization and comparison with measurements

Raw powers (`phase_noise_power`, `carrier_power`) use FFT amplitudes divided
by the window sums, so a complex carrier on a bin peaks at 1. The `*_dbc`
properties instead refer to the largest carrier cell in the result, which
includes the window's straddle loss for a return between bins. That is the
reference to use with a measured peak: add the measured peak level to
`phase_noise_dbc` for the expected noise in the same units. `carrier_power`
holds the deterministic window response; `total_dbc` adds carrier and noise in
power. Thermal noise is not included.

Use the measurement's windows, zero padding, target position within its bin,
and processing stage. Compare power averages with these expected powers;
averaging dB values biases the result. A saturated or noisy measured peak is
not a clean reference. Channel summation is not modelled: a skirt has its
return's spatial signature, so a measurement after channel summation needs
[phase_noise.md: “Every channel carries the same noise”](phase_noise.md#every-channel-carries-the-same-noise).

A skirt that keeps its dBc level as the return's power changes fits phase
noise, but other multiplicative disturbances behave the same way. A window
change helps tell the window's leakage from noise: leakage changes strongly
with the window, noise mainly through the window's noise bandwidth.

## Worked example: a strong return at 2.3 m

`examples/phase_noise.py` with its defaults models a strong return at 2.3 m,
such as a reference reflector in a small measurement chamber, with a
CTRX8188F-like waveform:

| Setting | Default |
|---|---|
| Return range | 2.3 m |
| Slope | 39.06 MHz/µs (400 MHz over the 10.24 µs payload) |
| ADC | Real, 50 MS/s, 512 samples |
| Chirps, period | 1024, 15.96 µs |
| Velocity reference | 76.78 GHz |
| Spectrum | CTRX8188F 76–77 GHz, typical, constant extrapolation, all shared |
| Offset band | 1 Hz–20 MHz |
| Windows | Blackman–Harris (range), Hann (Doppler) |

The beat is 599.4 kHz and the range bins are 0.375 m apart, so the return
falls between bins; its largest cell is at 2.248 m. At 2.3 m the delay is
15.3 ns, and the delay filter suppresses the LO's noise by 40 dB at 100 kHz and
20 dB at 1 MHz, leaving a residual of about −120 dBc/Hz from 0.1 to 10 MHz.

- **One chirp's range FFT** has −66 dBc per bin next to the return. Each bin
  collects the residual over the window's noise bandwidth (196 kHz), and real
  sampling adds the other lobe's skirt.
- **The range–Doppler map** has −94 dBc per cell, about 28 dB lower. The noise
  is nearly independent from chirp to chirp, so the Doppler FFT gains
  10 log₁₀(1024/1.5) = 28.3 dB on the carrier over it. The model computes the
  correlation; that gain is not universal.
- **The noise fills every Doppler cell,** although the return is stationary.
  The fall beyond about 80 m comes from the 20 MHz edge of the offset band, not
  from the hardware.
- **Measured** on the CARKIT radar in a chamber, with a reflector at
  2.2–2.5 m, the skirt at 1–12 MHz offset lay 2.3–3.1 dB below the typical
  table's prediction, and between the typical and maximum tables at
  0.3–0.5 MHz ([CARKIT study, README.md: “A strong return's phase-noise
  skirt”](../studies/2026-09-11_carkit-validation/README.md#a-strong-returns-phase-noise-skirt)).

The dBc levels leave out the return's strength. A range–Doppler peak 100 dB
above the thermal noise per cell puts −94 dBc per cell 6 dB above it; a peak
90 dB above, 4 dB below it. The CARKIT reflector with its eight-TX beam was
strong enough to lift the floor at all ranges by 1.9–8.3 dB.

Doubling the quadrature resolution
(`--integration-oversample 8 --max-integration-points 8000000`) changes the
map near the return by less than 0.00001 dB.

## Numerical method and validation

Midpoint quadrature over the offset spectrum gives the band-limited IF
covariance. Sampling it at the actual fast- and slow-time lags and weighting
by the windows' autocorrelations gives the expected periodogram; the signed
lags are folded to the FFT sizes before a 2D FFT. A chirp period that is a
whole number of samples needs one covariance IFFT; any other period uses one
IFFT per chirp lag and keeps the fractional timing. Results are deterministic.

The grid resolves the CPI by `integration_oversample` (default 4) and puts at
least 16 intervals across the offset band. `integration_step_hz` reports the
spacing. Doubling the oversampling checks convergence for a region of
interest; narrow features, steep spectra and hard band edges need more.
`max_integration_points` guards against huge allocations and raises rather
than coarsening the grid.

The tests (`tests/test_phase_noise.py`) cover the table and its
interpolation, the delay filter and independent residuals, white-noise window
gains, peak normalization, zero padding, range and Doppler coordinates, the
real-sampling lobes, chirp correlation, convergence and the residual variance.
A direct frequency-domain integration checks the covariance method for whole
and fractional chirp periods. A Monte Carlo test checks it from first
principles: random LO phase noise on actual chirps, mixed with its delayed
echo, averages to the predicted map. Another test checks that the return's own
range cell, summed over Doppler, holds the per-chirp phase variance that
`chirp_frequency_error_rms_hz` gives.

## Phase-noise data

**CTRX8188F.** `ctrx8188f_phase_noise(rf_band=..., level=...)` holds the
TX-port CW table of the target datasheet, rev. 0.20, Table 22
([phase_noise.md: “Phase noise and how it is specified”](phase_noise.md#phase-noise-and-how-it-is-specified)).
`level="maximum"` gives the specified maxima at the five offsets; values
interpolated between them are a model, not a guaranteed mask. A payload that
crosses 77 GHz needs a choice between the two bands. The table does not
separate shared from independent noise and does not describe chirping.
Assigning all of it to `shared` is an assumption, which the CARKIT
measurements support.

**TI AWR2243.** The [AWR2243 datasheet, SWRS223D, Section 7.7,
pp. 19–20](https://www.ti.com/lit/ds/symlink/awr2243.pdf) gives the typical RF
phase noise at 1 MHz offset only:

| VCO | RF coverage | Typical SSB level |
|---|---|---|
| VCO1 | 76–78 GHz | −96 dBc/Hz |
| VCO2 | 76–81 GHz | −94 dBc/Hz |

Its footnote 4 gives the synthesizer settings for these values. The
multi-offset clock specifications on p. 24 concern the 40 MHz reference
input, not the RF output. [SPRACV2, *Cascade Coherency and Phase Shifter
Calibration*](https://www.ti.com/lit/an/spracv2/spracv2.pdf) gives no RF
spectrum either. One offset cannot predict a skirt or a per-chirp error: both
depend on the spectrum's shape from 10 kHz to several MHz. Supply a measured
`TabulatedPhaseNoise`, or label any assumed shape as illustrative.
