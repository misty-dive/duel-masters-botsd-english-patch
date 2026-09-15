#!/usr/bin/env python3
"""UI76 R7 embedded-English Card Info data patch.

Runtime evidence proved that redirecting shared CardText getters was unsafe and that
LIST_1.BIN is lazy-loaded. R7 retains the accepted UI68 CardText getters and LIST
loader byte-identical, and instead repacks only the executable's embedded *rules*
master strings into canonical English. This makes the Special Ability panel English
before the external LIST has loaded, without changing CardText lifecycle semantics.

The established 65-entry legacy race-name table localization is retained as an
independent static cleanup. No global font or keyboard changes are made here.
"""
from __future__ import annotations
from pathlib import Path
import argparse, bisect, csv, hashlib, struct

VA_DELTA = 0xFF000
EXPECTED_SHA = '834d50b75adce47c5dace19838a2e28e3c692611d173d88477514ac299cb6378'
MASTER_TABLE_VA = 0x444268
MASTER_COUNT = 2376
RACE_PTR_TABLE_VA = 0x4436D8
RACE_COUNT = 65
RACE_OVERFLOW_START = 0x470080
RACE_OVERFLOW_LIMIT = 0x470400
# Keep the full old R5 scratch area excluded from rules allocation even though R6
# does not execute code there. This prevents collisions with the one legacy race
# overflow string and makes rollback/provenance obvious.
RESERVED_DATA = [(0x470000, 0x470400)]
# Established all-zero linker slack immediately before the 0x470000 master-pointer
# global. We independently prove it is zero and has no decoded MIPS memory access.
SAFE_SLACK_BASE = (0x46A5AC, 0x470000)
SLACK_REF_GUARD = 0x100  # preserve +/-256 bytes around any aligned pointer-like target

GETTER_VAS = (0x15EB58, 0x15EB80, 0x15EBA8, 0x15EBD0)
GETTER_LEN = 40
LOADER_CAVE_VA = 0x41285C
LOADER_CAVE_LEN = 36


def off(va: int) -> int:
    return va - VA_DELTA


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_game(text: str, label: str) -> bytes:
    if text == '<EMPTY>':
        text = ''
    if '~' in text:
        raise ValueError(f"{label}: literal '~' is reserved for patched Ü glyph")
    text = text.replace('Ü', '~')
    try:
        return text.encode('cp932', errors='strict')
    except UnicodeEncodeError as e:
        raise ValueError(f'{label}: not representable in patched game font: {text[e.start:e.end]!r}') from e


def decode_cstr(blob: bytes, va: int) -> str:
    o = off(va)
    if not (0 <= o < len(blob)):
        raise ValueError(f'pointer outside executable: {va:#x}')
    e = blob.find(b'\0', o)
    if e < 0:
        raise ValueError(f'unterminated string at {va:#x}')
    return blob[o:e].decode('cp932', errors='strict').replace('~', 'Ü')


def cstr_interval(blob: bytes, va: int) -> tuple[int, int]:
    o = off(va)
    if not (0 <= o < len(blob)):
        raise ValueError(f'pointer outside executable: {va:#x}')
    e = blob.find(b'\0', o)
    if e < 0:
        raise ValueError(f'unterminated string at {va:#x}')
    return va, e + VA_DELTA + 1


def load_rows(path: Path) -> dict[int, dict[str, str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        out = {int(r['master_text_id']): r for r in csv.DictReader(f)}
    if set(out) != set(range(MASTER_COUNT)):
        missing = sorted(set(range(MASTER_COUNT)) - set(out))
        extra = sorted(set(out) - set(range(MASTER_COUNT)))
        raise ValueError(f'master CSV IDs not exactly 0..{MASTER_COUNT-1}; missing={missing[:8]} extra={extra[:8]}')
    return out


def merge_ranges(ranges: list[tuple[int,int]]) -> list[tuple[int,int]]:
    out: list[tuple[int,int]] = []
    for a,z in sorted(ranges):
        if a >= z:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], z))
        else:
            out.append((a,z))
    return out


