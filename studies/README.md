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
  (CTRX8188F, eight TX, eight RX, FARAD-IV antenna) against our range and
  phase-noise models, from a corner reflector carried and on a tripod, a
  hand-held reflector at 5 and 10 m, the office-window scene with Infineon's
  firmware and ours, and traffic seen from a motorway bridge. Two reflector
  sessions disagree by 4.4 dB (1.2–1.7 dB above and 3–4 dB below the model
  without hardware losses), so the absolute check is open. The receiver's
  low-IF background excess is noise between 1 and 5 MHz. With our firmware's
  chirp timing the per-chirp frequency error is 3.1–3.6 kHz rms, at the
  CTRX8188F CW phase-noise table's level; with Infineon's it is 14–30 kHz.
  Results, open questions and planned measurements are in
  [`NOTES.md`](2026-09-11_carkit-validation/NOTES.md); the scripts process the
  raw data (not in the repo) via `make study_260911_carkit_validation`.
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
