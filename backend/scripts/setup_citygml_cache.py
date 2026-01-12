#!/usr/bin/env python3
"""
CityGML Cache Setup Script for Tokyo 23 Wards

This script downloads and caches CityGML data for all 23 wards of Tokyo
to enable 10-50x faster processing for PLATEAU data.

Usage:
    python setup_citygml_cache.py [--skip-existing] [--cache-dir PATH] [--datasets-json PATH]

Requirements:
    - 5GB+ free disk space
    - Stable internet connection (30-60 min download time)
"""

import argparse
import json
import os
import shutil
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
from tqdm import tqdm


def check_disk_space(cache_dir: Path, required_gb: float = 5.0) -> bool:
    """Check if there's enough disk space available."""
    check_path = cache_dir.parent
    while not check_path.exists() and check_path != check_path.parent:
        check_path = check_path.parent
    stat = shutil.disk_usage(check_path)
    available_gb = stat.free / (1024 ** 3)

    print(f"Checking disk space...")
    if available_gb < required_gb:
        print(f"ERROR: {required_gb}GB required, but only {available_gb:.1f}GB available")
        return False

    print(f"✓ {available_gb:.1f} GB available")
    return True


def load_tokyo23_datasets(json_path: str = "tokyo23_datasets.json") -> List[Dict]:
    """Load pre-generated dataset information."""
    if not os.path.exists(json_path):
        print(f"ERROR: Dataset file not found: {json_path}")
        print("Please ensure tokyo23_datasets.json exists in the current directory.")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        datasets = json.load(f)

    print(f"Loading Tokyo 23 wards dataset information...")
    print(f"Found {len(datasets)} wards")
    return datasets


