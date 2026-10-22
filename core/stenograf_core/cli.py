"""CLI: одна дорожка с диаризацией или две (mic + system)."""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import jiwer

from stenograf_core.asr import NUM_THREADS
from stenograf_core.paths import models_dir
from stenograf_core.pipeline import transcribe_meeting


def normalize(text: str) -> str:
    text = text.lower().replace('ё', 'е')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


def transcribe_whisper(path: Path) -> str:
    model = models_dir() / 'ggml-large-v3-turbo-q5_0.bin'
    out = subprocess.run(
        ['whisper-cli', '-m', str(model), '-l', 'ru', '-t', str(NUM_THREADS), '-nt', '-np', '-f', str(path)],
        check=True, capture_output=True, text=True,
    )
    return ' '.join(out.stdout.split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', type=Path, nargs='?', help='одна дорожка, диаризация спикеров')
    parser.add_argument('--mic', type=Path)
    parser.add_argument('--system', type=Path)
    parser.add_argument('--ref', type=Path, help='эталон: WER и сравнение с Whisper')
    parser.add_argument('--speakers', type=int, default=-1)
    args = parser.parse_args()

    mic = args.mic
    system = args.system or args.audio
    if mic is None and system is None:
        parser.error('нужен файл или --mic/--system')

    started = time.perf_counter()
    turns = transcribe_meeting(mic, system, num_speakers=args.speakers)
    elapsed = time.perf_counter() - started

    print('\n### Транскрипт\n')
    for turn in turns:
        who = 'Я' if turn.speaker == 'me' else turn.speaker.replace('speaker-', 'Спикер ')
        print(f'[{int(turn.start // 60):02d}:{int(turn.start % 60):02d}] {who}: {turn.text}')
    print(f'\nГотово за {elapsed:.1f} с, реплик: {len(turns)}')

    if not args.ref:
        return

    ref = json.loads(args.ref.read_text())
    ref_text = normalize(' '.join(item['text'] for item in ref))
    expected = len({item['speaker'] for item in ref})
    found = len({turn.speaker for turn in turns})
    print(f'Спикеров найдено: {found} из {expected}, реплик: {len(turns)} из {len(ref)}')

    whisper_started = time.perf_counter()
    whisper_text = transcribe_whisper(system or mic)
    hypothesis = normalize(' '.join(turn.text for turn in turns))
    print(f'\nWER GigaAM v3:           {jiwer.wer(ref_text, hypothesis):.1%}')
    print(f'WER Whisper v3-turbo q5: {jiwer.wer(ref_text, normalize(whisper_text)):.1%} '
          f'({time.perf_counter() - whisper_started:.1f} с)')


if __name__ == '__main__':
    main()
