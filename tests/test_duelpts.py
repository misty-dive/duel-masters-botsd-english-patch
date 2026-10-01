from __future__ import annotations

from botsd.duelpts import load_spec


def test_issue2_spec_preserves_proven_fix_signature() -> None:
    spec = load_spec()
    assert spec["target_member"] == "DUELPTS_SRC_G_P00_TGA"
    assert spec["digit_restore"] == [128, 357, 221, 385]
    assert spec["old_left_box"] == [145, 374, 221, 408]
    assert spec["new_left_bbox"] == [149, 385, 219, 408]
    assert spec["expected_v11_damage"] == {
        "1": 0, "2": 0, "3": 0, "4": 0, "5": 0,
        "6": 71, "7": 136, "8": 205, "9": 206,
    }
    assert spec["expected_output_sha256"] == (
        "7162d840c58aca34391819c2df2787013454b0ad45449d1be2cab353f4ec7de3"
    )
