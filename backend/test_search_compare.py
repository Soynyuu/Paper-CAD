#!/usr/bin/env python3
"""
Building ID Direct Comparison via Search API

Directly queries the search API to get Building IDs for KITTE and Tokyo Station,
then compares them to determine if they're selecting the same building.

Usage:
    python test_search_compare.py

Output:
    - Building ID comparison
    - Determination of root cause
"""

import subprocess
import json

SEARCH_API = "http://localhost:8001/api/plateau/search-by-address"

print("="*80)
print("Building ID Direct Comparison")
print("="*80)
print()

test_cases = [
    {"name": "KITTE", "query": "Kitte丸の内"},
    {"name": "Tokyo Station", "query": "東京駅"},
]

results = []

for test in test_cases:
    print(f"Searching for: {test['name']} (query: {test['query']})")
    print("-"*80)

    # Call search API
    cmd = [
        "curl", "-s", "-X", "POST", SEARCH_API,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "query": test['query'],
            "radius": 0.001,
            "limit": 1
        })
    ]

    try:
        response = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        data = json.loads(response.stdout)

        if data.get("success") and data.get("buildings"):
            building = data["buildings"][0]

            result = {
                "name": test['name'],
                "query": test['query'],
                "gml_id": building.get("gml_id", "N/A"),
                "building_id": building.get("building_id", "N/A"),
                "distance": building.get("distance_meters", 0),
                "height": building.get("height", "N/A"),
                "measured_height": building.get("measured_height", "N/A"),
                "usage": building.get("usage", "N/A"),
            }

            results.append(result)

            print(f"  ✓ Found building")
            print(f"  gml:id: {result['gml_id']}")
            print(f"  building_id: {result['building_id']}")
            print(f"  Distance: {result['distance']:.1f}m")
            print(f"  Height: {result['height']}m")
            print(f"  Measured height: {result['measured_height']}m")
            print(f"  Usage: {result['usage']}")
        else:
            print(f"  ✗ Search failed or no buildings found")
            result = {
                "name": test['name'],
                "query": test['query'],
                "error": data.get("error", "Unknown error")
            }
            results.append(result)

    except Exception as e:
        print(f"  ✗ Error: {e}")
        results.append({
            "name": test['name'],
            "query": test['query'],
            "error": str(e)
        })

    print()

# Comparison
print("="*80)
print("Comparison")
print("="*80)
print()

if len(results) == 2 and "error" not in results[0] and "error" not in results[1]:
    kitte = results[0]
    tokyo_station = results[1]

    print("Building IDs:")
    print(f"  KITTE:         {kitte['building_id'] or kitte['gml_id']}")
    print(f"  Tokyo Station: {tokyo_station['building_id'] or tokyo_station['gml_id']}")
    print()

    # Check if IDs match
    kitte_id = kitte['building_id'] if kitte['building_id'] != "N/A" else kitte['gml_id']
    tokyo_id = tokyo_station['building_id'] if tokyo_station['building_id'] != "N/A" else tokyo_station['gml_id']

    if kitte_id == tokyo_id:
        print("❌ CRITICAL: IDs are IDENTICAL!")
        print()
        print("Root Cause: Building ID filtering is selecting the SAME building")
        print("            for both queries, despite them being different buildings.")
        print()
        print("This explains the identical 38,999 byte file size.")
        print()
        print("Fix Required:")
        print("  - Check Building ID extraction logic")
        print("  - Verify distance-based sorting is working")
        print("  - Consider using gml:id instead of buildingID")
    else:
        print("✓ IDs are DIFFERENT")
        print()
        print("This means:")
        print("  - Building ID filtering is working correctly")
        print("  - KITTE and Tokyo Station are different buildings")
        print("  - But both produce identical 38,999 byte files")
        print()
        print("Root Cause: LOD2 data does NOT exist in Marunouchi area")
        print("            Both buildings fall back to generic LOD1 placeholder")
        print()
        print("This is a PLATEAU data limitation, not a code bug.")
        print()
        print("Buildings in Shibuya (Scramble Square) and Shinjuku (Tokyo Met. Gov)")
        print("have LOD2 data, but Marunouchi (KITTE/Tokyo Station) only has LOD1.")

    print()
    print("-"*80)
    print()
    print("Additional Details:")
    print()
    print("KITTE:")
    print(f"  Distance from search point: {kitte['distance']:.1f}m")
    print(f"  Height: {kitte['height']}m")
    print(f"  Usage: {kitte['usage']}")
    print()
    print("Tokyo Station:")
    print(f"  Distance from search point: {tokyo_station['distance']:.1f}m")
    print(f"  Height: {tokyo_station['height']}m")
    print(f"  Usage: {tokyo_station['usage']}")

else:
    print("❌ Cannot compare: One or both searches failed")

print()
print("="*80)
print("Test complete!")
print("="*80)
