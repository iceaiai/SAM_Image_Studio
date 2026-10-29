#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
python3 scripts/bootstrap_python.py --run scripts/prepare_offline.py "$@"
