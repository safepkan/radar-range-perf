# Reading the chamber diagnostic

Run the configurable single-return diagnostic with:

```sh
source venv/bin/activate
MPLBACKEND=Agg venv/bin/python examples/phase_noise.py --output-dir local/phase_noise_chamber
```

Omit `MPLBACKEND=Agg` to display it interactively as well. The script produces
the chamber diagnostic using supplied waveform settings, saving
`phase_noise.png` and `phase_noise.npz`. Its acquisition defaults match the
reported chamber waveform. FFT windows, RF reference and the shared-source
noise assumption still need to be matched to the measurement.

For a progression of controlled examples, including visibility above thermal
noise, see [the phase-noise tutorial](phase_noise_tutorial.md) and run
`examples/phase_noise_tutorial.py`.

All curves are expected powers, not random noise realizations. The example
uses the Infineon typical CW TX spectrum as a shared source, real sampling
averaged over unknown carrier phase, and ideal IF filtering. It is not yet a
reconstruction of the chamber measurement.

## Reported chamber acquisition

The reported CTRX8188F measurement settings are:

| Setting | Reported value |
|---|---|
| Reflector range | 2.3 m |
| RF start frequency / payload bandwidth | 76.58 GHz / 400 MHz |
| ADC | Real, 50 MS/s, 512 samples (10.24 µs payload) |
| Chirps / PRI | 1024 / 15.96 µs |
| RX channels / gain setting | All / -3 dB |
| TX selection | Individual TX, or TX1 + TX6 + TX7 + TX8 |
| Analog high-pass setting | 300 kHz |
| Waiting / flyback time | 60 ns / 60 ns |
| Pre-payload time | 5.54 µs = 277 × 20 ns |
| Dummy chirps | 1, in addition to the 1024 retained chirps |

The ADC duration is consistent with the sample count and rate. The supplied PRI
gives a 62.6566 kHz PRF, a 16.34304 ms CPI and 61.1881 Hz Doppler-bin spacing,
assuming 1024 retained chirps with the same TX configuration. The dummy chirp
is excluded from this calculation. An alternating TX schedule would require
the sampling times of the selected channel sequence instead.

The listed segments sum to 15.90 µs, leaving 60 ns of the stated PRI unspecified.
The model uses the reported 15.96 µs PRI directly; it does not infer that interval
from the individual segments. Pre-payload and dummy-chirp settling are outside
the stationary model.

The 400 MHz bandwidth covers the 10.24 µs ADC payload, giving

$$
S=\frac{400\,\mathrm{MHz}}{10.24\,\mathrm{\mu s}}
 =39.0625\,\mathrm{MHz/\mu s}
 =39.0625\,\mathrm{THz/s}.
$$

The resulting beat at 2.3 m is **599.373 kHz**, and the unpadded range-bin spacing
is **0.3747 m**. A slope of 390.6 THz/s would instead sweep about 4 GHz during
the payload and is inconsistent with the reported bandwidth.

Range/Doppler windows still need confirmation before comparing bin levels with
measurements. Whether 76.58 GHz denotes the start of the payload or an earlier ramp segment
also matters for selecting the RF-band source table. A 400 MHz payload beginning
at 76.58 GHz stays below 77 GHz; the same payload after 5.54 µs of ramping from
76.58 GHz would cross 77 GHz.

The default run uses the lower-band typical source table, Blackman–Harris/Hann
windows, and 76.78 GHz as a representative frequency for velocity conversion,
assuming a payload spanning 76.58–76.98 GHz. Override the reference with
`--center-frequency-ghz`. It does not determine the source spectrum;
`--rf-band` selects that table explicitly.

At these acquisition settings, checking doubled integration resolution requires
`--integration-oversample 8 --max-integration-points 8000000`. This increases
memory use; save it to a separate output directory for comparison.

With these assumptions, the prediction is approximately -66 dBc/bin
in the single-chirp range FFT and -94 dBc/bin in the range–Doppler FFT at the
range bin nearest the reflector. These refer to each plot's own carrier peak;
use a measured peak from the same processing stage when comparing visibility.
Doubling quadrature resolution changes this
range–Doppler column by less than 0.00001 dB. Predictions near the artificial
20 MHz oscillator-offset cutoff are more sensitive to quadrature and the
assumed spectral tail. The map color span is capped at 20 dB to keep the main
pedestal visible; darker regions can fall below its displayed floor.

The 300 kHz high-pass response is **not included** in these plots. Table 31,
page 41 of the supplied Infineon datasheet describes a second-order analog
high-pass filter with a **-6 dB** corner, not a single-pole -3 dB corner. Its
response matters at the reflector's approximately 599 kHz beat. Scaling the plots by a
measured carrier peak does not fully account for frequency-dependent filtering
of the noise sidebands. The datasheet also lists a 22.5 MHz maximum usable IF
bandwidth at 50 MS/s; the model's ideal Nyquist passband extends to 25 MHz.
Avoid treating its filter-edge predictions as hardware behavior.

RX gain and reflector RCS are not inputs to the relative dBc calculation.
Compare against a single RX channel and a fixed TX configuration first;
channel combining, dummy-chirp settling and hardware filter transients are not
represented by this stationary single-return model.

## Figure: a return at 2.3 m, relative to its own peak

The default scenario in `phase_noise.png` uses a waveform with
39.0625 MHz/µs slope, 50 MS/s, 512 samples per chirp, 1024 chirps and 15.96 µs chirp
spacing. The assumed range window is Blackman–Harris and Doppler window is Hann.
The sampling duration is 10.24 µs, sampled bandwidth 400 MHz, range-bin spacing
about 0.3747 m and Doppler-bin spacing 61.188 Hz. The nominal 2.3 m return falls
between range bins; its largest bin is at about 2.248 m. No thermal noise is
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
  about -65.94 dBc/bin near the reflector despite the roughly -120 dBc/Hz spectrum in A.
  Real sampling includes noise from both conjugate carrier lobes.
* **D — range–Doppler phase-noise map.** Only random phase-noise power is
  shown; the carrier and window leakage are excluded. For these settings,
  the floor near the reflector is approximately -94.34 dBc/bin. Its vertical
  extent means the noise occupies many Doppler bins, even though the reflector
  itself is stationary. The color span is capped at 20 dB. The sharp drop near
  80 m comes from the chosen 20 MHz oscillator-offset cutoff; it is not a
  prediction of the hardware IF filter or an intrinsic phase-noise boundary.
* **E — range cut at zero Doppler.** This is the corresponding row of D,
  with carrier and leakage added as separate curves. Relative to C, the
  phase-noise floor near the reflector is roughly 28.4 dB lower. In this example its broad noise
  spectrum gives nearly uncorrelated chirp contributions; 1024 chirps with a
  Hann window give approximately `10*log10(1024/1.5) = 28.3 dB` improvement.
  The model calculates correlation explicitly; that gain is not universal.
* **F — Doppler cut at the peak range bin.** This selects about 2.248 m and
  shows the narrow zero-Doppler carrier response above the phase-noise floor.
  The broad, approximately flat floor here is consistent with D. Phase noise
  does not necessarily appear as a narrow Doppler skirt centered on a target;
  its appearance depends on its spectrum and the chirp sampling/processing.

The dBc normalization deliberately removes return strength. A -94 dBc/bin
prediction and a measured range–Doppler peak 100 dB above thermal imply phase
noise about 6 dB above thermal. A peak 90 dB above thermal puts that same
contribution about 4 dB below thermal. Use peak and thermal levels from the same
processing stage. The relative figure alone cannot establish visibility.
