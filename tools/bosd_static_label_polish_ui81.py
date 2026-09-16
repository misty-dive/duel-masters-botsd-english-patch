#!/usr/bin/env python3
"""Render the UI81 static English labels into verified indexed-TGA archive members.

Text is fitted to measured boxes and archive containment is checked after rebuilding."""
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, importlib.util, struct, sys
from PIL import Image, ImageDraw, ImageFont
ADV_SHA = '92c957f9b711a081ea8977629010d6dcf90852274c58149629fb5db2bfbba1b2'

# Indexed TGA palettes/layouts are preserved; only measured label regions are repainted.
ADVSCN_SHA = '526bcc6e7a4bc92c9f2a521a0e8113a75fba86daa49d3453aff156b8de95ced3'
DUELPTS_SHA = 'bb17488771f42a97a558b1afa1268f54f300c6c88050e9b1da29c9d7819833e4'

def sha(b):
    return hashlib.sha256(b).hexdigest()

def loadmod(path, name):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    sys.modules[name] = m
    s.loader.exec_module(m)
    return m

class ITGA:

    def __init__(self, raw):
        self.raw = raw
        self.idlen, self.cmaptype, self.imgtype = (raw[0], raw[1], raw[2])
        self.cf, self.cl, self.cb = struct.unpack_from('<HHB', raw, 3)
        self.xo, self.yo, self.w, self.h, self.bpp, self.desc = struct.unpack_from('<HHHHBB', raw, 8)
        if not (self.cmaptype == 1 and self.imgtype == 1 and (self.bpp == 8) and (self.cb in (24, 32))):
            raise ValueError('unsupported TGA')
        po = 18 + self.idlen
        self.bpe = self.cb // 8
        self.palette = []
        for i in range(self.cl):
            ent = raw[po + i * self.bpe:po + (i + 1) * self.bpe]
            if self.cb == 32:
                B, G, R, A = ent
            else:
                B, G, R = ent
                A = 255
            self.palette.append((R, G, B, A))
        self.pixoff = po + self.cl * self.bpe
        stored = raw[self.pixoff:self.pixoff + self.w * self.h]
        rows = [bytearray(stored[y * self.w:(y + 1) * self.w]) for y in range(self.h)]
        if not self.desc & 32:
            rows.reverse()
        self.idx = rows

    def bytes(self):
        rows = [bytes(r) for r in self.idx]
        if not self.desc & 32:
            rows = list(reversed(rows))
        out = bytearray(self.raw)
        out[self.pixoff:self.pixoff + self.w * self.h] = b''.join(rows)
        return bytes(out)

    def color(self, index):
        return self.palette[index - self.cf]

    def nearest(self, c):
        r, g, b, a = c
        best = 10 ** 20
        bi = 0
        for j, p in enumerate(self.palette):
            d = (r - p[0]) ** 2 + (g - p[1]) ** 2 + (b - p[2]) ** 2 + 2 * (a - p[3]) ** 2
            if d < best:
                best = d
                bi = j + self.cf
        return bi

    def rgba(self):
        im = Image.new('RGBA', (self.w, self.h))
        im.putdata([self.color(v) for r in self.idx for v in r])
        return im

def inpaint_horizontal(t, box):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        lx = max(0, x0 - 5)
        rx = min(t.w - 1, x1 + 4)
        lc = [t.color(t.idx[y][x]) for x in range(max(0, lx - 2), min(t.w, lx + 3))]
        rc = [t.color(t.idx[y][x]) for x in range(max(0, rx - 2), min(t.w, rx + 3))]
        av = lambda cs: tuple((round(sum((c[k] for c in cs)) / len(cs)) for k in range(4)))
        A, B = (av(lc), av(rc))
        sp = max(1, x1 - x0 - 1)
        for x in range(x0, x1):
            q = (x - x0) / sp
            t.idx[y][x] = t.nearest(tuple((round(A[k] * (1 - q) + B[k] * q) for k in range(4))))

