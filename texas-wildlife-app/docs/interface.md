# Interface: Person A → Person B

This file is the contract between the two halves. **Neither person changes it alone.** Propose a change at a Tue/Thu check-in, agree, then update this file and `contract/` in the same PR.

Mock versions of everything below live in `mocks/` and `contract/fake_identify.py`, so B can build before A's real outputs exist.

---

## 1. Texas species list (due Fri Nov 20)

CSV, one row per species. Mock: `mocks/species_sample.csv`

| column | type | notes |
|---|---|---|
| species_id | string | stable ID; never reused or renumbered |
| scientific_name | string | e.g. `Dasypus novemcinctus` |
| common_name | string | e.g. `Nine-banded Armadillo` |
| family | string | e.g. `Dasypodidae` |
| protected | `yes` / `no` | from the TPWD list; `yes` = location must be blurred on the map |
| venomous | `yes` / `no` | drives the venomous-species warning |

## 2. Rarity table (due Fri Nov 20)

CSV, one row per species × region × season. Mock: `mocks/rarity_sample.csv`

| column | type | notes |
|---|---|---|
| species_id | string | matches the species list |
| region | string | EPA Level III ecoregion code (Texas has 12) |
| season | `spring` / `summer` / `fall` / `winter` | **confirm season definition in setup week** |
| rarity_tier | `common` / `uncommon` / `rare` / `very_rare` | **placeholder tier names; A confirms** |

## 3. ID function (due Sat Nov 21)

Python function in the repo. Code version of this contract: `contract/id_contract.py`

```python
identify(photo_path, latitude, longitude, obs_date) -> IDResult
```

**Input**
- `photo_path`: path to the uploaded image file (**confirm in setup week:** path vs. raw bytes)
- `latitude`, `longitude`: floats (decimal degrees)
- `obs_date`: `datetime.date`

**Output: `IDResult`**
- `guesses`: exactly 3 `Guess` objects, sorted highest confidence first
  - each `Guess` has `species_id` (string) and `confidence` (float, 0 to 1)
- `not_sure`: `True` when the top confidence is below `NOT_SURE_CUTOFF`

`NOT_SURE_CUTOFF` is a placeholder (0.5) in `contract/id_contract.py`. A sets the final value from the accuracy work.

**Until Nov 21**, B uses `contract/fake_identify.py`, which returns made-up guesses in exactly this format. When the real function lands, B switches by setting `USE_FAKE_ID=0` in `.env`, with no other code changes.

`tests/test_contract.py` checks that the fake follows this contract. A's real function must pass the same test.

---

## Open decisions for setup week (Nov 12–15)
- [ ] Photo input: file path or raw bytes?
- [ ] Season boundaries (which months are which season)
- [ ] Final rarity tier names
- [ ] Final `NOT_SURE_CUTOFF` (A, from accuracy results, can be set later)
- [ ] Web framework (record in CLAUDE.md)
