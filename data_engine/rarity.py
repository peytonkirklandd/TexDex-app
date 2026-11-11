"""Step 2: rarity tiers per species x region x season.

Input: the sightings CSV produced by regions.assign_regions()
       (needs columns species_id, latitude, longitude, obs_date, region).
Output: CSV in the exact docs/interface.md format:
        species_id, region, season, rarity_tier

Two methods, both answer "how often does this species turn up here, this season?":

1. simple
   share = (sightings of this species) / (all sightings in that region+season)
   Easy to explain, but it measures what people *report*, not what lives
   there. One birder logging 300 grackles in an afternoon makes grackles look
   300x more common than the one snake they also saw.

2. effort_adjusted
   frequency = (visits where the species was seen at least once)
               / (all visits in that region+season)
   A "visit" is one place on one day. Counting each species at most once per
   visit removes the "300 grackles" problem, and dividing by the number of
   visits removes the "this region just has more observers" problem. This is
   the same idea eBird uses for its frequency charts.

PLACEHOLDERS to settle with real data: the tier cutoffs and the season months.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

# Meteorological seasons. PLACEHOLDER: docs/interface.md lists the season
# definition as an open decision for setup week.
SEASON_BY_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "fall", 10: "fall", 11: "fall",
}

# (minimum value, tier name), checked top to bottom. Anything below the last
# cutoff is "very_rare". PLACEHOLDER numbers until we see the real spread.
# Each tier is 10x rarer than the one above, because species counts are very
# lopsided (a few species make up most sightings), so equal steps would put
# almost everything in the bottom tier.
SIMPLE_CUTOFFS = [(0.01, "common"), (0.001, "uncommon"), (0.0001, "rare")]
# Frequencies run higher than shares (a common bird is on a big fraction of
# visits but is still a small slice of all sightings), so the cutoffs are higher.
EFFORT_CUTOFFS = [(0.10, "common"), (0.01, "uncommon"), (0.001, "rare")]

# How finely to round coordinates when deciding "same place".
# 2 decimal places of a degree is roughly 1 km.
VISIT_ROUNDING = 2

OUTPUT_COLUMNS = ["species_id", "region", "season", "rarity_tier"]


def season_of(obs_date: date) -> str:
    return SEASON_BY_MONTH[obs_date.month]


def tier_for(value: float, cutoffs: list[tuple[float, str]]) -> str:
    """Turn a share/frequency (0 to 1) into a tier name."""
    for minimum, tier in cutoffs:
        if value >= minimum:
            return tier
    return "very_rare"


def _read_usable_rows(sightings_path):
    """Yield (species_id, region, obs_date, latitude, longitude) for rows that
    have a region and a readable date. Skips the rest."""
    with open(sightings_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("region"):
                continue  # outside every region
            try:
                # [:10] keeps "2025-11-01" from longer stamps like "2025-11-01T08:30:00"
                obs_date = date.fromisoformat(row["obs_date"][:10])
            except (TypeError, ValueError):
                continue
            yield row["species_id"], row["region"], obs_date, row["latitude"], row["longitude"]


def simple_shares(sightings_path) -> dict:
    """{(species_id, region, season): share of all sightings in that region+season}"""
    counts = defaultdict(int)  # (species, region, season) -> sightings
    totals = defaultdict(int)  # (region, season) -> sightings
    for species_id, region, obs_date, _lat, _lon in _read_usable_rows(sightings_path):
        season = season_of(obs_date)
        counts[(species_id, region, season)] += 1
        totals[(region, season)] += 1
    return {
        key: count / totals[(key[1], key[2])] for key, count in counts.items()
    }


def effort_adjusted_frequencies(sightings_path) -> dict:
    """{(species_id, region, season): fraction of visits that reported the species}"""
    visits = defaultdict(set)  # (region, season) -> set of visits
    species_visits = defaultdict(set)  # (species, region, season) -> set of visits
    for species_id, region, obs_date, lat, lon in _read_usable_rows(sightings_path):
        season = season_of(obs_date)
        # One visit = one place on one day. Using a set means the same
        # species logged 300 times on one visit still counts once.
        visit = (obs_date, round(float(lat), VISIT_ROUNDING), round(float(lon), VISIT_ROUNDING))
        visits[(region, season)].add(visit)
        species_visits[(species_id, region, season)].add(visit)
    return {
        key: len(seen_on) / len(visits[(key[1], key[2])])
        for key, seen_on in species_visits.items()
    }


def build_rarity_table(sightings_path, out_path, method: str = "effort_adjusted") -> dict:
    """Write the rarity CSV for the handoff to Person B. Returns a summary dict.

    A species only gets a row for a region+season where it was actually seen.
    No row means "no record here", which is different from "very_rare".
    """
    if method == "simple":
        values, cutoffs = simple_shares(sightings_path), SIMPLE_CUTOFFS
    elif method == "effort_adjusted":
        values, cutoffs = effort_adjusted_frequencies(sightings_path), EFFORT_CUTOFFS
    else:
        raise ValueError(f"unknown method: {method!r} (use 'simple' or 'effort_adjusted')")

    tier_counts = defaultdict(int)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)
        # sorted() so the file comes out in the same order every run.
        for (species_id, region, season), value in sorted(values.items()):
            tier = tier_for(value, cutoffs)
            tier_counts[tier] += 1
            writer.writerow([species_id, region, season, tier])
    return {"method": method, "rows": len(values), "tiers": dict(tier_counts)}
