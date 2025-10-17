#!/usr/bin/env python3
"""
KITTE Marunouchi LOD2 Debug Test Script

This script fetches KITTE building from PLATEAU and converts to STEP with
detailed debug logging to diagnose why LOD2 geometry is being simplified.

Usage:
    python test_kitte_debug.py

Output:
    - kitte_debug_output.txt: Detailed debug log
    - kitte_building.step: Generated STEP file
"""

import sys
import os
import tempfile
from io import StringIO

# Redirect stdout to capture all debug output
original_stdout = sys.stdout
log_buffer = StringIO()

class TeeOutput:
    """Write to both console and string buffer"""
    def __init__(self, *outputs):
        self.outputs = outputs

    def write(self, text):
        for output in self.outputs:
            output.write(text)

    def flush(self):
        for output in self.outputs:
            output.flush()

# Redirect stdout to both console and buffer
sys.stdout = TeeOutput(original_stdout, log_buffer)

print("="*80)
print("KITTE Marunouchi LOD2 Debug Test")
print("="*80)
print()

# Import after stdout redirection
from services.plateau_fetcher import search_buildings_by_address
from services.citygml_to_step import export_step_from_citygml

print("[1] Searching for KITTE building...")
print()

# Search for KITTE
search_result = search_buildings_by_address(
    query='Kitte丸の内',
    radius=0.001,
    limit=1
)

if not search_result['success']:
    print(f"ERROR: Search failed - {search_result.get('error')}")
    sys.exit(1)

buildings = search_result['buildings']
if not buildings:
    print("ERROR: No buildings found")
    sys.exit(1)

building = buildings[0]
print(f"Found building:")
print(f"  - GML ID: {building.gml_id}")
print(f"  - Building ID: {building.building_id}")
print(f"  - Distance: {building.distance_meters:.1f}m")
print(f"  - Height: {building.height}m")
print(f"  - Measured Height: {building.measured_height}m")
print()

# Get CityGML
citygml_xml = search_result.get('citygml_xml')
if not citygml_xml:
    print("ERROR: No CityGML data")
    sys.exit(1)

print(f"CityGML size: {len(citygml_xml):,} bytes")
print()

# Save CityGML to temp file
tmpdir = tempfile.mkdtemp()
gml_path = os.path.join(tmpdir, "kitte.gml")
with open(gml_path, 'w', encoding='utf-8') as f:
    f.write(citygml_xml)

print(f"Saved CityGML to: {gml_path}")
print()

# Output STEP path
output_step = "kitte_building.step"

print("="*80)
print("[2] Converting to STEP with DEBUG enabled")
print("="*80)
print()
print("Parameters:")
print("  - debug: True")
print("  - method: solid")
print("  - precision_mode: standard")
print("  - shape_fix_level: minimal")
print("  - merge_building_parts: False")
print("  - building_ids: [from search]")
print()

# Determine building ID and filter attribute
if building.building_id:
    building_ids = [building.building_id]
    filter_attribute = "buildingID"
else:
    building_ids = [building.gml_id]
    filter_attribute = "gml:id"

print(f"Using building ID: {building_ids[0]} (attribute: {filter_attribute})")
print()
print("-"*80)
print()

# Convert with DEBUG enabled
ok, msg = export_step_from_citygml(
    gml_path,
    output_step,
    limit=None,
    debug=True,  # FORCE DEBUG ON
    method="solid",
    precision_mode="standard",
    shape_fix_level="minimal",
    building_ids=building_ids,
    filter_attribute=filter_attribute,
    merge_building_parts=False  # Keep parts separate for detail
)

print()
print("-"*80)
print()
print("="*80)
print("[3] Conversion Result")
print("="*80)
print()

if ok:
    file_size = os.path.getsize(output_step)
    print(f"✓ SUCCESS")
    print(f"  Output: {output_step}")
    print(f"  Size: {file_size:,} bytes")
    print()

    # Analyze file size
    if file_size < 50000:
        print("⚠ WARNING: File size suspiciously small (<50KB)")
        print("  Expected LOD2 building should be larger")
        print("  This suggests geometry was simplified or LOD2 extraction failed")
    else:
        print("✓ File size looks reasonable for detailed LOD2 model")
else:
    print(f"✗ FAILED: {msg}")

print()
print("="*80)
print("[4] Summary")
print("="*80)
print()
print("Debug log saved to: kitte_debug_output.txt")
print()
print("Key things to check in the log:")
print("  1. [LOD3]/[LOD2]/[LOD1] - Which LOD level was found?")
print("  2. 'Found X BuildingPart(s)' - Number of building parts")
print("  3. 'extracted X faces' - How many faces were extracted")
print("  4. 'Solid extraction: X exterior faces' - Faces from gml:Solid")
print("  5. 'boundedBy extraction: X faces' - Faces from boundary surfaces")
print("  6. Any 'ERROR' or 'WARNING' messages")
print()

# Restore stdout and save log
sys.stdout = original_stdout
log_content = log_buffer.getvalue()

# Save to file
with open('kitte_debug_output.txt', 'w', encoding='utf-8') as f:
    f.write(log_content)

print("="*80)
print("Test complete! Check kitte_debug_output.txt for detailed logs.")
print("="*80)
