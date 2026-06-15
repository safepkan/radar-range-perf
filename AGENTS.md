# Working Approach

- The goal is a small, scriptable Python toolbox for **range-performance analysis
  of 77 GHz FMCW radars** (with or without MIMO): SNR / SCR / SINR link budgets,
  single-scan Pd, range/angle sweeps, coverage contours and multi-scan track
  acquisition. No GUI — everything is composed and driven from scripts.
- Development happens here in the CLI; planning may be done in plan mode or in a
  separate discussion thread (the workflow is not fixed yet).
- This is a standalone repo, deliberately kept out of the `l2-sp` monorepo — it
  is a separate concern with a somewhat different audience.

## Provenance

- The package was selected from two LLM-generated candidates, both frozen under
  `archive/` (`archive/radarperf`, `archive/radar-range-tools`). `archive/` is
  **not** linted, type-checked or tested — it is a temporary historical record,
  to be deleted (along with this Provenance section) once anything useful has
  been pulled across.
- `radarperf/` (the working package) started as a copy of `archive/radarperf` and
  diverges from here.

## Planned next steps (ports from the radar-range-tools candidate)

1. Vectorize the engine core over range/az/el (avoid per-`Geometry` Python loops
   in sweeps).
2. Richer noise model: `T_sys = T_ant + (F - 1) * T0`, with a configurable antenna
   temperature and a noise bandwidth distinct from the ADC sample rate.
3. A generic `CombiningStage` processing model (alternative `Processing` Protocol
   implementation) for arbitrary multi-stage combining beyond TDM/DDM/BPM.
4. Bring in the project's controlled CTRX8188F defaults (14.5 dBm, 9.7 dB NF).
   Optional: matplotlib plotting helpers (`radarperf[plot]`).

## Code Guidelines

- Target Python >= 3.12 (CI covers 3.12 and 3.14). Use type hints throughout;
  prefer builtin generics (`list[int]`, `dict[str, Any]`) over `typing.List` /
  `typing.Dict`.
- Formatting / lint / type checks: `black`, `flake8`, `mypy`. Always run
  `venv/bin/python pre_commit.py` (or `make pre_commit`) after modifying code,
  not just before pushing. CI runs `pre_commit.py --no-dirty`.
- **mypy runs in `strict` mode** here — stricter than the `l2-sp` /
  `stone-soup-tracking` house config. The codebase already satisfies it; keep it
  that way.
- flake8 config lives in `pyproject.toml` (via `Flake8-pyproject`): line length
  88, ignoring E203/E501/E741/W503.
- Use the repo venv interpreter for project commands; avoid bare `python`.
- Manage dependencies via `pyproject.toml`; `requirements.txt` is just `-e .[dev]`.
  Pin exact versions, mirroring house practice.
- Ask before running commands that modify environments outside the repo or that
  require new dependencies.

## Conventions

- Angles: azimuth positive to the **left**, elevation positive **up**; direction
  cosines `u = sin(az) cos(el)`, `v = sin(el)`. Cartesian helpers use `x` forward,
  `y` left, `z` up — consistent with `l2-sp/CONVENTIONS.md`.
- Chipset / antenna / RCS presets are **illustrative** unless explicitly sourced
  from a controlled datasheet or measurement. Copy a preset and override fields
  with real numbers for project calculations.

## Commands

- `make setup_venv` — create `venv` and install (`-r requirements.txt`). Pick a
  Python version with `ENV=venv312` or `VENV_PYTHON=$(command -v python3.12)`.
- `make pre_commit` — format + lint + type-check (reformats in place).
- `make check` — same, but check-only (no reformatting; what CI runs).
- `make test` — `pytest tests`.
- `make examples` — run the example scripts as a smoke check.
