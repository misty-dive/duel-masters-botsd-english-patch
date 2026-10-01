from __future__ import annotations

import csv
import os
import struct
from pathlib import Path

import pytest

from botsd.scrpack import parse_chunk_commands
from botsd.storytext import build_story_catalog, write_story_catalog


def _cmd(opcode: int, payload: bytes) -> bytes:
    return struct.pack("<HH", opcode, len(payload)) + payload


def _dialogue(text: str, payload_size: int) -> bytes:
    raw = text.encode("cp932")
    prefix = b"\0" * 6 + struct.pack("<H", len(raw))
    if len(prefix) + len(raw) > payload_size:
        raise ValueError("test dialogue does not fit")
    return _cmd(0x1D03, prefix + raw + b"\0" * (payload_size - len(prefix) - len(raw)))


def _outer(chunks: list[bytes]) -> bytes:
    count = len(chunks)
    cursor = 12 + count * 4
    offsets: list[int] = []
    body = bytearray()
    for chunk in chunks:
        offsets.append(cursor + len(body))
        body.extend(chunk)
    total = cursor + len(body)
    return b"sda\0" + struct.pack("<II", total, count) + struct.pack(
        f"<{count}I", *offsets
    ) + bytes(body)


def test_story_catalog_uses_chunk_and_command_ordinal_as_stable_identity(tmp_path: Path) -> None:
    retail = _outer([b"".join([
        _cmd(0x0001, b"AB"),
        _dialogue("テスト", 24),
        _cmd(0x0002, b"CD"),
        _dialogue("同じ", 20),
    ])])
    translated = _outer([b"".join([
        _cmd(0x0001, b"AB"),
        _dialogue("A longer test", 32),
        _cmd(0x0002, b"CD"),
        _dialogue("同じ", 20),
    ])])
    rows, report = build_story_catalog(retail, translated)
    assert [row.resource_id for row in rows] == ["scrpack.000.0001", "scrpack.000.0003"]
    assert rows[0].source_text == "テスト"
    assert rows[0].translation == "A longer test"
    assert rows[0].source_file_offset != rows[0].translation_file_offset or rows[0].translation_payload_size != rows[0].source_payload_size
    assert rows[0].changed is True
    assert rows[1].changed is False
    assert report.rows == 2
    assert report.translated_rows == 1
    assert report.identical_rows == 1

    out = tmp_path / "story.csv"
    assert write_story_catalog(out, rows) == 2
    with out.open(encoding="utf-8-sig", newline="") as stream:
        saved = list(csv.DictReader(stream))
    assert saved[0]["resource_id"] == "scrpack.000.0001"
    assert saved[0]["source_text"] == "テスト"
    assert saved[0]["translation"] == "A longer test"


def test_real_retail_v12_story_catalog_when_components_are_available() -> None:
    retail_dir = os.environ.get("BOTSD_RETAIL_COMPONENT_DIR")
    v12_dir = os.environ.get("BOTSD_V12_COMPONENT_DIR")
    if not retail_dir or not v12_dir:
        pytest.skip("real retail/v1.2 component directories not supplied")
    retail = (Path(retail_dir) / "SCRPACK.SDA").read_bytes()
    translated = (Path(v12_dir) / "SCRPACK.SDA").read_bytes()
    rows, report = build_story_catalog(retail, translated)
    assert report.rows == 9581
    assert report.chunks == 208
    assert report.translated_rows == 9499
    assert report.identical_rows == 82
    assert len({row.resource_id for row in rows}) == 9581
    known = [
        row
        for row in rows
        if row.translation == "If the World's Balance tips too far toward release..."
    ]
    assert len(known) == 1
    assert known[0].resource_id == "scrpack.123.0646"


def _choice(options: list[str], payload_size: int) -> bytes:
    payload = bytearray(b"\x00\x00\x02\x00\x00\x00")
    payload += struct.pack("<H", len(options))
    for option in options:
        raw = option.encode("cp932")
        payload += struct.pack("<H", len(raw)) + raw
    if len(payload) > payload_size:
        raise ValueError("test choices do not fit")
    payload += b"\0" * (payload_size - len(payload))
    return _cmd(0x1F03, bytes(payload))


