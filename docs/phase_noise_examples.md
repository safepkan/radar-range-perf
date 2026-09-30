# Worked example: a strong return at 2.3 m

Run the configurable single-return diagnostic with:

```sh
source venv/bin/activate
MPLBACKEND=Agg venv/bin/python examples/phase_noise.py --output-dir local/phase_noise_example
```

Omit `MPLBACKEND=Agg` to display it interactively as well. The script saves
`phase_noise.png` and `phase_noise.npz`; `--help` lists the waveform, sampling,
noise, window and output options.

For a progression of controlled examples, including visibility above thermal
noise, see [the phase-noise tutorial](phase_noise_tutorial.md) and run
`examples/phase_noise_tutorial.py`.

All curves are expected powers, not random noise realizations. The example
uses the Infineon typical CW TX spectrum as a shared source, real sampling
averaged over unknown carrier phase, and ideal IF filtering.

## Waveform

The defaults describe a CTRX8188F-like acquisition with real sampling:

| Setting | Default |
|---|---|
| Return range | 2.3 m |
| Slope | 39.0625 MHz/µs (400 MHz across the 10.24 µs payload) |
| ADC | Real, 50 MS/s, 512 samples |
| Chirps / PRI | 1024 / 15.96 µs |
| Velocity reference | 76.78 GHz, the centre of a 76.58–76.98 GHz payload |
| Source table | CTRX8188F 76–77 GHz, typical, constant extrapolation |
| Windows | Blackman–Harris (range), Hann (Doppler) |

This gives a 62.6566 kHz PRF, a 16.34304 ms CPI and 61.1881 Hz Doppler-bin
spacing. The beat at 2.3 m is **599.373 kHz**, and the unpadded range-bin
spacing is **0.3747 m**. The return falls between range bins; its largest bin
is at about 2.248 m. `--rf-band` selects the source table explicitly; a payload
crossing 77 GHz needs a choice between the two bands.

Checking doubled integration resolution at these settings requires
`--integration-oversample 8 --max-integration-points 8000000`. This increases
memory use; save it to a separate output directory for comparison.

With these assumptions, the prediction is approximately -66 dBc/bin in the
single-chirp range FFT and -94 dBc/bin in the range–Doppler FFT at the range bin
nearest the return. These refer to each plot's own carrier peak; use a measured
peak from the same processing stage when comparing with data. Doubling
quadrature resolution changes this range–Doppler column by less than
0.00001 dB. Predictions near the artificial 20 MHz oscillator-offset cutoff are
more sensitive to quadrature and the assumed spectral tail. The map color span
is capped at 20 dB to keep the main pedestal visible; darker regions can fall
below its displayed floor.

**Hardware IF filters are not included.** The CTRX8188F's analog high-pass
filter is second order, with its corner specified at -6 dB (datasheet Table 31,
page 41). A corner of a few hundred kHz shapes the sidebands of a 599 kHz beat,
which scaling by a measured peak does not undo. The datasheet's maximum usable
IF bandwidth at 50 MS/s is 22.5 MHz, whereas the ideal model passes up to
25 MHz; do not read its predictions near the filter edges as hardware behavior.
Channel combining, dummy-chirp settling and filter transients are not
represented by this stationary single-return model either.

## Figure: the return relative to its own peak

Read the six panels of `phase_noise.png` left to right, top row then bottom row.
No thermal noise is present in this figure.

* **A — source and residual SSB spectra.** Horizontal frequency is offset from
  the target beat, not beat frequency itself. The blue line is the assumed
  source spectrum; orange includes cancellation between the delayed return
  and receiver LO. Values are dBc **per Hz**. At 100 kHz the source is about
  -80 dBc/Hz and the residual about -120 dBc/Hz.
* **B — cancellation transfer.** This is the dB difference between the two
  spectra in A. A 2.3 m round trip gives about 15.34 ns delay. The shared
  phase noise is suppressed by about 40 dB at 100 kHz and 20 dB at 1 MHz.
  That weakening cancellation largely offsets the falling source spectrum,
  producing the nearly flat residual in A. A transfer of 0 dB would mean no
  suppression, not zero phase noise.
* **C — single-chirp range FFT.** Blue is phase noise, orange dashed is the
  deterministic carrier and its window leakage, and green is their sum in
  power. Here the units are dBc **per FFT bin**. The carrier peak is the 0 dBc
  reference. A bin collects noise over its window bandwidth, so the floor is
  about -65.94 dBc/bin near the return despite the roughly -120 dBc/Hz spectrum
  in A. Real sampling includes noise from both conjugate carrier lobes.
* **D — range–Doppler phase-noise map.** Only random phase-noise power is
  shown; the carrier and window leakage are excluded. For these settings,
  the floor near the return is approximately -94.34 dBc/bin. Its vertical
  extent means the noise occupies many Doppler bins, even though the return
  itself is stationary. The sharp drop near 80 m comes from the chosen 20 MHz
  oscillator-offset cutoff; it is not a prediction of the hardware IF filter or
  an intrinsic phase-noise boundary.
* **E — range cut at zero Doppler.** This is the corresponding row of D,
  with carrier and leakage added as separate curves. Relative to C, the
  phase-noise floor near the return is roughly 28.4 dB lower. In this example
  its broad noise spectrum gives nearly uncorrelated chirp contributions; 1024
  chirps with a Hann window give approximately `10*log10(1024/1.5) = 28.3 dB`
  improvement. The model calculates correlation explicitly; that gain is not
  universal.
* **F — Doppler cut at the peak range bin.** This selects about 2.248 m and
  shows the narrow zero-Doppler carrier response above the phase-noise floor.
  The broad, approximately flat floor here is consistent with D. Phase noise
  does not necessarily appear as a narrow Doppler skirt centered on a target;
  its appearance depends on its spectrum and the chirp sampling/processing.

The dBc normalization deliberately removes return strength. A -94 dBc/bin
prediction and a range–Doppler peak 100 dB above thermal imply phase noise
about 6 dB above thermal. A peak 90 dB above thermal puts that same
contribution about 4 dB below thermal. Use peak and thermal levels from the same
processing stage. The relative figure alone cannot establish visibility.
