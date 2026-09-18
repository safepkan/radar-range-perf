# Single-return phase-noise diagnostics

This module predicts the expected noise skirt of one strong return, independently
of antenna gain, RCS, transmit power and the link-budget engine. Outputs are
relative to the carrier. It is intended for comparison with single-channel
range spectra and range–Doppler measurements before integrating phase noise into
scene-level performance calculations.

## Quick start

```python
from radarperf import FmcwWaveform
from radarperf.phase_noise import (
    SingleReturnPhaseNoise, ctrx8188f_phase_noise, phase_noise_fft,
)
from radarperf.plotting import plot_phase_noise_cut, plot_phase_noise_map

# Illustrative settings: substitute the actual chamber waveform.
waveform = FmcwWaveform.from_slope(
    center_frequency_hz=76.5e9,
    chirp_slope_hz_per_s=40e12,
    sample_rate_hz=20e6,
    n_samples=256,
    n_chirps=64,
    chirp_repetition_time_s=25e-6,
)
source = ctrx8188f_phase_noise(extrapolation="constant")
model = SingleReturnPhaseNoise.from_range(2.3, shared=source)
result = phase_noise_fft(
    model, waveform,
    offset_band_hz=(1.0, 20e6),
    sampling="real_phase_averaged",
    range_window="blackmanharris",
    doppler_window="hann",
)
plot_phase_noise_map(result)
plot_phase_noise_cut(result)                 # range cut at carrier Doppler
plot_phase_noise_cut(result, axis="doppler") # Doppler cut at carrier range

# Same units as the measured peak, e.g. dBFS or calibrated dBm per FFT bin.
measured_peak_level = -20.0  # illustrative
predicted_noise_level = measured_peak_level + result.phase_noise_dbc
```

Run `MPLBACKEND=Agg venv/bin/python examples/phase_noise.py` after activating
the venv. It saves the six-panel chamber diagnostic (`phase_noise.png`) and its
NPZ arrays to `/tmp/radarperf_phase_noise` (platform temp directory). `--help`
lists waveform, sampling, noise, window and output options. Interactive runs
also show the figure. See [the chamber walkthrough](phase_noise_examples.md)
for its panels and scaling.

For a guided progression, run `examples/phase_noise_tutorial.py`. Its six lessons
cover cancellation, slope, windows, Doppler structure, sampling, and visibility
above thermal noise. It writes a local HTML gallery, PNGs and NPZ arrays; see
[the tutorial guide](phase_noise_tutorial.md). Its `--visibility-*` controls
set the reflector range and return levels for the visibility lesson.
No new dependencies are required.

For a single-chirp range FFT set `range_doppler=False`; chirp count and repetition
time then do not affect the result. Arbitrary finite real-valued window arrays
are accepted in addition to SciPy window names (periodic windows by default).

## Physical model and units

For a common source, the dechirped phase is the difference of delayed and
current oscillator phase. Its spectrum has the transfer

$$
K(f,\tau)=4\sin^2(\pi f\tau).
$$

In the small-phase approximation the two-sided complex-return noise PSD,
relative to carrier power, is

$$
S_\epsilon(f)=K(f,\tau_\mathrm{eff})\,10^{L_\mathrm{shared}(|f|)/10}
             +10^{L_\mathrm{independent}(|f|)/10}.
$$

SSB L is in dBc/Hz; each signed sideband gets that linear density, without an
extra factor of two. Integrating both sides supplies the factor of two in total
phase variance. Missing source terms are zero. Independent input is the sum of
independent residual contributions at the final RF frequency, each counted once.
It is not the receiver's additive thermal noise floor.

