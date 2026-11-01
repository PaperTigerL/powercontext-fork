#!/usr/bin/env bash
#
# Self-test for the MiniMax SDD context module.
#
#   PRODUCT=/path/to/powercontext-checkout ./run_selftest.sh
#
# The checkout must contain src/powercontext (branch 2026-competition or
# later). Requirements: Linux x86_64, Python 3.12, uv, and an environment
# with the PowerContext dependencies and pylibseekdb installed:
#
#   uv pip install -e "$PRODUCT[seekdb,cli,server]" pytest pytest-asyncio
#
# The script runs the six acceptance gates and prints one line per gate.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"
PYTHON="${PYTHON:-python3}"

PRODUCT="${PRODUCT:-${1:-}}"
if [[ -n "${1:-}" ]]; then shift; fi

if [[ -z "$PRODUCT" ]]; then
  echo "usage: PRODUCT=/path/to/powercontext-checkout $0" >&2
  echo "       the checkout must contain src/powercontext" >&2
  exit 2
fi
if [[ ! -d "$PRODUCT/src/powercontext" ]]; then
  echo "not a powercontext checkout (no src/powercontext): $PRODUCT" >&2
  exit 2
fi

export PYTHONPATH="$PRODUCT/src:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export CTXMODULE_SEEKDB_DIR="${CTXMODULE_SEEKDB_DIR:-$ROOT/.ctxmodule-data/seekdb}"
export CTXMODULE_TRANSCRIPT_DIR="${CTXMODULE_TRANSCRIPT_DIR:-$ROOT/transcript}"
export POWERCONTEXT_HOME="${POWERCONTEXT_HOME:-$ROOT/.ctxmodule-data/powercontext}"
export CTXMODULE_LLM_PROVIDER="${CTXMODULE_LLM_PROVIDER:-replay}"

mkdir -p "$ROOT/.ctxmodule-data" "$ROOT/.ctxmodule-data/powercontext"

echo "product   : $PRODUCT"
echo "python    : $($PYTHON --version 2>&1)"
echo "workspace : $ROOT/.ctxmodule-data"
echo "provider  : $CTXMODULE_LLM_PROVIDER"
echo

cd "$ROOT"
"$PYTHON" -m pytest verify -q -p no:cacheprovider "$@"
status=$?

echo
if [[ $status -eq 0 ]]; then
  echo "RESULT: all six acceptance gates passed"
else
  echo "RESULT: at least one acceptance gate failed (pytest exit $status)"
fi
exit $status
