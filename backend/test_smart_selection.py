#!/usr/bin/env python3
"""
Smart Building Selection Verification Test

Tests the new smart scoring algorithm to verify it correctly selects
prominent landmarks (like KITTE JP Tower) instead of auxiliary buildings.

Usage:
    python test_smart_selection.py

Expected Result:
    - KITTE query should select the 205m JP Tower (not 7m auxiliary building)
    - Tokyo Station query should select the actual station building
    - File sizes should be significantly larger (LOD2 data, not LOD1 fallback)
"""

import subprocess
import json
import os

SEARCH_API = "http://localhost:8001/api/plateau/search-by-address"
CONVERT_API = "http://localhost:8001/api/plateau/fetch-and-convert"

print("="*80)
print("Smart Building Selection Verification")
print("="*80)
print()

# Test cases
test_cases = [
    {
        "name": "KITTE Marunouchi",
        "query": "Kitte丸の内",
        "expected_height_min": 150,  # Should be ~205m
        "description": "Landmark query - should prioritize height"
    },
    {
        "name": "Tokyo Station",
        "query": "東京駅",
        "expected_height_min": 20,   # Should be actual station building
        "description": "Landmark query - should select proper station"
    },
]

results = []

print("PHASE 1: Search API Verification")
print("-"*80)
print()

for test in test_cases:
    print(f"Testing: {test['name']}")
    print(f"  Query: {test['query']}")
    print(f"  Type: {test['description']}")
    print()

    # Call search API
    cmd = [
        "curl", "-s", "-X", "POST", SEARCH_API,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "query": test['query'],
            "radius": 0.001,
            "limit": 5  # Get top 5 to see scoring results
        })
    ]

    try:
        response = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        data = json.loads(response.stdout)

        if data.get("success") and data.get("buildings"):
            buildings = data["buildings"]
            top_building = buildings[0]

            print(f"  ✓ Search successful - found {len(buildings)} buildings")
            print()
            print(f"  TOP RESULT (Selected Building):")
            print(f"    Building ID: {top_building.get('building_id', 'N/A')}")
            print(f"    GML ID: {top_building.get('gml_id', 'N/A')[:50]}...")
            print(f"    Height: {top_building.get('height', 'N/A')}m")
            print(f"    Measured Height: {top_building.get('measured_height', 'N/A')}m")
            print(f"    Distance: {top_building.get('distance_meters', 0):.1f}m")
            print(f"    Usage: {top_building.get('usage', 'N/A')}")
            print()

            # Verify height expectation
            height = top_building.get('height') or top_building.get('measured_height', 0)
            if height >= test['expected_height_min']:
                print(f"  ✅ HEIGHT CHECK PASSED: {height}m >= {test['expected_height_min']}m")
                status = "PASS"
            else:
                print(f"  ❌ HEIGHT CHECK FAILED: {height}m < {test['expected_height_min']}m")
                print(f"     Expected prominent landmark, got small building")
                status = "FAIL"

            print()
            print(f"  Other candidates (for comparison):")
            for i, bldg in enumerate(buildings[1:4], 2):
                h = bldg.get('height') or bldg.get('measured_height', 0)
                d = bldg.get('distance_meters', 0)
                print(f"    {i}. Height: {h}m, Distance: {d:.1f}m")

            results.append({
                "name": test['name'],
                "query": test['query'],
                "status": status,
                "selected_height": height,
                "selected_distance": top_building.get('distance_meters', 0),
                "gml_id": top_building.get('gml_id', 'N/A'),
                "building_id": top_building.get('building_id', 'N/A'),
            })

        else:
            print(f"  ✗ Search failed: {data.get('error', 'Unknown error')}")
            results.append({
                "name": test['name'],
                "query": test['query'],
                "status": "ERROR",
                "error": data.get('error', 'Unknown error')
            })

    except Exception as e:
        print(f"  ✗ Exception: {e}")
        results.append({
            "name": test['name'],
            "query": test['query'],
            "status": "ERROR",
            "error": str(e)
        })

    print()
    print("-"*80)
    print()

