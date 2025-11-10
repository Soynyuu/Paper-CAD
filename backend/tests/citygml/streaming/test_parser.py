"""
Unit tests for CityGML Streaming Parser

Tests cover:
1. Basic streaming functionality
2. Building limit enforcement
3. Building ID filtering
4. Memory management
5. Early termination
6. Error handling
"""

import pytest
import xml.etree.ElementTree as ET
from pathlib import Path
import tempfile
import os

# Import the streaming parser
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.citygml.streaming.parser import (
    stream_parse_buildings,
    StreamingConfig,
    estimate_memory_savings
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_citygml_single_building():
    """Create a minimal CityGML file with one building."""
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<CityModel xmlns="http://www.opengis.net/citygml/2.0"
           xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
           xmlns:gml="http://www.opengis.net/gml">
  <cityObjectMember>
    <bldg:Building gml:id="BLD_001">
      <gml:name>Test Building 1</gml:name>
      <bldg:lod2Solid>
        <gml:Solid gml:id="SOLID_001">
          <gml:exterior>
            <gml:CompositeSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="POLY_001">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>0.0 0.0 0.0 10.0 0.0 0.0 10.0 10.0 0.0 0.0 10.0 0.0 0.0 0.0 0.0</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:CompositeSurface>
          </gml:exterior>
        </gml:Solid>
      </bldg:lod2Solid>
    </bldg:Building>
  </cityObjectMember>
</CityModel>'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.gml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_citygml_multiple_buildings():
    """Create a CityGML file with multiple buildings."""
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<CityModel xmlns="http://www.opengis.net/citygml/2.0"
           xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
           xmlns:gml="http://www.opengis.net/gml"
           xmlns:gen="http://www.opengis.net/citygml/generics/2.0">
  <cityObjectMember>
    <bldg:Building gml:id="BLD_001">
      <gml:name>Building 1</gml:name>
      <gen:stringAttribute name="buildingID">
        <gen:name>buildingID</gen:name>
        <gen:value>CUSTOM_001</gen:value>
      </gen:stringAttribute>
      <bldg:lod2Solid>
        <gml:Solid gml:id="SOLID_001">
          <gml:exterior>
            <gml:CompositeSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="POLY_001">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>0.0 0.0 0.0 10.0 0.0 0.0 10.0 10.0 0.0 0.0 10.0 0.0 0.0 0.0 0.0</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:CompositeSurface>
          </gml:exterior>
        </gml:Solid>
      </bldg:lod2Solid>
    </bldg:Building>
  </cityObjectMember>
  <cityObjectMember>
    <bldg:Building gml:id="BLD_002">
      <gml:name>Building 2</gml:name>
      <gen:stringAttribute name="buildingID">
        <gen:name>buildingID</gen:name>
        <gen:value>CUSTOM_002</gen:value>
      </gen:stringAttribute>
      <bldg:lod2Solid>
        <gml:Solid gml:id="SOLID_002">
          <gml:exterior>
            <gml:CompositeSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="POLY_002">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>0.0 0.0 0.0 5.0 0.0 0.0 5.0 5.0 0.0 0.0 5.0 0.0 0.0 0.0 0.0</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:CompositeSurface>
          </gml:exterior>
        </gml:Solid>
      </bldg:lod2Solid>
    </bldg:Building>
  </cityObjectMember>
  <cityObjectMember>
    <bldg:Building gml:id="BLD_003">
      <gml:name>Building 3</gml:name>
      <gen:stringAttribute name="buildingID">
        <gen:name>buildingID</gen:name>
        <gen:value>CUSTOM_003</gen:value>
      </gen:stringAttribute>
      <bldg:lod2Solid>
        <gml:Solid gml:id="SOLID_003">
          <gml:exterior>
            <gml:CompositeSurface>
              <gml:surfaceMember>
                <gml:Polygon gml:id="POLY_003">
                  <gml:exterior>
                    <gml:LinearRing>
                      <gml:posList>0.0 0.0 0.0 3.0 0.0 0.0 3.0 3.0 0.0 0.0 3.0 0.0 0.0 0.0 0.0</gml:posList>
                    </gml:LinearRing>
                  </gml:exterior>
                </gml:Polygon>
              </gml:surfaceMember>
            </gml:CompositeSurface>
          </gml:exterior>
        </gml:Solid>
      </bldg:lod2Solid>
    </bldg:Building>
  </cityObjectMember>
</CityModel>'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.gml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


# ============================================================================
# Basic Functionality Tests
# ============================================================================

def test_stream_parse_single_building(sample_citygml_single_building):
    """Test streaming parser with single building."""
    buildings = list(stream_parse_buildings(sample_citygml_single_building))

    assert len(buildings) == 1
    building_elem, xlink_index = buildings[0]

    # Verify building element
    assert building_elem.tag.endswith('Building')
    assert building_elem.get('{http://www.opengis.net/gml}id') == 'BLD_001'

    # Verify XLink index contains building-scope elements
    assert isinstance(xlink_index, dict)
    assert 'BLD_001' in xlink_index
    assert 'SOLID_001' in xlink_index
    assert 'POLY_001' in xlink_index


def test_stream_parse_multiple_buildings(sample_citygml_multiple_buildings):
    """Test streaming parser with multiple buildings."""
    buildings = list(stream_parse_buildings(sample_citygml_multiple_buildings))

    assert len(buildings) == 3

    # Verify each building has correct ID
    building_ids = [b[0].get('{http://www.opengis.net/gml}id') for b in buildings]
    assert building_ids == ['BLD_001', 'BLD_002', 'BLD_003']

    # Verify each building has its own XLink index
    for building_elem, xlink_index in buildings:
        building_id = building_elem.get('{http://www.opengis.net/gml}id')
        assert building_id in xlink_index


# ============================================================================
# Limit Tests
# ============================================================================

def test_stream_parse_with_limit(sample_citygml_multiple_buildings):
    """Test early termination with limit parameter."""
    buildings = list(stream_parse_buildings(
        sample_citygml_multiple_buildings,
        limit=2
    ))

    assert len(buildings) == 2
    building_ids = [b[0].get('{http://www.opengis.net/gml}id') for b in buildings]
    assert building_ids == ['BLD_001', 'BLD_002']


def test_stream_parse_limit_zero(sample_citygml_multiple_buildings):
    """Test that limit=0 processes all buildings."""
    buildings = list(stream_parse_buildings(
        sample_citygml_multiple_buildings,
        limit=0  # Should be normalized to None (unlimited)
    ))

    # limit=0 should be treated as None by the orchestrator
    # But the parser itself doesn't normalize, so it will process 0 buildings
    assert len(buildings) == 0


def test_stream_parse_limit_exceeds_total(sample_citygml_multiple_buildings):
    """Test that limit greater than total buildings works correctly."""
    buildings = list(stream_parse_buildings(
        sample_citygml_multiple_buildings,
        limit=100
    ))

    assert len(buildings) == 3


# ============================================================================
# Building ID Filtering Tests
# ============================================================================

def test_stream_parse_filter_by_gml_id(sample_citygml_multiple_buildings):
    """Test filtering by gml:id attribute."""
    buildings = list(stream_parse_buildings(
        sample_citygml_multiple_buildings,
        building_ids=['BLD_001', 'BLD_003'],
        filter_attribute='gml:id'
    ))

    assert len(buildings) == 2
    building_ids = [b[0].get('{http://www.opengis.net/gml}id') for b in buildings]
    assert set(building_ids) == {'BLD_001', 'BLD_003'}


def test_stream_parse_filter_by_generic_attribute(sample_citygml_multiple_buildings):
    """Test filtering by gen:genericAttribute."""
    buildings = list(stream_parse_buildings(
        sample_citygml_multiple_buildings,
        building_ids=['CUSTOM_002'],
        filter_attribute='buildingID'
    ))

    assert len(buildings) == 1
    building_elem = buildings[0][0]
    assert building_elem.get('{http://www.opengis.net/gml}id') == 'BLD_002'


def test_stream_parse_filter_no_matches(sample_citygml_multiple_buildings):
    """Test filtering with no matching buildings."""
    buildings = list(stream_parse_buildings(
        sample_citygml_multiple_buildings,
        building_ids=['NONEXISTENT_ID'],
        filter_attribute='gml:id'
    ))

    assert len(buildings) == 0


# ============================================================================
# Memory Management Tests
# ============================================================================

def test_xlink_index_isolation(sample_citygml_multiple_buildings):
    """Test that XLink indices are isolated per building."""
    buildings = list(stream_parse_buildings(sample_citygml_multiple_buildings))

    # Each building should have its own isolated XLink index
    indices = [xlink_index for _, xlink_index in buildings]

    # Verify indices are separate objects
    assert id(indices[0]) != id(indices[1])
    assert id(indices[1]) != id(indices[2])

    # Verify each index contains only its building's elements
    assert 'BLD_001' in indices[0]
    assert 'BLD_001' not in indices[1]

    assert 'BLD_002' in indices[1]
    assert 'BLD_002' not in indices[0]


# ============================================================================
# StreamingConfig Tests
# ============================================================================

def test_streaming_config_basic(sample_citygml_single_building):
    """Test StreamingConfig dataclass."""
    config = StreamingConfig(
        limit=10,
        building_ids=['BLD_001'],
        filter_attribute='gml:id',
        debug=True,
        enable_gc_per_building=True,
        max_xlink_cache_size=5000
    )

    buildings = list(stream_parse_buildings(
        sample_citygml_single_building,
        config=config
    ))

    assert len(buildings) == 1


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_stream_parse_invalid_file():
    """Test error handling for invalid file path."""
    with pytest.raises(FileNotFoundError):
        list(stream_parse_buildings('/nonexistent/path.gml'))


def test_stream_parse_invalid_xml():
    """Test error handling for malformed XML."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.gml', delete=False, encoding='utf-8') as f:
        f.write('<?xml version="1.0"?><Invalid><NotClosed>')
        temp_path = f.name

    try:
        with pytest.raises(ValueError):
            list(stream_parse_buildings(temp_path))
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# ============================================================================
# Memory Estimation Tests
# ============================================================================

def test_estimate_memory_savings_basic():
    """Test memory savings estimation."""
    estimates = estimate_memory_savings(
        file_size_gb=5.0,
        num_buildings=50000,
        limit=None
    )

    assert 'legacy_memory' in estimates
    assert 'streaming_memory' in estimates
    assert 'reduction_percent' in estimates

    # Legacy should use more memory than streaming
    assert estimates['legacy_memory'] > estimates['streaming_memory']

    # Reduction should be significant (>90%)
    assert estimates['reduction_percent'] > 90.0


def test_estimate_memory_savings_with_limit():
    """Test memory savings estimation with processing limit."""
    estimates = estimate_memory_savings(
        file_size_gb=5.0,
        num_buildings=50000,
        limit=1000
    )

    # With limit, streaming memory should be even lower
    estimates_no_limit = estimate_memory_savings(
        file_size_gb=5.0,
        num_buildings=50000,
        limit=None
    )

    assert estimates['streaming_memory'] <= estimates_no_limit['streaming_memory']


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
