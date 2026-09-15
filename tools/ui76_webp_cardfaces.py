#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,mmap,os,shutil,sqlite3,subprocess,sys,time,unicodedata,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed,ProcessPoolExecutor
from pathlib import Path
from PIL import Image
import numpy as np

DB_COMMIT='e10343da98f1a02c33d5b866e3a82ea2968bf16f'
DB_BLOB_SHA1='2f109745d05d194ca9ec76c256455487dda42e02'
DB_URL=f'https://raw.githubusercontent.com/bmenneni/SimpleJavaDmdb/{DB_COMMIT}/duelmasters.db'
IMG_BASE='https://img.duelmasters.us'
COLORS=(224,192,160,144,128,112,96,80,72,64,56,48,40,32)
ALLOWED_SOURCE_CLASSES={'official_webp','community_proxy','project_scanstyle_exception','alternate_art_scanstyle_exception'}

# worker globals
_WF=None; _MM=None; _OFFS=None; _REND=None; _UI=None; _STRONG=None

def sha256_path(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1<<20),b''): h.update(x)
 return h.hexdigest()

def git_blob_sha1(data:bytes):
 return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def norm_name(s:str):
 s=unicodedata.normalize('NFKD',s or '')
 s=''.join(c for c in s if not unicodedata.combining(c)).casefold()
 return ''.join(c for c in s if c.isalnum())

def download(url:str,dst:Path,min_size=1000):
 if dst.exists() and dst.stat().st_size>=min_size:return
 dst.parent.mkdir(parents=True,exist_ok=True)
 tmp=dst.with_suffix(dst.suffix+'.part')
 try: tmp.unlink()
 except FileNotFoundError: pass
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 BOTSD-English-patch/UI76-R4'})
 err=None
 for n in range(3):
  try:
   with urllib.request.urlopen(req,timeout=60) as r,tmp.open('wb') as f: shutil.copyfileobj(r,f)
   if tmp.stat().st_size<min_size: raise RuntimeError('download too small')
   tmp.replace(dst); return
  except Exception as e:
   err=e
   try: tmp.unlink()
   except FileNotFoundError: pass
   time.sleep(1+n)
 cp=subprocess.run(['curl','-fL','--retry','3','--connect-timeout','20','-A','Mozilla/5.0 BOTSD-English-patch/UI76-R4',url,'-o',str(tmp)],capture_output=True,text=True)
 if cp.returncode or not tmp.exists() or tmp.stat().st_size<min_size:
  try: tmp.unlink()
  except FileNotFoundError: pass
  raise RuntimeError(f'download failed {url}: {err}; curl: {cp.stderr.strip()}')
 tmp.replace(dst)

def load_module(path:Path,name:str):
 sp=importlib.util.spec_from_file_location(name,path)
 if not sp or not sp.loader:raise RuntimeError(path)
 m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m

def ensure_db(cache:Path,provided:Path|None,offline:bool,allow_unpinned=False):
 if provided:
  p=provided
 else:
  p=cache/'duelmasters.db'
  if not p.exists():
   if offline: raise RuntimeError(f'offline and database absent: {p}')
   print('Downloading pinned English card database...',flush=True);download(DB_URL,p,100000)
 data=p.read_bytes(); got=git_blob_sha1(data)
 if got!=DB_BLOB_SHA1 and not allow_unpinned: raise RuntimeError(f'database Git blob SHA-1 mismatch: {got} expected {DB_BLOB_SHA1}')
 print(f'English card DB verified: {p} git-blob {got}',flush=True)
 return p

def db_rows(db:Path):
 con=sqlite3.connect(str(db));con.row_factory=sqlite3.Row
 try:
  rows=[dict(r) for r in con.execute('SELECT card_id, card_name, card_set, coll_num FROM CARD ORDER BY card_id')]
 finally:con.close()
 if len(rows)<900: raise RuntimeError(f'English card DB unexpectedly small: {len(rows)}')
 for r in rows:r['card_id']=int(r['card_id'])
 return rows

