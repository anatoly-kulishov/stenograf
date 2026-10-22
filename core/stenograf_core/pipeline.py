"""Сборка реплик: mic = «Я», system = диаризация собеседников."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from stenograf_core.asr import split_phrases, transcribe_gigaam
from stenograf_core.audio import SAMPLE_RATE, load_audio
from stenograf_core.diarize import assign_speakers, diarize

Progress = Callable[[str, int], None]


@dataclass
class Turn:
    start: float
    speaker: str
    text: str

    def to_json(self) -> dict[str, float | str]:
        return asdict(self)


def _noop(_stage: str, _pct: int) -> None:
    return None


def _label(cluster: int, labels: dict[int, str]) -> str:
    return labels.setdefault(cluster, f'speaker-{len(labels) + 1}')


def transcribe_track(path: Path, speaker: str | None, on_progress: Progress, num_speakers: int) -> list[Turn]:
    """speaker='me' без диаризации. speaker=None - кластера sherpa-onnx."""
    on_progress('load', 10)
    samples = load_audio(path)
    if len(samples) < SAMPLE_RATE // 5:
        return []

    on_progress('vad', 25)
    phrases = split_phrases(samples)
    on_progress('asr', 45)
    texts = transcribe_gigaam(samples, phrases)

    if speaker == 'me':
        speakers = ['me'] * len(phrases)
    else:
        on_progress('diarize', 70)
        clusters = assign_speakers(phrases, diarize(samples, num_speakers=num_speakers))
        labels: dict[int, str] = {}
        speakers = [_label(cluster, labels) for cluster in clusters]

    return [
        Turn(start, spk, text)
        for (start, _), spk, text in zip(phrases, speakers, texts)
        if text
    ]


def merge_turns(turns: list[Turn]) -> list[Turn]:
    ordered = sorted(turns, key=lambda turn: turn.start)
    merged: list[Turn] = []
    for turn in ordered:
        if merged and merged[-1].speaker == turn.speaker:
            merged[-1] = Turn(merged[-1].start, turn.speaker, f'{merged[-1].text} {turn.text}')
        else:
            merged.append(turn)
    return merged


def transcribe_meeting(
    mic: Path | None,
    system: Path | None,
    on_progress: Progress | None = None,
    num_speakers: int = -1,
) -> list[Turn]:
    report = on_progress or _noop
    turns: list[Turn] = []
    if mic is not None:
        turns.extend(transcribe_track(mic, 'me', report, num_speakers))
    if system is not None:
        turns.extend(transcribe_track(system, None, report, num_speakers))
    report('done', 100)
    return merge_turns(turns)
