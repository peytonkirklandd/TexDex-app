"""Tests for the month-by-region table (data_engine/month_region.py)."""
from pathlib import Path

from data_engine.month_region import build_month_region_table, load_month_region_table
from data_engine.regions import assign_regions

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_counts_per_region_month_species(tmp_path):
    assigned = tmp_path / "assigned.csv"
    assign_regions(FIXTURES / "sightings_sample.csv", FIXTURES / "regions_sample.geojson", assigned)
    out = tmp_path / "month_region.csv"

    summary = build_month_region_table(assigned, out)
    table = load_month_region_table(out)

    # Hand-counted from tests/fixtures/sightings_sample.csv
    assert table[("30", 11)] == {"sp_0001": 6, "sp_0003": 1, "sp_0007": 3}
    assert table[("30", 4)] == {"sp_0001": 2, "sp_0003": 2}
    assert table[("24", 7)] == {"sp_0002": 4, "sp_0004": 1}
    # The 20th sighting is outside every region, so 19 are counted.
    assert summary == {"rows": 7, "region_months": 3, "sightings_counted": 19}


def test_years_are_pooled(tmp_path):
    src = tmp_path / "assigned.csv"
    src.write_text(
        "species_id,latitude,longitude,obs_date,region\n"
        "sp_0001,30.27,-97.74,2024-11-01,30\n"
        "sp_0001,30.27,-97.74,2025-11-20,30\n"
    )
    out = tmp_path / "month_region.csv"
    build_month_region_table(src, out)
    assert load_month_region_table(out) == {("30", 11): {"sp_0001": 2}}
