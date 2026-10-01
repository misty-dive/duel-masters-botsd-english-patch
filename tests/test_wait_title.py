from __future__ import annotations

from pathlib import Path

from botsd.wait_title import load_spec, load_strings


ROOT = Path(__file__).resolve().parents[1]


def test_wait_title_semantics_are_externalized() -> None:
    spec = load_spec(ROOT / "botsd" / "assets" / "wait_title_ui82.json")
    strings = load_strings(ROOT / "localization" / "en" / "wait_title_ui82.json")
    assert len(spec["wait"]["input_sha256"]) == 64
    assert len(spec["title"]["input_sha256"]) == 64
    assert spec["wait"]["text_id"] in strings
    assert strings["please_wait"] == "Please wait..."
    assert spec["title"]["member"] == "TITLE_SRC_TITLE_01_TGA"
    assert len(spec["title"]["clear_boxes"]) == 2
