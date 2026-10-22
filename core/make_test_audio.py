"""Сгенерировать audio/dialog.wav и эталон рядом."""

from pathlib import Path

from stenograf_core.synth import DIALOG, build_dialog


def main() -> None:
    out = build_dialog(Path('audio/dialog.wav'))
    print(f'{out} готов, реплик: {len(DIALOG)}')


if __name__ == '__main__':
    main()
