# Stenograf

**Локальный транскрибатор встреч для русского языка.**

Запись → распознавание речи → кто сказал что → протокол. Всё на своём компьютере, без облака и без бота в Zoom.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.1-blue.svg)](https://github.com/anatoly-kulishov/stenograf/releases/tag/v0.0.1)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![macOS 14.4+](https://img.shields.io/badge/macOS-14.4+-black.svg)](#быстрый-старт)

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

## Что умеет сейчас (v0.0.1)

- Десктоп на macOS: Tauri + запись микрофона и системного звука **двумя дорожками**
- **Локальный ASR** на [GigaAM v3](https://github.com/salute-developers/GigaAM) (MIT) через [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- **Диаризация** собеседников (pyannote segmentation + NeMo TitaNet). Микрофон = «Я» без диаризации
- **VAD-фразы** → спикер по пересечению с диаризацией (как WhisperX: границы диаризации не режут слова)
- **Пунктуация** из коробки (GigaAM punct)
- Индикатор записи в окне и в трее
- CLI для готовых файлов (`m4a`, `mp3`, `wav`, … через `ffmpeg`)
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

- macOS 14.4+ (Core Audio process taps; Windows после MVP)
- Python 3.12, [uv](https://github.com/astral-sh/uv), [ffmpeg](https://ffmpeg.org/)
- Node.js, [pnpm](https://pnpm.io/), Rust
- ~500 МБ на модели (не входят в бандл приложения)

### Установка и запуск

```bash
git clone https://github.com/anatoly-kulishov/stenograf.git
cd stenograf

pnpm setup    # модели + uv sync + pnpm install + ссылка в Application Support
pnpm dev      # приложение
```

Первый запуск спросит доступ к микрофону и к системному звуку. Скажите собеседникам, что ведёте заметки. «Стоп» отдаёт две дорожки в Python-сайдкар и показывает реплики «Я» / «Спикер N».

Пока в колонках тишина, системная дорожка может быть пустой: Core Audio tap не шлёт буферы, если выводить нечего.

| Команда | Что делает |
|---|---|
| `pnpm setup` | модели, ядро, зависимости, symlink моделей для `.app` |
| `pnpm dev` | Tauri в dev |
| `pnpm cli -- файл.m4a` | CLI транскрипции |
| `pnpm models` | только модели |
| `pnpm sidecar` | PyInstaller `--onedir` (~70 МБ без моделей) |
| `pnpm build` | сайдкар + `.app` |

Те же шаги: `scripts/*.sh`.

**Модели.** В репо: `./models`. Для собранного `.app` нужен тот же набор в  
`~/Library/Application Support/stenograf/models` - `pnpm setup` делает symlink. Без этого сайдкар упадёт на `silero_vad.onnx`.

### CLI

```bash
pnpm cli -- путь/к/встрече.m4a
pnpm cli -- --mic mic.wav --system system.wav

cd core
uv run python make_test_audio.py
uv run python -m stenograf_core.cli audio/dialog.wav --ref audio/dialog.ref.json
uv run pytest
```

Пример вывода:

```
### Транскрипт (57 с аудио)

[00:00] Спикер 1: Добрый день. Нам нужно, чтобы карточки товаров загружались быстрее и было удобно, как обычно.
[00:07] Спикер 2: Понял. Быстрее. Это сколько секунд сейчас и сколько хотите получить?
[00:14] Спикер 1: Сейчас где-то 10 секунд. Хотим примерно как у конкурентов, но побыстрее.
...
```

### Сборка `.app`

```bash
pnpm build
# → app/src-tauri/target/release/bundle/macos/Stenograf.app
```

Сборка без подписи Apple Developer ID: Gatekeeper может ругаться. Модели по-прежнему снаружи бандла.

Релизы: [GitHub Releases](https://github.com/anatoly-kulishov/stenograf/releases).

## Как устроено

```
React  →  Tauri (Rust)
            ├─ cpal: микрофон → mic.wav 16 кГц = «Я»
            └─ Core Audio tap (cidre): системный звук → system.wav 16 кГц
                 │
                 ▼
          Python-сайдкар, JSON lines stdin/stdout
            system: Silero VAD → GigaAM → диаризация по пересечению
            mic:    Silero VAD → GigaAM, спикер «Я»
```

Почему VAD, а не куски от диаризации: границы кластеров часто режут слово пополам («оценку» → «Плоценку»). Фразы режет VAD, спикер вешается поверх.

План спринтов: [docs/ROADMAP.md](docs/ROADMAP.md).

## Roadmap

- [x] Offline ASR + диаризация на русском
- [x] Сравнение с Whisper
- [x] macOS: две дорожки, Tauri, сайдкар (v0.0.1)
- [ ] Hotwords / словарь терминов (Excel, КТРУ, ОКПД)
- [ ] Прогон на реальных созвонах
- [ ] Саммари: договорённости, риски, вопросы заказчику (llama.cpp)
- [ ] Экспорт Markdown / Obsidian + MCP
- [ ] Windows (WASAPI loopback)
- [ ] Подпись и нотаризация `.app`

## Стек

| Слой | Модель / либа | Лицензия |
|---|---|---|
| ASR | GigaAM v3 RNNT punct (Sber) | MIT |
| Runtime | sherpa-onnx | Apache-2.0 |
| VAD | Silero VAD | MIT |
| Segmentation | pyannote 3.0 (ONNX) | MIT |
| Embeddings | NeMo TitaNet small | Apache-2.0 / CC-BY |
| Desktop | Tauri 2 + React | MIT / Apache-2.0 |

## Почему не просто Whisper / Meetily

| | Foresight | Meetily CE | Stenograf |
|---|---|---|---|
| Русский ASR | нет | Whisper | **GigaAM** |
| Диаризация в OSS | нет | Pro only | **да** |
| Полностью локально | да | да | да |
| UI / промпты на русском | нет | нет | **цель** |
| macOS + Windows + Linux | только Mac | да | macOS, CLI |

## Acknowledgments

- [GigaAM](https://github.com/salute-developers/GigaAM) - SberDevices
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) - Xiaomi / k2-fsa
- [Meetily](https://github.com/Zackriya-Solutions/meeting-minutes) - референс десктопного UX
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) - бенчмарк

## License

MIT. Модели скачиваются отдельно и идут под своими лицензиями (см. таблицу выше).
