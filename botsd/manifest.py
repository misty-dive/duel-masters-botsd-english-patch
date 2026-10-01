from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any


@dataclass(frozen=True)
class ComponentVersion:
    size: int
    sha256: str


@dataclass(frozen=True)
class Component:
    name: str
    iso_offset: int
    v12: ComponentVersion
    v13: ComponentVersion




@dataclass(frozen=True)
class CardTextLayout:
    load_va_delta: int
    master_table_va: int
    loop_count_va: int
    loader_return_va: int
    code_cave_va: int
    text_resource_global_gp_offset: int
    card_text_object_global_gp_offset: int
    retail_list_pointer_count: int


@dataclass(frozen=True)
class DeckTextLayout:
    callout_offset: int
    callout_size: int
    title_offset: int
    title_size: int
    data_offset: int
    record_count: int


@dataclass(frozen=True)
class ShopBoosterLayout:
    table_offset: int
    record_stride: int
    code_offset: int
    code_size: int
    description_offset: int
    description_size: int
    metadata_offset: int
    metadata_size: int


@dataclass(frozen=True)
class Baseline:
    serial: str
    release: str
    clean_iso_size: int
    clean_iso_sha256: str
    patched_iso_size: int
    full_ppf_size: int
    full_ppf_sha256: str
    hotfix_from_v12_size: int
    hotfix_from_v12_sha256: str
    internal_card_count: int
    card_resource_count: int
    display_text_count: int
    master_text_count: int
    components: tuple[Component, ...]

    @property
    def combined_text_pointer_count(self) -> int:
        return self.display_text_count + self.master_text_count

    def component(self, name: str) -> Component:
        for component in self.components:
            if component.name.casefold() == name.casefold():
                return component
        raise KeyError(name)


def _load() -> dict[str, Any]:
    text = files("botsd").joinpath("release_manifest.json").read_text(encoding="utf-8")
    return json.loads(text)


def _version(raw: dict[str, Any]) -> ComponentVersion:
    return ComponentVersion(int(raw["size"]), str(raw["sha256"]))


_RAW = _load()
_COUNTS = _RAW["counts"]
BASELINE = Baseline(
    serial=str(_RAW["serial"]),
    release=str(_RAW["release"]),
    clean_iso_size=int(_RAW["clean_iso"]["size"]),
    clean_iso_sha256=str(_RAW["clean_iso"]["sha256"]),
    patched_iso_size=int(_RAW["patched_iso"]["size"]),
    full_ppf_size=int(_RAW["full_ppf"]["size"]),
    full_ppf_sha256=str(_RAW["full_ppf"]["sha256"]),
    hotfix_from_v12_size=int(_RAW["hotfix_from_v12"]["size"]),
    hotfix_from_v12_sha256=str(_RAW["hotfix_from_v12"]["sha256"]),
    internal_card_count=int(_COUNTS["internal_cards"]),
    card_resource_count=int(_COUNTS["card_resources"]),
    display_text_count=int(_COUNTS["display_text"]),
    master_text_count=int(_COUNTS["master_text"]),
    components=tuple(
        Component(
            name=str(row["name"]),
            iso_offset=int(row["iso_offset"]),
            v12=_version(row["v12"]),
            v13=_version(row["v13"]),
        )
        for row in _RAW["components"]
    ),
)

# Release constants are derived from the single JSON manifest above.
DUELPTS_V13_SHA256 = str(_RAW["duelpts"]["sha256"])
DUELPTS_ISO_OFFSET = int(_RAW["duelpts"]["iso_offset"])
CARD_LAYER_RANGES = tuple(tuple(int(value) for value in row) for row in _RAW["card_layer_ranges"])
KEYBOARD_MODE_FILE_OFFSET = int(_RAW["keyboard"]["mode_file_offset"])
KEYBOARD_MODE_VA = int(_RAW["keyboard"]["mode_va"])

V12_FULL_PPF_SHA256 = str(_RAW["previous_releases"]["v1.2"]["full_ppf_sha256"])
V12_FULL_PPF_NAME = str(_RAW["previous_releases"]["v1.2"]["full_ppf_name"])

UNPACK_SIZE = int(_RAW["unpack"]["size"])
UNPACK_CHUNK_COUNT = int(_RAW["unpack"]["chunk_count"])
RETAIL_UNPACK_SHA256 = str(_RAW["unpack"]["retail_sha256"])
SECOND_NAME_FIRST = int(_RAW["unpack"]["second_name_first"])
SECOND_NAME_LAST = int(_RAW["unpack"]["second_name_last"])
LOCALIZED_UNPACK_SHA256 = str(_RAW["unpack"]["localized_sha256"])
SECOND_NAME_PAYLOAD_SHA256 = str(_RAW["unpack"]["second_name_payload_sha256"])
SECOND_NAME_TITLE_BAND: tuple[int, int, int, int] = tuple(  # type: ignore[assignment]
    int(value) for value in _RAW["unpack"]["second_name_title_band"]
)
SECOND_NAME_DETECT_ROWS: tuple[int, int] = tuple(  # type: ignore[assignment]
    int(value) for value in _RAW["unpack"]["second_name_detect_rows"]
)


RETAIL_SHA256 = {str(name): str(value) for name, value in _RAW.get("retail_assets", {}).items()}
LOCALIZED_ASSETS = {
    str(name): ComponentVersion(int(row["size"]), str(row["sha256"]))
    for name, row in _RAW.get("localized_assets", {}).items()
}


def _layout(cls, key: str):
    raw = _RAW[key]
    return cls(**{name: int(raw[name]) for name in cls.__dataclass_fields__})


CARD_TEXT_LAYOUT = _layout(CardTextLayout, "card_text")
DECK_TEXT_LAYOUT = _layout(DeckTextLayout, "deck_text")
SHOP_BOOSTER_LAYOUT = _layout(ShopBoosterLayout, "shop_booster_table")
