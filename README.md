# TexDex-app

Photograph a wild animal in Texas, get an AI identification (BioCLIP 2) boosted by what lives in that region this month, and fill your Dex.

## What the app does

Three tabs along the bottom:

1. **Catch** (camera icon). Opens the rear camera. Take a photo, the app checks it is usable (not blurry, too dark, or too far away, and says why in plain words if it is), then shows the model's top 3 guesses. You confirm one and it is saved.
2. **Dex** (book icon). A map of Texas split into the 12 EPA Level III ecoregions plus Gulf waters. Pick a region, filter by animal group (birds, mammals, reptiles, amphibians, fish, sharks and rays). Each animal is a card: your photo if you have caught it, a silhouette if not. With no filters it shows every species from #001.
3. **Profile**. Level, XP, badges, progress per animal group, recent catches.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # Windows ARM: see the note in requirements.txt first
python -m data_engine.fetch_ecoregions   # once: downloads the map shapes into data/
python -m app                    # demo mode: instant, but guesses are random
python -m app --bioclip          # real BioCLIP 2 identification
python -m pytest
```

Open http://localhost:5000 and sign up with a **made-up** username and password.

To try it on a phone, the page must be served over https (phone browsers only allow the camera on https or localhost). Deployment to a Hugging Face Space is not done yet.

## What is real and what is not (yet)

| Part | Status |
|---|---|
| BioCLIP 2 identification + location boost | Real. Runs locally with `--bioclip`. |
| Ecoregion shapes, Texas outline | Real (EPA, U.S. Census Bureau). Downloaded into `data/`, not in git. |
| Species list, regions, rarity, protected flags | **Demo data** in `app/demo_data/`: real Texas species, illustrative values. Replaced by Person A's GBIF tables via the `TEXDEX_*` environment variables in `app/config.py`. |
| Accounts and storage | Local SQLite file (`app/store.py`). The Supabase tables and row-level security are written in `app/supabase/schema.sql` but not applied. |

## Layout
```
contract/     shared ID function contract + fake (both agree before changing)
data_engine/  Person A: regions, rarity, month table, BioCLIP scoring, real identify()
app/          Person B: server, catch flow, Dex, profile, privacy, static front end
  server.py       web routes (Flask)
  catch.py        photo -> check -> identify -> confirm -> save
  photo_check.py  blurry / dark / too small checks and the plain-language messages
  dex.py          species, regions, rarity lookups, collection computed from catches
  game.py         XP, levels, badges (all computed from catches)
  privacy.py      location blurring for protected species
  store.py        SQLite tables
  static/         the one-page front end (HTML, CSS, JavaScript)
mocks/        fake sample data in the agreed formats
docs/         interface spec, per-person briefs, data-sources log
tests/        contract tests + each half's tests
data/         raw/licensed data, the database and saved photos (git-ignored)
```
