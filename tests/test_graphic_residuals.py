from __future__ import annotations

from pathlib import Path

from botsd.graphic_residuals import load_spec


ROOT = Path(__file__).resolve().parents[1]


def test_graphic_residual_spec_is_hash_guarded_and_contained() -> None:
    spec = load_spec(ROOT / "botsd" / "assets" / "graphic_residuals_ui82.json")
    assert set(spec) >= {"lobby", "tour", "deck"}
    for key in ("lobby", "tour", "deck"):
        assert len(spec[key]["input_sha256"]) == 64
        assert spec[key]["member"].endswith("_TGA")
    assert spec["lobby"]["label"] == "NO RANK"
    assert spec["tour"]["label"] == "BLOCK C"
    assert spec["deck"]["label"] == "HOF"
