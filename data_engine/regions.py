"""Step 1: assign each sighting to a region (EPA ecoregion, or county).

Input files
- sightings CSV with at least: species_id, latitude, longitude, obs_date
- regions GeoJSON: one Feature per region, Polygon or MultiPolygon, in plain
  latitude/longitude (WGS84). The EPA shapefile ships in a different map
  projection, so it must be converted to lat/lon GeoJSON once before use.

Output: the same sightings CSV with one extra column, `region`.

Sightings that are in Texas but not inside any land ecoregion (the Gulf, bays,
barrier-island edges) are NOT dropped. They get the region code
OUTSIDE_REGION, so marine fish, sharks, rays and seabirds still get rarity
tiers and a location boost of their own.

Why plain Python instead of geopandas: the "is this point inside this shape"
test is about 10 lines, has no install headaches on the Hugging Face Space, and
we can explain it line by line. If the full GBIF download turns out too slow,
we can swap the inside of assign_regions() for geopandas without changing how
it is called.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

# The column in the EPA Level III ecoregion file that holds the region code.
EPA_CODE_PROPERTY = "US_L3CODE"

# Region code for a point that is inside the Texas box below but outside
# every land ecoregion. In practice that is Gulf and bay water.
OUTSIDE_REGION = "outside_land"

# A loose rectangle around Texas plus its Gulf waters:
# (min_lon, min_lat, max_lon, max_lat). PLACEHOLDER edges, to be checked
# against the real download.
# Why we need it: without a limit, "outside every ecoregion" would also
# swallow plain mistakes, like a sighting at latitude 0 / longitude 0 or one
# in Oklahoma, and count them as Gulf sightings.
TEXAS_BOUNDS = (-106.7, 25.5, -93.0, 36.6)


def _point_in_ring(lon: float, lat: float, ring: list) -> bool:
    """Ray casting: draw a line from the point straight east and count how many
    edges of the shape it crosses. Odd = inside, even = outside.

    Why it works: every time the line crosses an edge it switches between
    inside and outside, and far to the east it is definitely outside.
    """
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # Does this edge span the point's latitude? (one end above, one below)
        if (yi > lat) != (yj > lat):
            # Longitude where the edge crosses the point's latitude.
            x_cross = xi + (lat - yi) * (xj - xi) / (yj - yi)
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _point_in_polygon(lon: float, lat: float, rings: list) -> bool:
    """A GeoJSON polygon is an outer ring followed by optional holes.
    Inside the polygon = inside the outer ring and not inside any hole."""
    if not _point_in_ring(lon, lat, rings[0]):
        return False
    return not any(_point_in_ring(lon, lat, hole) for hole in rings[1:])


def load_regions(geojson_path, code_property: str = EPA_CODE_PROPERTY) -> list[dict]:
    """Read a regions GeoJSON into a simple list:
    [{"code": "30", "bbox": (min_lon, min_lat, max_lon, max_lat), "polygons": [...]}, ...]
    """
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)

    regions = []
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] == "Polygon":
            polygons = [geom["coordinates"]]
        elif geom["type"] == "MultiPolygon":
            polygons = geom["coordinates"]
        else:
            raise ValueError(f"unsupported geometry type: {geom['type']}")

        # Bounding box = the smallest rectangle around the shape. Checking the
        # rectangle first is a cheap way to skip regions that are nowhere near
        # the point, so we only run the slow test on likely matches.
        lons = [pt[0] for poly in polygons for pt in poly[0]]
        lats = [pt[1] for poly in polygons for pt in poly[0]]
        regions.append(
            {
                "code": str(feature["properties"][code_property]),
                "bbox": (min(lons), min(lats), max(lons), max(lats)),
                "polygons": polygons,
            }
        )
    return regions


def find_region(latitude: float, longitude: float, regions: list[dict]) -> str | None:
    """Return the code of the region containing the point, or None if the
    point is outside every region (e.g. offshore, or outside Texas)."""
    for region in regions:
        min_lon, min_lat, max_lon, max_lat = region["bbox"]
        if not (min_lon <= longitude <= max_lon and min_lat <= latitude <= max_lat):
            continue
        for rings in region["polygons"]:
            if _point_in_polygon(longitude, latitude, rings):
                return region["code"]
    return None


def region_for_point(
    latitude: float, longitude: float, regions: list[dict], bounds=TEXAS_BOUNDS
) -> str | None:
    """The region code to use for a point. Three possible answers:
    - an ecoregion code, if the point is inside one
    - OUTSIDE_REGION, if it is inside the Texas box but in no ecoregion (water)
    - None, if it is outside the Texas box altogether (not our data)
    """
    code = find_region(latitude, longitude, regions)
    if code is not None:
        return code
    min_lon, min_lat, max_lon, max_lat = bounds
    if min_lon <= longitude <= max_lon and min_lat <= latitude <= max_lat:
        return OUTSIDE_REGION
    return None


def assign_regions(
    sightings_path,
    regions_path,
    out_path,
    code_property: str = EPA_CODE_PROPERTY,
    bounds=TEXAS_BOUNDS,
) -> dict:
    """Add a `region` column to a sightings CSV. Returns a small summary dict.

    Reads and writes one row at a time, so a huge file never has to fit in memory.
    Every row is kept and every row is counted in exactly one summary bucket:
    - in_ecoregion:   region = the ecoregion code
    - outside_land:   region = OUTSIDE_REGION (in the Texas box, in no ecoregion)
    - outside_texas:  region left empty (outside the Texas box; later steps skip it)
    - bad_coordinates: region left empty (latitude/longitude missing or not a number)
    """
    regions = load_regions(regions_path, code_property)
    # Many sightings share the exact same coordinates (popular birding spots),
    # so remember answers we already worked out.
    cache: dict[tuple[float, float], str | None] = {}
    summary = {
        "rows": 0, "in_ecoregion": 0, "outside_land": 0, "outside_texas": 0, "bad_coordinates": 0,
    }

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(sightings_path, newline="", encoding="utf-8") as fin, open(
        out_path, "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=list(reader.fieldnames) + ["region"])
        writer.writeheader()
        for row in reader:
            summary["rows"] += 1
            try:
                point = (float(row["latitude"]), float(row["longitude"]))
            except (TypeError, ValueError):
                summary["bad_coordinates"] += 1
                row["region"] = ""
                writer.writerow(row)
                continue
            if point not in cache:
                cache[point] = region_for_point(point[0], point[1], regions, bounds)
            code = cache[point]
            row["region"] = code or ""
            if code is None:
                summary["outside_texas"] += 1
            elif code == OUTSIDE_REGION:
                summary["outside_land"] += 1
            else:
                summary["in_ecoregion"] += 1
            writer.writerow(row)
    return summary
