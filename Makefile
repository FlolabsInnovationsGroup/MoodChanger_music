PYTHON ?= .venv/Scripts/python.exe

.PHONY: help run run-mock test lint

help:
	@echo "Makefile targets: run, run-mock, test, lint"

run:
	$(PYTHON) -m uvicorn app:app --reload --port 8001

run-mock:
	@SET MOCK_MODE=1 && $(PYTHON) -m uvicorn app:app --reload --port 8001

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m pip install black -q
	black --check . || true
