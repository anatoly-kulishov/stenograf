from stenograf_core.metrics import HypTurn, RefTurn, score


def test_score_perfect() -> None:
    ref = [RefTurn(0.0, '1', 'привет ктру'), RefTurn(3.0, '2', 'понял')]
    hyp = [HypTurn(0.0, 'speaker-1', 'привет ктру'), HypTurn(3.0, 'speaker-2', 'понял')]
    report = score(ref, hyp)
    assert report.wer == 0.0
    assert report.missed_turns == 0
    assert report.ref_speakers == 2


def test_score_missed_turn() -> None:
    ref = [
        RefTurn(0.0, '1', 'первая фраза'),
        RefTurn(10.0, '2', 'секретная реплика которую пропустили'),
    ]
    hyp = [HypTurn(0.0, 'speaker-1', 'первая фраза')]
    report = score(ref, hyp)
    assert report.missed_turns == 1
    assert report.missed_ratio == 0.5
