# TexDex-app

Photograph a wild animal in Texas, get an AI identification boosted by real GBIF sighting data, and build your collection and a shared map.

> Person B finishes this README during polish week (Nov 27–30).

## Layout
```
contract/     shared ID function contract + fake (both agree before changing)
data_engine/  Person A: data cleaning, rarity, BioCLIP, real identify()
app/          Person B: Supabase, pages, catch flow, map, deployment
mocks/        fake sample data in the agreed formats
docs/         interface spec, per-person briefs, data-sources log
tests/        contract tests + each half's tests
data/         raw/licensed data (git-ignored)
```

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest
```
