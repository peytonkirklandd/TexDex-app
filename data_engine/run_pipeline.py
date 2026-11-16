"""Run the data steps in order and print a short summary of each.

    python -m data_engine.run_pipeline --sightings <csv> --regions <geojson> --out-dir <folder>

Try it on the made-up test files:

    python -m data_engine.run_pipeline --sightings tests/fixtures/sightings_sample.csv --regions tests/fixtures/regions_sample.geojson --out-dir data/processed_sample

It only prints counts, never rows, so it is safe to run on the big real files.
Keep --out-dir inside data/ so outputs stay out of git.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .month_region import build_month_region_table
from .rarity import build_rarity_table
from .regions import EPA_CODE_PROPERTY, assign_regions


def run_pipeline(sightings_path, regions_path, out_dir, code_property=EPA_CODE_PROPERTY) -> dict:
    """Run every step. Returns {step name: summary dict}."""
    out_dir = Path(out_dir)
    assigned = out_dir / "sightings_with_region.csv"
    return {
        "assign_regions": assign_regions(sightings_path, regions_path, assigned, code_property),
        "rarity_simple": build_rarity_table(assigned, out_dir / "rarity_simple.csv", "simple"),
        "rarity_effort_adjusted": build_rarity_table(
            assigned, out_dir / "rarity_effort_adjusted.csv", "effort_adjusted"
        ),
        "month_region": build_month_region_table(assigned, out_dir / "month_region.csv"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the TexDex data tables.")
    parser.add_argument("--sightings", required=True, help="sightings CSV")
    parser.add_argument("--regions", required=True, help="regions GeoJSON (lat/lon)")
    parser.add_argument("--out-dir", required=True, help="folder for the output CSVs")
    parser.add_argument("--code-property", default=EPA_CODE_PROPERTY,
                        help="GeoJSON property holding the region code")
    args = parser.parse_args()

    summaries = run_pipeline(args.sightings, args.regions, args.out_dir, args.code_property)
    for step, summary in summaries.items():
        print(f"{step}: {summary}")
    print(f"outputs written to {args.out_dir}")


if __name__ == "__main__":
    main()
