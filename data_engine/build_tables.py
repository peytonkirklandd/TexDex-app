"""Turn the GBIF counts into the tables the app and identify() read.

    python -m data_engine.build_tables

Inputs (written by fetch_gbif_counts.py):
  data/raw/gbif_counts.csv     region, month, species_key, sightings
  data/raw/gbif_species.json   names, family, order, class, IUCN code per species

Outputs (in data/processed/, never in git):
  species.csv         docs/interface.md species list
  rarity.csv          docs/interface.md rarity table
  month_region.csv    region, month, species_id, sightings  (the location boost)
  species_groups.csv  species_id, animal_class, icon        (Dex filters and sketches)

Every species that is left out is counted in the printed summary, with the reason.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from .fetch_gbif_counts import MIN_SIGHTINGS, RAW
from .rarity import build_rarity_from_month_table

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"

# GBIF files ray-finned fishes straight under "animals with a backbone" with
# no class at all. Every other backboned animal has one, so "no class" here
# means a ray-finned fish, and we give it its usual name.
CLASS_WHEN_BLANK = "Actinopterygii"

# Classes with a backbone-like rod but that nobody would call wildlife to
# photograph (sea squirts, salps, lancelets). Everything else is kept.
NOT_VERTEBRATES = {"Ascidiacea", "Thaliacea", "Appendicularia", "Leptocardii"}

# People, pets and farm animals turn up in the records. Not wildlife.
NOT_WILD = {"Homo sapiens", "Felis catus", "Canis familiaris", "Bos taurus", "Equus caballus",
            "Ovis aries", "Capra hircus"}

# Order the species list by kind of animal, then most-reported first.
CLASS_ORDER = ["Aves", "Mammalia", "Squamata", "Testudines", "Crocodylia", "Amphibia",
               "Actinopterygii", "Petromyzonti", "Elasmobranchii", "Holocephali"]

# PLACEHOLDER for the protected flag until the TPWD list is loaded: globally
# threatened on the IUCN Red List (Vulnerable, Endangered, Critically
# Endangered), plus Texas species we know are state or federally listed.
# Leaning towards "yes" is the safe mistake: it only blurs a map pin.
IUCN_THREATENED = {"VU", "EN", "CR"}
KNOWN_PROTECTED = {
    "Phrynosoma cornutum", "Grus americana", "Leopardus pardalis", "Setophaga chrysoparia",
    "Tympanuchus pallidicinctus", "Ursus americanus", "Lepidochelys kempii", "Gopherus berlandieri",
    "Anaxyrus houstonensis", "Eurycea sosorum", "Eurycea rathbuni", "Cyprinodon bovinus",
    "Pristis pectinata", "Charadrius melodus", "Falco femoralis", "Trichechus manatus",
}
VENOMOUS_FAMILIES = {"Viperidae", "Elapidae", "Helodermatidae"}

# Which little sketch stands for a species in the Dex: first match wins,
# looked up by family, then order, then class.
ICONS = {
    # birds
    "Accipitriformes": "🦅", "Falconiformes": "🦅", "Cathartiformes": "🦅", "Strigiformes": "🦉",
    "Anseriformes": "🦆", "Podicipediformes": "🦆", "Gaviiformes": "🦆", "Suliformes": "🦆",
    "Pelecaniformes": "🦩", "Gruiformes": "🦩", "Ciconiiformes": "🦩", "Phoenicopteriformes": "🦩",
    "Galliformes": "🦃", "Aves": "🐦",
    # mammals
    "Felidae": "🐆", "Canidae": "🐺", "Ursidae": "🐻", "Mustelidae": "🦦", "Procyonidae": "🦝",
    "Suidae": "🐗", "Tayassuidae": "🐗", "Dasypodidae": "🦔", "Didelphidae": "🐀",
    "Chiroptera": "🦇", "Lagomorpha": "🐇", "Rodentia": "🐿️", "Cetacea": "🐬", "Sirenia": "🐬",
    "Artiodactyla": "🦌", "Mammalia": "🦌",
    # reptiles: lizard families are the exception, so snakes are the default
    "Phrynosomatidae": "🦎", "Dactyloidae": "🦎", "Teiidae": "🦎", "Scincidae": "🦎",
    "Gekkonidae": "🦎", "Crotaphytidae": "🦎", "Anguidae": "🦎", "Iguanidae": "🦎",
    "Eublepharidae": "🦎", "Sphaerodactylidae": "🦎", "Polychrotidae": "🦎", "Helodermatidae": "🦎",
    "Xantusiidae": "🦎", "Agamidae": "🦎", "Chamaeleonidae": "🦎", "Lacertidae": "🦎",
    "Squamata": "🐍", "Testudines": "🐢", "Crocodylia": "🐊",
    # amphibians
    "Caudata": "🦎", "Amphibia": "🐸",
    # fish
    "Myliobatiformes": "ray", "Rajiformes": "ray", "Rhinopristiformes": "ray", "Torpediniformes": "ray",
    "Elasmobranchii": "🦈", "Actinopterygii": "🐟",
}


def icon_for(family: str, order: str, animal_class: str) -> str:
    return ICONS.get(family) or ICONS.get(order) or ICONS.get(animal_class) or "🐾"


def tidy_common_name(common: str, scientific: str) -> str:
    """GBIF's English names are untidy: "Bullfrog, North American bullfrog",
    "Texas spiny lizard", or just the Latin second word ("Scutulatus").
    Keep the first name offered, capitalise each word, and fall back to the
    scientific name when there is no real English name."""
    common = common.split(",")[0].strip()
    if not common or common.lower() == scientific.split()[-1].lower():
        return scientific
    return " ".join(word[:1].upper() + word[1:] for word in common.split())


def build_tables(raw_dir=RAW, out_dir=PROCESSED) -> dict:
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    details = json.loads((raw_dir / "gbif_species.json").read_text(encoding="utf-8"))
    counts = defaultdict(int)  # (region, month, species_key) -> sightings
    totals = defaultdict(int)  # species_key -> sightings anywhere, any month
    with open(raw_dir / "gbif_counts.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n = int(row["sightings"])
            counts[(row["region"], int(row["month"]), row["species_key"])] += n
            totals[row["species_key"]] += n

    left_out = defaultdict(int)
    species = []
    for key, total in totals.items():
        if total < MIN_SIGHTINGS:
            left_out[f"fewer_than_{MIN_SIGHTINGS}_sightings"] += 1
            continue
        d = details.get(key)
        if d is None:
            left_out["no_details_from_gbif"] += 1
            continue
        animal_class = d["class"] or CLASS_WHEN_BLANK
        if animal_class in NOT_VERTEBRATES:
            left_out["not_a_vertebrate"] += 1
            continue
        if d["scientific_name"] in NOT_WILD:
            left_out["people_pets_farm_animals"] += 1
            continue
        if len(d["scientific_name"].split()) != 2:
            left_out["not_a_plain_species_name"] += 1  # hybrids, forms, unnamed
            continue
        common = tidy_common_name(d["common_name"], d["scientific_name"])
        species.append({
            "key": key, "species_id": f"gbif_{key}", "total": total, "animal_class": animal_class,
            "scientific_name": d["scientific_name"], "common_name": common, "family": d["family"],
            "has_common_name": common != d["scientific_name"],
            "protected": "yes" if (d["iucn"] in IUCN_THREATENED or d["scientific_name"] in KNOWN_PROTECTED) else "no",
            "venomous": "yes" if d["family"] in VENOMOUS_FAMILIES else "no",
            "icon": icon_for(d["family"], d["order"], animal_class),
        })

    def position(sp):
        c = sp["animal_class"]
        return (CLASS_ORDER.index(c) if c in CLASS_ORDER else len(CLASS_ORDER), c, -sp["total"])
    species.sort(key=position)

    out_dir.mkdir(parents=True, exist_ok=True)

    def write(name, header, rows):
        with open(out_dir / name, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

    write("species.csv", ["species_id", "scientific_name", "common_name", "family", "protected", "venomous"],
          [[s[c] for c in ("species_id", "scientific_name", "common_name", "family", "protected", "venomous")]
           for s in species])
    write("species_groups.csv", ["species_id", "animal_class", "icon"],
          [[s["species_id"], s["animal_class"], s["icon"]] for s in species])
    id_of = {s["key"]: s["species_id"] for s in species}
    write("month_region.csv", ["region", "month", "species_id", "sightings"],
          [[region, month, id_of[key], n] for (region, month, key), n in sorted(counts.items()) if key in id_of])

    # Rarity compares each animal with its own kind (see rarity.py for why).
    class_of = {s["species_id"]: s["animal_class"] for s in species}
    rarity = build_rarity_from_month_table(out_dir / "month_region.csv", out_dir / "rarity.csv", class_of)

    per_class = defaultdict(int)
    for s in species:
        per_class[s["animal_class"]] += 1
    return {
        "species": len(species), "by_class": dict(per_class), "left_out": dict(left_out),
        "protected": sum(s["protected"] == "yes" for s in species),
        "venomous": sum(s["venomous"] == "yes" for s in species),
        "without_english_name": sum(not s["has_common_name"] for s in species),
        "rarity": rarity,
    }


if __name__ == "__main__":
    for name, value in build_tables().items():
        print(f"{name}: {value}")
