from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import HashMismatchError, VerificationError
from .hashing import sha256_path, sha256_range
from .manifest import BASELINE
from .ppf import PPFStats, apply as apply_ppf
from .ppf import verify as verify_ppf


@dataclass(frozen=True)
class BuildReport:
    source_sha256: str
    patch_sha256: str
    output_size: int
    ppf: PPFStats


def verify_release_components(image: str | Path) -> None:
    image_path = Path(image)
    for component in BASELINE.components:
        got = sha256_range(image_path, component.iso_offset, component.v13.size)
        if got != component.v13.sha256:
            raise VerificationError(
                f"{component.name}: output range SHA-256 {got} != expected {component.v13.sha256}"
            )


def build_release_image(
    source_iso: str | Path,
    release_ppf: str | Path,
    output_iso: str | Path,
    *,
    allow_unverified_patch: bool = False,
) -> BuildReport:
    source_path = Path(source_iso)
    patch_path = Path(release_ppf)
    output_path = Path(output_iso)
    if source_path.stat().st_size != BASELINE.clean_iso_size:
        raise HashMismatchError(
            f"clean ISO size {source_path.stat().st_size} != expected {BASELINE.clean_iso_size}"
        )
    source_hash = sha256_path(source_path)
    if source_hash != BASELINE.clean_iso_sha256:
        raise HashMismatchError(
            f"clean ISO SHA-256 {source_hash} != expected {BASELINE.clean_iso_sha256}"
        )

    patch_hash = sha256_path(patch_path)
    if not allow_unverified_patch:
        if patch_path.stat().st_size != BASELINE.full_ppf_size:
            raise HashMismatchError(
                f"v1.3 PPF size {patch_path.stat().st_size} != expected {BASELINE.full_ppf_size}"
            )
        if patch_hash != BASELINE.full_ppf_sha256:
            raise HashMismatchError(
                f"v1.3 PPF SHA-256 {patch_hash} != expected {BASELINE.full_ppf_sha256}"
            )

    stats = verify_ppf(patch_path)
    apply_ppf(source_path, patch_path, output_path, target_size=BASELINE.patched_iso_size)
    if output_path.stat().st_size != BASELINE.patched_iso_size:
        raise VerificationError(
            f"output size {output_path.stat().st_size} != expected {BASELINE.patched_iso_size}"
        )
    if not allow_unverified_patch:
        verify_release_components(output_path)
    return BuildReport(source_hash, patch_hash, output_path.stat().st_size, stats)
