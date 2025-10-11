#!/usr/bin/env python3
"""
Test script for Nominatim API geocoding
"""

import requests
import json
import time

def test_geocoding(query: str):
    """Test geocoding with Nominatim API"""
    print(f"\n{'='*60}")
    print(f"Testing query: {query}")
    print(f"{'='*60}")

    url = "https://nominatim.openstreetmap.org/search"

    # Test different parameter combinations
    test_cases = [
        {
            "name": "Basic search",
            "params": {
                "q": query,
                "format": "json",
                "limit": 3,
            }
        },
        {
            "name": "With country code",
            "params": {
                "q": query,
                "format": "json",
                "limit": 3,
                "countrycodes": "jp",
            }
        },
        {
            "name": "With country code and language",
            "params": {
                "q": query,
                "format": "json",
                "limit": 3,
                "countrycodes": "jp",
                "accept-language": "ja",
            }
        },
        {
            "name": "With addressdetails",
            "params": {
                "q": query,
                "format": "json",
                "limit": 3,
                "countrycodes": "jp",
                "addressdetails": 1,
            }
        },
    ]

    headers = {
        "User-Agent": "Paper-CAD/1.0 (https://github.com/Soynyuu/paper-cad)"
    }

    for i, test in enumerate(test_cases):
        print(f"\n{i+1}. {test['name']}")
        print(f"   Params: {test['params']}")

        try:
            response = requests.get(url, params=test['params'], headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")

            if response.ok:
                data = response.json()
                print(f"   Results: {len(data)}")

                if data:
                    for j, result in enumerate(data[:3]):
                        print(f"\n   Result {j+1}:")
                        print(f"     Display name: {result.get('display_name', 'N/A')}")
                        print(f"     Lat/Lon: {result.get('lat', 'N/A')}, {result.get('lon', 'N/A')}")
                        print(f"     Type: {result.get('type', 'N/A')}")
                        print(f"     Class: {result.get('class', 'N/A')}")
                else:
                    print("   ❌ No results found")
            else:
                print(f"   ❌ Error: {response.status_code} {response.text}")

        except Exception as e:
            print(f"   ❌ Exception: {e}")

        # Respect rate limit
        time.sleep(1.5)

if __name__ == "__main__":
    # Test queries
    queries = [
        "東京駅",
        "東京都江東区豊洲6-2-7",
        "豊洲6-2-7",
        "Tokyo Station",
        "渋谷スクランブルスクエア",
        "Shibuya Scramble Square",
    ]

    for query in queries:
        test_geocoding(query)

    print(f"\n{'='*60}")
    print("Testing complete!")
    print(f"{'='*60}\n")
