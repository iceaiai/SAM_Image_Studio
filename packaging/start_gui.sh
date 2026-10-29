#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
SAM_STUDIO_ENV=.venv
if [[ -f samstudio/resources/offline_profile.json ]]; then SAM_STUDIO_ENV=.venv-offline; fi
if [[ ! -x "$SAM_STUDIO_ENV/bin/python" ]]; then
  printf '%s\n' 'Run bash packaging/install_cpu.sh first.'
  exit 1
fi
export SAM_STUDIO_OFFLINE_ROOT="$PWD"
exec "$SAM_STUDIO_ENV/bin/python" -m samstudio "$@"
