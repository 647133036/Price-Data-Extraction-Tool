#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Activate the local virtualenv when present
if [ -d ".venv" ]; then
  # Load project dependencies
  source .venv/bin/activate
fi

# Run the weekly extraction using config files under config/
python -m price_extractor "$@"
