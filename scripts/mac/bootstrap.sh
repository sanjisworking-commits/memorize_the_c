#!/usr/bin/env bash
# Idempotent Mac bootstrap: venv, deps, learning units if missing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

pick_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo ""
  fi
}

PY="$(pick_python)"
if [[ -z "$PY" ]]; then
  echo "Need Python 3.10+ (python3.12 preferred)."
  exit 1
fi

VER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
MAJOR="${VER%%.*}"
MINOR="${VER#*.}"
if (( MAJOR < 3 || (MAJOR == 3 && MINOR < 10) )); then
  echo "Python $VER is too old; need 3.10+."
  exit 1
fi

if [[ -d .venv && ! -x .venv/bin/python ]]; then
  echo "Removing broken .venv…"
  rm -rf .venv
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv with $PY ($VER)…"
  if ! "$PY" -m venv .venv; then
    echo "Failed to create .venv (on Debian/Ubuntu: sudo apt install python3-venv)."
    rm -rf .venv
    exit 1
  fi
else
  echo "Using existing .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements-ci.txt
pip install -e .

REVIEWED="data/output/constitution.reviewed.json"
UNITS="data/output/learning_units.json"

if [[ ! -f "$UNITS" ]]; then
  echo "Missing $UNITS — generating…"
  if [[ ! -f "$REVIEWED" ]]; then
    echo "Applying corrections overlay…"
    python -m constitution_memorizer.cli correct --force
  else
    echo "Found $REVIEWED; skipping correct"
  fi
  python -m constitution_memorizer.cli generate-units --force
else
  echo "Found $UNITS — skipping correct / generate-units"
fi

mkdir -p data/progress

echo
echo "Bootstrap complete."
echo "Next steps:"
echo "  1. Start UI:  open scripts/mac/start-ui.command"
echo "     or:        python -m constitution_memorizer.cli serve --host 127.0.0.1 --port 8001"
echo "  2. Agents:    bash scripts/mac/install-all-agents.sh   # needs NTFY_TOPIC for reminders"
echo "  3. Backup:    bash scripts/mac/backup-progress.sh"
echo "Bookmark: http://127.0.0.1:8001/"
