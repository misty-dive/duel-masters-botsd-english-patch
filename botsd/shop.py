from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from .errors import FormatError, VerificationError
from .manifest import SHOP_BOOSTER_LAYOUT

BOOSTER_TABLE_OFFSET = SHOP_BOOSTER_LAYOUT.table_offset
BOOSTER_RECORD_STRIDE = SHOP_BOOSTER_LAYOUT.record_stride
BOOSTER_CODE_OFFSET = SHOP_BOOSTER_LAYOUT.code_offset
BOOSTER_CODE_SIZE = SHOP_BOOSTER_LAYOUT.code_size
BOOSTER_DESCRIPTION_OFFSET = SHOP_BOOSTER_LAYOUT.description_offset
BOOSTER_DESCRIPTION_SIZE = SHOP_BOOSTER_LAYOUT.description_size
BOOSTER_METADATA_OFFSET = SHOP_BOOSTER_LAYOUT.metadata_offset
BOOSTER_METADATA_SIZE = SHOP_BOOSTER_LAYOUT.metadata_size


@dataclass(frozen=True)
class BoosterDescription:
    code: str
    description: str


def _cstr(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("cp932", errors="strict")


def load_booster_descriptions(path: str | Path) -> tuple[BoosterDescription, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if int(raw.get("schema_version", 0)) != 1:
        raise ValueError("unsupported booster-description schema version")
    rows: list[BoosterDescription] = []
    seen: set[str] = set()
    for entry in raw.get("records", []):
        code = str(entry.get("code", "")).strip()
        description = str(entry.get("description", "")).strip()
        if not code or not description:
            raise ValueError("booster record requires non-empty code and description")
        if code in seen:
            raise ValueError(f"duplicate booster code {code!r}")
        seen.add(code)
        rows.append(BoosterDescription(code, description))
    if not rows:
        raise ValueError("booster description file contains no records")
    return tuple(rows)


def patch_booster_descriptions(
    source: bytes,
    records: Iterable[BoosterDescription],
    *,
    table_offset: int = BOOSTER_TABLE_OFFSET,
) -> bytes:
    """Patch fixed booster-description fields while proving metadata containment."""
    rows = tuple(records)
    out = bytearray(source)
    table_end = table_offset + len(rows) * BOOSTER_RECORD_STRIDE
    if table_offset < 0 or table_end > len(source):
        raise FormatError("booster table lies outside executable")

    for index, row in enumerate(rows):
        record = table_offset + index * BOOSTER_RECORD_STRIDE
        code_slice = source[
            record + BOOSTER_CODE_OFFSET : record + BOOSTER_CODE_OFFSET + BOOSTER_CODE_SIZE
        ]
        got_code = _cstr(code_slice)
        if got_code != row.code:
            raise VerificationError(
                f"booster record {index}: code {got_code!r} != expected {row.code!r}"
            )
        encoded = row.description.encode("cp932", errors="strict")
        if len(encoded) + 1 > BOOSTER_DESCRIPTION_SIZE:
            raise ValueError(
                f"{row.code}: description is {len(encoded)} bytes; max is "
                f"{BOOSTER_DESCRIPTION_SIZE - 1}"
            )
        metadata_start = record + BOOSTER_METADATA_OFFSET
        metadata_before = source[metadata_start : metadata_start + BOOSTER_METADATA_SIZE]
        start = record + BOOSTER_DESCRIPTION_OFFSET
        out[start : start + BOOSTER_DESCRIPTION_SIZE] = encoded + b"\0" * (
            BOOSTER_DESCRIPTION_SIZE - len(encoded)
        )
        if bytes(out[metadata_start : metadata_start + BOOSTER_METADATA_SIZE]) != metadata_before:
            raise VerificationError(f"{row.code}: price/image/index metadata changed")
    if len(out) != len(source):
        raise VerificationError("booster description patch changed executable size")
    return bytes(out)
