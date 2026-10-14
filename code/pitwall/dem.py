"""Automatic wall outlines and stable ground from a free elevation model.

Plain-language header: instead of drawing walls by hand, this file finds them from
the shape of the ground. Inside a circle around the pit centre, any 30 m square
steeper than 25 degrees is wall. Walls are grouped by the direction they face
(8 compass directions) and by which side of the pit they sit on, so the east wall
of a pit, which faces west, is named "faces_W_E". Gently sloping ground in a ring
outside the pit becomes the candidate stable ground. You check the result on a
preview map; you do not need to open this file.

Elevation source: Copernicus GLO-30 DEM (30 m), public on AWS Open Data. Its radar
acquisitions date from about 2011 to 2015, so walls cut after that are missing or
in the wrong place. That is a stated limitation, and the preview map is how it is
caught. Fetching needs rasterio and network access to the AWS bucket (works on the
GitHub runner; the build workspace is blocked).
"""

from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

COPDEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_"
              "{ew}{lon:03d}_00_DEM/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif")
COPDEM_LANDING = "https://registry.opendata.aws/copernicus-dem/"
COPDEM_CREDIT = ("Copernicus DEM GLO-30, produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and "
                 "(c) Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European "
                 "Union and ESA; all rights reserved")
DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def tile_urls(bbox):
    lon0, lat0, lon1, lat1 = bbox
    urls = []
    for la in range(math.floor(lat0), math.floor(lat1) + 1):
        for lo in range(math.floor(lon0), math.floor(lon1) + 1):
            ns, ew = ("N", la) if la >= 0 else ("S", -la), ("E", lo) if lo >= 0 else ("W", -lo)
            urls.append(COPDEM_URL.format(ns=ns[0], lat=ns[1], ew=ew[0], lon=ew[1]))
    return urls


def fetch_dem_utm(bbox, epsg, pixel=30.0):
    """Read the GLO-30 tiles covering bbox and resample them onto a 30 m UTM grid (needs rasterio)."""
    import rasterio  # type: ignore
    from rasterio.merge import merge  # type: ignore
    from rasterio.warp import Resampling, reproject  # type: ignore

    from .geo import lonlat_to_utm
    srcs = [rasterio.open(u) for u in tile_urls(bbox)]
    mosaic, transform = merge(srcs, bounds=tuple(bbox))
    xs, ys = lonlat_to_utm([bbox[0], bbox[2], bbox[0], bbox[2]], [bbox[1], bbox[1], bbox[3], bbox[3]], epsg)
    x = np.arange(math.floor(min(xs) / pixel) * pixel + pixel / 2, max(xs), pixel)
    y = np.arange(math.ceil(max(ys) / pixel) * pixel - pixel / 2, min(ys), -pixel)
    dst = np.full((y.size, x.size), np.nan, np.float32)
    dst_transform = rasterio.transform.from_origin(x[0] - pixel / 2, y[0] + pixel / 2, pixel, pixel)
    reproject(mosaic[0].astype(np.float32), dst, src_transform=transform, src_crs=srcs[0].crs,
              dst_transform=dst_transform, dst_crs=f"EPSG:{epsg}", resampling=Resampling.bilinear,
              src_nodata=srcs[0].nodata, dst_nodata=np.nan)
    return dst, x, y


def slope_aspect(z, pixel=30.0):
    """Slope (degrees) and aspect (compass direction the face looks toward, degrees) for a north-up grid."""
    gy, gx = np.gradient(z.astype(float), pixel)
    dzdx, dzdy = gx, -gy                      # rows run south, so flip the y derivative
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360) % 360
    return slope, aspect


def _sector(deg):
    return ((np.asarray(deg) + 22.5) // 45).astype(int) % 8


def auto_walls(z, x, y, centre_xy, radius_m, slope_min=25.0, min_pixels=20, pixel=30.0):
    """Return {wall_id: mask} and {wall_id: properties} for steep ground near the pit centre."""
    slope, aspect = slope_aspect(z, pixel)
    xx, yy = np.meshgrid(x, y)
    dx, dy = xx - centre_xy[0], yy - centre_xy[1]
    inside = np.hypot(dx, dy) <= radius_m
    steep = inside & (slope >= slope_min) & np.isfinite(z)
    steep = ndimage.binary_opening(steep, structure=np.ones((2, 2), bool))   # drop single-pixel speckle
    face = _sector(aspect)
    side = _sector(np.degrees(np.arctan2(dx, dy)) % 360)                     # bearing from centre
    masks, props = {}, {}
    for f in range(8):
        for s in range(8):
            m = steep & (face == f) & (side == s)
            if m.sum() < min_pixels:
                continue
            wid = f"faces_{DIRS[f]}_{DIRS[s]}"
            a = np.radians(aspect[m])
            masks[wid] = m
            props[wid] = {"wall_id": wid,
                          "aspect_deg": round(float(np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) % 360), 1),
                          "slope_deg": round(float(np.median(slope[m])), 1),
                          "n_pixels": int(m.sum()), "source": "auto from Copernicus GLO-30"}
    return masks, props


