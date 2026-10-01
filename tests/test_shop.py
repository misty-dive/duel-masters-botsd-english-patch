from __future__ import annotations

from botsd.shop import (
    BOOSTER_DESCRIPTION_OFFSET,
    BOOSTER_DESCRIPTION_SIZE,
    BOOSTER_METADATA_OFFSET,
    BOOSTER_RECORD_STRIDE,
    BoosterDescription,
    patch_booster_descriptions,
)


def _record(code: str, description: str, metadata: bytes) -> bytes:
    out = bytearray(BOOSTER_RECORD_STRIDE)
    code_bytes = code.encode("ascii")
    out[: len(code_bytes)] = code_bytes
    desc = description.encode("cp932")
    out[BOOSTER_DESCRIPTION_OFFSET : BOOSTER_DESCRIPTION_OFFSET + len(desc)] = desc
    out[BOOSTER_METADATA_OFFSET : BOOSTER_METADATA_OFFSET + len(metadata)] = metadata
    return bytes(out)


def test_booster_description_patch_preserves_metadata() -> None:
    metadata_a = bytes(range(16))
    metadata_b = bytes(range(16, 32))
    source = _record("DM-06", "Old", metadata_a) + _record("DM-07", "Old2", metadata_b)
    target = patch_booster_descriptions(
        source,
        (
            BoosterDescription("DM-06", "Stomp-A-Trons of Invincible Wrath"),
            BoosterDescription("DM-07", "Thundercharge of Ultra Destruction"),
        ),
        table_offset=0,
    )
    assert len(target) == len(source)
    assert target[BOOSTER_METADATA_OFFSET : BOOSTER_METADATA_OFFSET + 16] == metadata_a
    second = BOOSTER_RECORD_STRIDE + BOOSTER_METADATA_OFFSET
    assert target[second : second + 16] == metadata_b
    first_desc = target[
        BOOSTER_DESCRIPTION_OFFSET : BOOSTER_DESCRIPTION_OFFSET + BOOSTER_DESCRIPTION_SIZE
    ].split(b"\0", 1)[0]
    assert first_desc.decode("cp932") == "Stomp-A-Trons of Invincible Wrath"
