"""Geometry helpers with no compiled dependencies.

Plain-language header: this file converts map coordinates (longitude and latitude)
to the metre grid the NASA maps use (UTM), and decides which 30 m squares fall
inside a drawn wall outline. You do not need to open it.

UTM forward/inverse use the standard Krueger series (WGS84), accurate to well
under a millimetre within a zone, which is far below the 30 m pixel size.
pyproj is used instead when installed, so results match GIS software exactly.
"""

from __future__ import annotations

import json
import math

import numpy as np
from matplotlib.path import Path

_A = 6378137.0
_F = 1 / 298.257223563
_K0 = 0.9996
_N = _F / (2 - _F)
_AA = _A / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64)
_ALPHA = (_N / 2 - 2 * _N**2 / 3 + 5 * _N**3 / 16,
          13 * _N**2 / 48 - 3 * _N**3 / 5,
          61 * _N**3 / 240)
_BETA = (_N / 2 - 2 * _N**2 / 3 + 37 * _N**3 / 96,
         _N**2 / 48 + _N**3 / 15,
         17 * _N**3 / 480)
_DELTA = (2 * _N - 2 * _N**2 / 3 - 2 * _N**3,
          7 * _N**2 / 3 - 8 * _N**3 / 5,
          56 * _N**3 / 15)


def epsg_to_zone(epsg: int) -> tuple[int, bool]:
    """Return (zone, northern) for a WGS84 UTM EPSG code (326xx north, 327xx south)."""
    if 32601 <= epsg <= 32660:
        return epsg - 32600, True
    if 32701 <= epsg <= 32760:
        return epsg - 32700, False
    raise ValueError(f"EPSG {epsg} is not a WGS84 UTM zone")


def _try_pyproj(epsg, inverse):
    try:
        from pyproj import Transformer  # type: ignore
    except ImportError:
        return None
    if inverse:
        return Transformer.from_crs(epsg, 4326, always_xy=True)
    return Transformer.from_crs(4326, epsg, always_xy=True)


def lonlat_to_utm(lon, lat, epsg: int, use_pyproj: bool = True):
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    if use_pyproj:
        t = _try_pyproj(epsg, inverse=False)
        if t is not None:
            return t.transform(lon, lat)
    zone, north = epsg_to_zone(epsg)
    lon0 = math.radians(-183 + 6 * zone)
    phi = np.radians(lat)
    lam = np.radians(lon) - lon0
    e = math.sqrt(_F * (2 - _F))
    t = np.sinh(np.arctanh(np.sin(phi)) - e * np.arctanh(e * np.sin(phi)))
    xi_p = np.arctan2(t, np.cos(lam))
    eta_p = np.arctanh(np.sin(lam) / np.sqrt(1 + t**2))
    xi, eta = xi_p.copy(), eta_p.copy()
    for j, a in enumerate(_ALPHA, start=1):
        xi = xi + a * np.sin(2 * j * xi_p) * np.cosh(2 * j * eta_p)
        eta = eta + a * np.cos(2 * j * xi_p) * np.sinh(2 * j * eta_p)
    x = 500000.0 + _K0 * _AA * eta
    y = _K0 * _AA * xi + (0.0 if north else 10000000.0)
    return x, y


def utm_to_lonlat(x, y, epsg: int, use_pyproj: bool = True):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if use_pyproj:
        t = _try_pyproj(epsg, inverse=True)
        if t is not None:
            return t.transform(x, y)
    zone, north = epsg_to_zone(epsg)
    lon0 = math.radians(-183 + 6 * zone)
    xi = (y - (0.0 if north else 10000000.0)) / (_K0 * _AA)
    eta = (x - 500000.0) / (_K0 * _AA)
    xi_p, eta_p = xi.copy(), eta.copy()
    for j, b in enumerate(_BETA, start=1):
        xi_p = xi_p - b * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
        eta_p = eta_p - b * np.cos(2 * j * xi) * np.sinh(2 * j * eta)
    chi = np.arcsin(np.sin(xi_p) / np.cosh(eta_p))
    phi = chi.copy()
    for j, d in enumerate(_DELTA, start=1):
        phi = phi + d * np.sin(2 * j * chi)
    lam = np.arctan2(np.sinh(eta_p), np.cos(xi_p))
    return np.degrees(lam + lon0), np.degrees(phi)


def polygon_mask(rings_lonlat, x_coords, y_coords, epsg: int) -> np.ndarray:
    """Boolean [ny, nx] mask of pixel centres inside a polygon given as lon/lat rings.

    rings_lonlat: list of rings, first is the outer boundary, the rest are holes.
    x_coords, y_coords: 1-D pixel-centre coordinates of the raster grid (metres).
    """
    xx, yy = np.meshgrid(x_coords, y_coords)
    pts = np.column_stack([xx.ravel(), yy.ravel()])
    inside = np.zeros(pts.shape[0], dtype=bool)
    for i, ring in enumerate(rings_lonlat):
        ring = np.asarray(ring, dtype=float)
        rx, ry = lonlat_to_utm(ring[:, 0], ring[:, 1], epsg)
        hit = Path(np.column_stack([rx, ry])).contains_points(pts)
        inside = inside | hit if i == 0 else inside & ~hit
    return inside.reshape(xx.shape)


def load_geojson_polygons(path: str) -> list[dict]:
    """Read a GeoJSON FeatureCollection of Polygon/MultiPolygon features.

    Returns a list of {"properties": {...}, "polygons": [[ring, ...], ...]}.
    """
    with open(path) as f:
        gj = json.load(f)
    out = []
    for feat in gj["features"]:
        g = feat["geometry"]
        if g["type"] == "Polygon":
            polys = [g["coordinates"]]
        elif g["type"] == "MultiPolygon":
            polys = g["coordinates"]
        else:
            raise ValueError(f"{path}: unsupported geometry {g['type']}")
        out.append({"properties": feat.get("properties", {}), "polygons": polys})
    return out


def features_mask(features, x_coords, y_coords, epsg) -> np.ndarray:
    m = np.zeros((len(y_coords), len(x_coords)), dtype=bool)
    for feat in features:
        for rings in feat["polygons"]:
            m |= polygon_mask(rings, x_coords, y_coords, epsg)
    return m


def downslope_vector(aspect_deg: float, slope_deg: float) -> np.ndarray:
    """Unit vector (east, north, up) pointing down a face with this aspect and slope.

    Aspect is the compass direction the face looks toward (0 = north, 90 = east).
    Material sliding off the face moves outward along the aspect and downward.
    """
    a, s = math.radians(aspect_deg), math.radians(slope_deg)
    return np.array([math.sin(a) * math.cos(s), math.cos(a) * math.cos(s), -math.sin(s)])
