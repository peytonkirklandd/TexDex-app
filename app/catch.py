"""The catch flow: photo -> quality check -> ID -> user confirms -> saved.

Two steps, on purpose:
  1. start_identify(): check the photo, ask identify() for its 3 guesses, and
     park the result as "pending".
  2. confirm_catch(): the user picks one of those 3 guesses and it is saved.
Why two steps: the model can be wrong, so a person confirms before anything
goes in the collection, and they can only pick from what the model offered
(nobody can claim an ocelot from a photo of a house cat by editing the request).

This file never touches model or scoring logic. It only calls
contract.identify(), as the Person B brief requires.
"""
from __future__ import annotations

import hashlib
import io
import secrets
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from contract import identify
from data_engine.rarity import season_of
from data_engine.regions import load_regions, region_for_point

from . import game, photo_check, store
from .privacy import location_to_store

MAX_PHOTO_SIDE = 1280  # saved photos are shrunk to this; plenty for the model and the Dex

# identify() needs a latitude and longitude. When the phone gives us none we
# pass this point, which is outside the Texas box, so identify() applies no
# location boost instead of boosting for the wrong place.
NO_LOCATION = (0.0, 0.0)


class CatchFlow:
    def __init__(self, config: dict, dex, storage=store, db=None):
        """storage is the store.py module (SQLite) or supabase_store.py; both
        have the same functions. db is what those functions take first."""
        self.config = config
        self.dex = dex
        self.store = storage
        self.db = db if db is not None else config["db_path"]
        self.photo_dir = Path(config["photo_dir"])
        self._regions = None

    # ---------- helpers ----------

    def region_at(self, latitude, longitude) -> str:
        """Region code for a point, or '' when unknown (no GPS, outside
        Texas, or the ecoregion file has not been downloaded)."""
        if latitude is None or longitude is None:
            return ""
        path = Path(self.config["regions_geojson"])
        if not path.is_file():
            return ""
        if self._regions is None:
            self._regions = load_regions(path)
        return region_for_point(latitude, longitude, self._regions) or ""

    def _guess_cards(self, result, region: str, today: date) -> list[dict]:
        cards = []
        for guess in result.guesses:
            sp = self.dex.species.get(guess.species_id)
            if sp is None:
                continue  # the model knows a species the Dex list does not; skip it
            cards.append({
                **sp,
                "confidence": round(guess.confidence, 4),
                "tier": self.dex.tier(guess.species_id, region or None, season_of(today)),
            })
        return cards

    # ---------- step 1 ----------

    def start_identify(self, user_id: int, photo_bytes: bytes, latitude, longitude) -> dict:
        """Returns {"ok": True, pending_id, guesses, region} or {"ok": False, "error": {...}}."""
        try:
            image = Image.open(io.BytesIO(photo_bytes))
            # Phones store "which way up" as a note in the file instead of
            # rotating the pixels. Apply it so the model sees it upright.
            image = ImageOps.exif_transpose(image).convert("RGB")
        except (UnidentifiedImageError, OSError):
            return {"ok": False, "error": photo_check.NOT_A_PHOTO}

        # Duplicate check: the hash is a fingerprint of the exact file. The
        # same file always gives the same fingerprint.
        photo_hash = hashlib.sha256(photo_bytes).hexdigest()
        if self.store.photo_already_used(self.db, user_id, photo_hash):
            return {"ok": False, "error": photo_check.DUPLICATE}

        problem = photo_check.check_photo(image)
        if problem:
            return {"ok": False, "error": problem}

        # Throw away any earlier photo this user took but never confirmed.
        for old_file in self.store.clear_pending(self.db, user_id):
            Path(old_file).unlink(missing_ok=True)

        image.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))
        folder = self.photo_dir / str(user_id)
        folder.mkdir(parents=True, exist_ok=True)
        photo_file = folder / f"{secrets.token_hex(8)}.jpg"
        image.save(photo_file, "JPEG", quality=88)

        today = date.today()
        lat, lon = (latitude, longitude) if latitude is not None and longitude is not None else NO_LOCATION
        result = identify(str(photo_file), lat, lon, today)

        # The fake ID function's confidences are random, so its not_sure flag
        # is only enforced with the real model.
        if result.not_sure and not self.config["use_fake_id"]:
            error = self._why_not_sure(image, photo_file, lat, lon, today)
            photo_file.unlink(missing_ok=True)
            return {"ok": False, "error": error}

        region = self.region_at(latitude, longitude)
        guesses = self._guess_cards(result, region, today)
        if not guesses:
            photo_file.unlink(missing_ok=True)
            return {"ok": False, "error": photo_check.NOT_CLEAR}
        pending_id = self.store.add_pending(
            self.db, user_id, str(photo_file), photo_hash, latitude, longitude,
            [{"species_id": g["species_id"], "confidence": g["confidence"]} for g in guesses])
        return {"ok": True, "pending_id": pending_id, "guesses": guesses,
                "region": self.dex_region(region)}

    def _why_not_sure(self, image, photo_file: Path, lat, lon, today) -> dict:
        """The model was not sure. Work out which plain-language reason to give.

        Test: cut out the middle half of the photo and ask again. If the
        model IS sure about the close-up, the animal was there but too small
        in the frame, so the fix is "get closer". If it is still unsure, we
        simply can't make out an animal.
        """
        width, height = image.size
        middle = image.crop((width // 4, height // 4, width * 3 // 4, height * 3 // 4))
        crop_file = photo_file.with_name(photo_file.stem + "_crop.jpg")
        middle.save(crop_file, "JPEG", quality=88)
        try:
            closer = identify(str(crop_file), lat, lon, today)
        finally:
            crop_file.unlink(missing_ok=True)
        return photo_check.NOT_CLEAR if closer.not_sure else photo_check.TOO_FAR

    def dex_region(self, code: str) -> dict | None:
        from .dex import region_info
        return region_info(code) if code else None

    # ---------- step 2 ----------

    def confirm_catch(self, user_id: int, pending_id: str, species_id: str) -> dict | None:
        """Save the catch. Returns the "reveal" data for the celebration
        screen, or None if the pending ID is unknown or the species was not
        one of the model's guesses."""
        pending = self.store.take_pending(self.db, user_id, pending_id)
        if pending is None:
            return None
        confidence = {g["species_id"]: g["confidence"] for g in pending["guesses"]}.get(species_id)
        sp = self.dex.species.get(species_id)
        if confidence is None or sp is None:
            Path(pending["photo_file"]).unlink(missing_ok=True)
            return None

        before = self.store.catches_for_user(self.db, user_id)
        badges_before = {b["key"] for b in game.badges(before, self.dex) if b["earned"]}
        xp_before = sum(c["xp"] for c in before)
        is_new = all(c["species_id"] != species_id for c in before)

        # The region comes from the TRUE location (so rarity and the Dex are
        # right), but only the blurred location is saved for protected species.
        region = self.region_at(pending["latitude"], pending["longitude"])
        tier = self.dex.tier(species_id, region or None, season_of(date.today()))
        xp = game.xp_for_catch(tier, is_new)
        save_lat, save_lon = location_to_store(sp["protected"], pending["latitude"], pending["longitude"])

        catch_id = self.store.add_catch(
            self.db, user_id=user_id, species_id=species_id, photo_file=pending["photo_file"],
            photo_hash=pending["photo_hash"], latitude=save_lat, longitude=save_lon,
            region=region, tier=tier, confidence=confidence, xp=xp)

        after = self.store.catches_for_user(self.db, user_id)
        new_badges = [b for b in game.badges(after, self.dex)
                      if b["earned"] and b["key"] not in badges_before]
        level_before = game.level_for_xp(xp_before)
        level_after = game.level_for_xp(xp_before + xp)
        return {
            "catch_id": catch_id,
            "species": {**sp, "tier": tier},
            "is_new_species": is_new,
            "xp": xp,
            "level": level_after,
            "leveled_up": level_after["level"] > level_before["level"],
            "new_badges": new_badges,
            "region": self.dex_region(region),
            "location_blurred": sp["protected"] and save_lat is not None,
            "species_count": len({c["species_id"] for c in after}),
        }
