from __future__ import annotations

from botsd.card_sources import choose_candidate, git_blob_sha1, normalize_name


def test_git_blob_sha1_uses_git_object_identity() -> None:
    # Canonical Git blob hash for b"test\n".
    assert git_blob_sha1(b"test\n") == "9daeafb9864cf43055ae93beb0afd6c7d144bfa4"


def test_normalize_name_is_accent_and_punctuation_insensitive() -> None:
    assert normalize_name("Überdragon Baham") == normalize_name("Uberdragon-Baham")


def test_choose_candidate_prefers_matching_numbered_set() -> None:
    rows = [
        {"card_id": 12, "card_set": "DM-02"},
        {"card_id": 18, "card_set": "DM-01"},
    ]
    chosen, status = choose_candidate(rows, "DM-01")
    assert chosen is not None and chosen["card_id"] == 18
    assert status == "official_set"


def test_choose_candidate_prefers_official_promo_for_special() -> None:
    rows = [
        {"card_id": 9500, "card_set": "Community"},
        {"card_id": 9007, "card_set": "Promo"},
    ]
    chosen, status = choose_candidate(rows, "Special/Promo")
    assert chosen is not None and chosen["card_id"] == 9007
    assert status == "official_promo"
