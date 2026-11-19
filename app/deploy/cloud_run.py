"""Put TexDex online with Google Cloud Run.

    gcloud auth login                       (once, in your browser)
    gcloud config set project <project-id>  (once)
    python -m app.deploy.cloud_run

What it does:
  1. Copies what the server needs into a temporary folder:
       - the git-tracked code in app/, contract/, data_engine/ and requirements.txt
       - the species tables and map shapes from data/processed/
       - the Dockerfile
     The data/ files are NOT in git (CLAUDE.md rule 4). They only go into
     the private container image that Cloud Run runs. .env and anything
     else are never copied.
  2. Asks Cloud Run to build that folder with the Dockerfile and run it.
     The Supabase URL and PUBLIC key are passed as settings. The secret key
     never leaves your laptop.

Settings, and why:
  --memory 4Gi --cpu 2      BioCLIP 2 needs about 3 GB of memory.
  --max-instances 1         one server process, because unconfirmed catches
                            are kept in its memory (supabase_store.py).
  --min-instances 0         sleeps when nobody is using it, so it stays in
                            the free tier. The first visit after a sleep
                            takes about a minute.
  --cpu-boost               extra CPU while starting up, so waking is faster.
  --allow-unauthenticated   anyone with the link can open the site (the app
                            itself still needs an account).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import load_config

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SERVICE = "texdex"
REGION = "us-central1"  # one of the regions where Cloud Run's free allowance applies
FOLDERS = ["app", "contract", "data_engine"]
DATA_FILES = ["species.csv", "rarity.csv", "species_groups.csv", "month_region.csv",
              "ecoregions.geojson", "texas_outline.geojson"]


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", *FOLDERS, "requirements.txt"],
                         cwd=ROOT, check=True, capture_output=True, text=True)
    return [line for line in out.stdout.splitlines() if line]


def main() -> None:
    config = load_config()
    if not (config["supabase_url"] and config["supabase_key"]):
        sys.exit("Put SUPABASE_URL and SUPABASE_ANON_KEY in .env first.")
    if config["demo_data"]:
        sys.exit("Only the 84-species demo list was found. Build Person A's tables into data/processed/ first.")
    processed = Path(config["species_csv"]).parent
    missing = [name for name in DATA_FILES if not (processed / name).is_file()]
    if missing:
        sys.exit(f"Missing from {processed}: {', '.join(missing)}")
    gcloud = shutil.which("gcloud")
    if gcloud is None:
        sys.exit("The gcloud command was not found. Install the Google Cloud CLI first.")

    with tempfile.TemporaryDirectory() as folder:
        stage = Path(folder)
        for name in tracked_files():
            (stage / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, stage / name)
        (stage / "data" / "processed").mkdir(parents=True)
        for name in DATA_FILES:
            shutil.copy2(processed / name, stage / "data" / "processed" / name)
        # Linux line endings: a Windows checkout can turn them into \r\n,
        # which would end up inside the start command on the server.
        dockerfile = (HERE / "Dockerfile").read_text(encoding="utf-8").replace("\r\n", "\n")
        (stage / "Dockerfile").write_text(dockerfile, encoding="utf-8", newline="\n")

        settings = f"SUPABASE_URL={config['supabase_url']},SUPABASE_ANON_KEY={config['supabase_key']}"
        subprocess.run([
            gcloud, "run", "deploy", SERVICE, "--source", str(stage), "--region", REGION,
            "--memory", "4Gi", "--cpu", "2", "--max-instances", "1", "--min-instances", "0",
            "--cpu-boost", "--timeout", "300", "--allow-unauthenticated",
            "--set-env-vars", settings, "--quiet",
        ], check=True)


if __name__ == "__main__":
    main()
