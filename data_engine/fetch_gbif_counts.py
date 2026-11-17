"""Ask GBIF how many times each species was reported in each Texas region in
each calendar month, and look up each species' names and family.

    python -m data_engine.fetch_gbif_counts

Why counts and not the raw sightings: Texas has over 60 million bird records
alone. GBIF's public search can do the counting for us ("facets"): one
request returns "species X: 1,204 records" for every species matching a
filter. We send one request per region per month (13 x 12 = 156 requests)
instead of downloading tens of millions of rows. No GBIF account is needed.

The filter on every request (log changes in docs/data-sources-log.md):
  - animals with a backbone (phylum Chordata)
  - human observations only (no museum specimens, no fossils)
  - year 2000 or later, has coordinates, no flagged coordinate problems
  - inside the region's outline AND inside Texas (GBIF's own Texas boundary)

Trade-off: with counts we cannot tell which sightings were made on the same
visit, so only the "simple" rarity method can be built from this file. The
effort-adjusted method still needs the full GBIF download.

Outputs (in data/raw/, never in git):
  gbif_counts.csv    region, month, species_key, sightings
  gbif_species.json  species_key -> names, family, order, class, IUCN code
"""
from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .fetch_ecoregions import SERVICE as EPA_SERVICE
from .fetch_ecoregions import TEXAS_L3_CODES
from .regions import OUTSIDE_REGION, TEXAS_BOUNDS

GBIF = "https://api.gbif.org/v1"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

CHORDATA = 44                # GBIF's id for "animals with a backbone"
TEXAS_GADM = "USA.44_1"      # GBIF's id for the state of Texas (GADM boundaries)
FIRST_YEAR = 2000
# A species needs at least this many Texas records to be listed. Keeps out
# one-off strays and misidentifications. PLACEHOLDER value.
MIN_SIGHTINGS = 5

# Rough outline of Texas Gulf waters, just seaward of the barrier islands,
# out to roughly 100 km: (longitude, latitude) corners. Hand-drawn PLACEHOLDER.
GULF_OUTLINE = [(-93.84, 29.62), (-94.75, 29.22), (-95.30, 28.87), (-96.00, 28.52), (-96.40, 28.30),
                (-97.00, 27.80), (-97.30, 27.00), (-97.12, 26.05), (-96.00, 26.00), (-94.50, 27.50),
                (-93.80, 28.80)]


def _get_json(url: str, tries: int = 4):
    """GET a URL and parse the JSON, waiting and retrying if the server is busy."""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "texdex-class-project"})
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            # GBIF answers with an empty body when it has nothing on file
            # (a species with no IUCN assessment, for example).
            return json.loads(body) if body.strip() else None
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
        time.sleep(3 * (attempt + 1))


# ---------- region outlines as text GBIF understands (WKT) ----------

def _signed_area(ring) -> float:
    """Shoelace formula. Positive = points run anticlockwise."""
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2


def _ring_text(ring) -> str:
    ring = [(round(p[0], 3), round(p[1], 3)) for p in ring]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    # GBIF wants the outline anticlockwise. Clockwise would mean "everything
    # on Earth EXCEPT this shape", so we flip it if needed.
    if _signed_area(ring) < 0:
        ring.reverse()
    return "(" + ",".join(f"{x} {y}" for x, y in ring) + ")"


def _gbif_accepts(wkt: str) -> bool:
    """Ask GBIF for nothing (limit 0) with this outline, to see if it takes it.
    It refuses outlines that are too long for a web address or that cross
    over themselves, which simplifying a wiggly coastline can cause."""
    params = urllib.parse.urlencode({"taxonKey": CHORDATA, "limit": 0, "geometry": wkt, "gadmGid": TEXAS_GADM})
    try:
        request = urllib.request.Request(f"{GBIF}/occurrence/search?{params}",
                                         headers={"User-Agent": "texdex-class-project"})
        urllib.request.urlopen(request, timeout=120).read()
        return True
    except urllib.error.HTTPError as error:
        if error.code == 400:
            return False
        raise


def region_wkt(code: str, max_chars: int = 2400) -> str:
    """One ecoregion's outline as WKT (the text format GBIF reads).

    We ask EPA for the outline at coarser and coarser detail until GBIF
    accepts it. Coarse is fine here: the edges only decide which region a
    sighting near a boundary is counted in.
    """
    min_lon, min_lat, max_lon, max_lat = TEXAS_BOUNDS
    for simplify_degrees in (0.03, 0.05, 0.08, 0.12, 0.16, 0.2, 0.3, 0.4, 0.6):
        params = urllib.parse.urlencode({
            "where": f"US_L3CODE='{code}'", "outFields": "US_L3CODE", "outSR": "4326",
            "maxAllowableOffset": str(simplify_degrees), "geometryPrecision": "3", "f": "geojson"})
        data = _get_json(EPA_SERVICE + "?" + params)
        rings = []
        for feature in data["features"]:
            geometry = feature["geometry"]
            polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
            for polygon in polygons:
                outer = [(p[0], p[1]) for p in polygon[0]]  # outer edge only; holes are ignored
                lons, lats = [p[0] for p in outer], [p[1] for p in outer]
                # Skip pieces nowhere near Texas, and specks (small islands).
                if max(lons) < min_lon or min(lons) > max_lon or max(lats) < min_lat or min(lats) > max_lat:
                    continue
                if len(outer) < 4 or abs(_signed_area(outer)) < 0.02:
                    continue
                rings.append(outer)
        wkt = "MULTIPOLYGON(" + ",".join("(" + _ring_text(r) + ")" for r in rings) + ")"
        if len(wkt) <= max_chars and _gbif_accepts(wkt):
            return wkt
    raise RuntimeError(f"region {code}: GBIF would not accept the outline at any level of detail")


def all_region_filters() -> dict:
    """{region code: extra search filters for that region}"""
    filters = {code: {"geometry": region_wkt(code), "gadmGid": TEXAS_GADM} for code in TEXAS_L3_CODES}
    # The Gulf is outside GBIF's Texas land boundary, so no gadmGid there.
    filters[OUTSIDE_REGION] = {"geometry": "POLYGON(" + _ring_text(list(GULF_OUTLINE)) + ")"}
    return filters


# ---------- counting ----------

def count_species(extra_filters: dict, month: int) -> dict:
    """{species_key: number of records} for one region and one month."""
    counts, offset, page = {}, 0, 1000
    while True:
        params = {
            "taxonKey": CHORDATA, "basisOfRecord": "HUMAN_OBSERVATION", "occurrenceStatus": "PRESENT",
            "hasCoordinate": "true", "hasGeospatialIssue": "false", "year": f"{FIRST_YEAR},2100",
            "month": month, "limit": 0, "facet": "speciesKey", "facetLimit": page, "facetOffset": offset,
            **extra_filters,
        }
        data = _get_json(f"{GBIF}/occurrence/search?" + urllib.parse.urlencode(params))
        rows = data["facets"][0]["counts"] if data["facets"] else []
        for row in rows:
            counts[row["name"]] = row["count"]
        if len(rows) < page:
            return counts
        offset += page


def fetch_counts(out_path=RAW / "gbif_counts.csv") -> dict:
    filters = all_region_filters()
    jobs = [(region, month) for region in filters for month in range(1, 13)]

    def run(job):
        region, month = job
        return region, month, count_species(filters[region], month)

    # 4 requests at a time: quick, without leaning on GBIF's servers.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, jobs))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["region", "month", "species_key", "sightings"])
        for region, month, counts in results:
            for species_key, n in sorted(counts.items()):
                writer.writerow([region, month, species_key, n])
                rows += 1
    return {"requests": len(jobs), "rows": rows,
            "records_counted": sum(sum(c.values()) for _r, _m, c in results)}


# ---------- species details ----------

def species_details(species_key: str) -> dict | None:
    info = _get_json(f"{GBIF}/species/{species_key}")
    if not info:
        return None
    common = info.get("vernacularName") or ""
    if not common:
        names = _get_json(f"{GBIF}/species/{species_key}/vernacularNames?limit=100") or {}
        english = [n["vernacularName"] for n in names.get("results", []) if n.get("language") == "eng"]
        common = english[0] if english else ""
    iucn = _get_json(f"{GBIF}/species/{species_key}/iucnRedListCategory") or {}
    return {
        "scientific_name": info.get("canonicalName") or info.get("scientificName", ""),
        "common_name": common,
        "family": info.get("family", ""),
        "order": info.get("order", ""),
        "class": info.get("class", ""),
        "iucn": iucn.get("code", ""),
    }


def fetch_species(counts_path=RAW / "gbif_counts.csv", out_path=RAW / "gbif_species.json") -> dict:
    totals: dict[str, int] = {}
    with open(counts_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            totals[row["species_key"]] = totals.get(row["species_key"], 0) + int(row["sightings"])
    wanted = sorted(key for key, n in totals.items() if n >= MIN_SIGHTINGS)

    # Keep what an earlier run already looked up, so a rerun is quick.
    known = json.loads(Path(out_path).read_text(encoding="utf-8")) if Path(out_path).is_file() else {}
    missing = [key for key in wanted if key not in known]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, details in zip(missing, pool.map(species_details, missing)):
            if details:
                known[key] = details
    Path(out_path).write_text(json.dumps(known, indent=0), encoding="utf-8")
    return {"species_seen": len(totals), f"with_{MIN_SIGHTINGS}_or_more": len(wanted),
            "looked_up_now": len(missing), "details_saved": len(known)}


if __name__ == "__main__":
    print("counts:", fetch_counts())
    print("species:", fetch_species())
