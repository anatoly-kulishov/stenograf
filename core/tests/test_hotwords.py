"""Нормализация словаря и инициализация recognizer с hotwords."""

from pathlib import Path

from stenograf_core.asr import _build_recognizer, gigaam_dir
from stenograf_core.hotwords import load_terms, normalize_term, write_hotwords_file


def test_normalize_latin_spaced() -> None:
    assert normalize_term('Excel') == 'e x c e l'
    assert normalize_term('ктру') == 'ктру'
    assert normalize_term('как обычно') == 'как обычно'
    assert normalize_term('# comment') == ''


def test_default_hotwords_load() -> None:
    terms = load_terms()
    assert terms
    assert any('к' in term for term in terms)


def test_recognizer_with_hotwords(tmp_path: Path) -> None:
    if not gigaam_dir().is_dir():
        return
    path = write_hotwords_file(['ктру', 'e x c e l'], tmp_path / 'hw.txt')
    assert path is not None
    recognizer = _build_recognizer(path)
    assert recognizer is not None
