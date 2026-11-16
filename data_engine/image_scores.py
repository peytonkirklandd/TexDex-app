"""Photo scoring: the one place BioCLIP 2 plugs in.

An image scorer is any function shaped like this:

    scorer(photo_path, species_rows) -> {species_id: score}

where species_rows are the rows of the species list CSV and each score is
0 or more (higher = looks more like that species).

Two scorers live here:
- bioclip_image_scores: the real one (BioCLIP 2). Needs the packages in
  requirements.txt and downloads the model the first time it runs.
- placeholder_image_scores: every species gets the same score. Used by the
  test suite so tests run without the model or any photo files.

Which one identify() uses is set by the TEXDEX_IMAGE_SCORER environment
variable: "bioclip" (the default) or "placeholder".

How BioCLIP scoring works (zero-shot classification, no training by us):
  1. Write one short sentence per species, e.g.
     "a photo of Mimus polyglottos with common name Northern Mockingbird."
  2. The model turns each sentence into a list of numbers (an "embedding"),
     and turns the photo into a list of numbers in the same space.
  3. The closer the photo's numbers are to a sentence's numbers, the better
     that species matches. Softmax turns those closeness values into
     scores that add up to 1.
Nothing in here knows about animal groups: birds, mammals, reptiles,
amphibians and fish are all just rows in the species list.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path

BIOCLIP_MODEL = "hf-hub:imageomics/bioclip-2"


def placeholder_image_scores(photo_path, species_rows: list[dict]) -> dict:
    """Stand-in for BioCLIP: every species gets the same score.

    Why equal scores and not random ones: equal scores honestly mean "the
    photo told us nothing", so a low top confidence (and not_sure=True) is the
    correct result. It never opens the photo, so it works before any photos exist.
    """
    return {row["species_id"]: 1.0 for row in species_rows}


def species_prompt(row: dict) -> str:
    """The sentence BioCLIP compares the photo against for one species.

    Why scientific + common name: BioCLIP was trained on text in this style,
    and using both names gives it two chances to recognise the species.
    This wording is a choice to check in the accuracy report.
    """
    return f"a photo of {row['scientific_name']} with common name {row['common_name']}."


# lru_cache = "remember the answer". Loading the model takes several seconds
# and a lot of memory, so we do it once per run, not once per photo.
@lru_cache(maxsize=1)
def _load_bioclip():
    # Imported here, not at the top of the file, so that everything else in
    # data_engine (rarity, regions, tests) works without torch installed.
    import open_clip

    model, _train_transform, preprocess = open_clip.create_model_and_transforms(BIOCLIP_MODEL)
    model.eval()  # "we are using the model, not training it"
    return model, preprocess, open_clip.get_tokenizer(BIOCLIP_MODEL)


# Where finished text embeddings are kept between runs (data/ is git-ignored).
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


# The species sentences never change between photos, so their embeddings are
# worked out once and reused. With the full Texas list (over a thousand
# species) that first pass takes minutes on a laptop, so the result is also
# saved to disk. The file name includes a fingerprint of the sentences and
# the model name: change the species list or the wording and a new file is
# made, so a stale one can never be used by mistake.
@lru_cache(maxsize=4)
def _text_embeddings(prompts: tuple):
    import torch

    text = "|".join((BIOCLIP_MODEL,) + prompts)
    fingerprint = hashlib.sha256(text.encode()).hexdigest()[:16]
    cache_file = _CACHE_DIR / f"text_embeddings_{fingerprint}.pt"
    if cache_file.is_file():
        return torch.load(cache_file, weights_only=True)

    model, _preprocess, tokenizer = _load_bioclip()
    chunks = []
    with torch.no_grad():  # no_grad: skip training bookkeeping, saves memory
        # In small batches so a list of a few thousand species does not need
        # all its memory at once.
        for start in range(0, len(prompts), 64):
            features = model.encode_text(tokenizer(list(prompts[start : start + 64])))
            # Scale each embedding to length 1, so the dot product below
            # measures direction only (cosine similarity).
            chunks.append(features / features.norm(dim=-1, keepdim=True))
    embeddings = torch.cat(chunks)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(embeddings, cache_file)
    return embeddings


def bioclip_image_scores(photo_path, species_rows: list[dict]) -> dict:
    """Score one photo against every species with BioCLIP 2.

    Returns {species_id: probability}; the probabilities add up to 1 across
    the species list. Raises FileNotFoundError if the photo does not exist.
    """
    import torch
    from PIL import Image

    model, preprocess, _tokenizer = _load_bioclip()
    text = _text_embeddings(tuple(species_prompt(row) for row in species_rows))

    # convert("RGB") handles PNGs with transparency and black-and-white photos.
    with Image.open(photo_path) as img:
        pixels = preprocess(img.convert("RGB")).unsqueeze(0)  # unsqueeze: a batch of 1

    with torch.no_grad():
        image = model.encode_image(pixels)
        image = image / image.norm(dim=-1, keepdim=True)
        # logit_scale is a number the model learned in training. It stretches
        # the similarities so softmax gives a confident spread instead of
        # nearly equal scores for everything.
        similarities = model.logit_scale.exp() * image @ text.T
        probabilities = similarities.softmax(dim=-1)[0].tolist()

    return {row["species_id"]: p for row, p in zip(species_rows, probabilities)}


SCORERS = {"bioclip": bioclip_image_scores, "placeholder": placeholder_image_scores}


def default_image_scorer():
    """The scorer named by TEXDEX_IMAGE_SCORER ("bioclip" if not set)."""
    name = os.getenv("TEXDEX_IMAGE_SCORER") or "bioclip"
    if name not in SCORERS:
        raise ValueError(f"TEXDEX_IMAGE_SCORER must be one of {sorted(SCORERS)}, got {name!r}")
    return SCORERS[name]
