"""Tests for Person B's half: photo checks, location blurring, the Dex
(collection logic), the game rules, and the catch flow through the web API.

Everything runs on the made-up demo data and the fake ID function, with a
throwaway database in a temporary folder. No model, no network.
"""
import io
from datetime import date

import pytest
from PIL import Image, ImageFilter

from app import game, photo_check, store
from app.catch import CatchFlow
from app.config import DEMO, load_config
from app.dex import Dex
from app.privacy import BLUR_GRID_DEGREES, blur_location, location_to_store
from app.server import create_app
from contract.id_contract import Guess, IDResult

AUSTIN = (30.2672, -97.7431)


# ---------- helpers ----------

def sharp_image(size=(640, 480)) -> Image.Image:
    """Random speckle: lots of crisp detail, medium brightness. Random, so
    every call gives a different file (which the duplicate check needs)."""
    return Image.effect_noise(size, 70).convert("RGB")


def jpeg_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=92)
    return buffer.getvalue()


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.delenv("TEXDEX_SPECIES_CSV", raising=False)
    cfg = load_config()
    cfg.update(db_path=tmp_path / "test.sqlite3", photo_dir=tmp_path / "photos",
               use_fake_id=True, warm_up_model=False,
               # No ecoregion file in tests: region lookups return '' (unknown).
               regions_geojson=tmp_path / "none.geojson", outline_geojson=tmp_path / "none2.geojson")
    return cfg


@pytest.fixture
def dex():
    return Dex(DEMO / "species.csv", DEMO / "rarity.csv", DEMO / "species_groups.csv")


@pytest.fixture
def client(config):
    return create_app(config).test_client()


def sign_up(client, username="ranger_test"):
    # Made-up test account (CLAUDE.md rule 5: never real credentials).
    return client.post("/api/signup", json={
        "username": username, "password": "not-a-real-password", "display_name": "Test Ranger"})


def send_photo(client, image=None, lat=AUSTIN[0], lon=AUSTIN[1]):
    data = {"photo": (io.BytesIO(jpeg_bytes(image or sharp_image())), "photo.jpg")}
    if lat is not None:
        data.update(lat=str(lat), lon=str(lon))
    return client.post("/api/identify", data=data, content_type="multipart/form-data")


# ---------- photo checks ----------

def test_sharp_photo_passes():
    assert photo_check.check_photo(sharp_image()) is None


def test_blurry_photo_is_rejected_in_plain_language():
    blurry = sharp_image().filter(ImageFilter.GaussianBlur(6))
    problem = photo_check.check_photo(blurry)
    assert problem["code"] == "blurry"
    # The message must say what is wrong and what to do, with no jargon.
    assert "blurry" in problem["title"].lower()
    assert problem["message"] and problem["tip"]


def test_blur_lowers_the_sharpness_score():
    image = sharp_image()
    assert photo_check.sharpness(image.filter(ImageFilter.GaussianBlur(6))) < photo_check.sharpness(image)


def test_dark_bright_and_tiny_photos_are_rejected():
    assert photo_check.check_photo(Image.new("RGB", (640, 480), (5, 5, 5)))["code"] == "too_dark"
    assert photo_check.check_photo(Image.new("RGB", (640, 480), (250, 250, 250)))["code"] == "too_bright"
    assert photo_check.check_photo(sharp_image((120, 90)))["code"] == "too_small"


# ---------- location blurring ----------

def test_blur_moves_the_point_but_not_far():
    lat, lon = blur_location(26.1234, -97.5678)
    assert (lat, lon) != (26.1234, -97.5678)
    assert abs(lat - 26.1234) <= BLUR_GRID_DEGREES / 2
    assert abs(lon - -97.5678) <= BLUR_GRID_DEGREES / 2


def test_nearby_points_blur_to_the_same_place():
    # Many sightings of one animal must not average out to its true spot.
    assert blur_location(26.01, -97.51) == blur_location(26.24, -97.74) == (26.125, -97.625)


def test_only_protected_species_are_blurred():
    assert location_to_store(False, 26.1234, -97.5678) == (26.1234, -97.5678)
    assert location_to_store(True, 26.1234, -97.5678) == blur_location(26.1234, -97.5678)
    assert location_to_store(True, None, None) == (None, None)


# ---------- the Dex (collection logic) ----------

