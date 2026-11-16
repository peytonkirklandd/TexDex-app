# TexDex-app (Case 2)

## Goal
A Texas-only web app: a user photographs a wild animal, an AI model (BioCLIP 2) identifies the species, and each new species is saved to the user's collection and a shared map. What makes it ours is the **data engine**: rarity tiers and a "what lives here this month" location boost built from real GBIF sightings, plus a published accuracy report. The app is the front end for that work.

Final files are due before class on **Tue Dec 1, 2026**. Code freeze is **Sun Nov 30**.

## Who owns what
- **Person A (Data + AI)** owns `data_engine/`: GBIF cleaning, ecoregions/counties, species list, rarity, month-by-region table, BioCLIP setup, the real ID function, accuracy report, venomous warnings, species pages.
- **Person B (App + Backend)** owns `app/`: Supabase tables + row-level security, sign-up/log-in/profile, catch flow, My Collection, shared map with protected species blurred, duplicate-photo check, deployment to Hugging Face.
- **Shared, both must agree before changing:** `contract/` and `docs/interface.md`.

Each session's brief is in `docs/brief-person-a.md` or `docs/brief-person-b.md`. Read yours before starting work.

## Hard rules
1. Only edit files in your own folder (`data_engine/` or `app/`), plus tests and docs for your half.
2. **Never edit `contract/` or `docs/interface.md` on your own.** If the contract needs to change, stop and ask me.
3. Person B never changes model or ID logic; B only *calls* `identify()`.
4. Nothing from `data/` goes into git (licensed/raw data). Log every data source, filter, and download date in `docs/data-sources-log.md`.
5. No real passwords or personal accounts. Use made-up test accounts only. Secrets live in `.env`, which is never committed.
6. Protected-species locations must never be exposed unblurred anywhere: map, API responses, logs, or exports.

## How to work
- One small task at a time, on its own branch (e.g. `a/rarity-tiers`, `b/catch-flow`). Every change goes through a GitHub pull request that the other person reviews.
- Write tests for new behavior and run `python -m pytest` before saying a task is done. `tests/test_contract.py` must always pass.
- Commit in small steps with clear messages.

## We have to explain all of this in an interview without AI
Both of us will be quizzed on the whole project (Dec 10 or 12), so:
- Prefer the simplest code that works over clever code.
- Comment the *why* on any non-obvious logic (rarity math, score combining, blurring).
- In every PR description, include a short plain-English "How this works" section: what it does, why we built it this way, and what could go wrong.

## Stack
- Python 3.11+, `pytest` for tests
- Supabase (auth + Postgres with row-level security)
- BioCLIP 2 for identification
- Deployment: free Hugging Face Space (B confirms BioCLIP 2 fits during setup)
- Web framework: **Flask** (Python server in `app/server.py`, plain HTML/CSS/JavaScript front end in `app/static/`). Local storage is SQLite until the Supabase project exists.

## Scope guardrails
Cut list (do NOT build): this-week forecast, zoo/aquarium detection, iNaturalist export, leaderboards/social, native mobile apps, training our own model.
If we miss Checkpoint 2 (Nov 23): cut species pages first, then the duplicate-photo check. Never cut accounts/collections, identification, rarity, the accuracy report, or tests.
