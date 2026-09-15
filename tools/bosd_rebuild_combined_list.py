#!/usr/bin/env python3
"""Rebuild and self-validate BOTSD's 4058-pointer externalized LIST_1.BIN."""
from __future__ import annotations
import argparse, csv, hashlib, sys
from pathlib import Path

# Import from the project tool shipped beside this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bosd_cardtext_externalizer_v3 import (  # type: ignore
    DISPLAY_COUNT, MASTER_COUNT, TOTAL_POINTERS,
    build_combined_list, parse_combined_relative,
)


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def materialize(rows, id_col, expected_count):
    out = [None] * expected_count
    for r in rows:
        i = int(r[id_col])
        if not 0 <= i < expected_count:
            raise ValueError(f"{id_col} {i} out of range")
        if out[i] is not None:
            raise ValueError(f"duplicate {id_col} {i}")
        tr = r.get("translation", "")
        src = r.get("source_japanese", "")
        out[i] = "" if tr == "<EMPTY>" else (tr if tr else src)
    missing = [i for i,v in enumerate(out) if v is None]
    if missing:
        raise ValueError(f"missing {id_col} rows: {missing[:20]}")
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--display", type=Path, required=True)
    ap.add_argument("--master", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a=ap.parse_args()
    drows=read_rows(a.display); mrows=read_rows(a.master)
    if len(drows)!=DISPLAY_COUNT or len(mrows)!=MASTER_COUNT:
        raise ValueError(f"wrong row counts: display={len(drows)} master={len(mrows)}")
    d=materialize(drows,"list_index",DISPLAY_COUNT)
    m=materialize(mrows,"master_text_id",MASTER_COUNT)
    raw=build_combined_list(d,m)
    dc,mc=parse_combined_relative(raw)
    if dc!=d or mc!=m:
        raise RuntimeError("combined LIST round-trip self-check failed")
    a.out.write_bytes(raw)
    print(f"Wrote {a.out}")
    print(f"Pointers: {TOTAL_POINTERS} = {DISPLAY_COUNT} display + {MASTER_COUNT} master")
    print(f"Size: {len(raw)} bytes")
    print(f"SHA-256: {hashlib.sha256(raw).hexdigest()}")

if __name__=="__main__": main()
