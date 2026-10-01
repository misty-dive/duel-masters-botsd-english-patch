from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .archive import parse_archive_bytes
from .errors import HashMismatchError, VerificationError
from .indexed_tga import IndexedTGA
from .ui_graphics import replace_member_fixed


@dataclass(frozen=True)
class DuelPtsFixResult:
    data: bytes
    changed_pixels: int
    before_digit_mismatches: dict[str, int]
    after_digit_mismatches: dict[str, int]
    report_lines: tuple[str, ...]


def load_spec(path: str | Path | None = None) -> dict:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets/duelpts_issue2.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_issue2_fix(
    clean_archive: bytes,
    v11_archive: bytes,
    *,
    spec: dict | None = None,
    verify_hashes: bool = True,
) -> DuelPtsFixResult:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow and NumPy are required for DUELPTS repair") from exc

    spec = spec or load_spec()
    if verify_hashes:
        clean_hash = _sha(clean_archive)
        v11_hash = _sha(v11_archive)
        if clean_hash != spec["clean_sha256"]:
            raise HashMismatchError(f"clean DUELPTS SHA-256 {clean_hash} != {spec['clean_sha256']}")
        if v11_hash != spec["v11_sha256"]:
            raise HashMismatchError(f"v1.1 DUELPTS SHA-256 {v11_hash} != {spec['v11_sha256']}")

    clean = parse_archive_bytes(clean_archive, label="DUELPTS clean", decompress=True)
    v11 = parse_archive_bytes(v11_archive, label="DUELPTS v1.1", decompress=True)
    clean_map = {member.name: member for member in clean.members}
    v11_map = {member.name: member for member in v11.members}
    if set(clean_map) != set(v11_map):
        raise VerificationError("DUELPTS archive member set mismatch")
    target = str(spec["target_member"])
    changed_members = [
        name for name in clean_map if clean_map[name].raw != v11_map[name].raw
    ]
    if changed_members != [target]:
        raise VerificationError(f"unexpected DUELPTS decompressed differences: {changed_members}")
    clean_raw = clean_map[target].raw
    v11_raw = v11_map[target].raw
    if clean_raw is None or v11_raw is None:
        raise VerificationError("DUELPTS target did not decompress")

    clean_tga = IndexedTGA(clean_raw)
    patch_tga = IndexedTGA(v11_raw)
    if (clean_tga.width, clean_tga.height) != (patch_tga.width, patch_tga.height):
        raise VerificationError("DUELPTS TGA geometry mismatch")
    if clean_tga.raw[: clean_tga.pixel_offset] != patch_tga.raw[: patch_tga.pixel_offset]:
        raise VerificationError("DUELPTS TGA header/palette mismatch")

    before = np.frombuffer(bytes(patch_tga.indices_top_down()), dtype=np.uint8).reshape(
        patch_tga.height, patch_tga.width
    ).copy()
    clean_indices = np.frombuffer(bytes(clean_tga.indices_top_down()), dtype=np.uint8).reshape(
        clean_tga.height, clean_tga.width
    )
    fixed = before.copy()

    x0, y0, x1, y1 = (int(v) for v in spec["left_text_bbox"])
    left = before[y0:y1, x0:x1].copy()
    keep = np.isin(left, [int(spec["face_index"]), int(spec["outline_index"])])
    left = np.where(keep, left, 0).astype(np.uint8)
    if not keep.any() or left.shape != (24, 70):
        raise VerificationError("unexpected v1.1 LEFT raster geometry")

    bx0, by0, bx1, by1 = (int(v) for v in spec["old_left_box"])
    region = fixed[by0:by1, bx0:bx1]
    old_text = np.isin(region, [int(spec["face_index"]), int(spec["outline_index"])])
    region[old_text] = 0
    fixed[by0:by1, bx0:bx1] = region

    dx0, dy0, dx1, dy1 = (int(v) for v in spec["digit_restore"])
    fixed[dy0:dy1, dx0:dx1] = clean_indices[dy0:dy1, dx0:dx1]

    nx0, ny0, nx1, ny1 = (int(v) for v in spec["new_left_bbox"])
    resized = np.array(
        Image.fromarray(left, mode="L").resize(
            (nx1 - nx0, ny1 - ny0), Image.Resampling.NEAREST
        ),
        dtype=np.uint8,
    )
    destination = fixed[ny0:ny1, nx0:nx1]
    use = resized != 0
    destination[use] = resized[use]
    fixed[ny0:ny1, nx0:nx1] = destination

    before_counts: dict[str, int] = {}
    after_counts: dict[str, int] = {}
    for label, bounds in spec["digit_boxes"].items():
        gx0, gx1 = (int(v) for v in bounds)
        before_counts[label] = int(
            (before[357:385, gx0:gx1] != clean_indices[357:385, gx0:gx1]).sum()
        )
        after_counts[label] = int(
            (fixed[357:385, gx0:gx1] != clean_indices[357:385, gx0:gx1]).sum()
        )
    expected_damage = {str(k): int(v) for k, v in spec["expected_v11_damage"].items()}
    if before_counts != expected_damage:
        raise VerificationError(f"unexpected v1.1 digit damage signature: {before_counts}")
    if any(after_counts.values()):
        raise VerificationError(f"DUELPTS digit restoration failed: {after_counts}")

    delta = fixed != before
    yy, xx = np.where(delta)
    if len(xx) == 0:
        raise VerificationError("DUELPTS fix changed no pixels")
    outside = (xx < bx0) | (xx >= bx1) | (yy < by0) | (yy >= by1)
    if outside.any():
        raise VerificationError("DUELPTS fix changed pixels outside old LEFT rectangle")

    patch_tga.replace_top_down(fixed.astype(np.uint8).tobytes())
    fixed_raw = patch_tga.to_bytes()
    output = replace_member_fixed(v11_archive, target, fixed_raw)
    if verify_hashes and _sha(output) != spec["expected_output_sha256"]:
        raise VerificationError(
            f"DUELPTS output SHA-256 {_sha(output)} != {spec['expected_output_sha256']}"
        )
    report = (
        "BOTSD issue #2 duel digit fix: PASS",
        f"output_sha256={_sha(output)}",
        f"changed_pixels_vs_v11={int(delta.sum())}",
        "v11_digit_mismatch_pixels=" + ",".join(f"{d}:{before_counts[d]}" for d in "123456789"),
        "fixed_digit_mismatch_pixels=" + ",".join(f"{d}:{after_counts[d]}" for d in "123456789"),
        "changes_outside_old_LEFT_rectangle=0",
        "RESULT=PASS",
    )
    return DuelPtsFixResult(output, int(delta.sum()), before_counts, after_counts, report)