def test_no_filters_shows_every_species_from_the_beginning(dex):
    view = dex.view([])
    assert len(view["entries"]) == view["total"] == 84
    assert [e["number"] for e in view["entries"]] == list(range(1, 85))
    assert view["caught"] == 0 and not any(e["caught"] for e in view["entries"])


def test_region_filter_only_shows_species_that_live_there(dex):
    gulf = dex.view([], region="outside_land")
    names = {e["common_name"] for e in gulf["entries"]}
    assert "Bull Shark" in names and "Red Drum" in names
    assert "Mule Deer" not in names


def test_group_filter_and_fish_are_included(dex):
    view = dex.view([])
    keys = [g["key"] for g in view["groups"]]
    assert keys == ["birds", "mammals", "reptiles", "amphibians", "fish", "sharks_rays"]
    sharks = dex.view([], group="sharks_rays")
    assert {e["animal_class"] for e in sharks["entries"]} == {"Elasmobranchii"}
    # Both filters together.
    hill_birds = dex.view([], region="30", group="birds")
    assert hill_birds["entries"] and all(e["group"] == "birds" for e in hill_birds["entries"])


def test_button_counts_match_what_tapping_them_shows(dex):
    view = dex.view([], region="outside_land")
    for group in view["groups"]:
        assert group["total"] == len(dex.view([], region="outside_land", group=group["key"])["entries"])


def test_unknown_class_gets_its_own_group_instead_of_being_dropped(tmp_path):
    (tmp_path / "s.csv").write_text(
        "species_id,scientific_name,common_name,family,protected,venomous\n"
        "x1,Limulus polyphemus,Atlantic Horseshoe Crab,Limulidae,no,no\n")
    (tmp_path / "g.csv").write_text("species_id,animal_class,icon\nx1,Merostomata,\n")
    (tmp_path / "r.csv").write_text("species_id,region,season,rarity_tier\nx1,34,summer,rare\n")
    view = Dex(tmp_path / "s.csv", tmp_path / "r.csv", tmp_path / "g.csv").view([])
    assert view["groups"][0]["label"] == "Merostomata"
    assert view["entries"][0]["icon"] == "🐾"


def test_collection_is_computed_from_catches(dex):
    catches = [
        {"id": 1, "species_id": "sp_0007", "caught_at": "2026-11-01T10:00:00", "region": "30", "tier": "common"},
        {"id": 2, "species_id": "sp_0007", "caught_at": "2026-11-05T10:00:00", "region": "30", "tier": "common"},
    ]
    view = dex.view(catches)
    deer = next(e for e in view["entries"] if e["species_id"] == "sp_0007")
    assert view["caught"] == 1
    assert deer["caught"] and deer["catch_count"] == 2
    assert deer["first_caught"] == "2026-11-01T10:00:00"
    assert deer["photo_id"] == 2  # the latest photo is the one shown


def test_tier_falls_back_from_season_to_region_to_statewide(dex):
    assert dex.tier("sp_0005", "34", "winter") == "very_rare"   # whooping crane
    assert dex.tier("sp_0005", "34", "summer") == "very_rare"   # not there in summer: region's tier
    assert dex.tier("sp_0005", "25") == "very_rare"             # not in that region: statewide
    assert dex.tier("no_such_species") == "uncommon"


# ---------- game rules ----------

def test_xp_rewards_rarity_and_new_species():
    assert game.xp_for_catch("very_rare", True) > game.xp_for_catch("rare", True) > game.xp_for_catch("common", True)
    assert game.xp_for_catch("common", False) < game.xp_for_catch("common", True)
    assert game.xp_for_catch("common", False) == 8  # 20% of 40


def test_levels_follow_the_square_rule():
    assert game.level_for_xp(0)["level"] == 1
    assert game.level_for_xp(99)["level"] == 1
    assert game.level_for_xp(100)["level"] == 2
    assert game.level_for_xp(400)["level"] == 3
    info = game.level_for_xp(150)
    assert (info["xp_into_level"], info["xp_for_level"], info["xp_to_next"]) == (50, 300, 250)
    assert game.level_for_xp(10 ** 9)["title"] == game.TITLES[-1]  # never runs off the list