def subtract_ranges(ranges: list[tuple[int,int]], blocked: list[tuple[int,int]]) -> list[tuple[int,int]]:
    result = []
    for a,z in merge_ranges(ranges):
        cur = [(a,z)]
        for ba,bz in merge_ranges(blocked):
            nxt=[]
            for x,y in cur:
                if bz <= x or ba >= y:
                    nxt.append((x,y)); continue
                if x < ba: nxt.append((x,ba))
                if bz < y: nxt.append((bz,y))
            cur=nxt
        result.extend(cur)
    return merge_ranges(result)


def decoded_mips_memory_refs(src: bytes, a: int, z: int):
    """Conservative local constant-propagation scan over .text/.vutext.

    Finds absolute memory accesses formed from LUI plus ADDIU/DADDIU/ORI and
    load/store offsets. The R6 slack pool is accepted only if this returns none.
    """
    text_a, text_z = 0x100000, 0x439CB0
    mem_ops = {0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,
               0x28,0x29,0x2A,0x2B,0x2E,0x2F,0x31,0x35,0x39,0x3D}
    hits=[]
    for va in range(text_a, text_z, 4):
        w=struct.unpack_from('<I',src,off(va))[0]
        if w>>26 != 0x0F:
            continue
        reg=(w>>16)&31; cur=(w&0xFFFF)<<16
        for step in range(1,13):
            va2=va+step*4
            if va2>=text_z: break
            w2=struct.unpack_from('<I',src,off(va2))[0]
            op=w2>>26; rs=(w2>>21)&31; rt=(w2>>16)&31
            imm=w2&0xFFFF; simm=imm if imm<0x8000 else imm-0x10000
            if op in mem_ops and rs==reg:
                addr=(cur+simm)&0xFFFFFFFF
                if a<=addr<z:
                    hits.append((va,va2,addr,op))
            if rt==reg:
                if op in (0x09,0x19) and rs==reg:
                    cur=(cur+simm)&0xFFFFFFFF
                elif op==0x0D and rs==reg:
                    cur=cur|imm
                elif op==0x0F:
                    cur=imm<<16
                elif op in mem_ops:
                    break
                elif op != 0:
                    break
            if op==0:
                rd=(w2>>11)&31
                if rd==reg and rd!=0:
                    break
    return hits


def verified_slack_segments(src: bytes):
    a,z=SAFE_SLACK_BASE
    o1,o2=off(a),off(z)
    if any(src[o1:o2]):
        raise ValueError(f'R6 slack {a:#x}-{z:#x} is not all zero')
    memrefs=decoded_mips_memory_refs(src,a,z)
    if memrefs:
        raise ValueError(f'R6 slack has decoded MIPS memory refs: {memrefs[:8]}')

    # Full-word values that numerically fall in the zero range can be instruction
    # encodings or packet data rather than pointers. Preserve a guard around every
    # such target anyway, so R6 never writes where even a pointer-like value aims.
    targets=set()
    for o in range(0,len(src)-3,4):
        v=struct.unpack_from('<I',src,o)[0]
        if a<=v<z:
            targets.add(v)
    blocked=[]
    for v in sorted(targets):
        blocked.append((max(a,v-SLACK_REF_GUARD),min(z,v+SLACK_REF_GUARD)))
    segs=subtract_ranges([(a,z)],blocked)
    if not segs:
        raise ValueError('all R6 slack eliminated by conservative pointer guards')
    return segs,sorted(targets),memrefs


def load_race_map(rows: dict[int,dict[str,str]]) -> dict[str,str]:
    m={}
    for r in rows.values():
        roles=set((r.get('roles') or '').split('|'))
        jp=r.get('source_japanese') or ''
        en=r.get('translation') or ''
        if 'race' in roles and jp and en and en != '<EMPTY>':
            m.setdefault(jp,en)
    return m


