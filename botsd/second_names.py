from __future__ import annotations

import csv
import hashlib
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .cardfaces import ascii_text
from .errors import VerificationError
from .gamefont import GameFont
from .hashing import sha256_path
from .indexed_tga import IndexedTGA, changed_pixel_count
from .manifest import (
    BASELINE,
    RETAIL_UNPACK_SHA256,
    SECOND_NAME_DETECT_ROWS,
    SECOND_NAME_FIRST,
    SECOND_NAME_LAST,
    SECOND_NAME_PAYLOAD_SHA256,
    SECOND_NAME_TITLE_BAND,
    UNPACK_CHUNK_COUNT,
    UNPACK_SIZE,
)
from .sda import OuterSDA
from .ui_graphics import update_tga_from_rgba
from .unpack import write_second_name_patch

if TYPE_CHECKING:
    from PIL import Image

CARD_COUNT = BASELINE.card_resource_count
SECOND_NAME_CHUNK_SIZE = 18_432
QA_SAMPLES = frozenset({0, 2, 14, 36, 100, 200, 300, 400, 500, 600, 623, 676})


@dataclass(frozen=True)
class SecondNameRow:
    sequence: int
    chunk: int
    english_name: str
    retail_sha256: str
    patched_sha256: str
    size: int
    title_detection: str
    title_colour: str
    source_title_mask_pixels: int
    source_title_mask_bbox: tuple[int, int, int, int]
    changed_pixels: int
    changed_bbox: tuple[int, int, int, int]
    rendered_mask_width: int
    rendered_mask_height: int


@dataclass(frozen=True)
class SecondNameRenderResult:
    retail_sha256: str
    patch_zip_sha256: str
    payload_sha256: str
    chunks: int
    fallback_title_detectors: int
    changed_pixels_total: int
    rows: tuple[SecondNameRow, ...]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_names(path: str | Path) -> list[str]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != CARD_COUNT:
        raise ValueError(f"inventory rows={len(rows)}; expected {CARD_COUNT}")
    names: list[str] = []
    for sequence, row in enumerate(rows):
        if "seq" in row and row["seq"] not in (None, "") and int(row["seq"]) != sequence:
            raise ValueError(f"inventory sequence mismatch at row {sequence}: {row['seq']!r}")
        name = (row.get("english_name") or "").strip()
        if not name:
            raise ValueError(f"inventory row {sequence}: missing english_name")
        names.append(name)
    return names


def _find_title_ramp(tga: IndexedTGA):
    """Recover the retail Japanese title's palette-ramp component.

    This is the exact recovered UI82 strategy: prefer palette ramps whose high-confidence
    members are exclusive to the title band, with a conservative top-dominant fallback for
    the single known shared-ramp case (sequence 623).
    """
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise RuntimeError("NumPy is required for second-name rendering") from exc

    if tga.info.palette_first != 0:
        raise VerificationError("second-name renderer expects a zero-based TGA palette")
    y0, y1 = SECOND_NAME_DETECT_ROWS
    array = np.frombuffer(bytes(tga.indices_top_down()), dtype=np.uint8).reshape(
        tga.height, tga.width
    )
    top = Counter(array[y0:y1].ravel().tolist())
    lower = Counter(array[y1:].ravel().tolist())
    palette = tga.palette
    ids = [index for index, colour in enumerate(palette) if top[index] and colour[3] >= 5]

    parent = {index: index for index in ids}

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for position, left in enumerate(ids):
        rgb_left = palette[left][:3]
        for right in ids[position + 1 :]:
            rgb_right = palette[right][:3]
            if max(abs(rgb_left[channel] - rgb_right[channel]) for channel in range(3)) <= 6:
                union(left, right)

    groups: dict[int, list[int]] = {}
    for index in ids:
        groups.setdefault(find(index), []).append(index)

    candidates: list[tuple[float, list[int], set[int], str]] = []
    for group in groups.values():
        alphas = {palette[index][3] for index in group}
        exclusive = [index for index in group if lower[index] == 0]
        exclusive_pixels = sum(top[index] for index in exclusive)
        lower_pixels = sum(lower[index] for index in group)
        if len(alphas) >= 5 and len(exclusive) >= 4 and exclusive_pixels >= 60:
            score = exclusive_pixels * len(alphas) / (1 + math.sqrt(lower_pixels))
            candidates.append((score, group, set(exclusive), "exclusive"))

    if not candidates:
        for group in groups.values():
            alphas = {palette[index][3] for index in group}
            top_pixels = sum(top[index] for index in group)
            lower_pixels = sum(lower[index] for index in group)
            seeds = {
                index
                for index in group
                if top[index] >= max(5, lower[index] * 4)
            }
            seed_pixels = sum(top[index] for index in seeds)
            if (
                len(alphas) >= 5
                and len(seeds) >= 3
                and seed_pixels >= 60
                and top_pixels >= 100
            ):
                score = seed_pixels * len(alphas) / (1 + math.sqrt(lower_pixels))
                candidates.append((score, group, seeds, "top-dominant-fallback"))

    if not candidates:
        raise VerificationError("unable to identify title palette ramp")

    _, group, seeds, method = max(candidates, key=lambda item: item[0])
    candidate_mask = np.isin(array[y0:y1], list(group))
    seed_mask = np.isin(array[y0:y1], list(seeds))

    seen = np.zeros_like(candidate_mask, dtype=bool)
    stack = [tuple(item) for item in np.argwhere(seed_mask)]
    for y, x in stack:
        seen[y, x] = True
    cursor = 0
    while cursor < len(stack):
        y, x = stack[cursor]
        cursor += 1
        for delta_y in (-1, 0, 1):
            for delta_x in (-1, 0, 1):
                if delta_x == 0 and delta_y == 0:
                    continue
                yy, xx = y + delta_y, x + delta_x
                if (
                    0 <= yy < seen.shape[0]
                    and 0 <= xx < seen.shape[1]
                    and candidate_mask[yy, xx]
                    and not seen[yy, xx]
                ):
                    seen[yy, xx] = True
                    stack.append((yy, xx))

    ys, xs = np.where(seen)
    if len(xs) < 100:
        raise VerificationError(f"title mask implausibly small: {len(xs)}")
    colour_index = max(group, key=lambda index: palette[index][3])
    colour = palette[colour_index][:3]
    bbox = (int(xs.min()), y0 + int(ys.min()), int(xs.max() + 1), y0 + int(ys.max() + 1))
    return seen, colour, method, bbox, len(xs)


