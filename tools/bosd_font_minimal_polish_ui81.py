#!/usr/bin/env python3
"""UI80 minimal runtime-font polish.

Starts from accepted UI55 FONTLINK and changes exactly two half-width ASCII cells:
  apostrophe 0x27 and lowercase l 0x6C.
No uppercase A-Z or full-width A-Z cells are changed. Targeted static labels are prebuilt separately.
"""
from pathlib import Path
import argparse,hashlib,struct
from PIL import Image
EXPECTED_SHA='e78a5ed905b9ef8c6ec01b67b41ee771b47b0f9e91ecddc9cd8767f7416dac0b'
ENTRY_COUNT=453
ALIGN=0x40

def sha(b):
    return hashlib.sha256(b).hexdigest()
def decompress(blob):
    want=struct.unpack_from('<I',blob,0)[0]
    p=4
    out=bytearray()
    while True:
        t=struct.unpack_from('<H',blob,p)[0]
        p+=2
        if t==0:
            break
        ln=t>>11
        if ln:
            d=t&0x7ff
            if not d or d>len(out):
                raise ValueError('bad backref')
            for _ in range(ln):
                out.append(out[-d])
        else:
            ln=t&0x7ff
            out+=blob[p:p+ln]
            p+=ln
    if len(out)!=want or p!=len(blob):
        raise ValueError('decode mismatch')
    return bytes(out)
def compress(data):
    n=len(data)
    best=[0]*n
    dist=[0]*n
    for pos in range(n):
        maxd=min(0x7ff,pos)
        bl=0
        bd=0
        lim=min(31,n-pos)
        for d in range(1,maxd+1):
            if data[pos]!=data[pos-d]:
                continue
            l=1
            while l<lim and data[pos+l]==data[pos+l-d]:
                l+=1
            if l>bl:
                bl,bd=l,d
                if bl==31:
                    break
        best[pos]=bl
        dist[pos]=bd
    INF=10**9
    dp=[INF]*(n+1)
    choice=[None]*n
    dp[n]=0
    for pos in range(n-1,-1,-1):
        lim=min(0x7ff,n-pos)
        bc=INF
        bk=1
        for ln in range(1,lim+1):
            c=2+ln+dp[pos+ln]
            if c<bc:
                bc,bk=c,ln
        dp[pos]=bc
        choice[pos]=('lit',bk)
        for ln in range(3,best[pos]+1):
            c=2+dp[pos+ln]
            if c<dp[pos]:
                dp[pos]=c
                choice[pos]=('ref',ln,dist[pos])
    out=bytearray(struct.pack('<I',n))
    pos=0
    while pos<n:
        ch=choice[pos]
        if ch[0]=='lit':
            ln=ch[1]
            out.extend(struct.pack('<H',ln))
            out.extend(data[pos:pos+ln])
            pos+=ln
        else:
            _,ln,d=ch
            out.extend(struct.pack('<H',(ln<<11)|d))
            pos+=ln
    out.extend(b'\0\0')
    return bytes(out)
def read_pac(raw):
    if raw[:4]!=b'DPAC':
        raise ValueError('not DPAC')
    count,align=struct.unpack_from('<II',raw,4)
    if (count,align)!=(ENTRY_COUNT,ALIGN):
        raise ValueError((count,align))
    es=[]
    p=12
    for i in range(count):
        name=raw[p:p+16].split(b'\0',1)[0].decode('ascii')
        size,off=struct.unpack_from('<II',raw,p+16)
        es.append(dict(i=i,name=name,size=size,off=off,dir=p,blob=raw[off:off+size]))
        p+=24
    return es
def geom(d):
    w,h,g,r=struct.unpack_from('<HHHH',d,0)
    if r!=0 or g!=w*h//2 or (len(d)-8)%g:
        raise ValueError((w,h,g,r,len(d)))
    return w,h,g,(len(d)-8)//g
def unpack4(raw):
    a=[]
    for z in raw:
        a.extend((z>>4,z&15))
    return a
def pack4(vals):
    return bytes(((vals[i]&15)<<4)|(vals[i+1]&15) for i in range(0,len(vals),2))
def get_glyph(page,idx):
    w,h,g,n=geom(page)
    vals=unpack4(page[8+idx*g:8+(idx+1)*g])
    im=Image.new('L',(w,h))
    im.putdata([v*17 for v in vals])
    return im
