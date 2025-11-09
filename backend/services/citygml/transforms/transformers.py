"""
Coordinate transformation functions using pyproj.

This module provides functions to create coordinate transformers for 2D (XY)
and 3D (XYZ) transformations between different CRS.
"""

from typing import Callable, Tuple

from ..core.types import CoordinateTransform2D, CoordinateTransform3D


def make_xy_transformer(source_crs: str, target_crs: str) -> CoordinateTransform2D:
    """
    Create a 2D coordinate transformer (x, y) → (X, Y).

    Automatically handles lat/lon swapping for geographic CRS (where CityGML
    often stores coordinates as (lat, lon) instead of (lon, lat)).

    Args:
        source_crs: Source CRS (e.g., "EPSG:4326", "EPSG:6668")
        target_crs: Target CRS (e.g., "EPSG:6676", "EPSG:6677")

    Returns:
        Transform function (x, y) -> (X, Y) in meters

    Example:
        >>> transformer = make_xy_transformer("EPSG:4326", "EPSG:6676")
        >>> # WGS84 (lat, lon) to JGD2011 Japan Plane CS 9
        >>> x, y = transformer(35.6811, 139.7670)
        >>> x, y
        (-32824.123, 23456.789)

    Raises:
        RuntimeError: If pyproj is not installed

    Notes:
        - Uses pyproj.Transformer with always_xy=True for consistent axis order
        - Automatically swaps lat/lon for geographic source CRS
        - Output is always in target CRS units (typically meters)
    """
    try:
        from pyproj import CRS, Transformer
    except Exception as e:
        raise RuntimeError("pyproj is required for reprojection but is not installed") from e

    s = CRS.from_user_input(source_crs)
    t = CRS.from_user_input(target_crs)
    transformer = Transformer.from_crs(s, t, always_xy=True)

    # If source is geographic (lat/lon), CityGML often stores as (lat, lon)
    # but pyproj always_xy expects (lon, lat), so we swap
    swap = s.is_geographic

    def tx(x: float, y: float) -> Tuple[float, float]:
        if swap:
            xx, yy = float(y), float(x)  # (lon, lat) for pyproj
        else:
            xx, yy = float(x), float(y)
        X, Y = transformer.transform(xx, yy)
        return X, Y

    return tx


def make_xyz_transformer(source_crs: str, target_crs: str) -> CoordinateTransform3D:
    """
    Create a 3D coordinate transformer (x, y, z) → (X, Y, Z).

    Similar to make_xy_transformer but handles 3D coordinates.
    Automatically handles lat/lon swapping for geographic CRS.

    Args:
        source_crs: Source CRS (e.g., "EPSG:4326", "EPSG:6668")
        target_crs: Target CRS (e.g., "EPSG:6676", "EPSG:6677")

    Returns:
        Transform function (x, y, z) -> (X, Y, Z) in meters

    Example:
        >>> transformer = make_xyz_transformer("EPSG:4326", "EPSG:6676")
        >>> # WGS84 (lat, lon, height) to JGD2011 Japan Plane CS 9
        >>> x, y, z = transformer(35.6811, 139.7670, 50.0)
        >>> x, y, z
        (-32824.123, 23456.789, 50.0)

    Raises:
        RuntimeError: If pyproj is not installed

    Notes:
        - Uses pyproj.Transformer with always_xy=True for consistent axis order
        - Automatically swaps lat/lon for geographic source CRS
        - Z coordinate is typically height/elevation in meters
        - Output is always in target CRS units (typically meters)
    """
    try:
        from pyproj import CRS, Transformer
    except Exception as e:
        raise RuntimeError("pyproj is required for reprojection but is not installed") from e

    s = CRS.from_user_input(source_crs)
    t = CRS.from_user_input(target_crs)
    transformer = Transformer.from_crs(s, t, always_xy=True)

    # If source is geographic (lat/lon), swap to (lon, lat) for pyproj
    swap = s.is_geographic

    def tx(x: float, y: float, z: float) -> Tuple[float, float, float]:
        if swap:
            xx, yy = float(y), float(x)  # (lon, lat) for pyproj
        else:
            xx, yy = float(x), float(y)
        X, Y, Z = transformer.transform(xx, yy, float(z))
        return X, Y, Z

    return tx
