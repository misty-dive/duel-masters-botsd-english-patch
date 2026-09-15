#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,sys
from PIL import Image
import numpy as np

EXPECTED={
 'lobby':'c247dfa6e8f42d321f6f27b20910aaca45d54e4240a1a6ae7df91dbb17d136c6',
 'tour':'da768a8e4fabba737dfe71122aa91cc99b035b26c6500db395145337303ab1f7',
 'deck':'fbd00d4c8944927dd10ec5a51660e1bbddba6a94cecda32e1d1bca618546218c',
}
TARGETS={
 'lobby':'LOBBY_SRC_RK_P01_TGA',
 'tour':'TOUR_SRC_TN_P01_TGA',
 'deck':'DECK_SRC_AD_P07_TGA',
}

def sha(b):return hashlib.sha256(b).hexdigest()
def nearest_alpha_indices(t,rgb):
    vals=[]
    for i,(r,g,b,a) in enumerate(t.pal):
        d=(r-rgb[0])**2+(g-rgb[1])**2+(b-rgb[2])**2
        vals.append((d,i,a))
    md=min(x[0] for x in vals)
    return sorted((a,i) for d,i,a in vals if d==md)
def idx_for_alpha(cands,a):return min(cands,key=lambda z:abs(z[0]-a))[1]
def repack_one(path,out,member_name,newraw,parse,rebuild):
    # Fixed-allocation in-place member replacement: never recompress unrelated members.
    # Use the project's stronger overlap-aware encoder when compression=1 so fixed retail slots remain intact.
    import struct
    from bosd_ui_archive_tool_v1 import lzss_decompress
    from bosd_ui_lzss_strong import compress as strong_compress
    arc=parse(path,decompress=True); old={m.name:m.raw for m in arc.members}; target=next((m for m in arc.members if m.name==member_name),None)
    if target is None:raise RuntimeError(f'{member_name} missing')
    if target.compression == 0:
        blob=newraw
    elif target.compression == 1:
        comp=strong_compress(newraw)
        if lzss_decompress(comp,len(newraw)) != newraw: raise RuntimeError('strong LZSS round-trip failed')
        blob=struct.pack('<I',len(newraw))+comp
    else: raise RuntimeError(f'unsupported compression {target.compression}')
    ordered=arc.members; i=ordered.index(target)
    next_rel=ordered[i+1].data_rel if i+1<len(ordered) else len(arc.raw)-arc.data_start
    alloc=next_rel-target.data_rel
    if len(blob)>alloc:raise RuntimeError(f'{member_name}: compressed {len(blob)} exceeds fixed allocation {alloc}')
    raw=bytearray(arc.raw); start=arc.data_start+target.data_rel
    raw[start:start+alloc]=blob+b'\0'*(alloc-len(blob))
    struct.pack_into('<I',raw,target.record_off+264,len(blob))
    out.write_bytes(bytes(raw))
    if len(raw)!=len(arc.raw):raise RuntimeError('archive size changed')
    chk=parse(out,decompress=True)
    for m in chk.members:
        if m.name!=member_name and m.raw!=old[m.name]:raise RuntimeError(f'non-target changed: {m.name}')
    return old[member_name],next(m.raw for m in chk.members if m.name==member_name)
def containment(TGA,oldraw,newraw,boxes):
    a=np.asarray(TGA(oldraw).image());b=np.asarray(TGA(newraw).image());m=np.any(a!=b,axis=2)
    allow=np.zeros(m.shape,bool)
    for x0,y0,x1,y1 in boxes:allow[y0:y1,x0:x1]=True
    if np.any(m & ~allow):raise RuntimeError('pixel change escaped declared box')
    return int(m.sum())

