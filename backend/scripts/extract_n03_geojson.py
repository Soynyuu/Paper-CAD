#!/usr/bin/env python3
"""
Extract GeoJSON files from N03 zip archives.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract N03 GeoJSON files from zip archives.")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing N03 zip files.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write extracted GeoJSON files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing GeoJSON files.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_paths = sorted(input_dir.glob("*.zip"))
    if not zip_paths:
        raise SystemExit(f"No zip files found in {input_dir}")

    extracted = 0
    for zip_path in zip_paths:
        with ZipFile(zip_path) as zf:
            for member in zf.namelist():
                if not member.lower().endswith(".geojson"):
                    continue
                target = output_dir / Path(member).name
                if target.exists() and not args.overwrite:
                    continue
                with zf.open(member) as src:
                    target.write_bytes(src.read())
                extracted += 1

    print(f"Extracted {extracted} GeoJSON files to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
