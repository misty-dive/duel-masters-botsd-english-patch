from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

ENTRY_COUNT = 453
ALIGNMENT = 0x40
ASCII_WIDTH = 12
ASCII_HEIGHT = 24
ASCII_GLYPH_BYTES = 144


def load_ue_spec(path: str | Path | None = None) -> dict:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets/font_ue.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


_UE_SPEC = load_ue_spec()
UE_INPUT_ASSET = str(_UE_SPEC["input_asset"])
UE_SOURCE_PAGE = str(_UE_SPEC["source_page"])
UE_TARGET_PAGE = str(_UE_SPEC["target_page"])
UE_SOURCE_GLYPH_INDEX = int(_UE_SPEC["source_glyph_index"])
UE_TARGET_GLYPH_INDEX = int(_UE_SPEC["target_glyph_index"])
UE_VERTICAL_SHIFT = int(_UE_SPEC["vertical_shift"])
UE_DIAERESIS_COLUMNS = tuple(int(value) for value in _UE_SPEC["diaeresis_columns"])
UE_DIAERESIS_TOP_VALUE = int(_UE_SPEC["diaeresis_top_value"])
UE_DIAERESIS_SECOND_VALUE = int(_UE_SPEC["diaeresis_second_value"])


@dataclass(frozen=True)
class FontEntry:
    index: int
    directory_offset: int
    name: str
    stored_size: int
    offset: int
    blob: bytes


def decompress(blob: bytes) -> bytes:
    if len(blob) < 6:
        raise ValueError("FONTLINK stream is too short")
    wanted = struct.unpack_from("<I", blob, 0)[0]
    pos = 4
    out = bytearray()
    while True:
        if pos + 2 > len(blob):
            raise ValueError("missing FONTLINK stream terminator")
        token = struct.unpack_from("<H", blob, pos)[0]
        pos += 2
        if token == 0:
            break
        length = token >> 11
        if length:
            distance = token & 0x7FF
            if distance == 0 or distance > len(out):
                raise ValueError(f"bad FONTLINK back-reference {distance}")
            for _ in range(length):
                out.append(out[-distance])
        else:
            length = token & 0x7FF
            if pos + length > len(blob):
                raise ValueError("FONTLINK literal overruns stream")
            out.extend(blob[pos : pos + length])
            pos += length
    if len(out) != wanted or pos != len(blob):
        raise ValueError(
            f"FONTLINK decode mismatch output={len(out)}/{wanted} consumed={pos}/{len(blob)}"
        )
    return bytes(out)


def compress(data: bytes) -> bytes:
    out = bytearray(struct.pack("<I", len(data)))
    literals = bytearray()
    pos = 0

    def flush() -> None:
        while literals:
            chunk = bytes(literals[:0x7FF])
            del literals[: len(chunk)]
            out.extend(struct.pack("<H", len(chunk)))
            out.extend(chunk)

    while pos < len(data):
        best_length = 0
        best_distance = 0
        for distance in range(1, min(0x7FF, pos) + 1):
            length = 0
            while (
                length < 31
                and pos + length < len(data)
                and data[pos + length] == data[pos + length - distance]
            ):
                length += 1
            if length > best_length:
                best_length = length
                best_distance = distance
                if length == 31:
                    break
        if best_length >= 3:
            flush()
            out.extend(struct.pack("<H", (best_length << 11) | best_distance))
            pos += best_length
        else:
            literals.append(data[pos])
            pos += 1
            if len(literals) == 0x7FF:
                flush()
    flush()
    out.extend(b"\0\0")
    result = bytes(out)
    if decompress(result) != data:
        raise RuntimeError("FONTLINK compression round-trip failed")
    return result


def parse_pac(raw: bytes, *, expected_count: int = ENTRY_COUNT, expected_alignment: int = ALIGNMENT) -> list[FontEntry]:
    if raw[:4] != b"DPAC":
        raise ValueError("not a FONTLINK DPAC archive")
    if len(raw) < 12:
        raise ValueError("truncated FONTLINK header")
    count, alignment = struct.unpack_from("<II", raw, 4)
    if count != expected_count or alignment != expected_alignment:
        raise ValueError(
            f"unexpected FONTLINK directory count/alignment {(count, alignment)}"
        )
    entries: list[FontEntry] = []
    pos = 12
    for index in range(count):
        if pos + 24 > len(raw):
            raise ValueError("truncated FONTLINK directory")
        name = raw[pos : pos + 16].split(b"\0", 1)[0].decode("ascii")
        size, offset = struct.unpack_from("<II", raw, pos + 16)
        if offset + size > len(raw):
            raise ValueError(f"FONTLINK member {name} exceeds archive")
        entries.append(FontEntry(index, pos, name, size, offset, raw[offset : offset + size]))
        pos += 24
    return entries


def page_geometry(data: bytes | bytearray) -> tuple[int, int, int, int]:
    if len(data) < 8:
        raise ValueError("font page too short")
    width, height, glyph_bytes, reserved = struct.unpack_from("<HHHH", data, 0)
    if reserved != 0 or glyph_bytes != width * height // 2 or (len(data) - 8) % glyph_bytes:
        raise ValueError("bad font-page geometry")
    return width, height, glyph_bytes, (len(data) - 8) // glyph_bytes


