from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .hashing import sha256_path
from .manifest import (
    BASELINE,
    RETAIL_UNPACK_SHA256,
    SECOND_NAME_FIRST,
    SECOND_NAME_LAST,
    UNPACK_SIZE,
)
from .sda import OuterSDA, replace_chunks_in_copy

CARD_COUNT = BASELINE.card_resource_count


@dataclass(frozen=True)
class UnpackVerification:
    retail_sha256: str
    target_sha256: str
    changed_chunks: tuple[int, ...]
    chunk_count: int


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_inventory_chunk_set(path: str | Path) -> set[int]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != CARD_COUNT:
        raise ValueError(f"inventory rows={len(rows)}; expected {CARD_COUNT}")
    result = {int(row[key]) for row in rows for key in ("large_chunk", "small_chunk")}
    if len(result) != CARD_COUNT * 2:
        raise ValueError("inventory card chunk set is malformed")
    return result


def apply_second_name_patch(
    ui76_compiled: str | Path,
    patch_zip: str | Path,
    output: str | Path,
) -> UnpackVerification:
    source = OuterSDA(ui76_compiled)
    if source.size != UNPACK_SIZE:
        raise ValueError(f"input size {source.size} != {UNPACK_SIZE}")
    with zipfile.ZipFile(patch_zip) as archive:
        rows = list(
            csv.DictReader(io.TextIOWrapper(archive.open("manifest.csv"), encoding="utf-8"))
        )
        if len(rows) != CARD_COUNT:
            raise ValueError(f"patch manifest rows={len(rows)}")
        replacements: dict[int, bytes] = {}
        for row in rows:
            index = int(row["chunk"])
            if not SECOND_NAME_FIRST <= index <= SECOND_NAME_LAST:
                raise ValueError(f"bad second-name patch chunk {index}")
            source_chunk = source.read_chunk(index)
            if _sha(source_chunk) != row["retail_sha256"]:
                raise ValueError(f"chunk {index}: source is not exact manifest preimage")
            payload = archive.read(f"chunks/{index:04d}.bin")
            if len(payload) != len(source_chunk) or _sha(payload) != row["patched_sha256"]:
                raise ValueError(f"chunk {index}: patch payload verification failed")
            replacements[index] = payload
    expected = set(range(SECOND_NAME_FIRST, SECOND_NAME_LAST + 1))
    if set(replacements) != expected:
        raise ValueError("target second-name chunk sequence is incomplete")
    target = replace_chunks_in_copy(source, output, replacements)
    changed = tuple(source.changed_chunks(target))
    if set(changed) != expected:
        raise RuntimeError("UNPACK containment mismatch after second-name patch")
    return UnpackVerification(
        sha256_path(source.path), sha256_path(target.path), changed, source.chunk_count
    )


def verify_ui76(
    retail: str | Path,
    compiled: str | Path,
    inventory: str | Path,
) -> UnpackVerification:
    retail_sda = OuterSDA(retail)
    target = OuterSDA(compiled)
    retail_hash = sha256_path(retail_sda.path)
    if retail_sda.size != UNPACK_SIZE or retail_hash != RETAIL_UNPACK_SHA256:
        raise ValueError("retail UNPACK preflight failed")
    if target.size != UNPACK_SIZE or not retail_sda.same_layout(target):
        raise ValueError("compiled UNPACK size/offset table changed")
    expected = load_inventory_chunk_set(inventory)
    changed = tuple(retail_sda.changed_chunks(target))
    if set(changed) != expected:
        extra = sorted(set(changed) - expected)[:12]
        missing = sorted(expected - set(changed))[:12]
        raise ValueError(f"UI76 changed-set mismatch extra={extra} missing={missing}")
    return UnpackVerification(retail_hash, sha256_path(target.path), changed, target.chunk_count)


def verify_ui82(
    retail: str | Path,
    ui76: str | Path,
    ui82: str | Path,
    inventory: str | Path,
    patch_zip: str | Path,
) -> tuple[UnpackVerification, tuple[int, ...]]:
    retail_sda = OuterSDA(retail)
    u76 = OuterSDA(ui76)
    u82 = OuterSDA(ui82)
    retail_hash = sha256_path(retail_sda.path)
    if retail_sda.size != UNPACK_SIZE or retail_hash != RETAIL_UNPACK_SHA256:
        raise ValueError("retail UNPACK preflight failed")
    if not retail_sda.same_layout(u76) or not retail_sda.same_layout(u82):
        raise ValueError("UNPACK size/offset table changed")
    old = load_inventory_chunk_set(inventory)
    second = set(range(SECOND_NAME_FIRST, SECOND_NAME_LAST + 1))
    changed_76 = set(retail_sda.changed_chunks(u76))
    changed_82 = set(retail_sda.changed_chunks(u82))
    delta = tuple(u76.changed_chunks(u82))
    if changed_76 != old:
        raise ValueError("UI76 changed-set mismatch")
    if changed_82 != old | second:
        raise ValueError("UI82 changed-set mismatch")
    if set(delta) != second:
        raise ValueError("UI76->UI82 delta mismatch")

    with zipfile.ZipFile(patch_zip) as archive:
        rows = list(
            csv.DictReader(io.TextIOWrapper(archive.open("manifest.csv"), encoding="utf-8"))
        )
        if len(rows) != CARD_COUNT:
            raise ValueError("patch manifest row count mismatch")
        for row in rows:
            index = int(row["chunk"])
            if retail_sda.chunk_sha256(index) != row["retail_sha256"]:
                raise ValueError(f"retail payload verification failed for chunk {index}")
            if u82.chunk_sha256(index) != row["patched_sha256"]:
                raise ValueError(f"UI82 payload verification failed for chunk {index}")
    result = UnpackVerification(
        retail_hash,
        sha256_path(u82.path),
        tuple(sorted(changed_82)),
        u82.chunk_count,
    )
    return result, delta


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    return info




