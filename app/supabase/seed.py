"""Copy the species and rarity tables from our CSVs into Supabase.

    python -m app.supabase.seed

Run it once after applying schema.sql, and again whenever the CSVs change
(for example when Person A's real GBIF tables replace the demo ones). Rows
that already exist are updated, not duplicated.

Why the SECRET key: the species and rarity tables are read-only for app
users (see schema.sql), so filling them needs the project's secret key,
which skips row-level security. It is read from SUPABASE_SECRET_KEY in your
local .env. Never put it on the web server or in git; the app itself only
ever uses the public key.
"""
from __future__ import annotations

import csv
import os

import requests

from app.config import load_config

BATCH = 500  # rows per request, so a large rarity table goes up in chunks


def _yes(value: str) -> bool:
    return str(value).strip().lower() in ("yes", "true", "1")


def _upload(url: str, key: str, table: str, rows: list[dict]) -> None:
    headers = {"apikey": key, "Content-Type": "application/json",
               # "if this primary key exists already, update it instead"
               "Prefer": "resolution=merge-duplicates,return=minimal"}
    if key.startswith("eyJ"):  # older "service_role" keys are JWTs and go here too
        headers["Authorization"] = f"Bearer {key}"
    for start in range(0, len(rows), BATCH):
        r = requests.post(f"{url}/rest/v1/{table}", headers=headers,
                          json=rows[start:start + BATCH], timeout=60)
        if r.status_code >= 400:
            raise SystemExit(f"{table}: {r.status_code} {r.text[:300]}")
    print(f"{table}: {len(rows)} rows")


def main() -> None:
    config = load_config()
    url, key = config["supabase_url"], os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SECRET_KEY in .env first.")
    url = url.rstrip("/")

    with open(config["species_csv"], newline="", encoding="utf-8") as f:
        species = [{"species_id": r["species_id"], "scientific_name": r["scientific_name"],
                    "common_name": r["common_name"], "family": r["family"],
                    "protected": _yes(r["protected"]), "venomous": _yes(r["venomous"])}
                   for r in csv.DictReader(f)]
    with open(config["rarity_csv"], newline="", encoding="utf-8") as f:
        rarity = [{"species_id": r["species_id"], "region": r["region"],
                   "season": r["season"], "rarity_tier": r["rarity_tier"]}
                  for r in csv.DictReader(f)]

    print(f"From {config['species_csv'].parent}")
    _upload(url, key, "species", species)  # first: rarity rows point at species
    _upload(url, key, "rarity", rarity)


if __name__ == "__main__":
    main()
