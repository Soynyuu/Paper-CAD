"""
Tests for CityGML Cache functionality in plateau_fetcher.py

This test suite verifies:
- Mesh index loading and caching
- Ward resolution from mesh codes
- Cache hit/miss scenarios
- API fallback behavior
- Environment variable configuration
- Backward compatibility
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.plateau_fetcher import (
    _get_cache_config,
    _load_mesh_index,
    _get_ward_from_mesh,
    _get_wards_from_mesh,
    _load_gml_from_cache,
    _load_gml_from_cache_multi,
    _combine_gml_files,
    fetch_citygml_from_plateau,
    fetch_citygml_by_mesh_code,
    fetch_citygml_by_municipality,
    _MESH_INDEX_CACHE
)


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)

        # Create mesh index
        mesh_index = {
            "version": "1.0.0",
            "created_at": "2024-01-12T10:00:00Z",
            "index": {
                "53393580": "13101",  # Chiyoda-ku
                "53393581": "13101",
                "53393586": "13113",  # Shibuya-ku
                "53393587": ["13113", "13104"]  # Mesh spanning multiple wards
            }
        }

        with open(cache_dir / "mesh_to_ward_index.json", 'w', encoding='utf-8') as f:
            json.dump(mesh_index, f)

        # Create ward directory for Chiyoda-ku (13101)
        ward_dir = cache_dir / "13101_千代田区"
        ward_dir.mkdir(parents=True)

        # Create ward metadata
        ward_metadata = {
            "area_code": "13101",
            "ward_name": "千代田区",
            "mesh_codes": ["53393580", "53393581"]
        }

        with open(ward_dir / "ward_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(ward_metadata, f)

        # Create GML files
        gml_dir = ward_dir / "udx" / "bldg"
        gml_dir.mkdir(parents=True)

        # Sample CityGML content
        sample_gml = """<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:core="http://www.opengis.net/citygml/2.0"
                xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                xmlns:gml="http://www.opengis.net/gml">
  <core:cityObjectMember>
    <bldg:Building gml:id="test_building_1">
      <gml:name>Test Building 1</gml:name>
    </bldg:Building>
  </core:cityObjectMember>
</core:CityModel>"""

        with open(gml_dir / "53393580_bldg_001_op.gml", 'w', encoding='utf-8') as f:
            f.write(sample_gml)

        with open(gml_dir / "53393580_bldg_002_op.gml", 'w', encoding='utf-8') as f:
            f.write(sample_gml.replace("test_building_1", "test_building_2"))

        # Create ward directories for multi-ward mesh (53393587 spans 13113 and 13104)
        multi_ward_samples = [
            ("13113", "渋谷区", "multi_ward_building_1"),
            ("13104", "新宿区", "multi_ward_building_2"),
        ]

        for area_code, ward_name, building_id in multi_ward_samples:
            ward_dir = cache_dir / f"{area_code}_{ward_name}"
            ward_dir.mkdir(parents=True)

            ward_metadata = {
                "area_code": area_code,
                "ward_name": ward_name,
                "mesh_codes": ["53393587"]
            }

            with open(ward_dir / "ward_metadata.json", 'w', encoding='utf-8') as f:
                json.dump(ward_metadata, f)

            gml_dir = ward_dir / "udx" / "bldg"
            gml_dir.mkdir(parents=True)
            gml_content = sample_gml.replace("test_building_1", building_id)
            with open(gml_dir / "53393587_bldg_001_op.gml", 'w', encoding='utf-8') as f:
                f.write(gml_content)

        yield cache_dir


class TestCacheConfiguration:
    """Test cache configuration loading."""

    def test_get_cache_config_default(self):
        """Test default cache configuration."""
        with patch.dict(os.environ, {}, clear=True):
            config = _get_cache_config()
            assert config["enabled"] is False
            assert "citygml_cache" in str(config["cache_dir"])

    def test_get_cache_config_enabled(self):
        """Test cache configuration when enabled."""
        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": "/custom/path"
        }):
            config = _get_cache_config()
            assert config["enabled"] is True
            assert str(config["cache_dir"]) == "/custom/path"


class TestMeshIndexLoading:
    """Test mesh index loading and caching."""

    def test_load_mesh_index_disabled(self, temp_cache_dir):
        """Test that mesh index returns empty dict when cache is disabled."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {"CITYGML_CACHE_ENABLED": "false"}):
            index = _load_mesh_index()
            assert index == {}

    def test_load_mesh_index_success(self, temp_cache_dir):
        """Test successful mesh index loading."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            index = _load_mesh_index()
            assert "53393580" in index
            assert index["53393580"] == "13101"
            assert index["53393587"] == ["13113", "13104"]  # Multi-ward mesh

    def test_load_mesh_index_caching(self, temp_cache_dir):
        """Test that mesh index is cached after first load."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            index1 = _load_mesh_index()
            index2 = _load_mesh_index()
            # Should return same object (cached)
            assert index1 is index2


