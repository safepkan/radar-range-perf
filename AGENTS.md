# Working Approach

- The goal is a small, scriptable Python toolbox for **range-performance analysis
  of 77 GHz FMCW radars** (with or without MIMO): SNR / SCR / SINR link budgets,
  single-scan Pd, range/angle sweeps, coverage contours and multi-scan track
  acquisition. No GUI — everything is composed and driven from scripts.
- Development happens here in the CLI; planning may be done in plan mode or in a
  separate discussion thread (the workflow is not fixed yet).
- This is a standalone repo, deliberately kept out of the `l2-sp` monorepo — it
  is a separate concern with a somewhat different audience.

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
- Docstrings are read as plain text, not rendered: no Sphinx roles (`:class:`,
  `:func:`, `:meth:`, ...) or directives (`.. note::`). Refer to code as
  ``` ``Name`` ``` and write notes as ordinary paragraphs.
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

## Documentation and studies

- `docs/` is reference documentation, not only usage notes. When adding or
  changing a model term, say where it comes from (derivation, assumptions,
  where it breaks down), not just what it is.
- Every number in docs, docstrings and studies needs a cited source (document,
  revision, table), a shown derivation or a stated toolbox computation;
  otherwise leave it out.
- Values for a particular part (front-end, antenna) go on its page under
  `docs/hardware/`. `docs/losses.md` stays a generic catalogue, and a preset's
  docstring stays short and points to the page.
- Docs must read on GitHub without running anything. Draw their figures with a
  script under `examples/` into `docs/figures/<topic>/`, tracked through
  `docs/.gitignore`; `make smoke` draws them into a temporary directory.
- `studies/` are dated records of what was done. A concluded study is not
  edited to follow later model changes, and issued documents under a study's
  `deliverables/` are immutable. Fold lasting results into `docs/` and the
  toolbox instead.

## Commands

- `make setup_venv` — create `venv` and install (`-r requirements.txt`). Pick a
  Python version with `ENV=venv312` or `VENV_PYTHON=$(command -v python3.12)`.
- `make pre_commit` — format + lint + type-check (reformats in place).
- `make check` — same, but check-only (no reformatting; what CI runs).
- `make test` — `pytest tests`.
- `make smoke` — run the example scripts headless (`MPLBACKEND=Agg`) as a smoke check; run `python examples/<name>.py` directly to view them interactively.
