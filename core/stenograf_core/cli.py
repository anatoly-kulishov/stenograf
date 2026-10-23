"""CLI: одна дорожка с диаризацией или две (mic + system), либо eval встречи."""

import argparse
import json
import time
from pathlib import Path

import jiwer

from stenograf_core.asr import NUM_THREADS
from stenograf_core.eval_meeting import evaluate_meeting, list_meetings
from stenograf_core.hotwords import DEFAULT_HOTWORDS
from stenograf_core.metrics import normalize
from stenograf_core.paths import models_dir
from stenograf_core.pipeline import transcribe_meeting


def transcribe_whisper(path: Path) -> str:
    model = models_dir() / 'ggml-large-v3-turbo-q5_0.bin'
    import subprocess

    out = subprocess.run(
        ['whisper-cli', '-m', str(model), '-l', 'ru', '-t', str(NUM_THREADS), '-nt', '-np', '-f', str(path)],
        check=True, capture_output=True, text=True,
    )
    return ' '.join(out.stdout.split())


def _print_turns(turns) -> None:
    print('\n### Транскрипт\n')
    for turn in turns:
        who = 'Я' if turn.speaker == 'me' else turn.speaker.replace('speaker-', 'Спикер ')
        print(f'[{int(turn.start // 60):02d}:{int(turn.start % 60):02d}] {who}: {turn.text}')


def _hotwords_arg(args: argparse.Namespace) -> Path | bool:
    if args.no_hotwords:
        return False
    if args.hotwords:
        return args.hotwords
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', type=Path, nargs='?', help='одна дорожка, диаризация спикеров')
    parser.add_argument('--mic', type=Path)
    parser.add_argument('--system', type=Path)
    parser.add_argument('--ref', type=Path, help='эталон: WER и сравнение с Whisper')
    parser.add_argument('--speakers', type=int, default=-1)
    parser.add_argument('--hotwords', type=Path, help=f'словарь терминов (по умолчанию {DEFAULT_HOTWORDS.name})')
    parser.add_argument('--no-hotwords', action='store_true', help='greedy_search без словаря')
    parser.add_argument('--eval', type=Path, help='каталог eval/meetings или одна встреча')
    args = parser.parse_args()

    if args.eval is not None:
        root = args.eval
        meetings = [root] if (root / 'ref.json').is_file() else list_meetings(root)
        if not meetings:
            parser.error(f'нет встреч с ref.json в {root}')
        for meeting in meetings:
            report, turns = evaluate_meeting(meeting, hotwords=_hotwords_arg(args), num_speakers=args.speakers)
            print(f'\n## {meeting.name}')
            _print_turns(turns)
            print(
                f'\nWER {report.wer:.1%} | спикеры {report.hyp_speakers}/{report.ref_speakers} | '
                f'реплики {report.hyp_turns}/{report.ref_turns} | '
                f'пропуски {report.missed_turns} ({report.missed_ratio:.0%})'
            )
            (meeting / 'hyp.json').write_text(
                json.dumps([turn.to_json() for turn in turns], ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            (meeting / 'metrics.json').write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        return

    mic = args.mic
    system = args.system or args.audio
    if mic is None and system is None:
        parser.error('нужен файл, --mic/--system или --eval')

    started = time.perf_counter()
    turns = transcribe_meeting(mic, system, num_speakers=args.speakers, hotwords=_hotwords_arg(args))
    elapsed = time.perf_counter() - started

    _print_turns(turns)
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