def _changed_bbox(before: IndexedTGA, after: IndexedTGA) -> tuple[int, int, int, int]:
    a = before.indices_top_down()
    b = after.indices_top_down()
    points = [
        (offset % before.width, offset // before.width)
        for offset, (left, right) in enumerate(zip(a, b, strict=True))
        if left != right
    ]
    if not points:
        raise VerificationError("second-name render changed no pixels")
    return (
        min(x for x, _ in points),
        min(y for _, y in points),
        max(x for x, _ in points) + 1,
        max(y for _, y in points) + 1,
    )


def _write_qa(before: Image.Image, after: Image.Image, path: Path, chunk: int, name: str) -> None:
    from PIL import Image as PILImage
    from PIL import ImageDraw

    def composite(image: Image.Image):
        background = PILImage.new("RGBA", image.size, "white")
        background.alpha_composite(image)
        return background.convert("RGB").resize((512, 512), PILImage.Resampling.NEAREST)

    canvas = PILImage.new("RGB", (1024, 540), "white")
    canvas.paste(composite(before), (0, 28))
    canvas.paste(composite(after), (512, 28))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), f"chunk {chunk} BEFORE", fill="black")
    draw.text((520, 6), f"chunk {chunk} AFTER: {name}", fill="black")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def _write_report(path: Path, rows: list[SecondNameRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [field for field in SecondNameRow.__dataclass_fields__]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            record = {field: getattr(row, field) for field in fields}
            record["source_title_mask_bbox"] = ",".join(map(str, row.source_title_mask_bbox))
            record["changed_bbox"] = ",".join(map(str, row.changed_bbox))
            writer.writerow(record)


def render_second_names(
    retail_unpack: str | Path,
    inventory: str | Path,
    fontlink: str | Path,
    output_zip: str | Path,
    *,
    qa_dir: str | Path | None = None,
    report_csv: str | Path | None = None,
    verify_retail: bool = True,
    verify_frozen_output: bool = True,
) -> SecondNameRenderResult:
    """Render the frozen English UI82 second-name layer from semantic sources.

    Only chunks 2037..2713 are read and only the measured title band in each 128x128 TGA may
    change. The output is the canonical deterministic patch ZIP consumed by
    :func:`botsd.unpack.apply_second_name_patch`.
    """
    try:
        import numpy as np
        from PIL import Image as PILImage
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise RuntimeError("Pillow and NumPy are required for second-name rendering") from exc

    source = OuterSDA(retail_unpack)
    retail_hash = sha256_path(source.path)
    if verify_retail and (source.size != UNPACK_SIZE or retail_hash != RETAIL_UNPACK_SHA256):
        raise VerificationError(
            f"retail UNPACK preflight failed: size={source.size} sha256={retail_hash}"
        )
    if source.chunk_count != UNPACK_CHUNK_COUNT:
        raise VerificationError(
            f"unexpected UNPACK chunk count {source.chunk_count}; expected {UNPACK_CHUNK_COUNT}"
        )

    names = _load_names(inventory)
    font = GameFont(fontlink)
    qa_root = Path(qa_dir) if qa_dir is not None else None

    rows: list[SecondNameRow] = []
    manifest_rows: list[dict[str, str]] = []
    payloads: list[tuple[int, bytes]] = []
    payload_hasher = hashlib.sha256()
    y0, y1 = SECOND_NAME_DETECT_ROWS

    for sequence, name in enumerate(names):
        index = SECOND_NAME_FIRST + sequence
        raw = source.read_chunk(index)
        if len(raw) != SECOND_NAME_CHUNK_SIZE:
            raise VerificationError(
                f"chunk {index}: size {len(raw)} != {SECOND_NAME_CHUNK_SIZE}"
            )
        before = IndexedTGA(raw)
        if (before.width, before.height, before.info.palette_bits) != (128, 128, 32):
            raise VerificationError(
                f"chunk {index}: unexpected TGA "
                f"{(before.width, before.height, before.info.palette_bits)}"
            )

        title_mask, colour, method, mask_bbox, mask_pixels = _find_title_ramp(before)
        original_image = before.to_rgba_image()
        rgba = np.array(original_image, dtype=np.uint8)
        band = rgba[y0:y1]
        band[title_mask] = [*colour, 0]
        rgba[y0:y1] = band
        image = PILImage.fromarray(rgba, "RGBA")

        rendered_name = ascii_text(name)
        mask = font.text_mask(rendered_name, spacing=1)
        target_height = 10
        width = max(1, round(mask.width * target_height / max(1, mask.height)))
        mask = mask.resize((width, target_height), PILImage.Resampling.LANCZOS)
        if mask.width > 120:
            mask = mask.resize((120, target_height), PILImage.Resampling.LANCZOS)
        x = 4 + (120 - mask.width) // 2
        y = y0 + (y1 - y0 - mask.height) // 2
        layer = PILImage.new("RGBA", mask.size, (*colour, 0))
        layer.putalpha(mask)
        image.alpha_composite(layer, (x, y))

        edited = IndexedTGA(raw)
        update_tga_from_rgba(edited, image, [SECOND_NAME_TITLE_BAND])
        output = edited.to_bytes()
        if len(output) != len(raw):
            raise VerificationError(f"chunk {index}: size changed")
        if raw[: before.pixel_offset] != output[: edited.pixel_offset]:
            raise VerificationError(f"chunk {index}: TGA metadata/palette changed")
        pixel_end_before = before.pixel_offset + before.width * before.height
        pixel_end_after = edited.pixel_offset + edited.width * edited.height
        if raw[pixel_end_before:] != output[pixel_end_after:]:
            raise VerificationError(f"chunk {index}: TGA trailer changed")

        changed = changed_pixel_count(before, edited, [SECOND_NAME_TITLE_BAND])
        if changed == 0:
            raise VerificationError(f"chunk {index}: no changes")
        changed_bbox = _changed_bbox(before, edited)
        patched_hash = _sha(output)
        retail_chunk_hash = _sha(raw)
        payload_hasher.update(output)
        payloads.append((index, output))
        manifest_rows.append(
            {
                "chunk": str(index),
                "retail_sha256": retail_chunk_hash,
                "patched_sha256": patched_hash,
            }
        )
        rows.append(
            SecondNameRow(
                sequence=sequence,
                chunk=index,
                english_name=rendered_name,
                retail_sha256=retail_chunk_hash,
                patched_sha256=patched_hash,
                size=len(output),
                title_detection=method,
                title_colour=f"#{colour[0]:02x}{colour[1]:02x}{colour[2]:02x}",
                source_title_mask_pixels=mask_pixels,
                source_title_mask_bbox=mask_bbox,
                changed_pixels=changed,
                changed_bbox=changed_bbox,
                rendered_mask_width=mask.width,
                rendered_mask_height=mask.height,
            )
        )
        if qa_root is not None and sequence in QA_SAMPLES:
            _write_qa(
                original_image,
                edited.to_rgba_image(),
                qa_root / f"chunk_{index}_before_after.png",
                index,
                rendered_name,
            )

    if len(payloads) != CARD_COUNT or payloads[-1][0] != SECOND_NAME_LAST:
        raise VerificationError("second-name render produced an incomplete chunk sequence")
    payload_hash = payload_hasher.hexdigest()
    if verify_frozen_output and payload_hash != SECOND_NAME_PAYLOAD_SHA256:
        raise VerificationError(
            f"frozen UI82 second-name payload mismatch: {payload_hash} "
            f"!= {SECOND_NAME_PAYLOAD_SHA256}"
        )

    write_second_name_patch(output_zip, manifest_rows, payloads)
    if report_csv is not None:
        _write_report(Path(report_csv), rows)

    return SecondNameRenderResult(
        retail_sha256=retail_hash,
        patch_zip_sha256=sha256_path(output_zip),
        payload_sha256=payload_hash,
        chunks=len(payloads),
        fallback_title_detectors=sum(row.title_detection != "exclusive" for row in rows),
        changed_pixels_total=sum(row.changed_pixels for row in rows),
        rows=tuple(rows),
    )
