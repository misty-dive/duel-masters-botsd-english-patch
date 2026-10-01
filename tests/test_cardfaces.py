from __future__ import annotations

import csv
import struct

from PIL import Image

from botsd.cardfaces import CardFaceRenderer, apply_master_overrides, ascii_text, load_spec, patch_small


class FakeFont:
    def text_mask(self, text: str, spacing: int = 1):
        width = max(1, len(text) * 5 + max(0, len(text) - 1) * spacing)
        return Image.new("L", (width, 12), 255)


def make_indexed_tga(width: int, height: int, fill: int = 0) -> bytes:
    header = bytearray(18)
    header[1] = 1
    header[2] = 1
    struct.pack_into("<HHB", header, 3, 0, 256, 32)
    struct.pack_into("<HHHHBB", header, 8, 0, 0, width, height, 8, 0x20)
    palette = bytearray()
    for value in range(256):
        palette.extend((value, value, value, 255))
    return bytes(header + palette + bytes([fill]) * (width * height))


def test_cardface_spec_tracks_three_layer_layout() -> None:
    spec = load_spec()
    assert spec.card_count == 677
    assert spec.large_chunk_first == 677
    assert spec.small_chunk_first == 1360
    assert spec.title_box == (82, 16, 362, 65)
    assert spec.panel_box == (44, 344, 356, 454)


def test_ascii_text_matches_historical_card_renderer_rules() -> None:
    assert ascii_text("■ Über  dragon\n") == "* Uber dragon"


def test_renderer_wraps_on_word_boundaries() -> None:
    spec = load_spec()
    renderer = CardFaceRenderer(FakeFont(), spec)
    lines = renderer.wrap("one two three four", 45)
    assert lines == ["one two", "three", "four"]


def test_master_override_uses_card_roles(tmp_path) -> None:
    rows = [{
        "internal_id": "7",
        "resource_key": "x",
        "english_name": "Old",
        "rules": "Old rules",
        "race": "Old race",
        "flavor": "",
        "card_type": "CREATURE",
    }]
    path = tmp_path / "master.csv"
    fields = ["master_text_id", "roles", "cards", "source_japanese", "translation"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"master_text_id": 1, "roles": "name", "cards": "7:x", "source_japanese": "", "translation": "New Name"},
            {"master_text_id": 2, "roles": "rules", "cards": "7:x", "source_japanese": "", "translation": "New Rules"},
            {"master_text_id": 3, "roles": "race", "cards": "7:x", "source_japanese": "", "translation": "New Race"},
            {"master_text_id": 4, "roles": "flavor", "cards": "7:x", "source_japanese": "", "translation": "New Flavor"},
        ])
    apply_master_overrides(rows, path)
    assert rows[0]["english_name"] == "New Name"
    assert rows[0]["rules"] == "New Rules"
    assert rows[0]["race"] == "New Race"
    assert rows[0]["flavor"] == "New Flavor"


def test_thumbnail_patch_is_box_contained() -> None:
    spec = load_spec()
    raw = make_indexed_tga(128, 128, fill=0)
    translated_large = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
    patched, changed = patch_small(raw, translated_large, spec)
    assert len(patched) == len(raw)
    assert changed > 0
