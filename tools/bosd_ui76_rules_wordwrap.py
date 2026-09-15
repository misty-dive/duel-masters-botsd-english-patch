#!/usr/bin/env python3
"""Pre-wrap English card rules on word boundaries for BOTSD Card Info.

BOTSD's retail rule renderer wraps by glyph advance, not English word boundaries,
so long English strings can split words ("sum"/"moning", "o"/"pponent").
This pass inserts explicit LF bytes *only in place of existing ASCII spaces*.
That keeps every string byte length unchanged while ensuring no emitted line exceeds
24 half-width cells (the measured safe capacity of the retail Card Info panel).

Width model for the canonical English rules used here:
  ASCII character = 1 cell
  BLACK SQUARE '■' = 2 cells
No other non-ASCII character occurs in the 654 rule translations.
"""
from pathlib import Path
import argparse,csv,hashlib,re
MAX_CELLS=24

def cells(s:str)->int:
    return sum(1 if ord(c)<128 else 2 for c in s)

def wrap_para(p:str)->str:
    """Replace selected existing spaces with LF; never insert/delete bytes."""
    if not p: return p
    chars=list(p)
    words=list(re.finditer(r'[^ ]+',p))
    if any(cells(m.group())>MAX_CELLS for m in words):
        bad=[m.group() for m in words if cells(m.group())>MAX_CELLS]
        raise ValueError(f'token longer than panel width: {bad!r}')
    line_start=0
    prev=None
    for m in words:
        # If including this whole word would exceed the measured line capacity,
        # break at the first separator space before this word.  Internal rule
        # spacing is overwhelmingly one byte; choosing the first preserves the
        # previous line without trailing-space width.
        if prev is not None and cells(p[line_start:m.end()])>MAX_CELLS:
            sep_start=prev.end()
            sep_end=m.start()
            if sep_start>=sep_end or p[sep_start:sep_end].strip(' '):
                raise ValueError('expected ASCII-space separator')
            br=sep_start
            chars[br]='\n'
            line_start=br+1
            # Remaining spaces in a rare multi-space separator become leading
            # indentation and are counted by the next capacity check.
            if cells(p[line_start:m.end()])>MAX_CELLS:
                raise ValueError(f'word plus preserved indentation exceeds width: {m.group()!r}')
        prev=m
    out=''.join(chars)
    if len(out)!=len(p): raise AssertionError('wrap changed character count')
    for a,b in zip(p,out):
        if a!=b and not (a==' ' and b=='\n'):
            raise AssertionError((a,b))
    return out

def wrap_text(t:str)->str:
    return '\n'.join(wrap_para(p) for p in t.split('\n'))

def norm_ws(t:str)->str:
    return ' '.join(t.split())

def sha_file(p:Path)->str:
    h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()

def read_rows(p:Path):
    with p.open('r',encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f);return r.fieldnames,list(r)

def write_rows(p:Path,fields,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();
    ap.add_argument('--master-in',type=Path,required=True);ap.add_argument('--display-in',type=Path,required=True)
    ap.add_argument('--master-out',type=Path,required=True);ap.add_argument('--display-out',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    mf,mrows=read_rows(a.master_in);df,drows=read_rows(a.display_in)
    rules={}
    inserted=0; changed=0; max_before=0; max_after=0; line_counts=[]
    for r in mrows:
        roles=set((r.get('roles') or '').split('|'))
        if 'rules' not in roles: continue
        mid=int(r['master_text_id']);t=r.get('translation','')
        if not t or t=='<EMPTY>': raise ValueError(f'rule {mid} missing English translation')
        # Current project rules contain only ASCII plus BLACK SQUARE.
        bad=sorted({c for c in t if ord(c)>=128 and c!='■'})
        if bad: raise ValueError(f'rule {mid} unsupported width chars {bad!r}')
        before_lines=t.split('\n'); max_before=max(max_before,max(cells(x) for x in before_lines))
        w=wrap_text(t)
        if len(w.encode('cp932'))!=len(t.encode('cp932')):
            raise ValueError(f'rule {mid}: byte length changed')
        if norm_ws(w)!=norm_ws(t): raise ValueError(f'rule {mid}: semantic token stream changed')
        after_lines=w.split('\n'); ma=max(cells(x) for x in after_lines) if after_lines else 0
        if ma>MAX_CELLS: raise ValueError(f'rule {mid}: wrapped line still too wide: {ma}')
        max_after=max(max_after,ma); inserted += w.count('\n')-t.count('\n')
        if w!=t: changed+=1
        r['translation']=w;rules[mid]=w;line_counts.append(len(after_lines))
    if len(rules)!=654: raise ValueError(f'expected 654 rules, got {len(rules)}')

    display_rule_rows=0
    for r in drows:
        mid=(r.get('master_text_id') or '').strip()
        if mid and int(mid) in rules:
            r['translation']=rules[int(mid)];display_rule_rows+=1
    write_rows(a.master_out,mf,mrows);write_rows(a.display_out,df,drows)

    # Round-trip and prove no non-rule master translation changed.
    _,chk=read_rows(a.master_out)
    cin={int(r['master_text_id']):r for r in csv.DictReader(a.master_in.open(encoding='utf-8-sig',newline=''))}
    cout={int(r['master_text_id']):r for r in chk}
    for mid in range(len(chk)):
        isrule=mid in rules
        if not isrule and cout[mid].get('translation','')!=cin[mid].get('translation',''):
            raise ValueError(f'non-rule translation changed: {mid}')
        if isrule and cout[mid]['translation']!=rules[mid]: raise ValueError(f'roundtrip mismatch rule {mid}')

    lines=[
      'UI76 R7 CARD RULE WORD-WRAP: PASS',f'max_cells={MAX_CELLS}',f'rules_verified={len(rules)}',
      f'rules_with_added_wraps={changed}',f'new_linebreaks_inserted={inserted}',f'display_rows_synchronized={display_rule_rows}',
      f'max_line_cells_before={max_before}',f'max_line_cells_after={max_after}',
      f'max_wrapped_lines_per_rule={max(line_counts)}',f'master_out_sha256={sha_file(a.master_out)}',f'display_out_sha256={sha_file(a.display_out)}',
      'All inserted line breaks replace existing ASCII spaces; encoded rule byte lengths are unchanged.',
      'No non-rule master translation is modified.'
    ]
    txt='\n'.join(lines)+'\n';print(txt,end='');a.report.write_text(txt,encoding='utf-8')
if __name__=='__main__':main()
