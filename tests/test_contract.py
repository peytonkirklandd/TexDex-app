"""Contract tests. These must always pass, for the fake now and the real identify() later.

Run the real one with: USE_FAKE_ID=0 python -m pytest
"""
import csv
import os
from datetime import date
from pathlib import Path

import pytest

from contract import identify, validate_result

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_INPUTS = [
    ("photo1.jpg", 30.2672, -97.7431, date(2026, 11, 15)),  # Austin
    ("photo2.jpg", 29.4241, -98.4936, date(2026, 4, 2)),  # San Antonio
    ("photo3.jpg", 31.7619, -106.4850, date(2026, 7, 20)),  # El Paso
]


@pytest.mark.parametrize("args", SAMPLE_INPUTS)
def test_identify_follows_contract(args):
    if os.getenv("USE_FAKE_ID", "1") == "0":
        pytest.importorskip("data_engine.identify")
    validate_result(identify(*args))


def test_fake_is_repeatable():
    assert identify(*SAMPLE_INPUTS[0]) == identify(*SAMPLE_INPUTS[0])


def _read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def test_species_mock_matches_interface():
    rows = _read(ROOT / "mocks" / "species_sample.csv")
    assert list(rows[0].keys()) == [
        "species_id", "scientific_name", "common_name", "family", "protected", "venomous"
    ]
    for r in rows:
        assert r["protected"] in {"yes", "no"}
        assert r["venomous"] in {"yes", "no"}


def test_rarity_mock_matches_interface():
    species = {r["species_id"] for r in _read(ROOT / "mocks" / "species_sample.csv")}
    rows = _read(ROOT / "mocks" / "rarity_sample.csv")
    assert list(rows[0].keys()) == ["species_id", "region", "season", "rarity_tier"]
    for r in rows:
        assert r["species_id"] in species
        assert r["season"] in {"spring", "summer", "fall", "winter"}
        assert r["rarity_tier"] in {"common", "uncommon", "rare", "very_rare"}
