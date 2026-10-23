#!/usr/bin/env bash
# Синтетическая встреча для проверки eval-харнесса (не замена реальных созвонов).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST="$ROOT/eval/meetings/demo-synth"
export STENOGRAF_MODELS="${STENOGRAF_MODELS:-$ROOT/models}"

mkdir -p "$DEST"
cd "$ROOT/core"
uv run python - <<PY
from pathlib import Path
from stenograf_core.synth import build_dialog

dest = Path('$DEST')
audio = build_dialog(dest / 'audio.wav')
ref = audio.with_suffix('.ref.json')
if ref != dest / 'ref.json':
    (dest / 'ref.json').write_text(ref.read_text(encoding='utf-8'), encoding='utf-8')
    if ref.exists() and ref != dest / 'ref.json':
        ref.unlink(missing_ok=True)
(dest / 'meta.json').write_text(
    '{"title": "demo-synth", "notes": "синтетика из TTS, только для smoke eval"}',
    encoding='utf-8',
)
print(dest)
PY
