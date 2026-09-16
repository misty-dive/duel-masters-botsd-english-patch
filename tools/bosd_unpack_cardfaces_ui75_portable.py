#!/usr/bin/env python3
"""UI75 UNPACK.IMG card-face localizer for Duel Masters: Birth of the Super Dragon.

Targets the 677 printed card resources in IMG/UNPACK.IMG:
  * 677 large CARDL one-member packed TGA archives (512x512 texture, card at x=0..383)
  * 677 corresponding raw 128x128 printed-card textures, in the same order

The 673 live cards map one-to-one to the verified project crosswalk. Four extra printed resources
are verified alternate print/art resources and map to the same canonical English card data.

Only the Japanese-bearing printed-text regions are edited on the large card face. The small-card
text regions are regenerated from the accepted translated large face using the retail-proven
384x512 -> 128x128 bicubic transform, while all pixels outside the scaled text regions remain
retail-identical.
"""
from __future__ import annotations
from pathlib import Path
import argparse,csv,struct,re,sys,unicodedata,importlib.util,hashlib,math
from PIL import Image,ImageFilter
import numpy as np

TITLE=(82,16,362,65)
TYPE=(52,315,354,343)
PANEL=(44,344,356,454)
LARGE_BOXES=[TITLE,TYPE,PANEL]
# Retail small faces are the 384x512 large card face resampled to 128x128. Expand by 1-2 px for filter bleed.
SMALL_BOXES=[(25,3,123,18),(15,77,120,88),(13,85,120,116)]


def load_module(path:Path,name:str):
    sp=importlib.util.spec_from_file_location(name,path)
    if not sp or not sp.loader:
        raise RuntimeError(path)
    m=importlib.util.module_from_spec(sp)
    sys.modules[name]=m
    sp.loader.exec_module(m)
    return m


