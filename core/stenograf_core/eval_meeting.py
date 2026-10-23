"""Прогон одной встречи из eval/meetings/<id>/."""

from __future__ import annotations

import json
from pathlib import Path

from stenograf_core.metrics import EvalReport, HypTurn, RefTurn, score
from stenograf_core.pipeline import Turn, transcribe_meeting


def load_ref(path: Path) -> list[RefTurn]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, list):
        raise ValueError(f'{path}: ожидался JSON-массив реплик')
    turns: list[RefTurn] = []
    for item in raw:
        turns.append(
            RefTurn(
                start=float(item.get('start', 0)),
                speaker=str(item['speaker']),
                text=str(item['text']),
                end=float(item['end']) if item.get('end') is not None else None,
            )
        )
    return turns


def hyp_from_turns(turns: list[Turn]) -> list[HypTurn]:
    return [HypTurn(start=turn.start, speaker=turn.speaker, text=turn.text) for turn in turns]


def resolve_audio(meeting_dir: Path) -> tuple[Path | None, Path | None]:
    mic = meeting_dir / 'mic.wav'
    system = meeting_dir / 'system.wav'
    audio = meeting_dir / 'audio.wav'
    if mic.is_file() or system.is_file():
        return (mic if mic.is_file() else None, system if system.is_file() else None)
    if audio.is_file():
        return None, audio
    raise FileNotFoundError(f'{meeting_dir}: нужен audio.wav или mic.wav/system.wav')


def evaluate_meeting(
    meeting_dir: Path,
    hotwords: Path | list[str] | bool | None = True,
    num_speakers: int = -1,
) -> tuple[EvalReport, list[Turn]]:
    ref_path = meeting_dir / 'ref.json'
    if not ref_path.is_file():
        raise FileNotFoundError(f'{meeting_dir}: нет ref.json')
    mic, system = resolve_audio(meeting_dir)
    turns = transcribe_meeting(mic, system, hotwords=hotwords, num_speakers=num_speakers)
    report = score(load_ref(ref_path), hyp_from_turns(turns))
    return report, turns


def list_meetings(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path for path in root.iterdir()
        if path.is_dir() and (path / 'ref.json').is_file()
    )
