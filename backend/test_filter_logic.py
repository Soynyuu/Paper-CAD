"""
Unit tests for building filtering logic (without OCCT dependency).

Run:
  python3 test_filter_logic.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from services.citygml_to_step import (
    _extract_generic_attributes,
    _filter_buildings,
    NS,
)


def test_extract_generic_attributes():
    """Test extraction of generic attributes from building elements."""
    print("\n" + "="*70)
    print("TEST 1: Extract generic attributes")
    print("="*70)

    # Parse test file
    tree = ET.parse("samples/multiple_buildings.gml")
    root = tree.getroot()
    buildings = root.findall(".//bldg:Building", NS)

    print(f"\nFound {len(buildings)} buildings in test file")

    for i, b in enumerate(buildings):
        gml_id = b.get("{http://www.opengis.net/gml}id")
        attrs = _extract_generic_attributes(b)
        print(f"\nBuilding {i+1}:")
        print(f"  gml:id: {gml_id}")
        print(f"  Generic attributes: {attrs}")

        # Verify buildingID was extracted
        if "buildingID" in attrs:
            print(f"  ✓ buildingID extracted: {attrs['buildingID']}")
        else:
            print(f"  ✗ buildingID not found")

    return len(buildings) == 3  # Should have 3 buildings


def test_filter_by_gml_id():
    """Test filtering buildings by gml:id."""
    print("\n" + "="*70)
    print("TEST 2: Filter by gml:id")
    print("="*70)

    # Parse test file
    tree = ET.parse("samples/multiple_buildings.gml")
    root = tree.getroot()
    buildings = root.findall(".//bldg:Building", NS)

    print(f"\nOriginal building count: {len(buildings)}")

    # Test 2a: Filter single building
    filtered = _filter_buildings(buildings, ["bldg_001"], "gml:id")
    print(f"\n[2a] Filter for bldg_001: {len(filtered)} buildings")
    if len(filtered) == 1:
        gml_id = filtered[0].get("{http://www.opengis.net/gml}id")
        print(f"  ✓ Correct: Found {gml_id}")
    else:
        print(f"  ✗ Expected 1 building, got {len(filtered)}")
        return False

    # Test 2b: Filter multiple buildings
    filtered = _filter_buildings(buildings, ["bldg_001", "bldg_003"], "gml:id")
    print(f"\n[2b] Filter for bldg_001, bldg_003: {len(filtered)} buildings")
    if len(filtered) == 2:
        gml_ids = [b.get("{http://www.opengis.net/gml}id") for b in filtered]
        print(f"  ✓ Correct: Found {gml_ids}")
    else:
        print(f"  ✗ Expected 2 buildings, got {len(filtered)}")
        return False

    # Test 2c: Filter non-existent building
    filtered = _filter_buildings(buildings, ["bldg_999"], "gml:id")
    print(f"\n[2c] Filter for bldg_999 (non-existent): {len(filtered)} buildings")
    if len(filtered) == 0:
        print(f"  ✓ Correct: No buildings found")
    else:
        print(f"  ✗ Expected 0 buildings, got {len(filtered)}")
        return False

    # Test 2d: No filter
    filtered = _filter_buildings(buildings, None, "gml:id")
    print(f"\n[2d] No filter (None): {len(filtered)} buildings")
    if len(filtered) == 3:
        print(f"  ✓ Correct: All buildings returned")
    else:
        print(f"  ✗ Expected 3 buildings, got {len(filtered)}")
        return False

    return True


def test_filter_by_generic_attribute():
    """Test filtering buildings by generic attribute."""
    print("\n" + "="*70)
    print("TEST 3: Filter by generic attribute (buildingID)")
    print("="*70)

    # Parse test file
    tree = ET.parse("samples/multiple_buildings.gml")
    root = tree.getroot()
    buildings = root.findall(".//bldg:Building", NS)

    print(f"\nOriginal building count: {len(buildings)}")

    # Test 3a: Filter single building by buildingID
    filtered = _filter_buildings(buildings, ["TEST-002"], "buildingID")
    print(f"\n[3a] Filter for TEST-002: {len(filtered)} buildings")
    if len(filtered) == 1:
        gml_id = filtered[0].get("{http://www.opengis.net/gml}id")
        attrs = _extract_generic_attributes(filtered[0])
        print(f"  ✓ Correct: Found {gml_id} with buildingID={attrs.get('buildingID')}")
    else:
        print(f"  ✗ Expected 1 building, got {len(filtered)}")
        return False

    # Test 3b: Filter multiple buildings by buildingID
    filtered = _filter_buildings(buildings, ["TEST-001", "TEST-003"], "buildingID")
    print(f"\n[3b] Filter for TEST-001, TEST-003: {len(filtered)} buildings")
    if len(filtered) == 2:
        details = []
        for b in filtered:
            gml_id = b.get("{http://www.opengis.net/gml}id")
            attrs = _extract_generic_attributes(b)
            details.append(f"{gml_id}(buildingID={attrs.get('buildingID')})")
        print(f"  ✓ Correct: Found {', '.join(details)}")
    else:
        print(f"  ✗ Expected 2 buildings, got {len(filtered)}")
        return False

    return True


def main() -> int:
    print("\n" + "="*70)
    print("Building Filter Logic Unit Tests (OCCT-independent)")
    print("="*70)

    try:
        success = True

        # Run all tests
        success = test_extract_generic_attributes() and success
        success = test_filter_by_gml_id() and success
        success = test_filter_by_generic_attribute() and success

        print("\n" + "="*70)
        if success:
            print("✓ All unit tests passed")
            print("="*70)
            return 0
        else:
            print("✗ Some tests failed")
            print("="*70)
            return 1

    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
