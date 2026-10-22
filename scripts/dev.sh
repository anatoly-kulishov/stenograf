#!/usr/bin/env bash
# Dev-режим: React + Tauri, сайдкар через uv (обёртка в binaries/).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/app"

if [[ ! -d node_modules ]]; then
  pnpm install
fi

if [[ ! -f "$ROOT/core/.venv/bin/python" ]]; then
  (cd "$ROOT/core" && uv sync)
fi

if [[ ! -f "$ROOT/models/silero_vad.onnx" ]]; then
  echo "Нет models/silero_vad.onnx. Сначала: ./scripts/setup.sh" >&2
  exit 1
fi

exec pnpm tauri dev
