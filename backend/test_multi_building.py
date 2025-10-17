#!/usr/bin/env python3
"""
Multi-Building LOD2 Extraction Test

Tests multiple famous buildings to identify LOD2 extraction pattern:
- KITTE (currently failing)
- Tokyo Station (should have LOD2)
- Shibuya Scramble Square (modern high-rise)
- Tokyo Metropolitan Government Building (landmark)

Usage:
    python test_multi_building.py

Output:
    - Summary table comparing all buildings
    - Individual STEP files for each building
"""

import os
import subprocess
import time

print("="*80)
print("Multi-Building LOD2 Extraction Test")
print("="*80)
print()

# Test buildings
buildings = [
    {"name": "KITTE Marunouchi", "query": "Kitte丸の内", "expected": "LOD2 or LOD1?"},
    {"name": "Tokyo Station", "query": "東京駅", "expected": "LOD2 (high confidence)"},
    {"name": "Shibuya Scramble Square", "query": "渋谷スクランブルスクエア", "expected": "LOD2 (modern)"},
    {"name": "Tokyo Metropolitan Gov", "query": "東京都庁", "expected": "LOD2 (landmark)"},
]

results = []

API_URL = "http://localhost:8001/api/plateau/fetch-and-convert"

print("Testing 4 buildings with LOD2 extraction...")
print()

for i, bldg in enumerate(buildings, 1):
    print(f"[{i}/4] Testing: {bldg['name']} (query: {bldg['query']})")
    print("-"*80)

    output_file = f"test_{i}_{bldg['name'].replace(' ', '_')}.step"

    # Call API via curl
    cmd = [
        "curl", "-s", "-X", "POST", API_URL,
        "-F", f"query={bldg['query']}",
        "-F", "radius=0.001",
        "-F", "building_limit=1",
        "-F", "debug=false",  # Disable debug for clean output
        "-F", "method=solid",
        "-F", "auto_reproject=true",
        "-F", "precision_mode=standard",
        "-F", "shape_fix_level=minimal",
        "-F", "merge_building_parts=false",
        "-o", output_file,
        "-w", "HTTP:%{http_code}|Size:%{size_download}",
    ]

    try:
        response = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = response.stdout.strip()

        # Parse response
        if "HTTP:200" in output:
            size_str = output.split("Size:")[-1] if "Size:" in output else "0"
            try:
                file_size = int(size_str)
            except:
                file_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0

            # Count entities in STEP file
            entity_count = 0
            face_count = 0
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    for line in f:
                        if line.startswith('#'):
                            entity_count += 1
                        if 'ADVANCED_FACE' in line:
                            face_count += 1

            # Determine LOD level
            if file_size < 50000:
                lod_level = "LOD1 (simple box)"
            elif file_size < 150000:
                lod_level = "LOD1-2 (intermediate)"
            else:
                lod_level = "LOD2 (detailed)"

            results.append({
                "name": bldg['name'],
                "status": "✓ Success",
                "file_size": file_size,
                "entities": entity_count,
                "faces": face_count,
                "lod": lod_level,
                "file": output_file
            })

            print(f"  Status: ✓ Success")
            print(f"  File size: {file_size:,} bytes")
            print(f"  Entities: {entity_count}")
            print(f"  Faces: {face_count}")
            print(f"  LOD Level: {lod_level}")

        else:
            results.append({
                "name": bldg['name'],
                "status": "✗ Failed",
                "file_size": 0,
                "entities": 0,
                "faces": 0,
                "lod": "N/A",
                "file": "N/A"
            })
            print(f"  Status: ✗ Failed (HTTP error)")

    except subprocess.TimeoutExpired:
        results.append({
            "name": bldg['name'],
            "status": "✗ Timeout",
            "file_size": 0,
            "entities": 0,
            "faces": 0,
            "lod": "N/A",
            "file": "N/A"
        })
        print(f"  Status: ✗ Timeout (>120s)")

    except Exception as e:
        results.append({
            "name": bldg['name'],
            "status": f"✗ Error: {e}",
            "file_size": 0,
            "entities": 0,
            "faces": 0,
            "lod": "N/A",
            "file": "N/A"
        })
        print(f"  Status: ✗ Error: {e}")

    print()
    time.sleep(1)  # Rate limiting

print()
print("="*80)
print("Summary")
print("="*80)
print()

# Print summary table
print(f"{'Building':<30} {'Size':>12} {'Entities':>10} {'Faces':>8} {'LOD':>20}")
print("-"*80)
for r in results:
    size_str = f"{r['file_size']:,}B" if r['file_size'] > 0 else "N/A"
    entities_str = str(r['entities']) if r['entities'] > 0 else "N/A"
    faces_str = str(r['faces']) if r['faces'] > 0 else "N/A"
    print(f"{r['name']:<30} {size_str:>12} {entities_str:>10} {faces_str:>8} {r['lod']:>20}")

print()
print("="*80)
print("Analysis")
print("="*80)
print()

# Analyze patterns
success_count = sum(1 for r in results if "Success" in r['status'])
lod2_count = sum(1 for r in results if "LOD2" in r['lod'])
lod1_count = sum(1 for r in results if "LOD1" in r['lod'])

print(f"Success rate: {success_count}/4")
print(f"LOD2 extractions: {lod2_count}/4")
print(f"LOD1 fallbacks: {lod1_count}/4")
print()

if lod2_count == 0:
    print("❌ PATTERN: All buildings fell back to LOD1")
    print("   → LOD2 extraction logic has a systemic bug")
    print("   → Check _extract_single_solid() strategies")
elif lod2_count == 4:
    print("✓ PATTERN: All buildings successfully extracted LOD2")
    print("   → No systemic issue, KITTE problem was isolated")
elif lod1_count > 0:
    print("⚠ PATTERN: Mixed results")
    print("   → Some buildings have LOD2, others don't")
    print("   → Possible issues:")
    print("     1. Some areas lack LOD2 in PLATEAU data")
    print("     2. Building ID filtering selecting wrong buildings")
    print("     3. XLink reference resolution failing for some datasets")

    # Check KITTE specifically
    kitte_result = next((r for r in results if "KITTE" in r['name']), None)
    if kitte_result and "LOD1" in kitte_result['lod']:
        print()
        print("   KITTE Analysis:")
        print(f"     - File size: {kitte_result['file_size']:,} bytes (suspiciously small)")
        print(f"     - Faces: {kitte_result['faces']} (6×N = simple boxes)")
        print("     - Recommendation: Check if KITTE area has LOD2 in PLATEAU")

print()
print("="*80)
print("Test complete!")
print("="*80)
