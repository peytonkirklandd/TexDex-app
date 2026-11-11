"""Location blurring (CLAUDE.md hard rule 6).

Protected species (ocelot, whooping crane, ...) can be harmed if people learn
exactly where they are. So for a protected species we blur the location
BEFORE it is saved. The exact point is never written to the database, which
means no map, API response, export or log can leak it later, even by mistake.
"""
from __future__ import annotations

import math

# Size of the blur grid in degrees. 0.25 degrees is roughly 25 km, so a
# blurred point only says "somewhere in this 25 km square".
BLUR_GRID_DEGREES = 0.25

# Everyone else's catches are shown on the shared map rounded to this many
# decimal places (2 = about 1 km). That is for the *user's* privacy: the map
# should not show the exact spot someone was standing.
SHARED_MAP_DECIMALS = 2


def blur_location(latitude: float, longitude: float) -> tuple[float, float]:
    """Snap a point to the centre of its grid square.

    Why the centre of a fixed grid and not "add some random noise": with
    random noise, many sightings of the same animal would cluster around the
    true spot and their average would give it away. Every point in a square
    maps to the same centre, so repeats reveal nothing more.
    """
    def snap(value: float) -> float:
        return round((math.floor(value / BLUR_GRID_DEGREES) + 0.5) * BLUR_GRID_DEGREES, 4)

    return snap(latitude), snap(longitude)


def location_to_store(protected: bool, latitude, longitude):
    """The coordinates that are allowed to be saved for a catch."""
    if latitude is None or longitude is None:
        return None, None
    if protected:
        return blur_location(latitude, longitude)
    return latitude, longitude


def location_for_shared_map(latitude: float, longitude: float) -> tuple[float, float]:
    return round(latitude, SHARED_MAP_DECIMALS), round(longitude, SHARED_MAP_DECIMALS)
