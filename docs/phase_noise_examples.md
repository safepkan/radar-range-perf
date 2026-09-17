# Reading the chamber diagnostic

Run the configurable single-return diagnostic with:

```sh
source venv/bin/activate
MPLBACKEND=Agg venv/bin/python examples/phase_noise.py --output-dir local/phase_noise
```

Omit `MPLBACKEND=Agg` to display it interactively as well. The script produces
the chamber diagnostic using supplied waveform settings, saving
`phase_noise.png` and `phase_noise.npz`. Its defaults are illustrative;
substitute the measured settings for comparison with chamber data.

For a progression of controlled examples, including visibility above thermal
noise, see [the phase-noise tutorial](phase_noise_tutorial.md) and run
`examples/phase_noise_tutorial.py`.

All curves are expected powers, not random noise realizations. The example
uses the Infineon typical CW TX spectrum as a shared source, real sampling
averaged over unknown carrier phase, and ideal IF filtering. It is not yet a
reconstruction of the chamber measurement.

## Figure: a return at 2.3 m, relative to its own peak

The default scenario in `phase_noise.png` uses a waveform with
40 MHz/µs slope, 20 MS/s, 256 samples per chirp, 64 chirps and 25 µs chirp
spacing. The range window is Blackman–Harris and the Doppler window is Hann.
The sampling duration is 12.8 µs, sampled bandwidth 512 MHz, range-bin spacing
about 0.293 m and Doppler-bin spacing 625 Hz. The nominal 2.3 m return falls
between range bins; its largest bin is at about 2.342 m. No thermal noise is
present in this figure.

Read the six panels left to right, top row then bottom row:

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
  around -65 to -68 dBc/bin despite the roughly -120 dBc/Hz spectrum in A.
  Real sampling includes noise from both conjugate carrier lobes.
* **D — range–Doppler phase-noise map.** Only random phase-noise power is
  shown; the carrier and window leakage are excluded. For these settings,
  the floor is approximately -81 to -84 dBc/bin. The color scale spans only
  about 3 dB, so the bright and dark stripes indicate modest changes. Their
  vertical extent means the noise occupies many Doppler bins, even though
  the reflector itself is stationary.
* **E — range cut at zero Doppler.** This is the corresponding row of D,
  with carrier and leakage added as separate curves. Relative to C, the
  phase-noise floor is roughly 16.3 dB lower. In this example its broad noise
  spectrum gives nearly uncorrelated chirp contributions; 64 chirps with a
  Hann window give approximately `10*log10(64/1.5) = 16.3 dB` improvement.
  The model calculates correlation explicitly; that gain is not universal.
* **F — Doppler cut at the peak range bin.** This selects about 2.342 m and
  shows the narrow zero-Doppler carrier response above the phase-noise floor.
  The broad, approximately flat floor here is consistent with D. Phase noise
  does not necessarily appear as a narrow Doppler skirt centered on a target;
  its appearance depends on its spectrum and the chirp sampling/processing.

The dBc normalization deliberately removes return strength. A -83 dBc/bin
prediction and a measured peak 90 dB above thermal imply phase noise about
7 dB above thermal. A peak only 70 dB above thermal puts that same contribution
about 13 dB below thermal. The relative figure alone cannot establish visibility.
