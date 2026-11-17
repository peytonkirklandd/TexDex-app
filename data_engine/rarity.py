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


def new_skip_counts() -> dict:
    """Counter for rows a step could not use, so nothing is dropped silently."""
    return {"skipped_no_region": 0, "skipped_bad_date": 0}


def _read_usable_rows(sightings_path, skipped: dict | None = None):
    """Yield (species_id, region, obs_date, latitude, longitude) for rows that
    have a region and a readable date. Rows it cannot use are counted in
    `skipped` (see new_skip_counts) instead of vanishing.

    Note: sightings over water are NOT skipped here. regions.assign_regions()
    gives them the region "outside_land", so they are counted like any other.
    An empty region only means outside Texas or unusable coordinates.
    """
    if skipped is None:
        skipped = new_skip_counts()
    with open(sightings_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("region"):
                skipped["skipped_no_region"] += 1
                continue
            try:
                # [:10] keeps "2025-11-01" from longer stamps like "2025-11-01T08:30:00"
                obs_date = date.fromisoformat(row["obs_date"][:10])
            except (TypeError, ValueError):
                skipped["skipped_bad_date"] += 1
                continue
            yield row["species_id"], row["region"], obs_date, row["latitude"], row["longitude"]


def simple_shares(sightings_path, skipped: dict | None = None) -> dict:
    """{(species_id, region, season): share of all sightings in that region+season}"""
    counts = defaultdict(int)  # (species, region, season) -> sightings
    totals = defaultdict(int)  # (region, season) -> sightings
    for species_id, region, obs_date, _lat, _lon in _read_usable_rows(sightings_path, skipped):
        season = season_of(obs_date)
        counts[(species_id, region, season)] += 1
        totals[(region, season)] += 1
    return {
        key: count / totals[(key[1], key[2])] for key, count in counts.items()
    }


def effort_adjusted_frequencies(sightings_path, skipped: dict | None = None) -> dict:
    """{(species_id, region, season): fraction of visits that reported the species}"""
    visits = defaultdict(set)  # (region, season) -> set of visits
    species_visits = defaultdict(set)  # (species, region, season) -> set of visits
    for species_id, region, obs_date, lat, lon in _read_usable_rows(sightings_path, skipped):
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
    skipped = new_skip_counts()
    if method == "simple":
        values, cutoffs = simple_shares(sightings_path, skipped), SIMPLE_CUTOFFS
    elif method == "effort_adjusted":
        values, cutoffs = effort_adjusted_frequencies(sightings_path, skipped), EFFORT_CUTOFFS
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
    return {"method": method, "rows": len(values), "tiers": dict(tier_counts), **skipped}


# ---------- rarity from a table of counts (no visit information) ----------

def shares_from_month_table(month_table_path, group_of: dict | None = None) -> dict:
    """{(species_id, region, season): share} from a month-by-region table
    (columns region, month, species_id, sightings).

    This is the "simple" method, with one change: when `group_of` is given
    ({species_id: animal group}), a species is compared only with its own
    kind. share = its sightings / all sightings OF THAT GROUP in the
    region + season.

    Why: birdwatchers file hundreds of times more records than anyone else.
    Measured against every sighting, a largemouth bass or a common toad
    would come out "very rare" only because few people report fish and
    frogs. Comparing fish with fish and birds with birds removes that.
    """
    counts = defaultdict(int)   # (species, region, season) -> sightings
    totals = defaultdict(int)   # (region, season, group) -> sightings
    with open(month_table_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            season = SEASON_BY_MONTH[int(row["month"])]
            group = group_of.get(row["species_id"], "") if group_of else ""
            n = int(row["sightings"])
            counts[(row["species_id"], row["region"], season)] += n
            totals[(row["region"], season, group)] += n
    return {
        (species_id, region, season):
            n / totals[(region, season, group_of.get(species_id, "") if group_of else "")]
        for (species_id, region, season), n in counts.items()
    }


def build_rarity_from_month_table(month_table_path, out_path, group_of: dict | None = None) -> dict:
    """Write the docs/interface.md rarity CSV from a month-by-region table."""
    shares = shares_from_month_table(month_table_path, group_of)
    tier_counts = defaultdict(int)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)
        for (species_id, region, season), share in sorted(shares.items()):
            tier = tier_for(share, SIMPLE_CUTOFFS)
            tier_counts[tier] += 1
            writer.writerow([species_id, region, season, tier])
    return {"method": "simple, within animal group" if group_of else "simple",
            "rows": len(shares), "tiers": dict(tier_counts)}
