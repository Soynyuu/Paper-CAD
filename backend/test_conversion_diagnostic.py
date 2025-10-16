#!/usr/bin/env python3
"""
CityGML to STEP Conversion Diagnostic Script

This script is designed to diagnose conversion failures by:
1. Testing multiple precision_mode and shape_fix_level combinations
2. Generating comprehensive logs with凡例 (legend) for LLM analysis
3. Comparing results to identify the best configuration

Usage:
    python test_conversion_diagnostic.py <building_id> [--citygml-path PATH]

Example:
    python test_conversion_diagnostic.py bldg_1db9c375-4ff6-4e3a-8c05-3a5c37e4580d

The script will:
- Search for the building (or use provided CityGML file)
- Try multiple conversion parameter combinations
- Generate detailed logs for each attempt
- Display a comparison table of results
- Recommend the best settings
"""

import sys
import os
import tempfile
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.plateau_fetcher import search_buildings_by_address
from services.citygml_to_step import export_step_from_citygml


def test_conversion(gml_path: str, building_id: str, precision_mode: str,
                    shape_fix_level: str, output_dir: str):
    """Test a single combination of parameters.

    Returns:
        dict: Result containing success status, file size, and error message
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"test_{precision_mode}_{shape_fix_level}_{timestamp}.step"
    output_path = os.path.join(output_dir, output_filename)

    print(f"\n{'='*80}")
    print(f"Testing: precision_mode={precision_mode}, shape_fix_level={shape_fix_level}")
    print(f"{'='*80}")

    try:
        ok, msg = export_step_from_citygml(
            gml_path,
            output_path,
            limit=None,
            debug=True,
            method="solid",
            precision_mode=precision_mode,
            shape_fix_level=shape_fix_level,
            building_ids=[building_id],
            filter_attribute="gml:id",
            merge_building_parts=False
        )

        result = {
            "precision_mode": precision_mode,
            "shape_fix_level": shape_fix_level,
            "success": ok,
            "message": msg,
            "output_path": output_path if ok else None,
            "file_size": os.path.getsize(output_path) if ok and os.path.exists(output_path) else 0
        }

        if ok:
            print(f"✓ SUCCESS: {output_filename} ({result['file_size']:,} bytes)")
        else:
            print(f"✗ FAILED: {msg}")

        return result

    except Exception as e:
        print(f"✗ EXCEPTION: {type(e).__name__}: {str(e)}")
        return {
            "precision_mode": precision_mode,
            "shape_fix_level": shape_fix_level,
            "success": False,
            "message": f"Exception: {type(e).__name__}: {str(e)}",
            "output_path": None,
            "file_size": 0
        }


def main():
    parser = argparse.ArgumentParser(
        description="Diagnostic tool for CityGML to STEP conversion failures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with building ID (will search PLATEAU API)
  python test_conversion_diagnostic.py bldg_1db9c375-4ff6-4e3a-8c05-3a5c37e4580d

  # Test with local CityGML file
  python test_conversion_diagnostic.py bldg_123 --citygml-path /path/to/file.gml

  # Test specific parameter combination only
  python test_conversion_diagnostic.py bldg_123 --quick --precision standard --shape-fix minimal
        """
    )

    parser.add_argument("building_id", help="Building ID (gml:id) to test")
    parser.add_argument("--citygml-path", help="Path to local CityGML file (optional)")
    parser.add_argument("--query", help="Address/facility name for PLATEAU search (default: use building_id)")
    parser.add_argument("--quick", action="store_true", help="Test only one combination (fastest)")
    parser.add_argument("--precision", default=None, help="Specific precision mode to test")
    parser.add_argument("--shape-fix", default=None, help="Specific shape fix level to test")

    args = parser.parse_args()

    building_id = args.building_id
    citygml_path = args.citygml_path

    print("="*80)
    print("CITYGML TO STEP CONVERSION DIAGNOSTIC TOOL")
    print("="*80)
    print(f"Building ID: {building_id}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*80)

    # Get CityGML file
    if citygml_path:
        if not os.path.exists(citygml_path):
            print(f"ERROR: CityGML file not found: {citygml_path}")
            return 1
        print(f"\nUsing local CityGML file: {citygml_path}")
        gml_path = citygml_path
    else:
        print(f"\nSearching PLATEAU API for building...")
        query = args.query or building_id

        search_result = search_buildings_by_address(
            query=query,
            radius=0.005,  # Larger radius to ensure we find the building
            limit=None  # No limit, search all
        )

        if not search_result['success']:
            print(f"ERROR: Search failed - {search_result.get('error')}")
            return 1

        citygml_xml = search_result.get('citygml_xml')
        if not citygml_xml:
            print("ERROR: No CityGML data in search results")
            return 1

        # Save to temporary file
        tmpdir = tempfile.mkdtemp()
        gml_path = os.path.join(tmpdir, "diagnostic_test.gml")
        with open(gml_path, 'w', encoding='utf-8') as f:
            f.write(citygml_xml)

        print(f"✓ CityGML retrieved ({len(citygml_xml):,} bytes)")
        print(f"  Saved to: {gml_path}")

    # Create output directory
    output_dir = tempfile.mkdtemp(prefix="conversion_diagnostic_")
    print(f"\nOutput directory: {output_dir}")

    # Define test combinations
    if args.quick:
        # Quick test: just one combination
        if args.precision and args.shape_fix:
            combinations = [(args.precision, args.shape_fix)]
        else:
            combinations = [("standard", "minimal")]
    else:
        # Full diagnostic: test multiple combinations
        precision_modes = ["standard", "high", "maximum"]
        shape_fix_levels = ["minimal", "standard", "aggressive"]

        if args.precision:
            precision_modes = [args.precision]
        if args.shape_fix:
            shape_fix_levels = [args.shape_fix]

        combinations = [
            (pm, sfl) for pm in precision_modes for sfl in shape_fix_levels
        ]

    print(f"\nWill test {len(combinations)} parameter combination(s):")
    for i, (pm, sfl) in enumerate(combinations, 1):
        print(f"  {i}. precision_mode={pm}, shape_fix_level={sfl}")

    # Run tests
    results = []
    for pm, sfl in combinations:
        result = test_conversion(gml_path, building_id, pm, sfl, output_dir)
        results.append(result)

    # Display results table
    print(f"\n{'='*80}")
    print("DIAGNOSTIC RESULTS SUMMARY")
    print(f"{'='*80}\n")

    print(f"{'Precision':<12} {'ShapeFix':<12} {'Status':<10} {'Size':<12} {'Message':<40}")
    print(f"{'-'*12} {'-'*12} {'-'*10} {'-'*12} {'-'*40}")

    for result in results:
        status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
        size = f"{result['file_size']:,} B" if result['file_size'] > 0 else "N/A"
        message = result['message'][:37] + "..." if len(result['message']) > 40 else result['message']

        print(f"{result['precision_mode']:<12} {result['shape_fix_level']:<12} {status:<10} {size:<12} {message:<40}")

    # Recommendations
    successful = [r for r in results if r['success']]

    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}")

    if successful:
        # Find the fastest successful combination (minimal shape_fix_level, standard precision)
        best = min(successful, key=lambda r: (
            {"minimal": 0, "standard": 1, "aggressive": 2}[r['shape_fix_level']],
            {"standard": 0, "high": 1, "maximum": 2}[r['precision_mode']]
        ))

        print(f"\n✓ {len(successful)}/{len(results)} combination(s) succeeded")
        print(f"\nRecommended settings:")
        print(f"  precision_mode: {best['precision_mode']}")
        print(f"  shape_fix_level: {best['shape_fix_level']}")
        print(f"  Output: {best['output_path']}")
        print(f"  Size: {best['file_size']:,} bytes")

        if best['shape_fix_level'] == 'minimal' and best['precision_mode'] == 'standard':
            print(f"\n💡 This is the fastest configuration!")
        else:
            print(f"\n⚠ Note: Standard/minimal would be faster but failed in this case.")
            print(f"   The geometry requires {best['shape_fix_level']} repair or {best['precision_mode']} precision.")
    else:
        print(f"\n✗ All {len(results)} combination(s) failed")
        print(f"\nPossible causes:")
        print(f"  1. Building geometry is fundamentally invalid (self-intersecting, degenerate)")
        print(f"  2. LOD data is missing or corrupted in the CityGML file")
        print(f"  3. Building ID does not exist in the provided CityGML")
        print(f"\nNext steps:")
        print(f"  1. Check the detailed logs in {output_dir}")
        print(f"  2. Verify the building ID exists: {building_id}")
        print(f"  3. Inspect the CityGML file manually to confirm LOD2/LOD3 data exists")

    # Log file locations
    log_dir = os.path.join(os.path.dirname(__file__), "debug_logs")
    if os.path.exists(log_dir):
        print(f"\n{'='*80}")
        print("DETAILED LOGS")
        print(f"{'='*80}")
        print(f"\nLog directory: {log_dir}")
        print(f"Log files are named: conversion_{building_id[:20]}_*.log")
        print(f"\nThese logs include:")
        print(f"  • LOG LEGEND (凡例) for LLM analysis")
        print(f"  • Phase-by-phase execution trace")
        print(f"  • Automatic repair attempts")
        print(f"  • Validation results")
        print(f"  • Error diagnostics with tracebacks")

    print(f"\n{'='*80}")
    print("Test complete!")
    print(f"{'='*80}\n")

    return 0 if successful else 1


if __name__ == "__main__":
    sys.exit(main())