def test_story_language_builder_handles_balanced_dialogue_and_choice_resizing() -> None:
    from botsd.storytext import (
        StoryChoiceTranslation,
        StoryDialogueTranslation,
        apply_story_language,
        audit_story_language,
    )

    source = _outer([
        b"".join([
            _cmd(0x0001, b"AB"),
            _dialogue("JP", 24),
            _choice(["A", "B"], 20),
            _cmd(0x0000, b""),
        ])
    ])
    dialogue = (
        StoryDialogueTranslation(
            "scrpack.000.0001", 0, 1, 28, "A longer test", 0
        ),
    )
    choices = (
        StoryChoiceTranslation("scrpack.000.0002", 0, 2, 16, ("Y", "N")),
    )
    target = apply_story_language(source, dialogue, choices)
    assert len(target) == len(source)
    commands = parse_chunk_commands(target, 0)
    assert [row.opcode for row in commands] == [0x0001, 0x1D03, 0x1F03, 0x0000]
    rows, report = build_story_catalog(source, target)
    assert report.rows == 1
    assert rows[0].translation == "A longer test"
    audit = audit_story_language(target, dialogue, choices)
    assert audit.dialogue_rows == 1
    assert audit.choice_rows == 1
    assert audit.dialogue_commands == 1
    assert audit.choice_commands == 1



def test_story_language_builder_consumes_padding_relocates_targets_and_preserves_v12_stale_branch() -> None:
    from botsd.storytext import StoryDialogueTranslation, apply_story_language

    # Meaningful retail command offsets are 0, 8, 28, 48, 56, 72.  Growing the dialogue by
    # eight bytes moves later commands while consuming two trailing four-byte zero commands.
    source_target = 72
    counted_targets = (
        b"\x24\x77\x04\x00\x00\x00"
        + struct.pack("<H", 2)
        + struct.pack("<II", source_target, 0)
    )
    stale_probability = struct.pack("<HI I H", 0, 10, source_target, 0)
    chunk = b"".join(
        [
            _cmd(0x0001, b"ABCD"),
            _dialogue("JP", 16),
            _cmd(0x1412, counted_targets),
            _cmd(0x020C, struct.pack("<I", source_target)),
            _cmd(0x070C, stale_probability),
            _cmd(0x0002, b"WXYZ"),
            *[_cmd(0x0000, b"") for _ in range(4)],
        ]
    )
    source = _outer([chunk])
    dialogue = (
        StoryDialogueTranslation("scrpack.000.0001", 0, 1, 24, "A longer test", 0),
    )
    target = apply_story_language(source, dialogue, ())
    assert len(target) == len(source)

    commands = parse_chunk_commands(target, 0)
    meaningful = list(commands)
    while meaningful and meaningful[-1].opcode == 0 and meaningful[-1].payload_size == 0:
        meaningful.pop()
    assert [row.opcode for row in meaningful] == [0x0001, 0x1D03, 0x1412, 0x020C, 0x070C, 0x0002]
    assert len(commands) - len(meaningful) == 2

    new_target = meaningful[5].chunk_relative_offset
    counted = meaningful[2]
    assert struct.unpack_from("<I", target, counted.file_offset + 12)[0] == new_target
    assert struct.unpack_from("<I", target, counted.file_offset + 16)[0] == 0
    jump = meaningful[3]
    assert struct.unpack_from("<I", target, jump.file_offset + 4)[0] == new_target

    # Public v1.2 historically failed to relocate the 0x070C probability branches.  The v1.2
    # compiler must preserve that stale retail target exactly; v1.3 repairs the three real cases.
    probability = meaningful[4]
    assert struct.unpack_from("<I", target, probability.file_offset + 10)[0] == source_target


def test_story_v12_spec_records_proven_historical_relocation_recipe() -> None:
    import json

    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / "botsd/assets/story_v12.json").read_text(encoding="utf-8"))
    assert spec["retail_scrpack_sha256"] == (
        "707e53a0f714dea7f3a059d973085fafd4f9120d0ef59e92bac42eb561514b11"
    )
    assert spec["v12_scrpack_sha256"] == (
        "1e3208976bb90749598e1d7359cfda51fe7c095cf3db10459265aeb5dd133051"
    )
    assert [row["opcode"] for row in spec["historical_relocation_rules"]] == [
        "0x010C",
        "0x020C",
        "0x1212",
        "0x1312",
        "0x1412",
    ]
    assert spec["historical_unrelocated_probability_opcode"] == "0x070C"
    assert spec["verified_relocation_field_updates"] == 2799


