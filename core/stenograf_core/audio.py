"""Загрузка аудио в 16 kHz mono float32."""

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


def load_audio(path: Path) -> np.ndarray:
    """Любой формат -> 16 kHz mono. WAV нужного формата читается без ffmpeg."""
    info = sf.info(str(path))
    if info.samplerate == SAMPLE_RATE and info.channels == 1 and path.suffix.lower() == '.wav':
        samples, _ = sf.read(path, dtype='float32')
        return np.asarray(samples, dtype=np.float32)

    with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
        subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(path), '-ar', str(SAMPLE_RATE), '-ac', '1', tmp.name],
            check=True,
        )
        samples, _ = sf.read(tmp.name, dtype='float32')
    return np.asarray(samples, dtype=np.float32)
