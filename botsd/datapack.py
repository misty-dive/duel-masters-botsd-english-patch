from __future__ import annotations

import hashlib
import json
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .errors import FormatError, HashMismatchError, VerificationError

PATCH_FORMAT = "BOSD_DATAPACK_CHUNK_PATCH_V1"


@dataclass(frozen=True)
class ChunkPatchResult:
    changed_chunks: tuple[int, ...]
    sha256: str
    size: int


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def apply_chunk_patch(source: bytes, patch_zip: str | Path) -> tuple[bytes, ChunkPatchResult]:
    """Apply a hash-gated fixed-size DATAPACK SDA chunk patch."""
    out = bytearray(source)
    with zipfile.ZipFile(patch_zip) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != PATCH_FORMAT:
            raise FormatError("bad DATAPACK patch format")
        if len(source) != int(manifest["retail_size"]) or _sha(source) != str(
            manifest["retail_sha256"]
        ):
            raise HashMismatchError("DATAPACK retail size/SHA-256 mismatch")
        if source[:4] != b"sda\0":
            raise FormatError("not a DATAPACK SDA")
        declared_size, chunk_count = struct.unpack_from("<II", source, 4)
        if declared_size != len(source):
            raise FormatError("SDA declared size mismatch")
        table_end = 12 + chunk_count * 4
        if table_end > len(source):
            raise FormatError("SDA chunk-offset table is truncated")
        offsets = list(struct.unpack_from("<" + "I" * chunk_count, source, 12))
        if offsets != sorted(offsets) or any(off < table_end or off > len(source) for off in offsets):
            raise FormatError("SDA chunk offsets are invalid")

        touched: list[int] = []
        for row in manifest.get("changed_chunks", []):
            index = int(row["index"])
            if not 0 <= index < chunk_count:
                raise FormatError(f"chunk index out of range: {index}")
            start = offsets[index]
            end = offsets[index + 1] if index + 1 < chunk_count else declared_size
            if start != int(row["offset"]) or end - start != int(row["size"]):
                raise VerificationError(f"chunk {index} layout mismatch")
            old = bytes(source[start:end])
            if _sha(old) != str(row["retail_sha256"]):
                raise HashMismatchError(f"chunk {index} retail hash mismatch")
            new = archive.read(str(row["file"]))
            if len(new) != end - start or _sha(new) != str(row["target_sha256"]):
                raise HashMismatchError(f"chunk {index} patch data corrupt")
            out[start:end] = new
            touched.append(index)

        target = bytes(out)
        if len(target) != int(manifest["target_size"]) or _sha(target) != str(
            manifest["target_sha256"]
        ):
            raise VerificationError("final DATAPACK hash mismatch")
    return target, ChunkPatchResult(tuple(touched), _sha(target), len(target))
