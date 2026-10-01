from __future__ import annotations

import csv
import json
import shutil
import struct
import unicodedata
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from .archive import member_allocation, parse_archive_bytes, replace_member_in_place
from .errors import FormatError, HashMismatchError, VerificationError
from .gamefont import GameFont
from .hashing import sha256_path
from .indexed_tga import Box, IndexedTGA, changed_pixel_count
from .lzss import compress as compress_greedy
from .lzss import compress_optimal
from .sda import OuterSDA
from .ui_graphics import update_tga_from_rgba
from .unpack import RETAIL_UNPACK_SHA256, UNPACK_SIZE


@dataclass(frozen=True)
class CardFaceSpec:
    card_count: int
    large_chunk_first: int
    small_chunk_first: int
    large_size: tuple[int, int]
    small_size: tuple[int, int]
    printed_face_crop: Box
    title_box: Box
    type_box: Box
    panel_box: Box
    small_boxes: tuple[Box, ...]
    title_max_scale: float
    type_max_scale: float
    rules_max_scale: float
    rules_split_max_scale: float
    rules_min_scale: float
    flavor_max_scale: float
    flavor_min_scale: float
    rules_flavor_split_y: int
    flavor_start_y: int


@dataclass(frozen=True)
class CardFaceMetrics:
    title_scale: float
    type_scale: float
    rules_scale: float
    rules_lines: int
    flavor_scale: float
    flavor_lines: int
    large_changed_pixels: int
    small_changed_pixels: int
    compression: str
    compressed_headroom: int


@dataclass(frozen=True)
class CardFaceBuildRow:
    sequence: int
    resource_key: str
    internal_id: int
    english_name: str
    large_chunk: int
    small_chunk: int
    metrics: CardFaceMetrics


class TextMaskFont(Protocol):
    def text_mask(self, text: str, spacing: int = 1): ...


def _box(value) -> Box:
    return tuple(int(x) for x in value)  # type: ignore[return-value]


def load_spec(path: str | Path | None = None) -> CardFaceSpec:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets/cardfaces_ui75.json").read_text(encoding="utf-8")
    )
    raw = json.loads(text)
    render = raw["render"]
    boxes = raw["large_boxes"]
    return CardFaceSpec(
        card_count=int(raw["card_count"]),
        large_chunk_first=int(raw["large_chunk_first"]),
        small_chunk_first=int(raw["small_chunk_first"]),
        large_size=(int(raw["large_texture"]["width"]), int(raw["large_texture"]["height"])),
        small_size=(int(raw["small_texture"]["width"]), int(raw["small_texture"]["height"])),
        printed_face_crop=_box(raw["printed_face_crop"]),
        title_box=_box(boxes["title"]),
        type_box=_box(boxes["type"]),
        panel_box=_box(boxes["panel"]),
        small_boxes=tuple(_box(value) for value in raw["small_boxes"]),
        title_max_scale=float(render["title_max_scale"]),
        type_max_scale=float(render["type_max_scale"]),
        rules_max_scale=float(render["rules_max_scale"]),
        rules_split_max_scale=float(render["rules_split_max_scale"]),
        rules_min_scale=float(render["rules_min_scale"]),
        flavor_max_scale=float(render["flavor_max_scale"]),
        flavor_min_scale=float(render["flavor_min_scale"]),
        rules_flavor_split_y=int(render["rules_flavor_split_y"]),
        flavor_start_y=int(render["flavor_start_y"]),
    )


def ascii_text(text: str) -> str:
    text = text.replace("■", "*").replace("Ü", "U")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.split())


def _read_inventory(path: str | Path, spec: CardFaceSpec) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = [{key: value or "" for key, value in row.items()} for row in csv.DictReader(handle)]
    if len(rows) != spec.card_count:
        raise ValueError(f"inventory rows={len(rows)}; expected {spec.card_count}")
    for sequence, row in enumerate(rows):
        large = int(row["large_chunk"])
        small = int(row["small_chunk"])
        if large != spec.large_chunk_first + sequence or small != spec.small_chunk_first + sequence:
            raise VerificationError(
                f"card {sequence}: unexpected chunk mapping large={large} small={small}"
            )
    return rows


