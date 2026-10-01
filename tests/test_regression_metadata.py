from botsd.regressions import VISUAL_REGRESSIONS


def test_visual_regressions_are_named_and_hash_guarded():
    names = {r.name for r in VISUAL_REGRESSIONS}
    assert names == {"CHANGE TURN clipping", "Deck Builder ACE badge", "Duel digits 6-9"}
    for regression in VISUAL_REGRESSIONS:
        assert len(regression.expected_sha256) == 64
        int(regression.expected_sha256, 16)