def test_repository_story_language_datasets_are_translation_only_and_complete() -> None:
    from botsd.storytext import (
        load_story_choice_translations,
        load_story_dialogue_translations,
    )

    root = Path(__file__).resolve().parents[1]
    dialogue_path = root / "localization/en/story_dialogue_v12.csv"
    choices_path = root / "localization/en/story_choices_v12.csv"
    dialogue = load_story_dialogue_translations(dialogue_path)
    choices = load_story_choice_translations(choices_path)
    assert len(dialogue) == 9499
    assert len(choices) == 293
    assert len({row.resource_id for row in dialogue}) == 9499
    assert len({row.resource_id for row in choices}) == 293
    header = dialogue_path.read_text(encoding="utf-8").splitlines()[0]
    assert "source_text" not in header
    assert "translation_file_offset" not in header
    assert "source_file_offset" not in header


def test_optional_exact_retail_to_v12_story_language_build() -> None:
    from botsd.hashing import sha256_bytes
    from botsd.manifest import BASELINE
    from botsd.storytext import (
        apply_story_language,
        load_story_choice_translations,
        load_story_dialogue_translations,
    )

    retail_dir = os.environ.get("BOTSD_RETAIL_COMPONENT_DIR")
    if not retail_dir:
        pytest.skip("set BOTSD_RETAIL_COMPONENT_DIR for exact retail->v1.2 SCRPACK regression")
    root = Path(__file__).resolve().parents[1]
    source = (Path(retail_dir) / "SCRPACK.SDA").read_bytes()
    dialogue = load_story_dialogue_translations(root / "localization/en/story_dialogue_v12.csv")
    choices = load_story_choice_translations(root / "localization/en/story_choices_v12.csv")
    target = apply_story_language(source, dialogue, choices)
    expected = BASELINE.component("SCRPACK.SDA").v12
    assert len(target) == expected.size
    assert sha256_bytes(target) == expected.sha256



def test_optional_exact_retail_to_v13_story_chain() -> None:
    import json

    from botsd.hashing import sha256_bytes
    from botsd.manifest import BASELINE
    from botsd.scrpack import build_v13_scrpack
    from botsd.storytext import (
        apply_story_language,
        load_story_choice_translations,
        load_story_dialogue_translations,
    )

    retail_dir = os.environ.get("BOTSD_RETAIL_COMPONENT_DIR")
    if not retail_dir:
        pytest.skip("set BOTSD_RETAIL_COMPONENT_DIR for exact retail->v1.3 SCRPACK regression")
    root = Path(__file__).resolve().parents[1]
    source = (Path(retail_dir) / "SCRPACK.SDA").read_bytes()
    dialogue = load_story_dialogue_translations(root / "localization/en/story_dialogue_v12.csv")
    choices = load_story_choice_translations(root / "localization/en/story_choices_v12.csv")
    v12 = apply_story_language(source, dialogue, choices)
    strings = json.loads((root / "localization/en/v13_maintenance.json").read_text(encoding="utf-8"))
    target = build_v13_scrpack(v12, strings).data
    expected = BASELINE.component("SCRPACK.SDA").v13
    assert len(target) == expected.size
    assert sha256_bytes(target) == expected.sha256


def test_optional_exact_v12_story_language_dataset_audit() -> None:
    from botsd.storytext import (
        audit_story_language,
        load_story_choice_translations,
        load_story_dialogue_translations,
    )

    v12_dir = os.environ.get("BOTSD_V12_COMPONENT_DIR")
    if not v12_dir:
        pytest.skip("set BOTSD_V12_COMPONENT_DIR for exact v1.2 story-language audit")
    root = Path(__file__).resolve().parents[1]
    target = (Path(v12_dir) / "SCRPACK.SDA").read_bytes()
    dialogue = load_story_dialogue_translations(root / "localization/en/story_dialogue_v12.csv")
    choices = load_story_choice_translations(root / "localization/en/story_choices_v12.csv")
    report = audit_story_language(target, dialogue, choices)
    assert report.dialogue_rows == 9499
    assert report.dialogue_commands == 9581
    assert report.choice_rows == 293
    assert report.choice_commands == 293
    assert report.chunks == 208
