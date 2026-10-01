from pathlib import Path

from botsd.ppf import apply, build, range_payload, verify


def test_ppf_roundtrip_and_extension(tmp_path: Path):
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    patch = tmp_path / "delta.ppf"
    output = tmp_path / "output.bin"

    source.write_bytes(bytes(range(250)) * 8)
    expected = bytearray(source.read_bytes())
    expected[15:24] = b"BOTSDv1.3"
    expected[700:1200] = b"Z" * 500
    expected.extend(b"\x00" * 300)
    target.write_bytes(expected)

    stats, changed = build(source, target, patch, description="BOTSD synthetic test")
    assert changed > 0
    assert verify(patch) == stats

    apply(source, patch, output, target_size=len(expected))
    assert output.read_bytes() == bytes(expected)


def test_ppf_range_payload(tmp_path: Path):
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    patch = tmp_path / "delta.ppf"
    source.write_bytes(b"A" * 1024)
    blob = bytearray(b"A" * 1024)
    blob[100:120] = b"B" * 20
    target.write_bytes(blob)
    build(source, target, patch)

    payload, mask = range_payload(patch, 90, 40)
    assert payload[10:30] == b"B" * 20
    assert mask[10:30] == b"\x01" * 20
    assert sum(mask) == 20