def download_ward_zip(
    open_data_url: str,
    output_path: Path,
    retry: int = 3
) -> bool:
    """
    Download ZIP file with exponential backoff retry.

    Args:
        open_data_url: URL to download
        output_path: Path to save the downloaded file
        retry: Number of retry attempts

    Returns:
        True if download succeeded, False otherwise
    """
    for attempt in range(1, retry + 1):
        try:
            response = requests.get(open_data_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(output_path, 'wb') as f:
                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    desc=f"  Downloading"
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            return True

        except requests.RequestException as e:
            if attempt == retry:
                print(f"  ERROR: Failed after {retry} attempts: {e}")
                raise

            wait_time = 5 * attempt
            print(f"  [Retry {attempt}/{retry}] Error: {e}")
            print(f"  Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

    return False


def validate_zip(zip_path: Path) -> bool:
    """Validate ZIP file integrity."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad_file = zf.testzip()
            return bad_file is None
    except zipfile.BadZipFile:
        return False


def extract_and_analyze_ward(
    zip_path: Path,
    extract_dir: Path,
    area_code: str
) -> Dict:
    """
    Extract ZIP and analyze mesh codes from filenames.

    Args:
        zip_path: Path to ZIP file
        extract_dir: Directory to extract to
        area_code: Ward area code (e.g., "13101")

    Returns:
        Dict with file_count, size_bytes, and mesh_codes
    """
    print(f"  Extracting...")

    # Validate ZIP
    if not validate_zip(zip_path):
        raise ValueError(f"ZIP file is corrupted: {zip_path}")

    # Extract
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_dir)

    # Find GML files (building data only)
    gml_files = list(extract_dir.rglob('udx/bldg/*.gml'))

    # Remove non-building data to save disk space
    udx_dir = extract_dir / "udx"
    if udx_dir.exists():
        for subdir in udx_dir.iterdir():
            if subdir.is_dir() and subdir.name != "bldg":
                shutil.rmtree(subdir)
                print(f"  Removed udx/{subdir.name}/ (not needed)")

    # Extract mesh codes from filenames
    # Format: {mesh_code}_bldg_*.gml (e.g., "53393580_bldg_6697_op.gml")
    mesh_codes: Set[str] = set()
    for gml_file in gml_files:
        filename = gml_file.name
        parts = filename.split('_')
        if len(parts) >= 3 and parts[1] == 'bldg':
            mesh_code = parts[0]
            mesh_codes.add(mesh_code)

    # Calculate total size
    total_size = sum(f.stat().st_size for f in extract_dir.rglob('*.gml'))

    return {
        "file_count": len(gml_files),
        "size_bytes": total_size,
        "mesh_codes": sorted(list(mesh_codes))
    }


def build_mesh_to_ward_index(global_metadata: Dict) -> Dict:
    """
    Build O(1) mesh→ward mapping from global metadata.

    Args:
        global_metadata: Global metadata dictionary

    Returns:
        Index dictionary with mesh code to ward mapping
    """
    index = {}

    for area_code, ward_info in global_metadata["wards"].items():
        for mesh_code in ward_info["mesh_codes"]:
            if mesh_code in index:
                # Mesh spans multiple wards
                if isinstance(index[mesh_code], str):
                    index[mesh_code] = [index[mesh_code], area_code]
                else:
                    index[mesh_code].append(area_code)
            else:
                index[mesh_code] = area_code

    return {
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "index": index
    }


def setup_ward_cache(
    dataset: Dict,
    cache_dir: Path,
    skip_existing: bool = False
) -> Dict:
    """
    Setup cache for a single ward.

    Args:
        dataset: Ward dataset information
        cache_dir: Base cache directory
        skip_existing: Skip if ward directory already exists

    Returns:
        Ward metadata dictionary
    """
    area_code = dataset["area_code"]
    ward_name = dataset["ward_name"]

    print(f"\n[{area_code}] {ward_name}")

    # Create ward directory
    ward_dir = cache_dir / f"{area_code}_{ward_name.replace('区', '-ku')}"

    if skip_existing and ward_dir.exists():
        print(f"  ✓ Skipping (already exists)")
        # Load existing metadata
        metadata_path = ward_dir / "ward_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)

    ward_dir.mkdir(parents=True, exist_ok=True)

    # Download ZIP
    zip_path = ward_dir / f"{area_code}.zip"
    try:
        download_ward_zip(dataset["open_data_url"], zip_path)
    except Exception as e:
        print(f"  ERROR: Failed to download: {e}")
        return None

    # Extract and analyze
    try:
        analysis = extract_and_analyze_ward(zip_path, ward_dir, area_code)
    except Exception as e:
        print(f"  ERROR: Failed to extract: {e}")
        return None

    # Remove ZIP to save space
    zip_path.unlink()

    # Create ward metadata
    ward_metadata = {
        "area_code": area_code,
        "ward_name": ward_name,
        "dataset_id": dataset["dataset_id"],
        "plateau_spec": dataset["plateau_spec"],
        "year": dataset["year"],
        "registration_year": dataset["registration_year"],
        "open_data_url": dataset["open_data_url"],
        "downloaded_at": datetime.now().isoformat(),
        "file_count": analysis["file_count"],
        "size_bytes": analysis["size_bytes"],
        "mesh_codes": analysis["mesh_codes"],
        "lod_levels": dataset["lod_levels"]
    }

    # Save ward metadata
    metadata_path = ward_dir / "ward_metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(ward_metadata, f, ensure_ascii=False, indent=2)

    print(f"  ✓ Cached ({analysis['file_count']} files, "
          f"{analysis['size_bytes'] / (1024**2):.1f} MB, "
          f"{len(analysis['mesh_codes'])} mesh codes)")

    return ward_metadata


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Setup CityGML cache for Tokyo 23 wards"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip wards that already have cache directories"
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="data/citygml_cache",
        help="Cache directory path (default: data/citygml_cache)"
    )
    parser.add_argument(
        "--datasets-json",
        type=str,
        default="tokyo23_datasets.json",
        help="Path to tokyo23_datasets.json (default: tokyo23_datasets.json)"
    )

    args = parser.parse_args()

    # Setup paths
    cache_dir = Path(args.cache_dir)

    print("=" * 70)
    print("CityGML Cache Setup for Tokyo 23 Wards")
    print("=" * 70)

    # Check disk space
    if not check_disk_space(cache_dir):
        sys.exit(1)

    # Load datasets
    datasets = load_tokyo23_datasets(args.datasets_json)

    # Create cache directory
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Setup cache for each ward
    global_metadata = {
        "version": "1.0.0",
        "plateau_spec": "4.1",
        "created_at": datetime.now().isoformat(),
        "total_wards": len(datasets),
        "total_size_bytes": 0,
        "wards": {}
    }

    failed_wards = []

    for i, dataset in enumerate(datasets, 1):
        print(f"\n[{i}/{len(datasets)}]", end=" ")

        ward_metadata = setup_ward_cache(dataset, cache_dir, args.skip_existing)

        if ward_metadata:
            area_code = dataset["area_code"]
            global_metadata["wards"][area_code] = {
                "name": dataset["ward_name"],
                "file_count": ward_metadata["file_count"],
                "size_bytes": ward_metadata["size_bytes"],
                "mesh_codes": ward_metadata["mesh_codes"],
                "lod_levels": ward_metadata["lod_levels"]
            }
            global_metadata["total_size_bytes"] += ward_metadata["size_bytes"]
        else:
            failed_wards.append(dataset["area_code"])

    # Build mesh→ward index
    print("\n\nBuilding mesh → ward index...")
    mesh_index = build_mesh_to_ward_index(global_metadata)
    mesh_index_path = cache_dir / "mesh_to_ward_index.json"
    with open(mesh_index_path, 'w', encoding='utf-8') as f:
        json.dump(mesh_index, f, ensure_ascii=False, indent=2)
    print(f"✓ Index created with {len(mesh_index['index'])} mesh codes")

    # Save global metadata
    metadata_path = cache_dir / "metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(global_metadata, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "=" * 70)
    print("Cache setup complete!")
    print("=" * 70)
    print(f"Total wards: {global_metadata['total_wards']}")
    print(f"Total size: {global_metadata['total_size_bytes'] / (1024**3):.2f} GB")

    if failed_wards:
        print(f"\n⚠ Failed wards ({len(failed_wards)}): {', '.join(failed_wards)}")
        print("You can retry with: python setup_citygml_cache.py --skip-existing")
    else:
        print("\n✓ All wards cached successfully!")

    print("\nTo enable cache, set in backend/.env:")
    print("  CITYGML_CACHE_ENABLED=true")
    print(f"  CITYGML_CACHE_DIR={args.cache_dir}")


if __name__ == "__main__":
    main()
