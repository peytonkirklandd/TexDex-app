"""Step 4: combine the photo scores (BioCLIP) with the location boost.

The idea in one line:

    final score  =  photo score  x  (how common the species is here this month) ^ weight

then rescale so all the final scores add up to 1.

Why multiply: this is Bayes' rule. The photo says "it looks like X"; the
month-by-region table says "X is (un)likely here before we even look". A
species needs both kinds of evidence to end up on top, which is exactly what
we want for look-alikes (two similar snakes, only one of which lives in West
Texas).
"""
from __future__ import annotations

# How strongly location counts. 0 = ignore location (photo only), 1 = full
# Bayes. PLACEHOLDER: pick the final value from the accuracy report.
# Why not just 1: sighting counts are extremely lopsided (a mockingbird can
# be 1000x more reported than an ocelot), and at full strength that would
# drown out a clear photo of a rare animal. Raising to a power below 1
# shrinks those gaps: with 0.5, "1000x more common" becomes "about 32x".
LOCATION_WEIGHT = 0.5


def location_prior(counts_here: dict, species_ids: list[str]) -> dict:
    """Turn sighting counts for one region+month into "how likely is each
    species here", as numbers that add up to 1.

        prior = (sightings of the species + 1) / (all sightings + number of species)

    Why the "+1" (called add-one or Laplace smoothing): our data is
    incomplete. Zero sightings does not prove a species is never there, and a
    plain zero would multiply the photo score down to zero, so the app could
    never identify it no matter how clear the photo was. Pretending we saw
    every species one extra time keeps unseen species possible but unlikely.
    With no sightings at all, every species gets the same value (no boost).
    """
    total = sum(counts_here.get(s, 0) for s in species_ids)
    return {s: (counts_here.get(s, 0) + 1) / (total + len(species_ids)) for s in species_ids}


def combine_scores(
    image_scores: dict, prior: dict | None, weight: float = LOCATION_WEIGHT
) -> dict:
    """Return {species_id: confidence}, where the confidences add up to 1.

    image_scores: {species_id: score >= 0} from the photo model.
    prior: output of location_prior(), or None when we have no location data
           (point outside every region, or tables not built yet). None means
           the answer is just the photo scores, rescaled.
    """
    if any(score < 0 for score in image_scores.values()):
        raise ValueError("image scores must not be negative")

    if prior is None:
        combined = dict(image_scores)
    else:
        combined = {s: score * prior[s] ** weight for s, score in image_scores.items()}

    total = sum(combined.values())
    if total == 0:
        # The photo model gave every species zero. We know nothing, so say so
        # with equal scores rather than dividing by zero.
        return {s: 1 / len(combined) for s in combined}
    # Dividing by the total makes the scores add up to 1, so each one reads
    # as a confidence between 0 and 1 (what the contract requires).
    return {s: value / total for s, value in combined.items()}
