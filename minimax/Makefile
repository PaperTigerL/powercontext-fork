# Self-test entry points for the MiniMax SDD context module.
#
#   make selftest PRODUCT=/path/to/powercontext-checkout
#   make record   PRODUCT=...      # record a live MiniMax session
#   make bootstrap                 # deterministic offline recording

PRODUCT ?= ../..
PYTHON  ?= python3

.PHONY: help selftest gates record bootstrap clean

help:
	@echo "make selftest PRODUCT=/path/to/powercontext-checkout   run the six gates"
	@echo "make record   PRODUCT=...                             record a live MiniMax session"
	@echo "make bootstrap                                        deterministic offline recording"
	@echo "make clean                                            remove the local workspace"

selftest:
	PRODUCT="$(PRODUCT)" PYTHON="$(PYTHON)" ./run_selftest.sh

gates:
	PRODUCT="$(PRODUCT)" PYTHON="$(PYTHON)" ./run_selftest.sh verify

record:
	PRODUCT="$(PRODUCT)" PYTHON="$(PYTHON)" ./run_selftest.sh --collect-only >/dev/null 2>&1 || true
	PYTHONPATH="$(PRODUCT)/src:$(CURDIR)" $(PYTHON) scripts/record_session.py --live

bootstrap:
	PYTHONPATH="$(PRODUCT)/src:$(CURDIR)" $(PYTHON) scripts/record_session.py --bootstrap

clean:
	rm -rf .ctxmodule-data .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
