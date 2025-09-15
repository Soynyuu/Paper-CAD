"""
Quick test for CityGML→STEP pipeline.

Run:
  python test_citygml_to_step.py \
    --input samples/minimal_building.gml \
    --output output/minimal_building.step

Note: .step is git-ignored by default.
"""

from __future__ import annotations

import argparse
import os

from services.citygml_to_step import export_step_from_citygml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="samples/minimal_building.gml")
    parser.add_argument("--output", default="output/minimal_building.step")
    parser.add_argument("--default-height", type=float, default=10.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    ok, msg = export_step_from_citygml(
        args.input,
        args.output,
        default_height=args.default_height,
        limit=args.limit,
        debug=args.debug,
    )
    print("success" if ok else "failed", "-", msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

