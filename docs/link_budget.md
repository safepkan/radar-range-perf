# How the link budget is computed

`Radar.link_budget` evaluates the FMCW range equation at one geometry and
returns the SNR per detector look, with every term itemised.
`Radar.probability_of_detection` turns that into a single-scan Pd, and the
sweeps in `radarperf.sweeps` evaluate the same terms over grids. This page
derives how the toolbox gets from its inputs to the SNR and the Pd: the energy
form of the range equation, the system temperature, the coherent gain of the
FFTs and the channels, non-coherent looks and collapsing, in-phase transmit,
and detection. [losses.md](losses.md) catalogues the loss terms, and
[false_alarms.md](false_alarms.md) covers the threshold side.

## In brief

- **The SNR is the received energy over the noise density.** The toolbox
  builds it as a single-sample SNR times the number of samples summed
  coherently, and the sample rate cancels out.
- **Passive losses ahead of the receiver also emit noise.** At 290 K a
  receive-side loss lowers the SNR by exactly its value.
- **The coherent gain is samples × chirps per transmitter × coherently
  combined channels.** TDM buys virtual aperture, not SNR. DDM and BPM gain a
  factor n_tx, because every transmitter sends on every chirp.
- **Channels combined non-coherently become detector looks,** which gain less
  than coherent combination: at Pd 90 %, 1.2 dB less for 4 looks and 3.0 dB
  less for 16. Noise-only cells summed with them, such as empty DDMA subbands,
  cost a further collapsing loss.
- **Looks over channels within one CPI share one RCS draw.** Model them as
  Swerling 1 or 3; Swerling 2 would credit a diversity gain that is not there.
- **In-phase transmit beats DDM by another factor n_tx,** because receiver
  noise enters once instead of n_tx times.

## The energy form of the range equation

$$
\mathrm{snr}_{\mathrm{sample}} = \frac{P_t G_t G_r \lambda^2 \sigma}{(4\pi)^3 R^4\, k T_{\mathrm{sys}} B_n\, L_{\mathrm{path}} L_{\mathrm{system}}},
\qquad
\mathrm{SNR} = \mathrm{snr}_{\mathrm{sample}}\,\frac{G_{\mathrm{coh}}}{L_{\mathrm{proc}}}
$$

