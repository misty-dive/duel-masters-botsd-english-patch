#!/usr/bin/env python3
"""Fix BOTSD English patch issue #2: malformed duel digits 6-9.

The v1.1 English DUELPTS atlas clears/paints the LEFT label too high, overlapping the
bottom rows of the shared 6-9 numeric glyphs. This tool restores those glyph pixels from
a clean Japanese DUELPTS.DAT and relocates the already-rendered LEFT raster downward so
the two atlas regions no longer overlap.

Inputs are hash-guarded to the verified clean and v1.1 files used for the diagnosis.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

CLEAN_SHA256 = "b90825eb09f455e473cf47f3721a46a277fd3fbb78bd361df6d5b5dc1141e89e"
V11_SHA256 = "d9296abff10b847157e54f8b59e6bcb084e0a727db77d99be3cb268005d5faa4"
TARGET = "DUELPTS_SRC_G_P00_TGA"

# Top-down atlas coordinates.
DIGIT_RESTORE = (128, 357, 221, 385)  # complete clean 6-9 glyph region
OLD_LEFT_BOX = (145, 374, 221, 408)
LEFT_TEXT_BBOX = (149, 379, 219, 403)  # verified v1.1 raster bbox
NEW_LEFT_BBOX = (149, 385, 219, 408)  # 70x23, safely below numeric glyphs
FACE_INDEX = 251
OUTLINE_INDEX = 10


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_local(name: str, filename: str):
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class IndexedTGA:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.idlen, self.cmaptype, self.imgtype = raw[0], raw[1], raw[2]
        self.cf, self.cl, self.cb = struct.unpack_from("<HHB", raw, 3)
        self.xo, self.yo, self.w, self.h, self.bpp, self.desc = struct.unpack_from("<HHHHBB", raw, 8)
        if not (self.cmaptype == 1 and self.imgtype == 1 and self.bpp == 8 and self.cb in (24, 32)):
            raise ValueError("unsupported TGA")
        self.bpe = self.cb // 8
        self.pixoff = 18 + self.idlen + self.cl * self.bpe
        stored = np.frombuffer(raw[self.pixoff:self.pixoff + self.w * self.h], dtype=np.uint8).reshape(self.h, self.w).copy()
        self.idx = stored if (self.desc & 32) else stored[::-1].copy()

    def bytes(self) -> bytes:
        stored = self.idx if (self.desc & 32) else self.idx[::-1]
        out = bytearray(self.raw)
        out[self.pixoff:self.pixoff + self.w * self.h] = stored.astype(np.uint8).tobytes()
        return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("clean_duelpts", type=Path)
    ap.add_argument("v11_duelpts", type=Path)
    ap.add_argument("output_duelpts", type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    arcmod = load_local("issue2_arc", "bosd_ui_archive_tool_v1.py")
    strong = load_local("issue2_lzss", "bosd_ui_lzss_strong.py")

    clean_bytes = args.clean_duelpts.read_bytes()
    v11_bytes = args.v11_duelpts.read_bytes()
    if sha256(clean_bytes) != CLEAN_SHA256:
        raise SystemExit(f"clean input SHA-256 mismatch: {sha256(clean_bytes)}")
    if sha256(v11_bytes) != V11_SHA256:
        raise SystemExit(f"v1.1 input SHA-256 mismatch: {sha256(v11_bytes)}")

    clean_arc = arcmod.parse_archive(args.clean_duelpts, decompress=True)
    v11_arc = arcmod.parse_archive(args.v11_duelpts, decompress=True)
    clean_members = {m.name: m for m in clean_arc.members}
    v11_members = {m.name: m for m in v11_arc.members}
    if set(clean_members) != set(v11_members):
        raise RuntimeError("archive member set mismatch")

    # Confirm the only decompressed member changed by the English patch is the target atlas.
    changed_raw = [n for n in clean_members if clean_members[n].raw != v11_members[n].raw]
    if changed_raw != [TARGET]:
        raise RuntimeError(f"unexpected decompressed member differences: {changed_raw}")

    cm = clean_members[TARGET]
    pm = v11_members[TARGET]
    clean_tga = IndexedTGA(cm.raw)
    patch_tga = IndexedTGA(pm.raw)
    if (clean_tga.w, clean_tga.h, clean_tga.pixoff) != (patch_tga.w, patch_tga.h, patch_tga.pixoff):
        raise RuntimeError("TGA geometry mismatch")
    if cm.raw[:clean_tga.pixoff] != pm.raw[:patch_tga.pixoff]:
        raise RuntimeError("TGA header/palette mismatch")

    before = patch_tga.idx.copy()
    fixed = before.copy()

    # Verified v1.1 LEFT text raster. Preserve its exact palette indices, but compress it
    # vertically by one row so it fits entirely below the numeric strip.
    x0, y0, x1, y1 = LEFT_TEXT_BBOX
    left_raster = before[y0:y1, x0:x1].copy()
    keep = np.isin(left_raster, [FACE_INDEX, OUTLINE_INDEX])
    left_raster = np.where(keep, left_raster, 0).astype(np.uint8)
    if not keep.any() or left_raster.shape != (24, 70):
        raise RuntimeError("unexpected LEFT raster geometry")

    # Remove old LEFT glyph pixels, leaving the already-cleared Japanese-label background.
    bx0, by0, bx1, by1 = OLD_LEFT_BOX
    region = fixed[by0:by1, bx0:bx1]
    old_text = np.isin(region, [FACE_INDEX, OUTLINE_INDEX])
    region[old_text] = 0
    fixed[by0:by1, bx0:bx1] = region

    # Restore 6-9 (including their lower anti-aliased/outline rows) exactly from retail.
    dx0, dy0, dx1, dy1 = DIGIT_RESTORE
    fixed[dy0:dy1, dx0:dx1] = clean_tga.idx[dy0:dy1, dx0:dx1]

    # Re-place LEFT wholly below the digit strip. Nearest-neighbor keeps the indexed face/outline.
    nx0, ny0, nx1, ny1 = NEW_LEFT_BBOX
    resized = np.array(Image.fromarray(left_raster, mode="L").resize((nx1-nx0, ny1-ny0), Image.Resampling.NEAREST), dtype=np.uint8)
    dst = fixed[ny0:ny1, nx0:nx1]
    use = resized != 0
    dst[use] = resized[use]
    fixed[ny0:ny1, nx0:nx1] = dst
    patch_tga.idx = fixed

    # Hard QA: 1-5 were already correct; 6-9 must now match the clean atlas exactly.
    digit_boxes = {
        "1": (25, 36), "2": (44, 63), "3": (66, 86), "4": (88, 108),
        "5": (110, 128), "6": (128, 152), "7": (155, 174),
        "8": (176, 196), "9": (199, 221),
    }
    before_counts = {}
    after_counts = {}
    for label, (gx0, gx1) in digit_boxes.items():
        before_counts[label] = int((before[357:385, gx0:gx1] != clean_tga.idx[357:385, gx0:gx1]).sum())
        after_counts[label] = int((fixed[357:385, gx0:gx1] != clean_tga.idx[357:385, gx0:gx1]).sum())
    if any(after_counts[d] for d in "123456789"):
        raise RuntimeError(f"digit restoration failed: {after_counts}")
    if [before_counts[d] for d in "12345"] != [0, 0, 0, 0, 0]:
        raise RuntimeError(f"unexpected v1.1 damage to digits 1-5: {before_counts}")
    if [before_counts[d] for d in "6789"] != [71, 136, 205, 206]:
        raise RuntimeError(f"unexpected v1.1 6-9 damage signature: {before_counts}")

    # No pixel outside the old LEFT rectangle may change relative to v1.1.
    delta = fixed != before
    yy, xx = np.where(delta)
    if len(xx) == 0:
        raise RuntimeError("fix made no changes")
    outside = ((xx < bx0) | (xx >= bx1) | (yy < by0) | (yy >= by1))
    if outside.any():
        raise RuntimeError("fix changed pixels outside the LEFT rectangle")

    fixed_raw = patch_tga.bytes()
    comp = strong.compress(fixed_raw)
    new_blob = struct.pack("<I", len(fixed_raw)) + comp
    if arcmod.decode_member_blob(new_blob, pm.compression) != fixed_raw:
        raise RuntimeError("compressed target did not round-trip")
    next_rel = v11_arc.members[pm.index + 1].data_rel if pm.index + 1 < len(v11_arc.members) else len(v11_bytes) - v11_arc.data_start
    alloc = next_rel - pm.data_rel
    if len(new_blob) > alloc:
        raise RuntimeError(f"fixed target overflows allocation: {len(new_blob)}/{alloc}")

    out = bytearray(v11_bytes)
    start = v11_arc.data_start + pm.data_rel
    out[start:start + len(new_blob)] = new_blob
    out[start + len(new_blob):start + alloc] = b"\x00" * (alloc - len(new_blob))
    struct.pack_into("<I", out, pm.record_off + 264, len(new_blob))
    args.output_duelpts.write_bytes(out)

    # Reparse output and verify all non-target decompressed members are unchanged from v1.1.
    verify_arc = arcmod.parse_archive(args.output_duelpts, decompress=True)
    verify_members = {m.name: m for m in verify_arc.members}
    if verify_members[TARGET].raw != fixed_raw:
        raise RuntimeError("output target raw mismatch")
    for name in v11_members:
        if name != TARGET and verify_members[name].raw != v11_members[name].raw:
            raise RuntimeError(f"non-target member changed: {name}")

    report = [
        "BOTSD GitHub issue #2 duel digit fix QA",
        f"clean_sha256={CLEAN_SHA256}",
        f"v11_sha256={V11_SHA256}",
        f"output_sha256={sha256(bytes(out))}",
        f"output_size={len(out)}",
        f"target={TARGET}",
        f"target_raw_sha256={sha256(fixed_raw)}",
        f"target_blob_size={len(new_blob)} allocation={alloc} headroom={alloc-len(new_blob)}",
        f"changed_pixels_vs_v11={int(delta.sum())}",
        f"changed_pixel_bbox=({int(xx.min())},{int(yy.min())})-({int(xx.max()+1)},{int(yy.max()+1)})",
        "v11_digit_mismatch_pixels=" + ",".join(f"{d}:{before_counts[d]}" for d in "123456789"),
        "fixed_digit_mismatch_pixels=" + ",".join(f"{d}:{after_counts[d]}" for d in "123456789"),
        "non_target_decompressed_members=byte-identical",
        "changes_outside_old_LEFT_rectangle=0",
        "RESULT=PASS",
    ]
    text = "\n".join(report) + "\n"
    print(text, end="")
    if args.report:
        args.report.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