def choose_candidate(cands,set_label):
 def official(r): return r['card_id']<901 or 9000<r['card_id']<9081
 def promo(r): return 9000<r['card_id']<9081
 if set_label.upper().startswith('DM-'):
  same=[r for r in cands if (r.get('card_set') or '').casefold()==set_label.casefold()]
  if same:return min(same,key=lambda r:r['card_id']),('official_set' if len(same)==1 else 'official_set_multi_lowest')
  off=[r for r in cands if official(r)]
  if off:return min(off,key=lambda r:r['card_id']),'official_set_mismatch'
  if cands:return min(cands,key=lambda r:r['card_id']),'community_set_mismatch'
  return None,'no_db_match'
 pp=[r for r in cands if promo(r)]
 if pp:return min(pp,key=lambda r:r['card_id']),('official_promo' if len(pp)==1 else 'official_promo_multi_lowest')
 off=[r for r in cands if r['card_id']<901]
 if off:return min(off,key=lambda r:r['card_id']),('official_tcg_reprint' if len(off)==1 else 'official_tcg_reprint_lowest')
 if cands:return min(cands,key=lambda r:r['card_id']),'community_english_image'
 return None,'no_db_match'

def build_map(inventory:Path,crosswalk:Path,db:Path):
 inv=list(csv.DictReader(inventory.open(encoding='utf-8-sig')))
 if len(inv)!=677:raise RuntimeError(f'inventory rows {len(inv)}, expected 677')
 cw={int(r['internal_id']):r for r in csv.DictReader(crosswalk.open(encoding='utf-8-sig'))}
 if len(cw)!=673:raise RuntimeError(f'crosswalk rows {len(cw)}, expected 673')
 cards=db_rows(db);by={}
 for c in cards:by.setdefault(norm_name(c['card_name']),[]).append(c)
 out=[]
 for seq,row in enumerate(inv):
  iid=int(row['internal_id']); c=cw[iid]; name=c['official_english_name']; set_label=c['set_label']
  cand,status=choose_candidate(by.get(norm_name(name),[]),set_label)
  m=dict(seq=seq,resource_key=row['resource_key'],canonical_key=row['canonical_key'],internal_id=iid,
         english_name=name,set_label=set_label,collector_label=c['collector_label'],status=status,
         source_class='',source_file='')
  if cand:
   m.update(db_card_id=cand['card_id'],db_name=cand['card_name'],db_set=cand.get('card_set') or '',db_coll_num=cand.get('coll_num') or '',
            source_url=f'{IMG_BASE}/{cand["card_id"]:04d}.webp',source_class=('community_proxy' if status.startswith('community_') else 'official_webp'),source_file=f'images/{cand["card_id"]:04d}.webp')
  else:m.update(db_card_id='',db_name='',db_set='',db_coll_num='',source_url='')
  m['large_chunk']=int(row['large_chunk']);m['small_chunk']=int(row['small_chunk']);out.append(m)
 return out

def load_exception_manifest(exception_dir:Path):
 p=exception_dir/'manifest.csv'
 if not p.is_file(): raise RuntimeError(f'exception manifest missing: {p}')
 rows=list(csv.DictReader(p.open(encoding='utf-8-sig')));out={}
 required={'resource_key','internal_id','english_name','source_class','image_file','image_sha256','provenance'}
 if not rows or not required.issubset(rows[0]): raise RuntimeError(f'exception manifest fields invalid: need {sorted(required)}')
 for r in rows:
  k=r['resource_key'].strip()
  if not k or k in out: raise RuntimeError(f'duplicate/empty exception resource key {k!r}')
  if r['source_class'] not in {'project_scanstyle_exception','alternate_art_scanstyle_exception'}: raise RuntimeError(f'invalid exception source class {k}: {r["source_class"]}')
  img=exception_dir/r['image_file']
  if not img.is_file(): raise RuntimeError(f'exception image missing {k}: {img}')
  got=sha256_path(img)
  if got.lower()!=r['image_sha256'].lower(): raise RuntimeError(f'exception image SHA mismatch {k}: {got} expected {r["image_sha256"]}')
  with Image.open(img) as im:
   if im.size!=(384,512): raise RuntimeError(f'exception image dimensions {k}: {im.size}, expected 384x512')
  out[k]=(r,img)
 return out

