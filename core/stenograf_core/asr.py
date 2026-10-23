"""VAD-фразы и распознавание GigaAM v3 (пунктуация из коробки)."""

from pathlib import Path

import numpy as np
import sherpa_onnx

from stenograf_core.audio import SAMPLE_RATE
from stenograf_core.hotwords import load_terms, normalize_term, write_hotwords_file
from stenograf_core.paths import models_dir

GIGAAM_FEATURE_DIM = 64
# GigaAM обучен на коротких отрезках, длинные фразы VAD режет принудительно
MAX_CHUNK_SEC = 20
VAD_WINDOW = 512
NUM_THREADS = 8
HOTWORDS_SCORE = 1.5
MODELING_UNIT = 'cjkchar'


def gigaam_dir() -> Path:
    return models_dir() / 'sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16'


def split_phrases(samples: np.ndarray) -> list[tuple[float, float]]:
    """Фразы режет VAD, не диаризация: её границы рвут слова посередине."""
    config = sherpa_onnx.VadModelConfig(
        silero_vad=sherpa_onnx.SileroVadModelConfig(
            model=str(models_dir() / 'silero_vad.onnx'),
            max_speech_duration=MAX_CHUNK_SEC,
        ),
        sample_rate=SAMPLE_RATE,
    )
    vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=MAX_CHUNK_SEC * 2)
    phrases: list[tuple[float, float]] = []

    def drain() -> None:
        while not vad.empty():
            phrases.append((vad.front.start / SAMPLE_RATE, (vad.front.start + len(vad.front.samples)) / SAMPLE_RATE))
            vad.pop()

    for offset in range(0, len(samples), VAD_WINDOW):
        vad.accept_waveform(samples[offset:offset + VAD_WINDOW])
        drain()

    vad.flush()
    drain()
    return phrases


def _build_recognizer(hotwords_path: Path | None) -> sherpa_onnx.OfflineRecognizer:
    root = gigaam_dir()
    kwargs: dict[str, object] = {
        'encoder': str(root / 'encoder.int8.onnx'),
        'decoder': str(root / 'decoder.onnx'),
        'joiner': str(root / 'joiner.onnx'),
        'tokens': str(root / 'tokens.txt'),
        'feature_dim': GIGAAM_FEATURE_DIM,
        'model_type': 'nemo_transducer',
        'num_threads': NUM_THREADS,
        'modeling_unit': MODELING_UNIT,
    }
    if hotwords_path is not None:
        kwargs.update(
            decoding_method='modified_beam_search',
            max_active_paths=4,
            hotwords_file=str(hotwords_path),
            hotwords_score=HOTWORDS_SCORE,
        )
    return sherpa_onnx.OfflineRecognizer.from_transducer(**kwargs)


def transcribe_gigaam(
    samples: np.ndarray,
    segments: list[tuple[float, float]],
    hotwords: Path | list[str] | None = None,
) -> list[str]:
    """hotwords: путь к словарю, список терминов или None (без beam/hotwords)."""
    prepared: Path | None = None
    if isinstance(hotwords, Path):
        terms = load_terms(hotwords)
        prepared = write_hotwords_file(terms, models_dir() / '.cache' / 'hotwords.runtime.txt')
    elif isinstance(hotwords, list):
        terms = [term for term in (normalize_term(item) for item in hotwords) if term]
        prepared = write_hotwords_file(terms, models_dir() / '.cache' / 'hotwords.runtime.txt')

    recognizer = _build_recognizer(prepared)
    streams = []
    for start, end in segments:
        stream = recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)])
        streams.append(stream)

    if streams:
        recognizer.decode_streams(streams)
    return [stream.result.text.strip() for stream in streams]
