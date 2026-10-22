#!/usr/bin/env bash
# PyInstaller --onedir. Модели не входят в бандл.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/core"

uv run pyinstaller --noconfirm --onedir --name stenograf-core \
  --collect-all sherpa_onnx \
  --collect-all soundfile \
  stenograf_core/__main__.py

echo '{"id": 1, "cmd": "ping"}' | ./dist/stenograf-core/stenograf-core
du -sh ./dist/stenograf-core
