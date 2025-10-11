"""
Test script for building ID filtering in CityGML → STEP conversion.

Run:
  python test_building_id_filter.py
"""

from __future__ import annotations

import os
import tempfile

from services.citygml_to_step import export_step_from_citygml


def test_filter_by_gml_id():
    """Test filtering buildings by gml:id attribute."""
    print("\n" + "="*70)
    print("TEST 1: Filter by gml:id")
    print("="*70)

    input_file = "samples/multiple_buildings.gml"
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
        output_file = tmp.name

    try:
        # Test 1a: Extract single building
        print("\n[1a] Extracting single building: bldg_001")
        ok, msg = export_step_from_citygml(
            input_file,
            output_file,
            building_ids=["bldg_001"],
            filter_attribute="gml:id",
            debug=True,
        )
        print(f"Result: {'✓ SUCCESS' if ok else '✗ FAILED'}")
        print(f"Message: {msg}")

        # Test 1b: Extract multiple buildings
        print("\n[1b] Extracting multiple buildings: bldg_001, bldg_003")
        ok, msg = export_step_from_citygml(
            input_file,
            output_file,
            building_ids=["bldg_001", "bldg_003"],
            filter_attribute="gml:id",
            debug=True,
        )
        print(f"Result: {'✓ SUCCESS' if ok else '✗ FAILED'}")
        print(f"Message: {msg}")

        # Test 1c: Non-existent building ID
        print("\n[1c] Attempting to extract non-existent building: bldg_999")
        ok, msg = export_step_from_citygml(
            input_file,
            output_file,
            building_ids=["bldg_999"],
            filter_attribute="gml:id",
            debug=True,
        )
        print(f"Result: {'✓ EXPECTED FAILURE' if not ok else '✗ UNEXPECTED SUCCESS'}")
        print(f"Message: {msg}")

    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)


def test_filter_by_generic_attribute():
    """Test filtering buildings by generic attribute."""
    print("\n" + "="*70)
    print("TEST 2: Filter by generic attribute (buildingID)")
    print("="*70)

    input_file = "samples/multiple_buildings.gml"
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
        output_file = tmp.name

    try:
        # Test 2a: Extract by buildingID attribute
        print("\n[2a] Extracting by generic attribute buildingID: TEST-002")
        ok, msg = export_step_from_citygml(
            input_file,
            output_file,
            building_ids=["TEST-002"],
            filter_attribute="buildingID",
            debug=True,
        )
        print(f"Result: {'✓ SUCCESS' if ok else '✗ FAILED'}")
        print(f"Message: {msg}")

        # Test 2b: Extract multiple by buildingID
        print("\n[2b] Extracting multiple by buildingID: TEST-001, TEST-003")
        ok, msg = export_step_from_citygml(
            input_file,
            output_file,
            building_ids=["TEST-001", "TEST-003"],
            filter_attribute="buildingID",
            debug=True,
        )
        print(f"Result: {'✓ SUCCESS' if ok else '✗ FAILED'}")
        print(f"Message: {msg}")

    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)


def test_no_filter():
    """Test conversion without filtering (baseline)."""
    print("\n" + "="*70)
    print("TEST 3: No filter (process all buildings)")
    print("="*70)

    input_file = "samples/multiple_buildings.gml"
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
        output_file = tmp.name

    try:
        print("\n[3a] Processing all buildings (no filter)")
        ok, msg = export_step_from_citygml(
            input_file,
            output_file,
            building_ids=None,
            debug=True,
        )
        print(f"Result: {'✓ SUCCESS' if ok else '✗ FAILED'}")
        print(f"Message: {msg}")

    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)


def main() -> int:
    print("\n" + "="*70)
    print("CityGML Building ID Filter Test Suite")
    print("="*70)

    try:
        test_filter_by_gml_id()
        test_filter_by_generic_attribute()
        test_no_filter()

        print("\n" + "="*70)
        print("✓ All tests completed")
        print("="*70)
        return 0

    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
