"""Fake ID function for Person B to build against until Nov 21.

It ignores the photo and returns made-up guesses in exactly the contract format,
drawn from the mock species list. Seeded by the inputs, so the same inputs
always give the same answer (which makes testing easier).
"""
from __future__ import annotations

import csv
import random
from datetime import date
from pathlib import Path

from .id_contract import NOT_SURE_CUTOFF, NUM_GUESSES, Guess, IDResult, PhotoInput

_MOCK_SPECIES = Path(__file__).resolve().parent.parent / "mocks" / "species_sample.csv"


def _species_ids() -> list[str]:
    with open(_MOCK_SPECIES, newline="") as f:
        return [row["species_id"] for row in csv.DictReader(f)]


def fake_identify(
    photo_path: PhotoInput, latitude: float, longitude: float, obs_date: date
) -> IDResult:
    rng = random.Random(f"{photo_path}|{latitude}|{longitude}|{obs_date}")
    picks = rng.sample(_species_ids(), NUM_GUESSES)
    confs = sorted((round(rng.uniform(0.05, 0.95), 3) for _ in picks), reverse=True)
    guesses = [Guess(species_id=s, confidence=c) for s, c in zip(picks, confs)]
    return IDResult(guesses=guesses, not_sure=confs[0] < NOT_SURE_CUTOFF)
