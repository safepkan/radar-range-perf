# Flat makefile used as a command shortener.
#
# The active virtual environment is selected with ENV (default: venv).  A name
# like ENV=venv312 selects the python3.12 interpreter; override VENV_PYTHON to
# pick an interpreter explicitly, e.g.
#
#   make setup_venv VENV_PYTHON=$(command -v python3.12)

ENV ?= venv
ENV_PYTHON_VERSION ?= $(shell printf '%s\n' "$(ENV)" | sed -n 's/.*venv\([0-9]\)\([0-9][0-9]\)$$/\1.\2/p')
VENV_PYTHON ?= $(shell \
	if [ -f "$(ENV)/pyvenv.cfg" ]; then \
		home=$$(sed -n 's/^home = //p' "$(ENV)/pyvenv.cfg" | sed 1q); \
		if [ -n "$(ENV_PYTHON_VERSION)" ] && [ -x "$$home/python$(ENV_PYTHON_VERSION)" ]; then \
			printf '%s\n' "$$home/python$(ENV_PYTHON_VERSION)"; \
		elif [ -x "$$home/python3" ]; then \
			printf '%s\n' "$$home/python3"; \
		else \
			command -v python3; \
		fi; \
	elif [ -n "$(ENV_PYTHON_VERSION)" ] && command -v "python$(ENV_PYTHON_VERSION)" >/dev/null 2>&1; then \
		command -v "python$(ENV_PYTHON_VERSION)"; \
	else \
		command -v python3; \
	fi)
PYTHON := ./$(ENV)/bin/python
PIP := ./$(ENV)/bin/pip

.PHONY: setup_venv
setup_venv:
	rm -rf $(ENV)/
	$(VENV_PYTHON) -m venv $(ENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

.PHONY: update_venv
update_venv:
	$(PIP) install -r requirements.txt

.PHONY: pre_commit
pre_commit:
	PATH="$(CURDIR)/$(ENV)/bin:$$PATH" $(PYTHON) pre_commit.py

.PHONY: check
check:
	PATH="$(CURDIR)/$(ENV)/bin:$$PATH" $(PYTHON) pre_commit.py --no-dirty

.PHONY: test
test:
	$(PYTHON) -m pytest tests

.PHONY: smoke
smoke:
	$(PYTHON) examples/basic_link_budget.py
	$(PYTHON) examples/ddma_combinations.py
	MPLBACKEND=Agg $(PYTHON) examples/pd_vs_range.py
	MPLBACKEND=Agg $(PYTHON) examples/plotting_demo.py
	MPLBACKEND=Agg $(PYTHON) examples/phase_noise.py
	MPLBACKEND=Agg $(PYTHON) examples/phase_noise_tutorial.py

# Regenerate every working figure of the Lannik Psi study headlessly and run
# its study-local tests. Figures land under the study's generated/ directory
# (gitignored); only reviewed or delivered outputs are copied to deliverables/.
.PHONY: study_260902_lannik_psi
study_260902_lannik_psi:
	MPLBACKEND=Agg $(PYTHON) studies/2026-09-02_lannik-psi/lannik_psi.py
	MPLBACKEND=Agg $(PYTHON) studies/2026-09-02_lannik-psi/quadrant_mimo.py
	MPLBACKEND=Agg $(PYTHON) studies/2026-09-02_lannik-psi/rx_layout_experiment.py
	MPLBACKEND=Agg $(PYTHON) studies/2026-09-02_lannik-psi/rx_resolution_experiment.py
	MPLBACKEND=Agg $(PYTHON) studies/2026-09-02_lannik-psi/rx_stagger_amount_experiment.py
	$(PYTHON) -m pytest studies/2026-09-02_lannik-psi -q

# Regenerate the CARKIT validation study from the raw data, which are not in
# the repo: the 2026-09-11 walk, the 2026-09-22 outdoor reflector captures, the
# out-of-window captures of 2026-09-30, 2026-08-27 (converted once with
# window_convert_infineon.m) and 2026-10-02, and the 2026-10-01 field and
# highway captures. Override their locations with CARKIT_WALK_DATA=/path,
# CARKIT_OUTDOOR_DATA=/path, CARKIT_WINDOW_DATA=/path,
# CARKIT_WINDOW_INFINEON_DATA=/path, CARKIT_WINDOW_1002_DATA=/path,
# CARKIT_FIELD_DATA=/path and CARKIT_HIGHWAY_DATA=/path.
CARKIT_WALK_DATA ?= $(HOME)/Data/tmp/walk-hallesaker-tx1-1-psi
CARKIT_OUTDOOR_DATA ?= $(HOME)/Data/carkit/2026-09-22_phase_noise_outdoor_reflector
CARKIT_WINDOW_DATA ?= $(HOME)/Data/carkit/2026-09-30_out-the_window
CARKIT_WINDOW_INFINEON_DATA ?= $(HOME)/Data/carkit/2026-08-27_test_out_of_office_window/converted_adc
CARKIT_WINDOW_1002_DATA ?= $(HOME)/Data/carkit/2026-10-02_out_the_window
CARKIT_FIELD_DATA ?= $(HOME)/Data/carkit/2026-10-01_reflector_lindevi
CARKIT_HIGHWAY_DATA ?= $(HOME)/Data/carkit/2026-10-01_highway_sandsjobacka
CARKIT_STUDY := studies/2026-09-11_carkit-validation
CARKIT_STEPS := walk_extract walk_background walk_reference_snr walk_dynamics \
	walk_pedestal walk_long_range walk_model outdoor_scene outdoor_phase outdoor_model \
	window_scene window_phase window_range_scale field_if field_level highway_traffic
CARKIT_WINDOW_1002_OUTPUT := $(CARKIT_STUDY)/generated/window/2026-10-02
CARKIT_WINDOW_1002_LEVELS := medium-10dB:medium-0dB,short-10dB:short-0dB,medium-8TX:medium-0dB
.PHONY: study_260911_carkit_validation
study_260911_carkit_validation:
	$(PYTHON) -m pytest $(CARKIT_STUDY) -q
	@export CARKIT_WALK_DATA="$(CARKIT_WALK_DATA)" \
		CARKIT_OUTDOOR_DATA="$(CARKIT_OUTDOOR_DATA)" \
		CARKIT_WINDOW_DATA="$(CARKIT_WINDOW_DATA)" \
		CARKIT_WINDOW_INFINEON_DATA="$(CARKIT_WINDOW_INFINEON_DATA)" \
		CARKIT_FIELD_DATA="$(CARKIT_FIELD_DATA)" \
		CARKIT_HIGHWAY_DATA="$(CARKIT_HIGHWAY_DATA)" MPLBACKEND=Agg; \
	for step in $(CARKIT_STEPS); do \
		$(PYTHON) $(CARKIT_STUDY)/$$step.py || exit 1; \
	done; \
	$(PYTHON) $(CARKIT_STUDY)/window_scene.py --data "$(CARKIT_WINDOW_1002_DATA)" \
		--cases auto --output $(CARKIT_WINDOW_1002_OUTPUT)/scene \
		--level-pairs $(CARKIT_WINDOW_1002_LEVELS) || exit 1; \
	$(PYTHON) $(CARKIT_STUDY)/window_phase.py --data "$(CARKIT_WINDOW_1002_DATA)" \
		--cases auto --scene $(CARKIT_WINDOW_1002_OUTPUT)/scene \
		--output $(CARKIT_WINDOW_1002_OUTPUT)/phase

.PHONY: clean
clean:
	rm -rf build dist *.egg-info
	find . -path ./$(ENV) -prune -o -name __pycache__ -type d -exec rm -rf {} +
