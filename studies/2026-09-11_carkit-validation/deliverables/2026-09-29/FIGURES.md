# Figures for the 2026-09-29 Slack summary

Suggested posting: paste [SLACK_SUMMARY.md](SLACK_SUMMARY.md) into the existing
thread, attach figures 1 and 2, and paste their captions with the attachments.
Figure 3 is optional if the CPI discussion warrants another plot. The images
are unchanged copies of the corresponding generated analysis outputs.

## 1. Current SNR reference — recommended

[reference_snr.png](reference_snr.png)

**Caption to paste:**

Target-free background reference and resulting SNR. Top: background at the
target's range and near its Doppler, estimated from other CPIs when the
reflector is away from that range. The outbound/inbound points sample different
Doppler neighborhoods. Bottom: per-CPI linear mean of RX SNRs, normalized by
R⁻⁴ to 100 m and provisionally from 11.27 to 10 dBsm. Orange is the complete
39-CPI inbound interval, averaging 33.86 dB in this dB-domain fit, versus the
32.67 dB model. Blue shows the much weaker outbound return for diagnostic
comparison only; it is excluded from the sensitivity benchmark. These are
normalizations of measurements at approximately 15–51 m, not measurements at
100 m. Target/scene variation is much larger than sensitivity to the background
estimator.

Source: `generated/reference_snr/reference_snr.png`, produced by
`analyze_walk_reference_snr.py`.

## 2. Target-associated Doppler pedestal — recommended

[background_vs_signal.png](background_vs_signal.png)

**Caption to paste:**

Remote-Doppler background at the reflector's range versus target strength.
Background power is averaged over absolute velocities above 20 m/s and compared
with a temporal reference at the same range. The stronger inbound return raises
this background by a median of about 1.2 dB; the weaker outbound return produces
little elevation. Displaced-range controls are approximately unchanged. This
supports a target-associated pedestal, but does not establish oscillator phase
noise as its cause. The target-power axis has an arbitrary ADC/FFT reference;
it is not calibrated received dBm. This diagnostic uses remote-Doppler temporal
controls; the SNR reference in figure 1 uses controls near the target Doppler.

Source: `generated/dynamics/background_vs_signal.png`, produced by
`analyze_walk_dynamics.py`.

## 3. CPI integration — optional

[coherent_gain.png](coherent_gain.png)

**Caption to paste:**

SNR gain from reprocessing 128, 256, 512 and 1024 chirps (approximately
2.04–16.34 ms). The dashed line is ideal constant-tone gain relative to 128
chirps. Solid lines are median measured gains; shading is the 10th–90th
percentile spread across CPIs, not a confidence interval. At 1024 chirps, the
inbound median is 0.20 dB below ideal and the outbound median 1.41 dB below.
These are incremental deficits relative to 128 chirps, not measurements of
total hardware coherence loss. All non-overlapping shorter segments are used,
with Blackman windows and a local target search for each segment.

Source: `generated/dynamics/coherent_gain.png`, produced by
`analyze_walk_dynamics.py`.