The source delay transfer follows Eq. 10 of
[Siddiq et al., *Phase Noise in FMCW Radar Systems*](https://purehost.bath.ac.uk/ws/files/186750499/Phase_Noise_in_FMCW_Radar_Systems.pdf).
The implementation uses the first-order signal `carrier * (1 + j*epsilon)`.
It does not model loss of coherence or carrier broadening at large phase variance.
Integrated residual phase variance must be much less than one radian squared;
the caller must check that assumption when supplying large or steep spectra.

`delay_s` sets the target beat delay. `differential_delay_s` changes the effective
noise delay only. This accommodates hardware imbalance when range has already
been calibrated; it does not predict the hardware's beat-frequency calibration.

For 2.3 m and zero additional delay, the delay is 15.34 ns. With the lower-band
typical Infineon spectrum entirely assigned to the shared source, residual SSB
levels at 100 kHz, 1 MHz, 5 MHz and 10 MHz are approximately -120.3, -120.3,
-122.4 and -121.7 dBc/Hz. Cancellation can therefore turn a falling source
spectrum into a fairly flat residual floor.

## Infineon data and extrapolation

The preset transcribes the TX-port **CW** values in the CTRX8188F Target Datasheet
v0.20, 2025-06-17, Table 22, pages 26–27, supplied for this project. It does not
read or package the PDF at runtime.

| Offset | 76–77 GHz typ/max | >77–81 GHz typ/max |
|---|---|---|
| 10 kHz | -79 / -73 | -78 / -73 |
| 100 kHz | -80 / -75 | -78 / -73 |
| 1 MHz | -100 / -97 | -98 / -95 |
| 5 MHz | -116 / -111 | -114 / -109 |
| 10 MHz | -121 / -115 | -120 / -114 |

All entries are dBc/Hz. `level="maximum"` selects the specified maxima;
interpolation between these points is a model, not a guaranteed mask. Select
the appropriate RF band explicitly, especially for ramps crossing 77 GHz.

The table does not specify a chirped spectrum or separate shared and independent
contributions. Assigning all TX noise to `shared` is an explicit simplifying
assumption, and may overestimate cancellation. The separate LO-output table is
not used to infer a residual by subtracting unrelated specifications.

`TabulatedPhaseNoise` interpolates linearly in dB versus log10 offset. The default
`extrapolation="error"` rejects out-of-table queries. `constant` holds endpoint
levels; `slope` extends endpoint slopes. The example explicitly chooses constant
extrapolation, including below 10 kHz: it is illustrative, especially for
close-in Doppler behavior. Replace the table with measured data when available.

`offset_band_hz` is mandatory and refers to positive oscillator offsets from the
return. Both signs are included; all contributions outside those bounds are
zero. Thus `(1e4, 1e7)` predicts only the datasheet-supported band contribution,
not the complete noise skirt. The smooth PSD API does not evaluate zero offset:
the carrier and finite-width FFT bins are handled separately.

## Range, Doppler and sampling

For positive slope S, this module defines

$$
f_b=S\tau+f_D,\qquad R_\mathrm{apparent}=cf_b/(2S),\qquad v_D=\lambda f_D/2.
$$

Positive Doppler and velocity mean positive phase advance in the modeled
complex signal. Check the measurement's mixer/FFT sign convention. Apparent
range includes Doppler coupling; it is not motion-corrected range. Target beat
and Doppler must be unambiguous. The model neglects range migration during a CPI.

The phase-noise calculation has an explicit sampling choice; existing waveform
and frontend objects do not currently track sampling mode or hardware sampling
capabilities. The Infineon example uses real sampling. Select complex sampling
explicitly for a TI configuration producing complex IF data.

* `complex`: one complex beat carrier, with signed range frequencies.
* `real_phase_averaged`: both conjugate beat lobes contribute. The output retains
  frequencies from DC up to (excluding) Nyquist. Carrier and noise powers are
  normalized to the positive lobe, and averaged over an unknown reflection
  carrier phase. For a broad flat skirt, including the other lobe can raise
  the positive-range noise by 3 dB relative to the complex model.

The real mode averages cross terms between lobes to zero. It is suitable as an
ensemble prediction; near DC/overlapping lobes, a fixed reflector phase can
matter and this is not an exact fixed-phase ADC simulation. No synthetic
Hilbert conversion is assumed. The carrier reference includes both lobes'
phase-averaged deterministic window responses.

The IF filter is ideal unity gain in `[-fs/2, fs/2)` and zero outside, applied
before sampling. The real mode uses the corresponding symmetric filter. Actual
CTRX8188F high-pass/decimation responses are not yet represented. The existing
waveform `noise_bandwidth_hz` is a scalar ENBW, insufficient to define a filter
shape, and is not used by this diagnostic. Compare away from filter edges until
the actual transfer function is incorporated. Out-of-band ADC aliasing is excluded;
slow-time aliasing from sampling at the chirp rate is included.

`chirp_correlation="stationary"` samples the same stationary process at
`m*chirp_repetition_time + n/sample_rate`, preserving correlation across gaps.
`"independent"` preserves within-chirp covariance but discards cross-chirp
covariance. Both are explicit assumptions; neither predicts reset/settling
transients. A phase-noise offset influences fast and slow time together, so a
range–Doppler map cannot generally be obtained by distributing a range skirt
uniformly over Doppler or by applying a blanket chirp integration gain.

## FFT normalization and measurement comparison

Raw result powers use FFT amplitudes divided by `sum(range_window) *
sum(doppler_window)`. A complex carrier exactly on a bin has unit peak power.
Off-bin targets have a smaller peak; zero padding samples the window response
more densely without changing physical integration gain.

The `phase_noise_dbc`, `carrier_dbc` and `total_dbc` properties instead reference
the largest deterministic carrier bin in that result. This is the normalization
to use when scaling by a measured peak. `carrier_power` contains deterministic
window leakage; `phase_noise_power` contains expected random noise power;
`total_dbc` adds them in linear power. Thermal noise is excluded.

With otherwise fixed gain, processing and source phase-noise characteristics,
reducing the return by 10 dB reduces the absolute phase-noise skirt by 10 dB
while its dBc level stays fixed. Visibility above a fixed thermal floor can
therefore disappear with another 10 dB TX backoff. This is consistent with the
reported chamber observation, but is not by itself proof of phase noise; this
model does not assess covariance eigenvalues or other signal-dependent effects.

Use the same FFT windows, padding, target bin offset and processing stage as the
measurement. Power-domain averages are comparable to these expected powers;
averaging logged magnitudes introduces a different statistical bias. A measured
peak contaminated by saturation or appreciable noise is not a clean carrier
reference. MIMO/channel summation and spatial phase-noise covariance are deferred.

## Numerical method and validation

Midpoint frequency quadrature supplies a band-limited IF covariance. Sampling
that covariance at actual fast/slow-time differences and multiplying by window
autocorrelations gives the expected FFT periodogram. Signed lags are folded to
the requested FFT sizes before a 2D FFT. Integer sample-period chirp timing
needs one covariance IFFT; arbitrary timing uses additional IFFTs, preserving
fractional timing without rounding chirp times. Results are deterministic.

The integration grid resolves the CPI by `integration_oversample` (default 4)
and places at least 16 intervals across the requested offset-band width.
`integration_step_hz` records the actual grid spacing. Double oversampling to
check convergence for the region of interest; narrow features or steep spectra
can need more resolution. Hard integration/filter boundaries are especially
sensitive. `max_integration_points` limits the frequency grid and raises if the
requested resolution would exceed it; it does not silently coarsen the model.

Tests cover table provenance, interpolation, delay limits, independent residuals,
white-noise FFT/window gain, peak normalization, zero padding, range/Doppler
coordinates, real-image contributions, chirp correlation, and convergence. A
separate direct frequency-mode integration verifies the covariance calculation
for both integer and fractional chirp timing.