def apply_master_overrides(rows: list[dict[str, str]], master_csv: str | Path | None) -> None:
    if master_csv is None:
        return
    import re

    by_id: dict[int, dict[str, str]] = {}
    with Path(master_csv).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            role = (row.get("roles") or "").strip()
            match = re.match(r"^(\d+):", row.get("cards", ""))
            if role in {"name", "rules", "race", "flavor"} and match:
                by_id.setdefault(int(match.group(1)), {})[role] = row.get("translation", "") or ""
    missing = []
    for row in rows:
        card_id = int(row["internal_id"])
        values = by_id.get(card_id, {})
        if values.get("name"):
            row["english_name"] = values["name"]
        for key in ("rules", "race", "flavor"):
            if key in values:
                row[key] = values[key]
        if not row.get("english_name") or (row.get("card_type") != "SPELL" and not row.get("race")):
            missing.append((card_id, row.get("resource_key", "")))
    if missing:
        raise VerificationError(f"master override left required card text missing: {missing[:10]}")


def _low_frequency(image, box: Box, small: tuple[int, int]):
    from PIL import Image

    crop = image.crop(box)
    width = min(small[0], crop.width)
    height = min(small[1], crop.height)
    return crop.resize((width, height), Image.Resampling.BOX).resize(
        crop.size, Image.Resampling.BILINEAR
    )


class CardFaceRenderer:
    def __init__(self, font: TextMaskFont, spec: CardFaceSpec):
        self.font = font
        self.spec = spec

    def width(self, text: str) -> int:
        return self.font.text_mask(text, spacing=1).width

    def wrap(self, paragraph: str, max_width: int) -> list[str]:
        words = paragraph.split()
        output: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if current and self.width(candidate) > max_width:
                output.append(current)
                current = word
            else:
                current = candidate
        if current:
            output.append(current)
        return output

    def layout(self, text: str, box: Box, max_scale: float, min_scale: float):
        paragraphs = []
        for paragraph in text.replace("\r", "").split("\n"):
            paragraph = ascii_text(paragraph)
            if paragraph:
                paragraphs.append(paragraph)
        if not paragraphs:
            return [], 1.0, 0
        width = box[2] - box[0] - 4
        height = box[3] - box[1] - 4
        scale = max_scale
        while scale >= min_scale - 1e-9:
            lines: list[str] = []
            max_base_width = max(1, int(width / scale))
            for index, paragraph in enumerate(paragraphs):
                lines.extend(self.wrap(paragraph, max_base_width))
                if index + 1 < len(paragraphs):
                    lines.append("")
            line_height = max(4, round(24 * scale))
            if len(lines) * line_height <= height:
                return lines, scale, line_height
            scale -= 0.01
        raise VerificationError(f"text does not fit card box {box}: {text[:80]!r}")

    def draw_one(self, image, box: Box, text: str, max_scale: float, *, bold: bool = False):
        from PIL import Image, ImageFilter

        text = ascii_text(text)
        mask = self.font.text_mask(text, spacing=1)
        width = box[2] - box[0] - 4
        height = box[3] - box[1] - 4
        scale = min(max_scale, width / max(1, mask.width), height / max(1, mask.height))
        mask = mask.resize(
            (max(1, round(mask.width * scale)), max(1, round(mask.height * scale))),
            Image.Resampling.LANCZOS,
        )
        x = box[0] + (box[2] - box[0] - mask.width) // 2
        y = box[1] + (box[3] - box[1] - mask.height) // 2
        if bold:
            mask = mask.filter(ImageFilter.MaxFilter(3))
        layer = Image.new("RGBA", mask.size, (8, 8, 8, 0))
        layer.putalpha(mask)
        image.alpha_composite(layer, (x, y))
        return scale

    def draw_wrapped(self, image, box: Box, text: str, max_scale: float, min_scale: float):
        from PIL import Image

        lines, scale, line_height = self.layout(text, box, max_scale, min_scale)
        y = box[1] + 2
        for line in lines:
            if line:
                mask = self.font.text_mask(line, spacing=1)
                mask = mask.resize(
                    (max(1, round(mask.width * scale)), max(1, round(mask.height * scale))),
                    Image.Resampling.LANCZOS,
                )
                layer = Image.new("RGBA", mask.size, (8, 8, 8, 0))
                layer.putalpha(mask)
                image.alpha_composite(layer, (box[0] + 2, y))
            y += line_height
        return scale, len(lines)

    def edit_large(self, raw: bytes, row: dict[str, str]):
        tga = IndexedTGA(raw)
        if (tga.width, tga.height) != self.spec.large_size:
            raise FormatError(f"unexpected large card geometry {(tga.width, tga.height)}")
        original = tga.to_rgba_image()
        image = original.copy()
        image.paste(_low_frequency(original, self.spec.title_box, (18, 3)), self.spec.title_box)
        image.paste(_low_frequency(original, self.spec.type_box, (18, 2)), self.spec.type_box)
        image.paste(_low_frequency(original, self.spec.panel_box, (18, 7)), self.spec.panel_box)

        title_scale = self.draw_one(
            image, self.spec.title_box, row["english_name"], self.spec.title_max_scale, bold=True
        )
        card_type = row["card_type"]
        type_label = card_type if card_type == "SPELL" else card_type + " / " + row["race"]
        type_scale = self.draw_one(
            image, self.spec.type_box, type_label, self.spec.type_max_scale
        )
        rules = (row.get("rules") or "").replace("■", "\n*")
        flavor = row.get("flavor") or ""
        if flavor:
            rule_box = (
                self.spec.panel_box[0],
                self.spec.panel_box[1],
                self.spec.panel_box[2],
                self.spec.rules_flavor_split_y,
            )
            flavor_box = (
                self.spec.panel_box[0],
                self.spec.flavor_start_y,
                self.spec.panel_box[2],
                self.spec.panel_box[3],
            )
            rules_scale, rules_lines = self.draw_wrapped(
                image,
                rule_box,
                rules,
                self.spec.rules_split_max_scale,
                self.spec.rules_min_scale,
            )
            flavor_scale, flavor_lines = self.draw_wrapped(
                image,
                flavor_box,
                flavor,
                self.spec.flavor_max_scale,
                self.spec.flavor_min_scale,
            )
        else:
            rules_scale, rules_lines = self.draw_wrapped(
                image,
                self.spec.panel_box,
                rules,
                self.spec.rules_max_scale,
                self.spec.rules_min_scale,
            )
            flavor_scale, flavor_lines = 1.0, 0

        before = IndexedTGA(raw)
        update_tga_from_rgba(
            tga,
            image,
            (self.spec.title_box, self.spec.type_box, self.spec.panel_box),
        )
        after = IndexedTGA(tga.to_bytes())
        changed = changed_pixel_count(
            before, after, (self.spec.title_box, self.spec.type_box, self.spec.panel_box)
        )
        final_image = after.to_rgba_image()
        return (
            after.to_bytes(),
            final_image,
            title_scale,
            type_scale,
            rules_scale,
            rules_lines,
            flavor_scale,
            flavor_lines,
            changed,
        )


