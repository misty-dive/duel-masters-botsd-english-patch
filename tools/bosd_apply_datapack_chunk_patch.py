#!/usr/bin/env python3
from pathlib import Path
import argparse,json,hashlib,struct,zipfile

def sha(x): return hashlib.sha256(x).hexdigest()
def main():
 ap=argparse.ArgumentParser(description='Apply verified BOSD fixed-size DATAPACK chunk patch.')
 ap.add_argument('retail',type=Path);ap.add_argument('patch',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
 b=bytearray(a.retail.read_bytes())
 with zipfile.ZipFile(a.patch) as z:
  m=json.loads(z.read('manifest.json'))
  if m.get('format')!='BOSD_DATAPACK_CHUNK_PATCH_V1': raise SystemExit('ERROR: bad patch format')
  if len(b)!=m['retail_size'] or sha(b)!=m['retail_sha256']: raise SystemExit('ERROR: DATAPACK retail size/SHA-256 mismatch')
  if b[:4]!=b'sda\0': raise SystemExit('ERROR: not SDA')
  size,n=struct.unpack_from('<II',b,4);offs=list(struct.unpack_from('<'+'I'*n,b,12))
  if size!=len(b): raise SystemExit('ERROR: SDA declared size mismatch')
  touched=[]
  for row in m['changed_chunks']:
   i=row['index'];o=offs[i];e=offs[i+1] if i+1<n else size
   if o!=row['offset'] or e-o!=row['size']: raise SystemExit(f'ERROR: chunk {i} layout mismatch')
   old=bytes(b[o:e])
   if sha(old)!=row['retail_sha256']: raise SystemExit(f'ERROR: chunk {i} retail hash mismatch')
   new=z.read(row['file'])
   if len(new)!=e-o or sha(new)!=row['target_sha256']: raise SystemExit(f'ERROR: chunk {i} patch data corrupt')
   b[o:e]=new;touched.append(i)
  if len(b)!=m['target_size'] or sha(b)!=m['target_sha256']: raise SystemExit('ERROR: final DATAPACK hash mismatch')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(b)
 print(f'Patched {len(touched)} DATAPACK chunks: {touched}')
 print('Output SHA-256:',sha(b))
if __name__=='__main__':main()
