from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import FormatError, VerificationError
from .hashing import sha256_bytes
from .manifest import DECK_TEXT_LAYOUT

CALLOUT_OFFSET = DECK_TEXT_LAYOUT.callout_offset
CALLOUT_SIZE = DECK_TEXT_LAYOUT.callout_size
TITLE_OFFSET = DECK_TEXT_LAYOUT.title_offset
TITLE_SIZE = DECK_TEXT_LAYOUT.title_size
DATA_OFFSET = DECK_TEXT_LAYOUT.data_offset
RECIPE_FORMAT = "BOTSD_DECK_TEXT_EN_V1"


@dataclass(frozen=True)
class DeckTextRecord:
    filename: str
    source_callout: str
    source_title: str
    callout: str
    title: str


@dataclass(frozen=True)
class DeckTextResult:
    filename: str
    source_sha256: str
    target_sha256: str
    size: int


def _read_field(raw: bytes, offset: int, size: int) -> str:
    return raw[offset : offset + size].split(b"\0", 1)[0].decode("cp932", errors="strict")


def _encode_ascii_field(text: str, size: int, label: str) -> bytes:
    try:
        encoded = text.encode("ascii", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label}: English deck text must be ASCII") from exc
    if len(encoded) >= size:
        raise ValueError(f"{label}: {len(encoded)} bytes will not fit {size - 1}-byte field")
    return encoded + b"\0" * (size - len(encoded))


def load_records(path: str | Path) -> tuple[DeckTextRecord, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != RECIPE_FORMAT:
        raise FormatError(f"{path}: unexpected deck-text recipe format")
    records: list[DeckTextRecord] = []
    seen: set[str] = set()
    for index, row in enumerate(data.get("records", []), 1):
        try:
            record = DeckTextRecord(
                filename=str(row["file"]),
                source_callout=str(row["source_callout"]),
                source_title=str(row["source_title"]),
                callout=str(row["callout"]),
                title=str(row["title"]),
            )
        except KeyError as exc:
            raise FormatError(f"{path}: record {index} missing {exc.args[0]!r}") from exc
        if not record.filename.upper().endswith(".DAT"):
            raise FormatError(f"{path}: invalid deck filename {record.filename!r}")
        if record.filename in seen:
            raise FormatError(f"{path}: duplicate deck filename {record.filename}")
        seen.add(record.filename)
        _encode_ascii_field(record.callout, CALLOUT_SIZE, f"{record.filename} callout")
        _encode_ascii_field(record.title, TITLE_SIZE, f"{record.filename} title")
        records.append(record)
    if len(records) != DECK_TEXT_LAYOUT.record_count:
        raise FormatError(
            f"{path}: expected {DECK_TEXT_LAYOUT.record_count} deck-text records, got {len(records)}"
        )
    return tuple(records)


def patch_deck_file(raw: bytes, record: DeckTextRecord) -> bytes:
    if len(raw) < DATA_OFFSET:
        raise FormatError(f"{record.filename}: file is shorter than 0x{DATA_OFFSET:X} bytes")
    got_callout = _read_field(raw, CALLOUT_OFFSET, CALLOUT_SIZE)
    got_title = _read_field(raw, TITLE_OFFSET, TITLE_SIZE)
    if got_callout != record.source_callout or got_title != record.source_title:
        raise VerificationError(
            f"{record.filename}: source text mismatch: "
            f"{(got_callout, got_title)!r} != "
            f"{(record.source_callout, record.source_title)!r}"
        )
    output = bytearray(raw)
    output[CALLOUT_OFFSET:TITLE_OFFSET] = _encode_ascii_field(
        record.callout, CALLOUT_SIZE, f"{record.filename} callout"
    )
    output[TITLE_OFFSET:DATA_OFFSET] = _encode_ascii_field(
        record.title, TITLE_SIZE, f"{record.filename} title"
    )
    target = bytes(output)
    if len(target) != len(raw) or target[:CALLOUT_OFFSET] != raw[:CALLOUT_OFFSET]:
        raise VerificationError(f"{record.filename}: header containment failed")
    if target[DATA_OFFSET:] != raw[DATA_OFFSET:]:
        raise VerificationError(f"{record.filename}: deck/card composition bytes changed")
    if _read_field(target, CALLOUT_OFFSET, CALLOUT_SIZE) != record.callout:
        raise VerificationError(f"{record.filename}: callout verification failed")
    if _read_field(target, TITLE_OFFSET, TITLE_SIZE) != record.title:
        raise VerificationError(f"{record.filename}: title verification failed")
    return target


def patch_directory(
    input_dir: str | Path,
    output_dir: str | Path,
    recipe: str | Path,
) -> tuple[DeckTextResult, ...]:
    source_dir = Path(input_dir)
    target_dir = Path(output_dir)
    records = load_records(recipe)
    by_name = {record.filename: record for record in records}
    files = {path.name: path for path in source_dir.glob("*.DAT")}
    if set(files) != set(by_name):
        missing = sorted(set(by_name) - set(files))
        extra = sorted(set(files) - set(by_name))
        raise VerificationError(f"DECK inventory mismatch missing={missing} extra={extra}")
    target_dir.mkdir(parents=True, exist_ok=True)
    results: list[DeckTextResult] = []
    for name in sorted(by_name):
        source = files[name].read_bytes()
        target = patch_deck_file(source, by_name[name])
        (target_dir / name).write_bytes(target)
        results.append(
            DeckTextResult(
                filename=name,
                source_sha256=sha256_bytes(source),
                target_sha256=sha256_bytes(target),
                size=len(target),
            )
        )
    return tuple(results)
