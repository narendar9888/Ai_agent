.PHONY: setup run test clean evaluate lint help

PYTHON ?= python3

help:
	@echo "Adaptive Cost-Aware Tool Planning Harness (ACTP)"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup     - Install Python dependencies"
	@echo "  make run       - Run the ACTP interactive CLI harness"
	@echo "  make test      - Run automated test suite with pytest"
	@echo "  make evaluate  - Run baseline and ablation evaluation suite"
	@echo "  make clean     - Clean temporary caches and test artifacts"

setup:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m src.main

test:
	pytest -q

evaluate:
	$(PYTHON) -m src.evaluation.runner

clean:
	rm -rf .pytest_cache __pycache__ src/__pycache__ src/**/__pycache__ tests/__pycache__ .coverage evaluation/results/*.tmp
