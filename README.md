# Stenograf

**Локальный транскрибатор встреч для русского языка.**

Запись → распознавание речи → кто сказал что → протокол. Всё на своём компьютере, без облака и без бота в Zoom.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Status: PoC](https://img.shields.io/badge/status-PoC-orange.svg)](#roadmap)

> Альтернатива [Google AI Edge Foresight](https://vc.ru/id553757/3189473-google-ai-edge-foresight-lokalnyy-transkribator), [Meetily](https://meetily.ai/) и Granola: **русский ASR из коробки**, диаризация в открытом коде, интерфейс и промпты на русском.

---

## Зачем

Зарубежных opensource-транскрибаторов полно. Модели русский умеют. Сайты и UX - нет: английский по умолчанию, либо всё что угодно кроме русского.

Google Foresight локальный и красивый, но:

- только Mac + Apple Silicon
- только английская речь
- нет диаризации
- каждые 30 минут орёт, что слушает

Granola закрывает сценарий, но уносит аудио в облако.

**Stenograf** - privacy-first пайплайн под русские встречи с бизнесом: договорённости, размытые формулировки («как обычно», «побыстрее»), follow-up со ссылками на таймкоды.

## Что умеет сейчас (PoC)

- **Локальный ASR** на [GigaAM v3](https://github.com/salute-developers/GigaAM) (MIT) через [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- **Диаризация** (pyannote segmentation + NeMo TitaNet)
- **VAD-фразы** → спикер по пересечению с диаризацией (как WhisperX: границы диаризации не режут слова)
- **Пунктуация** из коробки (GigaAM punct)
- Любой аудиоформат через `ffmpeg` (m4a, mp3, wav, …)
- Сравнение с Whisper large-v3-turbo (`--ref`)

## Результаты на тестовом диалоге

Синтетический диалог 2 спикеров, ~57 с, macOS M-series, CPU 8 потоков:

| | GigaAM v3 | Whisper large-v3-turbo q5 |
|---|---|---|
| **WER** | **7.1%** | 10.2% |
| Время | 1.2 с (CPU) | 2.0 с (Metal) |
| Диаризация | да, 2/2 | нет |
| RTF всего пайплайна | ~0.05 | - |

Whisper на том же файле **молча пропустил** реплику «Хорошо, две секунды» - для протокола договорённостей это хуже, чем опечатка в цифре.

> Тест упрощённый: оба «голоса» из одного TTS со сдвигом тона. На реальных созвонах цифры будут другими - прогоняйте свои записи.

## Быстрый старт

### Требования

- macOS / Linux (Windows пока не проверяли)
- Python 3.12
- [uv](https://github.com/astral-sh/uv)
- [ffmpeg](https://ffmpeg.org/)
- ~500 МБ на модели (GigaAM + диаризация + VAD)

### Установка

```bash
git clone https://github.com/anatoly-kulishov/stenograf.git
cd stenograf

uv sync
./download_models.sh
```

### Запуск

```bash
# своя запись
uv run python poc.py путь/к/встрече.m4a

# известное число спикеров
uv run python poc.py встреча.m4a --speakers 2

# синтетический диалог + WER vs Whisper (нужен brew install whisper-cpp)
uv run python make_test_audio.py
uv run python poc.py audio/dialog.wav --ref audio/dialog.ref.json
```

Пример вывода:

```
### Транскрипт (57 с аудио)

[00:00] Спикер 1: Добрый день. Нам нужно, чтобы карточки товаров загружались быстрее и было удобно, как обычно.
[00:07] Спикер 2: Понял. Быстрее. Это сколько секунд сейчас и сколько хотите получить?
[00:14] Спикер 1: Сейчас где-то 10 секунд. Хотим примерно как у конкурентов, но побыстрее.
...
```

## Как устроено

```
аудио
  │
  ├─► pyannote + TitaNet ──► сегменты спикеров
  │
  └─► Silero VAD ──► фразы ──► GigaAM v3 ──► текст
                         │
                         └─► assign speaker by overlap ──► протокол
```

Почему VAD, а не куски от диаризации: границы кластеров часто режут слово пополам («оценку» → «Плоценку»). Фразы режет VAD, спикер вешается поверх.

## Roadmap

- [x] Offline ASR + диаризация на русском
- [x] Сравнение с Whisper
- [ ] Hotwords / словарь терминов (Excel, КТРУ, ОКПД)
- [ ] Прогон на реальных созвонах
- [ ] Саммари: договорённости, риски, вопросы заказчику (Ollama / локальная LLM)
- [ ] Экспорт Markdown / Obsidian + MCP
- [ ] Десктоп (форк [Meetily](https://github.com/Zackriya-Solutions/meeting-minutes) или свой Tauri)

## Стек

| Слой | Модель / либа | Лицензия |
|---|---|---|
| ASR | GigaAM v3 RNNT punct (Sber) | MIT |
| Runtime | sherpa-onnx | Apache-2.0 |
| VAD | Silero VAD | MIT |
| Segmentation | pyannote 3.0 (ONNX) | MIT |
| Embeddings | NeMo TitaNet small | Apache-2.0 / CC-BY |

## Почему не просто Whisper / Meetily

| | Foresight | Meetily CE | Stenograf |
|---|---|---|---|
| Русский ASR | нет | Whisper | **GigaAM** |
| Диаризация в OSS | нет | Pro only | **да** |
| Полностью локально | да | да | да |
| UI / промпты на русском | нет | нет | **цель** |
| macOS + Windows + Linux | только Mac | да | PoC: CLI |

## Acknowledgments

- [GigaAM](https://github.com/salute-developers/GigaAM) - SberDevices
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) - Xiaomi / k2-fsa
- [Meetily](https://github.com/Zackriya-Solutions/meeting-minutes) - референс десктопного UX
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) - бенчмарк

## License

MIT. Модели скачиваются отдельно и идут под своими лицензиями (см. таблицу выше).
