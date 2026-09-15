#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, sys
from PIL import Image, ImageFilter, ImageChops

WAIT_SHA='0a66aa328feb850fe29bb8eed96bad92e8cb27b0212f633f4d2563a49a42f552'
TITLE_SHA='03b0f6e3988902b9181213c7dfa168afda40364de46ea349ee0a67a96c442c81'
TITLE_MEMBER='TITLE_SRC_TITLE_01_TGA'

def sha(b): return hashlib.sha256(b).hexdigest()

def fit_mask(font,text,maxw,maxh):
    m=font.text_mask(text,spacing=1)
    s=min(1.0,maxw/m.width,maxh/m.height)
    if s<0.999:
        m=m.resize((max(1,round(m.width*s)),max(1,round(m.height*s))),Image.Resampling.LANCZOS)
    return m

def draw_outlined(base, box, font, text, maxh, center=True, outline=1):
    x0,y0,x1,y1=box
    m=fit_mask(font,text,(x1-x0)-4,min(maxh,(y1-y0)-2))
    if center: x=x0+(x1-x0-m.width)//2
    else: x=x0+2
    y=y0+(y1-y0-m.height)//2
    if outline:
        om=m.filter(ImageFilter.MaxFilter(outline*2+1))
        lay=Image.new('RGBA',om.size,(0,0,0,255)); lay.putalpha(om)
        base.alpha_composite(lay,(x,y))
    lay=Image.new('RGBA',m.size,(241,241,241,255)); lay.putalpha(m)
    base.alpha_composite(lay,(x,y))
    return (x,y,x+m.width,y+m.height)

def changed_bbox(a,b):
    d=ImageChops.difference(a,b)
    return d.getbbox()

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--wait-in',type=Path,required=True);ap.add_argument('--wait-out',type=Path,required=True)
 ap.add_argument('--title-in',type=Path,required=True);ap.add_argument('--title-out',type=Path,required=True)
 ap.add_argument('--fontlink',type=Path,required=True);ap.add_argument('--tools-dir',type=Path,required=True)
 ap.add_argument('--report',type=Path);ap.add_argument('--preview-dir',type=Path)
 a=ap.parse_args()
 sys.path.insert(0,str(a.tools_dir)); sys.path.insert(0,str(a.tools_dir.parent))
 from bosd_unpack_cardfaces_ui75_portable import TGA,GameFont
 import bosd_font_ue_patch as fontbase
 from bosd_ui_archive_tool_v1 import parse_archive,rebuild_archive
 font=GameFont(a.fontlink,fontbase)
 lines=['UI82 WAIT + TITLE TARGETED STATIC PATCH']
 # WAIT: the Japanese line occupies the top strip only; spinner begins below it.
 wr=a.wait_in.read_bytes()
 if sha(wr)!=WAIT_SHA: raise SystemExit(f'WAIT source hash mismatch: {sha(wr)}')
 wt=TGA(wr); wb=wt.image(); wi=wb.copy(); wait_box=(0,0,256,28)
 wi.paste((0,0,0,0),wait_box)
 placed=draw_outlined(wi,(2,1,180,27),font,'Please wait...',22,center=False,outline=0)
 wout=wt.update(wi,[wait_box]); a.wait_out.write_bytes(wout)
 wchk=TGA(wout).image()
 if ImageChops.difference(wb,wchk).getbbox() is None: raise RuntimeError('WAIT did not change')
 # pixel containment: decoded pixels outside top strip must be identical
 import numpy as np
 aa=np.asarray(wb); bb=np.asarray(wchk)
 mask=np.any(aa!=bb,axis=2); mask[:28,:]=False
 if mask.any(): raise RuntimeError('WAIT changed pixels outside y=0..27')
 lines += [f'WAIT input_sha256={sha(wr)}',f'WAIT output_sha256={sha(wout)}',f'WAIT target_box={wait_box}',f'WAIT english_bbox={placed}', 'WAIT containment=PASS']
 # TITLE: start from accepted UI55-English title archive, not retail.
 tr=a.title_in.read_bytes()
 if sha(tr)!=TITLE_SHA: raise SystemExit(f'TITLE source hash mismatch: {sha(tr)}')
 arc=parse_archive(a.title_in,decompress=True)
 m=next((m for m in arc.members if m.name==TITLE_MEMBER),None)
 if m is None: raise RuntimeError('title member missing')
 tt=TGA(m.raw); tb=tt.image(); ti=tb.copy()
 # Measured duplicate Japanese branding occupies x=282..407, y=74..96 over transparent background.
 logo_box=(281,72,409,98); ti.paste((0,0,0,0),logo_box)
 logo_text=None  # remove redundant Japanese brand overlay
 # Preserve the original copyright symbol at far left; replace only キッズステーション.
 copy_box=(0,246,137,265); ti.paste((0,0,0,0),copy_box)
 copy_text=None  # remove duplicate Japanese rights line
 tout_tga=tt.update(ti,[logo_box,copy_box])
 a.title_out.parent.mkdir(parents=True,exist_ok=True)
 rebuild_archive(arc,{TITLE_MEMBER:tout_tga},a.title_out,pad_to=len(tr))
 tor=a.title_out.read_bytes()
 if len(tor)!=len(tr): raise RuntimeError('TITLE archive allocation changed')
 chk=parse_archive(a.title_out,decompress=True)
 # unchanged decompressed members must be byte-identical
 for old,new in zip(arc.members,chk.members):
  if old.name==TITLE_MEMBER: continue
  if old.raw!=new.raw: raise RuntimeError(f'non-target TITLE member changed: {old.name}')
 tc=TGA(next(x for x in chk.members if x.name==TITLE_MEMBER).raw).image()
 ta=np.asarray(tb); tz=np.asarray(tc); mm=np.any(ta!=tz,axis=2)
 allowed=np.zeros(mm.shape,dtype=bool);allowed[logo_box[1]:logo_box[3],logo_box[0]:logo_box[2]]=True;allowed[copy_box[1]:copy_box[3],copy_box[0]:copy_box[2]]=True
 if np.any(mm & ~allowed): raise RuntimeError('TITLE changed pixels outside declared boxes')
 lines += [f'TITLE input_sha256={sha(tr)}',f'TITLE output_sha256={sha(tor)}',f'TITLE logo_box={logo_box}','TITLE logo_text=repeated Japanese brand overlay removed (main logo already English)',f'TITLE copyright_box={copy_box}','TITLE copyright_text=duplicate Japanese rights line removed (primary line already English)', 'TITLE non-target-members=BYTE-IDENTICAL', 'TITLE pixel containment=PASS', 'RESULT=PASS']
 if a.preview_dir:
  a.preview_dir.mkdir(parents=True,exist_ok=True)
  # Composite against gray so transparency is visible in QA.
  for name,im in [('WAIT_UI82',wchk),('TITLE_UI82',tc)]:
   bg=Image.new('RGBA',im.size,(80,80,80,255));bg.alpha_composite(im);bg.convert('RGB').save(a.preview_dir/(name+'.png'))
 text='\n'.join(lines)+'\n';print(text,end='')
 if a.report:a.report.write_text(text,encoding='utf-8')
if __name__=='__main__': main()
