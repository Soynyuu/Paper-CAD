#!/usr/bin/env python3
"""
Test script for PLATEAU Data Catalog API
"""

import requests
import sys


def test_plateau_api(name: str, lat: float, lon: float, radius: float = 0.001):
    """Test PLATEAU API with specific coordinates"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Coordinates: ({lat}, {lon})")
    print(f"Radius: {radius}")
    print(f"{'='*60}")

    # Calculate bounding box
    lon1 = lon - radius
    lat1 = lat - radius
    lon2 = lon + radius
    lat2 = lat + radius

    # PLATEAU API endpoint (note: lon,lat order!)
    url = f"https://api.plateauview.mlit.go.jp/datacatalog/citygml/r:{lon1},{lat1},{lon2},{lat2}"

    print(f"\nURL: {url}")
    print(f"Bbox: ({lat1},{lon1}) to ({lat2},{lon2})")

    try:
        print(f"\nSending request...")
        response = requests.get(url, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"Content-Length: {len(response.content)} bytes")

        if response.ok:
            content = response.text
            if content.strip().startswith("<?xml"):
                print("✓ Valid XML response")
                # Count buildings
                building_count = content.count("<bldg:Building")
                print(f"✓ Found {building_count} building(s)")
            else:
                print("❌ Response is not XML")
                print(f"First 200 chars: {content[:200]}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")

    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    # Test cases with known locations
    test_cases = [
        ("Tokyo Station (東京駅)", 35.681236, 139.767125, 0.001),
        ("Shibuya Scramble Square", 35.6583792, 139.7022161, 0.001),
        ("Tokyo Station (larger radius)", 35.681236, 139.767125, 0.005),
        ("Shibuya (larger radius)", 35.6583792, 139.7022161, 0.005),
        # Tokyo city area
        ("Toyosu (豊洲)", 35.6544, 139.7967, 0.001),
        # Known PLATEAU coverage area
        ("Marunouchi", 35.6814, 139.7650, 0.001),
    ]

    for name, lat, lon, radius in test_cases:
        test_plateau_api(name, lat, lon, radius)
        print()

    print(f"\n{'='*60}")
    print("Testing complete!")
    print(f"{'='*60}\n")
