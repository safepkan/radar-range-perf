## Summary from Codex — 2026-09-29

We have independently reprocessed the walking-reflector recording, including per-RX signal/noise estimates, different CPI lengths and checks of the background around the target. Processing uses Blackman windows and fourfold FFT padding on both axes, consistent with Viktor's clarification.

**The measurements and radar-equation model are reasonably close, but this recording does not establish a transferable implementation gain or loss.** The initial apparent 4 dB advantage compared different SNR statistics and references. Our current comparison leaves roughly 1.2–1.4 dB in favour of the measurement, with substantial uncertainty from the target and scene.

**The current reference point**

Using the complete contiguous inbound interval—39 CPIs over approximately 17–51 m—we obtain **33.9 dB, normalized to 100 m and 10 dBsm**, against the model's **32.7 dB**. A 37-CPI amplitude-selected subset gives 34.1 dB. These are R⁻⁴ fit normalizations, not measurements at 100 m.

We measure signal and background power separately per RX, average the channel SNRs in linear units, and then fit the range-normalized values in dB over time. There is no coherent RX combination or additional 9 dB RX credit. The background reference comes from the same range and near the same Doppler, in other CPIs when the reflector is away from that range.

The walking reflector is provisionally assigned **11.27 dBsm**, based on its reported 1.27 dB excess over the nominal 10 dBsm reference; we subtract that excess to report the 10 dBsm result above. The relative comparison is useful, but the absolute RCS remains uncalibrated. Viktor's hand calculation of 32.63 dB and the model's 32.67 dB agree closely.

**What happened to the original discrepancy?**

We approximately reproduce the magnitude-sum plot's 36.7 dB normalization. A magnitude sum is a valid statistic, but it is not the conventional signal-power/noise-power SNR. Channel averaging, the background reference and the RCS assumption all matter. They do not provide three unique, independent corrections that add up to exactly 4 dB.

Averaging in linear units versus dB changes the answer appreciably because this target fluctuates. For all 39 inbound CPIs, the chosen 33.9 dB summary becomes 34.5 dB with fully linear averaging over time, or 32.5 dB with dB averaging across both channels and time. These describe different properties of the same data; near-exact agreement under one convention is not precise model validation.

The noise estimate is much less sensitive: changing the control times, reflector exclusion distance or averaging region changes the reference by less than about 0.1 dB. Different background estimators agree within about 0.1 dB too.

**The target varies much more than the noise estimate**

**Only the inbound leg is used for the sensitivity benchmark.** The outbound peak-cell signal power is approximately 12.5 dB weaker after range correction. It is not treated as a calibrated reflector measurement; we retain it for diagnostic comparisons and use target-free regions as background controls. Maintaining reflector alignment or avoiding obscuration while walking away may be harder, but the cause of the difference is not established.

The stronger inbound return does not establish that the reflector achieves its assumed RCS. Even within that interval, observations below and above 30 m give normalized averages differing by about 1.3 dB. Reflector pointing, the person carrying it and propagation remain plausible contributors.

There are also large, changing RX differences, including deep nulls. Fixed amplitude calibration cannot explain the whole effect. In one example, a channel is 28 dB below the strongest channel at the selected cell, but 16 dB below when power is integrated over a surrounding patch. Composite returns and motion are plausible; the mechanism is not identified.

**Two distinct background effects**

First, the relatively stable additive background varies with range/beat frequency: it falls roughly 0.6 dB over 15–50 m and is higher there than in the far quarter used by the original estimator. We do not know why. Filtering is a candidate, but the noise curve does not establish that the signal receives the same filtering.

Second, the strong reflector has a **broad Doppler pedestal localized around its range**. On the inbound leg, background at that range is elevated by about 1.2 dB even at absolute velocities beyond 20 m/s. The excess tracks target strength; displaced ranges show little corresponding elevation. This supports a signal-dependent disturbance, possibly phase/amplitude modulation, but does not identify oscillator phase noise.

For the radar-equation comparison we use the additive background without that target-associated elevation. If the pedestal scales with target power, a weak target's own pedestal should become negligible near detection threshold. Strong other returns can still create a dynamic-range problem. The pedestal's range extent and physical cause remain open.

**CPI duration is not the main issue in the inbound benchmark**

Reprocessing 128–1024 chirps gives nearly the expected integration gain inbound: the median additional deficit from 128 to 1024 chirps is about **0.2 dB**. Outbound it is about **1.4 dB**, with much broader Doppler structure. Pedestrian/hand-held-reflector motion can contribute, especially outbound. These results argue against several dB of additional CPI loss in the inbound benchmark; they do not measure total hardware coherence loss.

**What next?**

A controlled measurement should now be more informative than further refinement of this walk: a stationary tripod reflector at several ranges, a TX-power sweep at each range with unchanged RX settings, and reflector-absent background captures. Repeat selected points at another height or a small displacement to assess multipath. Measure the reflector's physical dimensions and, ideally, make an independent RCS comparison. Covering exposed stand parts with absorber is a useful control, although earlier characterization suggests a small stand contribution.

Sensitivity validation and phase-noise/dynamic-range work can share a measurement session while retaining separate objectives. The earlier chamber questions about channel group delays and the covariance cell selection remain unresolved by this walk.

For now, retain this as a useful radar-equation reality check without applying a general hardware correction or transferring the chamber's measured coherent-summing gain into a range budget. Pd/range comparisons should follow separately with consistent target, Pfa, antenna and waveform assumptions.
