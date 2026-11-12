"""The Dex: every species, which regions it lives in, how rare it is there,
and which ones a user has caught.

Loads the species list and rarity table once (the CSV formats in
docs/interface.md). A user's collection is worked out from their catches
each time it is asked for; nothing about "caught or not" is stored here.
"""
from __future__ import annotations

import csv
from pathlib import Path

# Rarest last. Used to pick "the most common tier" when a species has
# several tiers across seasons.
TIER_ORDER = ["common", "uncommon", "rare", "very_rare"]
TIER_LABELS = {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "very_rare": "Very Rare"}
SEASONS = ["spring", "summer", "fall", "winter"]

# The 12 EPA Level III ecoregions that touch Texas, west to east-ish, plus
# the data engine's code for Gulf and bay water. Names are EPA's; the
# colours and one-line descriptions are ours. A region code that is not in
# this table still works: it is shown under its code with a neutral colour.
REGION_INFO = {
    "23": ("Arizona/New Mexico Mountains", "Sky-island peaks of the Guadalupes", "#8a7a9a"),
    "24": ("Chihuahuan Deserts", "Big Bend country: desert, canyon, yucca", "#c98e5a"),
    "25": ("High Plains", "The Llano Estacado: flat, windy, wide open", "#d2b46a"),
    "26": ("Southwestern Tablelands", "Red canyons and caprock of the Panhandle", "#b5694a"),
    "27": ("Central Great Plains", "Rolling mesquite and red-dirt prairie", "#b9a878"),
    "29": ("Cross Timbers", "Post-oak woods and tallgrass in between", "#8f9a5a"),
    "30": ("Edwards Plateau", "The Hill Country: limestone, springs, caves", "#6f8f6a"),
    "31": ("Southern Texas Plains", "Thorn-scrub brush country", "#c2a24e"),
    "32": ("Texas Blackland Prairies", "Deep black soil, the last tallgrass", "#7d8fa3"),
    "33": ("East Central Texas Plains", "Post-oak savanna", "#8fae9a"),
    "34": ("Western Gulf Coastal Plain", "Marsh, bay and barrier island", "#6aa3a8"),
    "35": ("South Central Plains", "The Piney Woods", "#4f7a58"),
    "outside_land": ("Gulf & Coastal Waters", "Open water, bays and surf", "#5f86a8"),
}

# How scientific class names are grouped into the filter buttons. A class
# that is not listed here is NOT dropped: it gets its own button named after
# the class (see group_for_class).
CLASS_GROUPS = {
    "Aves": ("birds", "Birds", "🐦"),
    "Mammalia": ("mammals", "Mammals", "🦌"),
    # GBIF splits reptiles into these orders-as-classes; people think "reptiles".
    "Reptilia": ("reptiles", "Reptiles", "🦎"),
    "Squamata": ("reptiles", "Reptiles", "🦎"),
    "Testudines": ("reptiles", "Reptiles", "🦎"),
    "Crocodylia": ("reptiles", "Reptiles", "🦎"),
    "Amphibia": ("amphibians", "Amphibians", "🐸"),
    "Actinopterygii": ("fish", "Fish", "🐟"),
    "Elasmobranchii": ("sharks_rays", "Sharks & Rays", "🦈"),
}
GROUP_ORDER = ["birds", "mammals", "reptiles", "amphibians", "fish", "sharks_rays"]


def group_for_class(animal_class: str) -> tuple[str, str, str]:
    """(key, label, icon) of the filter button for a scientific class."""
    if animal_class in CLASS_GROUPS:
        return CLASS_GROUPS[animal_class]
    name = animal_class or "Other"
    return (name.lower(), name, "🐾")


def region_info(code: str) -> dict:
    name, blurb, color = REGION_INFO.get(code, (f"Region {code}", "", "#8a8fa8"))
    return {"code": code, "name": name, "blurb": blurb, "color": color}


