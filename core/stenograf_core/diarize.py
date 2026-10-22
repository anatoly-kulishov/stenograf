"""Диаризация: pyannote segmentation 3.0 + NeMo TitaNet через sherpa-onnx."""

from pathlib import Path

import numpy as np
import sherpa_onnx

from stenograf_core.asr import NUM_THREADS
from stenograf_core.paths import models_dir

# на тестовом диалоге titanet разметил 8/8 реплик, campplus путался
DEFAULT_EMBEDDING = 'nemo_en_titanet_small.onnx'


def diarize(
    samples: np.ndarray,
    num_speakers: int = -1,
    embedding: Path | None = None,
    threshold: float = 0.5,
) -> list[tuple[float, float, int]]:
    root = models_dir()
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(root / 'sherpa-onnx-pyannote-segmentation-3-0/model.onnx'),
            ),
            num_threads=NUM_THREADS,
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(embedding or root / DEFAULT_EMBEDDING),
            num_threads=NUM_THREADS,
        ),
        # num_clusters=-1 -> число спикеров по порогу
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_speakers, threshold=threshold),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    result = sherpa_onnx.OfflineSpeakerDiarization(config).process(samples).sort_by_start_time()
    return [(seg.start, seg.end, seg.speaker) for seg in result]


def assign_speakers(phrases: list[tuple[float, float]], turns: list[tuple[float, float, int]]) -> list[int]:
    """Спикер фразы = спикер с максимальным пересечением по времени."""
    speakers: list[int] = []
    for start, end in phrases:
        overlap: dict[int, float] = {}
        for turn_start, turn_end, speaker in turns:
            overlap[speaker] = overlap.get(speaker, 0.0) + max(0.0, min(end, turn_end) - max(start, turn_start))

        best = max(overlap, key=overlap.get, default=None)
        if best is not None and overlap[best] > 0:
            speakers.append(best)
        else:
            speakers.append(speakers[-1] if speakers else 0)
    return speakers
