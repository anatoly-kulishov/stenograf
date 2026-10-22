#!/usr/bin/env bash
# Первый запуск: модели, Python-ядро, зависимости приложения.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

if [[ ! -f models/silero_vad.onnx ]]; then
  ./scripts/download_models.sh
else
  echo "models: уже есть"
fi

# .app ищет модели здесь (не в репозитории)
SUPPORT="$HOME/Library/Application Support/stenograf/models"
mkdir -p "$(dirname "$SUPPORT")"
if [[ ! -e "$SUPPORT" ]]; then
  ln -s "$ROOT/models" "$SUPPORT"
  echo "models → $SUPPORT"
elif [[ ! -f "$SUPPORT/silero_vad.onnx" ]]; then
  echo "Внимание: $SUPPORT есть, но без silero_vad.onnx" >&2
fi

(cd core && uv sync)
(cd app && pnpm install)

echo
echo "Готово. Запуск: pnpm dev"
echo "CLI:         pnpm cli -- путь/к/файлу.m4a"
