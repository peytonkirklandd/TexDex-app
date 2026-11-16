# Data Sources Log

Every dataset we use: where it came from, the license, filters applied, and the download date. Raw files stay in `data/` and never go into git.

| Source | What we use it for | License / citation | Filters applied | Downloaded | Notes |
|---|---|---|---|---|---|
| GBIF occurrences (Texas) | Sightings → species list, rarity, month-by-region | GBIF download DOI + citation: TBD | | | |
| EPA Level III ecoregions (EPA public map service `USEPA_Ecoregions_Level_III_and_IV`, layer 11) | Region assignment; the Dex map | U.S. Government work, public domain. Cite: U.S. EPA, Level III Ecoregions of the Continental United States. | The 12 Level III codes that touch Texas (23-27, 29-35); outlines simplified to about 1 km | 2026-11-11 | Fetched by `python -m data_engine.fetch_ecoregions` into `data/processed/`. Shapes run past the state line. |
| Texas state outline (U.S. Census Bureau TIGERweb, State_County layer 0) | Drawing the Dex map; clipping ecoregions to Texas | U.S. Government work, public domain | NAME = 'Texas'; simplified to about 1 km | 2026-11-11 | Same script. |
| Demo species table (`app/demo_data/`) | Lets the app run before the GBIF tables exist | Written by us; not from any dataset | n/a | n/a | Real Texas species, but regions, seasons, rarity and protected flags are ILLUSTRATIVE. Must not be reported as results. |
| TPWD Species-by-County list | Protected flag | | | | |
| Venomous-species list | Venomous flag | | | | |
| BioCLIP 2 (`imageomics/bioclip-2` on Hugging Face) | Identification model | MIT license. Cite: Gu et al., "BioCLIP 2: Emergent Properties from Scaling Hierarchical Contrastive Learning," NeurIPS 2025; model DOI 10.57967/hf/5765. The model card also asks to cite OpenCLIP and the original BioCLIP paper. | n/a | 2026-11-11 | Loaded through `open_clip` 3.3.0. Weights are cached by Hugging Face outside the repo, never committed. |

## Limitations
(Person A fills this in during polish week.)
