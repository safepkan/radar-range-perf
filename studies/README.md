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
them with the code and assumptions that produced them.

Run a study from the repo root with the project venv, e.g.:

    venv/bin/python studies/2026-06-22_config-comparison/config_comparison.py

## Studies

- `2026-06-22_config-comparison/` — Pd (single scan) and 2-of-3 acquisition
  probability vs range for the current Lannik Omega, a modified Lannik Omega,
  and a separate future product. The scenario and per-configuration assumptions
  are documented in `config_comparison.py`.
