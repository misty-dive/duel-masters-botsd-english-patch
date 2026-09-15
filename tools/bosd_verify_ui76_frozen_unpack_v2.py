#!/usr/bin/env python3
"""Independent full-range verifier for the frozen UI76 compiled 677-card UNPACK.

Unlike the historical verifier, this checks the final SDA chunk through EOF too.
"""
from pathlib import Path
import argparse,csv,hashlib,struct
RETAIL_SHA='179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece'
SIZE=151525376

def sha(b): return hashlib.sha256(b).hexdigest()
def outer(b):
    if b[:4] != b'sda\0': raise SystemExit('ERROR: not SDA')
    decl,n=struct.unpack_from('<II',b,4)
    if decl != len(b): raise SystemExit(f'ERROR: declared size {decl} != {len(b)}')
    return list(struct.unpack_from('<'+'I'*n,b,12))
def bounds(o,i,total): return o[i], (o[i+1] if i+1 < len(o) else total)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('retail',type=Path);ap.add_argument('compiled',type=Path);ap.add_argument('inventory',type=Path);ap.add_argument('--report',type=Path)
    a=ap.parse_args();R=a.retail.read_bytes();C=a.compiled.read_bytes()
    if len(R)!=SIZE or sha(R)!=RETAIL_SHA: raise SystemExit('ERROR: retail UNPACK preflight failed')
    if len(C)!=SIZE: raise SystemExit(f'ERROR: compiled UNPACK size {len(C)} != {SIZE}')
    ro,co=outer(R),outer(C)
    if ro!=co: raise SystemExit('ERROR: outer SDA offsets changed')
    rows=list(csv.DictReader(a.inventory.open(encoding='utf-8-sig',newline='')))
    if len(rows)!=677: raise SystemExit(f'ERROR: inventory rows={len(rows)}')
    exp=set(int(r[k]) for r in rows for k in ('large_chunk','small_chunk'))
    if len(exp)!=1354: raise SystemExit('ERROR: expected card chunk set malformed')
    changed=set()
    for i in range(len(ro)):
        s,e=bounds(ro,i,len(R))
        if R[s:e]!=C[s:e]: changed.add(i)
    if changed!=exp:
        raise SystemExit(f'ERROR: UI76 changed-set mismatch extra={sorted(changed-exp)[:12]} missing={sorted(exp-changed)[:12]}')
    txt=('UI76 FROZEN 677-CARD CHECKPOINT V2: PASS\n'
         f'retail_sha256={sha(R)}\ncompiled_sha256={sha(C)}\nouter_size={len(C)}\nouter_chunks={len(ro)}\n'
         'outer_offsets_unchanged=yes\nchanged_card_chunks=1354\nnon_card_chunks_byte_identical=yes\n'
         'large_resources=677\nprinted_thumbnail_resources=677\nfinal_chunk_checked_through_eof=yes\nreconversion_performed=no\n')
    if a.report:a.report.write_text(txt,encoding='utf-8')
    print(txt,end='')
if __name__=='__main__': main()
