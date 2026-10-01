from __future__ import annotations

from pathlib import Path

import pytest

from botsd.decktext import (
    CALLOUT_OFFSET,
    CALLOUT_SIZE,
    DATA_OFFSET,
    TITLE_OFFSET,
    TITLE_SIZE,
    DeckTextRecord,
    load_records,
    patch_deck_file,
    patch_directory,
)
from botsd.errors import VerificationError


def _retail_record(record: DeckTextRecord, tail: bytes = b"composition") -> bytes:
    raw = bytearray(b"\xA5" * DATA_OFFSET + tail)
    raw[CALLOUT_OFFSET:TITLE_OFFSET] = record.source_callout.encode("cp932") + b"\0" * (
        CALLOUT_SIZE - len(record.source_callout.encode("cp932"))
    )
    raw[TITLE_OFFSET:DATA_OFFSET] = record.source_title.encode("cp932") + b"\0" * (
        TITLE_SIZE - len(record.source_title.encode("cp932"))
    )
    return bytes(raw)


def test_english_recipe_is_explicit_and_complete() -> None:
    records = load_records(Path("localization/en/deck_text.json"))
    assert len(records) == 60
    assert len({record.filename for record in records}) == 60
    assert records[0].filename == "00_1.DAT"
    assert records[0].callout == "This will clear the way!"
    assert records[-1].filename == "28_2.DAT"


def test_deck_text_patch_preserves_composition() -> None:
    record = load_records(Path("localization/en/deck_text.json"))[0]
    source = _retail_record(record, b"\x01\x02\x03deckdata")
    target = patch_deck_file(source, record)
    assert target[:CALLOUT_OFFSET] == source[:CALLOUT_OFFSET]
    assert target[DATA_OFFSET:] == source[DATA_OFFSET:]
    assert target[CALLOUT_OFFSET:TITLE_OFFSET].split(b"\0", 1)[0] == record.callout.encode()
    assert target[TITLE_OFFSET:DATA_OFFSET].split(b"\0", 1)[0] == record.title.encode()


def test_deck_text_source_guard() -> None:
    record = load_records(Path("localization/en/deck_text.json"))[0]
    source = bytearray(_retail_record(record))
    source[CALLOUT_OFFSET] ^= 1
    with pytest.raises(VerificationError, match="source text mismatch"):
        patch_deck_file(bytes(source), record)


def test_patch_directory_requires_exact_inventory(tmp_path: Path) -> None:
    recipe = Path("localization/en/deck_text.json")
    records = load_records(recipe)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for record in records:
        (input_dir / record.filename).write_bytes(_retail_record(record))
    rows = patch_directory(input_dir, tmp_path / "output", recipe)
    assert len(rows) == len(records)
    (input_dir / "EXTRA.DAT").write_bytes(b"x" * DATA_OFFSET)
    with pytest.raises(VerificationError, match="inventory mismatch"):
        patch_directory(input_dir, tmp_path / "output2", recipe)
