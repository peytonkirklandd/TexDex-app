"""The game layer: XP, levels, titles and badges.

Everything here is worked out from the list of catches. Nothing is stored,
so a level or badge can never get out of step with the collection.
"""
from __future__ import annotations

import math

# XP for a species the user has never caught before. Rarer = worth more;
# each step is roughly 2.5x, to match how much harder each tier is to find.
XP_NEW_SPECIES = {"common": 40, "uncommon": 100, "rare": 250, "very_rare": 600}
# A repeat of a species you already have still earns a little, so going out
# is always rewarded, but far less than finding something new.
REPEAT_SHARE = 0.2

TITLES = [
    "Greenhorn", "Trail Scout", "Brush Tracker", "Field Naturalist", "Creek Wader",
    "Canyon Ranger", "Hill Country Guide", "Big Bend Explorer", "Lone Star Naturalist",
    "Legend of the Llano",
]


def xp_for_catch(tier: str, is_new_species: bool) -> int:
    full = XP_NEW_SPECIES.get(tier, XP_NEW_SPECIES["uncommon"])
    return full if is_new_species else max(5, round(full * REPEAT_SHARE))


def level_for_xp(xp: int) -> dict:
    """Level n starts at 100 * (n-1)^2 XP: 0, 100, 400, 900, 1600, ...

    Why a square: each level takes a bit more than the last (100, 300, 500,
    ... more XP), so early levels come fast and keep new players hooked,
    while later ones take real exploring.
    """
    level = int(math.sqrt(xp / 100)) + 1
    floor = 100 * (level - 1) ** 2
    ceiling = 100 * level ** 2
    return {
        "level": level,
        "title": TITLES[min(level, len(TITLES)) - 1],
        "xp": xp,
        "xp_into_level": xp - floor,
        "xp_for_level": ceiling - floor,
        "xp_to_next": ceiling - xp,
    }


def badges(catches: list[dict], dex) -> list[dict]:
    """Every badge with earned True/False, worked out from the catches."""
    species = {c["species_id"] for c in catches}
    infos = [dex.species[sid] for sid in species if sid in dex.species]
    regions = {c["region"] for c in catches if c["region"]}
    tiers = {c["tier"] for c in catches}

    result = []

    def add(key, icon, name, hint, earned):
        result.append({"key": key, "icon": icon, "name": name, "hint": hint, "earned": bool(earned)})

    add("first_catch", "📸", "First Catch", "Log your first animal", len(catches) >= 1)
    add("species_5", "🌱", "Getting Started", "Discover 5 species", len(species) >= 5)
    add("species_15", "🧭", "Explorer", "Discover 15 species", len(species) >= 15)
    add("species_40", "🏆", "Master Naturalist", "Discover 40 species", len(species) >= 40)

    # One badge per animal group that exists in the species list. Built from
    # the data, so a new group (fish, say) gets a badge without code changes.
    from .dex import GROUP_ORDER, group_for_class

    groups = {}  # group key -> (label, icon)
    for sp in dex.species.values():
        key, label, icon = group_for_class(sp["animal_class"])
        groups[key] = (label, icon)
    ordered = [g for g in GROUP_ORDER if g in groups] + sorted(set(groups) - set(GROUP_ORDER))
    for key in ordered:
        label, icon = groups[key]
        add(f"group_{key}", icon, f"{label} Spotter", f"Catch your first of the {label.lower()}",
            any(sp["group"] == key for sp in infos))

    add("regions_3", "🗺️", "Road Tripper", "Catch animals in 3 regions", len(regions) >= 3)
    add("regions_6", "🚙", "Cross-Texas", "Catch animals in 6 regions", len(regions) >= 6)
    add("rare_find", "💎", "Rare Find", "Catch a rare or very rare species",
        tiers & {"rare", "very_rare"})
    add("very_rare", "🌟", "Once in a Lifetime", "Catch a very rare species", "very_rare" in tiers)
    add("venomous", "⚠️", "Respectful Distance", "Photograph a venomous species (from far away!)",
        any(sp["venomous"] for sp in infos))
    add("protected", "🛡️", "Guardian", "Record a protected species",
        any(sp["protected"] for sp in infos))
    add("gulf", "🌊", "Salt Life", "Catch something in Gulf or bay waters",
        "outside_land" in regions)
    return result


def profile_stats(catches: list[dict], dex) -> dict:
    from .dex import TIER_ORDER, region_info

    species = {c["species_id"] for c in catches}
    rarest = None
    if catches:
        best = max(catches, key=lambda c: TIER_ORDER.index(c["tier"]) if c["tier"] in TIER_ORDER else 0)
        sp = dex.species.get(best["species_id"])
        if sp:
            rarest = {"common_name": sp["common_name"], "tier": best["tier"], "icon": sp["icon"]}
    regions = sorted({c["region"] for c in catches if c["region"]})
    return {
        "species": len(species),
        "species_total": len(dex.species),
        "catches": len(catches),
        "regions": len(regions),
        "regions_total": len(dex.regions),
        "region_names": [region_info(r)["name"] for r in regions],
        "rarest": rarest,
    }
