# Developer tasks. Nothing here downloads data, trains or evaluates.
PYTHON ?= python

.PHONY: help install lint format typecheck test repo-check protocol site-data site-data-check \
        check-python check build website-install website-build clean

help:
	@echo "install          install package with dev extras"
	@echo "check            full local validation (python + website data sync)"
	@echo "check-python     lint, format check, types, tests, repository scan, protocol hash"
	@echo "site-data        regenerate website/data/*.json from sources of truth"
	@echo "build            build sdist and wheel"
	@echo "website-build    install and build the static website"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check src tests scripts

format:
	$(PYTHON) -m ruff format src tests scripts

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest

repo-check:
	$(PYTHON) -m brats_uncertainty.cli check-repo

protocol:
	$(PYTHON) -m brats_uncertainty.cli verify-protocol

site-data:
	$(PYTHON) -m brats_uncertainty.cli export-site-data

site-data-check:
	$(PYTHON) -m brats_uncertainty.cli export-site-data --check

check-python: lint typecheck test repo-check protocol
	$(PYTHON) -m ruff format --check src tests scripts

check: check-python site-data-check

build:
	$(PYTHON) -m build

website-install:
	cd website && npm ci

website-build: website-install
	cd website && npm run build

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache website/.next website/out