def patch_small(raw: bytes, translated_large, spec: CardFaceSpec) -> tuple[bytes, int]:
    from PIL import Image

    tga = IndexedTGA(raw)
    if (tga.width, tga.height) != spec.small_size:
        raise FormatError(f"unexpected small card geometry {(tga.width, tga.height)}")
    target = translated_large.crop(spec.printed_face_crop).resize(
        spec.small_size, Image.Resampling.BICUBIC
    )
    before = IndexedTGA(raw)
    update_tga_from_rgba(tga, target, spec.small_boxes)
    after = IndexedTGA(tga.to_bytes())
    return after.to_bytes(), changed_pixel_count(before, after, spec.small_boxes)


def _patch_large_chunk(chunk: bytes, edited_tga: bytes) -> tuple[bytes, str, int]:
    if len(chunk) < 8:
        raise FormatError("large card chunk is too short")
    inner_size = struct.unpack_from("<I", chunk, 0)[0]
    if not 0 < inner_size <= len(chunk):
        raise FormatError(f"invalid inner archive size {inner_size}")
    inner = chunk[:inner_size]
    archive = parse_archive_bytes(inner, label="UNPACK::<card>", decompress=False)
    if len(archive.members) != 1:
        raise VerificationError(f"expected one-member card archive, got {len(archive.members)}")
    member = archive.members[0]
    if member.compression != 1:
        raise VerificationError(f"expected compressed card member, got {member.compression}")
    allocation = member_allocation(archive, member)
    greedy = compress_greedy(edited_tga)
    method = "greedy"
    compressed = greedy
    if 4 + len(compressed) > allocation:
        compressed = compress_optimal(edited_tga)
        method = "optimal"
    if 4 + len(compressed) > allocation:
        raise VerificationError(
            f"card member cannot fit fixed allocation: {4 + len(compressed)} > {allocation}"
        )
    rebuilt_inner = replace_member_in_place(
        inner,
        member.name,
        edited_tga,
        compressed_stream=compressed,
    )
    if len(rebuilt_inner) != inner_size:
        raise VerificationError("inner card archive size changed")
    rebuilt = rebuilt_inner + chunk[inner_size:]
    if rebuilt[inner_size:] != chunk[inner_size:]:
        raise VerificationError("outer card-chunk slack changed")
    return rebuilt, method, allocation - (4 + len(compressed))


