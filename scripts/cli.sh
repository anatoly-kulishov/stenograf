#!/usr/bin/env bash
# CLI транскрипции. Примеры:
#   ./scripts/cli.sh путь/к/встрече.m4a
#   ./scripts/cli.sh --mic mic.wav --system system.wav
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/core"

export STENOGRAF_MODELS="${STENOGRAF_MODELS:-$ROOT/models}"

if [[ ! -f .venv/bin/python ]]; then
  uv sync
fi

exec uv run python -m stenograf_core.cli "$@"