def auto_stable(z, x, y, centre_xy, r_in, r_out, slope_max=10.0, pixel=30.0):
    """Gently sloping ground in a ring outside the pit: the candidate stable reference."""
    slope, _ = slope_aspect(z, pixel)
    xx, yy = np.meshgrid(x, y)
    r = np.hypot(xx - centre_xy[0], yy - centre_xy[1])
    return (r >= r_in) & (r <= r_out) & (slope <= slope_max) & np.isfinite(z)


def regrid_nearest(mask, src_x, src_y, dst_x, dst_y):
    """Nearest-neighbour transfer of a boolean raster between two north-up grids (same CRS)."""
    ix = np.clip(np.searchsorted(src_x, dst_x), 1, len(src_x) - 1)
    ix -= (np.abs(dst_x - src_x[ix - 1]) < np.abs(dst_x - src_x[ix]))
    ys = src_y[::-1]
    iy = np.clip(np.searchsorted(ys, dst_y), 1, len(ys) - 1)
    iy -= (np.abs(dst_y - ys[iy - 1]) < np.abs(dst_y - ys[iy]))
    iy = len(src_y) - 1 - iy
    out = mask[np.ix_(iy, ix)]
    outside = ((dst_y < src_y.min() - 15) | (dst_y > src_y.max() + 15))[:, None] | \
              ((dst_x < src_x.min() - 15) | (dst_x > src_x.max() + 15))[None, :]
    return out & ~outside


def find_pits(z, pixel=30.0, window_m=2500.0, depth_min_m=40.0, area_min_m2=1.0e5):
    """District mode: label open pits as closed depressions well below the surrounding ground.

    The surrounding ground is a smoothed surface (median over window_m). Pixels more than
    depth_min_m below it, in connected patches larger than area_min_m2, are pits. Returns
    (labels, list of pit dicts with centre index, area and depth), largest pit first.
    """
    zf = np.where(np.isfinite(z), z, np.nanmedian(z))
    w = max(3, int(window_m / pixel) | 1)
    coarse = ndimage.median_filter(zf[::4, ::4], size=max(3, w // 4))
    surround = ndimage.zoom(coarse, (zf.shape[0] / coarse.shape[0], zf.shape[1] / coarse.shape[1]), order=1)
    surround = surround[: zf.shape[0], : zf.shape[1]]
    deep = (surround - zf) > depth_min_m
    lab, n = ndimage.label(deep)
    pits = []
    for k in range(1, n + 1):
        m = lab == k
        area = m.sum() * pixel * pixel
        if area < area_min_m2:
            continue
        iy, ix = np.nonzero(m)
        pits.append({"label": k, "iy": float(iy.mean()), "ix": float(ix.mean()), "area_m2": float(area),
                     "depth_m": float(np.max(surround[m] - zf[m])),
                     "radius_m": float(np.sqrt(area / np.pi))})
    pits.sort(key=lambda p: -p["area_m2"])
    out = np.zeros(z.shape, np.int16)
    for i, p in enumerate(pits, start=1):
        out[lab == p["label"]] = i
        p["pit"] = i
    return out, pits


def regrid_values(values, src_x, src_y, dst_x, dst_y):
    """Nearest-neighbour transfer of a float raster between two north-up grids (same CRS); NaN outside."""
    ix = np.clip(np.searchsorted(src_x, dst_x), 1, len(src_x) - 1)
    ix -= (np.abs(dst_x - src_x[ix - 1]) < np.abs(dst_x - src_x[ix]))
    ys = src_y[::-1]
    iy = np.clip(np.searchsorted(ys, dst_y), 1, len(ys) - 1)
    iy -= (np.abs(dst_y - ys[iy - 1]) < np.abs(dst_y - ys[iy]))
    iy = len(src_y) - 1 - iy
    out = values[np.ix_(iy, ix)].astype(float)
    outside = ((dst_y < src_y.min() - 15) | (dst_y > src_y.max() + 15))[:, None] | \
              ((dst_x < src_x.min() - 15) | (dst_x > src_x.max() + 15))[None, :]
    out[outside] = np.nan
    return out
