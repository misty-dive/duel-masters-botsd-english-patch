#!/usr/bin/env python3
"""Apply the prebuilt UI82 second-card-sprite chunks to a verified UI76 compiled UNPACK."""
from pathlib import Path
import argparse,csv,hashlib,io,struct,zipfile
RETAIL_SHA='179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece';SIZE=151525376
FIRST=2037;LAST=2713

def sha(b):return hashlib.sha256(b).hexdigest()
def outer(b):
 if b[:4]!=b'sda\0':raise ValueError('not SDA')
 decl,n=struct.unpack_from('<II',b,4)
 if decl!=len(b):raise ValueError('declared size mismatch')
 return list(struct.unpack_from('<'+'I'*n,b,12))
def bounds(offs,i,total):return offs[i],(offs[i+1] if i+1<len(offs) else total)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('ui76_compiled',type=Path);ap.add_argument('patch_zip',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--report',type=Path);a=ap.parse_args()
 P=a.ui76_compiled.read_bytes()
 if len(P)!=SIZE:raise SystemExit(f'ERROR: input size {len(P)} != {SIZE}')
 offs=outer(P)
 with zipfile.ZipFile(a.patch_zip) as z:
  rows=list(csv.DictReader(io.TextIOWrapper(z.open('manifest.csv'),encoding='utf-8')))
  if len(rows)!=677:raise SystemExit(f'ERROR: patch manifest rows={len(rows)}')
  out=bytearray(P); touched=[]
  for r in rows:
   idx=int(r['chunk']);
   if idx<FIRST or idx>LAST:raise SystemExit(f'ERROR: bad patch chunk {idx}')
   s,e=bounds(offs,idx,len(P));src=P[s:e]
   # UI76 verifier guarantees these are retail-identical. Hash gating here proves it independently.
   if sha(src)!=r['retail_sha256']:raise SystemExit(f'ERROR: chunk {idx} input is not exact retail preimage')
   q=z.read(f'chunks/{idx:04d}.bin')
   if len(q)!=e-s or sha(q)!=r['patched_sha256']:raise SystemExit(f'ERROR: patch payload failed at chunk {idx}')
   out[s:e]=q;touched.append(idx)
 if touched!=list(range(FIRST,LAST+1)):raise SystemExit('ERROR: target chunk sequence incomplete')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(out);Q=a.output.read_bytes()
 # Independent containment relative to input: exact target byte ranges only.
 for i in range(len(offs)):
  s,e=bounds(offs,i,len(P));diff=P[s:e]!=Q[s:e]
  if diff!=(FIRST<=i<=LAST):raise SystemExit(f'ERROR: archive containment mismatch chunk {i}, diff={diff}')
 txt=('UI82 SECOND-SPRITE APPLY: PASS\n'+f'input_sha256={sha(P)}\noutput_sha256={sha(Q)}\n'
      f'outer_size={len(Q)}\nouter_offsets_unchanged=yes\npatched_chunks=677\nchunk_range={FIRST}-{LAST}\n'
      'full_card_layers_677_2036_untouched=yes\nchunks_2714_plus_untouched=yes\nfull_card_reconversion_performed=no\n')
 if a.report:a.report.write_text(txt,encoding='utf-8')
 print(txt,end='')
if __name__=='__main__':main()
