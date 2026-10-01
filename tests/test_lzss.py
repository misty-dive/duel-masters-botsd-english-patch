import random

import pytest

from botsd.lzss import compress, decompress


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"hello world",
        b"A" * 1024,
        (b"abc123" * 800) + b"tail",
        bytes(range(256)) * 8,
    ],
)
def test_roundtrip(data: bytes):
    encoded = compress(data)
    assert decompress(encoded, len(data)) == data


def test_roundtrip_deterministic_random_payload():
    rng = random.Random(65882)
    data = bytes(rng.randrange(256) for _ in range(8192))
    assert decompress(compress(data, max_candidates=1), len(data)) == data
    assert decompress(compress(data, max_candidates=7), len(data)) == data


def test_candidate_limit_validation():
    with pytest.raises(ValueError):
        compress(b"abc", max_candidates=0)


def test_optimal_encoder_roundtrip_and_not_worse_on_repetition():
    from botsd.lzss import compress_optimal

    data = (b"BOTSD-" * 1000) + (b"A" * 5000)
    fast = compress(data)
    optimal = compress_optimal(data)
    assert decompress(optimal, len(data)) == data
    assert len(optimal) <= len(fast)
