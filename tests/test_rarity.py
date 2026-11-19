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

    # The skipped rows show up in the summary instead of disappearing.
    summary = build_rarity_table(path, tmp_path / "out.csv")
    assert summary["skipped_no_region"] == 1
    assert summary["skipped_bad_date"] == 1


def test_water_sightings_get_rarity_tiers_too(tmp_path):
    # Fish in the Gulf carry the region "outside_land" and are rated like any other.
    path = _write(
        tmp_path,
        [
            "sp_f001,27.50,-96.50,2025-07-05,outside_land",
            "sp_f001,27.80,-96.90,2025-07-06,outside_land",
            "sp_f002,27.50,-96.50,2025-07-05,outside_land",
        ],
    )
    shares = simple_shares(path)
    assert shares[("sp_f001", "outside_land", "summer")] == pytest.approx(2 / 3)
    assert shares[("sp_f002", "outside_land", "summer")] == pytest.approx(1 / 3)


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


# ---------- rarity from a table of counts ----------

def test_shares_from_counts_compare_each_animal_with_its_own_kind(tmp_path):
    from data_engine.rarity import build_rarity_from_month_table, shares_from_month_table

    table = tmp_path / "month_region.csv"
    table.write_text(
        "region,month,species_id,sightings\n"
        "30,4,bird_a,900\n"      # April and May are both spring, so they add up
        "30,5,bird_a,90\n"
        "30,4,bird_b,10\n"
        "30,4,fish_a,3\n"
        "30,4,fish_b,1\n"
        "30,7,fish_a,5\n"        # summer is a separate season
    )
    groups = {"bird_a": "birds", "bird_b": "birds", "fish_a": "fish", "fish_b": "fish"}

    # Against every sighting, the fish look vanishingly rare...
    plain = shares_from_month_table(table)
    assert plain[("fish_a", "30", "spring")] == pytest.approx(3 / 1004)
    # ...but among fish, fish_a is 3 of the 4 spring fish records.
    within = shares_from_month_table(table, groups)
    assert within[("fish_a", "30", "spring")] == pytest.approx(3 / 4)
    assert within[("fish_b", "30", "spring")] == pytest.approx(1 / 4)
    assert within[("bird_a", "30", "spring")] == pytest.approx(990 / 1000)
    assert within[("fish_a", "30", "summer")] == pytest.approx(1.0)

    out = tmp_path / "rarity.csv"
    summary = build_rarity_from_month_table(table, out, groups)
    with open(out, newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == ["species_id", "region", "season", "rarity_tier"]
    assert summary["rows"] == len(rows) == 5


# ---------- building the app's tables from GBIF counts ----------

def test_build_tables_from_made_up_gbif_files(tmp_path):
    import json
    from data_engine.build_tables import build_tables, tidy_common_name

    assert tidy_common_name("Bullfrog, North American bullfrog", "Lithobates catesbeianus") == "Bullfrog"
    assert tidy_common_name("Texas spiny lizard", "Sceloporus olivaceus") == "Texas Spiny Lizard"
    assert tidy_common_name("Scutulatus", "Crotalus scutulatus") == "Crotalus scutulatus"
    assert tidy_common_name("", "Falco atricapillus") == "Falco atricapillus"

    raw, out = tmp_path / "raw", tmp_path / "out"
    raw.mkdir()
    (raw / "gbif_counts.csv").write_text(
        "region,month,species_key,sightings\n"
        "30,4,1,50\n30,7,1,40\n"          # a bird
        "outside_land,7,2,9\n"            # a fish with no class in GBIF
        "30,4,3,6\n"                      # a rattlesnake
        "30,4,4,2\n"                      # too few sightings
        "30,4,5,80\n"                     # a person
        "30,4,6,30\n"                     # a sea squirt
    )
    def sp(sci, common, family, order, cls, iucn=""):
        return {"scientific_name": sci, "common_name": common, "family": family, "order": order,
                "class": cls, "iucn": iucn}
    (raw / "gbif_species.json").write_text(json.dumps({
        "1": sp("Grus americana", "Whooping Crane", "Gruidae", "Gruiformes", "Aves", "EN"),
        "2": sp("Sciaenops ocellatus", "red drum", "Sciaenidae", "Perciformes", ""),
        "3": sp("Crotalus atrox", "Western Diamond-backed Rattlesnake", "Viperidae", "", "Squamata", "LC"),
        "4": sp("Rarus rarus", "Rare Thing", "Raridae", "", "Aves"),
        "5": sp("Homo sapiens", "Human", "Hominidae", "Primates", "Mammalia"),
        "6": sp("Styela plicata", "Pleated Sea Squirt", "Styelidae", "", "Ascidiacea"),
    }))

    summary = build_tables(raw, out)

    with open(out / "species.csv", newline="", encoding="utf-8") as f:
        species = {r["scientific_name"]: r for r in csv.DictReader(f)}
    with open(out / "species_groups.csv", newline="", encoding="utf-8") as f:
        groups = {r["species_id"]: r["animal_class"] for r in csv.DictReader(f)}

    assert set(species) == {"Grus americana", "Sciaenops ocellatus", "Crotalus atrox"}
    # Every species left out is counted with its reason.
    assert summary["left_out"] == {"fewer_than_5_sightings": 1, "people_pets_farm_animals": 1,
                                   "not_a_vertebrate": 1}
    assert species["Grus americana"]["protected"] == "yes"
    assert species["Crotalus atrox"]["venomous"] == "yes"
    assert species["Sciaenops ocellatus"]["common_name"] == "Red Drum"
    assert groups[species["Sciaenops ocellatus"]["species_id"]] == "Actinopterygii"  # blank class = fish
    assert list(species["Grus americana"].keys()) == [
        "species_id", "scientific_name", "common_name", "family", "protected", "venomous"]
    with open(out / "month_region.csv", newline="") as f:
        assert len(list(csv.DictReader(f))) == 4
