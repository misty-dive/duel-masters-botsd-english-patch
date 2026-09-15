#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct
from pathlib import Path

EXPECTED_SHA256='599ddb34c9756f7d60c0f00c24755dca64e0ae81b7ae8643367b169c9d746c7a'
ENTRY_COUNT=453; ALIGNMENT=0x40
U_PAGE='half0003.lz'; TARGET_PAGE='half0005.lz'

def sha256(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def read_pac(path:Path):
    raw=path.read_bytes()
    if sha256(raw)!=EXPECTED_SHA256: raise ValueError(f'unexpected FONTLINK SHA-256: {sha256(raw)}')
    if raw[:4]!=b'DPAC': raise ValueError('not DPAC')
    count,align=struct.unpack_from('<II',raw,4)
    if (count,align)!=(ENTRY_COUNT,ALIGNMENT): raise ValueError((count,align))
    entries=[];p=12
    for i in range(count):
        name=raw[p:p+16].split(b'\0',1)[0].decode('ascii')
        size,off=struct.unpack_from('<II',raw,p+16)
        entries.append(dict(index=i,dir_off=p,name=name,size=size,off=off,blob=raw[off:off+size]))
        p+=24
    return raw,entries

def font_decompress(blob:bytes)->bytes:
    wanted=struct.unpack_from('<I',blob,0)[0];p=4;out=bytearray()
    while True:
        if p+2>len(blob): raise ValueError('missing terminator')
        t=struct.unpack_from('<H',blob,p)[0];p+=2
        if t==0: break
        ln=t>>11
        if ln:
            d=t&0x7ff
            if d==0 or d>len(out): raise ValueError(('bad backref',d,len(out)))
            for _ in range(ln): out.append(out[-d])
        else:
            ln=t
            if p+ln>len(blob): raise ValueError('literal overrun')
            out+=blob[p:p+ln];p+=ln
    if len(out)!=wanted or p!=len(blob): raise ValueError(('decode mismatch',len(out),wanted,p,len(blob)))
    return bytes(out)

def font_compress(data:bytes)->bytes:
    out=bytearray(struct.pack('<I',len(data)));lit=bytearray();pos=0
    def flush():
        nonlocal lit
        while lit:
            chunk=bytes(lit[:0x7ff]);del lit[:len(chunk)]
            out.extend(struct.pack('<H',len(chunk)));out.extend(chunk)
    while pos<len(data):
        bestl=0;bestd=0
        for d in range(1,min(0x7ff,pos)+1):
            l=0
            while l<31 and pos+l<len(data) and data[pos+l]==data[pos+l-d]: l+=1
            if l>bestl:
                bestl,bestd=l,d
                if l==31: break
        if bestl>=3:
            flush();out.extend(struct.pack('<H',(bestl<<11)|bestd));pos+=bestl
        else:
            lit.append(data[pos]);pos+=1
            if len(lit)==0x7ff: flush()
    flush();out+=b'\0\0';return bytes(out)

def geom(d:bytes):
    w,h,g,r=struct.unpack_from('<HHHH',d,0)
    if r!=0 or g!=w*h//2 or (len(d)-8)%g: raise ValueError('bad page geometry')
    return w,h,g,(len(d)-8)//g

def unpack4(raw):
    p=[]
    for z in raw:p.extend((z>>4,z&15))
    return p

def pack4(p): return bytes(((p[i]&15)<<4)|(p[i+1]&15) for i in range(0,len(p),2))

def make_ue(u,w,h):
    out=[0]*(w*h)
    for y in range(h-1): out[(y+1)*w:(y+2)*w]=u[y*w:(y+1)*w]
    for x in (2,3,7,8): out[x]=5;out[w+x]=15
    return out

def build(raw,entries):
    by={e['name']:e for e in entries};u=by[U_PAGE];t=by[TARGET_PAGE]
    ud=bytearray(font_decompress(u['blob']));td=bytearray(font_decompress(t['blob']))
    if geom(ud)!=(12,24,144,16) or geom(td)!=(12,24,144,15): raise ValueError('unexpected ASCII page geometry')
    ug=144;tg=144;ui=5;ti=14
    up=unpack4(ud[8+ui*ug:8+(ui+1)*ug]);newglyph=pack4(make_ue(up,12,24))
    td[8+ti*tg:8+(ti+1)*tg]=newglyph
    newblob=font_compress(bytes(td))
    if font_decompress(newblob)!=bytes(td): raise RuntimeError('roundtrip failed')
    nextoff=min(e['off'] for e in entries if e['off']>t['off']);alloc=nextoff-t['off']
    if len(newblob)>alloc: raise ValueError(('patched page too large',len(newblob),alloc))
    out=bytearray(raw);struct.pack_into('<I',out,t['dir_off']+16,len(newblob))
    out[t['off']:nextoff]=newblob+b'\0'*(alloc-len(newblob))
    if len(out)!=len(raw): raise RuntimeError('archive size changed')
    # reparse all entries and validate; 452 untouched blobs exact
    p=12;new=[]
    for i in range(ENTRY_COUNT):
        name=out[p:p+16].split(b'\0',1)[0].decode('ascii');size,off=struct.unpack_from('<II',out,p+16)
        new.append(dict(name=name,size=size,off=off,blob=bytes(out[off:off+size])));p+=24
    oldby={e['name']:e for e in entries}
    for e in new:
        font_decompress(e['blob'])
        if e['name']!=TARGET_PAGE and e['blob']!=oldby[e['name']]['blob']: raise RuntimeError('unrelated resource changed '+e['name'])
    return bytes(out),dict(old=t['size'],new=len(newblob),alloc=alloc,sha=sha256(out))

def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('check');p.add_argument('fontlink',type=Path)
    p=sp.add_parser('patch');p.add_argument('fontlink',type=Path);p.add_argument('output',type=Path)
    a=ap.parse_args();raw,entries=read_pac(a.fontlink)
    for e in entries:font_decompress(e['blob'])
    if a.cmd=='check':
        print('FONTLINK SHA-256:',sha256(raw));print('All 453 font streams decode successfully.')
    else:
        out,m=build(raw,entries);a.output.write_bytes(out)
        print('Patched FONTLINK:',a.output);print('Archive size:',len(out),'bytes (unchanged)')
        print(f"half0005.lz: {m['old']} -> {m['new']} bytes; slot allocation {m['alloc']} bytes")
        print('All later offsets unchanged; 452 untouched resources byte-identical.')
        print('All 453 font streams decode successfully.');print('Patched SHA-256:',m['sha'])
if __name__=='__main__':main()
