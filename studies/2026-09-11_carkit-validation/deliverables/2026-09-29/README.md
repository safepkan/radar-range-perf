# Reflector-walk results, as posted

Our reply on Slack on 29 September 2026, in Swedish, to Viktor's report of
2026-09-22 ([CARKIT report.pdf](../../inputs/CARKIT%20report.pdf)), from our
own analysis of his corner reflector carried towards the radar. These files
are a record and are not edited.

- [SLACK_POST_SV.md](SLACK_POST_SV.md): the post.
- [reference_snr.png](reference_snr.png) and
  [pedestal_scaling.png](pedestal_scaling.png): its figures 1 and 2.

Later analysis revised three of its points. The study's report gives the
first and the overall result in [Earlier results](../../README.md#earlier-results).

- **The per-chirp frequency error.** The post put it 8–12 dB above the
  datasheet's phase noise, reaching up to 0.7 rad at 1 km. That held only for
  Infineon's chirp timing. With enough time between chirps it is 3.1–3.6 kHz
  rms, at the level of the datasheet's CW phase-noise table
  ([The per-chirp frequency error](../../NOTES.md#the-per-chirp-frequency-error)).
- **The noise reference.** The post leaned towards the receiver's background
  rise at low IF being the IF gain's shape, which would make the noise at the
  target the right reference. A later measurement with two chirp slopes showed
  that the rise is noise. The report takes the noise at 5.3 MHz IF, where it
  is flat ([The receiver background](../../NOTES.md#the-receiver-background)).
- **The carried reflector's level.** The post left it about 1.2 dB above the
  model, with the reflector's RCS at the lab comparison's 11.27 dBsm.
  Corrected for that comparison's short range, the RCS is about 12.1 dBsm, and
  the reflector comes out +0.3 dB against the model
  ([Reflector](../../NOTES.md#reflector),
  [The chamber reflector](../../NOTES.md#the-chamber-reflector)).
