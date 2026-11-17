from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from botsd.hashing import sha256_bytes
from botsd.v14 import build_v14


ROOT = Path(__file__).resolve().parents[1]


def test_v14_recipe_records_exact_release_hashes_and_counts() -> None:
    spec = json.loads((ROOT / "botsd/assets/v14.json").read_text(encoding="utf-8"))
    strings = json.loads(
        (ROOT / "localization/en/v14_maintenance.json").read_text(encoding="utf-8")
    )
    assert spec["v14"]["full_ppf_sha256"] == (
        "2a37012be8ea61ecb9c2cecf1d1f2295a75bb3f3ec50dd00cca022cff8596767"
    )
    assert spec["v14"]["hotfix_from_v13_sha256"] == (
        "7acfd4fdf4a28eaa236f7e198e9056d86b75287d05eee8ab523514dbbb680237"
    )
    assert spec["v14"]["full_ppf_size"] == 141102291
    assert spec["v14"]["hotfix_from_v13_size"] == 14352
    assert spec["v14"]["executable_differing_bytes"] == 839
    assert spec["v14"]["scrpack_differing_bytes"] == 5038
    assert len(strings["races"]) == 27
    assert len(strings["overflow_dialogue"]) == 56
    assert len(strings["xenon_dialogue"]) == 11
    assert len(strings["xenon_payload_sizes"]) == 19


def test_v14_localization_is_cp932_safe_and_ids_are_stable() -> None:
    strings = json.loads(
        (ROOT / "localization/en/v14_maintenance.json").read_text(encoding="utf-8")
    )
    ids: list[str] = []
    for group in ("races", "overflow_dialogue", "xenon_dialogue"):
        for row in strings[group]:
            ids.append(str(row["id"]))
            row["source"].encode("cp932")
            row["replacement"].encode("cp932")
            assert row["review_status"] == "human_reviewed"
    assert len(ids) == len(set(ids))


def test_optional_exact_v14_component_rebuild() -> None:
    v13_dir = os.environ.get("BOTSD_V13_COMPONENT_DIR")
    retail_dir = os.environ.get("BOTSD_RETAIL_COMPONENT_DIR")
    if not v13_dir or not retail_dir:
        pytest.skip(
            "set BOTSD_V13_COMPONENT_DIR and BOTSD_RETAIL_COMPONENT_DIR "
            "for exact v1.4 component regression"
        )

    exe = (Path(v13_dir) / "SLPM_658.82").read_bytes()
    scr = (Path(v13_dir) / "SCRPACK.SDA").read_bytes()
    retail = (Path(retail_dir) / "SCRPACK.SDA").read_bytes()
    result = build_v14(exe, scr, retail)

    assert sha256_bytes(result.executable) == (
        "2c5114dd5aff14a27e1f38f6a47eeaf6e21b1fab9edd00b3d880eda6d90adca3"
    )
    assert sha256_bytes(result.scrpack) == (
        "fe5e451f4587983fdb8dd4bca1b8d816aa3efd53eaf0268f9ed72a66cc741145"
    )
    assert result.executable_differing_bytes == 839
    assert result.scrpack_differing_bytes == 5038
