#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  printf '%s\n' 'Run bash packaging/install_cpu.sh first.'
  exit 1
fi
exec .venv/bin/python -m samstudio "$@"
