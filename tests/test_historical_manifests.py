from __future__ import annotations

from botsd.font_polish import UI80_FONTLINK_SHA256, load_spec as load_font_spec
from botsd.fontlink import (
    UE_DIAERESIS_COLUMNS,
    UE_INPUT_ASSET,
    UE_SOURCE_GLYPH_INDEX,
    UE_SOURCE_PAGE,
    UE_TARGET_GLYPH_INDEX,
    UE_TARGET_PAGE,
    load_ue_spec,
)
from botsd.keyboard import (
    HISTORICAL_V12_INPUT_SHA256,
    HISTORICAL_V12_NEW_MODE,
    MODE_OFFSET,
    MODE_VA,
    V13_FINAL_MODE,
    load_spec as load_keyboard_spec,
)
from botsd.manifest import (
    BASELINE,
    RETAIL_SHA256,
    RETAIL_UNPACK_SHA256,
    SECOND_NAME_FIRST,
    SECOND_NAME_LAST,
    UNPACK_SIZE,
)


def test_unpack_constants_come_from_release_manifest() -> None:
    assert UNPACK_SIZE == 151_525_376
    assert RETAIL_UNPACK_SHA256 == "179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece"
    assert (SECOND_NAME_FIRST, SECOND_NAME_LAST) == (2037, 2713)
    assert SECOND_NAME_LAST - SECOND_NAME_FIRST + 1 == BASELINE.card_resource_count


def test_keyboard_checkpoint_is_machine_readable() -> None:
    spec = load_keyboard_spec()
    assert MODE_VA == spec["mode_va"]
    assert MODE_OFFSET == spec["mode_file_offset"]
    assert HISTORICAL_V12_INPUT_SHA256 == spec["historical_input_sha256"]
    assert HISTORICAL_V12_NEW_MODE == 6
    assert V13_FINAL_MODE == 9


def test_font_polish_checkpoint_is_machine_readable() -> None:
    spec = load_font_spec()
    assert UI80_FONTLINK_SHA256 == spec["input_sha256"]
    assert spec["changed_members"] == ["half0000.lz", "half0004.lz"]
    assert spec["lowercase_l"]["expected_source_bbox"] == [10, 1, 14, 22]


def test_font_ue_checkpoint_is_machine_readable() -> None:
    spec = load_ue_spec()
    assert UE_INPUT_ASSET == spec["input_asset"] == "FONTLINK.PAC"
    assert RETAIL_SHA256[UE_INPUT_ASSET] == (
        "599ddb34c9756f7d60c0f00c24755dca64e0ae81b7ae8643367b169c9d746c7a"
    )
    assert UE_SOURCE_PAGE == spec["source_page"] == "half0003.lz"
    assert UE_TARGET_PAGE == spec["target_page"] == "half0005.lz"
    assert UE_SOURCE_GLYPH_INDEX == spec["source_glyph_index"] == 5
    assert UE_TARGET_GLYPH_INDEX == spec["target_glyph_index"] == 14
    assert UE_DIAERESIS_COLUMNS == tuple(spec["diaeresis_columns"]) == (2, 3, 7, 8)
