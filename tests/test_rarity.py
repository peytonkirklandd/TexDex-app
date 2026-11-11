"""Tests for the rarity math (data_engine/rarity.py). Tiny made-up inputs with
answers worked out by hand."""
import csv
from datetime import date

import pytest

from data_engine.rarity import (
    EFFORT_CUTOFFS,
    SIMPLE_CUTOFFS,
    build_rarity_table,
    effort_adjusted_frequencies,
    season_of,
    simple_shares,
    tier_for,
)

HEADER = "species_id,latitude,longitude,obs_date,region\n"


def _write(tmp_path, lines):
    path = tmp_path / "assigned.csv"
    path.write_text(HEADER + "\n".join(lines) + "\n")
    return path


def test_season_of():
    assert season_of(date(2026, 1, 15)) == "winter"
    assert season_of(date(2026, 12, 1)) == "winter"
    assert season_of(date(2026, 4, 2)) == "spring"
    assert season_of(date(2026, 7, 20)) == "summer"
    assert season_of(date(2026, 11, 15)) == "fall"


def test_tier_cutoffs_include_the_boundary():
    assert tier_for(0.5, SIMPLE_CUTOFFS) == "common"
    assert tier_for(0.01, SIMPLE_CUTOFFS) == "common"  # exactly on the line
    assert tier_for(0.0099, SIMPLE_CUTOFFS) == "uncommon"
    assert tier_for(0.0005, SIMPLE_CUTOFFS) == "rare"
    assert tier_for(0.00001, SIMPLE_CUTOFFS) == "very_rare"
    assert tier_for(0.05, EFFORT_CUTOFFS) == "uncommon"


def test_simple_share_is_count_over_region_season_total(tmp_path):
    path = _write(
        tmp_path,
        [
            # region 30, fall: 3 mockingbirds + 1 deer = 4 sightings
            "sp_0001,30.27,-97.74,2025-11-01,30",
            "sp_0001,30.27,-97.74,2025-11-01,30",
            "sp_0001,30.27,-97.74,2025-11-02,30",
            "sp_0007,30.27,-97.74,2025-11-02,30",
            # region 24, fall: must not mix into region 30's total
            "sp_0001,31.76,-106.49,2025-11-01,24",
            # region 30, spring: a different season, also separate
            "sp_0007,30.27,-97.74,2025-04-01,30",
        ],
    )
    shares = simple_shares(path)
    assert shares[("sp_0001", "30", "fall")] == pytest.approx(3 / 4)
    assert shares[("sp_0007", "30", "fall")] == pytest.approx(1 / 4)
    assert shares[("sp_0001", "24", "fall")] == pytest.approx(1.0)
    assert shares[("sp_0007", "30", "spring")] == pytest.approx(1.0)


def test_effort_adjustment_counts_a_species_once_per_visit(tmp_path):
    # 4 visits in region 30, fall (a visit = one place on one day):
    #   A: Nov 1 at (30.27, -97.74): mockingbird x3, deer x1
    #   B: Nov 2 at (30.27, -97.74): mockingbird
    #   C: Nov 1 at (29.42, -98.49): mockingbird
    #   D: Nov 3 at (29.42, -98.49): deer
    path = _write(
        tmp_path,
        [
            "sp_0001,30.27,-97.74,2025-11-01,30",
            "sp_0001,30.27,-97.74,2025-11-01,30",
            "sp_0001,30.27,-97.74,2025-11-01,30",
            "sp_0007,30.27,-97.74,2025-11-01,30",
            "sp_0001,30.27,-97.74,2025-11-02,30",
            "sp_0001,29.42,-98.49,2025-11-01,30",
            "sp_0007,29.42,-98.49,2025-11-03,30",
        ],
    )
    freq = effort_adjusted_frequencies(path)
    assert freq[("sp_0001", "30", "fall")] == pytest.approx(3 / 4)  # visits A, B, C
    assert freq[("sp_0007", "30", "fall")] == pytest.approx(2 / 4)  # visits A, D

    # The simple method is swayed by the 3 repeat mockingbirds on visit A.
    shares = simple_shares(path)
    assert shares[("sp_0001", "30", "fall")] == pytest.approx(5 / 7)
    assert shares[("sp_0007", "30", "fall")] == pytest.approx(2 / 7)


def test_nearby_points_on_one_day_are_one_visit(tmp_path):
    # Two points about 100 m apart on the same day round to the same place,
    # so that is 1 visit, and the deer was on 1 of 1 visits.
    path = _write(
        tmp_path,
        [
            "sp_0001,30.2701,-97.7401,2025-11-01,30",
            "sp_0007,30.2709,-97.7409,2025-11-01,30",
        ],
    )
    freq = effort_adjusted_frequencies(path)
    assert freq[("sp_0007", "30", "fall")] == pytest.approx(1.0)


def test_rows_without_region_or_date_are_skipped(tmp_path):
    path = _write(
        tmp_path,
        [
            "sp_0001,30.27,-97.74,2025-11-01,30",
            "sp_0007,35.20,-101.80,2025-11-01,",  # no region
            "sp_0007,30.27,-97.74,not-a-date,30",  # bad date
        ],
    )
    assert simple_shares(path) == {("sp_0001", "30", "fall"): 1.0}


@pytest.mark.parametrize("method", ["simple", "effort_adjusted"])
def test_output_file_matches_interface_format(tmp_path, method):
    path = _write(
        tmp_path,
        [
            "sp_0001,30.27,-97.74,2025-11-01,30",
            "sp_0007,30.27,-97.74,2025-11-01,30",
            "sp_0002,31.76,-106.49,2025-07-04,24",
        ],
    )
    out = tmp_path / "rarity.csv"
    summary = build_rarity_table(path, out, method=method)

    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == ["species_id", "region", "season", "rarity_tier"]
    assert summary["rows"] == len(rows) == 3
    for r in rows:
        assert r["season"] in {"spring", "summer", "fall", "winter"}
        assert r["rarity_tier"] in {"common", "uncommon", "rare", "very_rare"}


def test_unknown_method_is_an_error(tmp_path):
    path = _write(tmp_path, ["sp_0001,30.27,-97.74,2025-11-01,30"])
    with pytest.raises(ValueError):
        build_rarity_table(path, tmp_path / "out.csv", method="magic")