class TestWardResolution:
    """Test mesh code to ward resolution."""

    def test_get_ward_from_mesh_single_ward(self, temp_cache_dir):
        """Test ward resolution for mesh in single ward."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            ward = _get_ward_from_mesh("53393580")
            assert ward == "13101"

    def test_get_ward_from_mesh_multiple_wards(self, temp_cache_dir):
        """Test ward resolution for mesh spanning multiple wards (returns first)."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            ward = _get_ward_from_mesh("53393587")
            assert ward == "13113"  # Should return first ward

    def test_get_wards_from_mesh_multiple_wards(self, temp_cache_dir):
        """Test ward list resolution for mesh spanning multiple wards."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            wards = _get_wards_from_mesh("53393587")
            assert wards == ["13113", "13104"]

    def test_get_ward_from_mesh_not_found(self, temp_cache_dir):
        """Test ward resolution for unknown mesh code."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            ward = _get_ward_from_mesh("99999999")
            assert ward is None


class TestCacheHit:
    """Test cache hit scenarios."""

    def test_load_gml_from_cache_success(self, temp_cache_dir):
        """Test successful GML loading from cache."""
        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            xml = _load_gml_from_cache("53393580", "13101")
            assert xml is not None
            assert "test_building" in xml
            assert "CityModel" in xml

    def test_load_gml_from_cache_not_found(self, temp_cache_dir):
        """Test GML loading when mesh not in cache."""
        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            xml = _load_gml_from_cache("99999999", "13101")
            assert xml is None

    def test_load_gml_from_cache_multi_ward(self, temp_cache_dir):
        """Test loading GML from multiple ward caches for a single mesh."""
        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            xml = _load_gml_from_cache_multi("53393587", ["13113", "13104"])
            assert xml is not None
            assert "multi_ward_building_1" in xml
            assert "multi_ward_building_2" in xml

    @patch('services.plateau_fetcher.requests.get')
    def test_fetch_citygml_by_mesh_code_multi_ward_cache_hit(
        self, mock_requests_get, temp_cache_dir
    ):
        """Test mesh cache hit across multiple wards without API fallback."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            xml = fetch_citygml_by_mesh_code("53393587", timeout=30)
            assert xml is not None
            assert "multi_ward_building_1" in xml
            assert "multi_ward_building_2" in xml
            assert not mock_requests_get.called


class TestCombineGmlFiles:
    """Test combining multiple GML files."""

    def test_combine_gml_files_single(self, temp_cache_dir):
        """Test combining single GML file (returns as-is)."""
        gml_file = temp_cache_dir / "13101_千代田区" / "udx" / "bldg" / "53393580_bldg_001_op.gml"
        combined = _combine_gml_files([gml_file])
        assert "test_building_1" in combined
        assert "CityModel" in combined

    def test_combine_gml_files_multiple(self, temp_cache_dir):
        """Test combining multiple GML files."""
        gml_dir = temp_cache_dir / "13101_千代田区" / "udx" / "bldg"
        gml_files = [
            gml_dir / "53393580_bldg_001_op.gml",
            gml_dir / "53393580_bldg_002_op.gml"
        ]
        combined = _combine_gml_files(gml_files)
        assert "test_building_1" in combined
        assert "test_building_2" in combined
        # Should have merged cityObjectMember elements
        assert combined.count("cityObjectMember") >= 2


class TestCacheFallback:
    """Test cache miss and API fallback scenarios."""

    @patch('services.plateau_fetcher.requests.get')
    @patch('services.plateau_fetcher.latlon_to_mesh_3rd')
    def test_fetch_citygml_from_plateau_cache_disabled(
        self, mock_latlon_to_mesh, mock_requests_get, temp_cache_dir
    ):
        """Test that API is used when cache is disabled."""
        # Mock mesh calculation
        mock_latlon_to_mesh.return_value = "53393580"

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cities": [{
                "cityName": "Test City",
                "files": {
                    "bldg": [{
                        "url": "http://example.com/test.gml"
                    }]
                }
            }]
        }
        mock_response.text = "<CityModel>Test</CityModel>"
        mock_requests_get.return_value = mock_response

        with patch.dict(os.environ, {"CITYGML_CACHE_ENABLED": "false"}):
            xml = fetch_citygml_from_plateau(35.681236, 139.767125)
            # Should fall back to API
            assert mock_requests_get.called

    @patch('services.plateau_fetcher.requests.get')
    @patch('services.plateau_fetcher.latlon_to_mesh_3rd')
    def test_fetch_citygml_from_plateau_cache_miss(
        self, mock_latlon_to_mesh, mock_requests_get, temp_cache_dir
    ):
        """Test API fallback when cache miss occurs."""
        # Clear module-level cache
        import services.plateau_fetcher
        services.plateau_fetcher._MESH_INDEX_CACHE = None

        # Mock mesh calculation (unknown mesh)
        mock_latlon_to_mesh.return_value = "99999999"

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cities": [{
                "cityName": "Test City",
                "files": {
                    "bldg": [{
                        "url": "http://example.com/test.gml"
                    }]
                }
            }]
        }
        mock_response.text = "<CityModel>Test</CityModel>"
        mock_requests_get.return_value = mock_response

        with patch.dict(os.environ, {
            "CITYGML_CACHE_ENABLED": "true",
            "CITYGML_CACHE_DIR": str(temp_cache_dir)
        }):
            xml = fetch_citygml_from_plateau(35.681236, 139.767125)
            # Should fall back to API after cache miss
            assert mock_requests_get.called


class TestBackwardCompatibility:
    """Test that cache integration maintains backward compatibility."""

    @patch('services.plateau_fetcher.requests.get')
    @patch('services.plateau_fetcher.latlon_to_mesh_3rd')
    def test_fetch_citygml_from_plateau_signature(
        self, mock_latlon_to_mesh, mock_requests_get
    ):
        """Test that function signature is unchanged."""
        # Mock mesh calculation
        mock_latlon_to_mesh.return_value = "53393580"

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cities": [{
                "cityName": "Test City",
                "files": {
                    "bldg": [{
                        "url": "http://example.com/test.gml"
                    }]
                }
            }]
        }
        mock_response.text = "<CityModel>Test</CityModel>"
        mock_requests_get.return_value = mock_response

        # Call with original signature
        xml = fetch_citygml_from_plateau(35.681236, 139.767125, radius=0.001, timeout=30)

        # Should return string or None (original behavior)
        assert xml is None or isinstance(xml, str)

    @patch('services.plateau_fetcher.requests.get')
    def test_fetch_citygml_by_mesh_code_signature(self, mock_requests_get):
        """Test that function signature is unchanged."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cities": [{
                "cityName": "Test City",
                "files": {
                    "bldg": [{
                        "url": "http://example.com/test.gml"
                    }]
                }
            }]
        }
        mock_response.text = "<CityModel>Test</CityModel>"
        mock_requests_get.return_value = mock_response

        # Call with original signature
        xml = fetch_citygml_by_mesh_code("53393580", timeout=30)

        # Should return string or None (original behavior)
        assert xml is None or isinstance(xml, str)