def unpack_4bpp(raw: bytes | bytearray) -> list[int]:
    pixels: list[int] = []
    for value in raw:
        pixels.extend((value >> 4, value & 15))
    return pixels


def pack_4bpp(pixels: list[int]) -> bytes:
    if len(pixels) % 2:
        raise ValueError("4bpp pixel count must be even")
    return bytes(
        ((pixels[index] & 15) << 4) | (pixels[index + 1] & 15)
        for index in range(0, len(pixels), 2)
    )


def make_ue_from_u(
    u_pixels: list[int],
    width: int = ASCII_WIDTH,
    height: int = ASCII_HEIGHT,
    *,
    vertical_shift: int = UE_VERTICAL_SHIFT,
    diaeresis_columns: tuple[int, ...] = UE_DIAERESIS_COLUMNS,
    top_value: int = UE_DIAERESIS_TOP_VALUE,
    second_value: int = UE_DIAERESIS_SECOND_VALUE,
) -> list[int]:
    if len(u_pixels) != width * height:
        raise ValueError("source glyph size mismatch")
    if not 0 <= vertical_shift < height:
        raise ValueError("invalid U-diaeresis vertical shift")
    output = [0] * (width * height)
    for y in range(height - vertical_shift):
        source_start = y * width
        target_start = (y + vertical_shift) * width
        output[target_start : target_start + width] = u_pixels[source_start : source_start + width]
    for x in diaeresis_columns:
        if not 0 <= x < width:
            raise ValueError("U-diaeresis column outside glyph")
        output[x] = top_value
        output[width + x] = second_value
    return output


def replace_member_in_place(raw: bytes, entries: list[FontEntry], name: str, new_blob: bytes) -> bytes:
    by_name = {entry.name: entry for entry in entries}
    if name not in by_name:
        raise ValueError(f"FONTLINK member not found: {name}")
    entry = by_name[name]
    later = [other.offset for other in entries if other.offset > entry.offset]
    allocation_end = min(later) if later else len(raw)
    allocation = allocation_end - entry.offset
    if len(new_blob) > allocation:
        raise ValueError(f"{name}: patched member too large {len(new_blob)}/{allocation}")
    out = bytearray(raw)
    struct.pack_into("<I", out, entry.directory_offset + 16, len(new_blob))
    out[entry.offset:allocation_end] = new_blob + b"\0" * (allocation - len(new_blob))
    return bytes(out)


def patch_reserved_ue(
    raw: bytes,
    *,
    spec_path: str | Path | None = None,
    source_page: str | None = None,
    target_page: str | None = None,
) -> bytes:
    spec = load_ue_spec(spec_path)
    source_page = source_page or str(spec["source_page"])
    target_page = target_page or str(spec["target_page"])
    source_index = int(spec["source_glyph_index"])
    target_index = int(spec["target_glyph_index"])
    source_geometry = tuple(int(value) for value in spec["source_geometry"])
    target_geometry = tuple(int(value) for value in spec["target_geometry"])

    entries = parse_pac(raw)
    by_name = {entry.name: entry for entry in entries}
    if source_page not in by_name or target_page not in by_name:
        raise ValueError("FONTLINK U-diaeresis source/target page is missing")
    source = bytearray(decompress(by_name[source_page].blob))
    target = bytearray(decompress(by_name[target_page].blob))
    if page_geometry(source) != source_geometry or page_geometry(target) != target_geometry:
        raise ValueError("unexpected ASCII font-page geometry")

    width, height, glyph_bytes, source_count = source_geometry
    _, _, target_glyph_bytes, target_count = target_geometry
    if glyph_bytes != target_glyph_bytes or not 0 <= source_index < source_count:
        raise ValueError("invalid U-diaeresis source glyph recipe")
    if not 0 <= target_index < target_count:
        raise ValueError("invalid U-diaeresis target glyph recipe")
    u_pixels = unpack_4bpp(
        source[8 + source_index * glyph_bytes : 8 + (source_index + 1) * glyph_bytes]
    )
    new_glyph = pack_4bpp(
        make_ue_from_u(
            u_pixels,
            width,
            height,
            vertical_shift=int(spec["vertical_shift"]),
            diaeresis_columns=tuple(int(value) for value in spec["diaeresis_columns"]),
            top_value=int(spec["diaeresis_top_value"]),
            second_value=int(spec["diaeresis_second_value"]),
        )
    )
    target[
        8 + target_index * glyph_bytes : 8 + (target_index + 1) * glyph_bytes
    ] = new_glyph
    new_blob = compress(bytes(target))
    output = replace_member_in_place(raw, entries, target_page, new_blob)

    output_entries = parse_pac(output)
    old_by_name = {entry.name: entry for entry in entries}
    for entry in output_entries:
        decompress(entry.blob)
        if entry.name != target_page and entry.blob != old_by_name[entry.name].blob:
            raise RuntimeError(f"unrelated FONTLINK resource changed: {entry.name}")
    return output
