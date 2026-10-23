"""JSON lines по stdin/stdout. Логи только в stderr."""

import json
import sys
import traceback
from pathlib import Path

from stenograf_core.pipeline import transcribe_meeting


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def handle(request: dict) -> None:
    request_id = request.get('id')
    command = request.get('cmd')
    if command == 'ping':
        emit({'id': request_id, 'event': 'pong'})
        return
    if command != 'transcribe':
        emit({'id': request_id, 'event': 'error', 'message': f'неизвестная команда: {command}'})
        return

    mic = Path(request['mic']) if request.get('mic') else None
    system = Path(request['system']) if request.get('system') else None
    hotwords: Path | bool
    if request.get('hotwords') is False:
        hotwords = False
    elif isinstance(request.get('hotwords'), str):
        hotwords = Path(request['hotwords'])
    else:
        hotwords = True

    def on_progress(stage: str, pct: int) -> None:
        emit({'id': request_id, 'event': 'progress', 'stage': stage, 'pct': pct})

    turns = transcribe_meeting(
        mic,
        system,
        on_progress,
        num_speakers=int(request.get('speakers', -1)),
        hotwords=hotwords,
    )
    emit({'id': request_id, 'event': 'result', 'turns': [turn.to_json() for turn in turns]})


def main() -> None:
    emit({'event': 'ready'})
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                emit({'event': 'error', 'message': 'ожидался JSON-объект'})
                continue
            request_id = request.get('id')
            handle(request)
        except Exception as exc:  # noqa: BLE001 - сайдкар не должен падать на одной команде
            traceback.print_exc(file=sys.stderr)
            emit({'id': request_id, 'event': 'error', 'message': str(exc)})


if __name__ == '__main__':
    main()
