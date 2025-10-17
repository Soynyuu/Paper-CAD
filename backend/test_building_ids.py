#!/usr/bin/env python3
"""
Building ID Verification Test

Compares Building IDs used for KITTE vs Tokyo Station to determine
if they're selecting the same building (which would explain the
identical 38,999 byte file size).

This will capture server logs to see which Building IDs are being used.

Usage:
    python test_building_ids.py

Output:
    - Building ID comparison for KITTE and Tokyo Station
    - filter_attribute values
    - Determination of root cause
"""

import subprocess
import time
import re

API_URL = "http://localhost:8001/api/plateau/fetch-and-convert"

print("="*80)
print("Building ID Verification Test")
print("="*80)
print()
print("NOTE: Watch the BACKEND TERMINAL for [API] log lines")
print("      We need to capture the Building IDs being used")
print()
print("-"*80)
print()

test_cases = [
    {"name": "KITTE", "query": "Kitte丸の内"},
    {"name": "Tokyo Station", "query": "東京駅"},
]

print("Testing 2 buildings and comparing Building IDs...")
print()

for i, test in enumerate(test_cases, 1):
    print(f"[{i}/2] Testing: {test['name']}")
    print(f"Query: {test['query']}")
    print()

    print("Sending request...")
    print("→ Check BACKEND TERMINAL for lines:")
    print("  - '[API] Selected X building(s):'")
    print("  - '  1. <building_id> (XX.Xm)'")
    print("  - This will show the exact Building ID being used")
    print()

    output_file = f"buildingid_test_{i}.step"

    cmd = [
        "curl", "-s", "-X", "POST", API_URL,
        "-F", f"query={test['query']}",
        "-F", "radius=0.001",
        "-F", "building_limit=1",
        "-F", "debug=false",  # Server still logs [API] lines even without debug
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
            print(f"✓ Request successful (HTTP 200)")

            # Get file size
            import os
            file_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
            print(f"  File size: {file_size:,} bytes")
        else:
            print(f"✗ Request failed (HTTP {status_code})")

    except Exception as e:
        print(f"✗ Error: {e}")

    print()
    print("⏸  Please check the BACKEND TERMINAL for the Building ID")
    print("   (Look for the [API] Selected log line)")
    print()

    if i < len(test_cases):
        print("Waiting 3 seconds before next test...")
        print()
        time.sleep(3)

print("="*80)
print("Manual Analysis Required")
print("="*80)
print()
print("Please compare the Building IDs from the BACKEND TERMINAL:")
print()
print("Expected log format:")
print("  [API] Selected 1 building(s):")
print("  1. <building_id_here> (XX.Xm)")
print()
print("Questions to answer:")
print("  1. Are the Building IDs IDENTICAL for KITTE and Tokyo Station?")
print("     → YES: Building ID filtering bug confirmed")
print("     → NO: Different buildings, but both lack LOD2")
print()
print("  2. What type of IDs are being used?")
print("     - Long hex strings (e.g., 5ffc2bd4-bd77-...): gml:id format")
print("     - Short IDs (e.g., 13100-bldg-xxx): buildingID format")
print()
print("  3. If IDs are different but files are identical (38,999 bytes):")
print("     → LOD2 data does not exist in Marunouchi area")
print("     → Both buildings fall back to generic LOD1 placeholder")
print()
print("="*80)