def write_second_name_patch(
    output_zip: str | Path,
    rows: list[dict[str, str]],
    payloads: list[tuple[int, bytes]],
) -> None:
    """Write the canonical deterministic second-name patch ZIP format."""
    out = Path(output_zip)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = io.StringIO(newline="")
    writer = csv.DictWriter(
        manifest,
        fieldnames=("chunk", "retail_sha256", "patched_sha256"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(_zip_info("manifest.csv"), manifest.getvalue().encode("utf-8"))
        for index, payload in payloads:
            archive.writestr(_zip_info(f"chunks/{index:04d}.bin"), payload)

    with zipfile.ZipFile(out) as archive:
        check = list(
            csv.DictReader(io.TextIOWrapper(archive.open("manifest.csv"), encoding="utf-8"))
        )
        if check != rows:
            raise RuntimeError("second-name patch manifest round-trip mismatch")
        for row in check:
            index = int(row["chunk"])
            payload = archive.read(f"chunks/{index:04d}.bin")
            if _sha(payload) != row["patched_sha256"]:
                raise RuntimeError(f"second-name patch payload round-trip failed at {index}")


def create_second_name_patch(
    retail: str | Path,
    ui76: str | Path,
    ui82: str | Path,
    output_zip: str | Path,
    *,
    inventory: str | Path | None = None,
    verify_retail: bool = True,
) -> UnpackVerification:
    """Create the deterministic 677-chunk UI82 second-name patch payload ZIP.

    This packages the already-rendered second 128x128 card-sprite layer.  It deliberately does
    not regenerate card artwork; semantic sprite generation remains a separate historical step.
    The source UI76 image is required so the delta is proven to contain exactly chunks 2037..2713.
    """
    retail_sda = OuterSDA(retail)
    u76 = OuterSDA(ui76)
    u82 = OuterSDA(ui82)
    retail_hash = sha256_path(retail_sda.path)
    if verify_retail and (
        retail_sda.size != UNPACK_SIZE or retail_hash != RETAIL_UNPACK_SHA256
    ):
        raise ValueError(
            f"retail UNPACK preflight failed: size={retail_sda.size} sha256={retail_hash}"
        )
    if not retail_sda.same_layout(u76) or not retail_sda.same_layout(u82):
        raise ValueError("UNPACK size/offset table changed")

    second = set(range(SECOND_NAME_FIRST, SECOND_NAME_LAST + 1))
    delta = set(u76.changed_chunks(u82))
    if delta != second:
        raise ValueError(
            f"UI76->UI82 second-name delta mismatch extra={sorted(delta-second)[:8]} "
            f"missing={sorted(second-delta)[:8]}"
        )
    if inventory is not None:
        old = load_inventory_chunk_set(inventory)
        changed_76 = set(retail_sda.changed_chunks(u76))
        changed_82 = set(retail_sda.changed_chunks(u82))
        if changed_76 != old:
            raise ValueError("UI76 changed-set mismatch while creating second-name patch")
        if changed_82 != old | second:
            raise ValueError("UI82 changed-set mismatch while creating second-name patch")

    rows: list[dict[str, str]] = []
    payloads: list[tuple[int, bytes]] = []
    for index in range(SECOND_NAME_FIRST, SECOND_NAME_LAST + 1):
        retail_chunk = retail_sda.read_chunk(index)
        ui76_chunk = u76.read_chunk(index)
        if retail_chunk != ui76_chunk:
            raise ValueError(f"chunk {index}: UI76 unexpectedly changed second-name preimage")
        payload = u82.read_chunk(index)
        if len(payload) != len(retail_chunk):
            raise ValueError(f"chunk {index}: UI82 payload changed allocation")
        rows.append(
            {
                "chunk": str(index),
                "retail_sha256": _sha(retail_chunk),
                "patched_sha256": _sha(payload),
            }
        )
        payloads.append((index, payload))

    write_second_name_patch(output_zip, rows, payloads)

    return UnpackVerification(
        retail_hash,
        sha256_path(u82.path),
        tuple(range(SECOND_NAME_FIRST, SECOND_NAME_LAST + 1)),
        u82.chunk_count,
    )
