#!/usr/bin/env python3
"""UI81 data-only keyboard initial-mode patch.

The game's software-keyboard constructor copies the persistent mode byte at
GP+0x23B (virtual address 0x62852B, file offset 0x52952B) into object+0x54.
Retail initializes that file-backed .sdata byte to 0 (KANA).  The soft-key
handler table proves the four primary pages select modes 0, 3, 6/9, and 12;
the third handler toggles modes 6/9 and corresponds to the on-screen A/ABC
page.  Initializing this one byte to 6 therefore opens the existing English
lowercase page first, without rearranging or altering any keyboard page.
"""
from pathlib import Path
import argparse, hashlib
EXPECTED_INPUT_SHA='5a0b96714f3c19d0fa6a2691f6d005ea44841305a0ad4ff3be36341d65abb682'
MODE_VA=0x62852B
VA_DELTA=0xFF000
MODE_OFF=MODE_VA-VA_DELTA
OLD=0
NEW=6

def sha(b): return hashlib.sha256(b).hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('input_elf');ap.add_argument('output_elf');ap.add_argument('--report');a=ap.parse_args()
 src=Path(a.input_elf).read_bytes(); got=sha(src)
 if got!=EXPECTED_INPUT_SHA: raise SystemExit(f'ERROR: expected UI80 executable {EXPECTED_INPUT_SHA}, got {got}')
 if src[MODE_OFF]!=OLD: raise SystemExit(f'ERROR: initial keyboard mode byte at {MODE_OFF:#x} is {src[MODE_OFF]}, expected {OLD}')
 out=bytearray(src);out[MODE_OFF]=NEW;blob=bytes(out)
 diffs=[i for i,(x,y) in enumerate(zip(src,blob)) if x!=y]
 if diffs!=[MODE_OFF]: raise RuntimeError(f'unexpected diff offsets: {diffs[:16]}')
 Path(a.output_elf).write_bytes(blob)
 lines=[
  'UI81 KEYBOARD DEFAULT-ENGLISH PATCH',
  f'input_sha256={got}',f'output_sha256={sha(blob)}',f'file_size={len(blob)}',
  f'mode_virtual_address={MODE_VA:#x}',f'mode_file_offset={MODE_OFF:#x}',
  f'initial_mode={OLD}->6 (A/ABC lowercase page)',
  'patch_bytes=1','keyboard_pages=UNCHANGED','keyboard_mode_switching_code=UNCHANGED',
  'RESULT=PASS']
 text='\n'.join(lines)+'\n';print(text,end='')
 if a.report: Path(a.report).write_text(text,encoding='utf-8')
if __name__=='__main__':main()
