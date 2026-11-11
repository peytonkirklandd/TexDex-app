"""Photo scoring: the one place BioCLIP 2 plugs in.

An image scorer is any function shaped like this:

    scorer(photo_path, species_rows) -> {species_id: score}

where species_rows are the rows of the species list CSV and each score is
0 or more (higher = looks more like that species).

BioCLIP 2 is NOT wired in yet (that is the setup-week task). Until then
identify() uses the placeholder below, so its answers are driven by the
location boost alone. When BioCLIP is ready, add a `bioclip_image_scores`
function here with the same shape and point DEFAULT_IMAGE_SCORER at it.
Nothing else in the pipeline needs to change.
"""
from __future__ import annotations


def placeholder_image_scores(photo_path, species_rows: list[dict]) -> dict:
    """Stand-in for BioCLIP: every species gets the same score.

    Why equal scores and not random ones: equal scores honestly mean "the
    photo told us nothing", so a low top confidence (and not_sure=True) is the
    correct result. It never opens the photo, so it works before any photos exist.
    """
    return {row["species_id"]: 1.0 for row in species_rows}


DEFAULT_IMAGE_SCORER = placeholder_image_scores
