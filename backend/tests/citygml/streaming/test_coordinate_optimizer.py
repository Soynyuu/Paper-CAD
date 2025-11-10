"""
Unit tests for Coordinate Parsing Optimizer

Tests cover:
1. Optimized coordinate parsing (list comprehension)
2. NumPy vectorized parsing (if available)
3. 2D vs 3D detection
4. Error handling
5. Performance characteristics
"""

import pytest
import xml.etree.ElementTree as ET
import time
from pathlib import Path

# Import the coordinate optimizer
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.citygml.streaming.coordinate_optimizer import (
    parse_poslist_optimized,
    parse_poslist_numpy,
    parse_pos_optimized,
    parse_pos_numpy,
    benchmark_parsers,
    NUMPY_AVAILABLE
)


# ============================================================================
# Test Fixtures
# ============================================================================

def create_poslist_element(coords_text):
    """Helper to create gml:posList element."""
    return ET.fromstring(f'<gml:posList xmlns:gml="http://www.opengis.net/gml">{coords_text}</gml:posList>')


def create_pos_element(coords_text):
    """Helper to create gml:pos element."""
    return ET.fromstring(f'<gml:pos xmlns:gml="http://www.opengis.net/gml">{coords_text}</gml:pos>')


# ============================================================================
# Optimized Parser Tests (3D)
# ============================================================================

def test_parse_poslist_optimized_3d_basic():
    """Test 3D coordinate parsing."""
    elem = create_poslist_element('0.0 0.0 0.0 10.0 0.0 0.0 10.0 10.0 0.0 0.0 10.0 0.0')
    coords = parse_poslist_optimized(elem)

    assert len(coords) == 4
    assert coords[0] == (0.0, 0.0, 0.0)
    assert coords[1] == (10.0, 0.0, 0.0)
    assert coords[2] == (10.0, 10.0, 0.0)
    assert coords[3] == (0.0, 10.0, 0.0)


def test_parse_poslist_optimized_3d_complex():
    """Test 3D coordinates with varying heights."""
    elem = create_poslist_element('1.5 2.5 3.5 4.5 5.5 6.5 7.5 8.5 9.5')
    coords = parse_poslist_optimized(elem)

    assert len(coords) == 3
    assert coords[0] == (1.5, 2.5, 3.5)
    assert coords[1] == (4.5, 5.5, 6.5)
    assert coords[2] == (7.5, 8.5, 9.5)


# ============================================================================
# Optimized Parser Tests (2D)
# ============================================================================

def test_parse_poslist_optimized_2d_basic():
    """Test 2D coordinate parsing."""
    elem = create_poslist_element('0.0 0.0 10.0 0.0 10.0 10.0 0.0 10.0')
    coords = parse_poslist_optimized(elem)

    assert len(coords) == 4
    assert coords[0] == (0.0, 0.0, None)
    assert coords[1] == (10.0, 0.0, None)
    assert coords[2] == (10.0, 10.0, None)
    assert coords[3] == (0.0, 10.0, None)


# ============================================================================
# Edge Cases
# ============================================================================

def test_parse_poslist_optimized_empty():
    """Test empty element."""
    elem = create_poslist_element('')
    coords = parse_poslist_optimized(elem)
    assert coords == []


def test_parse_poslist_optimized_whitespace_only():
    """Test element with only whitespace."""
    elem = create_poslist_element('   \n  \t  ')
    coords = parse_poslist_optimized(elem)
    assert coords == []


def test_parse_poslist_optimized_extra_whitespace():
    """Test handling of extra whitespace."""
    elem = create_poslist_element('  0.0   0.0   0.0  10.0  0.0  0.0  ')
    coords = parse_poslist_optimized(elem)

    assert len(coords) == 2
    assert coords[0] == (0.0, 0.0, 0.0)
    assert coords[1] == (10.0, 0.0, 0.0)


def test_parse_poslist_optimized_invalid_tokens():
    """Test handling of invalid tokens (non-numeric)."""
    elem = create_poslist_element('0.0 0.0 0.0 INVALID 10.0 0.0 0.0')
    coords = parse_poslist_optimized(elem)

    # Should skip invalid token and try to parse remaining
    # Result depends on how many valid floats remain
    # With "0.0 0.0 0.0 10.0 0.0 0.0" = 6 floats = 2 3D points
    assert len(coords) == 2
    assert coords[0] == (0.0, 0.0, 0.0)
    assert coords[1] == (10.0, 0.0, 0.0)


def test_parse_poslist_optimized_invalid_dimensionality():
    """Test handling of invalid dimensionality (not divisible by 2 or 3)."""
    elem = create_poslist_element('0.0 0.0 0.0 10.0 0.0')
    coords = parse_poslist_optimized(elem)

    # 5 floats - not divisible by 2 or 3
    # Should return empty list
    assert coords == []


# ============================================================================
# NumPy Parser Tests (if available)
# ============================================================================

