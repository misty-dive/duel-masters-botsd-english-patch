from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping

from .errors import HashMismatchError, VerificationError
from .hashing import sha256_range
from .iso9660 import Iso9660, SECTOR
from .manifest import BASELINE


@dataclass(frozen=True)
class ExtractedAsset:
    name: str
    iso_path: str
    offset: int
    size: int
    sha256: str
    output: Path | None = None


def _copy_range(source: Path, offset: int, size: int, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    remaining = size
    with source.open("rb") as src, output.open("wb") as dst:
        src.seek(offset)
        while remaining:
            chunk = src.read(min(1024 * 1024, remaining))
            if not chunk:
                raise EOFError(f"short ISO read while extracting {output.name}")
            dst.write(chunk)
            remaining -= len(chunk)


def read_hash_manifest(path: str | Path) -> dict[str, str]:
    manifest = Path(path)
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        fields = tuple(reader.fieldnames or ())
        if "basename" not in fields or "sha256" not in fields:
            raise ValueError(f"{manifest}: expected tab-separated basename and sha256 columns")
        rows: dict[str, str] = {}
        for line, row in enumerate(reader, start=2):
            basename = (row.get("basename") or "").strip()
            digest = (row.get("sha256") or "").strip().lower()
            if not basename or len(digest) != 64:
                raise ValueError(f"{manifest}:{line}: invalid basename/SHA-256 row")
            key = basename.upper()
            if key in rows:
                raise ValueError(f"{manifest}:{line}: duplicate basename {basename!r}")
            rows[key] = digest
    return rows


def verify_hash_manifest(
    iso_path: str | Path,
    manifest_path: str | Path,
    extracts: Mapping[str, str | Path] | None = None,
) -> tuple[ExtractedAsset, ...]:
    """Verify/extract ISO files without loading the disc image into RAM."""
    image_path = Path(iso_path)
    image = Iso9660(image_path)
    expected = read_hash_manifest(manifest_path)
    wanted = {key.upper(): Path(value) for key, value in (extracts or {}).items()}
    unknown = sorted(set(wanted) - set(expected))
    if unknown:
        raise ValueError(f"extract requests are absent from hash manifest: {unknown}")

    rows: list[ExtractedAsset] = []
    for basename, digest in expected.items():
        entry = image.find_unique_basename(basename)
        offset = entry.extent * SECTOR
        got = sha256_range(image_path, offset, entry.size)
        if got != digest:
            raise HashMismatchError(
                f"{entry.path}: SHA-256 {got} != expected {digest}"
            )
        output = wanted.get(basename)
        if output is not None:
            _copy_range(image_path, offset, entry.size, output)
        rows.append(
            ExtractedAsset(
                name=basename,
                iso_path=entry.path,
                offset=offset,
                size=entry.size,
                sha256=got,
                output=output,
            )
        )
    return tuple(rows)


def extract_release_components(
    iso_path: str | Path,
    output_dir: str | Path,
    *,
    version: str = "v1.2",
) -> tuple[ExtractedAsset, ...]:
    """Extract the four release-maintenance components from an exact public patched ISO.

    The whole patched ISO hash was never published, so this proves identity through exact
    ISO size, ISO9660 location/size and all four component hashes.
    """
    if version not in {"v1.2", "v1.3"}:
        raise ValueError("version must be v1.2 or v1.3")
    image_path = Path(iso_path)
    if image_path.stat().st_size != BASELINE.patched_iso_size:
        raise HashMismatchError(
            f"patched ISO size {image_path.stat().st_size} != expected {BASELINE.patched_iso_size}"
        )
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    image = Iso9660(image_path)
    rows: list[ExtractedAsset] = []
    for component in BASELINE.components:
        entry = image.find_unique_basename(component.name)
        expected = component.v12 if version == "v1.2" else component.v13
        offset = entry.extent * SECTOR
        if offset != component.iso_offset:
            raise VerificationError(
                f"{entry.path}: ISO offset 0x{offset:X} != verified public offset "
                f"0x{component.iso_offset:X}"
            )
        if entry.size != expected.size:
            raise VerificationError(
                f"{entry.path}: size {entry.size} != expected {expected.size}"
            )
        digest = sha256_range(image_path, offset, entry.size)
        if digest != expected.sha256:
            raise HashMismatchError(
                f"{entry.path}: SHA-256 {digest} != expected {expected.sha256}"
            )
        target = output / component.name
        _copy_range(image_path, offset, entry.size, target)
        rows.append(
            ExtractedAsset(
                name=component.name,
                iso_path=entry.path,
                offset=offset,
                size=entry.size,
                sha256=digest,
                output=target,
            )
        )
    return tuple(rows)
