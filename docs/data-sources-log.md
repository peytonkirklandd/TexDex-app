# Data Sources Log

Every dataset we use: where it came from, the license, filters applied, and the download date. Raw files stay in `data/` and never go into git.

| Source | What we use it for | License / citation | Filters applied | Downloaded | Notes |
|---|---|---|---|---|---|
| GBIF occurrences (Texas) | Sightings → species list, rarity, month-by-region | GBIF download DOI + citation: TBD | | | |
| EPA Level III ecoregions | Region assignment | | | | |
| TPWD Species-by-County list | Protected flag | | | | |
| Venomous-species list | Venomous flag | | | | |
| BioCLIP 2 (`imageomics/bioclip-2` on Hugging Face) | Identification model | MIT license. Cite: Gu et al., "BioCLIP 2: Emergent Properties from Scaling Hierarchical Contrastive Learning," NeurIPS 2025; model DOI 10.57967/hf/5765. The model card also asks to cite OpenCLIP and the original BioCLIP paper. | n/a | 2026-11-11 | Loaded through `open_clip` 3.3.0. Weights are cached by Hugging Face outside the repo, never committed. |

## Limitations
(Person A fills this in during polish week.)
