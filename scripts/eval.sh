#!/usr/bin/env bash
# Прогон eval/meetings. Без встреч с ref.json - подсказка, не ошибка.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
MEETINGS="$ROOT/eval/meetings"
export STENOGRAF_MODELS="${STENOGRAF_MODELS:-$ROOT/models}"

cd "$ROOT/core"
if [[ ! -f .venv/bin/python ]]; then
  uv sync
fi

if ! find "$MEETINGS" -mindepth 2 -maxdepth 2 -name ref.json 2>/dev/null | grep -q .; then
  echo "Нет встреч в $MEETINGS (нужен ref.json)."
  echo "См. eval/README.md. Синтетика: pnpm cli -- --eval eval/meetings/demo-synth"
  exit 0
fi

exec uv run python -m stenograf_core.cli --eval "$MEETINGS" "$@"