def _read_csv(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Dex:
    def __init__(self, species_csv, rarity_csv, groups_csv=None):
        groups = {}
        if groups_csv and Path(groups_csv).is_file():
            groups = {row["species_id"]: row for row in _read_csv(groups_csv)}

        # Species keep the order of the file. The position is the Dex number.
        self.species: dict[str, dict] = {}
        for number, row in enumerate(_read_csv(species_csv), start=1):
            extra = groups.get(row["species_id"], {})
            key, label, default_icon = group_for_class(extra.get("animal_class", ""))
            self.species[row["species_id"]] = {
                "species_id": row["species_id"],
                "number": number,
                "common_name": row["common_name"],
                "scientific_name": row["scientific_name"],
                "family": row["family"],
                "animal_class": extra.get("animal_class", ""),
                "group": key,
                "group_label": label,
                "icon": extra.get("icon") or default_icon,
                "protected": row["protected"] == "yes",
                "venomous": row["venomous"] == "yes",
            }

        # rarity[(species_id, region)] = {season: tier}
        self.rarity: dict[tuple[str, str], dict[str, str]] = {}
        for row in _read_csv(rarity_csv):
            if row["species_id"] in self.species:
                self.rarity.setdefault((row["species_id"], row["region"]), {})[row["season"]] = (
                    row["rarity_tier"])

        # Regions in our preferred order, then any unknown codes alphabetically.
        seen = {region for _species, region in self.rarity}
        known = [code for code in REGION_INFO if code in seen]
        self.regions = known + sorted(seen - set(known))

    # ---------- rarity lookups ----------

    def regions_of(self, species_id: str) -> list[str]:
        return [r for r in self.regions if (species_id, r) in self.rarity]

    def tier(self, species_id: str, region: str | None = None, season: str | None = None) -> str:
        """Rarity tier to show for a species.

        Tries the most specific answer first and falls back step by step:
        this region + this season, then this region in any season, then
        anywhere in Texas. Where several tiers apply we show the most common
        one, so a species is never labelled rarer than it is at its best time.
        A species with no rarity rows at all is shown as "uncommon".
        """
        if region and (species_id, region) in self.rarity:
            by_season = self.rarity[(species_id, region)]
            if season in by_season:
                return by_season[season]
            return min(by_season.values(), key=TIER_ORDER.index)
        tiers = [t for (sid, _r), by_season in self.rarity.items() if sid == species_id
                 for t in by_season.values()]
        return min(tiers, key=TIER_ORDER.index) if tiers else "uncommon"

    # ---------- the Dex page ----------

    def view(self, catches: list[dict], region: str | None = None, group: str | None = None) -> dict:
        """Everything the Dex tab needs for one user and one pair of filters.

        catches: that user's rows from the catches table.
        region / group: None means "no filter". With no filters at all the
        result is every species, starting from number 1.
        """
        # Collection = which species appear in the catches. Keep each
        # species' first catch (for the date) and latest catch (for the photo).
        caught: dict[str, dict] = {}
        for c in catches:
            entry = caught.setdefault(c["species_id"], {"count": 0, "first": c["caught_at"]})
            entry["count"] += 1
            entry["photo_id"] = c["id"]

        def in_region(sid, code):
            return (sid, code) in self.rarity

        entries = []
        for sid, sp in self.species.items():
            if region and not in_region(sid, region):
                continue
            if group and sp["group"] != group:
                continue
            mine = caught.get(sid)
            entries.append({
                **sp,
                "tier": self.tier(sid, region),
                "caught": mine is not None,
                "catch_count": mine["count"] if mine else 0,
                "first_caught": mine["first"] if mine else None,
                "photo_id": mine["photo_id"] if mine else None,
            })

        # Counts for the region tabs respect the group filter, and counts for
        # the group buttons respect the region filter, so the numbers on the
        # buttons always match what tapping them would show.
        region_tabs = []
        for code in self.regions:
            ids = [sid for sid, sp in self.species.items()
                   if in_region(sid, code) and (not group or sp["group"] == group)]
            region_tabs.append({**region_info(code), "total": len(ids),
                                "caught": sum(1 for sid in ids if sid in caught)})

        group_tabs = {}
        for sid, sp in self.species.items():
            if region and not in_region(sid, region):
                continue
            tab = group_tabs.setdefault(sp["group"], {
                "key": sp["group"], "label": sp["group_label"],
                "icon": group_for_class(sp["animal_class"])[2], "total": 0, "caught": 0})
            tab["total"] += 1
            tab["caught"] += sid in caught
        ordered = [group_tabs[k] for k in GROUP_ORDER if k in group_tabs]
        ordered += [tab for key, tab in sorted(group_tabs.items()) if key not in GROUP_ORDER]

        return {
            "entries": entries,
            "regions": region_tabs,
            "groups": ordered,
            "total": len(self.species),
            "caught": sum(1 for sid in self.species if sid in caught),
        }

    def detail(self, species_id: str) -> dict | None:
        """One species page: where it lives and how rare it is each season."""
        sp = self.species.get(species_id)
        if sp is None:
            return None
        where = []
        for code in self.regions_of(species_id):
            by_season = self.rarity[(species_id, code)]
            where.append({**region_info(code),
                          "seasons": {s: by_season.get(s) for s in SEASONS}})
        return {**sp, "tier": self.tier(species_id), "regions": where}
