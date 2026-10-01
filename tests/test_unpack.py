from __future__ import annotations

from botsd.unpack import CARD_COUNT, SECOND_NAME_FIRST, SECOND_NAME_LAST


def test_unpack_layer_constants_are_contiguous() -> None:
    assert CARD_COUNT == 677
    assert SECOND_NAME_LAST - SECOND_NAME_FIRST + 1 == CARD_COUNT
    assert SECOND_NAME_FIRST == 2037
    assert SECOND_NAME_LAST == 2713
