#!/usr/bin/env python3
"""
Download N03 (Administrative Areas) GML zip files from NLNI.

This pulls the latest N03 dataset list from the official data list page
and downloads all zip files under the specified year directory.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path
from typing import Iterable, List


def _fetch_html(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_zip_paths(html: str, year: str) -> List[str]:
    pattern = rf"\.\./data/N03/N03-{re.escape(year)}/[^'\s]+\.zip"
    paths = sorted(set(re.findall(pattern, html)))
    return paths


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    with urllib.request.urlopen(url, timeout=60) as resp:
        dest.write_bytes(resp.read())


def _iter_paths(paths: List[str], limit: int | None) -> Iterable[str]:
    if limit is None:
        return paths
    return paths[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Download N03 GML zip files.")
    parser.add_argument(
        "--year",
        default="2025",
        help="Data year directory (default: 2025).",
    )
    parser.add_argument(
        "--list-url",
        default="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2025.html",
        help="N03 data list page URL.",
    )
    parser.add_argument(
        "--output-dir",
        default="backend/data/n03/2025",
        help="Output directory for zip files.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of files to download (for testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print URLs without downloading.",
    )
    parser.add_argument(
        "--include-full",
        action="store_true",
        help="Include the full nationwide zip (N03-YYYY0101_GML.zip).",
    )

    args = parser.parse_args()

    html = _fetch_html(args.list_url)
    paths = _extract_zip_paths(html, args.year)

    if not paths:
        print("No zip paths found. Check year or list URL.", file=sys.stderr)
        return 1

    base = "https://nlftp.mlit.go.jp/ksj/gml/"
    output_dir = Path(args.output_dir)

    full_name = f"N03-{args.year}0101_GML.zip"

    for rel_path in _iter_paths(paths, args.limit):
        url = base + rel_path.lstrip("./")
        dest = output_dir / Path(rel_path).name
        if not args.include_full and dest.name == full_name:
            continue
        if args.dry_run:
            print(url)
            continue
        print(f"Downloading {url} -> {dest}")
        _download(url, dest)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
