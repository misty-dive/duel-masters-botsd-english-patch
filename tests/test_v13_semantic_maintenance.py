from __future__ import annotations

import json
from importlib.resources import files

from botsd.exe_maintenance import load_spec as load_exe_spec
from botsd.localization import load_language_json
from botsd.scrpack import load_spec as load_scrpack_spec


def test_v13_executable_recipe_is_structural_not_raw_patch_table() -> None:
    cfg = load_exe_spec()
    assert cfg["master_overlap_repair"] == {
        "source_master_id": 2372,
        "intruder_master_id": 1161,
        "shift_bytes": 2,
        "reason": cfg["master_overlap_repair"]["reason"],
    }
    assert cfg["keyboard"]["old_mode"] == 6
    assert cfg["keyboard"]["new_mode"] == 9
    text = files("botsd").joinpath("assets", "exe_v13.json").read_text(encoding="utf-8")
    assert "offset" not in json.loads(text)["master_overlap_repair"]


def test_v13_scrpack_recipe_uses_command_ordinals() -> None:
    cfg = load_scrpack_spec()
    assert [row["chunk"] for row in cfg["branch_relocations"]] == [32, 32, 162]
    assert [row["branch_command_index"] for row in cfg["branch_relocations"]] == [326, 938, 123]
    assert [row["target_command_index"] for row in cfg["branch_relocations"]] == [479, 956, 141]
    assert cfg["dialogue_edits"][0]["command_index"] == 646
    assert all("file_offset" not in row for row in cfg["branch_relocations"])


def test_v13_dialogue_text_lives_in_english_localization_package() -> None:
    data = load_language_json("en", "v13_maintenance.json")
    row = data["dialogue"]["world_balance_wrap"]
    assert row["source"].endswith("release...")
    assert "#cr0" in row["replacement"]
    assert row["review_status"] == "runtime_verified"