def build_card_faces(
    unpack: str | Path,
    inventory: str | Path,
    fontlink: str | Path,
    output: str | Path,
    *,
    master_csv: str | Path | None = None,
    spec: CardFaceSpec | None = None,
    start: int = 0,
    end: int | None = None,
    verify_retail: bool = True,
) -> list[CardFaceBuildRow]:
    spec = spec or load_spec()
    source = OuterSDA(unpack)
    source_hash = sha256_path(source.path) if verify_retail else ""
    if verify_retail:
        if source.size != UNPACK_SIZE or source_hash != RETAIL_UNPACK_SHA256:
            raise HashMismatchError(
                f"retail UNPACK preflight failed: size={source.size} sha256={source_hash}"
            )
    rows = _read_inventory(inventory, spec)
    apply_master_overrides(rows, master_csv)
    stop = spec.card_count if end is None else end
    if not 0 <= start <= stop <= spec.card_count:
        raise ValueError(f"invalid card range {start}:{stop}")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with source.path.open("rb") as src, output_path.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
    target = OuterSDA(output_path)
    if not source.same_layout(target):
        raise VerificationError("UNPACK layout changed during initial copy")

    renderer = CardFaceRenderer(GameFont(fontlink), spec)
    report: list[CardFaceBuildRow] = []
    with output_path.open("r+b") as handle:
        for sequence in range(start, stop):
            row = rows[sequence]
            large_chunk = int(row["large_chunk"])
            small_chunk = int(row["small_chunk"])
            large_raw = source.read_chunk(large_chunk)
            inner_size = struct.unpack_from("<I", large_raw, 0)[0]
            archive = parse_archive_bytes(large_raw[:inner_size], decompress=True)
            if len(archive.members) != 1 or archive.members[0].raw is None:
                raise VerificationError(f"card {sequence}: invalid large-card inner archive")
            (
                edited_tga,
                final_large,
                title_scale,
                type_scale,
                rules_scale,
                rules_lines,
                flavor_scale,
                flavor_lines,
                large_changed,
            ) = renderer.edit_large(archive.members[0].raw, row)
            new_large_chunk, method, headroom = _patch_large_chunk(large_raw, edited_tga)
            small_raw = source.read_chunk(small_chunk)
            new_small, small_changed = patch_small(small_raw, final_large, spec)
            if len(new_large_chunk) != len(large_raw) or len(new_small) != len(small_raw):
                raise VerificationError(f"card {sequence}: chunk allocation changed")
            for index, payload in ((large_chunk, new_large_chunk), (small_chunk, new_small)):
                bounds = source.bounds(index)
                handle.seek(bounds.start)
                handle.write(payload)
            report.append(
                CardFaceBuildRow(
                    sequence,
                    row.get("resource_key", ""),
                    int(row["internal_id"]),
                    row["english_name"],
                    large_chunk,
                    small_chunk,
                    CardFaceMetrics(
                        title_scale,
                        type_scale,
                        rules_scale,
                        rules_lines,
                        flavor_scale,
                        flavor_lines,
                        large_changed,
                        small_changed,
                        method,
                        headroom,
                    ),
                )
            )

    final = OuterSDA(output_path)
    if not source.same_layout(final):
        raise VerificationError("UNPACK layout changed after card-face build")
    expected_changed = {
        index
        for sequence in range(start, stop)
        for index in (spec.large_chunk_first + sequence, spec.small_chunk_first + sequence)
    }
    actual_changed = set(source.changed_chunks(final))
    if start == 0 and stop == spec.card_count:
        if actual_changed != expected_changed:
            raise VerificationError(
                f"card-face changed-set mismatch extra={sorted(actual_changed-expected_changed)[:8]} "
                f"missing={sorted(expected_changed-actual_changed)[:8]}"
            )
    elif not actual_changed <= expected_changed:
        raise VerificationError("partial card-face build changed a chunk outside requested range")
    return report


def patch_large_card_chunk(chunk: bytes, edited_tga: bytes) -> tuple[bytes, str, int]:
    """Public fixed-allocation helper shared by the UI75/UI76 card-image builders."""
    return _patch_large_chunk(chunk, edited_tga)
