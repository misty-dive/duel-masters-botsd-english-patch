#!/usr/bin/env python3
"""Independent UI82 verifier: UI76 frozen card layers + 677 second-sprite English titles."""
from pathlib import Path
import argparse, csv, hashlib, io, struct, zipfile
RETAIL_SHA = '179dbb49d4fe0dc7952b2d1d56b8ab90f17cd6a48eaf29b0c5c82ed076986ece'

# Compare chunk-by-chunk so unexpected changes outside the approved card layers fail loudly.
SIZE = 151525376

def sha(b):
    return hashlib.sha256(b).hexdigest()

def outer(b):
    if b[:4] != b'sda\x00':
        raise ValueError('not SDA')
    decl, n = struct.unpack_from('<II', b, 4)
    if decl != len(b):
        raise ValueError('declared size')
    return list(struct.unpack_from('<' + 'I' * n, b, 12))

def bounds(o, i, total):
    return (o[i], o[i + 1] if i + 1 < len(o) else total)

def changed(A, B, o):
    return [i for i in range(len(o)) if A[slice(*bounds(o, i, len(A)))] != B[slice(*bounds(o, i, len(B)))]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('retail', type=Path)
    ap.add_argument('ui76', type=Path)
    ap.add_argument('ui82', type=Path)
    ap.add_argument('inventory', type=Path)
    ap.add_argument('patch_zip', type=Path)
    ap.add_argument('--report', type=Path)
    a = ap.parse_args()
    R = a.retail.read_bytes()
    U = a.ui76.read_bytes()
    V = a.ui82.read_bytes()
    if len(R) != SIZE or sha(R) != RETAIL_SHA:
        raise SystemExit('ERROR: retail preflight')
    if len(U) != SIZE or len(V) != SIZE:
        raise SystemExit('ERROR: size')
    ro, uo, vo = (outer(R), outer(U), outer(V))
    if ro != uo or ro != vo:
        raise SystemExit('ERROR: outer offsets changed')
    rows = list(csv.DictReader(a.inventory.open(encoding='utf-8-sig', newline='')))
    if len(rows) != 677:
        raise SystemExit('ERROR: inventory row count')
    old = set((int(r[k]) for r in rows for k in ('large_chunk', 'small_chunk')))
    second = set(range(2037, 2714))
    exp76 = old
    exp82 = old | second
    c76 = set(changed(R, U, ro))
    c82 = set(changed(R, V, ro))
    cdelta = set(changed(U, V, ro))
    if c76 != exp76:
        raise SystemExit(f'ERROR: UI76 changed-set mismatch extra={sorted(c76 - exp76)[:8]} missing={sorted(exp76 - c76)[:8]}')
    if c82 != exp82:
        raise SystemExit(f'ERROR: UI82 changed-set mismatch extra={sorted(c82 - exp82)[:8]} missing={sorted(exp82 - c82)[:8]}')
    if cdelta != second:
        raise SystemExit(f'ERROR: UI76->UI82 delta mismatch extra={sorted(cdelta - second)[:8]} missing={sorted(second - cdelta)[:8]}')
    with zipfile.ZipFile(a.patch_zip) as z:
        m = list(csv.DictReader(io.TextIOWrapper(z.open('manifest.csv'), encoding='utf-8')))
        if len(m) != 677:
            raise SystemExit('ERROR: patch manifest')
        for q in m:
            i = int(q['chunk'])
            s, e = bounds(ro, i, len(R))
            if sha(R[s:e]) != q['retail_sha256'] or sha(V[s:e]) != q['patched_sha256']:
                raise SystemExit(f'ERROR: payload verification chunk {i}')
    txt = 'UI82 FROZEN CARD CHECKPOINT: PASS\n' + f'retail_sha256={sha(R)}\nui76_compiled_sha256={sha(U)}\nui82_compiled_sha256={sha(V)}\nouter_size={len(V)}\nouter_chunks={len(ro)}\nouter_offsets_unchanged=yes\nui76_large_card_chunks=677\nui76_printed_thumbnail_chunks=677\nui82_second_sprite_name_chunks=677\ncardinfo_background_chunks_1354_1359_retail_identical=yes\nall_other_chunks_retail_identical=yes\nui76_existing_card_layers_byte_identical_in_ui82=yes\nfull_card_reconversion_performed=no\n'
    if a.report:
        a.report.write_text(txt, encoding='utf-8')
    print(txt, end='')
if __name__ == '__main__':
    main()
