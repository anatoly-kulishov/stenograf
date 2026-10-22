"""Синтетический диалог двух спикеров (macOS `say` + ffmpeg).

ponytail: в системе один русский голос (Milena), второй спикер - сдвиг тона.
Для диаризации это упрощённый кейс; на реальных записях перепроверять.
"""

import json
import subprocess
import tempfile
from pathlib import Path

SAMPLE_RATE = 16000
PAUSE_SEC = 0.7
PITCH_DOWN = f'asetrate={SAMPLE_RATE}*0.8,aresample={SAMPLE_RATE},atempo=1.25'

DIALOG = [
    ('client', 'Добрый день. Нам нужно, чтобы карточки товаров загружались быстрее и было удобно, как обычно.'),
    ('dev', 'Понял. Быстрее - это сколько секунд сейчас и сколько хотите получить?'),
    ('client', 'Сейчас где-то десять секунд. Хотим примерно как у конкурентов, ну, побыстрее.'),
    ('dev', 'Давайте зафиксируем цель: загрузка списка из ста карточек не дольше двух секунд.'),
    ('client', 'Хорошо, две секунды. И ещё добавьте выгрузку в эксель до конца месяца.'),
    ('dev', 'Выгрузку делаем к тридцать первому октября. Какие колонки должны быть в файле?'),
    ('client', 'Все, которые есть в таблице. Ну и цены, наверное, тоже.'),
    ('dev', 'Цен в таблице сейчас нет. Это отдельная задача, я заведу её и пришлю оценку в пятницу.'),
]


def build_dialog(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        silence = Path(tmp, 'silence.wav')
        subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'anullsrc=r={SAMPLE_RATE}:cl=mono',
             '-t', str(PAUSE_SEC), str(silence)],
            check=True,
        )
        parts: list[Path] = []
        for num, (speaker, text) in enumerate(DIALOG):
            aiff = Path(tmp, f'{num:02d}.aiff')
            wav = Path(tmp, f'{num:02d}.wav')
            subprocess.run(['say', '-v', 'Milena', '-o', str(aiff), text], check=True)
            filters = ['-af', PITCH_DOWN] if speaker == 'dev' else []
            subprocess.run(
                ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(aiff), '-ar', str(SAMPLE_RATE), '-ac', '1', *filters, str(wav)],
                check=True,
            )
            parts += [wav, silence]

        concat_list = Path(tmp, 'list.txt')
        concat_list.write_text(''.join(f"file '{part}'\n" for part in parts))
        subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat_list), str(out)],
            check=True,
        )

    ref = [{'speaker': speaker, 'text': text} for speaker, text in DIALOG]
    out.with_suffix('.ref.json').write_text(json.dumps(ref, ensure_ascii=False, indent=2))
    return out
