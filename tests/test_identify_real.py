"""Tests for the real identify() (data_engine/identify.py).

These call the real function directly, so they run no matter what
USE_FAKE_ID is set to. Photo scores come from small fake scorers here
so these tests need neither the BioCLIP model nor real photos
(tests/conftest.py selects the placeholder scorer; BioCLIP itself is
covered in tests/test_image_scores.py).
"""
from datetime import date
from pathlib import Path

import pytest

from contract import validate_result
from data_engine.identify import identify, identify_with
from data_engine.month_region import build_month_region_table
from data_engine.regions import assign_regions

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SPECIES = ROOT / "mocks" / "species_sample.csv"
REGIONS = FIXTURES / "regions_sample.geojson"

AUSTIN = (30.2672, -97.7431)
EL_PASO = (31.7619, -106.4850)
GULF = (27.5, -96.5)  # off Corpus Christi: in Texas waters, in no land region
FAR_AWAY = (45.0, -96.5)  # outside the Texas box altogether
SPECIES_WITH_FISH = FIXTURES / "species_with_fish.csv"


@pytest.fixture
def month_table(tmp_path):
    """Run the real pipeline steps on the made-up sightings."""
    assigned = tmp_path / "assigned.csv"
    assign_regions(FIXTURES / "sightings_sample.csv", REGIONS, assigned)
    out = tmp_path / "month_region.csv"
    build_month_region_table(assigned, out)
    return out


def _two_way_tie(photo_path, species_rows):
    """Fake photo model that cannot decide between the mockingbird (sp_0001)
    and the rattlesnake (sp_0002)."""
    scores = {row["species_id"]: 0.01 for row in species_rows}
    scores["sp_0001"] = 0.45
    scores["sp_0002"] = 0.45
    return scores


@pytest.mark.parametrize(
    "args",
    [
        ("photo1.jpg", *AUSTIN, date(2026, 11, 15)),
        ("photo2.jpg", 29.4241, -98.4936, date(2026, 4, 2)),
        ("photo3.jpg", *EL_PASO, date(2026, 7, 20)),
    ],
)
def test_real_identify_follows_contract_with_default_files(args):
    validate_result(identify(*args))


def test_real_identify_is_repeatable():
    args = ("photo1.jpg", *AUSTIN, date(2026, 11, 15))
    assert identify(*args) == identify(*args)


def test_location_boost_breaks_a_tie_toward_the_local_species(month_table):
    kwargs = dict(
        species_path=SPECIES,
        regions_path=REGIONS,
        month_table_path=month_table,
        image_scorer=_two_way_tie,
    )
    # Austin in November: mockingbirds are in the sightings, rattlesnakes are not.
    austin = identify_with("p.jpg", *AUSTIN, date(2026, 11, 15), **kwargs)
    validate_result(austin)
    assert austin.guesses[0].species_id == "sp_0001"
    assert austin.guesses[0].confidence > austin.guesses[1].confidence

    # Same photo scores near El Paso in July: the rattlesnake wins instead.
    el_paso = identify_with("p.jpg", *EL_PASO, date(2026, 7, 20), **kwargs)
    validate_result(el_paso)
    assert el_paso.guesses[0].species_id == "sp_0002"


def test_weight_zero_turns_the_boost_off(month_table):
    result = identify_with(
        "p.jpg", *AUSTIN, date(2026, 11, 15),
        species_path=SPECIES, regions_path=REGIONS, month_table_path=month_table,
        image_scorer=_two_way_tie, weight=0.0,
    )
    validate_result(result)
    assert result.guesses[0].confidence == pytest.approx(result.guesses[1].confidence)


def test_gulf_photo_is_boosted_toward_fish(month_table):
    def fish_or_bird(photo_path, species_rows):
        """Fake photo model torn between the red drum and the mockingbird."""
        scores = {row["species_id"]: 0.01 for row in species_rows}
        scores["sp_f001"] = 0.45
        scores["sp_0001"] = 0.45
        return scores

    kwargs = dict(
        species_path=SPECIES_WITH_FISH, regions_path=REGIONS,
        month_table_path=month_table, image_scorer=fish_or_bird,
    )
    # In the Gulf in July the made-up sightings are mostly red drum.
    gulf = identify_with("p.jpg", *GULF, date(2026, 7, 10), **kwargs)
    validate_result(gulf)
    assert gulf.guesses[0].species_id == "sp_f001"
    # The same photo scores in Austin in November go to the mockingbird.
    austin = identify_with("p.jpg", *AUSTIN, date(2026, 11, 15), **kwargs)
    assert austin.guesses[0].species_id == "sp_0001"


def test_point_outside_texas_gets_no_boost(month_table):
    result = identify_with(
        "p.jpg", *FAR_AWAY, date(2026, 11, 15),
        species_path=SPECIES, regions_path=REGIONS, month_table_path=month_table,
        image_scorer=_two_way_tie,
    )
    validate_result(result)
    assert result.guesses[0].confidence == pytest.approx(result.guesses[1].confidence)


def test_missing_data_files_still_gives_a_valid_answer():
    result = identify_with(
        "p.jpg", *AUSTIN, date(2026, 11, 15),
        species_path=SPECIES, image_scorer=_two_way_tie,
    )
    validate_result(result)


def test_not_sure_flag_follows_the_top_confidence():
    def confident(photo_path, species_rows):
        scores = {row["species_id"]: 0.01 for row in species_rows}
        scores["sp_0007"] = 0.94
        return scores

    sure = identify_with("p.jpg", *AUSTIN, date(2026, 11, 15), species_path=SPECIES, image_scorer=confident)
    assert sure.guesses[0].species_id == "sp_0007"
    assert sure.not_sure is False

    # The placeholder scorer gives every species the same score, so it should say "not sure".
    unsure = identify_with("p.jpg", *AUSTIN, date(2026, 11, 15), species_path=SPECIES)
    assert unsure.not_sure is True