print()
print("="*80)
print("PHASE 2: Full Conversion Test (if Phase 1 passed)")
print("="*80)
print()

# Only test conversion if search passed
passed_tests = [r for r in results if r.get('status') == 'PASS']

if passed_tests:
    print(f"Testing full conversion for {len(passed_tests)} building(s)...")
    print()

    for i, result in enumerate(passed_tests, 1):
        print(f"[{i}/{len(passed_tests)}] Converting: {result['name']}")
        print(f"  Expected height: {result['selected_height']:.1f}m")

        output_file = f"smart_selection_{result['name'].replace(' ', '_')}.step"

        cmd = [
            "curl", "-s", "-X", "POST", CONVERT_API,
            "-F", f"query={result['query']}",
            "-F", "radius=0.001",
            "-F", "building_limit=1",
            "-F", "debug=false",
            "-F", "method=solid",
            "-F", "auto_reproject=true",
            "-F", "precision_mode=standard",
            "-F", "shape_fix_level=minimal",
            "-F", "merge_building_parts=false",
            "-o", output_file,
            "-w", "%{http_code}",
        ]

        try:
            response = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            status_code = response.stdout.strip()

            if status_code == "200":
                file_size = os.path.getsize(output_file)
                print(f"  ✓ Conversion successful")
                print(f"  File size: {file_size:,} bytes")

                # Verify NOT the old 38,999 byte LOD1 fallback
                if file_size == 38999:
                    print(f"  ⚠️  WARNING: File size matches old LOD1 fallback!")
                    print(f"      This suggests LOD2 extraction may have failed")
                elif file_size > 100000:
                    print(f"  ✅ File size suggests successful LOD2 extraction")
                else:
                    print(f"  ⚠️  File size is small - may be LOD1")

                result['conversion_status'] = 'SUCCESS'
                result['file_size'] = file_size
            else:
                print(f"  ✗ Conversion failed (HTTP {status_code})")
                result['conversion_status'] = 'FAILED'

        except Exception as e:
            print(f"  ✗ Error: {e}")
            result['conversion_status'] = 'ERROR'

        print()

else:
    print("⚠️  Skipping conversion test - no searches passed Phase 1")
    print()

print("="*80)
print("FINAL SUMMARY")
print("="*80)
print()

print(f"{'Building':<30} {'Status':<10} {'Height':<10} {'Distance':<12} {'File Size':<15}")
print("-"*80)

for r in results:
    status = r.get('status', 'ERROR')
    height = f"{r.get('selected_height', 0):.1f}m" if 'selected_height' in r else "N/A"
    distance = f"{r.get('selected_distance', 0):.1f}m" if 'selected_distance' in r else "N/A"
    file_size = f"{r.get('file_size', 0):,}B" if 'file_size' in r else "N/A"

    status_symbol = "✅" if status == "PASS" else "❌"
    print(f"{r['name']:<30} {status_symbol} {status:<8} {height:<10} {distance:<12} {file_size:<15}")

print()
print("="*80)
print("ANALYSIS")
print("="*80)
print()

pass_count = sum(1 for r in results if r.get('status') == 'PASS')
fail_count = sum(1 for r in results if r.get('status') == 'FAIL')

if pass_count == len(results):
    print("✅ ALL TESTS PASSED!")
    print()
    print("Smart building selection is working correctly:")
    print("  - Landmark queries prioritize building height")
    print("  - Prominent buildings are selected over auxiliary structures")
    print("  - KITTE JP Tower (205m) is now selected instead of 7m building")
elif fail_count > 0:
    print(f"❌ {fail_count}/{len(results)} TESTS FAILED")
    print()
    print("Smart building selection may need adjustment:")
    print("  - Check scoring weights (distance vs height)")
    print("  - Verify landmark detection patterns")
    print("  - Review building height thresholds")
else:
    print("⚠️  TESTS INCOMPLETE")

print()
print("="*80)
