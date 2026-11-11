"""Tests for region assignment (data_engine/regions.py). Uses made-up shapes only."""
import csv
import json
from pathlib import Path

from data_engine.regions import (
    OUTSIDE_REGION,
    assign_regions,
    find_region,
    load_regions,
    region_for_point,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REGIONS = FIXTURES / "regions_sample.geojson"
SIGHTINGS = FIXTURES / "sightings_sample.csv"


def test_points_land_in_the_right_region():
    regions = load_regions(REGIONS)
    assert find_region(30.2672, -97.7431, regions) == "30"  # Austin
    assert find_region(29.4241, -98.4936, regions) == "30"  # San Antonio
    assert find_region(31.7619, -106.4850, regions) == "24"  # El Paso (MultiPolygon)


def test_point_outside_every_region_is_none():
    regions = load_regions(REGIONS)
    assert find_region(35.2, -101.8, regions) is None  # Amarillo: outside both fake boxes
    assert find_region(0.0, 0.0, regions) is None


def test_water_points_get_their_own_region_instead_of_being_dropped():
    regions = load_regions(REGIONS)
    # In the Gulf off Corpus Christi: inside the Texas box, in no land region.
    assert region_for_point(27.5, -96.5, regions) == OUTSIDE_REGION
    # Inside a land region: unchanged.
    assert region_for_point(30.2672, -97.7431, regions) == "30"
    # Nowhere near Texas (a classic bad coordinate): not ours, so None.
    assert region_for_point(0.0, 0.0, regions) is None
    assert region_for_point(45.0, -96.5, regions) is None


def test_hole_and_odd_shape(tmp_path):
    # An L-shaped region with a square hole cut out of it. Checks that the
    # inside/outside test is doing real geometry, not just a bounding box.
    l_shape = [[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4], [0, 0]]
    hole = [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]]
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"code": "L"},
                "geometry": {"type": "Polygon", "coordinates": [l_shape, hole]},
            }
        ],
    }
    path = tmp_path / "l.geojson"
    path.write_text(json.dumps(geojson))
    regions = load_regions(path, code_property="code")

    # find_region takes (latitude, longitude) = (y, x)
    assert find_region(1.0, 3.0, regions) == "L"  # bottom arm of the L
    assert find_region(3.0, 1.0, regions) == "L"  # top arm of the L
    assert find_region(3.0, 3.0, regions) is None  # in the bounding box, but in the L's notch
    assert find_region(1.0, 1.0, regions) is None  # inside the hole


def test_assign_regions_writes_region_column(tmp_path):
    out = tmp_path / "assigned.csv"
    summary = assign_regions(SIGHTINGS, REGIONS, out)

    # Every row lands in exactly one bucket, so the buckets add up to the row count.
    assert summary == {
        "rows": 25, "in_ecoregion": 19, "outside_land": 5, "outside_texas": 1, "bad_coordinates": 0,
    }
    with open(out, newline="") as f:
        rows = {r["sighting_id"]: r for r in csv.DictReader(f)}
    assert rows["s01"]["region"] == "30"
    assert rows["s15"]["region"] == "24"
    assert rows["s20"]["region"] == OUTSIDE_REGION  # in Texas, outside both fake boxes
    assert rows["s21"]["region"] == OUTSIDE_REGION  # a fish in the Gulf is kept
    assert rows["s25"]["region"] == ""  # latitude 0, longitude 0: not Texas
    assert len(rows) == 25  # no row is removed from the file
    # Original columns are kept untouched.
    assert rows["s01"]["species_id"] == "sp_0001"


def test_bad_coordinates_are_counted_not_crashed(tmp_path):
    src = tmp_path / "s.csv"
    src.write_text(
        "sighting_id,species_id,latitude,longitude,obs_date\n"
        "x1,sp_0001,,,2025-11-01\n"
        "x2,sp_0001,30.27,-97.74,2025-11-01\n"
    )
    summary = assign_regions(src, REGIONS, tmp_path / "out.csv")
    assert summary["bad_coordinates"] == 1
    assert summary["in_ecoregion"] == 1
