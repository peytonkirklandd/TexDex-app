"""Where the app finds its files. Everything can be overridden with an
environment variable, so switching from demo data to Person A's real tables
needs no code change.

  TEXDEX_SPECIES_CSV         species list           (docs/interface.md, section 1)
  TEXDEX_RARITY_CSV          rarity table           (docs/interface.md, section 2)
  TEXDEX_SPECIES_GROUPS_CSV  species_id -> animal_class, icon
  TEXDEX_MONTH_REGION_CSV    month-by-region table  (used inside identify())
  TEXDEX_REGIONS_GEOJSON     ecoregion shapes
  TEXDEX_OUTLINE_GEOJSON     Texas outline (for drawing the map)
  TEXDEX_APP_DATA            folder for the database and saved photos
  SUPABASE_URL, SUPABASE_ANON_KEY   when both are set, accounts, catches and
                             photos are kept in Supabase instead of the local
                             SQLite file (see supabase_store.py)

Settings can also come from a .env file in the project folder (never
committed). Real environment variables win over .env.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DEMO = ROOT / "app" / "demo_data"
PROCESSED = ROOT / "data" / "processed"


def _project_url(url: str | None) -> str | None:
    """Supabase's dashboard shows the address both as https://x.supabase.co
    and as https://x.supabase.co/rest/v1/. Accept either; keep the first."""
    if not url:
        return None
    url = url.strip().rstrip("/")
    return url.removesuffix("/rest/v1")


def load_config() -> dict:
    """Build the config dict from environment variables and defaults."""
    def path(env_name: str, default: Path) -> Path:
        return Path(os.getenv(env_name) or default)

    # Which species tables to use. The real ones (built from GBIF by
    # `python -m data_engine.build_tables`) win when they exist; otherwise the
    # small made-up demo set. TEXDEX_USE_DEMO=1 forces the demo set (tests do this).
    real_tables = (PROCESSED / "species.csv").is_file() and os.getenv("TEXDEX_USE_DEMO") != "1"
    tables = PROCESSED if real_tables else DEMO
    species_csv = path("TEXDEX_SPECIES_CSV", tables / "species.csv")
    app_data = path("TEXDEX_APP_DATA", ROOT / "data" / "app")  # data/ is git-ignored
    return {
        "species_csv": species_csv,
        "rarity_csv": path("TEXDEX_RARITY_CSV", tables / "rarity.csv"),
        "groups_csv": path("TEXDEX_SPECIES_GROUPS_CSV", tables / "species_groups.csv"),
        "month_region_csv": path("TEXDEX_MONTH_REGION_CSV", tables / "month_region.csv"),
        "regions_geojson": path("TEXDEX_REGIONS_GEOJSON", PROCESSED / "ecoregions.geojson"),
        "outline_geojson": path("TEXDEX_OUTLINE_GEOJSON", PROCESSED / "texas_outline.geojson"),
        "db_path": app_data / "texdex.sqlite3",
        "photo_dir": app_data / "photos",
        # True while the species list is the made-up demo one; the app shows a
        # "demo data" note so nobody mistakes it for real rarity numbers.
        "demo_data": species_csv == DEMO / "species.csv",
        # The fake ID function returns random confidences, so its "not sure"
        # flag means nothing. Only enforce it with the real model.
        "use_fake_id": os.getenv("USE_FAKE_ID", "1") == "1",
        "warm_up_model": True,
        # Empty = use the local SQLite file.
        "supabase_url": _project_url(os.getenv("SUPABASE_URL")),
        "supabase_key": os.getenv("SUPABASE_ANON_KEY") or None,
    }


def share_files_with_identify(config: dict) -> None:
    """identify() reads its file locations from environment variables. Point
    them at the same files the app uses, unless they were already set, so the
    model's species list and the Dex's species list can never disagree."""
    os.environ.setdefault("TEXDEX_SPECIES_CSV", str(config["species_csv"]))
    os.environ.setdefault("TEXDEX_MONTH_REGION_CSV", str(config["month_region_csv"]))
    os.environ.setdefault("TEXDEX_REGIONS_GEOJSON", str(config["regions_geojson"]))
