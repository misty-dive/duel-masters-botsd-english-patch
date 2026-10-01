from __future__ import annotations

import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path

import pytest

from botsd.hashing import sha256_bytes
from botsd.localization import load_language_json
from botsd.manifest import BASELINE
from botsd.semantic_assets import _decode_symbol_template
from botsd.v13 import build_component


def _json(name: str):
    return json.loads(files("botsd").joinpath("assets", name).read_text(encoding="utf-8"))


def test_ace_badge_recipe_separates_language_pixels_from_binary_geometry():
    cfg = _json("ace_badge_v13.json")
    language = load_language_json("en", "ace_badge_v13.json")["records"][0]
    assert "rows" not in cfg
    assert language["label"] == "ACE"
    width, height, pixels = _decode_symbol_template(cfg, language)
    assert (width, height) == (18, 16)
    assert len(pixels) == 288
    assert hashlib.sha256(pixels).hexdigest() == (
        "10bb4acdefe146b70177eba7e4a4df9aabda819889a1dee10e34e2b77cf563ff"
    )
    assert set(cfg["palette_symbols"]) == {"K", "a", "b", "c", "d", "e", "f", "g", "W"}
    # The visible word uses white and black pixels, while the rest rebuilds the badge background.
    assert pixels.count(255) == 49
    assert pixels.count(13) == 43
    assert cfg["compression"] == {"mode": "fast", "max_candidates": 96}
    assert cfg["expected_stored_size"] == 27520


def test_tchange_recipe_describes_layout_not_target_blob():
    cfg = _json("tchange_layout_v13.json")
    assert cfg["member"] == "STRIG_IMG_TCHANGE_TGA"
    assert cfg["background_index"] == 215
    assert cfg["clear_rect"] == [0, 29, 256, 130]
    assert [layer["name"] for layer in cfg["layers"]] == ["CHANGE", "TURN"]
    assert cfg["layers"][0]["shift"] == [0, -47]
    assert cfg["layers"][1]["shift"] == [-32, 47]
    assert cfg["compression"] == {"mode": "optimal", "max_candidates": 256}
    assert cfg["expected_stored_size"] == 12227


@pytest.mark.parametrize("name", ["SLPM_658.82", "SCRPACK.SDA", "TCHANGE.IMG", "DECK.DAT"])
def test_optional_exact_v13_component_regression(name: str):
    """Golden release regression when a maintainer supplies legal v1.2 component bytes.

    CI intentionally does not ship copyrighted game files, so the test skips there. A local
    maintainer can set BOTSD_V12_COMPONENT_DIR and all four published v1.3 hashes become
    permanent executable regressions, including the semantic visual builders.
    """
    root = os.environ.get("BOTSD_V12_COMPONENT_DIR")
    if not root:
        pytest.skip("set BOTSD_V12_COMPONENT_DIR for exact release-component regressions")
    path = Path(root) / name
    if not path.is_file():
        pytest.skip(f"missing local v1.2 component: {path}")
    source = path.read_bytes()
    target = build_component(name, source)
    assert len(target) == BASELINE.component(name).v13.size
    assert sha256_bytes(target) == BASELINE.component(name).v13.sha256