def apply_exception_sources(mapping,exception_dir:Path):
 ex=load_exception_manifest(exception_dir)
 unresolved=[m for m in mapping if not m['db_card_id']]
 expected={m['resource_key'] for m in unresolved}
 if set(ex)!=expected:
  raise RuntimeError(f'exception source set mismatch: manifest-only={sorted(set(ex)-expected)} missing={sorted(expected-set(ex))}')
 for m in unresolved:
  r,img=ex[m['resource_key']]
  if int(r['internal_id'])!=int(m['internal_id']) or r['english_name']!=m['english_name']:
   raise RuntimeError(f'exception identity mismatch {m["resource_key"]}: manifest {r["internal_id"]}/{r["english_name"]!r} mapping {m["internal_id"]}/{m["english_name"]!r}')
  m['source_class']=r['source_class'];m['source_file']=r['image_file'];m['source_url']='local://UI76_EXCEPTION_IMAGES/'+r['image_file']
  m['source_sha256']=r['image_sha256'];m['source_size']='384x512'
  m['status']='exact_project_scanstyle_alternate_art' if r['source_class']=='alternate_art_scanstyle_exception' else 'exact_project_scanstyle_exception'
 return ex

def save_mapping(rows,path:Path):
 path.parent.mkdir(parents=True,exist_ok=True)
 fields=['seq','resource_key','canonical_key','internal_id','english_name','set_label','collector_label','status','source_class','db_card_id','db_name','db_set','db_coll_num','source_file','source_url','source_sha256','source_size','source_colors','compression','compressed_headroom','large_chunk','small_chunk']
 with path.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def write_indices_preserve_palette(tga,rgba:Image.Image,region,source_colors:int):
 x0,y0,x1,y1=region;W,H=x1-x0,y1-y0
 src=rgba.convert('RGB').resize((W,H),Image.Resampling.LANCZOS)
 q=src.quantize(colors=source_colors,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE).convert('RGB')
 arr=np.asarray(q,dtype=np.uint8);uniq,inv=np.unique(arr.reshape(-1,3),axis=0,return_inverse=True)
 pal=np.asarray([p[:3] for p in tga.pal],dtype=np.int16);opaque=np.asarray([i for i,p in enumerate(tga.pal) if p[3]>=128],dtype=np.int16)
 if not len(opaque):raise RuntimeError('no opaque palette entries')
 opal=pal[opaque];best=np.empty(len(uniq),dtype=np.uint8);u=uniq.astype(np.int16)
 for a in range(0,len(u),512):
  z=u[a:a+512,None,:]-opal[None,:,:];d=(z.astype(np.int32)**2).sum(axis=2);best[a:a+512]=opaque[np.argmin(d,axis=1)].astype(np.uint8)
 mapped=best[inv].reshape(H,W);idx=np.frombuffer(bytes(tga.idx),dtype=np.uint8).reshape(tga.h,tga.w).copy();idx[y0:y1,x0:x1]=mapped
 rr=[idx[y].tobytes() for y in range(tga.h)]
 if not(tga.desc&0x20):rr.reverse()
 out=bytearray(tga.raw);out[tga.pixoff:tga.pixoff+tga.w*tga.h]=b''.join(rr);return bytes(out)

def _worker_init(base,renderer,archive,strong):
 global _WF,_MM,_OFFS,_REND,_UI,_STRONG
 _REND=load_module(Path(renderer),f'ui76_rend_{os.getpid()}');_UI=load_module(Path(archive),f'ui76_arc_{os.getpid()}');_STRONG=load_module(Path(strong),f'ui76_strong_{os.getpid()}')
 _WF=open(base,'rb');_MM=mmap.mmap(_WF.fileno(),0,access=mmap.ACCESS_READ);_,_OFFS=_REND.parse_outer(_MM)

