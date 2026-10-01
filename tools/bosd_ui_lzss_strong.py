#!/usr/bin/env python3
"""Compatibility wrapper for the shared overlap-capable BOTSD LZSS encoder."""
from pathlib import Path

import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from botsd.lzss import _optimal_match_table as _max_matches
from botsd.lzss import compress_optimal as compress

__all__ = ["compress", "_max_matches"]
