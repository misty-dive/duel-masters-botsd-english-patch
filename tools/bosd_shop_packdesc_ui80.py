#!/usr/bin/env python3
"""UI80 targeted English shop booster-description patch.

Patches only the eight fixed description fields in the booster-shop table.  The
R7 embedded-English/card-text executable must already have been produced.  Codes,
record tail integers, all runtime code, CardText getters, and every byte outside
the eight 0x58-byte description slots are preserved exactly.
"""
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, struct

EXPECTED_INPUT_SHA = 'fbb871f7c6326f4a56d507e8ca4c971c884d0cccc3ed824f0b3f8e4ac240adec'
TABLE_OFF = 0x4FDFF8
STRIDE = 0x68
DESC_OFF = 0x08
DESC_LEN = 0x58
RECORDS = [
    ('01-05', 'Legend Pack'),
    ('DM-06', 'Stomp-A-Trons of Invincible Wrath'),
    ('DM-07', 'Thundercharge of Ultra Destruction'),
    ('DM-08', 'Epic Dragons of Hyperchaos'),
    ('DM-09', 'Fatal Brood of Infinite Ruin'),
    ('DM-10', 'Shockwaves of the Shattered Rainbow'),
    ('DM-11', 'Blastosplosion of Gigantic Rage'),
    ('DM-12', 'Thrash of the Hybrid Megacreatures'),
]

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def read_cstr(b: bytes) -> str:
    return b.split(b'\0', 1)[0].decode('cp932', errors='strict')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input_elf')
    ap.add_argument('output_elf')
    ap.add_argument('--report')
    a = ap.parse_args()

    src = Path(a.input_elf).read_bytes()
    if sha(src) != EXPECTED_INPUT_SHA:
        raise SystemExit(f'ERROR: expected R7 executable {EXPECTED_INPUT_SHA}, got {sha(src)}')
    out = bytearray(src)
    slots = []
    lines = ['UI80 TARGETED SHOP PACK DESCRIPTION PATCH', f'input_sha256={sha(src)}']
    before_codes = []
    before_tails = []
    for i, (code, english) in enumerate(RECORDS):
        ro = TABLE_OFF + i * STRIDE
        got_code = read_cstr(src[ro:ro+8])
        if got_code != code:
            raise RuntimeError(f'record {i}: code {got_code!r} != {code!r}')
        before_codes.append(src[ro:ro+8])
        before_tails.append(src[ro+0x60:ro+0x68])
        old = read_cstr(src[ro+DESC_OFF:ro+DESC_OFF+DESC_LEN])
        enc = english.encode('cp932', errors='strict')
        if len(enc) + 1 > DESC_LEN:
            raise RuntimeError(f'{code}: English description too long: {len(enc)} bytes')
        so = ro + DESC_OFF
        out[so:so+DESC_LEN] = enc + b'\0' * (DESC_LEN-len(enc))
        slots.append((so, so+DESC_LEN))
        lines.append(f'{code}: {old} -> {english} ({len(enc)}/{DESC_LEN-1} bytes)')

    # Exact containment: changes may exist only in the eight description fields.
    diffs = [i for i,(x,y) in enumerate(zip(src,out)) if x != y]
    outside = [i for i in diffs if not any(s <= i < e for s,e in slots)]
    if outside:
        raise RuntimeError(f'bytes changed outside description slots: {outside[:16]}')

    # Verify codes/tails and English strings after patch.
    for i,(code,english) in enumerate(RECORDS):
        ro = TABLE_OFF + i * STRIDE
        if bytes(out[ro:ro+8]) != before_codes[i]:
            raise RuntimeError(f'{code}: code field changed')
        if bytes(out[ro+0x60:ro+0x68]) != before_tails[i]:
            raise RuntimeError(f'{code}: tail integers changed')
        got = read_cstr(bytes(out[ro+DESC_OFF:ro+DESC_OFF+DESC_LEN]))
        if got != english:
            raise RuntimeError(f'{code}: verify {got!r} != {english!r}')

    blob = bytes(out)
    Path(a.output_elf).write_bytes(blob)
    lines += [f'output_sha256={sha(blob)}', f'file_size={len(blob)}', f'differing_bytes={len(diffs)}',
              'containment=PASS (only eight 0x58-byte shop-description fields)',
              'runtime_code=UNCHANGED from R7', 'RESULT=PASS']
    text='\n'.join(lines)+'\n'
    print(text,end='')
    if a.report:
        Path(a.report).write_text(text, encoding='utf-8')

if __name__ == '__main__':
    main()
