from __future__ import annotations

import hashlib
import json
import struct
import zipfile
from pathlib import Path

from botsd.datapack import PATCH_FORMAT, apply_chunk_patch


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_datapack_fixed_chunk_patch(tmp_path: Path) -> None:
    header_size = 20
    chunk0 = b"ABCD"
    chunk1 = b"EFGH"
    source = bytearray(header_size + len(chunk0) + len(chunk1))
    source[:4] = b"sda\0"
    struct.pack_into("<II", source, 4, len(source), 2)
    struct.pack_into("<II", source, 12, header_size, header_size + len(chunk0))
    source[header_size : header_size + 4] = chunk0
    source[header_size + 4 :] = chunk1
    source_bytes = bytes(source)

    replacement = b"WXYZ"
    target = bytearray(source_bytes)
    target[header_size + 4 :] = replacement
    target_bytes = bytes(target)

    manifest = {
        "format": PATCH_FORMAT,
        "retail_size": len(source_bytes),
        "retail_sha256": _sha(source_bytes),
        "target_size": len(target_bytes),
        "target_sha256": _sha(target_bytes),
        "changed_chunks": [
            {
                "index": 1,
                "offset": header_size + 4,
                "size": 4,
                "retail_sha256": _sha(chunk1),
                "target_sha256": _sha(replacement),
                "file": "chunk1.bin",
            }
        ],
    }
    patch = tmp_path / "patch.zip"
    with zipfile.ZipFile(patch, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("chunk1.bin", replacement)

    rebuilt, result = apply_chunk_patch(source_bytes, patch)
    assert rebuilt == target_bytes
    assert result.changed_chunks == (1,)
    assert result.sha256 == _sha(target_bytes)
