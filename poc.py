"""PoC: диаризация + GigaAM v3 (sherpa-onnx) для русских встреч, сравнение с Whisper.

    uv run python poc.py audio/dialog.wav [--ref audio/dialog.ref.json] [--speakers 2]
"""

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

import jiwer
import sherpa_onnx
import soundfile as sf

SAMPLE_RATE = 16000
MODELS = Path('models')
GIGAAM = MODELS / 'sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16'
SEGMENTATION = MODELS / 'sherpa-onnx-pyannote-segmentation-3-0/model.onnx'
# на тестовом диалоге titanet разметил 8/8 реплик, campplus путался, eres2netv2 нестабилен при --speakers 2
EMBEDDING = MODELS / 'nemo_en_titanet_small.onnx'
VAD = MODELS / 'silero_vad.onnx'
WHISPER = MODELS / 'ggml-large-v3-turbo-q5_0.bin'

GIGAAM_FEATURE_DIM = 64
# GigaAM обучен на коротких отрезках, длинные фразы VAD режет принудительно
MAX_CHUNK_SEC = 20
VAD_WINDOW = 512
NUM_THREADS = 8


def load_audio(path: Path) -> list[float]:
    """Любой формат (m4a, mp3, ...) -> 16 kHz mono float32 через ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
        subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(path), '-ar', str(SAMPLE_RATE), '-ac', '1', tmp.name],
            check=True,
        )
        samples, _ = sf.read(tmp.name, dtype='float32')
    return samples


def diarize(samples, num_speakers: int, embedding: Path, threshold: float) -> list[tuple[float, float, int]]:
    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(SEGMENTATION)),
            num_threads=NUM_THREADS,
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(embedding), num_threads=NUM_THREADS),
        # num_clusters=-1 -> число спикеров по порогу
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_speakers, threshold=threshold),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    result = sherpa_onnx.OfflineSpeakerDiarization(config).process(samples).sort_by_start_time()
    return [(seg.start, seg.end, seg.speaker) for seg in result]


def split_phrases(samples) -> list[tuple[float, float]]:
    """Фразы для ASR режет VAD, а не диаризация: её границы рвут слова посередине."""
    config = sherpa_onnx.VadModelConfig(
        silero_vad=sherpa_onnx.SileroVadModelConfig(model=str(VAD), max_speech_duration=MAX_CHUNK_SEC),
        sample_rate=SAMPLE_RATE,
    )
    vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=MAX_CHUNK_SEC * 2)

    phrases = []

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


def assign_speakers(phrases: list[tuple[float, float]], turns: list[tuple[float, float, int]]) -> list[int]:
    """Спикер фразы = спикер с максимальным пересечением по времени."""
    speakers = []
    for start, end in phrases:
        overlap: dict[int, float] = {}
        for turn_start, turn_end, speaker in turns:
            overlap[speaker] = overlap.get(speaker, 0) + max(0.0, min(end, turn_end) - max(start, turn_start))

        best = max(overlap, key=overlap.get, default=None)
        speakers.append(best if best is not None and overlap[best] > 0 else (speakers[-1] if speakers else 0))
    return speakers


def transcribe_gigaam(samples, segments: list[tuple[float, float]]) -> list[str]:
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(GIGAAM / 'encoder.int8.onnx'),
        decoder=str(GIGAAM / 'decoder.onnx'),
        joiner=str(GIGAAM / 'joiner.onnx'),
        tokens=str(GIGAAM / 'tokens.txt'),
        feature_dim=GIGAAM_FEATURE_DIM,
        model_type='nemo_transducer',
        num_threads=NUM_THREADS,
    )

    streams = []
    for start, end in segments:
        stream = recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)])
        streams.append(stream)

    recognizer.decode_streams(streams)
    return [stream.result.text.strip() for stream in streams]


def transcribe_whisper(path: Path) -> str:
    out = subprocess.run(
        ['whisper-cli', '-m', str(WHISPER), '-l', 'ru', '-t', str(NUM_THREADS), '-nt', '-np', '-f', str(path)],
        check=True, capture_output=True, text=True,
    )
    return ' '.join(out.stdout.split())


def normalize(text: str) -> str:
    text = text.lower().replace('ё', 'е')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


def merge_turns(rows: list[tuple[float, int, str]]) -> list[tuple[float, int, str]]:
    turns = []
    for start, speaker, text in rows:
        if turns and turns[-1][1] == speaker:
            turns[-1] = (turns[-1][0], speaker, f'{turns[-1][2]} {text}')
        else:
            turns.append((start, speaker, text))
    return turns


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', type=Path)
    parser.add_argument('--ref', type=Path, help='эталон из make_test_audio.py: WER + сравнение с Whisper')
    parser.add_argument('--speakers', type=int, default=-1, help='число спикеров, если известно')
    parser.add_argument('--embedding', type=Path, default=EMBEDDING, help='модель эмбеддингов голоса')
    parser.add_argument('--threshold', type=float, default=0.5, help='порог кластеризации при --speakers -1')
    args = parser.parse_args()

    samples = load_audio(args.audio)
    duration = len(samples) / SAMPLE_RATE

    started = time.perf_counter()
    speaker_turns = diarize(samples, args.speakers, args.embedding, args.threshold)
    diarize_sec = time.perf_counter() - started

    started = time.perf_counter()
    phrases = split_phrases(samples)
    texts = transcribe_gigaam(samples, phrases)
    asr_sec = time.perf_counter() - started

    # метки кластеров произвольные, нумеруем в порядке появления
    labels: dict[int, int] = {}
    speakers = [labels.setdefault(spk, len(labels)) for spk in assign_speakers(phrases, speaker_turns)]
    turns = merge_turns([(start, spk, text) for (start, _), spk, text in zip(phrases, speakers, texts) if text])

    print(f'\n### Транскрипт ({duration:.0f} с аудио)\n')
    for start, speaker, text in turns:
        print(f'[{int(start // 60):02d}:{int(start % 60):02d}] Спикер {speaker + 1}: {text}')

    print(f'\nДиаризация: {diarize_sec:.1f} с, GigaAM: {asr_sec:.1f} с, '
          f'RTF {(diarize_sec + asr_sec) / duration:.3f} (CPU, {NUM_THREADS} потоков)')

    if not args.ref:
        return

    ref = json.loads(args.ref.read_text())
    ref_text = normalize(' '.join(item['text'] for item in ref))
    expected_speakers = len({item['speaker'] for item in ref})
    print(f'Спикеров найдено: {len({turn[1] for turn in turns})} из {expected_speakers}, '
          f'реплик: {len(turns)} из {len(ref)}')

    started = time.perf_counter()
    whisper_text = transcribe_whisper(args.audio)
    whisper_sec = time.perf_counter() - started

    gigaam_text = ' '.join(turn[2] for turn in turns)
    print(f'\nWER GigaAM v3:          {jiwer.wer(ref_text, normalize(gigaam_text)):.1%}')
    print(f'WER Whisper v3-turbo q5: {jiwer.wer(ref_text, normalize(whisper_text)):.1%} '
          f'({whisper_sec:.1f} с, Metal GPU, без диаризации)')
    print(f'\nWhisper: {whisper_text}')


if __name__ == '__main__':
    main()
