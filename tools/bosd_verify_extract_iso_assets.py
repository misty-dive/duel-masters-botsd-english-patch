#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,hashlib,importlib.util,sys
ap=argparse.ArgumentParser();ap.add_argument('iso',type=Path);ap.add_argument('hashes',type=Path);ap.add_argument('--extract',action='append',default=[],help='BASENAME=OUTPUT');a=ap.parse_args()
spec=importlib.util.spec_from_file_location('iso_mod',Path(__file__).with_name('bosd_iso_layout_patcher_v2.py'));m=importlib.util.module_from_spec(spec);sys.modules['iso_mod']=m;spec.loader.exec_module(m)
raw=a.iso.read_bytes(); iso=m.Iso9660(raw)
with a.hashes.open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f,delimiter='\t'))
expected={r['basename'].upper():r['sha256'].lower() for r in rows}
for name,h in expected.items():
 e=iso.find_unique_basename(name); data=raw[e.extent*m.SECTOR:e.extent*m.SECTOR+e.size]; got=hashlib.sha256(data).hexdigest()
 if got!=h: raise SystemExit(f'ERROR: {e.path} SHA-256 {got} != expected retail {h}')
 print(f'OK {e.path} {e.size} bytes {got}')
for item in a.extract:
 name,out=item.split('=',1); e=iso.find_unique_basename(name); data=raw[e.extent*m.SECTOR:e.extent*m.SECTOR+e.size]; p=Path(out);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);print('Extracted',e.path,'->',p)
