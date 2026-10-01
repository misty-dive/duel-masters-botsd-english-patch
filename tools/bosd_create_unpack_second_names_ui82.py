#!/usr/bin/env python3
"""Create the deterministic UI82 677-chunk second-card-sprite patch ZIP.

The generated archive is consumed by ``bosd_apply_unpack_second_names_ui82.py``.  It packages
only the UI76->UI82 delta and proves that the delta is exactly chunks 2037..2713.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botsd.unpack import create_second_name_patch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retail", type=Path)
    parser.add_argument("ui76", type=Path)
    parser.add_argument("ui82", type=Path)
    parser.add_argument("output_zip", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--allow-nonretail", action="store_true")
    args = parser.parse_args()
    result = create_second_name_patch(
        args.retail,
        args.ui76,
        args.ui82,
        args.output_zip,
        inventory=args.inventory,
        verify_retail=not args.allow_nonretail,
    )
    print("UI82 SECOND-SPRITE PATCH CREATE: PASS")
    print(f"output={args.output_zip}")
    print(f"payload_chunks={len(result.changed_chunks)}")
    print(f"retail_sha256={result.retail_sha256}")
    print(f"ui82_sha256={result.target_sha256}")


if __name__ == "__main__":
    main()
