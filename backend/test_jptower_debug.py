#!/usr/bin/env python3
"""
JP Tower API Debug Test - Test wall extraction for issue #48

This script calls the running backend API to fetch and convert JP Tower building
with debug=True, which will output detailed logs to the backend server terminal.

Issue #48: JP Tower walls are partially missing in STEP conversion
Expected: This fix should extract LOD3 WallSurface geometry correctly

Prerequisites:
    - Backend server must be running (python main.py)

Usage:
    python test_jptower_debug.py

Output:
    - Client side: Request/response summary
    - Server side: Detailed debug logs in the backend terminal
"""

import requests
import os

API_URL = "http://localhost:8001/api/plateau/fetch-and-convert"

print("="*80)
print("JP Tower Wall Extraction Debug Test (Issue #48)")
print("="*80)
print()
print(f"Target API: {API_URL}")
print("Building: JP Tower (JPタワー) - Marunouchi, Tokyo")
print("Address: 東京都千代田区丸の内2-7-2")
print()
print("NOTE: Detailed debug logs will appear in the BACKEND TERMINAL")
print("      (where you ran 'python main.py')")
print()
print("-"*80)
print()

# Prepare request
# Try facility name search first (recommended for better accuracy)
form_data = {
    'query': 'JPタワー',  # Facility name search
    'radius': '0.001',
    'building_limit': '1',
    'debug': 'true',  # ENABLE DEBUG
    'method': 'solid',
    'auto_reproject': 'true',
    'precision_mode': 'ultra',  # Use highest precision
    'shape_fix_level': 'ultra',  # Use most aggressive fixing
    'merge_building_parts': 'false'  # Keep parts separate to see details
}

print("[1] Sending API request...")
print()
print("Parameters:")
for key, value in form_data.items():
    print(f"  {key}: {value}")
print()

try:
    # Send request
    response = requests.post(API_URL, data=form_data, timeout=180)

    print("-"*80)
    print()
    print("[2] Response received")
    print()
    print(f"Status Code: {response.status_code}")
    print()

    if response.status_code == 200:
        print("✓ SUCCESS")
        print()

        # Get headers
        building_count = response.headers.get('X-Building-Count', 'N/A')
        print(f"Buildings converted: {building_count}")
        print()

        # Save STEP file
        output_file = "jptower_building.step"
        with open(output_file, 'wb') as f:
            f.write(response.content)

        file_size = os.path.getsize(output_file)
        print(f"STEP file saved: {output_file}")
        print(f"File size: {file_size:,} bytes")
        print()

        # Analyze file size
        if file_size < 100000:
            print("⚠ WARNING: File size suspiciously small (<100KB)")
            print("  JP Tower is a tall building and should have a large LOD2/LOD3 model")
            print("  Check the BACKEND TERMINAL for debug logs")
        else:
            print("✓ File size looks reasonable for detailed LOD2/LOD3")

        print()
        print("="*80)
        print("IMPORTANT: Check the BACKEND TERMINAL for detailed logs!")
        print("="*80)
        print()
        print("Look for these in the backend logs:")
        print("  1. LOD Detection:")
        print("     - [LOD DEBUG] Checking building:")
        print("     - ✓ Found LOD3 tag / ✓ Found LOD2 tag")
        print()
        print("  2. Conversion Strategy:")
        print("     - [CONVERSION DEBUG] Trying LOD3 Strategy...")
        print("     - [CONVERSION DEBUG] Trying LOD2 Strategy...")
        print("     - [CONVERSION DEBUG] Falling back to LOD2 (boundedBy)")
        print()
        print("  3. WallSurface Extraction:")
        print("     - [LOD2/LOD3] Found X boundedBy surfaces")
        print("     - WallSurface: extracted X faces")
        print("     - RoofSurface: extracted X faces")
        print()
        print("  4. BuildingPart:")
        print("     - Found X BuildingPart(s)")
        print("     - Extracted geometry from BuildingPart")
        print()
        print("  5. Expected for issue #48 fix:")
        print("     - Method 1 should find lod3MultiSurface or lod3Geometry")
        print("     - More WallSurface faces should be extracted than before")
        print()

    else:
        print(f"✗ FAILED")
        print()
        print("Response body:")
        try:
            error_data = response.json()
            print(f"  {error_data}")
        except:
            print(f"  {response.text[:500]}")
        print()

except requests.exceptions.ConnectionError:
    print("✗ ERROR: Cannot connect to backend API")
    print()
    print("Make sure the backend is running:")
    print("  cd backend")
    print("  python main.py")
    print()

except requests.exceptions.Timeout:
    print("✗ ERROR: Request timeout (>180s)")
    print()
    print("Check backend terminal for errors")
    print()

except Exception as e:
    print(f"✗ ERROR: {e}")
    print()

print("="*80)
print("Test complete - Issue #48 wall extraction verification")
print("="*80)
print()
print("Next steps:")
print("  1. Open jptower_building.step in a 3D viewer (e.g., FreeCAD)")
print("  2. Verify that walls are complete (no missing sections)")
print("  3. Compare with the screenshot in issue #48")
print()