def sha256(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

class TGA:
    def __init__(self,raw:bytes):
        self.raw=raw
        self.idl,self.cm,self.it=raw[:3]
        self.first,self.nn=struct.unpack_from('<HH',raw,3)
        self.dep=raw[7]
        self.x0,self.y0,self.w,self.h,self.pd,self.desc=struct.unpack_from('<HHHHBB',raw,8)
        if self.cm!=1 or self.it!=1 or self.first!=0 or self.pd!=8 or self.dep not in (24,32):
            raise ValueError((self.cm,self.it,self.first,self.nn,self.dep,self.w,self.h,self.pd,self.desc))
        self.step=self.dep//8
        self.po=18+self.idl
        self.pal=[]
        for k in range(self.nn):
            q=raw[self.po+k*self.step:self.po+(k+1)*self.step]
            if self.dep==32:
                B,G,R,A=q
            else:B,G,R=q;A=255
            self.pal.append((R,G,B,A))
        self.pixoff=self.po+self.nn*self.step
        pix=raw[self.pixoff:self.pixoff+self.w*self.h]
        rr=[pix[y*self.w:(y+1)*self.w] for y in range(self.h)]
        if not(self.desc&0x20):
            rr.reverse()
        self.idx=bytearray(b''.join(rr))
    def image(self)->Image.Image:
        dat=bytearray()
        for z in self.idx:
            dat.extend(self.pal[z])
        return Image.frombytes('RGBA',(self.w,self.h),bytes(dat))
    def update(self,im:Image.Image,boxes:list[tuple[int,int,int,int]])->bytes:
        if im.size!=(self.w,self.h):
            raise ValueError('size mismatch')
        idx=np.frombuffer(bytes(self.idx),dtype=np.uint8).reshape(self.h,self.w).copy()
        rgba=np.asarray(im.convert('RGBA'),dtype=np.uint8)
        pal=np.asarray(self.pal,dtype=np.int16)
        for x0,y0,x1,y1 in boxes:
            x0=max(0,x0)
            y0=max(0,y0)
            x1=min(self.w,x1)
            y1=min(self.h,y1)
            crop=rgba[y0:y1,x0:x1].reshape(-1,4)
            uniq,inv=np.unique(crop,axis=0,return_inverse=True)
            u=uniq.astype(np.int16)
            # Chunk unique colors to bound temporary memory. Distance metric matches the project's TGA editors.
            best=np.empty(len(u),dtype=np.uint8)
            for a in range(0,len(u),1024):
                q=u[a:a+1024,None,:]-pal[None,:,:]
                d=(q[:,:,:3].astype(np.int32)**2).sum(axis=2)+2*(q[:,:,3].astype(np.int32)**2)
                best[a:a+1024]=np.argmin(d,axis=1).astype(np.uint8)
            idx[y0:y1,x0:x1]=best[inv].reshape(y1-y0,x1-x0)
        rr=[idx[y].tobytes() for y in range(self.h)]
        if not(self.desc&0x20):
            rr.reverse()
        out=bytearray(self.raw)
        out[self.pixoff:self.pixoff+self.w*self.h]=b''.join(rr)
        return bytes(out)



class GameFont:
    """Half-width ASCII renderer from the game's FONTLINK.PAC; no external desktop font."""
    def __init__(self,fontlink:Path,fontbase):
        raw=fontlink.read_bytes()
        if raw[:4]!=b"DPAC":
            raise ValueError("FONTLINK not DPAC")
        count,align=struct.unpack_from("<II",raw,4)
        self.pages={}
        p=12
        for _ in range(count):
            name=raw[p:p+16].split(b"\0",1)[0].decode("ascii")
            size,ofs=struct.unpack_from("<II",raw,p+16)
            p+=24
            if name.startswith("half") and name.endswith(".lz"):
                d=fontbase.font_decompress(raw[ofs:ofs+size])
                w,h,g,c=fontbase.geom(d)
                if (w,h,g)==(12,24,144):
                    self.pages[name]=d
        if not self.pages:
            raise ValueError("no half-width font pages found")
    def glyph(self,ch:str)->Image.Image:
        code=ord(ch)
        if code<0x20 or code>0x7f:
            raise ValueError(f"non-ASCII UI glyph {ch!r}")
        n=code-0x20
        page=n//16
        idx=n%16
        name=f"half{page:04d}.lz"
        d=self.pages[name]
        raw=d[8+idx*144:8+(idx+1)*144]
        vals=[]
        for z in raw:
            vals.extend((z>>4,z&15))
        im=Image.new("L",(12,24))
        im.putdata([v*17 for v in vals])
        return im
    def text_mask(self,text:str,spacing=1)->Image.Image:
        glyphs=[self.glyph(c) for c in text]
        if not glyphs:
            return Image.new("L",(1,1),0)
        parts=[]
        for g in glyphs:
            bb=g.getbbox()
            parts.append(Image.new("L",(4,24),0) if bb is None else g.crop((bb[0],0,bb[2],24)))
        w=sum(p.width for p in parts)+spacing*max(0,len(parts)-1)
        out=Image.new("L",(max(1,w),24),0)
        x=0
        for p in parts:
            out.paste(p,(x,0))
            x+=p.width+spacing
        bb=out.getbbox()
        return out.crop(bb) if bb else Image.new("L",(1,1),0)

def apply_master_overrides(rows:list[dict],master_path:Path|None):
    if not master_path:
        return
    byid={}
    with master_path.open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            role=r.get("roles","").strip()
            m=re.match(r"^(\d+):",r.get("cards", ""))
            if role in {"name","rules","race","flavor"} and m:
                byid.setdefault(int(m.group(1)),{})[role]=r.get("translation","")
    missing=[]
    for row in rows:
        cid=int(row["internal_id"])
        d=byid.get(cid,{})
        if "name" in d and d["name"]:
            row["english_name"]=d["name"]
        if "rules" in d:
            row["rules"]=d["rules"]
        if "race" in d:
            row["race"]=d["race"]
        if "flavor" in d:
            row["flavor"]=d["flavor"]
        if not row.get("english_name") or (row.get("card_type")!="SPELL" and not row.get("race")):
            missing.append((cid,row.get("resource_key")))
    if missing:
        raise ValueError(f"master override left required card text missing: {missing[:10]}")

def ascii_text(s:str)->str:
    s=s.replace('■','*').replace('Ü','U')
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii')
    return ' '.join(s.split())


def lowfreq(im:Image.Image,box,small):
    c=im.crop(box)
    sw=min(small[0],c.width)
    sh=min(small[1],c.height)
    return c.resize((sw,sh),Image.Resampling.BOX).resize(c.size,Image.Resampling.BILINEAR)

class Renderer:
    def __init__(self,font):
        self.font=font
    def width(self,s):
        return self.font.text_mask(s,spacing=1).width
    def wrap(self,p,maxw):
        words=p.split()
        out=[]
        cur=''
        for w in words:
            cand=w if not cur else cur+' '+w
            if cur and self.width(cand)>maxw:
                out.append(cur)
                cur=w
            else:cur=cand
        if cur:
            out.append(cur)
        return out
    def layout(self,text,box,maxs,mins):
        paras=[]
        for p in text.replace('\r','').split('\n'):
            p=ascii_text(p)
            if p:
                paras.append(p)
        if not paras:
            return [],1.0,0
        W=box[2]-box[0]-4
        H=box[3]-box[1]-4
        s=maxs
        while s>=mins-1e-9:
            lines=[]
            maxbw=max(1,int(W/s))
            for pi,p in enumerate(paras):
                lines.extend(self.wrap(p,maxbw))
                if pi+1<len(paras):
                    lines.append('')
            lh=max(4,round(24*s))
            if len(lines)*lh<=H:
                return lines,s,lh
            s-=.01
        raise ValueError(f'text does not fit box {box}: {text[:80]!r}')
    def one(self,im,box,text,maxs,bold=False):
        text=ascii_text(text)
        m=self.font.text_mask(text,spacing=1)
        W=box[2]-box[0]-4
        H=box[3]-box[1]-4
        s=min(maxs,W/max(1,m.width),H/max(1,m.height))
        m=m.resize((max(1,round(m.width*s)),max(1,round(m.height*s))),Image.Resampling.LANCZOS)
        x=box[0]+(box[2]-box[0]-m.width)//2
        y=box[1]+(box[3]-box[1]-m.height)//2
        if bold:
            m=m.filter(ImageFilter.MaxFilter(3))
        lay=Image.new('RGBA',m.size,(8,8,8,0))
        lay.putalpha(m)
        im.alpha_composite(lay,(x,y))
        return s,m.size
    def wrapped(self,im,box,text,maxs,mins):
        lines,s,lh=self.layout(text,box,maxs,mins)
        y=box[1]+2
        for line in lines:
            if line:
                m=self.font.text_mask(line,spacing=1)
                m=m.resize((max(1,round(m.width*s)),max(1,round(m.height*s))),Image.Resampling.LANCZOS)
                lay=Image.new('RGBA',m.size,(8,8,8,0))
                lay.putalpha(m)
                im.alpha_composite(lay,(box[0]+2,y))
            y+=lh
        return s,len(lines),lh
    def edit(self,raw:bytes,row:dict):
        t=TGA(raw)
        if (t.w,t.h,t.dep)!=(512,512,32):
            raise ValueError((t.w,t.h,t.dep))
        orig=t.image()
        im=orig.copy()
        im.paste(lowfreq(orig,TITLE,(18,3)),TITLE)
        im.paste(lowfreq(orig,TYPE,(18,2)),TYPE)
        im.paste(lowfreq(orig,PANEL,(18,7)),PANEL)
        title_sc,_=self.one(im,TITLE,row['english_name'],.92,True)
        label=row['card_type'] if row['card_type']=='SPELL' else row['card_type']+' / '+row['race']
        type_sc,_=self.one(im,TYPE,label,.52,False)
        rules=(row['rules'] or '').replace('■','\n*')
        fl=row['flavor'] or ''
        if fl:
            rsc,rl,_=self.wrapped(im,(PANEL[0],PANEL[1],PANEL[2],421),rules,.48,.18)
            fsc,fln,_=self.wrapped(im,(PANEL[0],422,PANEL[2],PANEL[3]),fl,.40,.16)
        else:
            rsc,rl,_=self.wrapped(im,PANEL,rules,.50,.18)
            fsc=1.0
            fln=0
        out=t.update(im,LARGE_BOXES)
        # exact containment on large indices
        nt=TGA(out)
        outside=0
        changed=0
        def inside(x,y):
            return any(a<=x<c and b<=y<d for a,b,c,d in LARGE_BOXES)
        for p,(a,b) in enumerate(zip(t.idx,nt.idx)):
            if a!=b:
                changed+=1
                x=p%t.w
                y=p//t.w
                if not inside(x,y):
                    outside+=1
        if outside:
            raise RuntimeError(f'large changes outside declared boxes: {outside}')
        return out,im,(title_sc,type_sc,rsc,rl,fsc,fln,changed)


def parse_outer(b:bytes):
    if b[:4]!=b'sda\0':
        raise ValueError('not SDA')
    decl,n=struct.unpack_from('<II',b,4)
    if decl!=len(b):
        raise ValueError((decl,len(b)))
    return decl,list(struct.unpack_from('<'+'I'*n,b,12))


def archive_member(chunk:bytes,ui):
    inner=struct.unpack_from('<I',chunk,0)[0]
    if chunk[4:8]!=b'ALL ' or chunk[12:16]!=b'HDR ':
        raise ValueError('not inner archive')
    hs=struct.unpack_from('<I',chunk,8)[0]
    ds=8+hs
    rec_off=20
    rec=chunk[rec_off:rec_off+0x114]
    if rec[:4]!=b'FILE':
        raise ValueError('no FILE')
    name=rec[4:260].split(b'\0',1)[0].decode('ascii')
    dr,ss,c,ns=struct.unpack_from('<IIII',rec,260)
    if (hs,dr,c,ns)!=(504,0,1,0):
        raise ValueError((hs,dr,c,ns))
    raw=ui.decode_member_blob(chunk[ds:ds+ss],c)
    return inner,ds,rec_off,name,ss,raw


def rebuild_inner(chunk:bytes,newraw:bytes,ui,strong):
    inner,ds,ro,name,oldss,oldraw=archive_member(chunk,ui)
    blob=ui.encode_member_blob(newraw,1)
    method='greedy'
    if ds+len(blob)>inner:
        comp=strong.compress(newraw)
        ui.lzss_decompress(comp,len(newraw))
        blob=struct.pack('<I',len(newraw))+comp
        method='strong'
    if ds+len(blob)>inner:
        raise ValueError(f'compressed member does not fit inner allocation: {ds+len(blob)} > {inner}')
    out=bytearray(chunk)
    out[:inner]=b'\0'*inner
    # restore header verbatim then mutable size field
    out[:ds]=chunk[:ds]
    struct.pack_into('<I',out,ro+264,len(blob))
    out[ds:ds+len(blob)]=blob
    # declared inner size remains retail; bytes after inner in outer chunk remain retail (normally padding)
    got=ui.decode_member_blob(bytes(out[ds:ds+len(blob)]),1)
    if got!=newraw:
        raise RuntimeError('inner roundtrip')
    # ensure outside inner untouched
    if bytes(out[inner:])!=chunk[inner:]:
        raise RuntimeError('outer slack changed')
    return bytes(out),method,inner-ds-len(blob),oldss,len(blob),name


def patch_small(raw:bytes,translated_large:Image.Image):
    t=TGA(raw)
    if (t.w,t.h,t.dep)!=(128,128,32):
        raise ValueError((t.w,t.h,t.dep))
    target=translated_large.crop((0,0,384,512)).resize((128,128),Image.Resampling.BICUBIC)
    out=t.update(target,SMALL_BOXES)
    nt=TGA(out)
    def inside(x,y):
        return any(a<=x<c and b<=y<d for a,b,c,d in SMALL_BOXES)
    changed=outside=0
    for p,(a,b) in enumerate(zip(t.idx,nt.idx)):
        if a!=b:
            changed+=1
            x=p%128
            y=p//128
            if not inside(x,y):
                outside+=1
    if outside:
        raise RuntimeError(f'small changes outside boxes {outside}')
    return out,changed


def main():
    """Run the command-line patch/verification workflow."""
    ap=argparse.ArgumentParser()
    ap.add_argument('unpack',type=Path)
    ap.add_argument('inventory',type=Path)
    ap.add_argument('fontlink',type=Path)
    ap.add_argument('archive_tool',type=Path)
    ap.add_argument('font_tool',type=Path)
    ap.add_argument('strong_tool',type=Path)
    ap.add_argument('output',type=Path)
    ap.add_argument('--report',type=Path)
    ap.add_argument('--preview-dir',type=Path)
    ap.add_argument('--master',type=Path,help='final flavor-complete master CSV; overrides name/rules/race/flavor by internal card id')
    ap.add_argument('--start',type=int,default=0)
    ap.add_argument('--end',type=int,default=677)
    a=ap.parse_args()
    ui=load_module(a.archive_tool,'ui75_archive')
    fb=load_module(a.font_tool,'ui75_fontbase')
    strong=load_module(a.strong_tool,'ui75_strong')
    font=GameFont(a.fontlink,fb)
    rend=Renderer(font)
    B=a.unpack.read_bytes()
    decl,offs=parse_outer(B)
    rows=list(csv.DictReader(a.inventory.open(encoding='utf-8')))
    if len(rows)!=677:
        raise ValueError(len(rows))
    apply_master_overrides(rows,a.master)
    out=bytearray(B)
    report=[]
    pre=a.preview_dir
    if pre:
        pre.mkdir(parents=True,exist_ok=True)
    for seq,row in enumerate(rows):
        if seq<a.start or seq>=a.end:
            continue
        li=int(row['large_chunk'])
        si=int(row['small_chunk'])
        if li!=677+seq or si!=1360+seq:
            raise ValueError((seq,li,si))
        lo,le=offs[li],offs[li+1]
        chunk=B[lo:le]
        inner,ds,ro,name,oldss,raw=archive_member(chunk,ui)
        edited,preview,met=rend.edit(raw,row)
        # UI75 verifier/build semantic fix: thumbnails must derive from the final
        # palette-quantized large TGA, not the pre-quantization RGBA preview.
        final_large=TGA(edited).image()
        newchunk,method,headroom,oldstored,newstored,name2=rebuild_inner(chunk,edited,ui,strong)
        if len(newchunk)!=len(chunk):
            raise RuntimeError('large chunk size')
        out[lo:le]=newchunk
        so,se=offs[si],offs[si+1]
        sraw=B[so:se]
        snew,schg=patch_small(sraw,final_large)
        if len(snew)!=len(sraw):
            raise RuntimeError('small chunk size')
        out[so:se]=snew
        report.append(dict(seq=seq,resource_key=row['resource_key'],canonical_key=row['canonical_key'],internal_id=row['internal_id'],english_name=row['english_name'],large_chunk=li,small_chunk=si,large_member=name,compression=method,compressed_headroom=headroom,old_stored=oldstored,new_stored=newstored,title_scale=f'{met[0]:.4f}',type_scale=f'{met[1]:.4f}',rules_scale=f'{met[2]:.4f}',rules_lines=met[3],flavor_scale=f'{met[4]:.4f}',flavor_lines=met[5],large_changed_pixels=met[6],small_changed_pixels=schg))
        if pre and seq in {0,5,16,27,34,100,200,300,400,500,600,676}:
            final_large.crop((0,0,384,512)).save(pre/f'{seq:03d}_{row["resource_key"]}.png')
        if seq%50==0:
            print(f'{seq}/677 {row["resource_key"]} {row["english_name"]}',flush=True)
    # outer structure invariant
    if len(out)!=len(B):
        raise RuntimeError('outer size changed')
    d2,o2=parse_outer(bytes(out))
    if offs!=o2:
        raise RuntimeError('SDA offsets changed')
    a.output.write_bytes(out)
    rp=a.report or a.output.with_suffix('.csv')
    with rp.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=report[0].keys())
        w.writeheader()
        w.writerows(report)
    print('wrote',a.output,'sha256',sha256(bytes(out)))
    print('report',rp)
    print('min headroom',min(int(r['compressed_headroom']) for r in report),'strong',sum(r['compression']=='strong' for r in report))
    print('min title',min(float(r['title_scale']) for r in report),'min rules',min(float(r['rules_scale']) for r in report))

if __name__=='__main__':
    main()
