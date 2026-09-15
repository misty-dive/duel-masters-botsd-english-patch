#!/usr/bin/env python3
"""Fast verifier for the frozen compiled UI76 677-card UNPACK checkpoint.

This intentionally does not rebuild or re-download cards. It proves that the
candidate archive has the retail outer SDA geometry, differs from retail in
exactly the 677 large + 677 small card chunks listed by the canonical inventory,
and leaves every non-card chunk byte-identical.
"""
from pathlib import Path
import argparse,csv,hashlib,struct
RETAIL_SHA='179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece'
SIZE=151525376

def sha(b):return hashlib.sha256(b).hexdigest()
def outer(b):
 if b[:4]!=b'sda\0':raise SystemExit('ERROR: not SDA')
 decl,n=struct.unpack_from('<II',b,4)
 if decl!=len(b):raise SystemExit(f'ERROR: declared size {decl} != {len(b)}')
 offs=list(struct.unpack_from('<'+'I'*n,b,12))
 if len(offs)!=n:raise SystemExit('ERROR: outer table')
 return offs

def main():
 ap=argparse.ArgumentParser();ap.add_argument('retail',type=Path);ap.add_argument('compiled',type=Path);ap.add_argument('inventory',type=Path);ap.add_argument('--report',type=Path);a=ap.parse_args()
 B=a.retail.read_bytes();P=a.compiled.read_bytes()
 if len(B)!=SIZE or sha(B)!=RETAIL_SHA:raise SystemExit('ERROR: retail UNPACK preflight failed')
 if len(P)!=SIZE:raise SystemExit(f'ERROR: compiled UNPACK size {len(P)} != {SIZE}')
 ob,op=outer(B),outer(P)
 if ob!=op:raise SystemExit('ERROR: outer SDA offsets changed')
 with a.inventory.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 if len(rows)!=677:raise SystemExit(f'ERROR: inventory rows={len(rows)}')
 exp=sorted([int(r[k]) for r in rows for k in ('large_chunk','small_chunk')])
 if len(exp)!=1354 or len(set(exp))!=1354:raise SystemExit('ERROR: expected card chunk set malformed')
 changed=[i for i in range(len(ob)-1) if B[ob[i]:ob[i+1]]!=P[op[i]:op[i+1]]]
 if changed!=exp:
  extra=sorted(set(changed)-set(exp));missing=sorted(set(exp)-set(changed))
  raise SystemExit(f'ERROR: compiled changed chunk set mismatch: changed={len(changed)} extra={extra[:12]} missing={missing[:12]}')
 txt=('UI76 FROZEN 677-CARD CHECKPOINT: PASS\n'
      f'retail_sha256={sha(B)}\ncompiled_sha256={sha(P)}\nouter_size={len(P)}\nouter_chunks={len(ob)-1}\n'
      'outer_offsets_unchanged=yes\nchanged_card_chunks=1354\nnon_card_chunks_byte_identical=yes\n'
      'large_resources=677\nsmall_resources=677\nreconversion_performed=no\n')
 if a.report:a.report.write_text(txt,encoding='utf-8')
 print(txt,end='')
if __name__=='__main__':main()
