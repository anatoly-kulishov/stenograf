"""Метрики Sprint 2: WER, спикеры, пропуски реплик."""

from __future__ import annotations

import re
from dataclasses import dataclass

import jiwer


def normalize(text: str) -> str:
    text = text.lower().replace('ё', 'е')
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


@dataclass
class RefTurn:
    start: float
    speaker: str
    text: str
    end: float | None = None


@dataclass
class HypTurn:
    start: float
    speaker: str
    text: str


@dataclass
class EvalReport:
    wer: float
    ref_speakers: int
    hyp_speakers: int
    ref_turns: int
    hyp_turns: int
    missed_turns: int
    missed_ratio: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            'wer': self.wer,
            'ref_speakers': self.ref_speakers,
            'hyp_speakers': self.hyp_speakers,
            'ref_turns': self.ref_turns,
            'hyp_turns': self.hyp_turns,
            'missed_turns': self.missed_turns,
            'missed_ratio': self.missed_ratio,
        }


def _overlap(ref: RefTurn, hyp: HypTurn, default_len: float = 4.0) -> float:
    ref_end = ref.end if ref.end is not None else ref.start + default_len
    hyp_end = hyp.start + default_len
    return max(0.0, min(ref_end, hyp_end) - max(ref.start, hyp.start))


def count_missed_turns(ref: list[RefTurn], hyp: list[HypTurn], min_overlap: float = 0.3) -> int:
    """Реплика эталона пропущена, если нет гипотезы с пересечением по времени и общим словом."""
    missed = 0
    for item in ref:
        ref_words = set(normalize(item.text).split())
        if not ref_words:
            continue
        matched = False
        for cand in hyp:
            if _overlap(item, cand) < min_overlap:
                continue
            hyp_words = set(normalize(cand.text).split())
            if ref_words & hyp_words:
                matched = True
                break
        if not matched:
            missed += 1
    return missed


def score(ref: list[RefTurn], hyp: list[HypTurn]) -> EvalReport:
    ref_text = normalize(' '.join(item.text for item in ref))
    hyp_text = normalize(' '.join(item.text for item in hyp))
    wer = float(jiwer.wer(ref_text, hyp_text)) if ref_text else 0.0
    missed = count_missed_turns(ref, hyp)
    ref_n = len(ref)
    return EvalReport(
        wer=wer,
        ref_speakers=len({item.speaker for item in ref}),
        hyp_speakers=len({item.speaker for item in hyp}),
        ref_turns=ref_n,
        hyp_turns=len(hyp),
        missed_turns=missed,
        missed_ratio=(missed / ref_n) if ref_n else 0.0,
    )
