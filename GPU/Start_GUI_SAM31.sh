#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
# Run from an initialized Linux Conda shell; no Python packages are installed here.
conda run --no-capture-output -n sam-image-studio-sam3 python -m samstudio "$@"
