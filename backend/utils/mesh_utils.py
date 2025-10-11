"""
Japanese Standard Regional Mesh Code Utilities

Converts latitude/longitude coordinates to Japanese Standard Regional Mesh Codes
according to JIS X 0410 standard.

Mesh Levels:
- 1st mesh (80km): 4 digits (e.g., "5339")
- 2nd mesh (10km): 6 digits (e.g., "533945")
- 3rd mesh (1km): 8 digits (e.g., "53394511")
- 1/2 mesh (500m): 9 digits (e.g., "533945111")
- 1/4 mesh (250m): 10 digits (e.g., "5339451111")

Reference:
https://www.stat.go.jp/data/mesh/gaiyou.html
"""

from typing import Tuple


def latlon_to_mesh_1st(lat: float, lon: float) -> str:
    """Convert lat/lon to 1st mesh code (80km, 4 digits)

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        4-digit mesh code (e.g., "5339")
    """
    p = int(lat * 60 / 40)
    q = int(lon - 100)
    return f"{p:02d}{q:02d}"


def latlon_to_mesh_2nd(lat: float, lon: float) -> str:
    """Convert lat/lon to 2nd mesh code (10km, 6 digits)

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        6-digit mesh code (e.g., "533945")
    """
    # 1st mesh
    mesh1 = latlon_to_mesh_1st(lat, lon)

    # Calculate 2nd mesh indices within 1st mesh
    p = int(lat * 60 / 40)
    q = int(lon - 100)

    lat_remainder = lat - (p * 40 / 60)
    lon_remainder = lon - (100 + q)

    r = int(lat_remainder * 60 / 5)
    s = int(lon_remainder * 60 / 7.5)

    return f"{mesh1}{r}{s}"


def latlon_to_mesh_3rd(lat: float, lon: float) -> str:
    """Convert lat/lon to 3rd mesh code (1km, 8 digits)

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        8-digit mesh code (e.g., "53394511")
    """
    # 2nd mesh
    mesh2 = latlon_to_mesh_2nd(lat, lon)

    # Calculate 3rd mesh indices within 2nd mesh
    p = int(lat * 60 / 40)
    q = int(lon - 100)

    lat_remainder1 = lat - (p * 40 / 60)
    lon_remainder1 = lon - (100 + q)

    r = int(lat_remainder1 * 60 / 5)
    s = int(lon_remainder1 * 60 / 7.5)

    lat_remainder2 = lat_remainder1 - (r * 5 / 60)
    lon_remainder2 = lon_remainder1 - (s * 7.5 / 60)

    t = int(lat_remainder2 * 60 / 0.5)
    u = int(lon_remainder2 * 60 / 0.75)

    return f"{mesh2}{t}{u}"


def latlon_to_mesh_half(lat: float, lon: float) -> str:
    """Convert lat/lon to 1/2 mesh code (500m, 9 digits)

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        9-digit mesh code (e.g., "533945111")
    """
    # 3rd mesh
    mesh3 = latlon_to_mesh_3rd(lat, lon)

    # Calculate 1/2 mesh index within 3rd mesh
    p = int(lat * 60 / 40)
    q = int(lon - 100)

    lat_remainder1 = lat - (p * 40 / 60)
    lon_remainder1 = lon - (100 + q)

    r = int(lat_remainder1 * 60 / 5)
    s = int(lon_remainder1 * 60 / 7.5)

    lat_remainder2 = lat_remainder1 - (r * 5 / 60)
    lon_remainder2 = lon_remainder1 - (s * 7.5 / 60)

    t = int(lat_remainder2 * 60 / 0.5)
    u = int(lon_remainder2 * 60 / 0.75)

    lat_remainder3 = lat_remainder2 - (t * 0.5 / 60)
    lon_remainder3 = lon_remainder2 - (u * 0.75 / 60)

    # 1/2 mesh: 2x2 subdivision (1=SW, 2=SE, 3=NW, 4=NE)
    half_lat = int(lat_remainder3 / (0.25 / 60))
    half_lon = int(lon_remainder3 / (0.375 / 60))

    half_code = half_lat * 2 + half_lon + 1

    return f"{mesh3}{half_code}"