def patch_races(src: bytes, out: bytearray, rows, changes):
    race_map=load_race_map(rows)
    pto=off(RACE_PTR_TABLE_VA)
    ptrs=struct.unpack_from(f'<{RACE_COUNT}I', src, pto)
    pool=RACE_OVERFLOW_START
    patched=[]
    for i,p in enumerate(ptrs):
        a,z=cstr_interval(src,p); old=src[off(a):off(z)]
        jp=old[:-1].decode('cp932')
        en=race_map.get(jp)
        if not en:
            raise ValueError(f'no canonical race translation for table row {i}: {jp!r}')
        enc=encode_game(en,f'race[{i}]')+b'\0'
        final_ptr=p
        if len(enc) <= len(old):
            rep=enc+b'\0'*(len(old)-len(enc))
            if rep != old:
                out[off(a):off(z)] = rep
                changes.append((off(a),off(z),f'race string {i}: {jp} -> {en}'))
        else:
            pool=(pool+3)&~3
            if pool+len(enc)>RACE_OVERFLOW_LIMIT:
                raise ValueError('race overflow pool exhausted')
            po=off(pool)
            if any(src[po:po+len(enc)]):
                raise ValueError(f'race overflow destination not zero: {pool:#x}')
            out[po:po+len(enc)]=enc
            changes.append((po,po+len(enc),f'race overflow {i}: {en}'))
            q=pto+i*4
            out[q:q+4]=struct.pack('<I',pool)
            changes.append((q,q+4,f'race pointer {i} -> {pool:#x}'))
            final_ptr=pool; pool += len(enc)
        patched.append((i,final_ptr,jp,en))
    return patched,pool


def build_safe_rule_pool(src: bytes, ptrs: tuple[int,...], rule_ids: list[int]):
    rule_set=set(rule_ids)
    # Exact original rule intervals; CSV/source equality is verified by caller.
    ivals={p:cstr_interval(src,p) for p in sorted({ptrs[i] for i in rule_ids})}
    ranges=sorted(ivals.values())
    starts=[a for a,_ in ranges]
    def containing(v:int):
        k=bisect.bisect_right(starts,v)-1
        if k>=0 and v<ranges[k][1]: return ranges[k]
        return None

    blocked=set()
    reasons=[]
    # Any non-rule master pointer into a rule string means the source interval is shared.
    for i,p in enumerate(ptrs):
        if i in rule_set: continue
        q=containing(p)
        if q:
            blocked.add(q[0]); reasons.append(('nonrule_master',i,p,q))

    # Any other aligned pointer into a rule interval also conservatively blocks it.
    # Rule master table slots themselves are expected and excluded.
    table_o=off(MASTER_TABLE_VA)
    rule_slots={table_o+i*4 for i in rule_ids}
    for o in range(0,len(src)-3,4):
        if o in rule_slots: continue
        v=struct.unpack_from('<I',src,o)[0]
        q=containing(v)
        if q:
            blocked.add(q[0]); reasons.append(('other_ptr',o+VA_DELTA,v,q))

    free=[iv for p,iv in ivals.items() if p not in blocked]
    # Never use reserved data even if an interval somehow overlaps it.
    free=subtract_ranges(free,RESERVED_DATA)
    slack,slack_targets,slack_memrefs=verified_slack_segments(src)
    pool=merge_ranges(free+slack)
    return pool, blocked, reasons, ivals, slack, slack_targets, slack_memrefs


