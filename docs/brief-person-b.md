# Brief: Person B (App + Backend)

Read `CLAUDE.md` and `docs/interface.md` first.

## You own
`app/`, plus tests and docs for this half (README, demo script).

## Don't touch
`data_engine/`, `contract/`, `docs/interface.md` (ask first if the contract seems wrong). Never change model or ID logic; only call `identify()`.

## Build against mocks until A delivers
- Species/rarity data: `mocks/species_sample.csv`, `mocks/rarity_sample.csv`
- Identification: `from contract import identify` returns fake guesses while `USE_FAKE_ID=1` (the default)

## Tasks, in order

**Nov 12–15: Setup**
- [ ] Private GitHub repo (this starter), confirm folder structure and `.gitignore`
- [ ] Supabase project and a test sign-up from a script
- [ ] Check that BioCLIP 2 fits on a free Hugging Face Space
- [ ] Agree on the handoff formats and the ID function contract with A

**Nov 16–20: Foundations (Checkpoint 1, Fri Nov 20)**
- [ ] Database tables (profiles, catches, species, rarity) with row-level security
- [ ] Sign-up, log-in, and profile pages
- [ ] Skeleton app with every page; load species/rarity tables (mock first, then A's real CSVs)

**Nov 21–23: Core loop (Checkpoint 2, Mon Nov 23)**
- [ ] Catch flow: photo → ID → confirm → save
- [ ] My Collection page (found species vs. blank outlines), computed from catches, not a separate table
- [ ] Shared map, with protected species' locations blurred
- [ ] Switch to A's real `identify()` (`USE_FAKE_ID=0`) and retest the catch flow

**Nov 27–30: Polish (code freeze Nov 30)**
- [ ] Duplicate-photo check; deploy to Hugging Face
- [ ] Tests for location blurring and collection logic
- [ ] README, demo script, backup screen recording

## Done means
- On a phone: sign up, catch an animal, and see it in My Collection and on the map
- Protected-species locations are blurred everywhere they appear
- All tests pass, and the app is deployed
