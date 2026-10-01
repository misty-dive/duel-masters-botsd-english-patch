#!/usr/bin/env python3
"""Build the UI82 fixed-chunk patch for UNPACK chunks 2037..2713.

These are the second 677-card 128x128 cutout sprites.  The expensive UI76
full-card layers are deliberately not touched.  Each replacement is generated
from the exact retail chunk and edits only the measured title band.
"""
from __future__ import annotations
from pathlib import Path
import argparse,csv,hashlib,importlib.util,io,json,math,struct,sys,zipfile
from collections import Counter
from PIL import Image,ImageDraw
import numpy as np

RETAIL_SHA='179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece'
SIZE=151525376
FIRST=2037
COUNT=677
TITLE_BAND=(0,2,128,15)
Y0,Y1=3,14

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def load_cf(root:Path):
    p=root/'development_tools/bosd_unpack_cardfaces_ui75_portable.py'
    sp=importlib.util.spec_from_file_location('bosd_cf_ui82',p)
    if not sp or not sp.loader:raise RuntimeError(p)
    m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m);return m

def load_fontbase(path:Path):
    sp=importlib.util.spec_from_file_location('bosd_fontbase_ui82',path)
    if not sp or not sp.loader:raise RuntimeError(path)
    m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m);return m

def outer(b:bytes):
    if b[:4]!=b'sda\0':raise ValueError('not SDA')
    decl,n=struct.unpack_from('<II',b,4)
    if decl!=len(b):raise ValueError((decl,len(b)))
    return list(struct.unpack_from('<'+'I'*n,b,12))

def chunk(b:bytes,offs:list[int],i:int)->bytes:
    e=offs[i+1] if i+1<len(offs) else len(b)
    return b[offs[i]:e]

