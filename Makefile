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

.PHONY: examples
examples:
	$(PYTHON) examples/basic_link_budget.py
	$(PYTHON) examples/ddma_combinations.py
	$(PYTHON) examples/pd_vs_range.py

.PHONY: clean
clean:
	rm -rf build dist *.egg-info
	find . -path ./$(ENV) -prune -o -name __pycache__ -type d -exec rm -rf {} +