def allocate_dedup(texts: dict[bytes,list[int]], pool: list[tuple[int,int]]):
    segments=[[a,z] for a,z in pool]
    alloc={}
    # Best-fit decreasing is deterministic and keeps small source slots usable.
    for raw,ids in sorted(texts.items(), key=lambda kv:(-len(kv[0]), kv[0])):
        candidates=[(z-a,k,a) for k,(a,z) in enumerate(segments) if z-a>=len(raw)]
        if not candidates:
            raise ValueError(f'not enough safe embedded space for rule IDs {ids[:8]} ({len(raw)} bytes)')
        _,k,_=min(candidates)
        a,z=segments[k]
        alloc[raw]=a
        segments[k][0]=a+len(raw)
    return alloc,segments


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('input_elf',type=Path)
    ap.add_argument('master_csv',type=Path)
    ap.add_argument('output_elf',type=Path)
    ap.add_argument('--report',type=Path)
    args=ap.parse_args()

    src=args.input_elf.read_bytes()
    if sha256(src)!=EXPECTED_SHA:
        raise SystemExit(f'ERROR: input must be accepted UI68 baseline; got {sha256(src)} expected {EXPECTED_SHA}')
    rows=load_rows(args.master_csv)
    table_o=off(MASTER_TABLE_VA)
    ptrs=struct.unpack_from(f'<{MASTER_COUNT}I',src,table_o)
    rule_ids=sorted(i for i,r in rows.items() if 'rules' in set((r.get('roles') or '').split('|')))
    if len(rule_ids)!=654:
        raise ValueError(f'expected 654 rules rows, got {len(rule_ids)}')

    # Prove the baseline embedded rules are exactly the canonical Japanese source.
    for i in rule_ids:
        got=decode_cstr(src,ptrs[i])
        expected=rows[i].get('source_japanese') or ''
        if got!=expected:
            raise ValueError(f'embedded source mismatch at rule ID {i}: {got!r} != {expected!r}')
        if not rows[i].get('translation'):
            raise ValueError(f'rule ID {i} lacks English translation')

    # Snapshot code that MUST remain exactly accepted UI68.
    protected={va:src[off(va):off(va)+GETTER_LEN] for va in GETTER_VAS}
    protected[LOADER_CAVE_VA]=src[off(LOADER_CAVE_VA):off(LOADER_CAVE_VA)+LOADER_CAVE_LEN]
    nonrule_ptrs={i:ptrs[i] for i in range(MASTER_COUNT) if i not in set(rule_ids)}

    pool,blocked,reasons,ivals,slack,slack_targets,slack_memrefs=build_safe_rule_pool(src,ptrs,rule_ids)
    if not pool:
        raise ValueError('no safe rule repack pool')

    id_raw={}
    dedup={}
    for i in rule_ids:
        text=rows[i]['translation']
        raw=encode_game(text,f'rule[{i}]')+b'\0'
        id_raw[i]=raw; dedup.setdefault(raw,[]).append(i)
    alloc,left=allocate_dedup(dedup,pool)

    out=bytearray(src); changes=[]
    # Clear only reclaimable *original rule-string* intervals, not generic zero slack.
    safe_rule_intervals=[iv for p,iv in ivals.items() if p not in blocked]
    safe_rule_intervals=subtract_ranges(safe_rule_intervals,RESERVED_DATA)
    for a,z in safe_rule_intervals:
        o1,o2=off(a),off(z)
        if any(out[o1:o2]):
            out[o1:o2]=b'\0'*(o2-o1)
            changes.append((o1,o2,f'reclaim embedded Japanese rule pool {a:#x}-{z:#x}'))

    # Materialize each unique English rule once.
    for raw,va in sorted(alloc.items(), key=lambda kv:kv[1]):
        o=off(va)
        out[o:o+len(raw)]=raw
        changes.append((o,o+len(raw),f'English rule text at {va:#x}'))

    # Retarget only the 654 rule master slots.
    for i in rule_ids:
        va=alloc[id_raw[i]]
        q=table_o+i*4
        out[q:q+4]=struct.pack('<I',va)
        changes.append((q,q+4,f'master rule pointer {i} -> {va:#x}'))

    # Retain the established independent race enum localization.
    race_rows,race_pool_end=patch_races(src,out,rows,changes)

    result=bytes(out)
    if len(result)!=len(src): raise RuntimeError('executable size changed')

    # Code/lifecycle regression guards.
    for va,blob in protected.items():
        if result[off(va):off(va)+len(blob)]!=blob:
            raise RuntimeError(f'protected UI68 code changed at {va:#x}')

    # Non-rule master pointers are untouchable.
    new_ptrs=struct.unpack_from(f'<{MASTER_COUNT}I',result,table_o)
    for i,p in nonrule_ptrs.items():
        if new_ptrs[i]!=p:
            raise RuntimeError(f'non-rule master pointer changed at ID {i}')

    # Every embedded rule now resolves exactly to canonical English.
    for i in rule_ids:
        got=decode_cstr(result,new_ptrs[i])
        exp=rows[i]['translation']
        if got!=exp:
            raise RuntimeError(f'English embedded rule verify failed at {i}: {got!r} != {exp!r}')

    # Race table must decode to canonical English after patching.
    race_ptrs=struct.unpack_from(f'<{RACE_COUNT}I',result,off(RACE_PTR_TABLE_VA))
    race_map=load_race_map(rows)
    for i,p in enumerate(race_ptrs):
        got=decode_cstr(result,p)
        # Original JP text identifies expected row even when the pointer moved.
        op=struct.unpack_from('<I',src,off(RACE_PTR_TABLE_VA)+i*4)[0]
        jp=decode_cstr(src,op)
        if got!=race_map[jp]:
            raise RuntimeError(f'race verify failed row {i}: {got!r}')

    # Strict diff containment: every byte difference must lie in a declared range.
    allowed=bytearray(len(src))
    for a,z,_ in changes: allowed[a:z]=b'\1'*(z-a)
    diffs=[i for i,(a,b) in enumerate(zip(src,result)) if a!=b]
    bad=[i for i in diffs if not allowed[i]]
    if bad: raise RuntimeError(f'unexpected diff offsets: {bad[:20]}')

    # Canary checks from runtime screenshots/handoff.
    canaries={139:'Bolshack Dragon',251:'Barkwhip, the Smasher'}
    for rid,name in canaries.items():
        if decode_cstr(result,new_ptrs[rid])!=rows[rid]['translation']:
            raise RuntimeError(f'{name} rule canary failed')

    args.output_elf.write_bytes(result)
    free_left=sum(z-a for a,z in left)
    safe_rule_bytes=sum(z-a for a,z in safe_rule_intervals)
    report=[
        'UI76 R7 EMBEDDED ENGLISH SPECIAL-ABILITY PATCH',
        f'input_sha256={sha256(src)}',
        f'output_sha256={sha256(result)}',
        f'file_size={len(result)}',
        f'differing_bytes={len(diffs)}',
        '',
        'Runtime-regression containment:',
        '  CardText Name getter 0x15EB58: byte-identical to accepted UI68',
        '  CardText Rules getter 0x15EB80: byte-identical to accepted UI68',
        '  CardText Flavor getter 0x15EBA8: byte-identical to accepted UI68',
        '  CardText Race getter 0x15EBD0: byte-identical to accepted UI68',
        '  LIST loader cave 0x41285C: byte-identical to accepted UI68',
        '  No gp+0x2038 getter redirection; no R5 helper/snapshot runtime hook.',
        '',
        'Embedded rules:',
        f'  rule master IDs={len(rule_ids)}',
        f'  unique original rule strings={len(ivals)}',
        f'  conservatively blocked source intervals={len(blocked)}',
        f'  safe reclaimed original-rule bytes={safe_rule_bytes}',
        f'  unique English rule strings={len(dedup)}',
        f'  unique English encoded bytes={sum(len(x) for x in dedup)}',
        f'  safe allocation pool bytes={sum(z-a for a,z in pool)}',
        f'  guarded zero-slack segments={len(slack)} bytes={sum(z-a for a,z in slack)}',
        f'  pointer-like slack targets guarded={len(slack_targets)}: ' + ', '.join(hex(x) for x in slack_targets),
        f'  decoded MIPS memory accesses into slack={len(slack_memrefs)}',
        f'  allocation bytes remaining={free_left}',
        '  Every one of the 654 rule pointers decodes exactly to canonical English.',
        '  All 1,722 non-rule master pointers remain byte-identical.',
        '',
        f'Legacy race table rows localized={len(race_rows)}',
        f'Race overflow pool end={race_pool_end:#x} (limit {RACE_OVERFLOW_LIMIT:#x})',
        '',
        f'Bolshack rule ID 139 -> {decode_cstr(result,new_ptrs[139])}',
        f'Barkwhip rule ID 251 -> {decode_cstr(result,new_ptrs[251])}',
        '',
        'VERIFICATION: PASS',
    ]
    if reasons:
        report += ['', 'Conservatively blocked original rule intervals (reference summary):',
                   f'  reference records={len(reasons)}; unique intervals={len(blocked)}']
    txt='\n'.join(report)+'\n'
    if args.report: args.report.write_text(txt,encoding='utf-8')
    print(txt,end='')

if __name__=='__main__': main()
