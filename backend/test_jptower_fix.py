#!/usr/bin/env python3
"""
JP Tower LOD2 Wall Missing Fix Test Script

This script tests the fix for missing walls in JP Tower PLATEAU conversion.
The fix includes:
- Vertex deduplication to remove duplicate/near-duplicate vertices
- ShapeFix_Wire for automatic wire repair
- ShapeFix_Face for automatic face repair
- Enhanced error diagnostics with BRepBuilderAPI error codes

Usage:
    python test_jptower_fix.py

Output:
    - jptower_fix_output.txt: Detailed debug log with new diagnostics
    - jptower_building.step: Generated STEP file
    - Comparison with previous conversion (if available)
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
print("JP Tower LOD2 Wall Missing Fix Test")
print("="*80)
print()
print("Testing improvements:")
print("  ✓ Vertex deduplication (_deduplicate_vertices)")
print("  ✓ ShapeFix_Wire automatic repair")
print("  ✓ ShapeFix_Face automatic repair")
print("  ✓ Enhanced error diagnostics")
print()

# Import after stdout redirection
from services.plateau_fetcher import search_buildings_by_address
from services.citygml_to_step import export_step_from_citygml

print("[1] Searching for JP Tower...")
print()

# Search for JP Tower (JPタワー)
# JP Tower is located at 2-7-2 Marunouchi, Chiyoda-ku, Tokyo
search_result = search_buildings_by_address(
    query='JPタワー',
    radius=0.001,
    limit=1
)

if not search_result['success']:
    print(f"ERROR: Search failed - {search_result.get('error')}")
    sys.exit(1)

buildings = search_result['buildings']
if not buildings:
    print("ERROR: No buildings found")
    print("Trying alternative query: 東京駅...")

    # Fallback: Search near Tokyo Station
    search_result = search_buildings_by_address(
        query='東京駅',
        radius=0.002,
        limit=5
    )
    buildings = search_result['buildings'] if search_result['success'] else []

    if not buildings:
        print("ERROR: Still no buildings found")
        sys.exit(1)

building = buildings[0]
print(f"Found building:")
print(f"  - GML ID: {building.gml_id}")
print(f"  - Building ID: {building.building_id}")
print(f"  - Distance: {building.distance_meters:.1f}m")
print(f"  - Height: {building.height}m")
print(f"  - Measured Height: {building.measured_height}m")
print()

# Check if this is the correct JP Tower (known gml:id)
expected_id = "bldg_f0028aa3-e666-4608-8b70-4e981a45d6b5"
if building.gml_id != expected_id:
    print(f"WARNING: Found building ID doesn't match expected JP Tower ID")
    print(f"  Expected: {expected_id}")
    print(f"  Found: {building.gml_id}")
    print(f"  Proceeding anyway...")
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
gml_path = os.path.join(tmpdir, "jptower.gml")
with open(gml_path, 'w', encoding='utf-8') as f:
    f.write(citygml_xml)

print(f"Saved CityGML to: {gml_path}")
print()

# Output STEP path
output_step = "jptower_building.step"

print("="*80)
print("[2] Converting to STEP with ENHANCED DIAGNOSTICS")
print("="*80)
print()
print("Conversion parameters:")
print("  - debug: True")
print("  - method: solid")
print("  - precision_mode: standard")
print("  - shape_fix_level: minimal")
print("  - merge_building_parts: False")
print()
print("New features in this conversion:")
print("  • Automatic vertex deduplication")
print("  • ShapeFix_Wire for wire repair")
print("  • ShapeFix_Face for face repair")
print("  • Detailed error codes from BRepBuilderAPI")
print()

# Determine building ID and filter attribute
if building.building_id:
    building_ids = [building.building_id]
    filter_attribute = "buildingID"
else:
    building_ids = [building.gml_id]
    filter_attribute = "gml:id"

print(f"Using building ID: {building_ids[0]}")
print(f"Filter attribute: {filter_attribute}")
print()
print("-"*80)
print()

# Convert with DEBUG enabled
ok, msg = export_step_from_citygml(
    gml_path,
    output_step,
    limit=None,
    debug=True,  # FORCE DEBUG ON for detailed logs
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
print("[3] Conversion Result Analysis")
print("="*80)
print()

if ok:
    file_size = os.path.getsize(output_step)
    print(f"✓ SUCCESS")
    print(f"  Output: {output_step}")
    print(f"  Size: {file_size:,} bytes")
    print()

    # Analyze file size
    if file_size < 100000:
        print("⚠ WARNING: File size suspiciously small (<100KB)")
        print("  Expected LOD2 building should be larger")
        print("  This suggests some geometry may still be missing")
    else:
        print("✓ File size looks reasonable for detailed LOD2 model")
else:
    print(f"✗ FAILED: {msg}")

print()
print("="*80)
print("[4] What to Check in the Log")
print("="*80)
print()
print("Look for these NEW diagnostic messages:")
print("  • [Wire] Deduplicated vertices: X → Y")
print("  • [Wire] ShapeFix_Wire: Successfully closed wire")
print("  • [Wire] ShapeFix_Wire: Applied automatic repairs")
print("  • [Face] BRepBuilderAPI_MakeFace failed: [ERROR CODE]")
print("  • [Face] ShapeFix_Face: Successfully created face after repair")
print("  • [Face] Coordinate ranges: X=[...], Y=[...], Z=[...]")
print()
print("Compare with PREVIOUS log to see improvements:")
print("  • Fewer 'Face creation failed' messages")
print("  • More successful 'ShapeFix' repair messages")
print("  • Higher face count in 'boundedBy extraction summary'")
print()
print("Expected improvements:")
print("  - Previous: 74 faces from lod2Solid, 148 from boundedBy")
print("  - Target: Should be closer to 80 faces (all walls included)")
print()

# Restore stdout and save log
sys.stdout = original_stdout
log_content = log_buffer.getvalue()

# Save to file
output_log = 'jptower_fix_output.txt'
with open(output_log, 'w', encoding='utf-8') as f:
    f.write(log_content)

print("="*80)
print("Test complete!")
print("="*80)
print()
print(f"Debug log: {output_log}")
print(f"STEP file: {output_step}")
print()
print("Next steps:")
print("  1. Check the log for ShapeFix messages")
print("  2. Compare face counts with previous conversion")
print("  3. Open jptower_building.step in CAD to verify walls")
print()
