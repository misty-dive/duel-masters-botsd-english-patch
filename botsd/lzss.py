from __future__ import annotations

from collections import defaultdict, deque

from .errors import FormatError, VerificationError

WINDOW = 0x1000
RING_START = 0xFEE
MAX_MATCH = 18


def decompress(stream: bytes, expected_size: int) -> bytes:
    ring = bytearray(WINDOW)
    ring_pos = RING_START
    src = 0
    out = bytearray()
    flags = 0
    while src < len(stream):
        flags >>= 1
        if not (flags & 0x100):
            flags = stream[src] | 0xFF00
            src += 1
        if flags & 1:
            if src >= len(stream):
                break
            value = stream[src]
            src += 1
            out.append(value)
            ring[ring_pos] = value
            ring_pos = (ring_pos + 1) & 0xFFF
        else:
            if src + 1 >= len(stream):
                break
            b1 = stream[src]
            b2 = stream[src + 1]
            src += 2
            offset = b1 | ((b2 & 0xF0) << 4)
            count = (b2 & 0x0F) + 3
            for k in range(count):
                value = ring[(offset + k) & 0xFFF]
                out.append(value)
                ring[ring_pos] = value
                ring_pos = (ring_pos + 1) & 0xFFF
    if len(out) != expected_size:
        raise FormatError(f"LZSS output length mismatch: expected {expected_size}, got {len(out)}")
    return bytes(out)


def _candidate_match(data: bytes, pos: int, source: int) -> int:
    # Historical fast encoder behavior: deliberately avoids overlap matches.
    limit = min(MAX_MATCH, len(data) - pos, pos - source)
    length = 0
    while length < limit and data[source + length] == data[pos + length]:
        length += 1
    return length


def compress(data: bytes, max_candidates: int = 96) -> bytes:
    """Fast bounded-search encoder for the game's 4 KiB-window LZSS stream.

    ``max_candidates`` is an immutable per-token search limit. The historical tool
    accidentally mutated the caller's value and reset it to 96 after the first search.
    """
    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")

    recent: dict[bytes, deque[int]] = defaultdict(deque)
    out = bytearray()
    pos = 0

    def add_pos(p: int) -> None:
        if p + 2 >= len(data):
            return
        key = data[p : p + 3]
        queue = recent[key]
        queue.append(p)
        cutoff = p - WINDOW
        while queue and queue[0] < cutoff:
            queue.popleft()
        while len(queue) > 256:
            queue.popleft()

    while pos < len(data):
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if pos >= len(data):
                break
            best_len = 0
            best_source = -1
            if pos + 2 < len(data):
                queue = recent.get(data[pos : pos + 3])
                if queue:
                    searched = 0
                    for source in reversed(queue):
                        if pos - source > WINDOW:
                            break
                        length = _candidate_match(data, pos, source)
                        if length > best_len:
                            best_len = length
                            best_source = source
                            if length == MAX_MATCH:
                                break
                        searched += 1
                        if searched >= max_candidates:
                            break
            if best_len >= 3:
                ring_offset = (RING_START + best_source) & 0xFFF
                out.append(ring_offset & 0xFF)
                out.append(((ring_offset >> 4) & 0xF0) | ((best_len - 3) & 0x0F))
                old = pos
                pos += best_len
                for p in range(old, pos):
                    add_pos(p)
            else:
                flags |= 1 << bit
                out.append(data[pos])
                add_pos(pos)
                pos += 1
        out[flag_pos] = flags

    encoded = bytes(out)
    if decompress(encoded, len(data)) != data:
        raise VerificationError("internal LZSS round-trip verification failed")
    return encoded


def _optimal_match_table(data: bytes, max_candidates: int = 256) -> tuple[list[int], list[int]]:
    """Find longest overlap-capable matches for the fixed-allocation encoder."""
    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")
    size = len(data)
    recent: dict[bytes, deque[int]] = defaultdict(deque)
    lengths = [0] * size
    sources = [-1] * size
    for pos in range(size):
        if pos + 2 < size:
            key = data[pos : pos + 3]
            queue = recent.get(key)
            if queue:
                searched = 0
                for source in reversed(queue):
                    distance = pos - source
                    if distance > WINDOW:
                        break
                    limit = min(MAX_MATCH, size - pos)
                    length = 0
                    while length < limit:
                        src_value = (
                            data[source + length]
                            if length < distance
                            else data[pos + length - distance]
                        )
                        if src_value != data[pos + length]:
                            break
                        length += 1
                    if length > lengths[pos]:
                        lengths[pos] = length
                        sources[pos] = source
                    if length == MAX_MATCH:
                        break
                    searched += 1
                    if searched >= max_candidates:
                        break
            queue = recent[key]
            queue.append(pos)
            cutoff = pos - WINDOW
            while queue and queue[0] < cutoff:
                queue.popleft()
    return lengths, sources


def compress_optimal(data: bytes, max_candidates: int = 256) -> bytes:
    """Overlap-capable dynamic-programming encoder used for fixed-size UI allocations."""
    lengths, sources = _optimal_match_table(data, max_candidates)
    size = len(data)
    # dp[pos][slot] = minimum encoded bytes remaining when next token uses flag slot 0..7.
    dp = [[0] * 8 for _ in range(size + 1)]
    choice: list[list[tuple[str, int, int] | None]] = [[None] * 8 for _ in range(size)]
    for pos in range(size - 1, -1, -1):
        for slot in range(8):
            overhead = 1 if slot == 0 else 0
            next_slot = (slot + 1) & 7
            best = overhead + 1 + dp[pos + 1][next_slot]
            pick = ("L", 1, -1)
            if lengths[pos] >= 3:
                source = sources[pos]
                for length in range(3, lengths[pos] + 1):
                    cost = overhead + 2 + dp[pos + length][next_slot]
                    if cost < best:
                        best = cost
                        pick = ("M", length, source)
            dp[pos][slot] = best
            choice[pos][slot] = pick

    out = bytearray()
    pos = 0
    slot = 0
    flag_pos = 0
    flags = 0
    while pos < size:
        if slot == 0:
            flag_pos = len(out)
            out.append(0)
            flags = 0
        selected = choice[pos][slot]
        if selected is None:
            raise VerificationError("missing optimal LZSS parse decision")
        kind, length, source = selected
        if kind == "L":
            flags |= 1 << slot
            out.append(data[pos])
            pos += 1
        else:
            ring_offset = (RING_START + source) & 0xFFF
            out.append(ring_offset & 0xFF)
            out.append(((ring_offset >> 4) & 0xF0) | ((length - 3) & 0x0F))
            pos += length
        slot = (slot + 1) & 7
        if slot == 0:
            out[flag_pos] = flags
    if slot:
        out[flag_pos] = flags

    encoded = bytes(out)
    if decompress(encoded, len(data)) != data:
        raise VerificationError("optimal LZSS round-trip verification failed")
    return encoded