The first factor is the SNR of one complex baseband sample: the received power
over the noise power k·T_sys·B_n in the noise bandwidth B_n. B_n defaults to
the sample rate f_s, an ideal anti-alias filter (`FmcwWaveform.noise_bandwidth_hz`
overrides it). The antenna gains are normally a single channel's, and array
gain belongs to G_coh; a full-aperture pattern is the exception
([In-phase transmit](#in-phase-transmit)).

Within a chirp the beat tone has constant amplitude. Summing N samples
coherently, as the FFT does at the tone's bin, adds their amplitudes: the
signal power grows as N². Independent noise adds in power, as N. The SNR after
the sum is therefore N·snr_sample. Over a dwell T there are N = f_s·T samples,
so with B_n = f_s

$$
\mathrm{SNR} = f_s T\,\frac{P_r}{k T_{\mathrm{sys}} f_s} = \frac{P_r T}{k T_{\mathrm{sys}}} = \frac{E}{N_0},
$$

the received energy over the noise density. The sample rate cancels: sampling
faster adds samples, but also noise bandwidth. The dwell is the time the ADC
samples, n_chirps × n_samples / f_s (`FmcwWaveform.dwell_time_s`); the time
between payloads puts no energy into the sum.

A window w_n changes the sum's signal power to (Σw)² and its noise power to
Σw², so the SNR becomes snr_sample·(Σw)²/Σw². That is N divided by the
window's equivalent noise bandwidth in bins, so the window loss is 10 log₁₀ of
that bandwidth: 1.76 dB for Hann. A tone between bins also loses some peak
power (straddle), which the toolbox averages over the tone's position: 0.47 dB
per axis for Hann without padding. L_proc collects these with the CFAR,
beamforming, MIMO and other losses ([losses.md: “Processing”](losses.md#processing)).

The `snr_db` that the link budget reports is per detector look: G_coh and
L_proc are applied, but channels combined non-coherently are not. Those go to
the detector as looks ([Detection](#detection)).

## System temperature

Signal and noise are referred to the front-end's RF reference plane, where the
datasheet gives TX power and noise figure. Between the antenna and that plane
lie passive receive losses, L_rx = L_radome·L_rx,ant·L_rx,feed, at a physical
temperature of T0 = 290 K. A passive attenuator at T0 with loss L passes the
antenna's noise temperature T_ant reduced by 1/L and adds T0(1 − 1/L) of its
own: in thermal equilibrium, with T_ant = T0, what comes out must again be T0.
The receiver adds (F·D_nf − 1)·T0, with F its noise factor and D_nf any
derating. So

$$
T_{\mathrm{sys}} = \frac{T_{\mathrm{ant}}}{L_{\mathrm{rx}}} + T_0\left(1 - \frac{1}{L_{\mathrm{rx}}}\right) + (F D_{nf} - 1)\,T_0 .
$$

With the default T_ant = T0, this is F·D_nf·T0 whatever L_rx is. The signal is
reduced by L_rx, so a receive-side loss lowers the SNR by exactly its value. A
colder scene (`Radar(antenna_noise_temperature_k=...)` below 290 K) makes the
same loss cost a little more, because the loss's own noise replaces less noise
from the scene.

### A cold sky

At 77 GHz the clear sky is not very cold. Oxygen, in the wing of its band
around 60 GHz, and water vapour absorb, and so they also emit.
`itu.sky_brightness_temperature_k` integrates that emission along the path
through the ITU-R reference atmosphere, with the absorption of ITU-R P.676-13
([losses.md: “Propagation”](losses.md#propagation)). At 76.5 GHz, seen from sea
level:

| Elevation | 90° | 45° | 30° | 20° | 10° | 5° | 0° |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sky temperature | 55 K | 74 K | 97 K | 129 K | 195 K | 252 K | 288 K |

From 1 km up the zenith sky is 40 K, from 5 km 14 K. Along the horizon the
path is long enough to be opaque, and the sky is as warm as the air: the
default T_ant = T0 fits. Looking up, the antenna temperature falls. An ideal
pencil beam at the zenith sees the sky's 55 K; a real antenna weights the sky
with its whole pattern, and sidelobes that see the ground at about 290 K raise
it.

The SNR gained against T_ant = T0 is 10 log₁₀ of T_sys at T0 over T_sys at
T_ant. The receiver's own (F·D_nf − 1)·T0 dominates T_sys, so the gain cannot
exceed 10 log₁₀(F/(F − 1)), reached with T_ant = 0 and no receive loss.
Receive losses reduce it further, because their own noise at T0 replaces part
of the cold sky. Computed from the formula above, with the range gain for an
SNR that grows as R⁻⁴:

| Noise figure | Upper bound | T_ant 60 K, no receive loss | T_ant 60 K, 1.5 dB receive loss |
|---|---:|---:|---:|
| 9.7 dB (CTRX8188F, +3 dB step) | 0.49 dB, +2.9 % range | 0.39 dB, +2.2 % | 0.27 dB, +1.6 % |
| 10.2 dB (CTRX8188F, 0 dB step) | 0.44 dB, +2.5 % | 0.34 dB, +2.0 % | 0.24 dB, +1.4 % |
| 12 dB (AWR2243 preset) | 0.28 dB, +1.6 % | 0.22 dB, +1.3 % | 0.16 dB, +0.9 % |
| 14 dB (AWR1243 preset) | 0.18 dB, +1.0 % | 0.14 dB, +0.8 % | 0.10 dB, +0.6 % |

So with the noise figures of these MMICs, a radar looking straight up gains a
few tenths of a dB over one looking along the horizon: a percent or two of
range. For an upward-looking budget, set `Radar(antenna_noise_temperature_k=...)`.
It is one value per radar, not per direction, so a sweep over elevation keeps
it fixed.

## Coherent gain and the MIMO scheme

For one virtual channel, one transmitter and one receiver, the range FFT sums
n_samples (N_s) and the Doppler FFT sums the chirps on which that transmitter
sends. With N_c chirps per CPI:

| Scheme | Chirps per transmitter | Coherent gain per virtual channel | All channels combined coherently |
|---|---|---|---|
| `NONE` (one transmitter) | N_c | N_s·N_c | N_s·N_c·n_rx |
| `TDM` | N_c / n_tx | N_s·N_c / n_tx | N_s·N_c·n_rx |
| `DDM`, `BPM` | N_c | N_s·N_c | N_s·N_c·n_tx·n_rx |

- **TDM buys aperture, not SNR.** Each transmitter sends on one chirp in n_tx.
  Combining the n_tx virtual transmitters coherently restores the N_c chirps
  of a single transmitter: the virtual array grows, the energy on target does
  not. TDM's Doppler FFT runs over N_c/n_tx chirps per transmitter, so its
  window and straddle losses are for that length.
- **DDM and BPM gain n_tx because every transmitter sends on every chirp.**
  n_tx times the energy goes out. Once the transmitters are separated, in
  Doppler or by code, their returns add coherently. Imperfect separation goes
  in `mimo_loss_db`. DDM pays in unambiguous Doppler, which its subbands
  divide between the transmitters.

The engine's tests check that TDM matches a single transmitter in SNR and that
DDM beats it by n_tx (`tests/test_engine.py`).

## Coherent and non-coherent combination

For the RX axis and for the TX axis (DDMA subbands, for DDM and BPM),
`StandardProcessing` combines the channels in one of two ways:

- **Coherently,** by beamforming. The channel count multiplies G_coh, the
  ideal gain at the beam's pointing. A target away from it costs
  `beamforming_loss_db`, or the antenna model carries that loss:
  `UniformArrayAntenna` applies the array factor around a per-channel pattern,
  normalized to 0 dB at the beam centre, so the peak gain is not counted
  twice.
- **Non-coherently,** by summing powers. Each channel becomes a detector look.
  No beam has to point at the target.

Coherent combination makes better use of the SNR. Summing n looks
non-coherently needs more SNR per look than one coherent sum of the same
channels needs per channel. At Pd 90 % and Pfa 10⁻⁶ per test, for a
Swerling 1 target, it needs 1.2 dB more with 4 looks and 3.0 dB more with 16
(computed with `required_snr_db`: 21.1 dB for one look, against 16.4 and
12.1 dB per look).

On a DDMA radar with 4 TX, 4 RX and 6 Doppler subbands, the practical paths
are:

| Path | G_coh | Signal looks | Empty cells |
|---|---|---:|---:|
| RX and subbands non-coherent (TI's DDMA detection path) | N_s·N_c | 16 | 8 |
| RX coherent, subbands non-coherent | N_s·N_c·n_rx | 4 | 2 |
| RX and TX coherent (virtual array) | N_s·N_c·n_rx·n_tx | 1 | 0 |

`examples/ddma_combinations.py` evaluates them for an AWR2E44P and a
pedestrian at 90 m: Pd 0.37, 0.45 and 0.58, and 0.87 with in-phase transmit.
`StagedProcessing` expresses other topologies as an explicit list of named
coherent and non-coherent stages; for DDMA it reproduces `StandardProcessing`
(`tests/test_staged_processing.py`).

### Collapsing

DDMA allocates more Doppler subbands than transmitters, 6 for 4 TX, to leave
guard bands between them. Summed non-coherently with the others, an empty
subband adds noise but no signal. The detector's statistic then sums n_total
cells, of which only n_signal carry the target, and its threshold must cover
the noise of all of them. The link budget reports the noise-only cells as
`n_collapsing`, and the detector integrates them exactly. In the first path
above, 16 looks with 8 empty cells, the collapsing loss is 0.6 dB at Pd 90 %
(Swerling 1, Pfa 10⁻⁶ per test; computed with `probability_of_detection`).
When the TX axis is combined coherently, the transmitters are resolved first
and the empty subbands are discarded, so there is no collapsing.

### Fluctuation over looks

The detector's Swerling case says how the target's RCS varies from look to
look. Looks over channels within one CPI see the target at the same moment and
from almost the same angle, so they share one RCS draw: Swerling 1 (or 3),
the same RCS in every look. Swerling 2 (or 4) draws a new RCS for each look and
credits a diversity gain that is not there. For 16 looks at Pd 90 % it needs
7.6 dB less SNR per look than Swerling 1. With collapsing, the detector
supports Swerling 0, 1 and 3, and rejects 2 and 4.

## In-phase transmit

`StandardProcessing(transmit_coherent=True)` models all n_tx transmitters
sending the same waveform in phase, steered at the target: a transmit phased
array. The power density on the target is n_tx² that of one transmitter: n_tx
from the total power and n_tx from the transmit directivity. That is
20 log₁₀(n_tx) more SNR than one transmitter.

Against DDM, compare the SNR after the transmitters are combined. Let one
transmitter's return have amplitude a and the noise in one Doppler cell
variance σ².

- **DDM** separates the n_tx returns into n_tx Doppler subbands, each with its
  own noise. Their coherent sum has amplitude n_tx·a and noise variance n_tx·σ²,
  an SNR of n_tx·a²/σ².
- **In-phase transmit** adds the amplitudes in the air, so the receiver sees
  amplitude n_tx·a in one cell with noise σ², an SNR of n_tx²·a²/σ².

The signal is the same; the receiver's noise enters n_tx times in DDM and
once in phase. In-phase transmit therefore gains another 10 log₁₀(n_tx) over
DDM, in a model limited by receiver noise (`tests/test_combination.py`). It
has no virtual transmit aperture, though, so covering a wide field of view
means scanning the transmit beam. That costs dwell time, which a budget for
one direction does not count.

By default the antenna object describes one transmit element or subarray, and
the processing adds the array directivity. For a pattern of the complete
coherently fed aperture, set `tx_array_gain_in_antenna=True`: the pattern then
carries the directivity, and the processing adds only n_tx for the total power.

## Detection

`radarperf.detection` models a square-law detector that sums n looks
non-coherently, for Swerling cases 0–4 (5 is treated as 0):

- Swerling 0: exact, through the non-central chi-square distribution.
- Swerling 1 and 2: exact closed forms.
- Swerling 3: Gauss–Laguerre quadrature of the Swerling 0 result over the
  chi-square RCS distribution with four degrees of freedom.
- Swerling 4: an exact closed form, from the per-look Laplace transform.

The tests check all five against Monte Carlo simulation, and the Albersheim
and Shnidman approximations against the exact results
(`tests/test_detection.py`). With n_collapsing noise-only cells the statistic
sums n + n_collapsing cells, as above.

`Radar.probability_of_detection` uses the SINR by default. Clutter, so far
only rain ([losses.md: “Propagation”](losses.md#propagation)), gets the same
coherent gain and processing losses as the target and adds to the noise. The
threshold comes from the Pfa per range–Doppler cell, converted to a Pfa per
test ([false_alarms.md](false_alarms.md)). The CFAR is a fixed loss allowance.

## What the tests check

- `tests/test_noise.py`: the defaults reduce to k·T0·F·f_s; the antenna
  temperature and the noise bandwidth act as derived above.
- `tests/test_engine.py`: the SNR falls as R⁻⁴ and grows with the RCS; TDM
  matches a single transmitter and DDM beats it by n_tx; rain attenuates and
  its clutter lowers the SINR.
- `tests/test_processing.py`: the window losses are the windows' equivalent
  noise bandwidths and match Harris's table; padding reduces straddle; TDM's
  Doppler window spans the chirps per transmitter.
- `tests/test_combination.py`: the DDMA bookkeeping of the paths above;
  collapsing against its closed form and Monte Carlo; collapsing costs SNR and
  rejects Swerling 2 and 4; in-phase transmit beats DDM by n_tx and does not
  count the directivity twice with a full-aperture pattern; coherent
  combination detects better than non-coherent.
- `tests/test_detection.py` and `tests/test_staged_processing.py`, as above.
