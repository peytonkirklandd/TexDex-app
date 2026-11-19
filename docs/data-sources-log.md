# Data Sources Log

Every dataset we use: where it came from, the license, filters applied, and the download date. Raw files stay in `data/` and never go into git.

| Source | What we use it for | License / citation | Filters applied | Downloaded | Notes |
|---|---|---|---|---|---|
| GBIF occurrence counts for Texas (GBIF public API, `api.gbif.org/v1/occurrence/search` with `facet=speciesKey`; species names, family, class and IUCN code from `/v1/species/`) | Species list, rarity (simple method), month-by-region table | Records are CC0, CC BY or CC BY-NC depending on the publishing dataset (mostly eBird and iNaturalist). Cite: GBIF.org (16 November 2026) GBIF Occurrence Search, https://www.gbif.org. This is NOT a DOI download; the full download with a DOI is still to do. | Phylum Chordata; basisOfRecord = HUMAN_OBSERVATION; occurrenceStatus = PRESENT; year 2000 or later; hasCoordinate = true; hasGeospatialIssue = false; inside one simplified EPA Level III outline AND GADM Texas (`USA.44_1`), or inside a hand-drawn Gulf polygon; one request per region per month. Then: species with fewer than 5 records dropped (387), people/pets/farm animals dropped (5), non-vertebrate chordates dropped. | 2026-11-16 | 56,848,657 records counted; 1,356 species kept. Fetched by `python -m data_engine.fetch_gbif_counts` into `data/raw/`, tables built by `python -m data_engine.build_tables` into `data/processed/`. Counts only, so no per-visit information. |
| EPA Level III ecoregions (EPA public map service `USEPA_Ecoregions_Level_III_and_IV`, layer 11) | Region assignment; the Dex map | U.S. Government work, public domain. Cite: U.S. EPA, Level III Ecoregions of the Continental United States. | The 12 Level III codes that touch Texas (23-27, 29-35); outlines simplified to about 1 km | 2026-11-11 | Fetched by `python -m data_engine.fetch_ecoregions` into `data/processed/`. Shapes run past the state line. |
| Texas state outline (U.S. Census Bureau TIGERweb, State_County layer 0) | Drawing the Dex map; clipping ecoregions to Texas | U.S. Government work, public domain | NAME = 'Texas'; simplified to about 1 km | 2026-11-11 | Same script. |
| Demo species table (`app/demo_data/`) | Lets the app run before the GBIF tables exist | Written by us; not from any dataset | n/a | n/a | Real Texas species, but regions, seasons, rarity and protected flags are ILLUSTRATIVE. Must not be reported as results. |
| TPWD Species-by-County list | Protected flag | | | | |
| Venomous-species list | Venomous flag | | | | |
| BioCLIP 2 (`imageomics/bioclip-2` on Hugging Face) | Identification model | MIT license. Cite: Gu et al., "BioCLIP 2: Emergent Properties from Scaling Hierarchical Contrastive Learning," NeurIPS 2025; model DOI 10.57967/hf/5765. The model card also asks to cite OpenCLIP and the original BioCLIP paper. | n/a | 2026-11-11 | Loaded through `open_clip` 3.3.0. Weights are cached by Hugging Face outside the repo, never committed. |

## Limitations
(Person A finishes this in polish week. Known so far:)
- **Counts follow observers, not animals.** Over 95% of the GBIF records are birds. Rarity is therefore measured within each animal class, but inside a class it still reflects what people report and where they go.
- **Simple rarity only.** The API gives counts, not individual sightings, so the effort-adjusted method (per visit) cannot be built from it yet.
- **Region edges are approximate.** The outlines sent to GBIF are simplified (up to tens of km in places), so sightings near a boundary may be counted in the neighbouring region. The Gulf polygon is hand-drawn.
- **Protected flag is a placeholder**: IUCN Vulnerable/Endangered/Critically Endangered plus a short hand list, not the TPWD list. It over-flags some widespread birds (which only blurs their pins).
- **The list includes escaped and introduced species** that have 5 or more records, and common names are GBIF's, lightly tidied.
