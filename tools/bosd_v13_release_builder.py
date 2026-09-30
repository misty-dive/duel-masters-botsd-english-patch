#!/usr/bin/env python3
"""Build BOTSD v1.3 PPF3 release assets from exact public-v1.2 components.

Inputs:
  1) a directory containing the exact public-v1.2 versions of:
       SLPM_658.82, SCRPACK.SDA, TCHANGE.IMG, DECK.DAT
  2) the official public v1.2 full PPF

Outputs:
  - BOTSD_v1.2_to_v1.3_hotfix.ppf
  - Duel_Masters_Birth_of_Super_Dragon_English_v1.3.ppf
  - RELEASE_HASHES_v1.3.txt

The full v1.3 PPF is composed deterministically from the official v1.2 full PPF
plus the same-size v1.3 maintenance writes. A full v1.2 ISO is not required.

The absolute locations below are the verified locations in the public v1.2 ISO.
Every build cross-checks those locations against the official v1.2 PPF and exact
v1.2 component bytes before producing output.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import struct
import sys
from pathlib import Path

PPF_HEADER_SIZE = 60
MAX_RECORD = 0xFF
V12_FULL_PPF_SHA256 = "83429a57a8c6bba0bf3134600c9e08e9091ca0a7c366e583745db8209834c328"
V13_FULL_PPF_NAME = "Duel_Masters_Birth_of_Super_Dragon_English_v1.3.ppf"
V13_HOTFIX_NAME = "BOTSD_v1.2_to_v1.3_hotfix.ppf"

# Verified absolute byte positions in the public v1.2 ISO.
V12_FILE_OFFSETS = {
    "SLPM_658.82": 3054401536,  # LBA 1491407
    "SCRPACK.SDA": 1439242240,  # LBA 702755
    "TCHANGE.IMG": 581085184,   # LBA 283733
    "DECK.DAT": 3083677696,     # LBA 1505702 (appended/retargeted localized archive)
}


def sha256_file(path: Path, block: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def load_maintenance():
    path = Path(__file__).resolve().with_name("bosd_v13_maintenance.py")
    spec = importlib.util.spec_from_file_location("bosd_v13_maintenance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def ppf_header(description: str) -> bytes:
    desc = description.encode("ascii", errors="strict")
    if len(desc) > 50:
        raise ValueError("PPF description exceeds 50 ASCII bytes")
    return b"PPF30" + b"\x02" + desc.ljust(50, b"\0") + b"\0\0\0\0"


def read_ppf_header(fp) -> bytes:
    hdr = fp.read(PPF_HEADER_SIZE)
    if len(hdr) != PPF_HEADER_SIZE or hdr[:6] != b"PPF30\x02":
        raise ValueError("not expected PPF 3.0")
    if hdr[56:60] != b"\0\0\0\0":
        raise ValueError("unsupported PPF block-check/undo options")
    return hdr


def iter_ppf_records(path: Path):
    with path.open("rb") as fp:
        read_ppf_header(fp)
        while True:
            h = fp.read(9)
            if not h:
                break
            if len(h) != 9:
                raise ValueError(f"{path}: truncated PPF record header")
            off, size = struct.unpack("<QB", h)
            if size == 0:
                raise ValueError(f"{path}: zero-length PPF record")
            payload = fp.read(size)
            if len(payload) != size:
                raise ValueError(f"{path}: truncated PPF record payload")
            yield off, payload


def verify_ppf(path: Path, require_sorted: bool = True):
    count = payload_bytes = 0
    prev_end = -1
    max_end = 0
    for off, payload in iter_ppf_records(path):
        if require_sorted and off < prev_end:
            raise ValueError(f"{path}: overlapping/out-of-order PPF records")
        prev_end = off + len(payload)
        max_end = max(max_end, prev_end)
        count += 1
        payload_bytes += len(payload)
    return count, payload_bytes, max_end


def write_record(out, offset: int, payload: bytes) -> None:
    if not (1 <= len(payload) <= MAX_RECORD):
        raise ValueError(f"bad PPF record length {len(payload)}")
    out.write(struct.pack("<Q", offset))
    out.write(bytes([len(payload)]))
    out.write(payload)


def diff_records(old: bytes, new: bytes, abs_base: int):
    if len(old) != len(new):
        raise ValueError("v1.3 maintenance component changed size")
    i = 0
    while i < len(old):
        if old[i] == new[i]:
            i += 1
            continue
        start = i
        buf = bytearray()
        while i < len(old) and old[i] != new[i] and len(buf) < MAX_RECORD:
            buf.append(new[i])
            i += 1
        yield abs_base + start, bytes(buf)


def ppf_range(path: Path, start: int, size: int):
    out = bytearray(size)
    mask = bytearray(size)
    end = start + size
    for off, payload in iter_ppf_records(path):
        rend = off + len(payload)
        a = max(start, off)
        b = min(end, rend)
        if a < b:
            out[a-start:b-start] = payload[a-off:b-off]
            mask[a-start:b-start] = b"\x01" * (b-a)
    return bytes(out), bytes(mask)


def validate_public_v12_layout(v12_ppf: Path, v12_components: dict[str, bytes], maintenance):
    """Prove the hard-coded public-v1.2 file positions against the official PPF."""
    # SCRPACK/TCHANGE/DECK are completely covered by the official v1.2 PPF,
    # so their bytes can be independently reconstructed from the patch itself.
    for name in ("SCRPACK.SDA", "TCHANGE.IMG", "DECK.DAT"):
        src = v12_components[name]
        got, mask = ppf_range(v12_ppf, V12_FILE_OFFSETS[name], len(src))
        if not all(mask):
            raise RuntimeError(f"{name}: official v1.2 PPF does not fully cover verified file range")
        if got != src:
            raise RuntimeError(f"{name}: official v1.2 PPF bytes do not match exact v1.2 component")

    # The executable contains many retail-identical areas which the v1.2 PPF does not
    # rewrite. All PPF-covered bytes in the verified executable range must nevertheless
    # agree with the exact public-v1.2 executable, and every v1.3 executable edit must
    # already lie in a PPF-covered block.
    name = "SLPM_658.82"
    src = v12_components[name]
    got, mask = ppf_range(v12_ppf, V12_FILE_OFFSETS[name], len(src))
    covered = sum(mask)
    if covered < 1_000_000:
        raise RuntimeError(f"{name}: unexpectedly little public-v1.2 PPF coverage ({covered} bytes)")
    for i, m in enumerate(mask):
        if m and got[i] != src[i]:
            raise RuntimeError(f"{name}: public-v1.2 PPF mismatch at relative 0x{i:X}")
    target = maintenance.build_component(name, src)
    for i, (a, b) in enumerate(zip(src, target)):
        if a != b and not mask[i]:
            raise RuntimeError(f"{name}: v1.3 edit at relative 0x{i:X} is not covered by v1.2 full PPF")


def build_hotfix(v12_components: dict[str, bytes], v13_components: dict[str, bytes], output: Path):
    records = []
    rows = []
    for name in maintenance_order(v12_components):
        recs = list(diff_records(v12_components[name], v13_components[name], V12_FILE_OFFSETS[name]))
        records.extend(recs)
        rows.append((name, V12_FILE_OFFSETS[name], len(v12_components[name]), len(recs),
                     sum(len(p) for _, p in recs), hashlib.sha256(v13_components[name]).hexdigest()))
    records.sort(key=lambda x: x[0])
    prev_end = -1
    for off, payload in records:
        if off < prev_end:
            raise RuntimeError("generated hotfix records overlap")
        prev_end = off + len(payload)

    with output.open("wb") as out:
        out.write(ppf_header("Duel Masters BOTSD v1.2 to v1.3"))
        for off, payload in records:
            write_record(out, off, payload)
    verify_ppf(output)
    return rows, records


def maintenance_order(components):
    return [n for n in ("SLPM_658.82", "SCRPACK.SDA", "TCHANGE.IMG", "DECK.DAT") if n in components]


def merge_full_ppf(v12_ppf: Path, overlay_records, output: Path):
    # All current v1.3 bytes are within records already written by the public v1.2
    # full PPF. The code still supports gap inserts and verifies canonical ordering.
    overlay = {}
    for off, payload in overlay_records:
        for i, b in enumerate(payload):
            pos = off + i
            if pos in overlay:
                raise RuntimeError("overlay byte overlap")
            overlay[pos] = b

    remaining = overlay
    with v12_ppf.open("rb") as src, output.open("wb") as out:
        read_ppf_header(src)
        out.write(ppf_header("Duel Masters BOTSD English v1.3"))
        while True:
            h = src.read(9)
            if not h:
                break
            off, size = struct.unpack("<QB", h)
            payload = bytearray(src.read(size))
            if len(payload) != size:
                raise RuntimeError("truncated official v1.2 PPF")
            for i in range(size):
                pos = off + i
                if pos in remaining:
                    payload[i] = remaining.pop(pos)
            write_record(out, off, bytes(payload))

        # Not expected for v1.3, but keep the builder general and canonical.
        pairs = sorted(remaining.items())
        i = 0
        while i < len(pairs):
            start = pairs[i][0]
            buf = bytearray([pairs[i][1]])
            i += 1
            while i < len(pairs) and pairs[i][0] == start + len(buf) and len(buf) < MAX_RECORD:
                buf.append(pairs[i][1])
                i += 1
            write_record(out, start, bytes(buf))

    return verify_ppf(output)


def verify_full_component_targets(full_ppf: Path, v13_components: dict[str, bytes]):
    for name in ("SCRPACK.SDA", "TCHANGE.IMG", "DECK.DAT"):
        want = v13_components[name]
        got, mask = ppf_range(full_ppf, V12_FILE_OFFSETS[name], len(want))
        if not all(mask) or got != want:
            raise RuntimeError(f"full v1.3 PPF target verification failed for {name}")

    # For SLPM, verify every full-PPF-covered byte in the file against exact v1.3.
    name = "SLPM_658.82"
    want = v13_components[name]
    got, mask = ppf_range(full_ppf, V12_FILE_OFFSETS[name], len(want))
    for i, m in enumerate(mask):
        if m and got[i] != want[i]:
            raise RuntimeError(f"full v1.3 PPF executable mismatch at relative 0x{i:X}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("v12_dir", type=Path, help="directory containing exact public-v1.2 maintenance components")
    ap.add_argument("v12_full_ppf", type=Path, help="official public v1.2 full PPF")
    ap.add_argument("output_dir", type=Path, help="release output directory")
    a = ap.parse_args()

    maintenance = load_maintenance()
    if sha256_file(a.v12_full_ppf) != V12_FULL_PPF_SHA256:
        raise SystemExit("ERROR: official v1.2 full PPF SHA-256 mismatch")
    verify_ppf(a.v12_full_ppf)

    v12 = {}
    v13 = {}
    for name in maintenance_order(maintenance.V12_HASHES):
        p = a.v12_dir / name
        if not p.is_file():
            ap.error(f"missing public-v1.2 component: {p}")
        raw = p.read_bytes()
        if len(raw) != maintenance.SIZES[name]:
            raise SystemExit(f"ERROR: {name} size mismatch")
        got = hashlib.sha256(raw).hexdigest()
        if got != maintenance.V12_HASHES[name]:
            raise SystemExit(f"ERROR: {name} public-v1.2 SHA-256 mismatch: {got}")
        v12[name] = raw
        v13[name] = maintenance.build_component(name, raw)

    validate_public_v12_layout(a.v12_full_ppf, v12, maintenance)

    outdir = a.output_dir.expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    hotfix = outdir / V13_HOTFIX_NAME
    full = outdir / V13_FULL_PPF_NAME

    rows, overlay = build_hotfix(v12, v13, hotfix)
    full_stats = merge_full_ppf(a.v12_full_ppf, overlay, full)
    hotfix_stats = verify_ppf(hotfix)
    verify_full_component_targets(full, v13)

    # Strong property for this release: all v1.3 edits landed inside blocks already
    # emitted by v1.2, so the full PPF record/payload footprint is unchanged.
    v12_stats = verify_ppf(a.v12_full_ppf)
    if full_stats != v12_stats or full.stat().st_size != a.v12_full_ppf.stat().st_size:
        raise RuntimeError("unexpected v1.3 full-PPF footprint change")

    full_sha = sha256_file(full)
    hotfix_sha = sha256_file(hotfix)
    lines = [
        "Duel Masters: Birth of the Super Dragon — English v1.3 release hashes",
        "",
        f"Official v1.2 full PPF SHA-256: {V12_FULL_PPF_SHA256}",
        "",
        f"{V13_FULL_PPF_NAME}",
        f"  size: {full.stat().st_size}",
        f"  SHA-256: {full_sha}",
        f"  records: {full_stats[0]}",
        f"  payload bytes: {full_stats[1]}",
        "",
        f"{V13_HOTFIX_NAME}",
        f"  size: {hotfix.stat().st_size}",
        f"  SHA-256: {hotfix_sha}",
        f"  records: {hotfix_stats[0]}",
        f"  payload bytes: {hotfix_stats[1]}",
        "",
        "Verified public-v1.2 ISO locations / v1.3 components:",
    ]
    for name, off, size, recs, changed, out_hash in rows:
        lines.append(
            f"  {name}: ISO_offset=0x{off:X} LBA={off//2048} size={size} "
            f"hotfix_records={recs} changed_bytes={changed} v1.3_sha256={out_hash}"
        )
    lines += [
        "",
        "Verification:",
        "  official v1.2 PPF hash/structure=PASS",
        "  v1.2 component hashes=PASS",
        "  verified public-v1.2 file locations=PASS",
        "  SCRPACK/TCHANGE/DECK reconstructed from v1.2 PPF byte-for-byte=PASS",
        "  v1.3 full PPF target component verification=PASS",
        "  v1.3 hotfix records sorted/non-overlapping=PASS",
        "  full v1.3 PPF footprint equals official v1.2 PPF footprint=PASS",
        "  RESULT=PASS",
    ]
    report = "\n".join(lines) + "\n"
    (outdir / "RELEASE_HASHES_v1.3.txt").write_text(report, encoding="utf-8")
    print(report, end="")


if __name__ == "__main__":
    main()
