#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/models"
cd "$ROOT/models"
R=https://github.com/k2-fsa/sherpa-onnx/releases/download

curl -sSL "$R/asr-models/sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16.tar.bz2" | tar xj
curl -sSL "$R/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2" | tar xj
curl -sSLO "$R/speaker-recongition-models/nemo_en_titanet_small.onnx"
curl -sSLO "$R/asr-models/silero_vad.onnx"

# только для сравнения в `python -m stenograf_core.cli --ref` (нужен `brew install whisper-cpp`)
curl -sSLO https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin
