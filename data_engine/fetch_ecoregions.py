"""Download the EPA Level III ecoregion shapes for Texas as lat/lon GeoJSON.

    python -m data_engine.fetch_ecoregions

Sources (both U.S. Government works, public domain):
  - U.S. EPA "Ecoregions Level III and IV" public map service: the 12 Level
    III ecoregions that touch Texas.
  - U.S. Census Bureau TIGERweb: the Texas state outline.

Why we also need the state outline: EPA draws each ecoregion as one shape
that runs across state lines (the High Plains reach Colorado), and its
STATE_NAME column only names one state per region, so it cannot be used to
cut the shapes at the Texas border. The app uses the outline to draw the
map in the shape of Texas.

We ask the services for:
  - coordinates in plain latitude/longitude (outSR=4326), so no map
    projection maths is needed on our side,
  - simplified outlines (maxAllowableOffset, in degrees). 0.01 degrees is
    about 1 km, which keeps the files small and is far finer than the
    difference between two ecoregions' wildlife.

The files go in data/ (git-ignored). Log each download in docs/data-sources-log.md.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

SERVICE = ("https://geodata.epa.gov/arcgis/rest/services/ORD/"
           "USEPA_Ecoregions_Level_III_and_IV/MapServer/11/query")
STATE_SERVICE = ("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
                 "State_County/MapServer/0/query")
_PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"
DEFAULT_OUT = _PROCESSED / "ecoregions.geojson"
DEFAULT_OUTLINE_OUT = _PROCESSED / "texas_outline.geojson"

# The EPA Level III ecoregions that include part of Texas.
TEXAS_L3_CODES = ["23", "24", "25", "26", "27", "29", "30", "31", "32", "33", "34", "35"]


def _download_geojson(service: str, where: str, out_fields: str, simplify_degrees: float) -> dict:
    params = {
        "where": where,
        "outFields": out_fields,
        "outSR": "4326",
        "maxAllowableOffset": str(simplify_degrees),
        "geometryPrecision": "4",  # 4 decimal places is about 10 m
        "f": "geojson",
    }
    url = service + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=180) as response:
        data = json.load(response)
    if not data.get("features"):
        raise RuntimeError(f"map service did not return shapes: {str(data)[:200]}")
    return data


def _save(data: dict, out_path) -> int:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data), encoding="utf-8")
    return round(out_path.stat().st_size / 1024)


def fetch_ecoregions(out_path=DEFAULT_OUT, simplify_degrees: float = 0.01) -> dict:
    """Download the 12 ecoregion shapes and write them to out_path. Returns a summary."""
    code_list = ",".join(f"'{code}'" for code in TEXAS_L3_CODES)
    data = _download_geojson(
        SERVICE, f"US_L3CODE IN ({code_list})", "US_L3CODE,US_L3NAME", simplify_degrees)
    return {
        "features": len(data["features"]),
        "region_codes": sorted({f["properties"]["US_L3CODE"] for f in data["features"]}),
        "file_kb": _save(data, out_path),
        "out_path": str(out_path),
    }


def fetch_texas_outline(out_path=DEFAULT_OUTLINE_OUT, simplify_degrees: float = 0.01) -> dict:
    """Download the Texas state outline and write it to out_path. Returns a summary."""
    data = _download_geojson(STATE_SERVICE, "NAME='Texas'", "NAME", simplify_degrees)
    return {"features": len(data["features"]), "file_kb": _save(data, out_path),
            "out_path": str(out_path)}


if __name__ == "__main__":
    print(fetch_ecoregions())
    print(fetch_texas_outline())
