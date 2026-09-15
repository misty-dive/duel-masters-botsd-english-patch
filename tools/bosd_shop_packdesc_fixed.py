#!/usr/bin/env python3
"""Corrected shop booster-description patch.

The booster-shop record is 0x68 bytes:
  +0x00  8-byte code
  +0x08  0x50-byte description area
  +0x58  uint32 price (150 DP in retail)
  +0x5C  uint32 image ID
  +0x60  uint32 pack index
  +0x64  uint32 pack index

The earlier UI80 script incorrectly treated +0x08..+0x5F as text and zeroed
the price/image fields. This version preserves all metadata.
"""
from __future__ import annotations
from pathlib import Path
import argparse, hashlib

TABLE_OFF = 0x4FDFF8
STRIDE = 0x68
DESC_OFF = 0x08
DESC_LEN = 0x50

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

def cstr(b: bytes) -> str:
    return b.split(b'\0', 1)[0].decode('cp932', errors='strict')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input_elf')
    ap.add_argument('output_elf')
    a = ap.parse_args()

    src = Path(a.input_elf).read_bytes()
    out = bytearray(src)

    for i, (code, english) in enumerate(RECORDS):
        ro = TABLE_OFF + i * STRIDE
        if cstr(src[ro:ro+8]) != code:
            raise RuntimeError(f'record {i}: unexpected code')
        metadata = src[ro+0x58:ro+0x68]
        enc = english.encode('cp932')
        if len(enc) + 1 > DESC_LEN:
            raise RuntimeError(f'{code}: description too long')
        out[ro+DESC_OFF:ro+DESC_OFF+DESC_LEN] = enc + b'\0' * (DESC_LEN-len(enc))
        if bytes(out[ro+0x58:ro+0x68]) != metadata:
            raise RuntimeError(f'{code}: metadata changed')

    Path(a.output_elf).write_bytes(out)
    print(f'input_sha256={sha(src)}')
    print(f'output_sha256={sha(bytes(out))}')
    print('PASS: descriptions changed; price/image/pack metadata preserved')

if __name__ == '__main__':
    main()