def test_badges_come_from_catches(dex):
    none = {b["key"]: b["earned"] for b in game.badges([], dex)}
    assert not any(none.values())
    assert "group_fish" in none and "group_sharks_rays" in none  # built from the data

    shark = [{"id": 1, "species_id": "sp_0078", "region": "outside_land", "tier": "uncommon",
              "caught_at": "2026-07-01T10:00:00"}]
    earned = {b["key"] for b in game.badges(shark, dex) if b["earned"]}
    assert earned == {"first_catch", "group_sharks_rays", "gulf"}


# ---------- accounts ----------

def test_api_needs_a_login(client):
    assert client.get("/api/dex").status_code == 401
    assert client.get("/api/profile").status_code == 401
    assert send_photo(client).status_code == 401


def test_sign_up_log_in_and_log_out(client):
    assert sign_up(client).status_code == 200
    assert client.get("/api/profile").get_json()["user"]["display_name"] == "Test Ranger"
    assert sign_up(client).status_code == 409  # username taken
    client.post("/api/logout")
    assert client.get("/api/profile").status_code == 401
    wrong = client.post("/api/login", json={"username": "ranger_test", "password": "wrong-password"})
    assert wrong.status_code == 401
    right = client.post("/api/login", json={"username": "ranger_test", "password": "not-a-real-password"})
    assert right.status_code == 200


def test_weak_sign_ups_are_refused(client):
    assert client.post("/api/signup", json={"username": "ab", "password": "long-enough-pw"}).status_code == 400
    assert client.post("/api/signup", json={"username": "good_name", "password": "short"}).status_code == 400


def test_passwords_are_not_stored_in_plain_text(config):
    store.init_db(config["db_path"])
    store.create_user(config["db_path"], "someone", "not-a-real-password", "Someone")
    with store.connect(config["db_path"]) as conn:
        row = dict(conn.execute("SELECT * FROM users").fetchone())
    assert "not-a-real-password" not in str(row)


# ---------- the catch flow ----------

def test_photo_to_confirm_to_dex(client):
    sign_up(client)
    found = send_photo(client)
    assert found.status_code == 200
    body = found.get_json()
    assert body["ok"] and len(body["guesses"]) == 3
    pick = body["guesses"][0]

    reveal = client.post("/api/catches", json={
        "pending_id": body["pending_id"], "species_id": pick["species_id"]}).get_json()
    assert reveal["is_new_species"] and reveal["xp"] > 0
    assert any(b["key"] == "first_catch" for b in reveal["new_badges"])

    dex_view = client.get("/api/dex").get_json()
    entry = next(e for e in dex_view["entries"] if e["species_id"] == pick["species_id"])
    assert dex_view["caught"] == 1 and entry["caught"]
    assert client.get(f"/api/photos/{entry['photo_id']}").status_code == 200
    profile = client.get("/api/profile").get_json()
    assert profile["stats"]["catches"] == 1 and profile["level"]["xp"] == reveal["xp"]


def test_bad_photos_get_a_plain_language_error(client):
    sign_up(client)
    blurry = send_photo(client, sharp_image().filter(ImageFilter.GaussianBlur(6)))
    assert blurry.status_code == 422
    error = blurry.get_json()["error"]
    assert error["code"] == "blurry" and error["title"] and error["message"] and error["tip"]

    not_photo = client.post("/api/identify", data={"photo": (io.BytesIO(b"hello"), "x.jpg")},
                            content_type="multipart/form-data")
    assert not_photo.get_json()["error"]["code"] == "not_a_photo"


def test_can_only_confirm_a_species_the_model_guessed(client):
    sign_up(client)
    body = send_photo(client).get_json()
    guessed = {g["species_id"] for g in body["guesses"]}
    other = next(s for s in ("sp_0078", "sp_0079") if s not in guessed)
    refused = client.post("/api/catches", json={"pending_id": body["pending_id"], "species_id": other})
    assert refused.status_code == 400
    assert client.get("/api/dex").get_json()["caught"] == 0


def test_a_pending_id_works_only_once(client):
    sign_up(client)
    body = send_photo(client).get_json()
    payload = {"pending_id": body["pending_id"], "species_id": body["guesses"][0]["species_id"]}
    assert client.post("/api/catches", json=payload).status_code == 200
    assert client.post("/api/catches", json=payload).status_code == 400


def test_same_photo_twice_is_a_duplicate(client):
    sign_up(client)
    image = sharp_image()
    body = send_photo(client, image).get_json()
    client.post("/api/catches", json={"pending_id": body["pending_id"],
                                      "species_id": body["guesses"][0]["species_id"]})
    again = send_photo(client, image)
    assert again.status_code == 422 and again.get_json()["error"]["code"] == "duplicate"


