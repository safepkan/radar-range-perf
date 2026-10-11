# Infineon CTRX8188F

The CTRX8188F is a 76–81 GHz radar MMIC with eight transmit and eight receive
channels. This page collects what the toolbox uses about it: the datasheet's
figures, how to read them, and what measurements on one radar showed. The
datasheet and user manual are restricted (NDA) and kept outside the repository;
this page cites table numbers and short values only. [losses.md](../losses.md)
says where each term enters the range equation.

| Preset | What it holds |
|---|---|
| `frontend.ctrx8188f()` | 14.5 dBm per channel and a 10.2 dB noise figure: typical values at the 0 dB RX gain step and 10 MHz IF. Pass `noise_figure_db=9.7` for the +3 dB step |
| `phase_noise.ctrx8188f_phase_noise()` | The TX-port CW phase-noise table, both RF bands, typical and maximum ([phase_noise.md](../phase_noise.md)) |
| `phase_noise.ctrx8188f_chirp_settling()` | The per-chirp frequency error against the chirp timing, measured on one radar; illustrative |

## Datasheet figures

| Parameter | Typical | Limit | In the toolbox | Source |
|---|---|---|---|---|
| TX output power per channel, maximum setting | 14.5 dBm | 13.0 dBm minimum, 16.0 dBm maximum | `tx_power_w`; the shortfall to the minimum in `tx_power_derating_db` | [1] Table 22 |
| TX output power over temperature, closed-loop power control | | 1 dB variation | `tx_power_derating_db` | [1] Table 24 |
| TX output power over a frequency ramp | | 1.5 dB variation, in either RF band | `tx_power_derating_db` | [1] Table 24 |
| TX output power reduction | | 0–15 dB, accuracy 1.5, 2 and 3 dB over 0–6, 6–12 and 12–15 dB | | [1] Table 24 |
| Noise figure, 0 dB RX gain step ("low-noise mode") | 10.2 dB at 10 MHz IF, 10.5 dB at 1 MHz | 13.2 dB maximum at 10 MHz | `noise_figure_db`; the excess in `noise_figure_derating_db` | [1] Table 30 |
| Noise figure, +3 dB RX gain step ("ultra-low-noise mode") | 9.7 dB at 10 MHz IF, 9.9 dB at 1 MHz | 12.7 dB maximum at 10 MHz | the same | [1] Table 30 |
| Noise figure, negative RX gain steps | | up to the step's magnitude more (a worst-case bound) | `noise_figure_derating_db` | [1] Table 30; [3] |
| Conversion gain, 0 dB and +3 dB steps | 41.5 and 44.5 dB FS/mW | 38–45 and 41.0–48.0 dB FS/mW | | [1] Table 30 |
| RX passband ripple, 2 MHz to the lower of 22.5 MHz and 0.45 f_s | | 1.5 dB | not modelled | [1] Table 30 |
| RX channel-to-channel gain and phase drift | | 1 dB, 3.5° | `beamforming_loss_db` or `other_loss_db` | [1] Table 30 |
| TX output phase adjustment accuracy | | 4° | the same | [1] Table 24 |
| RX high-pass filter | second order, −6 dB at 300, 600, 1200, 2400 or 4800 kHz | ±10 % on the corner up to 2400 kHz; 4800 kHz not allowed during the payload | not modelled | [1] Table 31; [2] Table 120 |
| TX phase noise, CW | Table 22's five offsets | maximum at the same offsets | `ctrx8188f_phase_noise` | [1] Table 22 |
| Ramp timing | | flyback within ±500 kHz of the next start in 1 µs (4 GHz step); TX settling within 1.5 µs of the chirp start; slope 3–200 MHz/µs; payload 5.12–409.6 µs | | [1] Table 23 |