def clear_index(t, box, index):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            t.idx[y][x] = index

def text_mask(text, w, h, font_path):
    S = 4
    canvas = Image.new('L', (max(16, w * S), max(16, h * S)), 0)
    d = ImageDraw.Draw(canvas)
    lo, hi = (4, 160)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        f = ImageFont.truetype(str(font_path), mid * S)
        bb = d.textbbox((0, 0), text, font=f, stroke_width=0)
        if bb[2] - bb[0] <= (w - 2) * S and bb[3] - bb[1] <= (h - 2) * S:
            lo = mid
        else:
            hi = mid - 1
    f = ImageFont.truetype(str(font_path), lo * S)
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = (bb[2] - bb[0], bb[3] - bb[1])
    x = (canvas.width - tw) // 2 - bb[0]
    y = (canvas.height - th) // 2 - bb[1]
    d.text((x, y), text, font=f, fill=255)
    small = canvas.resize((w, h), Image.Resampling.LANCZOS)
    return small.point(lambda v: 255 if v >= 112 else 0)

def paint(t, text, box, font_path, clear, face, outline, bg=None):
    x0, y0, x1, y1 = box
    if clear == 'transparent':
        clear_index(t, box, 0 if bg is None else bg)
    else:
        inpaint_horizontal(t, box)
    m = text_mask(text, x1 - x0 - 2, y1 - y0 - 2, font_path)
    ox = x0 + 1
    oy = y0 + 1
    o = m.filter(ImageFilter.MaxFilter(3)) if False else None
    mp = m.load()
    W, H = m.size
    for yy in range(H):
        for xx in range(W):
            if mp[xx, yy]:
                continue
            found = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = (xx + dx, yy + dy)
                    if 0 <= nx < W and 0 <= ny < H and mp[nx, ny]:
                        found = True
                        break
                if found:
                    break
            if found:
                t.idx[oy + yy][ox + xx] = outline
    for yy in range(H):
        for xx in range(W):
            if mp[xx, yy]:
                t.idx[oy + yy][ox + xx] = face

