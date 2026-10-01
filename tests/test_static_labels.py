from __future__ import annotations

from pathlib import Path

from botsd.static_labels import load_asset_spec, load_strings


ROOT = Path(__file__).resolve().parents[1]


def test_static_label_specs_and_localization_are_separate() -> None:
    spec = load_asset_spec(ROOT / "botsd" / "assets" / "static_labels_ui81.json")
    strings = load_strings(ROOT / "localization" / "en" / "static_labels_ui81.json")
    ids = set()
    for archive in spec["archives"].values():
        assert len(archive["input_sha256"]) == 64
        for edits in archive["members"].values():
            for edit in edits:
                ids.add(edit["text_id"])
                assert len(edit["box"]) == 4
    assert ids == set(strings)
    assert strings["left"] == "LEFT"
    assert strings["character_select"] == "CHARACTER SELECT"
