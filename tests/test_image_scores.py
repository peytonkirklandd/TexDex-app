"""Tests for photo scoring (data_engine/image_scores.py).

The tests that load the real BioCLIP 2 model are skipped by default because
the model is a large download. Run them with:

    RUN_BIOCLIP_TESTS=1 python -m pytest tests/test_image_scores.py
"""
import csv
import os
from pathlib import Path

import pytest

from data_engine.image_scores import (
    bioclip_image_scores,
    default_image_scorer,
    placeholder_image_scores,
    species_prompt,
)

SPECIES_WITH_FISH = Path(__file__).resolve().parent / "fixtures" / "species_with_fish.csv"

needs_bioclip = pytest.mark.skipif(
    os.getenv("RUN_BIOCLIP_TESTS") != "1",
    reason="set RUN_BIOCLIP_TESTS=1 to run tests that load the BioCLIP model",
)


def _species_rows():
    with open(SPECIES_WITH_FISH, newline="") as f:
        return list(csv.DictReader(f))


def test_prompt_uses_scientific_and_common_name():
    row = {"scientific_name": "Sciaenops ocellatus", "common_name": "Red Drum"}
    assert species_prompt(row) == "a photo of Sciaenops ocellatus with common name Red Drum."


def test_scorer_is_chosen_by_environment_variable(monkeypatch):
    monkeypatch.setenv("TEXDEX_IMAGE_SCORER", "placeholder")
    assert default_image_scorer() is placeholder_image_scores
    monkeypatch.setenv("TEXDEX_IMAGE_SCORER", "bioclip")
    assert default_image_scorer() is bioclip_image_scores
    # Not set at all means the real model, so a deployed app never quietly
    # runs on the placeholder.
    monkeypatch.delenv("TEXDEX_IMAGE_SCORER")
    assert default_image_scorer() is bioclip_image_scores


def test_unknown_scorer_name_is_an_error(monkeypatch):
    monkeypatch.setenv("TEXDEX_IMAGE_SCORER", "magic")
    with pytest.raises(ValueError):
        default_image_scorer()


def test_placeholder_gives_every_species_the_same_score():
    scores = placeholder_image_scores("no_such_photo.jpg", _species_rows())
    assert len(scores) == 9
    assert len(set(scores.values())) == 1


@needs_bioclip
def test_bioclip_scores_every_species_and_adds_up_to_one(tmp_path):
    from PIL import Image

    photo = tmp_path / "plain.jpg"
    Image.new("RGB", (640, 480), (120, 140, 90)).save(photo)
    rows = _species_rows()

    scores = bioclip_image_scores(photo, rows)

    # One score per species, fish included: nothing is filtered by animal group.
    assert set(scores) == {row["species_id"] for row in rows}
    assert all(0.0 <= s <= 1.0 for s in scores.values())
    assert sum(scores.values()) == pytest.approx(1.0, abs=1e-4)
    # Same photo, same answer.
    assert bioclip_image_scores(photo, rows) == scores


@needs_bioclip
def test_bioclip_missing_photo_is_an_error():
    with pytest.raises(FileNotFoundError):
        bioclip_image_scores("no_such_photo.jpg", _species_rows())
