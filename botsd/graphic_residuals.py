from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .archive import parse_archive_bytes
from .hashing import sha256_bytes
from .indexed_tga import Box, IndexedTGA
from .ui_graphics import patch_indexed_member


@dataclass(frozen=True)
class ResidualBuild:
    data: bytes
    report_lines: tuple[str, ...]


def load_spec(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _box(row: dict[str, Any], key: str) -> Box:
    values = tuple(int(value) for value in row[key])
    if len(values) != 4:
        raise ValueError(f"{key}: expected four coordinates")
    return (values[0], values[1], values[2], values[3])


def _xy(row: dict[str, Any], key: str) -> tuple[int, int]:
    values = tuple(int(value) for value in row[key])
    if len(values) != 2:
        raise ValueError(f"{key}: expected two coordinates")
    return (values[0], values[1])


def _guard(source: bytes, row: dict[str, Any], label: str) -> str:
    got = sha256_bytes(source)
    expected = row.get("input_sha256")
    if expected and got != expected:
        raise ValueError(f"{label} source SHA-256 {got} != expected {expected}")
    return got


def _nearest_alpha_indices(tga: IndexedTGA, rgb: tuple[int, int, int]) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int, int]] = []
    first = tga.info.palette_first
    for slot, (red, green, blue, alpha) in enumerate(tga.palette):
        distance = (red - rgb[0]) ** 2 + (green - rgb[1]) ** 2 + (blue - rgb[2]) ** 2
        candidates.append((distance, first + slot, alpha))
    minimum = min(distance for distance, _, _ in candidates)
    return sorted((alpha, index) for distance, index, alpha in candidates if distance == minimum)


def _index_for_alpha(candidates: list[tuple[int, int]], alpha: int) -> int:
    return min(candidates, key=lambda row: abs(row[0] - alpha))[1]


def build_lobby(source: bytes, spec: dict[str, Any]) -> ResidualBuild:
    input_hash = _guard(source, spec, "LOBBY")
    archive = parse_archive_bytes(source, decompress=True)
    member_name = str(spec["member"])
    member = next(row for row in archive.members if row.name == member_name)
    if member.raw is None:
        raise RuntimeError("LOBBY member was not decompressed")
    tga = IndexedTGA(member.raw)

    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow and NumPy are required for UI82 residual graphics") from exc

    rgba = np.asarray(tga.to_rgba_image())
    sx0, sy0, sx1, sy1 = _box(spec, "source_box")
    source_rgb = rgba[sy0:sy1, sx0:sx1, :3].astype(np.float32)
    luminance = source_rgb.mean(2)
    mask = np.clip((luminance - 75.0) * 2.2, 0, 255).astype(np.uint8)
    mask[mask < 35] = 0
    mask_image = Image.fromarray(mask, "L").resize((60, 15), Image.Resampling.LANCZOS)

    target_box = _box(spec, "target_box")
    plane = tga.indices_top_down()
    clear_index = int(spec["clear_index"])
    x0, y0, x1, y1 = target_box
    for y in range(y0, y1):
        start = y * tga.width + x0
        plane[start : start + (x1 - x0)] = bytes([clear_index]) * (x1 - x0)

    rgb = tuple(int(value) for value in spec["target_rgb"])
    alpha_candidates = _nearest_alpha_indices(tga, rgb)  # type: ignore[arg-type]
    ox, oy = _xy(spec, "paste_xy")
    mask_array = np.asarray(mask_image)
    for yy in range(mask_array.shape[0]):
        for xx in range(mask_array.shape[1]):
            alpha = int(mask_array[yy, xx])
            if alpha:
                plane[(oy + yy) * tga.width + ox + xx] = _index_for_alpha(alpha_candidates, alpha)
    tga.replace_top_down(plane)
    result = patch_indexed_member(source, member_name, tga, [target_box])
    return ResidualBuild(
        result.archive,
        (
            f"input_sha256={input_hash}",
            f"output_sha256={sha256_bytes(result.archive)}",
            f"box={target_box} changed_pixels={result.changed_pixels}",
            f"label={spec['label']} (style reused from accepted label in same member)",
        ),
    )


