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

- `2026-09-02_lannik-psi/` — Lannik Psi design study, carried forward from
  config 3 of the 2026-06-22 comparison. It retains the same closing-target
  evaluation scenario and now models the proposed tapered 16 x 16 TX aperture,
  an analytical uniform rectangular RX subarray and a parametric eight-channel
  RX URA. The current coherent-study baseline again uses the supplied
  2.42 x 4.83-wavelength rectangular subarrays in a densely packed 4 x 2
  layout and a periodic 64-beam steering set. The square RX geometry remains
  an explicit comparison candidate. The beam set samples one fundamental
  array-factor cell with an 8 x 4 grid plus an equally sized half-cell-offset
  grid; it reproduces the
  best array-factor envelope throughout visible u/v space through periodic
  aliases. Static single-scan Pd coverage is shown in polar and Cartesian
  horizontal, vertical and diagonal cuts, with principal-region edges marked
  to expose the resulting angular ambiguity. The supplied
  presentation, MATLAB loader and TX/RX aperture data are archived under the
  study's `inputs/`. A separate `quadrant_mimo.py` experiment evaluates how
  well four ideal orthogonal TX-quadrant signatures distinguish the RX
  grating-lobe aliases, compares coherent and MIMO detection range, and models
  accumulation of binary ambiguity evidence in an illustrative interlaced
  schedule without adding experimental architecture to the main coherent-TX
  script. The living system-design record is maintained in
  [`NOTES.md`](2026-09-02_lannik-psi/NOTES.md), with the MIMO investigation in
  [`MIMO.md`](2026-09-02_lannik-psi/MIMO.md). The separate experimental
  `rx_layout_experiment.py` script shows the likely fixed rotated-square
  geometry and focuses the active electrical trade on staggered versus
  unstaggered rectangular RX phase-center layouts, without changing the main
  range baseline. Its decision rationale and near-term investigation plan are
  maintained separately in [`RX_LAYOUT.md`](2026-09-02_lannik-psi/RX_LAYOUT.md).
- `2026-06-22_config-comparison/` — Pd (single scan) and 2-of-3 acquisition
  probability vs range for the current Lannik Omega, a modified Lannik Omega,
  and a separate future product. The scenario and per-configuration assumptions
  are documented in `config_comparison.py`.
