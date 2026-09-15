#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, hashlib

EXPECTED_INPUT_SHA='a11e878177370c1c53a0a5e2777f90cc418ea5a3dea28f490f1e9bbab27af77a'

def sha(b): return hashlib.sha256(b).hexdigest()
def cstr(b): return b.split(b'\0',1)[0].decode('cp932',errors='strict')

def patch_slot(out, src, off, size, english, label, allowed, lines):
    enc=english.encode('cp932')
    if len(enc)+1>size: raise RuntimeError(f'{label}: {len(enc)} bytes will not fit {size-1}')
    old=cstr(src[off:off+size])
    out[off:off+size]=enc+b'\0'*(size-len(enc))
    allowed.append((off,off+size))
    lines.append(f'{label} @0x{off:X} size=0x{size:X}: {old!r} -> {english!r} ({len(enc)}/{size-1})')

# Fixed 0x10 civilization-combination slots. Water/Nature was already localized in UI68.
CIV=[
 (0x446488,'Light & Water'),
 (0x446498,'Light & Dark'),
 (0x4464A8,'Light & Fire'),
 (0x4464B8,'Light & Nature'),
 (0x4464C8,'Water & Dark'),
 (0x4464D8,'Water & Fire'),
 (0x4464F8,'Dark & Fire'),
 (0x446508,'Dark & Nature'),
 (0x446518,'Fire & Nature'),
]
# Independent pack-name/description table. Slots are bounded by the next original string.
PACK=[
 (0x4465A0,0x18,'DM-01\nBase Set'),
 (0x4465B8,0x48,'DM-02\nEvo-Crushinators of Doom'),
 (0x446600,0x48,'DM-03\nRampage of the\nSuper Warriors'),
 (0x446648,0x50,'DM-04\nShadowclash of\nBlinding Night'),
 (0x446698,0x48,'DM-05\nSurvivors of the\nMegapocalypse'),
 (0x446790,0x48,'DM-09\nFatal Brood of\nInfinite Ruin'),
 (0x4467D8,0x38,'DM-10\nShockwaves of the\nShattered Rainbow'),
 (0x446810,0x48,'DM-11\nBlastosplosion of\nGigantic Rage'),
 (0x446858,0x48,'DM-12\nThrash of the Hybrid\nMegacreatures'),
]
# The three neighboring local/offline Matsumoto trade strings were already English in UI68.
# Only this fixed slot was missed. Network trading strings at 0x4489xx are intentionally untouched.
OFFLINE_TRADE=[
 (0x4435E8,0x48,'Not enough cards!\nYou need at least 10 cards to trade.'),
]
# Memory-card save metadata. This sits in fh_mc beside BISLPM-65882 / PS2D and
# is player-visible in the PS2 memory-card browser, not network/debug text.
SAVE_METADATA=[
 (0x502A78,0x44,'Duel Masters: Birth of the Super Dragon'),
]

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('input_elf'); ap.add_argument('output_elf'); ap.add_argument('--report')
 a=ap.parse_args(); src=Path(a.input_elf).read_bytes()
 if sha(src)!=EXPECTED_INPUT_SHA: raise SystemExit(f'ERROR: expected UI81 ELF {EXPECTED_INPUT_SHA}, got {sha(src)}')
 out=bytearray(src); allowed=[]
 lines=['UI82 OFFLINE EXECUTABLE RESIDUAL PATCH',f'input_sha256={sha(src)}']
 # Guard adjacent already-good local trade strings and intentionally excluded network block.
 guards={
  0x4435C0:'Choose cards to trade.',0x443630:'Trade these cards?',0x443658:'End trading?',
  0x4464E8:'Wtr/Nat',0x4466E0:'DM-06\nStomp-A-Trons of\nInvincible Wrath',
  0x446710:'DM-07\nThundercharge of\nUltra Destruction',0x446750:'DM-08\nEpic Dragons of\nHyperchaos',
  0x4468A0:'Promo Cards',0x4489F0:'\nPlease wait.'
 }
 for off,want in guards.items():
  got=cstr(src[off:off+160])
  if got!=want: raise RuntimeError(f'guard 0x{off:X}: {got!r} != {want!r}')
 for off,text in CIV: patch_slot(out,src,off,0x10,text,f'civilization {text}',allowed,lines)
 for off,size,text in PACK: patch_slot(out,src,off,size,text,f'booster {text.split(chr(10))[0]}',allowed,lines)
 for off,size,text in OFFLINE_TRADE: patch_slot(out,src,off,size,text,'offline trade minimum-card warning',allowed,lines)
 for off,size,text in SAVE_METADATA: patch_slot(out,src,off,size,text,'memory-card save title',allowed,lines)
 diffs=[i for i,(x,y) in enumerate(zip(src,out)) if x!=y]
 outside=[i for i in diffs if not any(s<=i<e for s,e in allowed)]
 if outside: raise RuntimeError(f'changed outside approved slots: {outside[:16]}')
 # Verify network trade block is byte-identical as the user explicitly excluded obsolete online content.
 if bytes(out[0x4489F0:0x448B10])!=src[0x4489F0:0x448B10]: raise RuntimeError('network trade block changed')
 # Verify all output C strings.
 for off,text in CIV:
  if cstr(bytes(out[off:off+0x10]))!=text: raise RuntimeError(f'civilization verify failed {hex(off)}')
 for off,size,text in PACK:
  if cstr(bytes(out[off:off+size]))!=text: raise RuntimeError(f'pack verify failed {hex(off)}')
 for off,size,text in OFFLINE_TRADE:
  if cstr(bytes(out[off:off+size]))!=text: raise RuntimeError('trade verify failed')
 for off,size,text in SAVE_METADATA:
  if cstr(bytes(out[off:off+size]))!=text: raise RuntimeError('save metadata verify failed')
 blob=bytes(out); Path(a.output_elf).write_bytes(blob)
 lines += [f'output_sha256={sha(blob)}',f'differing_bytes={len(diffs)}',
           'containment=PASS (9 civilization slots + 9 pack-description slots + 1 offline trade slot + 1 save-metadata slot only)',
           'online/network trade block 0x4489F0-0x448B10=UNCHANGED', 'RESULT=PASS']
 text='\n'.join(lines)+'\n'; print(text,end='')
 if a.report: Path(a.report).write_text(text,encoding='utf-8')
if __name__=='__main__': main()