def latlon_to_mesh_quarter(lat: float, lon: float) -> str:
    """Convert lat/lon to 1/4 mesh code (250m, 10 digits)

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees

    Returns:
        10-digit mesh code (e.g., "5339451111")
    """
    # 1/2 mesh
    mesh_half = latlon_to_mesh_half(lat, lon)

    # Calculate 1/4 mesh index within 1/2 mesh
    p = int(lat * 60 / 40)
    q = int(lon - 100)

    lat_remainder1 = lat - (p * 40 / 60)
    lon_remainder1 = lon - (100 + q)

    r = int(lat_remainder1 * 60 / 5)
    s = int(lon_remainder1 * 60 / 7.5)

    lat_remainder2 = lat_remainder1 - (r * 5 / 60)
    lon_remainder2 = lon_remainder1 - (s * 7.5 / 60)

    t = int(lat_remainder2 * 60 / 0.5)
    u = int(lon_remainder2 * 60 / 0.75)

    lat_remainder3 = lat_remainder2 - (t * 0.5 / 60)
    lon_remainder3 = lon_remainder2 - (u * 0.75 / 60)

    half_lat = int(lat_remainder3 / (0.25 / 60))
    half_lon = int(lon_remainder3 / (0.375 / 60))

    lat_remainder4 = lat_remainder3 - (half_lat * 0.25 / 60)
    lon_remainder4 = lon_remainder3 - (half_lon * 0.375 / 60)

    # 1/4 mesh: 2x2 subdivision (1=SW, 2=SE, 3=NW, 4=NE)
    quarter_lat = int(lat_remainder4 / (0.125 / 60))
    quarter_lon = int(lon_remainder4 / (0.1875 / 60))

    quarter_code = quarter_lat * 2 + quarter_lon + 1

    return f"{mesh_half}{quarter_code}"


def get_neighboring_meshes_3rd(mesh_code: str) -> list[str]:
    """Get 8 neighboring 3rd mesh codes around the given mesh

    Args:
        mesh_code: 8-digit 3rd mesh code

    Returns:
        List of 9 mesh codes (center + 8 neighbors)
    """
    if len(mesh_code) != 8:
        raise ValueError(f"Expected 8-digit 3rd mesh code, got: {mesh_code}")

    mesh1 = mesh_code[:4]
    r = int(mesh_code[4])
    s = int(mesh_code[5])
    t = int(mesh_code[6])
    u = int(mesh_code[7])

    meshes = []

    # 3x3 grid around center
    for dt in [-1, 0, 1]:
        for du in [-1, 0, 1]:
            new_t = t + dt
            new_u = u + du
            new_r = r
            new_s = s

            # Handle overflow/underflow for 3rd mesh
            if new_t < 0:
                new_t += 10
                new_r -= 1
            elif new_t >= 10:
                new_t -= 10
                new_r += 1

            if new_u < 0:
                new_u += 10
                new_s -= 1
            elif new_u >= 10:
                new_u -= 10
                new_s += 1

            # Handle overflow/underflow for 2nd mesh
            # (Simplified - doesn't handle 1st mesh boundaries)
            if new_r < 0 or new_r >= 8 or new_s < 0 or new_s >= 8:
                continue  # Skip meshes outside 2nd mesh boundaries

            meshes.append(f"{mesh1}{new_r}{new_s}{new_t}{new_u}")

    return meshes


if __name__ == "__main__":
    # Test with Tokyo Station (35.681236, 139.767125)
    lat, lon = 35.681236, 139.767125

    print("Tokyo Station Coordinates:")
    print(f"  Latitude: {lat}")
    print(f"  Longitude: {lon}")
    print()

    print("Mesh Codes:")
    print(f"  1st mesh (80km): {latlon_to_mesh_1st(lat, lon)}")
    print(f"  2nd mesh (10km): {latlon_to_mesh_2nd(lat, lon)}")
    print(f"  3rd mesh (1km):  {latlon_to_mesh_3rd(lat, lon)}")
    print(f"  1/2 mesh (500m): {latlon_to_mesh_half(lat, lon)}")
    print(f"  1/4 mesh (250m): {latlon_to_mesh_quarter(lat, lon)}")
    print()

    # Test neighboring meshes
    mesh3 = latlon_to_mesh_3rd(lat, lon)
    neighbors = get_neighboring_meshes_3rd(mesh3)
    print(f"3rd mesh + neighbors ({len(neighbors)} total):")
    for i, m in enumerate(neighbors, 1):
        print(f"  {i:2d}. {m}")
