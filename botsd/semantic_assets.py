from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from .archive import parse_archive_bytes, replace_member_in_place
from .errors import FormatError, VerificationError
from .indexed_tga import IndexedTGA
from .lzss import compress, compress_optimal
from .localization import load_language_json


def _asset_json(name: str) -> dict[str, Any]:
    text = files("botsd").joinpath("assets").joinpath(name).read_text(encoding="utf-8")
    return json.loads(text)


def _member_raw(archive_bytes: bytes, member_name: str) -> bytes:
    archive = parse_archive_bytes(archive_bytes, decompress=True)
    try:
        member = next(row for row in archive.members if row.name == member_name)
    except StopIteration as exc:
        raise FormatError(f"archive member not found: {member_name}") from exc
    if member.raw is None:
        raise VerificationError(f"{member_name}: archive parser did not decompress member")
    return member.raw


def _compress_for_recipe(raw: bytes, recipe: dict[str, Any]) -> bytes:
    mode = str(recipe["mode"])
    max_candidates = int(recipe["max_candidates"])
    if mode == "fast":
        return compress(raw, max_candidates=max_candidates)
    if mode == "optimal":
        return compress_optimal(raw, max_candidates=max_candidates)
    raise ValueError(f"unknown semantic-asset compression mode: {mode}")


def build_tchange_v13(v12_archive: bytes) -> bytes:
    """Rebuild the published v1.3 CHANGE/TURN asset from semantic layout operations.

    No packed target bytes are stored. The source English glyph pixels are taken from the
    caller's exact v1.2 TGA and rearranged according to the editable layout recipe.
    """
    cfg = _asset_json("tchange_layout_v13.json")
    member_name = str(cfg["member"])
    raw = _member_raw(v12_archive, member_name)
    tga = IndexedTGA(raw)
    if (tga.width, tga.height) != (256, 256):
        raise FormatError(f"{member_name}: expected 256x256 indexed TGA")

    width = tga.width
    source_plane = tga.indices_top_down()
    source_rows = [
        bytearray(source_plane[y * width : (y + 1) * width]) for y in range(tga.height)
    ]
    rows = [row[:] for row in source_rows]
    background = int(cfg["background_index"])

    x0, y0, x1, y1 = (int(v) for v in cfg["clear_rect"])
    if not (0 <= x0 <= x1 <= tga.width and 0 <= y0 <= y1 <= tga.height):
        raise ValueError("TCHANGE clear rectangle is outside the TGA")
    fill = bytes([background]) * (x1 - x0)
    for y in range(y0, y1):
        rows[y][x0:x1] = fill

    # Layer order is meaningful where the two moved outlines touch.
    for layer in cfg["layers"]:
        src_y0, src_y1 = (int(v) for v in layer["source_rows"])
        dx, dy = (int(v) for v in layer["shift"])
        if not layer.get("copy_non_background", False):
            raise ValueError("TCHANGE v1.3 recipe requires copy_non_background=true")

        for sy in range(src_y0, src_y1):
            for sx, value in enumerate(source_rows[sy]):
                if value == background:
                    continue
                tx = sx + dx
                ty = sy + dy
                if not (0 <= tx < tga.width and 0 <= ty < tga.height):
                    raise VerificationError(
                        f"TCHANGE {layer['name']} move exits texture at ({sx},{sy})->({tx},{ty})"
                    )
                rows[ty][tx] = value

        for sy_text, runs in layer.get("boundary_runs", {}).items():
            sy = int(sy_text)
            for lo, hi in runs:
                for sx in range(int(lo), int(hi) + 1):
                    value = source_rows[sy][sx]
                    if value == background:
                        raise VerificationError(
                            f"TCHANGE {layer['name']} boundary run selected background "
                            f"at ({sx},{sy})"
                        )
                    tx = sx + dx
                    ty = sy + dy
                    if not (0 <= tx < tga.width and 0 <= ty < tga.height):
                        raise VerificationError("TCHANGE boundary move exits texture")
                    rows[ty][tx] = value

    tga.replace_top_down(b"".join(rows))
    new_raw = tga.to_bytes()
    if new_raw[: tga.pixel_offset] != raw[: tga.pixel_offset]:
        raise VerificationError("TCHANGE semantic edit changed TGA header/palette")
    pixel_end = tga.pixel_offset + tga.width * tga.height
    if new_raw[pixel_end:] != raw[pixel_end:]:
        raise VerificationError("TCHANGE semantic edit changed TGA trailer")

    compressed = _compress_for_recipe(new_raw, cfg["compression"])
    return replace_member_in_place(
        v12_archive,
        member_name,
        new_raw,
        compressed_stream=compressed,
        expected_stored_size=int(cfg["expected_stored_size"]),
    )


