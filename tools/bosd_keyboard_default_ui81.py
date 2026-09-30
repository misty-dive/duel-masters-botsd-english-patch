#!/usr/bin/env python3
"""Historical UI81 keyboard initial-mode patch retained for v1.2 reproducibility.

This tool deliberately reproduces the established v1.2 UI81 build-stage byte:
persistent keyboard mode 0 -> 6 at GP+0x23B / VA 0x62852B / file offset 0x52952B.

Post-v1.2 save-state and runtime QA proved that mode 6 is the *full-width* Latin
path, which is why user-entered deck names such as "Phoenix" were stored as
full-width CP932 Latin characters. The final v1.3 maintenance stage corrects the
public executable from mode 6 -> 9, the half-width Latin path.

Why keep this historical helper unchanged?
The downstream v1.2 build stages have established whole-file hash guards. Keeping
this stage byte-identical preserves reproducibility of the public v1.2 pipeline;
`bosd_v13_maintenance.py` is the canonical final correction for v1.3.

Do not use the mode-6 result as the final v1.3 executable.
"""
from pathlib import Path
import argparse, hashlib

EXPECTED_INPUT_SHA = '5a0b96714f3c19d0fa6a2691f6d005ea44841305a0ad4ff3be36341d65abb682'

MODE_VA = 6456619
VA_DELTA = 1044480
MODE_OFF = MODE_VA - VA_DELTA
OLD = 0
NEW = 6

def sha(b):
    return hashlib.sha256(b).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input_elf')
    ap.add_argument('output_elf')
    ap.add_argument('--report')
    a = ap.parse_args()

    src = Path(a.input_elf).read_bytes()
    got = sha(src)
    if got != EXPECTED_INPUT_SHA:
        raise SystemExit(f'ERROR: expected UI80 executable {EXPECTED_INPUT_SHA}, got {got}')
    if src[MODE_OFF] != OLD:
        raise SystemExit(
            f'ERROR: initial keyboard mode byte at {MODE_OFF:#x} is '
            f'{src[MODE_OFF]}, expected {OLD}'
        )

    out = bytearray(src)
    out[MODE_OFF] = NEW
    blob = bytes(out)
    diffs = [i for i, (x, y) in enumerate(zip(src, blob)) if x != y]
    if diffs != [MODE_OFF]:
        raise RuntimeError(f'unexpected diff offsets: {diffs[:16]}')

    Path(a.output_elf).write_bytes(blob)
    lines = [
        'UI81 HISTORICAL KEYBOARD MODE PATCH',
        f'input_sha256={got}',
        f'output_sha256={sha(blob)}',
        f'file_size={len(blob)}',
        f'mode_virtual_address={MODE_VA:#x}',
        f'mode_file_offset={MODE_OFF:#x}',
        'historical_v12_mode=0->6 (full-width Latin path; retained for v1.2 hash reproducibility)',
        'v13_final_mode=9 (applied later by bosd_v13_maintenance.py)',
        'patch_bytes=1',
        'keyboard_pages=UNCHANGED',
        'keyboard_mode_switching_code=UNCHANGED',
        'RESULT=PASS',
    ]
    text = '\n'.join(lines) + '\n'
    print(text, end='')
    if a.report:
        Path(a.report).write_text(text, encoding='utf-8')

if __name__ == '__main__':
    main()
