"""Где лежат модели: env (если файл есть), репозиторий или Application Support."""

import os
from pathlib import Path

VAD_NAME = 'silero_vad.onnx'


def _app_support() -> Path:
    return Path.home() / 'Library/Application Support/stenograf/models'


def _has_vad(directory: Path) -> bool:
    return (directory / VAD_NAME).is_file()


def models_dir() -> Path:
    env = os.environ.get('STENOGRAF_MODELS')
    if env:
        path = Path(env).expanduser()
        if _has_vad(path):
            return path

    for parent in Path(__file__).resolve().parents:
        candidate = parent / 'models'
        if _has_vad(candidate):
            return candidate

    support = _app_support()
    if _has_vad(support):
        return support

    # Путь для сообщения об ошибке: предпочитаем то, что явно задали.
    return Path(env).expanduser() if env else support


def require_models() -> Path:
    directory = models_dir()
    if not _has_vad(directory):
        raise FileNotFoundError(
            f'Нет {VAD_NAME} в {directory}. '
            'Запусти из репо: pnpm setup  (или ./scripts/download_models.sh).'
        )
    return directory
