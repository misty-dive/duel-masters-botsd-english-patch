#!/usr/bin/env python3
from pathlib import Path
import csv,hashlib,io,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fail(s):raise SystemExit('ERROR: '+s)
# Prebuilt immutable assets.
rows=list(csv.DictReader((ROOT/'UI82_PREBUILT_SHA256.tsv').open(encoding='utf-8-sig'),delimiter='\t'))
if len(rows)!=66:fail(f'prebuilt manifest row count {len(rows)} != 66')
for r in rows:
 p=ROOT/r['path']
 if not p.is_file():fail(f'missing {r["path"]}')
 if sha(p)!=r['sha256']:fail(f'hash mismatch {r["path"]}')
# Hidden DECK text family.
decks=sorted((ROOT/'DECK_TEXT_UI82').glob('*.DAT'))
if len(decks)!=60:fail(f'DECK_TEXT_UI82 count {len(decks)} != 60')
# Second-sprite patch manifest exact range and payload hashes.
with zipfile.ZipFile(ROOT/'UNPACK_UI82_SECOND_NAMES.zip') as z:
 m=list(csv.DictReader(io.TextIOWrapper(z.open('manifest.csv'),encoding='utf-8')))
 if len(m)!=677:fail(f'UNPACK patch rows {len(m)} != 677')
 chunks=[int(r['chunk']) for r in m]
 if chunks!=list(range(2037,2714)):fail('UNPACK patch chunk range/order mismatch')
 for r in m:
  q=z.read(f"chunks/{int(r['chunk']):04d}.bin")
  if hashlib.sha256(q).hexdigest()!=r['patched_sha256']:fail(f'UNPACK payload hash chunk {r["chunk"]}')
# Expanded retail preflight manifest: historical 32 + WAIT + 60 numbered decks = 93.
r=list(csv.DictReader((ROOT/'UI82_RETAIL_EXTRA_SHA256.tsv').open(encoding='utf-8-sig'),delimiter='\t'))
if len(r)!=93 or len({x['basename'].upper() for x in r})!=93:fail('retail preflight manifest count/uniqueness')
if 'WAIT.TGA' not in {x['basename'].upper() for x in r}:fail('WAIT.TGA absent from retail preflight')
# Required integration scripts/docs.
for rel in ['build_ui82.sh','build_ui82_comprehensive_iso.sh','prepare_ui82_card_cache.sh',
            'development_tools/bosd_verify_ui76_frozen_unpack_v2.py','development_tools/bosd_apply_unpack_second_names_ui82.py',
            'development_tools/bosd_verify_ui82_frozen_unpack.py','development_tools/bosd_offline_exec_residuals_ui82.py',
            'UI82_EXHAUSTIVE_AUDIT_REPORT.md','README_CHECKPOINT_UI82.md']:
 if not (ROOT/rel).is_file():fail('missing '+rel)
# Shell syntax.
for sh in ['build_ui82.sh','build_ui82_comprehensive_iso.sh','prepare_ui82_card_cache.sh']:
 if subprocess.run(['bash','-n',str(ROOT/sh)]).returncode:fail('bash syntax '+sh)
print('UI82 PACKAGE STATIC VERIFY: PASS')
print('prebuilt_assets=66')
print('deck_data_files=60')
print('second_sprite_chunks=677 (2037-2713)')
print('retail_preflight_basenames=93')
print('shell_syntax=PASS')
print('full_card_reconversion_path=DISABLED/BYPASSED')
