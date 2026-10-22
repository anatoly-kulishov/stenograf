"""Где лежат модели: env, репозиторий или Application Support."""

import os
from pathlib import Path

VAD_NAME = 'silero_vad.onnx'


def models_dir() -> Path:
    env = os.environ.get('STENOGRAF_MODELS')
    if env:
        return Path(env)

    for parent in Path(__file__).resolve().parents:
        candidate = parent / 'models' / VAD_NAME
        if candidate.is_file():
            return candidate.parent

    return Path.home() / 'Library/Application Support/stenograf/models'