def find_title_ramp(t):
    """Identify the retail Japanese title anti-alias ramp from palette/usage.

    Most sprites reserve a civilization-coloured alpha ramp almost exclusively
    for the name band.  One known card (seq 623) shares more of the black ramp
    with artwork, so a conservative top-dominant fallback handles it.
    """
    arr=np.array(t.idx,dtype=np.uint8).reshape(t.h,t.w)
    top=Counter(arr[Y0:Y1].ravel().tolist()); lower=Counter(arr[Y1:].ravel().tolist())
    ids=[i for i,p in enumerate(t.pal) if top[i] and p[3]>=5]
    parent={i:i for i in ids}
    def F(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]];a=parent[a]
        return a
    def U(a,b):
        a,b=F(a),F(b)
        if a!=b:parent[b]=a
    for z,i in enumerate(ids):
        ri=t.pal[i][:3]
        for j in ids[z+1:]:
            rj=t.pal[j][:3]
            if max(abs(ri[k]-rj[k]) for k in range(3))<=6:U(i,j)
    groups={}
    for i in ids:groups.setdefault(F(i),[]).append(i)
    candidates=[]
    for g in groups.values():
        alphas={t.pal[i][3] for i in g}
        exclusive=[i for i in g if lower[i]==0]
        excpix=sum(top[i] for i in exclusive); alltop=sum(top[i] for i in g); low=sum(lower[i] for i in g)
        if len(alphas)>=5 and len(exclusive)>=4 and excpix>=60:
            score=excpix*len(alphas)/(1+math.sqrt(low))
            candidates.append((score,g,set(exclusive),'exclusive'))
    if not candidates:
        # Conservative fallback for a palette where the title ramp is also used
        # sparsely by lower artwork.  Seeds must still be strongly top-dominant.
        for g in groups.values():
            alphas={t.pal[i][3] for i in g};alltop=sum(top[i] for i in g);low=sum(lower[i] for i in g)
            seeds={i for i in g if top[i]>=max(5,lower[i]*4)}
            seedpix=sum(top[i] for i in seeds)
            if len(alphas)>=5 and len(seeds)>=3 and seedpix>=60 and alltop>=100:
                score=seedpix*len(alphas)/(1+math.sqrt(low))
                candidates.append((score,g,seeds,'top-dominant-fallback'))
    if not candidates:raise RuntimeError('unable to identify title palette ramp')
    candidates.sort(reverse=True,key=lambda z:z[0]);score,g,seeds,method=candidates[0]
    G=set(g)
    cm=np.isin(arr[Y0:Y1],list(G)); seed=np.isin(arr[Y0:Y1],list(seeds))
    # Keep only candidate-colour components connected to reliable title-ramp seeds.
    seen=np.zeros_like(cm,bool); stack=[tuple(x) for x in np.argwhere(seed)]
    for y,x in stack:seen[y,x]=True
    q=0
    while q<len(stack):
        y,x=stack[q];q+=1
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                if dx==0 and dy==0:continue
                yy,xx=y+dy,x+dx
                if 0<=yy<seen.shape[0] and 0<=xx<seen.shape[1] and cm[yy,xx] and not seen[yy,xx]:
                    seen[yy,xx]=True;stack.append((yy,xx))
    ys,xs=np.where(seen)
    if len(xs)<100:raise RuntimeError(f'title mask implausibly small: {len(xs)}')
    # Highest-alpha palette entry represents the intended title colour.
    colour_idx=max(g,key=lambda i:t.pal[i][3]); colour=t.pal[colour_idx][:3]
    return seen,colour,method,(int(xs.min()),Y0+int(ys.min()),int(xs.max()+1),Y0+int(ys.max()+1)),len(xs),g

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('retail_unpack',type=Path)
    ap.add_argument('project_root',type=Path,help='changes/checkpoint root containing inventory, font and development_tools')
    ap.add_argument('output_zip',type=Path)
    ap.add_argument('--qa-dir',type=Path)
    a=ap.parse_args()
    B=a.retail_unpack.read_bytes()
    if len(B)!=SIZE or sha(B)!=RETAIL_SHA:raise SystemExit('ERROR: retail UNPACK preflight failed')
    offs=outer(B)
    if len(offs)!=2809:raise SystemExit(f'ERROR: unexpected UNPACK chunk count {len(offs)}')
    rows=list(csv.DictReader((a.project_root/'unpack_card_inventory.csv').open(encoding='utf-8-sig',newline='')))
    if len(rows)!=COUNT:raise SystemExit(f'ERROR: inventory rows {len(rows)} != {COUNT}')
    cf=load_cf(a.project_root); fb=load_fontbase(a.project_root/'bosd_font_ue_patch.py')
    font=cf.GameFont(a.project_root/'FONTLINK_UI81_EN.PAC',fb)
    rec=[]; replacements={}; samples={0,2,14,36,100,200,300,400,500,600,623,676}
    qa=a.qa_dir
    if qa:qa.mkdir(parents=True,exist_ok=True)
    for seq,row in enumerate(rows):
        idx=FIRST+seq; raw=chunk(B,offs,idx)
        if len(raw)!=18432:raise RuntimeError(f'chunk {idx}: size {len(raw)} != 18432')
        t=cf.TGA(raw)
        if (t.w,t.h,t.dep)!=(128,128,32):raise RuntimeError(f'chunk {idx}: unexpected TGA {(t.w,t.h,t.dep)}')
        titlemask,colour,method,maskbbox,maskpix,ramp=find_title_ramp(t)
        orig=t.image(); arr=np.array(orig)
        band=arr[Y0:Y1]
        # Remove exactly the detected Japanese title-ramp component(s), not a rectangular strip.
        band[titlemask]=[*colour,0];arr[Y0:Y1]=band
        im=Image.fromarray(arr,'RGBA')
        text=cf.ascii_text(row['english_name'])
        m=font.text_mask(text,spacing=1)
        target_h=10; w=max(1,round(m.width*target_h/max(1,m.height)))
        m=m.resize((w,target_h),Image.Resampling.LANCZOS)
        if m.width>120:m=m.resize((120,target_h),Image.Resampling.LANCZOS)
        x=4+(120-m.width)//2;y=Y0+(Y1-Y0-m.height)//2
        lay=Image.new('RGBA',m.size,(*colour,0));lay.putalpha(m);im.alpha_composite(lay,(x,y))
        out=t.update(im,[TITLE_BAND])
        if len(out)!=len(raw):raise RuntimeError(f'chunk {idx}: size changed')
        nt=cf.TGA(out)
        # TGA metadata and palette are immutable; only the index raster may change.
        if raw[:t.pixoff]!=out[:nt.pixoff] or raw[t.pixoff+t.w*t.h:]!=out[nt.pixoff+nt.w*nt.h:]:
            raise RuntimeError(f'chunk {idx}: non-pixel TGA bytes changed')
        changed=[]
        for p,(u,v) in enumerate(zip(t.idx,nt.idx)):
            if u!=v:
                yy=p//128;xx=p%128;changed.append((xx,yy))
                if not (TITLE_BAND[0]<=xx<TITLE_BAND[2] and TITLE_BAND[1]<=yy<TITLE_BAND[3]):
                    raise RuntimeError(f'chunk {idx}: changed pixel outside title band at {(xx,yy)}')
        if not changed:raise RuntimeError(f'chunk {idx}: no changes')
        replacements[idx]=out
        cb=(min(x for x,y in changed),min(y for x,y in changed),max(x for x,y in changed)+1,max(y for x,y in changed)+1)
        rec.append(dict(seq=seq,chunk=idx,english_name=text,retail_sha256=sha(raw),patched_sha256=sha(out),
                        size=len(out),title_detection=method,title_colour='#%02x%02x%02x'%colour,
                        source_title_mask_pixels=maskpix,source_title_mask_bbox='%d,%d,%d,%d'%maskbbox,
                        changed_pixels=len(changed),changed_bbox='%d,%d,%d,%d'%cb,
                        rendered_mask_width=m.width,rendered_mask_height=m.height))
        if qa and seq in samples:
            # Side-by-side 4x samples for human audit.
            def comp(z):
                bg=Image.new('RGBA',z.size,'white');bg.alpha_composite(z);return bg.convert('RGB').resize((512,512),Image.Resampling.NEAREST)
            before=comp(orig);after=comp(nt.image()); canvas=Image.new('RGB',(1024,540),'white');canvas.paste(before,(0,28));canvas.paste(after,(512,28))
            d=ImageDraw.Draw(canvas);d.text((8,6),f'chunk {idx} BEFORE',fill='black');d.text((520,6),f'chunk {idx} AFTER: {text}',fill='black')
            canvas.save(qa/f'chunk_{idx}_before_after.png')
    # Build deterministic ZIP with full fixed-size replacement chunks and CSV manifest.
    a.output_zip.parent.mkdir(parents=True,exist_ok=True)
    sio=io.StringIO(); fields=list(rec[0].keys());w=csv.DictWriter(sio,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rec)
    meta={
      'format':'BOSD UI82 second 677-card sprite title patch','retail_unpack_sha256':RETAIL_SHA,
      'first_chunk':FIRST,'last_chunk':FIRST+COUNT-1,'chunk_count':COUNT,'title_band':TITLE_BAND,
      'full_card_reconversion_performed':False,'source':'exact retail chunks 2037..2713',
    }
    with zipfile.ZipFile(a.output_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.writestr('manifest.csv',sio.getvalue())
        z.writestr('metadata.json',json.dumps(meta,indent=2,sort_keys=True)+'\n')
        for idx in sorted(replacements):z.writestr(f'chunks/{idx:04d}.bin',replacements[idx])
    print(f'UI82 SECOND-SPRITE PATCH: PASS')
    print(f'chunks={len(replacements)} range={FIRST}-{FIRST+COUNT-1}')
    print(f'zip={a.output_zip}')
    print(f'zip_sha256={sha(a.output_zip.read_bytes())}')
    print(f'fallback_title_detectors={sum(r["title_detection"]!="exclusive" for r in rec)}')
    print(f'changed_pixels_total={sum(int(r["changed_pixels"]) for r in rec)}')
    print('full_card_reconversion_performed=no')

if __name__=='__main__':main()
