# Brief: Person A (Data + AI)

Read `CLAUDE.md` and `docs/interface.md` first.

## You own
`data_engine/`, plus tests and docs for this half.

## Don't touch
`app/`, `contract/`, `docs/interface.md` (ask first if the contract seems wrong).

## Tasks, in order

**Nov 12–15: Setup**
- [ ] GBIF account and a one-month Texas test download
- [ ] Run BioCLIP 2 on 20 of our own animal photos
- [ ] Download EPA ecoregions and the TPWD Species-by-County list
- [ ] Agree on the handoff formats and the ID function contract with B

**Nov 16–20: Foundations (Checkpoint 1, Fri Nov 20)**
- [ ] Full Texas vertebrate download; grain, duplicate, and missing-value checks
- [ ] Assign sightings to ecoregions and counties; build the species list
- [ ] Rarity tiers (simple, effort-adjusted) and the month-by-region table
- [ ] Prepare species names for BioCLIP; build a test set of about 2,000 photos; first accuracy number
- [ ] **Hand off to B:** species list CSV + rarity table CSV in the exact format in `docs/interface.md`

**Nov 21–23: Core loop (Checkpoint 2, Mon Nov 23)**
- [ ] Real `identify()` in `data_engine/identify.py` with the location boost. It must pass `tests/test_contract.py`.
- [ ] Accuracy report: with vs. without the boost, by animal group

**Nov 27–30: Polish (code freeze Nov 30)**
- [ ] Venomous-species warnings and simple species pages (name, family, rarity, photo)
- [ ] Tests for region assignment, rarity math, and score combining
- [ ] `docs/data-sources-log.md` (licenses, GBIF citation) and a limitations section

## Done means
- The species and rarity CSVs match `docs/interface.md` exactly
- `identify()` returns the contract format and passes the contract test
- The accuracy report shows with vs. without the boost
- All tests pass, and every data source is logged
