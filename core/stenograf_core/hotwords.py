"""Словарь терминов для sherpa-onnx modified_beam_search."""

from pathlib import Path

# GigaAM tokens: кириллица кодируется целиком, латиница - по буквам через пробел.
DEFAULT_HOTWORDS = Path(__file__).resolve().parent / 'data' / 'hotwords.txt'


def normalize_term(term: str) -> str:
    term = term.strip().lower().replace('ё', 'е')
    if not term or term.startswith('#'):
        return ''
    # суффикс :score в формате sherpa
    score = ''
    if ' :' in term:
        term, score = term.rsplit(' :', 1)
        term = term.strip()
        score = f' :{score.strip()}'

    pieces: list[str] = []
    for word in term.split():
        if any('a' <= char <= 'z' for char in word):
            pieces.append(' '.join(word))
        else:
            pieces.append(word)
    return (' '.join(pieces) + score).strip()


def load_terms(path: Path | None = None) -> list[str]:
    source = path or DEFAULT_HOTWORDS
    if not source.is_file():
        return []
    terms: list[str] = []
    for line in source.read_text(encoding='utf-8').splitlines():
        encoded = normalize_term(line)
        if encoded:
            terms.append(encoded)
    return terms


def write_hotwords_file(terms: list[str], dest: Path) -> Path | None:
    if not terms:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('\n'.join(terms) + '\n', encoding='utf-8')
    return dest
