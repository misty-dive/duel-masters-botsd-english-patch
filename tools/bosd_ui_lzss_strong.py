#!/usr/bin/env python3
"""Stronger BOSD UI-LZSS encoder for fixed-allocation patches.

The retail decoder supports overlapping 4 KiB-window matches. The original project encoder
intentionally avoided overlap and used a greedy parse because relocated archives were allowed.
This module instead computes valid overlap matches and a dynamic-programming token parse while
preserving the exact retail bitstream format. Every caller must self-decompress/verify output.
"""
from collections import defaultdict,deque

def _max_matches(data:bytes,max_candidates:int=256):
    n=len(data)
    recent=defaultdict(deque)
    L=[0]*n
    Q=[-1]*n
    for pos in range(n):
        if pos+2<n:
            key=data[pos:pos+3]
            dq=recent.get(key)
            if dq:
                cnt=0
                for q in reversed(dq):
                    d=pos-q
                    if d>0x1000:
                        break
                    lim=min(18,n-pos)
                    k=0
                    while k<lim:
                        src=data[q+k] if k<d else data[pos+k-d]
                        if src!=data[pos+k]:
                            break
                        k+=1
                    if k>L[pos]:
                        L[pos]=k
                        Q[pos]=q
                    if k==18:
                        break
                    cnt+=1
                    if cnt>=max_candidates:
                        break
            dq=recent[key]
            dq.append(pos)
            cut=pos-0x1000
            while dq and dq[0]<cut:
                dq.popleft()
    return L,Q

def compress(data:bytes,max_candidates:int=256)->bytes:
    L,Q=_max_matches(data,max_candidates)
    n=len(data)
    # dp[pos][k] = minimum remaining encoded bytes when the next token is slot k of an 8-token flag group.
    dp=[[0]*8 for _ in range(n+1)]
    choice=[[None]*8 for _ in range(n)]
    for pos in range(n-1,-1,-1):
        for k in range(8):
            overhead=1 if k==0 else 0
            nk=(k+1)&7
            best=overhead+1+dp[pos+1][nk]
            pick=('L',1,-1)
            ml=L[pos]
            if ml>=3:
                q=Q[pos]
                for ln in range(3,ml+1):
                    c=overhead+2+dp[pos+ln][nk]
                    if c<best:
                        best=c
                        pick=('M',ln,q)
            dp[pos][k]=best
            choice[pos][k]=pick
    out=bytearray()
    pos=0
    k=0
    while pos<n:
        if k==0:
            flag_pos=len(out)
            out.append(0)
            flags=0
        typ,ln,q=choice[pos][k]
        if typ=='L':
            flags|=1<<k
            out.append(data[pos])
            pos+=1
        else:
            ro=(0xFEE+q)&0xFFF
            out.append(ro&0xFF)
            out.append(((ro>>4)&0xF0)|((ln-3)&0x0F))
            pos+=ln
        k=(k+1)&7
        if k==0:
            out[flag_pos]=flags
    if k:
        out[flag_pos]=flags
    return bytes(out)
