import pytest

from botsd.errors import VerificationError
from botsd.patching import BytePatch, apply_patches


def test_guarded_byte_patch_applies_and_composes() -> None:
    source = b"0123456789"
    patches = (
        BytePatch(2, b"23", b"AB", "first"),
        BytePatch(7, b"7", b"Z", "second"),
    )
    assert apply_patches(source, patches) == b"01AB456Z89"


def test_patch_refuses_wrong_preimage() -> None:
    patch = BytePatch(4, b"old", b"new", "guarded test")
    with pytest.raises(VerificationError):
        patch.apply(bytearray(b"xxxxxxxx"))
