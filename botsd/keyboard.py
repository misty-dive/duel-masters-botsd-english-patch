from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .hashing import sha256_bytes
from .patching import BytePatch, apply_patches


def load_spec(path: str | Path | None = None) -> dict:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path is not None
        else files("botsd").joinpath("assets/keyboard_ui81.json").read_text(encoding="utf-8")
    )
    return json.loads(text)


_SPEC = load_spec()
MODE_VA = int(_SPEC["mode_va"])
VA_DELTA = int(_SPEC["va_delta"])
MODE_OFFSET = int(_SPEC["mode_file_offset"])
if MODE_OFFSET != MODE_VA - VA_DELTA:
    raise RuntimeError("keyboard manifest VA/file-offset relationship is inconsistent")
HISTORICAL_V12_INPUT_SHA256 = str(_SPEC["historical_input_sha256"])
HISTORICAL_V12_OLD_MODE = int(_SPEC["historical_old_mode"])
HISTORICAL_V12_NEW_MODE = int(_SPEC["historical_v12_mode"])
V13_FINAL_MODE = int(_SPEC["v13_final_mode"])


@dataclass(frozen=True)
class KeyboardPatchResult:
    data: bytes
    input_sha256: str
    output_sha256: str
    offset: int
    old_mode: int
    new_mode: int


def patch_mode(
    source: bytes,
    *,
    old_mode: int,
    new_mode: int,
    expected_sha256: str | None = None,
) -> KeyboardPatchResult:
    if expected_sha256 is not None:
        got = sha256_bytes(source)
        if got != expected_sha256:
            raise ValueError(f"keyboard source SHA-256 {got} != expected {expected_sha256}")
    if not 0 <= old_mode <= 0xFF or not 0 <= new_mode <= 0xFF:
        raise ValueError("keyboard mode must fit in one byte")
    target = apply_patches(
        source,
        [BytePatch(MODE_OFFSET, bytes([old_mode]), bytes([new_mode]), "keyboard default mode")],
    )
    diffs = [index for index, (before, after) in enumerate(zip(source, target, strict=True)) if before != after]
    if diffs != [MODE_OFFSET]:
        raise RuntimeError(f"unexpected keyboard patch diff offsets: {diffs[:16]}")
    return KeyboardPatchResult(
        data=target,
        input_sha256=sha256_bytes(source),
        output_sha256=sha256_bytes(target),
        offset=MODE_OFFSET,
        old_mode=old_mode,
        new_mode=new_mode,
    )


def build_historical_v12_stage(source: bytes) -> KeyboardPatchResult:
    return patch_mode(
        source,
        old_mode=HISTORICAL_V12_OLD_MODE,
        new_mode=HISTORICAL_V12_NEW_MODE,
        expected_sha256=HISTORICAL_V12_INPUT_SHA256,
    )
