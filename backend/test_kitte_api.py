#!/usr/bin/env python3
"""
KITTE API Debug Test - Call running backend API with debug enabled

This script calls the running backend API to fetch and convert KITTE building
with debug=True, which will output detailed logs to the backend server terminal.

Prerequisites:
    - Backend server must be running (python main.py)

Usage:
    python test_kitte_api.py

Output:
    - Client side: Request/response summary
    - Server side: Detailed debug logs in the backend terminal
"""

import requests
import os

API_URL = "http://localhost:8001/api/plateau/fetch-and-convert"

print("="*80)
print("KITTE API Debug Test")
print("="*80)
print()
print(f"Target API: {API_URL}")
print()
print("NOTE: Detailed debug logs will appear in the BACKEND TERMINAL")
print("      (where you ran 'python main.py')")
print()
print("-"*80)
print()

# Prepare request
form_data = {
    'query': 'Kitte丸の内',
    'radius': '0.001',
    'building_limit': '1',
    'debug': 'true',  # ENABLE DEBUG
    'method': 'solid',
    'auto_reproject': 'true',
    'precision_mode': 'standard',
    'shape_fix_level': 'minimal',
    'merge_building_parts': 'false'  # Keep parts separate
}

print("[1] Sending API request...")
print()
print("Parameters:")
for key, value in form_data.items():
    print(f"  {key}: {value}")
print()

try:
    # Send request
    response = requests.post(API_URL, data=form_data, timeout=120)

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
        output_file = "kitte_building_api.step"
        with open(output_file, 'wb') as f:
            f.write(response.content)

        file_size = os.path.getsize(output_file)
        print(f"STEP file saved: {output_file}")
        print(f"File size: {file_size:,} bytes")
        print()

        # Analyze file size
        if file_size < 50000:
            print("⚠ WARNING: File size suspiciously small (<50KB)")
            print("  Expected LOD2 building should be larger")
            print("  Check the BACKEND TERMINAL for debug logs")
        else:
            print("✓ File size looks reasonable for detailed LOD2")

        print()
        print("="*80)
        print("IMPORTANT: Check the BACKEND TERMINAL for detailed logs!")
        print("="*80)
        print()
        print("Look for these in the backend logs:")
        print("  - [LOD2] Found... / [LOD1] Found...")
        print("  - 'Found X BuildingPart(s)'")
        print("  - 'extracted X faces'")
        print("  - 'Solid extraction: X exterior faces'")
        print("  - 'boundedBy extraction: X faces'")
        print("  - Any ERROR or WARNING messages")
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
    print("✗ ERROR: Request timeout (>120s)")
    print()
    print("Check backend terminal for errors")
    print()

except Exception as e:
    print(f"✗ ERROR: {e}")
    print()

print("="*80)
print("Test complete")
print("="*80)