[losses.md: “The equation with all terms”](../losses.md#the-equation-with-all-terms)
says how the derating terms act. Channel phase errors of rms σ cost coherent
combining exp(−σ²) ([losses.md: “Feed and antenna”](../losses.md#feed-and-antenna)).

### The reference plane

The datasheet quotes its RF parameters at the waveguide port on the far side of
a 1.2 mm reference PCB, so the package-to-PCB transition is inside its figures
for the reference footprint and stack-up ([1] Section 5, Figure 5). A different
PCB, or anything between that plane and the antenna, is a feed loss.

### The noise modes are RX gain steps

The datasheet gives the noise figure for a "low noise operation mode" and an
"ultra low noise operation mode" ([1] Table 30). The two modes are the RX gain
steps 0 dB and +3 dB, not a separate setting. The documents point that way:

- Every Table 30 row for either mode (nominal conversion gain, noise figure at
  1 MHz and at 10 MHz IF) is specified at one gain step: 0 dB for low-noise,
  +3 dB for ultra-low-noise.
- The two modes' nominal conversion gains are 3 dB apart, the size of that
  step, at minimum, typical and maximum: 38, 41.5 and 45 dB FS/mW against 41.0,
  44.5 and 48.0 dB FS/mW.
- The datasheet does not mention the modes outside Table 30, and the user
  manual [2] has no noise-mode setting. Its receiver configuration offers a
  gain select with steps +3, 0, −3, −6, −12 and −18 dB, in `Configure_RX()`
  (Table 46) and per ramp segment (`RX_GAINSET_SEL`, Table 120).

Infineon has confirmed it [3]: there is no noise-mode setting; the system
integrator sets the RX gain with `Configure_RX()` or in Infineon's ramp design
tool, and the default is 0 dB. A receiver at +3 dB gain therefore has the
ultra-low-noise figures, 0.5 dB below the preset at 10 MHz IF: use
`frontend.ctrx8188f(noise_figure_db=9.7)`. Since the chip defaults to 0 dB,
the firmware must set +3 dB explicitly. For a negative gain step, the
datasheet's allowance of at most the step's magnitude in extra noise figure is
a worst-case bound, the theoretical limit for a gain reduction. Infineon did
not say which row and column it is counted from, so the safe reading is the
0 dB row's maximum plus the step's magnitude.

### Typical, minimum and maximum

Infineon also states [3] that the datasheet's minimum and maximum values hold
over the whole functional range (junction temperature −40 to 135 °C,
76–81 GHz) unless a row states a narrower condition, and that typical values
are for a nominal part at nominal supply voltage and room temperature. So a
typical value is a starting point for a unit at room temperature, not a bound;
the derating terms cover temperature and part spread.

## Phase noise and the per-chirp frequency error

The datasheet specifies the TX-port phase noise in CW mode at five offsets
([1] Table 22; tabulated in [phase_noise.md: “Phase noise and how it is
specified”](../phase_noise.md#phase-noise-and-how-it-is-specified)). The LO
comes from a DPLL on a 50 MHz crystal, multiplied by six ([1] Figure 2,
Table 23). The datasheet says nothing about phase noise while chirping, or
about variation from chirp to chirp.

The per-chirp frequency error δf sets the link budget's Doppler integration
loss (`SystemLosses.chirp_frequency_error_rms_hz`). [phase_noise.md](../phase_noise.md)
derives it and its loss. Values with a 10.24 µs sampled ramp unless stated;
the measured values used a Blackman–Harris range window, which gives a higher
δf than Hann:

| Case | δf rms |
|---|---:|
| Computed from the CW table, typical; Hann range window, all of slow time (`chirp_frequency_error_rms_hz`) | 2.1–2.6 kHz |
| Same, maximum table | 3.7–4.5 kHz |
| Computed as in [4]: typical table, Blackman–Harris, \|f_D\| ≥ 500 Hz, for the waveforms in [4] | 2.7–3.5 kHz |
| Same, maximum table | 4.8–6.1 kHz |
| Measured: 36 µs or more of flyback and wait, 4.0 µs pre-payload | 3.1–3.6 kHz |
| Measured: 25.5 µs chirp period, 11.2 µs of flyback and wait, 4.0 µs pre-payload | 5.9 kHz |
| Measured: 60 ns flyback, 60 ns wait; pre-payload 5.5, 4.2, 3.5 µs | 14–19, 21, 30 kHz |
| Measured: 41 µs sampled ramp, 43 µs of flyback and wait | at most 0.56 kHz |

The ranges for computed values span the two RF bands. The time between chirps
sets the excess over the CW level. In [4]'s timing test the excess variance
halves with every 2.4 µs that the synthesizer spends in fast-settling mode
(flyback and wait), or every 1.2 µs of pre-payload, and δf comes within 10 % of
its floor at about 24, 20 or 15 µs of flyback and wait for a pre-payload of 2,
4 or 6 µs. The flyback's own length does not matter, and the datasheet's 1 µs
flyback ([1] Table 23) is far from enough. These figures come from one unit and
one ramp length; a longer sampled ramp averages the error down, as the last row
shows. `ctrx8188f_chirp_settling()` holds [4]'s fit and returns δf for a given
timing. The measurements confirm the delay law, σ = 2πτ·δf, up to 270 m.
[phase_noise.md: “The Doppler integration loss”](../phase_noise.md#the-doppler-integration-loss)
tabulates the loss up to 21 kHz; Infineon's timing, 14–30 kHz, would cost
1.5–6.9 dB at 1 km.

## Measured on one radar

The CARKIT validation study [4] measured one evaluation radar with the
CTRX8188F and the SENCITY FARAD-IV antenna ([sencity.md](sencity.md)), mostly at
the +3 dB RX gain step and with the 300 kHz high-pass.

- **Sensitivity.** With a 10 dBsm reference reflector on a fixed mount in a
  measurement chamber, the radar came out 0.4–0.7 dB below a model with the
  typical TX power and noise figure, the antenna's directivity and no hardware
  losses, with the noise taken where the receiver's noise is flat.
- **Receiver noise at low IF.** It rose towards low IF by more than Table 30
  says: a fixed reflector captured with two chirp slopes gained 0.8 dB of SNR
  from 1.25 to 5.3 MHz, against 0.2 dB between the datasheet's 1 and 10 MHz
  rows. From about 5 to 14 MHz a flat noise figure at the 10 MHz value fitted.
  Whether the difference is that unit, its temperature or the target
  datasheet's typical values is open. `noise_figure_derating_db` can carry it
  for targets at low IF.
- **The gain steps.** At the 0 dB step the noise at the ADC was 2.3–2.9 dB
  lower than at +3 dB, close to the 2.5 dB that the gain and noise-figure steps
  give.
- **The high-pass.** It fitted two coincident poles at 294 kHz, which take
  12.7 dB off a return at 162 kHz IF.
- **Phase noise.** The per-chirp frequency error matched the CW table with
  enough time between chirps (above). A strong return's skirt lay 2.3–3.1 dB
  below the typical CW table's prediction at 1–12 MHz offset, and between the
  typical and maximum tables at 0.3–0.5 MHz.

## References

1. Infineon, CTRX8188F Target Datasheet, rev. 0.20, 2025-06-17 (restricted,
   NDA): Figure 2 (block diagram), Section 5 and Figure 5 (RF reference
   plane), Table 22 (general characteristics, TX phase noise), Table 23 (PLL
   and VCO), Table 24 (TX RF module), Table 30 (receiver), Table 31 (RX
   high-pass filter).
2. Infineon, CTRX8188F User Manual, rev. 0.20, 2025-11-10 (restricted, NDA):
   Table 46 (`Configure_RX()` request), Table 120 (ramp segment configuration
   CONFIG0).
3. Infineon, email reply to our questions on the CTRX8188F noise modes and the
   conditions of [1] Table 30, 2026-10-02 (not public).
4. CARKIT validation study, `studies/2026-09-11_carkit-validation/`: the
   report ([README.md](../../studies/2026-09-11_carkit-validation/README.md))
   and, in [NOTES.md](../../studies/2026-09-11_carkit-validation/NOTES.md),
   “Sensitivity against the model”, “The receiver background”, “The per-chirp
   frequency error” and “A strong return's phase-noise skirt”.
