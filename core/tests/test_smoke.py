"""Протокол сайдкара и один прогон на синтетическом диалоге."""

import json
import subprocess
import sys
from pathlib import Path

import jiwer

from stenograf_core.cli import normalize
from stenograf_core.pipeline import transcribe_meeting
from stenograf_core.synth import build_dialog

# PoC дал 7.1%. Запас на дрейф TTS, не на сломанный пайплайн.
WER_CEILING = 0.2


def test_server_ping() -> None:
    proc = subprocess.run(
        [sys.executable, '-m', 'stenograf_core'],
        input='{"id": 1, "cmd": "ping"}\n',
        text=True,
        capture_output=True,
        check=True,
    )
    lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert lines[0] == {'event': 'ready'}
    assert lines[1] == {'id': 1, 'event': 'pong'}


def test_dialog_speakers_and_wer(tmp_path: Path) -> None:
    audio = build_dialog(tmp_path / 'dialog.wav')
    ref = json.loads(audio.with_suffix('.ref.json').read_text())

    turns = transcribe_meeting(None, audio)
    found = {turn.speaker for turn in turns}
    hypothesis = normalize(' '.join(turn.text for turn in turns))
    reference = normalize(' '.join(item['text'] for item in ref))

    assert len(found) == 2
    assert len(turns) >= 6
    assert jiwer.wer(reference, hypothesis) < WER_CEILING

    mine = transcribe_meeting(audio, None)
    assert mine and all(turn.speaker == 'me' for turn in mine)
