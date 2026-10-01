from __future__ import annotations

import os
from pathlib import Path

import pytest

from botsd.cardtext import (
    DISPLAY_COUNT,
    MASTER_COUNT,
    build_combined_list,
    check_patch_sites,
    decode_game_text,
    encode_cp932,
    materialize_translation_rows,
    parse_combined_relative,
    parse_master_text,
    parse_retail_list,
    patch_executable,
    read_csv_rows,
)
from botsd.hashing import sha256_bytes
from botsd.manifest import LOCALIZED_ASSETS, RETAIL_SHA256


def test_game_text_ue_mapping_roundtrip() -> None:
    raw = encode_cp932("Überdragon", "name")
    assert raw == b"~berdragon"
    assert decode_game_text(raw) == "Überdragon"
    with pytest.raises(ValueError, match="reserved"):
        encode_cp932("literal~tilde")


def test_materialize_translation_rows_fallback_and_empty() -> None:
    rows = [
        {"id": "0", "source_japanese": "source zero", "translation": "English zero"},
        {"id": "1", "source_japanese": "fallback", "translation": ""},
        {"id": "2", "source_japanese": "not used", "translation": "<EMPTY>"},
    ]
    assert materialize_translation_rows(rows, "id", 3) == ["English zero", "fallback", ""]


def test_combined_list_roundtrip_and_deduplication() -> None:
    display = [f"display {i}" for i in range(DISPLAY_COUNT)]
    master = [f"master {i}" for i in range(MASTER_COUNT)]
    display[100] = display[0]
    master[100] = display[0]
    raw = build_combined_list(display, master)
    got_display, got_master = parse_combined_relative(raw)
    assert got_display == display
    assert got_master == master


def test_retail_cardtext_structures_when_sources_available() -> None:
    root = os.environ.get("BOTSD_RETAIL_COMPONENT_DIR")
    if not root:
        pytest.skip("set BOTSD_RETAIL_COMPONENT_DIR to exact retail component directory")
    root_path = Path(root)
    exe_path = root_path / "SLPM_658.82"
    list_path = root_path / "LIST_1.BIN"
    assert sha256_bytes(exe_path.read_bytes()) == RETAIL_SHA256["SLPM_658.82"]
    assert sha256_bytes(list_path.read_bytes()) == RETAIL_SHA256["LIST_1.BIN"]
    display = parse_retail_list(list_path)
    assert len(display) == DISPLAY_COUNT + 1
    executable = exe_path.read_bytes()
    assert len(parse_master_text(executable)) == MASTER_COUNT
    check_patch_sites(executable)
    patched = patch_executable(executable)
    assert len(patched) == len(executable)
    assert patched != executable


def test_public_v12_combined_list_when_available() -> None:
    root = os.environ.get("BOTSD_V12_COMPONENT_DIR")
    if not root:
        pytest.skip("set BOTSD_V12_COMPONENT_DIR to exact public-v1.2 component directory")
    path = Path(root) / "LIST_1.BIN"
    if not path.is_file():
        pytest.skip("public-v1.2 LIST_1.BIN is not present in component directory")
    raw = path.read_bytes()
    expected = LOCALIZED_ASSETS["LIST_1.BIN"]
    assert len(raw) == expected.size
    assert sha256_bytes(raw) == expected.sha256
    display, master = parse_combined_relative(raw)
    assert len(display) == DISPLAY_COUNT
    assert len(master) == MASTER_COUNT


def test_repository_csvs_rebuild_valid_combined_list() -> None:
    # The public CSVs are maintained translation sources, not a frozen byte snapshot of the
    # historical v1.2 LIST_1.BIN. Exact release-byte verification is covered separately above
    # when BOTSD_V12_COMPONENT_DIR supplies the published component.
    data = Path("data")
    display_path = data / "bosd_list_display_card_rules_complete.csv"
    master_path = data / "bosd_master_text_card_rules_complete.csv"
    if not display_path.is_file() or not master_path.is_file():
        pytest.skip("full repository data/ directory is not present in standalone overlay")
    display = materialize_translation_rows(
        read_csv_rows(display_path), "list_index", DISPLAY_COUNT
    )
    master = materialize_translation_rows(
        read_csv_rows(master_path), "master_text_id", MASTER_COUNT
    )
    raw = build_combined_list(display, master)
    rebuilt_display, rebuilt_master = parse_combined_relative(raw)
    assert rebuilt_display == display
    assert rebuilt_master == master
