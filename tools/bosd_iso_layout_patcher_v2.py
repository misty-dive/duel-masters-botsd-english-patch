#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, os, shutil, struct
from dataclasses import dataclass
from pathlib import Path

SECTOR = 2048
KNOWN_RETAIL_SHA256 = {
    "SCRPACK.SDA": "707e53a0f714dea7f3a059d973085fafd4f9120d0ef59e92bac42eb561514b11",
    "SLPM_658.82": "846ed10f8247dc5fe6d9f41ccf11179bbbe3a9c9fde5991c8ebcc271dc38b11d",
    "LIST_1.BIN": "8e07816855adf656a95bed7d86d2434ef2842204b44237848204fb450772ebcf",
    "FONTLINK.PAC": "599ddb34c9756f7d60c0f00c24755dca64e0ae81b7ae8643367b169c9d746c7a",
    "TITLE.DAT": "1cdf5d217ca28d159eb1579f9d2c05c76afc7b0490621deced1c3f525ed51f61",
    "SKB.DAT": "5834969d8c16477f2d20b7e281fe596694a14708d1337743f18a1be43475edb3",
    "DUEL.DAT": "a70281ab94196c3d460505a78351821ca55fe0a9053e27afe870036781225710",
    "CARDINFO.DAT": "315468c8be20962829acfc020273d44ba608b8e8198f2911c8296c33b13f1a04",
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def u32le(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]

def read_both32(b: bytes, off: int) -> int:
    le = struct.unpack_from("<I", b, off)[0]
    be = struct.unpack_from(">I", b, off+4)[0]
    if le != be:
        raise ValueError(f"ISO9660 both-endian value mismatch at 0x{off:X}: {le} != {be}")
    return le

def write_both32(buf: bytearray, off: int, value: int):
    struct.pack_into("<I", buf, off, value)
    struct.pack_into(">I", buf, off+4, value)

@dataclass
class Entry:
    path: str
    name: str
    extent: int
    size: int
    flags: int
    record_off: int

class Iso9660:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.descriptors = []
        self.pvd_off = None
        self.root_extent = None
        self.root_size = None
        self._read_descriptors()

    def _read_descriptors(self):
        sec = 16
        while True:
            off = sec * SECTOR
            if off + SECTOR > len(self.raw):
                raise ValueError("truncated ISO before volume descriptor terminator")
            d = self.raw[off:off+SECTOR]
            typ = d[0]
            if d[1:6] != b"CD001":
                raise ValueError(f"not ISO9660 at volume descriptor sector {sec}")
            self.descriptors.append((typ, off))
            if typ == 1 and self.pvd_off is None:
                self.pvd_off = off
                root = d[156:]
                if root[0] < 34:
                    raise ValueError("invalid PVD root directory record")
                self.root_extent = read_both32(root, 2)
                self.root_size = read_both32(root, 10)
            if typ == 255:
                break
            sec += 1
        if self.pvd_off is None:
            raise ValueError("ISO9660 primary volume descriptor not found")

    def entries(self):
        out = []
        seen_dirs = set()
        self._walk_dir(self.root_extent, self.root_size, "", out, seen_dirs)
        return out

    def _walk_dir(self, extent: int, size: int, parent: str, out, seen_dirs):
        key=(extent,size)
        if key in seen_dirs:
            return
        seen_dirs.add(key)
        start=extent*SECTOR
        end=start+size
        if end>len(self.raw):
            raise ValueError(f"directory {parent or '/'} exceeds ISO size")
        pos=start
        children=[]
        while pos<end:
            rec_len=self.raw[pos]
            if rec_len==0:
                pos=((pos//SECTOR)+1)*SECTOR
                continue
            if pos+rec_len>end or rec_len<34:
                raise ValueError(f"bad directory record at ISO offset 0x{pos:X}")
            rec=self.raw[pos:pos+rec_len]
            ext=read_both32(rec,2)
            datalen=read_both32(rec,10)
            flags=rec[25]
            nlen=rec[32]
            ident=bytes(rec[33:33+nlen])
            if ident==b"\x00":
                name="."
            elif ident==b"\x01":
                name=".."
            else:
                name=ident.decode("ascii",errors="strict")
                if ";" in name:
                    name=name.split(";",1)[0]
            if name not in (".",".."):
                path=(parent.rstrip("/")+"/"+name) if parent else "/"+name
                e=Entry(path=path,name=name,extent=ext,size=datalen,flags=flags,record_off=pos)
                out.append(e)
                if flags & 0x02:
                    children.append(e)
            pos += rec_len
        for e in children:
            self._walk_dir(e.extent,e.size,e.path,out,seen_dirs)

    def find_unique_basename(self, basename: str) -> Entry:
        matches=[e for e in self.entries() if e.name.upper()==basename.upper()]
        if not matches:
            raise ValueError(f"{basename}: not found in ISO")
        if len(matches)!=1:
            raise ValueError(f"{basename}: multiple matches: {[e.path for e in matches]}")
        return matches[0]

def patch_iso(source: Path, output: Path, replacements: list[Path], strict_core: bool = True):
    src=source.read_bytes()
    if len(src)%SECTOR:
        raise ValueError(f"source ISO length is not a multiple of {SECTOR}")
    iso=Iso9660(src)
    entries={p.name: iso.find_unique_basename(p.name) for p in replacements}

    # For known BOSD core files, require the exact retail source bytes before patching.
    # This prevents accidentally stacking this development patch over a different build.
    for p in replacements:
        e=entries[p.name]
        expected=KNOWN_RETAIL_SHA256.get(p.name.upper())
        if expected and strict_core:
            original=src[e.extent*SECTOR:e.extent*SECTOR+e.size]
            got=sha256(original)
            if got != expected:
                raise ValueError(
                    f"{e.path}: source SHA-256 {got} does not match expected retail {expected}"
                )

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    out=bytearray(output.read_bytes())

    manifest=[]
    append_jobs=[]
    for p in replacements:
        data=p.read_bytes()
        e=entries[p.name]
        if e.flags & 0x02:
            raise ValueError(f"{e.path}: replacement target is a directory")
        old_start=e.extent*SECTOR
        old_alloc=((e.size+SECTOR-1)//SECTOR)*SECTOR
        if len(data) <= old_alloc:
            # Preserve the directory record and original extent. To avoid changing loader-visible
            # file length unless necessary, replacement must be exactly the recorded file size.
            if len(data) != e.size:
                raise ValueError(
                    f"{e.path}: replacement is {len(data)} bytes but retail file is {e.size}; "
                    "size-changing replacements are appended and retargeted, so use a larger file "
                    "or pad this replacement to the exact retail size."
                )
            out[old_start:old_start+old_alloc] = data + b"\0"*(old_alloc-len(data))
            manifest.append((e.path,"in-place",e.extent,e.extent,e.size,len(data),sha256(data)))
        else:
            append_jobs.append((p,data,e))

    # Append enlarged files without moving any existing sector.
    for p,data,e in append_jobs:
        if len(out)%SECTOR:
            out += b"\0"*(SECTOR-len(out)%SECTOR)
        new_extent=len(out)//SECTOR
        alloc=((len(data)+SECTOR-1)//SECTOR)*SECTOR
        out += data + b"\0"*(alloc-len(data))
        write_both32(out,e.record_off+2,new_extent)
        write_both32(out,e.record_off+10,len(data))
        manifest.append((e.path,"append+retarget",e.extent,new_extent,e.size,len(data),sha256(data)))

    # If anything was appended, update volume-space-size in every ISO9660 primary/supplementary
    # descriptor. Existing file and directory LBAs remain unchanged.
    if append_jobs:
        new_sectors=len(out)//SECTOR
        for typ,off in iso.descriptors:
            if typ in (1,2):
                write_both32(out,off+80,new_sectors)

    output.write_bytes(out)

    # Reparse output and prove each target reads back exactly.
    check=Iso9660(bytes(out))
    for p in replacements:
        data=p.read_bytes()
        e=check.find_unique_basename(p.name)
        got=bytes(out[e.extent*SECTOR:e.extent*SECTOR+e.size])
        if got!=data:
            raise RuntimeError(f"verification failed for {e.path}")
    return src,out,manifest

def main():
    ap=argparse.ArgumentParser(
        description="Layout-preserving ISO9660 file replacer for BOSD development builds. "
                    "Exact-size files overwrite their original sectors; enlarged files are appended "
                    "and only their ISO9660 directory record is retargeted."
    )
    ap.add_argument("source_iso",type=Path)
    ap.add_argument("output_iso",type=Path)
    ap.add_argument("replacement",type=Path,nargs="+",
                    help="replacement files; each basename must uniquely match a file in the ISO")
    ap.add_argument("--allow-nonretail", action="store_true",
                    help="skip known retail SHA-256 checks for core BOSD files (development/testing only)")
    a=ap.parse_args()
    for p in a.replacement:
        if not p.is_file():
            ap.error(f"replacement not found: {p}")
    src,out,manifest=patch_iso(a.source_iso,a.output_iso,a.replacement, strict_core=not a.allow_nonretail)
    print("Source ISO:",a.source_iso)
    print("Source size:",len(src),"bytes /",len(src)//SECTOR,"sectors")
    print("Source SHA-256:",sha256(src))
    print("Output ISO:",a.output_iso)
    print("Output size:",len(out),"bytes /",len(out)//SECTOR,"sectors")
    print("Output SHA-256:",sha256(out))
    print()
    for path,mode,old_lba,new_lba,old_size,new_size,h in manifest:
        print(f"{path}: {mode}")
        print(f"  LBA {old_lba} -> {new_lba}; size {old_size} -> {new_size}")
        print(f"  SHA-256 {h}")
    print()
    print("Verification: every replacement reads back byte-for-byte from the patched ISO.")
    print("Existing sectors were never relocated.")

if __name__=="__main__":
    main()
