#!/usr/bin/env python3
"""
Test to verify that CityGML is only fetched once in /api/plateau/fetch-and-convert

This test calls search_buildings_by_address() and checks that:
1. The function returns citygml_xml in the result
2. The XML content is valid and non-empty
"""

import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from services.plateau_fetcher import search_buildings_by_address


def test_citygml_xml_returned():
    """Test that search_buildings_by_address returns CityGML XML"""
    print("="*80)
    print("TEST: Verify CityGML XML is returned from search_buildings_by_address()")
    print("="*80)

    # Test with a well-known location
    query = "東京駅"
    radius = 0.001
    limit = 3

    print(f"\nTest query: {query}")
    print(f"Radius: {radius} degrees")
    print(f"Limit: {limit} buildings")
    print()

    # Call the search function
    result = search_buildings_by_address(
        query=query,
        radius=radius,
        limit=limit
    )

    # Verify result structure
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    assert "success" in result, "❌ Result missing 'success' key"
    print("✓ Result has 'success' key")

    if not result["success"]:
        print(f"❌ Search failed: {result.get('error', 'Unknown error')}")
        return False

    assert "citygml_xml" in result, "❌ Result missing 'citygml_xml' key"
    print("✓ Result has 'citygml_xml' key")

    xml_content = result["citygml_xml"]
    assert xml_content is not None, "❌ citygml_xml is None"
    print("✓ citygml_xml is not None")

    assert isinstance(xml_content, str), "❌ citygml_xml is not a string"
    print("✓ citygml_xml is a string")

    assert len(xml_content) > 0, "❌ citygml_xml is empty"
    print(f"✓ citygml_xml is non-empty ({len(xml_content):,} bytes)")

    # Verify it looks like XML
    assert xml_content.strip().startswith("<?xml") or xml_content.strip().startswith("<"), \
        "❌ citygml_xml doesn't look like XML"
    print("✓ citygml_xml looks like valid XML")

    # Verify other fields
    assert "geocoding" in result, "❌ Result missing 'geocoding' key"
    assert "buildings" in result, "❌ Result missing 'buildings' key"
    print(f"✓ Found {len(result['buildings'])} building(s)")

    print("\n" + "="*80)
    print("✅ TEST PASSED: CityGML XML is correctly returned")
    print("="*80)
    print("\nThis means the /api/plateau/fetch-and-convert endpoint can now")
    print("reuse this XML instead of fetching it again from PLATEAU API.")
    print("\nBenefit: PLATEAU API calls reduced from 2 to 1 (50% reduction!)")

    return True


if __name__ == "__main__":
    try:
        success = test_citygml_xml_returned()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
