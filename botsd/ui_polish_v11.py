from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .archive import parse_archive_bytes
from .errors import HashMismatchError, VerificationError
from .indexed_tga import Box, IndexedTGA
from .ui_graphics import paint_indexed_text, patch_indexed_member


@dataclass(frozen=True)
class UIPolishV11Result:
    opt: bytes
    deck: bytes
    executable: bytes
    report_lines: tuple[str, ...]


def _int(value: int | str) -> int:
    return value if isinstance(value, int) else int(value, 0)


def load_spec(path: str | Path | None = None) -> dict:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets/ui_polish_v11.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


def load_strings(path: str | Path) -> dict[str, str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()):
        raise ValueError("v1.1 UI-polish strings must be a JSON string map")
    return raw


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_archive(
    source: bytes,
    archive_spec: dict,
    strings: dict[str, str],
    font_path: str | Path,
    *,
    verify_hash: bool = True,
) -> tuple[bytes, list[str]]:
    expected = str(archive_spec["source_sha256"])
    got = _sha(source)
    if verify_hash and got != expected:
        raise HashMismatchError(f"v1.1 UI archive SHA-256 {got} != expected {expected}")
    output = source
    lines: list[str] = []
    for member_name, edits in archive_spec["members"].items():
        archive = parse_archive_bytes(output, decompress=True)
        target = next((member for member in archive.members if member.name == member_name), None)
        if target is None or target.raw is None:
            raise VerificationError(f"missing/decompression failure for {member_name}")
        tga = IndexedTGA(target.raw)
        boxes: list[Box] = []
        for edit in edits:
            box_values = tuple(int(v) for v in edit["box"])
            if len(box_values) != 4:
                raise ValueError(f"invalid v1.1 UI box for {member_name}: {box_values!r}")
            box: Box = (
                box_values[0],
                box_values[1],
                box_values[2],
                box_values[3],
            )
            boxes.append(box)
            op = edit["op"]
            if op == "clear":
                tga.fill_box(box, int(edit["index"]))
            elif op == "paint":
                key = str(edit["text"])
                if key not in strings:
                    raise ValueError(f"missing v1.1 UI string {key!r}")
                paint_indexed_text(
                    tga,
                    strings[key],
                    box,
                    font_path,
                    clear_mode=str(edit["mode"]),
                    face_index=int(edit["face"]),
                    outline_index=int(edit["outline"]),
                    background_index=(
                        int(edit["background"]) if "background" in edit else None
                    ),
                )
            else:
                raise ValueError(f"unsupported v1.1 UI edit op {op!r}")
        result = patch_indexed_member(output, member_name, tga, boxes)
        output = result.archive
        lines.append(
            f"{member_name}: changed_pixels={result.changed_pixels} "
            f"stored={result.stored_size}/{result.allocation}"
        )
    if len(output) != len(source):
        raise VerificationError("v1.1 UI archive size changed")
    return output, lines


def patch_executable(
    source: bytes,
    executable_spec: dict,
    strings: dict[str, str],
    *,
    verify_hash: bool = True,
) -> tuple[bytes, list[str]]:
    expected = str(executable_spec["source_sha256"])
    got = _sha(source)
    if verify_hash and got != expected:
        raise HashMismatchError(f"v1.1 executable SHA-256 {got} != expected {expected}")
    output = bytearray(source)
    allowed: list[tuple[int, int]] = []
    lines: list[str] = []

    units = executable_spec["record_units"]
    start, end = _int(units["offset"]), _int(units["end"])
    source_ascii = str(units["source_ascii"]).encode("ascii") + b"\0"
    if source[start : start + len(source_ascii)] != source_ascii:
        raise VerificationError("unexpected v1.1 Records unit source string")
    target = strings["record_units"].encode("ascii") + b"\0"
    if len(target) > end - start:
        raise VerificationError("v1.1 Records unit target does not fit fixed slot")
    output[start:end] = target + b"\0" * (end - start - len(target))
    allowed.append((start, end))
    lines.append(f"record_units@0x{start:X}: {strings['record_units']!r}")

    for row in executable_spec["copy_counts"]:
        offset, slot = _int(row["offset"]), int(row["slot"])
        japanese = str(row["source"]).encode("cp932")
        if source[offset : offset + len(japanese)] != japanese:
            raise VerificationError(f"unexpected deck copy-count source at 0x{offset:X}")
        text = strings[str(row["text"])].encode("ascii")
        if len(text) + 1 > slot:
            raise VerificationError(f"deck copy-count target at 0x{offset:X} does not fit")
        output[offset : offset + slot] = text + b"\0" * (slot - len(text))
        allowed.append((offset, offset + slot))
        lines.append(f"copy_count@0x{offset:X}: {text.decode('ascii')}")

    result = bytes(output)
    diffs = [i for i, (a, b) in enumerate(zip(source, result, strict=True)) if a != b]
    bad = [i for i in diffs if not any(start <= i < end for start, end in allowed)]
    if bad:
        raise VerificationError(f"v1.1 executable changed outside declared slots: {bad[:16]}")
    lines.append(f"executable_differing_bytes={len(diffs)}")
    return result, lines


def build_all(
    opt_source: bytes,
    deck_source: bytes,
    executable_source: bytes,
    font_path: str | Path,
    strings_path: str | Path,
    *,
    spec_path: str | Path | None = None,
) -> UIPolishV11Result:
    spec = load_spec(spec_path)
    strings = load_strings(strings_path)
    opt, opt_lines = patch_archive(opt_source, spec["archives"]["opt"], strings, font_path)
    deck, deck_lines = patch_archive(deck_source, spec["archives"]["deck"], strings, font_path)
    executable, exe_lines = patch_executable(executable_source, spec["executable"], strings)
    report = [
        "V1.1 UI POLISH SHARED BUILD: PASS",
        f"opt_sha256={_sha(opt)}",
        f"deck_sha256={_sha(deck)}",
        f"executable_sha256={_sha(executable)}",
        *[f"OPT {line}" for line in opt_lines],
        *[f"DECK {line}" for line in deck_lines],
        *[f"EXE {line}" for line in exe_lines],
        "archive_sizes=UNCHANGED",
        "pixel_and_executable_containment=PASS",
        "RESULT=PASS",
    ]
    return UIPolishV11Result(opt, deck, executable, tuple(report))
