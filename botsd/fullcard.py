from __future__ import annotations

import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .card_sources import (
    ALLOWED_SOURCE_CLASSES,
    apply_exception_sources,
    build_mapping,
    download_file,
    ensure_database,
    save_mapping,
)
from .cardfaces import patch_large_card_chunk
from .errors import HashMismatchError, VerificationError
from .hashing import sha256_path
from .indexed_tga import IndexedTGA
from .manifest import BASELINE
from .sda import OuterSDA
from .unpack import RETAIL_UNPACK_SHA256, UNPACK_SIZE

SOURCE_COLOR_ATTEMPTS = (224, 192, 160, 144, 128, 112, 96, 80, 72, 64, 56, 48, 40, 32)
PRINTED_FACE = (0, 0, 384, 512)


@dataclass(frozen=True)
class FullCardBuildReport:
    output_sha256: str
    resources: int
    online_resources: int
    exception_resources: int
    changed_chunks: int
    min_compressed_headroom: int
    min_source_colors: int
    source_class_counts: dict[str, int]
    status_counts: dict[str, int]


def replace_region_preserving_palette(
    tga: IndexedTGA,
    image,
    region: tuple[int, int, int, int],
    *,
    source_colors: int,
) -> bytes:
    """Quantize an RGBA/RGB source and map it onto an existing indexed TGA palette.

    Header, palette and every pixel outside ``region`` remain byte-identical. Source colors are
    mapped only to palette entries with alpha >= 128, matching the accepted UI76 pipeline.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow and NumPy are required for full-card conversion") from exc

    x0, y0, x1, y1 = region
    if not (0 <= x0 <= x1 <= tga.width and 0 <= y0 <= y1 <= tga.height):
        raise ValueError(f"region {region} outside {tga.width}x{tga.height}")
    width, height = x1 - x0, y1 - y0
    source = image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    quantized = source.quantize(
        colors=source_colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB")
    array = np.asarray(quantized, dtype=np.uint8)
    unique, inverse = np.unique(array.reshape(-1, 3), axis=0, return_inverse=True)
    palette = np.asarray([entry[:3] for entry in tga.palette], dtype=np.int16)
    opaque_slots = np.asarray(
        [slot for slot, entry in enumerate(tga.palette) if entry[3] >= 128], dtype=np.int32
    )
    if len(opaque_slots) == 0:
        raise VerificationError("indexed card texture has no opaque palette entries")
    opaque_palette = palette[opaque_slots]
    mapped_slots = np.empty(len(unique), dtype=np.int32)
    values = unique.astype(np.int16)
    for start in range(0, len(values), 512):
        difference = values[start : start + 512, None, :] - opaque_palette[None, :, :]
        distance = (difference.astype(np.int32) ** 2).sum(axis=2)
        mapped_slots[start : start + 512] = opaque_slots[np.argmin(distance, axis=1)]
    mapped_indices = mapped_slots[inverse].reshape(height, width) + tga.info.palette_first

    indices = np.frombuffer(bytes(tga.indices_top_down()), dtype=np.uint8).reshape(
        tga.height, tga.width
    ).copy()
    indices[y0:y1, x0:x1] = mapped_indices.astype(np.uint8)
    tga.replace_top_down(indices.tobytes())
    return tga.to_bytes()


def _convert_one(
    large_chunk: bytes,
    small_chunk: bytes,
    source_path: Path,
    english_name: str,
) -> tuple[bytes, bytes, int, str, int, str]:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow and NumPy are required for full-card conversion") from exc

    # Large chunks are the same one-member archive structure handled by the UI75 builder.
    import struct
    from .archive import parse_archive_bytes

    if len(large_chunk) < 8:
        raise VerificationError("large card chunk is too short")
    inner_size = struct.unpack_from("<I", large_chunk, 0)[0]
    archive = parse_archive_bytes(large_chunk[:inner_size], decompress=True)
    if len(archive.members) != 1 or archive.members[0].raw is None:
        raise VerificationError("large card chunk is not a one-member decoded archive")
    raw_large = archive.members[0].raw
    large_tga = IndexedTGA(raw_large)
    if (large_tga.width, large_tga.height) != (512, 512):
        raise VerificationError(f"unexpected large card dimensions {(large_tga.width, large_tga.height)}")

    with Image.open(source_path) as opened:
        scan = opened.convert("RGBA")
        original_size = f"{scan.width}x{scan.height}"
        selected: tuple[bytes, bytes, str, int, int] | None = None
        failure: Exception | None = None
        for colors in SOURCE_COLOR_ATTEMPTS:
            try:
                trial_tga = IndexedTGA(raw_large)
                new_raw = replace_region_preserving_palette(
                    trial_tga, scan, PRINTED_FACE, source_colors=colors
                )
                new_chunk, method, headroom = patch_large_card_chunk(large_chunk, new_raw)
                selected = (new_raw, new_chunk, method, headroom, colors)
                break
            except (VerificationError, ValueError) as exc:
                failure = exc
        if selected is None:
            raise VerificationError(
                f"{english_name}: no full-card palette candidate fits fixed allocation: {failure}"
            )
        new_large_raw, new_large_chunk, method, headroom, colors = selected

        after_large = IndexedTGA(new_large_raw)
        # The accepted UI76 edit is constrained to the printed x=0..383 face.
        old_idx = np.frombuffer(bytes(large_tga.indices_top_down()), dtype=np.uint8).reshape(512, 512)
        new_idx = np.frombuffer(bytes(after_large.indices_top_down()), dtype=np.uint8).reshape(512, 512)
        if not np.array_equal(old_idx[:, 384:], new_idx[:, 384:]):
            raise VerificationError("full-card conversion changed large pixels outside x=0..383")
        if raw_large[: large_tga.pixel_offset] != new_large_raw[: after_large.pixel_offset]:
            raise VerificationError("large card metadata/palette changed")

        # Small 128x128 printed card derives from the final palette-quantized large face.
        small_tga = IndexedTGA(small_chunk)
        if (small_tga.width, small_tga.height) != (128, 128):
            raise VerificationError(f"unexpected small card dimensions {(small_tga.width, small_tga.height)}")
        target = after_large.to_rgba_image().crop(PRINTED_FACE).resize(
            (128, 128), Image.Resampling.BICUBIC
        )
        new_small = replace_region_preserving_palette(
            IndexedTGA(small_chunk), target, (0, 0, 128, 128), source_colors=128
        )
        after_small = IndexedTGA(new_small)
        if small_chunk[: small_tga.pixel_offset] != new_small[: after_small.pixel_offset]:
            raise VerificationError("small card metadata/palette changed")
        if len(new_small) != len(small_chunk):
            raise VerificationError("small card texture size changed")
    return new_large_chunk, new_small, colors, method, headroom, original_size


def _resolve_sources(
    mapping: list[dict[str, object]],
    exceptions: dict[str, tuple[dict[str, str], Path]],
    cache_dir: Path,
    *,
    offline: bool,
) -> dict[int, Path]:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required for card source validation") from exc

    paths: dict[int, Path] = {}
    image_dir = cache_dir / "images"
    fetched: dict[int, tuple[Path, str, str]] = {}
    for row in mapping:
        if row.get("db_card_id"):
            db_id = int(str(row["db_card_id"]))
            if db_id not in fetched:
                path = image_dir / f"{db_id:04d}.webp"
                if not path.exists():
                    if offline:
                        raise FileNotFoundError(f"offline and image absent: {path}")
                    download_file(str(row["source_url"]), path, min_size=1000)
                with Image.open(path) as opened:
                    if opened.width < 100 or opened.height < 100:
                        raise VerificationError(f"bad image dimensions {path}: {opened.size}")
                    size = f"{opened.width}x{opened.height}"
                fetched[db_id] = (path, sha256_path(path), size)
            path, digest, size = fetched[db_id]
            row["source_sha256"] = digest
            row["source_size"] = size
            paths[int(str(row["seq"]))] = path
        else:
            _, path = exceptions[str(row["resource_key"])]
            paths[int(str(row["seq"]))] = path
    return paths


def build_full_card_images(
    base_unpack: str | Path,
    inventory: str | Path,
    crosswalk: str | Path,
    output: str | Path,
    qa_dir: str | Path,
    *,
    cache_dir: str | Path,
    exception_dir: str | Path,
    database: str | Path | None = None,
    offline: bool = False,
    allow_unpinned_db: bool = False,
    verify_retail: bool = True,
) -> FullCardBuildReport:
    """Build the accepted UI76 whole-card English image layer without loading UNPACK into RAM."""
    source = OuterSDA(base_unpack)
    if verify_retail:
        digest = sha256_path(source.path)
        if source.size != UNPACK_SIZE or digest != RETAIL_UNPACK_SHA256:
            raise HashMismatchError(
                f"retail UNPACK preflight failed: size={source.size} sha256={digest}"
            )
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    db = ensure_database(
        cache,
        Path(database) if database else None,
        offline=offline,
        allow_unpinned=allow_unpinned_db,
    )
    mapping = build_mapping(inventory, crosswalk, db)
    exceptions = apply_exception_sources(mapping, exception_dir)
    if len(mapping) != BASELINE.card_resource_count or any(
        str(row["source_class"]) not in ALLOWED_SOURCE_CLASSES for row in mapping
    ):
        raise VerificationError(
            f"not all {BASELINE.card_resource_count} card resources have an approved full-card source"
        )
    source_paths = _resolve_sources(mapping, exceptions, cache, offline=offline)

    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.path.open("rb") as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
    target = OuterSDA(destination)
    if not source.same_layout(target):
        raise VerificationError("UNPACK layout changed during full-card copy")

    with destination.open("r+b") as handle:
        for row in mapping:
            seq = int(str(row["seq"]))
            large_index = int(str(row["large_chunk"]))
            small_index = int(str(row["small_chunk"]))
            large_chunk = source.read_chunk(large_index)
            small_chunk = source.read_chunk(small_index)
            new_large, new_small, colors, method, headroom, source_size = _convert_one(
                large_chunk,
                small_chunk,
                source_paths[seq],
                str(row["english_name"]),
            )
            for index, payload in ((large_index, new_large), (small_index, new_small)):
                bounds = source.bounds(index)
                if len(payload) != bounds.size:
                    raise VerificationError(f"card {seq}: chunk {index} allocation changed")
                handle.seek(bounds.start)
                handle.write(payload)
            row["source_colors"] = colors
            row["compression"] = method
            row["compressed_headroom"] = headroom
            row["source_size"] = source_size

    final = OuterSDA(destination)
    if not source.same_layout(final):
        raise VerificationError("UNPACK layout changed after UI76 full-card build")
    expected = {int(str(row[key])) for row in mapping for key in ("large_chunk", "small_chunk")}
    changed = set(source.changed_chunks(final))
    if changed != expected:
        raise VerificationError(
            f"UI76 full-card changed-set mismatch extra={sorted(changed-expected)[:8]} "
            f"missing={sorted(expected-changed)[:8]}"
        )

    qa = Path(qa_dir)
    qa.mkdir(parents=True, exist_ok=True)
    save_mapping(mapping, qa / "UI76_WEBP_MAPPING.csv")
    classes = Counter(str(row["source_class"]) for row in mapping)
    statuses = Counter(str(row["status"]) for row in mapping)
    report = FullCardBuildReport(
        output_sha256=sha256_path(destination),
        resources=len(mapping),
        online_resources=sum(bool(row.get("db_card_id")) for row in mapping),
        exception_resources=sum(not bool(row.get("db_card_id")) for row in mapping),
        changed_chunks=len(changed),
        min_compressed_headroom=min(int(str(row["compressed_headroom"])) for row in mapping),
        min_source_colors=min(int(str(row["source_colors"])) for row in mapping),
        source_class_counts=dict(sorted(classes.items())),
        status_counts=dict(sorted(statuses.items())),
    )
    lines = [
        "UI76 FULL-CARD VERIFICATION: PASS",
        f"base_sha256 {sha256_path(source.path)}",
        f"output_sha256 {report.output_sha256}",
        f"outer_size {final.size}",
        "outer_offsets_unchanged yes",
        f"full_card_resources {report.resources}",
        f"online_webp_resources {report.online_resources}",
        f"packaged_exception_resources {report.exception_resources}",
        "ui75_synthetic_fallbacks 0",
        f"changed_outer_chunks {report.changed_chunks}",
        f"min_compressed_headroom {report.min_compressed_headroom}",
        f"min_source_colors {report.min_source_colors}",
        "whole_card_face_only x=0..383 yes",
        "large_and_small_metadata_palettes_preserved yes",
        "source_class_counts:",
        *[f"  {key}: {value}" for key, value in report.source_class_counts.items()],
        "status_counts:",
        *[f"  {key}: {value}" for key, value in report.status_counts.items()],
    ]
    (qa / "UI76_WEBP_VERIFICATION.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
