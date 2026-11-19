"""Tests for app/supabase_store.py.

The first group runs offline: Supabase's answers are faked, so they check
our logic (token refresh, pending IDs) without a network.

The last test talks to the real Supabase project and is skipped unless you
ask for it, because it creates test accounts there:
    TEXDEX_TEST_SUPABASE=1 python -m pytest tests/test_supabase_store.py
It is the "test sign-up from a script" from the Person B brief.
"""
from __future__ import annotations

import io
import os
import secrets

import pytest
from flask import Flask, g
from PIL import Image

from app import supabase_store as sb
from app.config import load_config
from app.server import create_app

DB = sb.SupabaseDB("https://example.supabase.co", "sb_publishable_test")


class FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code, self._body, self.text = status_code, body or {}, str(body)

    def json(self):
        return self._body


def test_usernames_become_addresses_that_can_never_be_real():
    # .example is reserved by the internet's rules, so no email ever goes anywhere.
    assert sb.email_for("trail_walker") == "trail_walker@texdex.example"


def test_a_valid_token_is_used_as_is(monkeypatch):
    monkeypatch.setattr(sb.requests, "get", lambda *a, **k: FakeResponse(200, {"id": "user-1"}))
    who = sb.who_is(DB, {sb.COOKIE: "good-token"})
    assert who == {"user_id": "user-1", "token": "good-token", "cookies": {}}


def test_an_expired_token_is_swapped_using_the_refresh_token(monkeypatch):
    monkeypatch.setattr(sb.requests, "get", lambda *a, **k: FakeResponse(401))
    sent = {}

    def fake_post(url, params=None, json=None, **kwargs):
        sent.update(url=url, params=params, json=json)
        return FakeResponse(200, {"access_token": "new-access", "refresh_token": "new-refresh",
                                  "user": {"id": "user-1"}})
    monkeypatch.setattr(sb.requests, "post", fake_post)

    who = sb.who_is(DB, {sb.COOKIE: "old", sb.REFRESH_COOKIE: "old-refresh"})
    assert sent["params"] == {"grant_type": "refresh_token"} and sent["json"] == {"refresh_token": "old-refresh"}
    assert who["user_id"] == "user-1" and who["token"] == "new-access"
    # The new pair goes back to the browser.
    assert who["cookies"] == {sb.COOKIE: "new-access", sb.REFRESH_COOKIE: "new-refresh"}


def test_no_valid_token_means_not_logged_in(monkeypatch):
    monkeypatch.setattr(sb.requests, "get", lambda *a, **k: FakeResponse(401))
    monkeypatch.setattr(sb.requests, "post", lambda *a, **k: FakeResponse(400))
    assert sb.who_is(DB, {sb.COOKIE: "old", sb.REFRESH_COOKIE: "expired"}) is None
    assert sb.who_is(DB, {}) is None


def test_pending_ids_are_one_use_and_only_for_their_owner():
    pending = sb.add_pending(DB, "alice", "a.jpg", "hash", 30.1, -97.1, [])
    assert sb.take_pending(DB, "bob", pending) is None           # not yours
    assert sb.take_pending(DB, "alice", pending)["photo_file"] == "a.jpg"
    assert sb.take_pending(DB, "alice", pending) is None         # already used
    sb.add_pending(DB, "carol", "c1.jpg", "h1", None, None, [])
    assert sb.clear_pending(DB, "carol") == ["c1.jpg"]


def test_data_calls_need_a_logged_in_user():
    with Flask(__name__).app_context():
        g.access_token = None
        with pytest.raises(sb.SupabaseError):
            sb.catches_for_user(DB, "anyone")


# ---------- against the real Supabase project (opt-in) ----------

live = pytest.mark.skipif(os.getenv("TEXDEX_TEST_SUPABASE") != "1",
                          reason="set TEXDEX_TEST_SUPABASE=1 to test against the real Supabase project")


@live
def test_accounts_and_catches_survive_a_restart_and_stay_private(tmp_path):
    config = load_config()
    assert config["supabase_url"] and config["supabase_key"], "put the Supabase keys in .env"
    config.update(use_fake_id=True, warm_up_model=False, photo_dir=tmp_path / "photos",
                  regions_geojson=tmp_path / "none.geojson", outline_geojson=tmp_path / "none.geojson")
    tag = secrets.token_hex(3)
    alice_name, bob_name, password = f"test_a_{tag}", f"test_b_{tag}", "made-up-test-pw"

    app = create_app(config)
    alice, bob = app.test_client(), app.test_client()
    assert alice.post("/api/signup", json={"username": alice_name, "password": password}).status_code == 200
    assert bob.post("/api/signup", json={"username": bob_name, "password": password}).status_code == 200
    # Taken usernames are refused.
    assert bob.post("/api/signup", json={"username": alice_name, "password": password}).status_code == 409

    photo = io.BytesIO()
    Image.effect_noise((640, 480), 70).convert("RGB").save(photo, "JPEG")
    body = alice.post("/api/identify", data={"photo": (io.BytesIO(photo.getvalue()), "p.jpg"),
                                             "lat": "30.2672", "lon": "-97.7431"},
                      content_type="multipart/form-data").get_json()
    assert body["ok"], body
    reveal = alice.post("/api/catches", json={"pending_id": body["pending_id"],
                                              "species_id": body["guesses"][0]["species_id"]}).get_json()
    catch_id = reveal["catch_id"]

    # A brand-new server (as after a restart) still knows Alice and her catch.
    restarted = create_app(config).test_client()
    assert restarted.post("/api/login", json={"username": alice_name, "password": password}).status_code == 200
    assert restarted.get("/api/dex").get_json()["caught"] == 1
    assert restarted.get(f"/api/photos/{catch_id}").status_code == 200

    # Bob can't see Alice's photo or catch: row-level security, not just our code.
    assert bob.get(f"/api/photos/{catch_id}").status_code == 404
    assert bob.get("/api/dex").get_json()["caught"] == 0