def _load_ace_language(language: str) -> dict[str, Any]:
    raw = load_language_json(language, "ace_badge_v13.json")
    records = raw.get("records")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise ValueError("ACE badge language resource must contain exactly one record")
    record = dict(records[0])
    if not str(record.get("label", "")).strip():
        raise ValueError("ACE badge language record requires a non-empty label")
    return record


def _decode_symbol_template(
    cfg: dict[str, Any],
    language_recipe: dict[str, Any],
) -> tuple[int, int, bytes]:
    symbols = {str(k): int(v) for k, v in cfg["palette_symbols"].items()}
    rows = [str(row) for row in language_recipe["rows"]]
    if not rows:
        raise ValueError("ACE badge template has no rows")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("ACE badge template rows have inconsistent widths")
    values = bytearray()
    for row in rows:
        for symbol in row:
            try:
                value = symbols[symbol]
            except KeyError as exc:
                raise ValueError(f"ACE badge template uses unknown symbol {symbol!r}") from exc
            if not 0 <= value <= 255:
                raise ValueError(f"ACE badge palette index outside byte range: {value}")
            values.append(value)
    return width, len(rows), bytes(values)


def build_deck_ace_v13(
    v12_archive: bytes,
    *,
    language: str = "en",
    language_recipe: dict[str, Any] | None = None,
) -> bytes:
    """Rebuild the v1.3 Deck Builder key-card badge from separated language pixels."""
    cfg = _asset_json("ace_badge_v13.json")
    language_recipe = language_recipe or _load_ace_language(language)
    member_name = str(cfg["member"])
    raw = _member_raw(v12_archive, member_name)
    tga = IndexedTGA(raw)
    if (tga.width, tga.height) != (512, 256):
        raise FormatError(f"{member_name}: expected 512x256 indexed TGA")

    x0, y0, x1, y1 = (int(v) for v in cfg["box"])
    template_width, template_height, template = _decode_symbol_template(cfg, language_recipe)
    if (x1 - x0, y1 - y0) != (template_width, template_height):
        raise ValueError(
            "ACE badge template dimensions do not match configured destination rectangle"
        )

    plane = tga.indices_top_down()
    rows = [
        bytearray(plane[y * tga.width : (y + 1) * tga.width]) for y in range(tga.height)
    ]
    for row_index in range(template_height):
        start = row_index * template_width
        rows[y0 + row_index][x0:x1] = template[start : start + template_width]

    tga.replace_top_down(b"".join(rows))
    new_raw = tga.to_bytes()
    if new_raw[: tga.pixel_offset] != raw[: tga.pixel_offset]:
        raise VerificationError("ACE semantic edit changed TGA header/palette")
    pixel_end = tga.pixel_offset + tga.width * tga.height
    if new_raw[pixel_end:] != raw[pixel_end:]:
        raise VerificationError("ACE semantic edit changed TGA trailer")

    compressed = _compress_for_recipe(new_raw, cfg["compression"])
    return replace_member_in_place(
        v12_archive,
        member_name,
        new_raw,
        compressed_stream=compressed,
        expected_stored_size=int(cfg["expected_stored_size"]),
    )
