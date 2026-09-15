#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, importlib.util, struct, sys

BASE_OPT_SHA = '6e5a8a2e07fa0acb1cc7e487f74531b36bd7407fee1bdce4845d6db39689c09b'
BASE_DECK_SHA = '11288d7940f0e72810729f4b0b4ced072c1ed5b91a06d4c59c1a674cdb5fe413'
BASE_EXE_SHA = 'f98007944275946c2ec2e6281205d0a1e1b7bf34aab60adfb436af1819e3587b'

FONT_DEFAULT = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def loadmod(path: Path, name: str):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    sys.modules[name] = m
    s.loader.exec_module(m)
    return m

def patch_archive(base: Path, out: Path, font: Path, targets: dict, expected_sha: str, helper, arcmod, strong):
    raw = base.read_bytes()
    if sha(raw) != expected_sha:
        raise SystemExit(f'Base hash mismatch for {base.name}: {sha(raw)}')
    arc = arcmod.parse_archive(base, decompress=True)
    data = bytearray(raw)
    changed_members = []
    for name, edits in targets.items():
        mem = next((x for x in arc.members if x.name == name), None)
        if mem is None:
            raise RuntimeError(f'Missing member {name}')
        t = helper.ITGA(mem.raw)
        before = [bytes(r) for r in t.idx]
        declared = []
        for e in edits:
            kind = e[0]
            if kind == 'paint':
                _, text, box, mode, face, outline, *rest = e
                helper.paint(t, text, box, font, mode, face, outline, rest[0] if rest else None)
                declared.append(box)
            elif kind == 'clear':
                _, box, index = e
                helper.clear_index(t, box, index)
                declared.append(box)
            else:
                raise ValueError(kind)
        patched = t.bytes()
        nb = struct.pack('<I', len(patched)) + strong.compress(patched)
        if arcmod.decode_member_blob(nb, 1) != patched:
            raise RuntimeError(f'LZ roundtrip failed: {name}')
        nxt = arc.members[mem.index + 1].data_rel if mem.index + 1 < len(arc.members) else len(raw) - arc.data_start
        alloc = nxt - mem.data_rel
        if len(nb) > alloc:
            raise RuntimeError(f'{name} compressed member overflow: {len(nb)}/{alloc}')
        st = arc.data_start + mem.data_rel
        data[st:st+alloc] = nb + b'\0' * (alloc - len(nb))
        struct.pack_into('<I', data, mem.record_off + 264, len(nb))
        diff = outside = 0
        for y in range(t.h):
            for x in range(t.w):
                if before[y][x] != t.idx[y][x]:
                    diff += 1
                    if not any(x0 <= x < x1 and y0 <= y < y1 for x0,y0,x1,y1 in declared):
                        outside += 1
        if not diff or outside:
            raise RuntimeError(f'{name}: bad pixel containment diff={diff} outside={outside}')
        changed_members.append((name, diff, len(nb), alloc))
    out.write_bytes(bytes(data))
    chk = arcmod.parse_archive(out, decompress=True)
    oldmap = {x.name:x for x in arc.members}
    newmap = {x.name:x for x in chk.members}
    for n, m in oldmap.items():
        if n not in targets and newmap[n].raw != m.raw:
            raise RuntimeError(f'Non-target member changed: {n}')
    return changed_members