def put_glyph(page,idx,im):
    w,h,g,n=geom(page)
    if im.size!=(w,h):
        raise ValueError((im.size,(w,h)))
    vals=[max(0,min(15,(int(v)+8)//17)) for v in im.getdata()]
    page[8+idx*g:8+(idx+1)*g]=pack4(vals)
def half_loc(c):
    o=ord(c)
    return f'half{(o-0x20)//0x10:04d}.lz',(o-0x20)%0x10

def main():
    """Run the command-line patch/verification workflow."""
    ap=argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--report')
    a=ap.parse_args()
    raw=Path(a.input).read_bytes()
    if sha(raw)!=EXPECTED_SHA:
        raise SystemExit(f'ERROR: base FONTLINK hash {sha(raw)} != {EXPECTED_SHA}')
    es=read_pac(raw)
    by={e['name']:e for e in es}
    names=['half0000.lz','half0002.lz','half0004.lz','full8102.lz','full8202.lz']
    pages={n:bytearray(decompress(by[n]['blob'])) for n in names}
    # Apostrophe: clean retail full-width quote glyph, downsampled into the half cell.
    p,idx=half_loc("'")
    src=get_glyph(pages['full8102.lz'],6).resize((12,24),Image.Resampling.BOX)
    vals=[max(0,min(15,(int(v)+8)//17))*17 for v in src.getdata()]
    q=Image.new('L',(12,24))
    q.putdata(vals)
    shifted=Image.new('L',(12,24),0)
    shifted.paste(q,(3,0))
    put_glyph(pages[p],idx,shifted)
    # Lowercase l: use the clean retail full-width l stem but keep half-cell metrics.
    p,idx=half_loc('l')
    src=get_glyph(pages['full8202.lz'],15)
    bb=src.getbbox()
    if bb!=(10,1,14,22):
        raise ValueError(('unexpected clean l source bbox',bb))
    clean=Image.new('L',(12,24),0)
    clean.paste(src.crop(bb),(2,1))
    put_glyph(pages[p],idx,clean)
    out=bytearray(raw)
    changed=[]
    stats=[]
    for name in ['half0000.lz','half0004.lz']:
        e=by[name]
        nb=compress(bytes(pages[name]))
        nextoff=min(x['off'] for x in es if x['off']>e['off'])
        alloc=nextoff-e['off']
        if len(nb)>alloc:
            raise ValueError(f'{name}: {len(nb)} > {alloc}')
        if decompress(nb)!=bytes(pages[name]):
            raise RuntimeError('roundtrip '+name)
        struct.pack_into('<I',out,e['dir']+16,len(nb))
        out[e['off']:nextoff]=nb+b'\0'*(alloc-len(nb))
        changed.append(name)
        stats.append((name,e['size'],len(nb),alloc))
    oes=read_pac(bytes(out))
    oby={e['name']:e for e in oes}
    actual=[e['name'] for e in es if e['size']!=oby[e['name']]['size'] or e['blob']!=oby[e['name']]['blob']]
    if actual!=changed:
        raise RuntimeError(('unexpected members',actual,changed))
    for e in oes:
        decompress(e['blob'])
    Path(a.output).write_bytes(out)
    lines=['UI80 MINIMAL RUNTIME FONT POLISH: PASS',f'input_sha256={sha(raw)}',f'output_sha256={sha(bytes(out))}',f'archive_size={len(out)} (unchanged)',
           'changed_glyphs=ASCII apostrophe(0x27), lowercase l(0x6C) only',
           'fullwidth_A-Z=byte-identical to accepted UI55 (broad UI79 experiment rolled back)',
           'all_halfwidth_A-Z=byte-identical to accepted UI55; all other lowercase cells unchanged']
    for n,o,z,al in stats:
        lines.append(f'{n}: compressed {o}->{z}; allocation={al}; headroom={al-z}')
    lines.append('VERIFICATION: all 453 streams decode; PAC size/offsets preserved; exactly two font members changed.')
    txt='\n'.join(lines)+'\n'
    print(txt,end='')
    if a.report:
        Path(a.report).write_text(txt,encoding='utf-8')
if __name__=='__main__':
    main()
