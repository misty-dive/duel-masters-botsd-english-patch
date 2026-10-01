from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from .errors import HashMismatchError

DEFAULT_CHUNK = 8 * 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(
    stream: BinaryIO, size: int | None = None, chunk_size: int = DEFAULT_CHUNK
) -> str:
    """Hash a stream from its current position.

    If ``size`` is supplied, exactly that many bytes are consumed and a short read is an error.
    """
    h = hashlib.sha256()
    remaining = size
    while remaining is None or remaining:
        want = chunk_size if remaining is None else min(chunk_size, remaining)
        chunk = stream.read(want)
        if not chunk:
            if remaining is not None and remaining:
                raise EOFError(f"short read while hashing: {remaining} bytes remain")
            break
        h.update(chunk)
        if remaining is not None:
            remaining -= len(chunk)
    return h.hexdigest()


def sha256_path(path: str | Path, chunk_size: int = DEFAULT_CHUNK) -> str:
    with Path(path).open("rb") as stream:
        return sha256_stream(stream, chunk_size=chunk_size)


def sha256_range(path: str | Path, offset: int, size: int, chunk_size: int = DEFAULT_CHUNK) -> str:
    if offset < 0 or size < 0:
        raise ValueError("offset and size must be non-negative")
    with Path(path).open("rb") as stream:
        stream.seek(offset)
        return sha256_stream(stream, size=size, chunk_size=chunk_size)


def verify_sha256(path: str | Path, expected: str, *, label: str | None = None) -> str:
    got = sha256_path(path)
    if got != expected:
        name = label or str(path)
        raise HashMismatchError(f"{name}: SHA-256 {got} != expected {expected}")
    return got
