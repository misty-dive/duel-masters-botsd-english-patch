from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from .errors import VerificationError


@dataclass(frozen=True)
class BytePatch:
    offset: int
    old: bytes
    new: bytes
    label: str

    def __post_init__(self) -> None:
        if len(self.old) != len(self.new):
            raise ValueError(f"{self.label}: same-size maintenance patches are required")

    def apply(self, data: bytearray) -> None:
        end = self.offset + len(self.old)
        got = bytes(data[self.offset:end])
        if got != self.old:
            raise VerificationError(
                f"{self.label}: input mismatch at 0x{self.offset:X}: "
                f"got {got.hex()}, expected {self.old.hex()}"
            )
        data[self.offset:end] = self.new


def apply_patches(source: bytes, patches: Iterable[BytePatch]) -> bytes:
    """Apply a guarded sequence of same-size byte patches and return immutable bytes."""
    out = bytearray(source)
    for patch in patches:
        patch.apply(out)
    return bytes(out)
