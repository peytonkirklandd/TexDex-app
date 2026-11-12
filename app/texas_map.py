"""Turn the ecoregion shapes into a drawing of Texas the Dex can show.

Input: the two GeoJSON files written by data_engine/fetch_ecoregions.py.
Output: SVG path strings (the browser's drawing instructions) for each
region and for the Texas outline, plus a label position for each region.

The EPA shapes run past the state line. We do not cut them ourselves: the
browser clips every region to the Texas outline when it draws (an SVG
clipPath), which is one line of markup instead of a polygon-clipping algorithm.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from data_engine.regions import _point_in_polygon, find_region, load_regions

WIDTH = 1000  # the drawing is 1000 units wide; height follows from Texas's shape


def _all_polygons(geometry: dict) -> list:
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]


class Projector:
    """Longitude/latitude -> x/y on the drawing.

    Longitude lines get closer together away from the equator, so a degree of
    longitude in Texas is only about 86% as wide as a degree of latitude.
    Multiplying x by cos(latitude) fixes that; without it Texas looks stretched.
    """

    def __init__(self, min_lon, min_lat, max_lon, max_lat):
        self.min_lon, self.max_lat = min_lon, max_lat
        self.squeeze = math.cos(math.radians((min_lat + max_lat) / 2))
        self.scale = WIDTH / ((max_lon - min_lon) * self.squeeze)
        self.height = round((max_lat - min_lat) * self.scale)

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        return (round((lon - self.min_lon) * self.squeeze * self.scale, 1),
                round((self.max_lat - lat) * self.scale, 1))


def _path(polygons: list, proj: Projector, keep_box=None) -> str:
    parts = []
    for rings in polygons:
        for ring in rings:
            if keep_box is not None:
                # Skip pieces that are entirely outside the Texas rectangle
                # (the Colorado end of the High Plains, for example).
                lons, lats = [p[0] for p in ring], [p[1] for p in ring]
                if (max(lons) < keep_box[0] or min(lons) > keep_box[2]
                        or max(lats) < keep_box[1] or min(lats) > keep_box[3]):
                    continue
            points, last = [], None
            for lon, lat in (p[:2] for p in ring):
                xy = proj.xy(lon, lat)
                if xy != last:  # drop repeats made by rounding
                    points.append(f"{xy[0]},{xy[1]}")
                    last = xy
            if len(points) >= 3:
                parts.append("M" + "L".join(points) + "Z")
    return "".join(parts)


def build_map(regions_geojson, outline_geojson) -> dict:
    """Returns {"available": False} if either file is missing, otherwise the
    drawing data. Slow-ish (about a second), so the server calls it once."""
    if not (Path(regions_geojson).is_file() and Path(outline_geojson).is_file()):
        return {"available": False}

    outline = json.loads(Path(outline_geojson).read_text(encoding="utf-8"))
    texas = [poly for feature in outline["features"] for poly in _all_polygons(feature["geometry"])]
    lons = [p[0] for poly in texas for p in poly[0]]
    lats = [p[1] for poly in texas for p in poly[0]]
    box = (min(lons), min(lats), max(lons), max(lats))
    proj = Projector(*box)

    data = json.loads(Path(regions_geojson).read_text(encoding="utf-8"))
    shapes = {}
    for feature in data["features"]:
        code = str(feature["properties"]["US_L3CODE"])
        shapes[code] = shapes.get(code, "") + _path(_all_polygons(feature["geometry"]), proj, box)

    # Label position = the middle of the part of each region that is inside
    # Texas. We lay a grid of points over the state, ask "which region is
    # this point in?" for each, and average the points per region.
    regions = load_regions(regions_geojson)
    sums: dict[str, list[float]] = {}
    boxes: dict[str, list[float]] = {}  # region -> [min_x, min_y, max_x, max_y] on the drawing
    step = 0.2
    lat = box[1]
    while lat <= box[3]:
        lon = box[0]
        while lon <= box[2]:
            if any(_point_in_polygon(lon, lat, rings) for rings in texas):
                code = find_region(lat, lon, regions)
                if code:
                    total = sums.setdefault(code, [0.0, 0.0, 0])
                    total[0] += lon
                    total[1] += lat
                    total[2] += 1
                    # Grow this region's rectangle to include the point. The
                    # Map tab zooms to this rectangle when a region is tapped.
                    x, y = proj.xy(lon, lat)
                    b = boxes.setdefault(code, [x, y, x, y])
                    b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)
            lon += step
        lat += step

    labels = {}
    for code, (lon_sum, lat_sum, n) in sums.items():
        labels[code] = proj.xy(lon_sum / n, lat_sum / n)

    return {
        "available": True,
        "width": WIDTH,
        "height": proj.height,
        "outline": _path(texas, proj),
        "regions": [{"code": code, "path": path, "label": labels.get(code),
                     "bbox": boxes.get(code)}
                    for code, path in shapes.items()],
        "box": box,
    }


def project_point(map_data: dict, latitude: float, longitude: float) -> tuple[float, float]:
    """Where a latitude/longitude lands on the drawing made by build_map()."""
    return Projector(*map_data["box"]).xy(longitude, latitude)