def patch_archive(base, out, font_path, targets, expected, arcmod, strong, rep):
    raw = base.read_bytes()
    if sha(raw) != expected:
        raise SystemExit(f'base hash mismatch {base.name} {sha(raw)}')
    arc = arcmod.parse_archive(base, decompress=True)
    data = bytearray(raw)
    changed = []
    for name, edits in targets.items():
        mem = next((x for x in arc.members if x.name == name))
        t = ITGA(mem.raw)
        before = [bytes(r) for r in t.idx]
        for text, box, mode, face, outline, *rest in edits:
            paint(t, text, box, font_path, mode, face, outline, rest[0] if rest else None)
        patched = t.bytes()
        nb = struct.pack('<I', len(patched)) + strong.compress(patched)
        if arcmod.decode_member_blob(nb, 1) != patched:
            raise RuntimeError('lz roundtrip')
        nxt = arc.members[mem.index + 1].data_rel if mem.index + 1 < len(arc.members) else len(raw) - arc.data_start
        alloc = nxt - mem.data_rel
        if len(nb) > alloc:
            raise RuntimeError(f'{name} overflow {len(nb)}/{alloc}')
        st = arc.data_start + mem.data_rel
        data[st:st + alloc] = nb + b'\x00' * (alloc - len(nb))
        struct.pack_into('<I', data, mem.record_off + 264, len(nb))
        diff = outside = 0
        for y in range(t.h):
            for x in range(t.w):
                if before[y][x] != t.idx[y][x]:
                    diff += 1
                    if not any((b[0] <= x < b[2] and b[1] <= y < b[3] for _, b, *_ in edits)):
                        outside += 1
        if not diff or outside:
            raise RuntimeError((name, diff, outside))
        changed.append((name, diff, len(nb), alloc, alloc - len(nb)))
    outb = bytes(data)
    out.write_bytes(outb)
    chk = arcmod.parse_archive(out, decompress=True)
    om = {x.name: x for x in arc.members}
    cm = {x.name: x for x in chk.members}
    for n, m in om.items():
        if n not in targets and cm[n].raw != m.raw:
            raise RuntimeError('non-target changed ' + n)
    rep.append(f'{base.name}->{out.name}: sha256={sha(outb)} size={len(outb)}')
    for r in changed:
        rep.append('  %s: changed_pixels=%d compressed=%d/%d headroom=%d' % r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('adv')
    ap.add_argument('advscn')
    ap.add_argument('duelpts')
    ap.add_argument('outdir')
    ap.add_argument('--font', required=True)
    ap.add_argument('--report')
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    arc = loadmod(here / 'bosd_ui_archive_tool_v1.py', 'ui81arc')
    strong = loadmod(here / 'bosd_ui_lzss_strong.py', 'ui81strong')
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    fp = Path(a.font)
    rep = ['UI81 TARGETED STATIC LABEL POLISH', 'renderer=prebuilt vector face; runtime FONTLINK untouched']
    sc = {'ADVSCN_SRC_AD_P14_TGA': [('CHARACTER SELECT', (150, 47, 357, 74), 'transparent', 254, 186, 0)], 'ADVSCN_SRC_AD_P15_TGA': [('SHOBU', (55, 6, 125, 31), 'horizontal', 255, 186), ('HAKUOH', (48, 46, 129, 71), 'horizontal', 255, 186), ('KOKUJO', (48, 86, 129, 111), 'horizontal', 255, 186), ('MIMI', (66, 126, 111, 151), 'horizontal', 255, 186), ('BUCKETMAN', (30, 166, 148, 191), 'horizontal', 255, 186)]}
    adv = {'ADV_SRC_AD_P13_TGA': [('BUY CARDS', (14, 4, 128, 31), 'transparent', 254, 240, 0), ('PRACTICE', (140, 4, 230, 31), 'transparent', 254, 240, 0), ('SELECT DUELIST', (262, 4, 431, 31), 'transparent', 254, 240, 0), ('EQUIP.', (1, 44, 63, 71), 'transparent', 254, 240, 0), ('SELECT DECK', (76, 44, 212, 71), 'transparent', 254, 240, 0)]}
    dp = []
    for text, y0, y1 in [('UNTAP', 101, 127), ('DRAW', 137, 163), ('CHARGE', 173, 199), ('SUMMON', 209, 235), ('ATTACK', 245, 271), ('END', 281, 307)]:
        dp += [(text, (38, y0, 150, y1), 'horizontal', 251, 10), (text, (243, y0, 341, y1), 'horizontal', 251, 10)]
    dp += [('DECK', (6, 321, 62, 341), 'horizontal', 251, 10), ('GRAVE', (122, 321, 183, 341), 'horizontal', 251, 10), ('HAND', (242, 321, 307, 341), 'horizontal', 251, 10), ('LEFT', (145, 374, 221, 408), 'transparent', 251, 10, 0)]
    patch_archive(Path(a.advscn), out / 'ADVSCN_UI81_EN.DAT', fp, sc, ADVSCN_SHA, arc, strong, rep)
    patch_archive(Path(a.adv), out / 'ADV_UI81_EN.DAT', fp, adv, ADV_SHA, arc, strong, rep)
    patch_archive(Path(a.duelpts), out / 'DUELPTS_UI81_EN.DAT', fp, {'DUELPTS_SRC_G_P00_TGA': dp}, DUELPTS_SHA, arc, strong, rep)
    rep += ['all_non_target_members=byte-identical', 'changed_pixels_outside_declared_rectangles=0', 'RESULT=PASS']
    txt = '\n'.join(rep) + '\n'
    print(txt, end='')
    if a.report:
        Path(a.report).write_text(txt, encoding='utf-8')
if __name__ == '__main__':
    main()
