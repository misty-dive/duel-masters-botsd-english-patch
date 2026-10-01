from __future__ import annotations

from botsd.exec_strings import decode_cstr, patch_fixed_slots


def test_fixed_exec_string_patching_is_slot_contained() -> None:
    source = bytearray(b"\0" * 256)
    source[16:24] = b"OLD\0\0\0\0\0"
    source[64:70] = b"GUARD\0"
    source[120:128] = b"NETWORK!"
    spec = {
        "guards": [{"offset": 64, "expected": "GUARD"}],
        "slots": [{"id": "label", "offset": 16, "size": 8}],
        "network_unchanged_range": [120, 128],
    }
    result = patch_fixed_slots(bytes(source), spec, {"label": "NEW"}, verify_input_hash=False)
    assert decode_cstr(result.data, 16, 8) == "NEW"
    assert result.data[120:128] == b"NETWORK!"
    assert result.data[:16] == bytes(source[:16])


def test_fixed_exec_string_rejects_overflow() -> None:
    source = b"\0" * 32
    spec = {"slots": [{"id": "label", "offset": 0, "size": 4}]}
    try:
        patch_fixed_slots(source, spec, {"label": "TOO LONG"}, verify_input_hash=False)
    except ValueError as exc:
        assert "will not fit" in str(exc)
    else:
        raise AssertionError("expected fixed-slot overflow to fail")