def _process(task):
 m,srcpath=task;seq=int(m['seq']);li=int(m['large_chunk']);si=int(m['small_chunk'])
 scan=Image.open(srcpath).convert('RGBA');orig_size=f'{scan.width}x{scan.height}'
 lo,le=_OFFS[li],_OFFS[li+1];chunk=bytes(_MM[lo:le]);inner,ds,ro,member,oldss,raw=_REND.archive_member(chunk,_UI);t=_REND.TGA(raw)
 chosen=None;last=None
 for colors in COLORS:
  try:
   newraw=write_indices_preserve_palette(t,scan,(0,0,384,512),colors)
   newchunk,method,headroom,oldstored,newstored,_=_REND.rebuild_inner(chunk,newraw,_UI,_STRONG);chosen=(colors,newraw,newchunk,method,headroom);break
  except Exception as e:last=e
 if chosen is None:raise RuntimeError(f'{m["english_name"]}: no full-face candidate fits fixed allocation: {last}')
 colors,newraw,newchunk,method,headroom=chosen;nt=_REND.TGA(newraw)
 if raw[:t.pixoff]!=newraw[:nt.pixoff] or raw[t.pixoff+t.w*t.h:]!=newraw[nt.pixoff+nt.w*nt.h:]:raise RuntimeError('large metadata/palette changed')
 oldidx=np.asarray(t.idx,dtype=np.uint8).reshape(t.h,t.w);newidx=np.asarray(nt.idx,dtype=np.uint8).reshape(nt.h,nt.w)
 if not np.array_equal(oldidx[:,384:],newidx[:,384:]):raise RuntimeError('large pixels outside 384px card face changed')
 after=nt.image().crop((0,0,384,512));so,se=_OFFS[si],_OFFS[si+1];sraw=bytes(_MM[so:se]);st=_REND.TGA(sraw)
 target=after.resize((128,128),Image.Resampling.BICUBIC);snew=write_indices_preserve_palette(st,target,(0,0,128,128),128)
 if len(snew)!=len(sraw):raise RuntimeError('small size changed')
 nst=_REND.TGA(snew)
 if sraw[:st.pixoff]!=snew[:nst.pixoff] or sraw[st.pixoff+st.w*st.h:]!=snew[nst.pixoff+nst.w*nst.h:]:raise RuntimeError('small metadata/palette changed')
 return seq,newchunk,snew,colors,method,headroom,orig_size

