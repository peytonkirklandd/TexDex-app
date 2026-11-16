"""Build the DEMO data files the app runs on until Person A's real tables exist.

    python -m app.demo_data.build_demo_data

Reads  demo_species_table.csv  (hand-written: real Texas species, but the
regions, seasons, rarity and protected flags are ILLUSTRATIVE, not measured)
and writes four files next to it, in the same formats the real ones will have:

  species.csv        docs/interface.md species list (6 columns)
  rarity.csv         docs/interface.md rarity table (4 columns)
  month_region.csv   data_engine month-by-region table (used for the location boost)
  species_groups.csv species_id -> animal_class, icon (what the Dex filters and draws with)

Nothing in here comes from GBIF or any licensed source, so these files are
safe to commit. To switch to real data, point the TEXDEX_* environment
variables at the real files (see app/config.py).
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Shorthand used in the `regions` column of the table. The numbers are EPA
# Level III ecoregion codes; "outside_land" is the data engine's code for
# Gulf and bay water.
LAND = ["23", "24", "25", "26", "27", "29", "30", "31", "32", "33", "34", "35"]
REGION_GROUPS = {
    "ALL": LAND,
    "WEST": ["23", "24"],
    "PLAINS": ["25", "26", "27"],
    "CENTRAL": ["29", "30", "32", "33"],
    "SOUTH": ["31", "34"],
    "EAST": ["33", "34", "35"],
    "GULF": ["outside_land"],
}
SEASON_MONTHS = {
    "winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8], "fall": [9, 10, 11],
}
# Made-up sighting counts per month for each tier, so the location boost has
# something to work with. Rarer tier = fewer pretend sightings.
PRETEND_SIGHTINGS = {"common": 120, "uncommon": 30, "rare": 6, "very_rare": 1}


def expand_regions(text: str) -> list[str]:
    """'WEST;30' -> ['23', '24', '30'] (no repeats, order kept)."""
    codes = []
    for part in text.split(";"):
        for code in REGION_GROUPS.get(part, [part]):
            if code not in codes:
                codes.append(code)
    return codes


def expand_seasons(text: str) -> list[str]:
    return list(SEASON_MONTHS) if text == "all" else text.split(";")


def build(out_dir=HERE) -> dict:
    out_dir = Path(out_dir)
    with open(HERE / "demo_species_table.csv", newline="", encoding="utf-8") as f:
        table = list(csv.DictReader(f))

    species, groups, rarity, months = [], [], [], []
    for row in table:
        species.append([row[c] for c in (
            "species_id", "scientific_name", "common_name", "family", "protected", "venomous")])
        groups.append([row["species_id"], row["animal_class"], row["icon"]])
        for region in expand_regions(row["regions"]):
            for season in expand_seasons(row["seasons"]):
                rarity.append([row["species_id"], region, season, row["tier"]])
                for month in SEASON_MONTHS[season]:
                    months.append([region, month, row["species_id"], PRETEND_SIGHTINGS[row["tier"]]])

    def write(name, header, rows):
        with open(out_dir / name, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    write("species.csv",
          ["species_id", "scientific_name", "common_name", "family", "protected", "venomous"], species)
    write("species_groups.csv", ["species_id", "animal_class", "icon"], groups)
    write("rarity.csv", ["species_id", "region", "season", "rarity_tier"], rarity)
    write("month_region.csv", ["region", "month", "species_id", "sightings"], sorted(months))
    return {"species": len(species), "rarity_rows": len(rarity), "month_rows": len(months),
            "classes": sorted({g[1] for g in groups})}


if __name__ == "__main__":
    print(build())