def test_catch_works_without_a_location(client):
    sign_up(client)
    body = send_photo(client, lat=None).get_json()
    assert body["ok"] and body["region"] is None


def test_other_users_cannot_load_your_photo(config):
    app = create_app(config)
    alice, bob = app.test_client(), app.test_client()
    sign_up(alice, "alice_test")
    sign_up(bob, "bob_test")
    body = send_photo(alice).get_json()
    reveal = alice.post("/api/catches", json={
        "pending_id": body["pending_id"], "species_id": body["guesses"][0]["species_id"]}).get_json()
    assert alice.get(f"/api/photos/{reveal['catch_id']}").status_code == 200
    assert bob.get(f"/api/photos/{reveal['catch_id']}").status_code == 404
    assert bob.get("/api/dex").get_json()["caught"] == 0  # collections are per user


def test_protected_species_location_is_blurred_before_saving(config, dex, tmp_path):
    store.init_db(config["db_path"])
    user = store.create_user(config["db_path"], "ocelot_fan", "not-a-real-password", "Fan")
    flow = CatchFlow(config, dex)
    exact = (26.1234, -97.5678)

    def catch(species_id):
        photo = tmp_path / f"{species_id}.jpg"
        sharp_image().save(photo)
        pending = store.add_pending(config["db_path"], user, str(photo), species_id, *exact,
                                    [{"species_id": species_id, "confidence": 0.9}])
        return flow.confirm_catch(user, pending, species_id)

    ocelot = catch("sp_0006")      # protected
    deer = catch("sp_0007")        # not protected
    rows = {c["species_id"]: c for c in store.catches_for_user(config["db_path"], user)}

    assert ocelot["location_blurred"] and not deer["location_blurred"]
    assert (rows["sp_0006"]["latitude"], rows["sp_0006"]["longitude"]) == blur_location(*exact)
    assert (rows["sp_0007"]["latitude"], rows["sp_0007"]["longitude"]) == exact
    # The exact point is nowhere in the database for the protected catch.
    with store.connect(config["db_path"]) as conn:
        everything = str([tuple(r) for r in conn.execute("SELECT * FROM catches WHERE species_id='sp_0006'")])
        leftover = conn.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
    assert "26.1234" not in everything and "97.5678" not in everything
    assert leftover == 0


def _fake_model(full_is_sure: bool, crop_is_sure: bool):
    """Stand-in for identify(): 'sure' or not depending on whether it is
    shown the whole photo or the cropped middle."""
    def identify(photo_path, latitude, longitude, obs_date):
        sure = crop_is_sure if str(photo_path).endswith("_crop.jpg") else full_is_sure
        top = 0.9 if sure else 0.2
        return IDResult(guesses=[Guess("sp_0007", top), Guess("sp_0001", 0.05), Guess("sp_0003", 0.01)],
                        not_sure=not sure)
    return identify


@pytest.mark.parametrize("crop_is_sure, expected", [(True, "too_far"), (False, "not_clear")])
def test_unsure_model_gives_the_right_reason(config, dex, monkeypatch, crop_is_sure, expected):
    config["use_fake_id"] = False  # behave as with the real model
    store.init_db(config["db_path"])
    user = store.create_user(config["db_path"], "far_away", "not-a-real-password", "Far")
    monkeypatch.setattr("app.catch.identify", _fake_model(False, crop_is_sure))

    result = CatchFlow(config, dex).start_identify(user, jpeg_bytes(sharp_image()), *AUSTIN)

    assert result["ok"] is False and result["error"]["code"] == expected
    # Nothing is kept from a rejected photo.
    assert not list((config["photo_dir"]).rglob("*.jpg"))


def test_sure_model_goes_through(config, dex, monkeypatch):
    config["use_fake_id"] = False
    store.init_db(config["db_path"])
    user = store.create_user(config["db_path"], "close_up", "not-a-real-password", "Close")
    monkeypatch.setattr("app.catch.identify", _fake_model(True, True))
    result = CatchFlow(config, dex).start_identify(user, jpeg_bytes(sharp_image()), *AUSTIN)
    assert result["ok"] and result["guesses"][0]["common_name"] == "White-tailed Deer"
