"""Step 3: the month-by-region table ("what lives here this month").

Input: the sightings CSV produced by regions.assign_regions().
Output CSV: region, month, species_id, sightings
            (one row per species seen in that region in that calendar month)

identify() uses this table for the location boost: a species that is often
reported in this region in this month gets its score nudged up.

Why month and not season: migration moves fast (a warbler can be everywhere
in April and gone in June), and the boost only helps if it follows that.
Why we store raw counts and not percentages: the smoothing in combine.py
needs the counts, and counts are easier to check by hand.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

OUTPUT_COLUMNS = ["region", "month", "species_id", "sightings"]


def build_month_region_table(sightings_path, out_path) -> dict:
    """Count sightings per region x month x species and write them to a CSV.
    Years are pooled: every November from every year goes in month 11."""
    counts = defaultdict(int)  # (region, month, species_id) -> sightings
    # Rows we cannot use are counted, not silently dropped. Sightings over
    # water are not among them: they carry the region "outside_land".
    skipped = {"skipped_no_region": 0, "skipped_bad_date": 0}
    with open(sightings_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("region"):
                skipped["skipped_no_region"] += 1  # outside Texas or bad coordinates
                continue
            try:
                month = date.fromisoformat(row["obs_date"][:10]).month
            except (TypeError, ValueError):
                skipped["skipped_bad_date"] += 1
                continue
            counts[(row["region"], month, row["species_id"])] += 1

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_COLUMNS)
        for (region, month, species_id), n in sorted(counts.items()):
            writer.writerow([region, month, species_id, n])

    return {
        "rows": len(counts),
        "region_months": len({(region, month) for region, month, _ in counts}),
        "sightings_counted": sum(counts.values()),
        **skipped,
    }


def load_month_region_table(table_path) -> dict:
    """Read the table back as {(region, month): {species_id: sightings}}."""
    table = defaultdict(dict)
    with open(table_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table[(row["region"], int(row["month"]))][row["species_id"]] = int(row["sightings"])
    return dict(table)
