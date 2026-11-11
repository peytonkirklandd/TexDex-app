"""Real ID function. Follows contract/id_contract.py and passes tests/test_contract.py.

What happens on each call:
  1. Score the photo against every species on our list   (image_scores.py)
  2. Find which region the point is in                    (regions.py)
  3. Look up what is reported in that region this month   (month_region.py)
  4. Multiply the two together and rescale to 0-1         (combine.py)
  5. Return the top 3, plus not_sure if the best one is weak

The three data files come from environment variables so we can switch from
mock to real data without touching code:
  TEXDEX_SPECIES_CSV       species list         (default: mocks/species_sample.csv)
  TEXDEX_REGIONS_GEOJSON   region shapes        (default: data/processed/ecoregions.geojson)
  TEXDEX_MONTH_REGION_CSV  month-by-region table (default: data/processed/month_region.csv)

If the region file or the month table is missing, identify() still works but
skips the location boost (photo scores only).
"""
from __future__ import annotations

import csv
import logging
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from contract.id_contract import NOT_SURE_CUTOFF, NUM_GUESSES, Guess, IDResult, PhotoInput

from .combine import LOCATION_WEIGHT, combine_scores, location_prior
from .image_scores import DEFAULT_IMAGE_SCORER
from .month_region import load_month_region_table
from .regions import find_region, load_regions

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SPECIES = _ROOT / "mocks" / "species_sample.csv"
_DEFAULT_REGIONS = _ROOT / "data" / "processed" / "ecoregions.geojson"
_DEFAULT_MONTH_TABLE = _ROOT / "data" / "processed" / "month_region.csv"


# lru_cache = "remember the answer". Each file is read once, the first time it
# is needed, instead of on every photo.
@lru_cache(maxsize=None)
def _load_species(path: str) -> tuple:
    with open(path, newline="", encoding="utf-8") as f:
        return tuple(csv.DictReader(f))


@lru_cache(maxsize=None)
def _load_regions(path: str) -> list:
    return load_regions(path)


@lru_cache(maxsize=None)
def _load_month_table(path: str) -> dict:
    return load_month_region_table(path)


def identify_with(
    photo_path: PhotoInput,
    latitude: float,
    longitude: float,
    obs_date: date,
    *,
    species_path,
    regions_path=None,
    month_table_path=None,
    image_scorer=DEFAULT_IMAGE_SCORER,
    weight: float = LOCATION_WEIGHT,
) -> IDResult:
    """identify() with every file and setting passed in explicitly.

    Tests use this with small made-up files, and the accuracy report will use
    it to compare weight=0 (no boost) against the boosted version.
    """
    species_rows = list(_load_species(str(species_path)))
    species_ids = [row["species_id"] for row in species_rows]
    if len(species_ids) < NUM_GUESSES:
        raise ValueError(f"need at least {NUM_GUESSES} species, got {len(species_ids)}")

    image_scores = image_scorer(photo_path, species_rows)

    # Location boost. prior stays None (= no boost) unless we have both data
    # files and the point falls inside a region.
    prior = None
    if regions_path and month_table_path:
        region = find_region(latitude, longitude, _load_regions(str(regions_path)))
        if region is not None:
            table = _load_month_table(str(month_table_path))
            counts_here = table.get((region, obs_date.month), {})
            prior = location_prior(counts_here, species_ids)

    confidences = combine_scores(image_scores, prior, weight)

    # Highest confidence first. Ties are broken by species_id so the same
    # input always gives the same order.
    ranked = sorted(confidences.items(), key=lambda item: (-item[1], item[0]))
    guesses = [Guess(species_id=s, confidence=c) for s, c in ranked[:NUM_GUESSES]]
    return IDResult(guesses=guesses, not_sure=guesses[0].confidence < NOT_SURE_CUTOFF)


def _existing_file(env_name: str, default: Path) -> Path | None:
    """Path from the environment variable (or the default) if the file exists, else None."""
    path = Path(os.getenv(env_name) or default)
    if path.is_file():
        return path
    # Says only which file is missing. Never log coordinates here: a
    # protected species' location must not end up in the logs (CLAUDE.md rule 6).
    log.warning("%s not found at %s; identify() will skip the location boost", env_name, path)
    return None


def identify(
    photo_path: PhotoInput, latitude: float, longitude: float, obs_date: date
) -> IDResult:
    """The function Person B calls (through contract.identify)."""
    return identify_with(
        photo_path,
        latitude,
        longitude,
        obs_date,
        species_path=os.getenv("TEXDEX_SPECIES_CSV") or _DEFAULT_SPECIES,
        regions_path=_existing_file("TEXDEX_REGIONS_GEOJSON", _DEFAULT_REGIONS),
        month_table_path=_existing_file("TEXDEX_MONTH_REGION_CSV", _DEFAULT_MONTH_TABLE),
    )