def patch_exe(base: Path, out: Path):
    raw = base.read_bytes()
    if sha(raw) != BASE_EXE_SHA:
        raise SystemExit(f'Base EXE hash mismatch: {sha(raw)}')
    b = bytearray(raw)
    changes = []
    # Record screen unit labels. The Japanese units were full-width glyphs. Earlier
    # ASCII G/W/% replacements were half-width and pulled later columns left.
    # Extra spaces restore the original column positions.
    off = 0x4FBD70
    old = b[off:off+15]
    expected = b'   G    W    %\x00'
    if old != expected:
        raise RuntimeError(f'Unexpected Record units at 0x{off:X}: {old!r}')
    new = b'   G     W     %\x00'
    # The original slot extends to the next string at 0x4FBD88.
    b[off:0x4FBD88] = new + b'\x00' * (0x4FBD88 - off - len(new))
    changes.append((off, 'Record unit spacing', old, new))

    # Remaining copy-count popup labels in the deck builder.
    for off, jp, en in [
        (0x446968, '１枚'.encode('cp932'), b'1'),
        (0x446970, '２枚'.encode('cp932'), b'2'),
        (0x446978, '３枚'.encode('cp932'), b'3'),
        (0x446980, '４枚'.encode('cp932'), b'4'),
    ]:
        slot = 8
        if not b[off:off+len(jp)].startswith(jp):
            raise RuntimeError(f'Unexpected deck count label at 0x{off:X}: {b[off:off+slot]!r}')
        oldslot = bytes(b[off:off+slot])
        b[off:off+slot] = en + b'\x00' * (slot-len(en))
        changes.append((off, f'{jp.decode("cp932")} -> {en.decode()}', oldslot, bytes(b[off:off+slot])))
    out.write_bytes(bytes(b))
    return changes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('opt')
    ap.add_argument('deck')
    ap.add_argument('exe')
    ap.add_argument('outdir')
    ap.add_argument('--font', default=FONT_DEFAULT)
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    helper = loadmod(here/'bosd_static_label_polish_ui81.py', 'ui11helper')
    arcmod = loadmod(here/'bosd_ui_archive_tool_v1.py', 'ui11arc')
    strong = loadmod(here/'bosd_ui_lzss_strong.py', 'ui11lz')
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    font = Path(a.font)

    # OPT: clean up the old striped English atlas using the same solid vector
    # renderer used for the verified UI81 Character Select / duel phase fixes.
    # Most labels live over transparent pixels; the title is baked over a plate.
    opt = {'OPT_SRC_OP_P00_TGA': [
        ('paint','ON',      (2,5,48,29),       'transparent',240,1,25),
        ('paint','OFF',     (82,5,128,29),     'transparent',240,1,25),
        ('paint','NORMAL',  (139,6,230,29),    'transparent',240,1,25),
        ('paint','LIGHT',   (235,6,281,29),    'transparent',240,1,25),
        ('paint','TYPE',    (305,5,377,29),    'transparent',240,1,25),
        ('paint','STEREO',  (390,5,481,29),    'transparent',240,1,25),
        ('paint','ON',      (2,35,48,63),      'transparent',74,1,25),
        ('paint','OFF',     (82,35,129,63),    'transparent',74,1,25),
        ('paint','NORMAL',  (139,35,231,63),   'transparent',74,1,25),
        ('paint','LIGHT',   (235,35,281,63),   'transparent',74,1,25),
        ('paint','TYPE',    (283,35,377,63),   'transparent',74,1,25),
        ('paint','STEREO',  (386,35,481,63),   'transparent',74,1,25),
        ('paint','MONO',    (2,70,94,93),      'transparent',240,1,25),
        ('paint','MONO',    (2,99,96,126),     'transparent',74,1,25),
        ('paint','MOVIES',  (3,141,96,165),    'transparent',240,1,25),
        ('paint','DUEL FX', (129,141,246,165), 'transparent',240,1,25),
        ('paint','CHAR FX', (252,141,366,165), 'transparent',240,1,25),
        ('paint','CAMERA',  (372,141,508,165), 'transparent',240,1,25),
        ('paint','SOUND',   (3,173,96,197),    'transparent',240,1,25),
        ('paint','VIBE',    (100,173,160,197), 'transparent',240,1,25),
        ('paint','OPTIONS', (306,184,470,217), 'horizontal', 240,1),
    ]}

    # DECK P02: tab labels and the standalone Japanese 枚 glyph used after
    # dynamic card counts.  P04: stats headings and civilization tabs.
    deck = {
      'DECK_SRC_DC_P02_TGA': [
        ('paint','DECK',  (13,18,58,42),   'horizontal',196,15),
        ('paint','DECK',  (87,18,132,42),  'horizontal',239,15),
        ('paint','CARDS', (13,68,59,103),  'horizontal',196,15),
        ('paint','CARDS', (87,68,133,102), 'horizontal',239,15),
        ('paint','STATS', (13,126,59,159), 'horizontal',196,15),
        ('paint','STATS', (87,126,133,158),'horizontal',239,15),
        ('clear',(488,2,506,18),0),
      ],
      'DECK_SRC_DC_P04_TGA': [
        ('paint','CARD RATIO',(43,8,150,29),   'horizontal',255,13),
        ('paint','ALL',       (187,8,235,29),  'horizontal',255,13),
        ('paint','LGT',       (5,62,41,83),    'horizontal',255,13),
        ('paint','WTR',       (69,62,105,83),  'horizontal',255,13),
        ('paint','DRK',       (133,62,169,83), 'horizontal',255,13),
        ('paint','FIR',       (198,62,233,83), 'horizontal',255,13),
        ('paint','NAT',       (1,121,43,142),  'horizontal',255,13),
        ('paint','MANA CURVE',(77,121,181,140),'horizontal',255,13),
      ],
    }

    opt_out = outdir/'OPT_UI11_POLISH.DAT'
    deck_out = outdir/'DECK_UI11_POLISH.DAT'
    exe_out = outdir/'SLPM_658.82_UI11_POLISH'
    oc = patch_archive(Path(a.opt), opt_out, font, opt, BASE_OPT_SHA, helper, arcmod, strong)
    dc = patch_archive(Path(a.deck), deck_out, font, deck, BASE_DECK_SHA, helper, arcmod, strong)
    ec = patch_exe(Path(a.exe), exe_out)
    print(f'OPT {sha(opt_out.read_bytes())} {opt_out.stat().st_size}')
    print(f'DECK {sha(deck_out.read_bytes())} {deck_out.stat().st_size}')
    print(f'EXE {sha(exe_out.read_bytes())} {exe_out.stat().st_size}')
    for row in oc+dc: print(' ', row)
    for row in ec: print(' ', hex(row[0]), row[1])

if __name__ == '__main__': main()