def main():
 ap=argparse.ArgumentParser();
 for n in ('lobby','tour','deck'):
  ap.add_argument(f'--{n}-in',type=Path,required=True);ap.add_argument(f'--{n}-out',type=Path,required=True)
 ap.add_argument('--tools-dir',type=Path,required=True);ap.add_argument('--report',type=Path);ap.add_argument('--preview-dir',type=Path)
 a=ap.parse_args();sys.path.insert(0,str(a.tools_dir))
 from bosd_ui_archive_tool_v1 import parse_archive,rebuild_archive
 from bosd_unpack_cardfaces_ui75_portable import TGA
 lines=['UI82 TARGETED GRAPHICAL RESIDUAL PATCH']
 for n in ('lobby','tour','deck'):
  p=getattr(a,n+'_in'); got=sha(p.read_bytes())
  if got!=EXPECTED[n]:raise SystemExit(f'{n} input hash mismatch: {got}')
 # LOBBY: replace remaining ランク外 alpha-mask glyph with the already-localized NO RANK label style from the same texture.
 la=parse_archive(a.lobby_in,decompress=True); lm=next(m for m in la.members if m.name==TARGETS['lobby']); lt=TGA(lm.raw)
 rgba=np.asarray(lt.image()); src=rgba[81:93,7:57,:3].astype(np.float32)
 # Derive only the white/gray lettering from the accepted top NO RANK instance (blue background stays excluded).
 lum=src.mean(2); mask=np.clip((lum-75.0)*2.2,0,255).astype(np.uint8)
 mask[mask<35]=0
 maskim=Image.fromarray(mask,'L').resize((60,15),Image.Resampling.LANCZOS)
 li=bytearray(lt.idx); clear=10 # palette index 10 = (247,247,247,0), the native transparent-white glyph background
 lobby_box=(0,303,73,330)
 for y in range(lobby_box[1],lobby_box[3]):
  for x in range(lobby_box[0],lobby_box[2]):li[y*lt.w+x]=clear
 cands=nearest_alpha_indices(lt,(247,247,247)); ma=np.asarray(maskim); ox,oy=5,309
 for yy in range(ma.shape[0]):
  for xx in range(ma.shape[1]):
   av=int(ma[yy,xx]);
   if av:li[(oy+yy)*lt.w+(ox+xx)]=idx_for_alpha(cands,av)
 # serialize changed index plane without palette/layout changes
 rr=[bytes(li[y*lt.w:(y+1)*lt.w]) for y in range(lt.h)]
 if not(lt.desc&0x20):rr.reverse()
 lr=bytearray(lt.raw);lr[lt.pixoff:lt.pixoff+lt.w*lt.h]=b''.join(rr);lnew=bytes(lr)
 old,new=repack_one(a.lobby_in,a.lobby_out,TARGETS['lobby'],lnew,parse_archive,rebuild_archive)
 changed=containment(TGA,old,new,[lobby_box]);lines += [f'LOBBY output_sha256={sha(a.lobby_out.read_bytes())}',f'LOBBY box={lobby_box} changed_pixels={changed}','LOBBY label=NO RANK (style reused from accepted label in same member)']
 # TOUR: replace ウ with C by copying the exact C glyph cell from the A-H row in the same texture.
 ta=parse_archive(a.tour_in,decompress=True);tm=next(m for m in ta.members if m.name==TARGETS['tour']);tt=TGA(tm.raw);ti=bytearray(tt.idx)
 srcbox=(64,2,96,34); dstbox=(100,77,132,109)
 # Python bytes(generator) is not row concatenate; do it explicitly.
 rows=[bytes(ti[y*tt.w+srcbox[0]:y*tt.w+srcbox[2]]) for y in range(srcbox[1],srcbox[3])]
 for j,row in enumerate(rows):ti[(dstbox[1]+j)*tt.w+dstbox[0]:(dstbox[1]+j)*tt.w+dstbox[2]]=row
 rr=[bytes(ti[y*tt.w:(y+1)*tt.w]) for y in range(tt.h)]
 if not(tt.desc&0x20):rr.reverse()
 tr=bytearray(tt.raw);tr[tt.pixoff:tt.pixoff+tt.w*tt.h]=b''.join(rr);tnew=bytes(tr)
 old,new=repack_one(a.tour_in,a.tour_out,TARGETS['tour'],tnew,parse_archive,rebuild_archive)
 changed=containment(TGA,old,new,[dstbox]);lines += [f'TOUR output_sha256={sha(a.tour_out.read_bytes())}',f'TOUR source_C_box={srcbox} target_box={dstbox} changed_pixels={changed}','TOUR label=BLOCK C (exact C glyph reused from same member)']
 # DECK: semantics proven by accepted DC_P03 atlas, which already labels the equivalent state HOF.
 da=parse_archive(a.deck_in,decompress=True);dm={m.name:m for m in da.members};dt=TGA(dm[TARGETS['deck']].raw);src_t=TGA(dm['DECK_SRC_DC_P03_TGA'].raw)
 # Accepted HOF glyph mask is cell x224..255,y96..127; letters specifically x+4..27,y+9..22.
 sim=np.asarray(src_t.image().convert('RGB')); sm=(sim[105:119,228:252].mean(2)>180).astype(np.uint8)*255
 # P07 two states: inactive top and active bottom. Clear only interior, preserve frames.
 di=bytearray(dt.idx); top=(4,79,29,104); bot=(4,107,29,133)
 for box,bg in [(top,81),(bot,37)]:
  for y in range(box[1],box[3]):
   for x in range(box[0],box[2]):di[y*dt.w+x]=bg
 # paste 24x14 HOF centered; foreground palette indices are the original Japanese glyph's dominant light colors.
 for oy,fg in [(85,204),(113,234)]:
  for yy in range(sm.shape[0]):
   for xx in range(sm.shape[1]):
    if sm[yy,xx]:di[(oy+yy)*dt.w+(4+xx)]=fg
 rr=[bytes(di[y*dt.w:(y+1)*dt.w]) for y in range(dt.h)]
 if not(dt.desc&0x20):rr.reverse()
 dr=bytearray(dt.raw);dr[dt.pixoff:dt.pixoff+dt.w*dt.h]=b''.join(rr);dnew=bytes(dr)
 old,new=repack_one(a.deck_in,a.deck_out,TARGETS['deck'],dnew,parse_archive,rebuild_archive)
 changed=containment(TGA,old,new,[top,bot]);lines += [f'DECK output_sha256={sha(a.deck_out.read_bytes())}',f'DECK boxes={top},{bot} changed_pixels={changed}','DECK semantic=HOF (verified against accepted DECK_SRC_DC_P03_TGA HOF cells)','DECK label raster=reused from accepted HOF atlas; frames/non-target icons preserved']
 if a.preview_dir:
  a.preview_dir.mkdir(parents=True,exist_ok=True)
  for p,n,mem in [(a.lobby_out,'LOBBY_UI82',TARGETS['lobby']),(a.tour_out,'TOUR_UI82',TARGETS['tour']),(a.deck_out,'DECK_UI82',TARGETS['deck'])]:
   ar=parse_archive(p,decompress=True);raw=next(m.raw for m in ar.members if m.name==mem);TGA(raw).image().save(a.preview_dir/(n+'.png'));TGA(raw).image().getchannel('A').save(a.preview_dir/(n+'_alpha.png'))
 lines += ['archive_sizes=UNCHANGED','non-target_members=BYTE-IDENTICAL (decompressed)','pixel_containment=PASS','RESULT=PASS']
 text='\n'.join(lines)+'\n';print(text,end='');
 if a.report:a.report.write_text(text,encoding='utf-8')
if __name__=='__main__':main()