def main():
 ap=argparse.ArgumentParser(description='BOTSD UI76 R4 whole-card English image replacement: 677/677 resources')
 ap.add_argument('base_unpack',type=Path);ap.add_argument('inventory',type=Path);ap.add_argument('crosswalk',type=Path)
 ap.add_argument('renderer_module',type=Path);ap.add_argument('archive_tool',type=Path);ap.add_argument('strong_tool',type=Path)
 ap.add_argument('out_unpack',type=Path);ap.add_argument('qa_dir',type=Path)
 ap.add_argument('--cache-dir',type=Path,required=True);ap.add_argument('--exception-dir',type=Path,required=True)
 ap.add_argument('--db',type=Path);ap.add_argument('--offline',action='store_true');ap.add_argument('--jobs',type=int,default=4);ap.add_argument('--allow-unpinned-db',action='store_true',help=argparse.SUPPRESS)
 a=ap.parse_args();a.qa_dir.mkdir(parents=True,exist_ok=True);a.cache_dir.mkdir(parents=True,exist_ok=True)
 if a.jobs<1:raise SystemExit('ERROR: --jobs must be >=1')
 db=ensure_db(a.cache_dir,a.db,a.offline,a.allow_unpinned_db);mapping=build_map(a.inventory,a.crosswalk,db);exceptions=apply_exception_sources(mapping,a.exception_dir)
 if len(mapping)!=677 or any(m['source_class'] not in ALLOWED_SOURCE_CLASSES for m in mapping):raise RuntimeError('not all 677 resources have an allowed full-card source')
 webrows=[m for m in mapping if m['db_card_id']];exrows=[m for m in mapping if not m['db_card_id']]
 print(f'UI76 image mapping: {len(mapping)}/677 full-card resources',flush=True)
 print(f'  online/public WebP: {len(webrows)}',flush=True);print(f'  packaged exact exceptions: {len(exrows)}',flush=True);print('  UI75 synthetic fallbacks: 0',flush=True)
 # Download one file per unique database image, concurrently.
 srcdir=a.cache_dir/'images';uniq={int(m['db_card_id']):m['source_url'] for m in webrows}
 def get_one(item):
  dbid,url=item;p=srcdir/f'{dbid:04d}.webp'
  if not p.exists():
   if a.offline:raise RuntimeError(f'offline and image absent: {p}')
   download(url,p,1000)
  with Image.open(p) as im:
   if im.width<100 or im.height<100:raise RuntimeError(f'bad image dimensions {p}: {im.size}')
   sz=f'{im.width}x{im.height}'
  return dbid,p,sha256_path(p),sz
 print(f'UI76 online source images: {len(uniq)} unique; download workers 12',flush=True);infos={}
 with ThreadPoolExecutor(max_workers=min(12,max(1,len(uniq)))) as ex:
  fut={ex.submit(get_one,x):x[0] for x in uniq.items()};done=0
  for f in as_completed(fut):
   dbid,p,h,sz=f.result();infos[dbid]=(p,h,sz);done+=1
   if done%50==0 or done==len(uniq):print(f'  sources {done}/{len(uniq)}',flush=True)
 source_paths={}
 for m in webrows:
  p,h,sz=infos[int(m['db_card_id'])];m['source_sha256']=h;m['source_size']=sz;source_paths[int(m['seq'])]=p
 for m in exrows:
  r,p=exceptions[m['resource_key']];source_paths[int(m['seq'])]=p
 save_mapping(mapping,a.qa_dir/'UI76_WEBP_MAPPING.csv')
 # Every resource, including the 22 exceptions, uses the same whole-card conversion path from retail UNPACK.
 rend=load_module(a.renderer_module,'ui76_parent_rend');B=a.base_unpack.read_bytes();decl,offs=rend.parse_outer(B);out=bytearray(B)
 tasks=[(m,str(source_paths[int(m['seq'])])) for m in mapping];results={}
 print(f'UI76 full-card conversion workers: {a.jobs}',flush=True)
 if a.jobs==1:
  _worker_init(str(a.base_unpack),str(a.renderer_module),str(a.archive_tool),str(a.strong_tool));iterator=map(_process,tasks)
  for n,res in enumerate(iterator,1):
   results[res[0]]=res
   if n%50==0 or n==len(tasks):print(f'  converted {n}/{len(tasks)}',flush=True)
 else:
  with ProcessPoolExecutor(max_workers=a.jobs,initializer=_worker_init,initargs=(str(a.base_unpack),str(a.renderer_module),str(a.archive_tool),str(a.strong_tool))) as ex:
   fs=[ex.submit(_process,t) for t in tasks]
   for n,f in enumerate(as_completed(fs),1):
    res=f.result();results[res[0]]=res
    if n%50==0 or n==len(tasks):print(f'  converted {n}/{len(tasks)}',flush=True)
 for m in mapping:
  seq=int(m['seq']);_,lchunk,sraw,colors,method,headroom,sz=results[seq];li=int(m['large_chunk']);si=int(m['small_chunk'])
  out[offs[li]:offs[li+1]]=lchunk;out[offs[si]:offs[si+1]]=sraw;m['source_colors']=colors;m['compression']=method;m['compressed_headroom']=headroom;m['source_size']=sz
 if len(out)!=len(B):raise RuntimeError('outer size changed')
 _,offs2=rend.parse_outer(bytes(out))
 if offs2!=offs:raise RuntimeError('outer offsets changed')
 changed=[i for i in range(len(offs)-1) if B[offs[i]:offs[i+1]]!=bytes(out[offs[i]:offs[i+1]])];expected=sorted([int(m[k]) for m in mapping for k in ('large_chunk','small_chunk')])
 if changed!=expected:raise RuntimeError(f'changed chunks mismatch: got {len(changed)}, expected {len(expected)}; first diff {[(x,y) for x,y in zip(changed,expected) if x!=y][:5]}')
 a.out_unpack.parent.mkdir(parents=True,exist_ok=True);a.out_unpack.write_bytes(out);save_mapping(mapping,a.qa_dir/'UI76_WEBP_MAPPING.csv')
 classes={};statuses={}
 for m in mapping:classes[m['source_class']]=classes.get(m['source_class'],0)+1;statuses[m['status']]=statuses.get(m['status'],0)+1
 minhead=min(int(m['compressed_headroom']) for m in mapping);mincolors=min(int(m['source_colors']) for m in mapping)
 txt=['UI76 FULL-CARD VERIFICATION: PASS',f'base_sha256 {sha256_path(a.base_unpack)}',f'output_sha256 {sha256_path(a.out_unpack)}',f'outer_size {len(out)}','outer_offsets_unchanged yes',f'full_card_resources {len(mapping)}',f'online_webp_resources {len(webrows)}',f'packaged_exception_resources {len(exrows)}','ui75_synthetic_fallbacks 0',f'changed_outer_chunks {len(changed)}',f'min_compressed_headroom {minhead}',f'min_source_colors {mincolors}','whole_card_face_only x=0..383 yes','large_and_small_metadata_palettes_preserved yes','source_class_counts:']+[f'  {k}: {v}' for k,v in sorted(classes.items())]+['status_counts:']+[f'  {k}: {v}' for k,v in sorted(statuses.items())]
 (a.qa_dir/'UI76_WEBP_VERIFICATION.txt').write_text('\n'.join(txt)+'\n',encoding='utf-8');print('\n'.join(txt),flush=True)

if __name__=='__main__':main()
