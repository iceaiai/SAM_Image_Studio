#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ -f samstudio/resources/offline_profile.json ]]; then
  python3 scripts/bootstrap_python.py --offline --run scripts/install_offline.py
else
  python3 scripts/bootstrap_python.py --run scripts/install_environment.py --backend cpu
fi