@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_parse_poslist_numpy_3d_basic():
    """Test NumPy 3D coordinate parsing."""
    elem = create_poslist_element('0.0 0.0 0.0 10.0 0.0 0.0 10.0 10.0 0.0 0.0 10.0 0.0')
    coords = parse_poslist_numpy(elem)

    assert len(coords) == 4
    assert coords[0] == (0.0, 0.0, 0.0)
    assert coords[1] == (10.0, 0.0, 0.0)
    assert coords[2] == (10.0, 10.0, 0.0)
    assert coords[3] == (0.0, 10.0, 0.0)


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_parse_poslist_numpy_2d_basic():
    """Test NumPy 2D coordinate parsing."""
    elem = create_poslist_element('0.0 0.0 10.0 0.0 10.0 10.0 0.0 10.0')
    coords = parse_poslist_numpy(elem)

    assert len(coords) == 4
    assert coords[0] == (0.0, 0.0, None)
    assert coords[1] == (10.0, 0.0, None)
    assert coords[2] == (10.0, 10.0, None)
    assert coords[3] == (0.0, 10.0, None)


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_parse_poslist_numpy_empty():
    """Test NumPy parser with empty element."""
    elem = create_poslist_element('')
    coords = parse_poslist_numpy(elem)
    assert coords == []


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_parse_poslist_numpy_fallback_on_error():
    """Test that NumPy parser falls back to optimized on invalid data."""
    elem = create_poslist_element('0.0 0.0 0.0 INVALID 10.0 0.0')
    coords = parse_poslist_numpy(elem)

    # Should fallback to optimized parser, which handles invalid tokens
    # Result: 5 valid floats - not divisible by 2 or 3, returns []
    assert coords == []


# ============================================================================
# Single Coordinate (gml:pos) Tests
# ============================================================================

def test_parse_pos_optimized_3d():
    """Test single 3D coordinate parsing."""
    elem = create_pos_element('1.5 2.5 3.5')
    coord = parse_pos_optimized(elem)

    assert coord == (1.5, 2.5, 3.5)


def test_parse_pos_optimized_2d():
    """Test single 2D coordinate parsing."""
    elem = create_pos_element('1.5 2.5')
    coord = parse_pos_optimized(elem)

    assert coord == (1.5, 2.5, None)


def test_parse_pos_optimized_empty():
    """Test single coordinate with empty element."""
    elem = create_pos_element('')
    coord = parse_pos_optimized(elem)

    assert coord is None


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_parse_pos_numpy_3d():
    """Test NumPy single 3D coordinate parsing."""
    elem = create_pos_element('1.5 2.5 3.5')
    coord = parse_pos_numpy(elem)

    assert coord == (1.5, 2.5, 3.5)


# ============================================================================
# Performance Tests
# ============================================================================

def test_benchmark_parsers_basic():
    """Test benchmark function."""
    sample_text = '0.0 0.0 0.0 10.0 0.0 0.0 10.0 10.0 0.0 0.0 10.0 0.0'
    results = benchmark_parsers(sample_text, iterations=100)

    assert 'optimized' in results
    assert results['optimized'] > 0

    if NUMPY_AVAILABLE:
        assert 'numpy' in results
        assert 'numpy_speedup' in results
        assert results['numpy'] > 0
        assert results['numpy_speedup'] > 0


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_numpy_faster_than_optimized():
    """Test that NumPy parser is faster for large datasets."""
    # Large dataset: 10,000 points
    points = ' '.join([f'{i}.0 {i+1}.0 {i+2}.0' for i in range(10000)])
    results = benchmark_parsers(points, iterations=10)

    # NumPy should be faster (speedup > 1.0)
    assert results['numpy_speedup'] > 1.0


# ============================================================================
# Consistency Tests (Optimized vs NumPy)
# ============================================================================

@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_optimized_numpy_consistency_3d():
    """Test that optimized and NumPy parsers produce identical results for 3D."""
    elem = create_poslist_element('1.1 2.2 3.3 4.4 5.5 6.6 7.7 8.8 9.9')

    coords_opt = parse_poslist_optimized(elem)
    coords_numpy = parse_poslist_numpy(elem)

    assert len(coords_opt) == len(coords_numpy)
    for i in range(len(coords_opt)):
        assert coords_opt[i] == coords_numpy[i]


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_optimized_numpy_consistency_2d():
    """Test that optimized and NumPy parsers produce identical results for 2D."""
    elem = create_poslist_element('1.1 2.2 3.3 4.4 5.5 6.6')

    coords_opt = parse_poslist_optimized(elem)
    coords_numpy = parse_poslist_numpy(elem)

    assert len(coords_opt) == len(coords_numpy)
    for i in range(len(coords_opt)):
        assert coords_opt[i] == coords_numpy[i]


# ============================================================================
# Large Dataset Tests
# ============================================================================

def test_parse_poslist_optimized_large_3d():
    """Test optimized parser with large 3D dataset (1000 points)."""
    points = ' '.join([f'{i}.0 {i+1}.0 {i+2}.0' for i in range(1000)])
    elem = create_poslist_element(points)

    coords = parse_poslist_optimized(elem)

    assert len(coords) == 1000
    assert coords[0] == (0.0, 1.0, 2.0)
    assert coords[-1] == (999.0, 1000.0, 1001.0)


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
def test_parse_poslist_numpy_large_3d():
    """Test NumPy parser with large 3D dataset (1000 points)."""
    points = ' '.join([f'{i}.0 {i+1}.0 {i+2}.0' for i in range(1000)])
    elem = create_poslist_element(points)

    coords = parse_poslist_numpy(elem)

    assert len(coords) == 1000
    assert coords[0] == (0.0, 1.0, 2.0)
    assert coords[-1] == (999.0, 1000.0, 1001.0)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
