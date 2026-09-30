# studies/

Dated reference studies that compute and plot range performance for specific
product configurations. Each study pins the exact front-end, antenna, waveform
and processing assumptions behind its results so the numbers can be reproduced
and audited later.

These are *not* part of the importable `radarperf` package and are not exercised
by `make smoke` / CI, but they are linted and type-checked by `pre_commit.py`
like the rest of the tree.

Each study lives under `YYYY-MM-DD_short-description/`, where the date identifies
the delivered or otherwise archived study snapshot. A study directory may
contain multiple scripts and supporting files:

    studies/
    └── 2026-06-22_config-comparison/
        ├── config_comparison.py
        ├── generated/       # preliminary/regenerated figures; PNGs ignored
        └── deliverables/    # reviewed final outputs; tracked

Scripts write working figures under their local `generated/` directory. Copy
the reviewed files delivered outside the repo into `deliverables/` to archive
them with the code and assumptions that produced them. When a study's raw
inputs are not in the repo, it may also track small data summaries (JSON/CSV)
and the figures its notes link to in `generated/`, so that its numbers and
figures stay reviewable and downstream steps can run without the raw data.

Run a study from the repo root with the project venv, e.g.:

    venv/bin/python studies/2026-06-22_config-comparison/config_comparison.py

A study may also have a Makefile target named after its folder that regenerates
all of its working figures headlessly and runs its study-local tests, e.g.
`make study_260902_lannik_psi` (about 3.5 minutes on the development Mac).

## Studies

- `2026-09-11_carkit-validation/` — validation of the CARKIT radar
  (CTRX8188F, TX1, eight RX) against our models, from two measurements: a
  walking corner reflector (2026-09-11) and a hand-held reflector at 5 and 10 m
  with 400 and 800 MHz sweeps (2026-09-22). The measured per-RX SNR is
  1.2–2.4 dB above the range model depending on the noise reference, so no
  correction follows. Every strong return carries the same per-chirp frequency
  error (about 14–17 kHz rms, a phase error of 2πτδf), 12–16 dB above what the
  CTRX8188F CW phase-noise table predicts. Results are in
  [`NOTES.md`](2026-09-11_carkit-validation/NOTES.md); the `walk_*.py` and
  `outdoor_*.py` scripts process the raw data (not in the repo) via
  `make study_260911_carkit_validation`.
- `2026-09-02_lannik-psi/` — Lannik Psi antenna-concept study, 2026-09-02 to
  2026-10-01, concluded. It took the June config-3 estimate to a TX aperture
  concept, two RX prototype layouts, interlaced half-aperture MIMO to resolve
  the RX grating-lobe ambiguities, and the antenna RFQ, archived as issued
  under the study's `deliverables/`. Start with its
  [README](2026-09-02_lannik-psi/README.md).
- `2026-06-22_config-comparison/` — Pd (single scan) and 2-of-3 acquisition
  probability vs range for the current Lannik Omega, a modified Lannik Omega,
  and a separate future product. The scenario and per-configuration assumptions
  are documented in `config_comparison.py`.
