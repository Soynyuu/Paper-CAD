#!/usr/bin/env python3
"""
Test script for PLATEAU LOD2 face extraction fix
"""
import sys
sys.path.insert(0, '.')

from services.citygml_to_step import export_step_from_citygml
import os

print("="*60)
print("Testing PLATEAU LOD2 Conversion Fix")
print("="*60)
print()

# Test with test_small.gml (simpler test case)
input_file = 'test_small.gml'
output_file = 'test_output_lod2_fix.step'

if not os.path.exists(input_file):
    print(f"❌ Test file not found: {input_file}")
    print("   Please ensure test_small.gml exists in backend/")
    sys.exit(1)

print(f"Input: {input_file}")
print(f"Output: {output_file}")
print()
print("Running conversion with debug=True...")
print("-"*60)

try:
    result = export_step_from_citygml(
        input_file,
        output_file,
        debug=True  # Enable debug output to see statistics
    )
    print("-"*60)
    print()
    print("✅ Conversion completed successfully!")
    print(f"   Output file: {result}")

    # Check output file size
    if os.path.exists(output_file):
        size = os.path.getsize(output_file)
        print(f"   File size: {size:,} bytes")

        # Count faces in STEP file (rough estimate)
        with open(output_file, 'r') as f:
            content = f.read()
            face_count = content.count('ADVANCED_FACE')
            print(f"   Estimated face count: {face_count}")

            if face_count > 0:
                print()
                print("✅ SUCCESS: Faces were created!")
                print(f"   Expected: With the fix, face creation should succeed")
                print(f"   Without fix: Would have ~0-2 faces")
            else:
                print()
                print("⚠️  WARNING: No faces found in STEP file")
                print("   This might indicate the test file is too simple")

except Exception as e:
    print("-"*60)
    print()
    print(f"❌ Conversion failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("="*60)
print("Test Complete")
print("="*60)