def build_tour(source: bytes, spec: dict[str, Any]) -> ResidualBuild:
    input_hash = _guard(source, spec, "TOUR")
    archive = parse_archive_bytes(source, decompress=True)
    member_name = str(spec["member"])
    member = next(row for row in archive.members if row.name == member_name)
    if member.raw is None:
        raise RuntimeError("TOUR member was not decompressed")
    tga = IndexedTGA(member.raw)
    source_box = _box(spec, "source_box")
    target_box = _box(spec, "target_box")
    tga.copy_box(source_box, (target_box[0], target_box[1]))
    result = patch_indexed_member(source, member_name, tga, [target_box])
    return ResidualBuild(
        result.archive,
        (
            f"input_sha256={input_hash}",
            f"output_sha256={sha256_bytes(result.archive)}",
            f"source_C_box={source_box} target_box={target_box} changed_pixels={result.changed_pixels}",
            f"label={spec['label']} (exact C glyph reused from same member)",
        ),
    )


def build_deck(source: bytes, spec: dict[str, Any]) -> ResidualBuild:
    input_hash = _guard(source, spec, "DECK")
    archive = parse_archive_bytes(source, decompress=True)
    members = {row.name: row for row in archive.members}
    target_name = str(spec["member"])
    source_name = str(spec["source_member"])
    target_raw = members[target_name].raw
    source_raw = members[source_name].raw
    if target_raw is None or source_raw is None:
        raise RuntimeError("DECK members were not decompressed")
    target = IndexedTGA(target_raw)
    source_tga = IndexedTGA(source_raw)

    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("NumPy is required for UI82 residual graphics") from exc

    source_box = _box(spec, "source_box")
    source_rgb = np.asarray(source_tga.to_rgba_image().convert("RGB"))
    sx0, sy0, sx1, sy1 = source_box
    mask = (source_rgb[sy0:sy1, sx0:sx1].mean(2) > 180).astype(np.uint8)

    top_box = _box(spec, "top_box")
    bottom_box = _box(spec, "bottom_box")
    plane = target.indices_top_down()
    for box, background in (
        (top_box, int(spec["top_background_index"])),
        (bottom_box, int(spec["bottom_background_index"])),
    ):
        x0, y0, x1, y1 = box
        for y in range(y0, y1):
            start = y * target.width + x0
            plane[start : start + (x1 - x0)] = bytes([background]) * (x1 - x0)

    for key_xy, key_fg in (
        ("top_paste_xy", "top_foreground_index"),
        ("bottom_paste_xy", "bottom_foreground_index"),
    ):
        ox, oy = _xy(spec, key_xy)
        foreground = int(spec[key_fg])
        for yy in range(mask.shape[0]):
            for xx in range(mask.shape[1]):
                if mask[yy, xx]:
                    plane[(oy + yy) * target.width + ox + xx] = foreground
    target.replace_top_down(plane)
    result = patch_indexed_member(source, target_name, target, [top_box, bottom_box])
    return ResidualBuild(
        result.archive,
        (
            f"input_sha256={input_hash}",
            f"output_sha256={sha256_bytes(result.archive)}",
            f"boxes={top_box},{bottom_box} changed_pixels={result.changed_pixels}",
            f"semantic={spec['label']} (raster reused from accepted source member {source_name})",
        ),
    )


def build_all(inputs: dict[str, Path], outputs: dict[str, Path], spec_path: Path) -> dict[str, ResidualBuild]:
    spec = load_spec(spec_path)
    results = {
        "lobby": build_lobby(inputs["lobby"].read_bytes(), spec["lobby"]),
        "tour": build_tour(inputs["tour"].read_bytes(), spec["tour"]),
        "deck": build_deck(inputs["deck"].read_bytes(), spec["deck"]),
    }
    for key, result in results.items():
        outputs[key].parent.mkdir(parents=True, exist_ok=True)
        outputs[key].write_bytes(result.data)
    return results
