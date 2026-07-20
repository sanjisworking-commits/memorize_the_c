#!/usr/bin/env bash
# Install serve + reminders LaunchAgents together.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MAC="$ROOT/scripts/mac"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS (Darwin). Detected: $(uname -s)"
  exit 1
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Missing .venv — run: bash scripts/mac/bootstrap.sh"
  exit 1
fi

echo "==> Installing serve agent (UI at login)…"
bash "$MAC/install-serve-agent.sh"

echo
echo "==> Installing reminders agent (daily 07:00)…"
if [[ -z "${NTFY_TOPIC:-}" ]]; then
  echo "NTFY_TOPIC is not set."
  echo "Export it first, then re-run this script, or install reminders alone:"
  echo "  export NTFY_TOPIC=cm-\$(whoami)-study"
  echo "  bash scripts/mac/install-reminders-agent.sh"
  echo
  echo "Serve agent is installed. Reminders skipped."
  exit 0
fi

bash "$MAC/install-reminders-agent.sh"

echo
echo "Both agents installed."
echo "  UI:        http://127.0.0.1:8001/"
echo "  Reminders: hourly ticks; cadence in Settings (default thrice)"
echo "Optional weekly backup: bash scripts/mac/install-backup-agent.sh"
