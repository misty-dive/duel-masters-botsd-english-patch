import pytest

from botsd.errors import VerificationError
from botsd.keyboard import MODE_OFFSET, patch_mode


def test_keyboard_patch_changes_exactly_one_byte() -> None:
    source = bytearray(MODE_OFFSET + 2)
    source[MODE_OFFSET] = 6
    result = patch_mode(bytes(source), old_mode=6, new_mode=9)
    assert result.data[MODE_OFFSET] == 9
    diffs = [i for i, (a, b) in enumerate(zip(source, result.data, strict=True)) if a != b]
    assert diffs == [MODE_OFFSET]


def test_keyboard_patch_guards_expected_old_mode() -> None:
    source = bytes(MODE_OFFSET + 2)
    with pytest.raises(VerificationError):
        patch_mode(source, old_mode=6, new_mode=9)
