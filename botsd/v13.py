from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from .errors import HashMismatchError, VerificationError
from .exe_maintenance import build_v13_executable
from .hashing import sha256_bytes
from .localization import load_language_json
from .manifest import BASELINE
from .scrpack import build_v13_scrpack
from .semantic_assets import build_deck_ace_v13, build_tchange_v13

COMPONENT_ORDER = ("SLPM_658.82", "SCRPACK.SDA", "TCHANGE.IMG", "DECK.DAT")


@dataclass(frozen=True)
class ComponentBuild:
    name: str
    source_sha256: str
    target_sha256: str
    size: int


def _guard_v12(name: str, source: bytes) -> None:
    component = BASELINE.component(name)
    if len(source) != component.v12.size:
        raise HashMismatchError(
            f"{name}: size {len(source)} != public v1.2 size {component.v12.size}"
        )
    got = sha256_bytes(source)
    if got != component.v12.sha256:
        raise HashMismatchError(
            f"{name}: input SHA-256 {got} != public v1.2 {component.v12.sha256}"
        )


def build_component(
    name: str,
    source: bytes,
    *,
    language: str = "en",
    maintenance_strings: Mapping[str, Any] | None = None,
) -> bytes:
    """Transform one exact public-v1.2 maintenance component into exact v1.3 bytes.

    Executable and SCRPACK maintenance is derived from parsed structures/semantic recipes rather
    than stored byte-diff blobs.  Language-specific dialogue text is loaded from the selected
    localization package unless supplied explicitly.
    """
    _guard_v12(name, source)
    if name == "SLPM_658.82":
        out = build_v13_executable(source).data
    elif name == "SCRPACK.SDA":
        strings = (
            dict(maintenance_strings)
            if maintenance_strings is not None
            else load_language_json(language, "v13_maintenance.json")
        )
        out = build_v13_scrpack(source, strings).data
    elif name == "TCHANGE.IMG":
        out = build_tchange_v13(source)
    elif name == "DECK.DAT":
        out = build_deck_ace_v13(source, language=language)
    else:
        raise KeyError(name)

    component = BASELINE.component(name)
    if len(out) != component.v13.size:
        raise VerificationError(
            f"{name}: v1.3 output size {len(out)} != expected {component.v13.size}"
        )
    got = sha256_bytes(out)
    if got != component.v13.sha256:
        raise VerificationError(
            f"{name}: v1.3 output SHA-256 {got} != expected {component.v13.sha256}"
        )
    return out


def build_directory(
    v12_dir: str | Path,
    output_dir: str | Path,
    *,
    language: str = "en",
) -> tuple[ComponentBuild, ...]:
    source_dir = Path(v12_dir)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    rows: list[ComponentBuild] = []
    for name in COMPONENT_ORDER:
        source_path = source_dir / name
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        source = source_path.read_bytes()
        target = build_component(name, source, language=language)
        (target_dir / name).write_bytes(target)
        rows.append(
            ComponentBuild(
                name=name,
                source_sha256=BASELINE.component(name).v12.sha256,
                target_sha256=BASELINE.component(name).v13.sha256,
                size=len(target),
            )
        )
    return tuple(rows)
