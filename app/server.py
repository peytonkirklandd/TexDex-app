"""The web server (Flask). Serves the one-page app and its JSON API.

    python -m app              demo mode: fake ID function (instant, no model)
    python -m app --bioclip    real BioCLIP 2 identification

Every /api route except sign-up, log-in and status needs a logged-in user,
and every query is filtered by that user's id. With Supabase, the database
also enforces that itself (row-level security, app/supabase/schema.sql).

Storage: Supabase when SUPABASE_URL and SUPABASE_ANON_KEY are set (accounts
and catches survive restarts), otherwise a local SQLite file (tests, offline).
"""
from __future__ import annotations

import io
import re
import tempfile
import threading
from datetime import date
from functools import wraps
from pathlib import Path

import requests
from flask import Flask, g, jsonify, request, send_file, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from data_engine.rarity import season_of

from . import game, store as sqlite_store, supabase_store
from .catch import CatchFlow
from .config import load_config, share_files_with_identify
from .dex import TIER_LABELS, Dex
from .privacy import location_for_shared_map
from .texas_map import build_map, project_point

STATIC = Path(__file__).resolve().parent / "static"
COOKIES = (supabase_store.COOKIE, supabase_store.REFRESH_COOKIE)  # cleared on log-out
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # stay logged in for 30 days
USERNAME_RULE = re.compile(r"^[a-z0-9_]{3,20}$")
AVATARS = ["🤠", "🦎", "🦅", "🦌", "🐍", "🐢", "🦇", "🐸", "🦈", "🌵", "⭐", "🌻"]


def create_app(config: dict | None = None) -> Flask:
    config = config or load_config()
    share_files_with_identify(config)
    # Pick the storage once. Both modules have the same functions, and `db`
    # is what each of them takes first (a Supabase address, or a file path).
    if config.get("supabase_url") and config.get("supabase_key"):
        store = supabase_store
        db = supabase_store.SupabaseDB(config["supabase_url"].rstrip("/"), config["supabase_key"])
    else:
        store = sqlite_store
        db = config["db_path"]
    store.init_db(db)

    app = Flask(__name__, static_folder=None)
    # On Google Cloud Run the app sits behind Google's https front door,
    # which passes the original "https" along in a header. ProxyFix reads it,
    # so request.is_secure is True there and cookies get the secure flag.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
    app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # refuse uploads over 15 MB
    dex = Dex(config["species_csv"], config["rarity_csv"], config["groups_csv"])
    flow = CatchFlow(config, dex, store, db)
    state = {"model_ready": config["use_fake_id"], "map": None}

    if not config["use_fake_id"] and config.get("warm_up_model"):
        # BioCLIP takes about a minute to load the first time it is used.
        # Do that in the background at start-up so the first real catch is fast.
        def warm_up():
            from PIL import Image

            from contract import identify
            with tempfile.TemporaryDirectory() as folder:
                tiny = Path(folder) / "warmup.jpg"
                Image.new("RGB", (224, 224), (90, 120, 80)).save(tiny)
                identify(str(tiny), 0.0, 0.0, date.today())
            state["model_ready"] = True

        threading.Thread(target=warm_up, daemon=True).start()

    # ---------- who is asking? ----------

    @app.before_request
    def load_user():
        g.user_id = g.access_token = None
        g.new_cookies = {}
        if not request.path.startswith("/api/"):
            return  # pages and static files don't need to know who is asking
        who = store.who_is(db, request.cookies)
        if who:
            g.user_id, g.access_token, g.new_cookies = who["user_id"], who["token"], who["cookies"]

    def set_cookies(response, cookies: dict):
        # httponly: page scripts cannot read the cookie. samesite: other
        # websites cannot make requests with it. secure: only sent over https
        # (left off on plain-http localhost so local testing still works).
        for name, value in cookies.items():
            response.set_cookie(name, value, httponly=True, samesite="Lax",
                                secure=request.is_secure, max_age=COOKIE_MAX_AGE)
        return response

    @app.after_request
    def refresh_cookies(response):
        # Supabase access tokens last an hour; who_is() swaps an expired one
        # for a fresh one, and this hands the fresh one back to the browser.
        return set_cookies(response, g.get("new_cookies") or {})

    def login_required(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.user_id is None:
                return jsonify(error="Please log in first."), 401
            return view(*args, **kwargs)
        return wrapper

    def start_session(session: dict):
        return set_cookies(jsonify(ok=True), session["cookies"])

    # ---------- pages ----------

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name):
        return send_from_directory(STATIC, name)

    # ---------- accounts ----------

    @app.post("/api/signup")
    def signup():
        body = request.get_json(silent=True) or {}
        username = str(body.get("username", "")).strip().lower()
        password = str(body.get("password", ""))
        display_name = str(body.get("display_name", "")).strip()[:30] or username
        if not USERNAME_RULE.match(username):
            return jsonify(error="Usernames are 3 to 20 letters, numbers or underscores."), 400
        if len(password) < 8:
            return jsonify(error="Passwords need at least 8 characters."), 400
        session = store.sign_up(db, username, password, display_name)
        if session is None:
            return jsonify(error="That username is taken. Try another."), 409
        return start_session(session)

    @app.post("/api/login")
    def login():
        body = request.get_json(silent=True) or {}
        session = store.log_in(db, str(body.get("username", "")).strip().lower(),
                               str(body.get("password", "")))
        if session is None:
            # Same message for "no such user" and "wrong password", so the
            # form cannot be used to find out which usernames exist.
            return jsonify(error="That username and password don't match."), 401
        return start_session(session)

    @app.post("/api/logout")
    def logout():
        store.log_out(db, request.cookies)
        g.new_cookies = {}  # don't hand back a refreshed token on the way out
        response = jsonify(ok=True)
        for name in COOKIES:
            response.delete_cookie(name)
        return response

    @app.get("/api/status")
    def status():
        return jsonify(
            logged_in=g.user_id is not None,
            model_ready=state["model_ready"],
            fake_id=config["use_fake_id"],
            demo_data=config["demo_data"],
        )

    # ---------- profile ----------

    def profile_payload(user_id: int) -> dict:
        user = store.get_user(db, user_id)
        catches = store.catches_for_user(db, user_id)
        recent = []
        for c in reversed(catches[-12:]):
            sp = dex.species.get(c["species_id"])
            if sp:
                recent.append({"catch_id": c["id"], "common_name": sp["common_name"],
                               "tier": c["tier"], "caught_at": c["caught_at"], "xp": c["xp"]})
        view = dex.view(catches)
        return {
            "user": user,
            "level": game.level_for_xp(sum(c["xp"] for c in catches)),
            "stats": game.profile_stats(catches, dex),
            "badges": game.badges(catches, dex),
            "groups": view["groups"],
            "recent": recent,
            "avatars": AVATARS,
            "tier_labels": TIER_LABELS,
        }

    @app.get("/api/profile")
    @login_required
    def profile():
        return jsonify(profile_payload(g.user_id))

    @app.post("/api/profile")
    @login_required
    def edit_profile():
        body = request.get_json(silent=True) or {}
        user = store.get_user(db, g.user_id)
        display_name = str(body.get("display_name", user["display_name"])).strip()[:30]
        avatar = body.get("avatar", user["avatar"])
        if not display_name or avatar not in AVATARS:
            return jsonify(error="Pick a name and one of the avatars."), 400
        store.update_profile(db, g.user_id, display_name, avatar)
        return jsonify(profile_payload(g.user_id))

    # ---------- the Dex ----------

    @app.get("/api/dex")
    @login_required
    def dex_view():
        region = request.args.get("region") or None
        group = request.args.get("group") or None
        # season=now means "the season it is today", worked out here on the
        # server so every user gets the same season boundaries as rarity.
        season = request.args.get("season") or None
        if season == "now":
            season = season_of(date.today())
        return jsonify(dex.view(store.catches_for_user(db, g.user_id), region, group, season))

    @app.get("/api/species/<species_id>")
    @login_required
    def species_detail(species_id):
        detail = dex.detail(species_id)
        if detail is None:
            return jsonify(error="No such species."), 404
        mine = [c for c in store.catches_for_user(db, g.user_id) if c["species_id"] == species_id]
        detail["catches"] = [{"catch_id": c["id"], "caught_at": c["caught_at"],
                              "region": flow.dex_region(c["region"])} for c in reversed(mine)]
        return jsonify(detail)

    @app.get("/api/map")
    @login_required
    def texas_map():
        """The Texas drawing plus a pin for every catch that has a location
        (the shared map). Where a pin goes comes from the phone's GPS reading
        at the moment the photo was taken, saved with the catch."""
        if state["map"] is None:
            state["map"] = build_map(config["regions_geojson"], config["outline_geojson"])
        data = state["map"]
        if not data["available"]:
            return jsonify(available=False)
        pins = []
        for point in store.all_catch_points(db):
            sp = dex.species.get(point["species_id"])
            if sp is None:
                continue
            # Protected species were blurred before saving; here every point
            # is also rounded to about 1 km for the user's own privacy.
            lat, lon = location_for_shared_map(point["latitude"], point["longitude"])
            x, y = project_point(data, lat, lon)
            mine = point["user_id"] == g.user_id
            pins.append({
                "x": x, "y": y, "tier": point["tier"], "mine": mine,
                "region": point["region"],
                "species_id": sp["species_id"], "common_name": sp["common_name"], "icon": sp["icon"],
                # True = this pin only marks a rough 25 km area (protected species).
                "approximate": sp["protected"],
                "date": point["caught_at"][:10],
                # Other people's pins carry no user id and no photo, only
                # what was seen and roughly where.
                "catch_id": point["id"] if mine else None,
            })
        return jsonify(available=True, width=data["width"], height=data["height"],
                       outline=data["outline"], regions=data["regions"], pins=pins)

    @app.get("/api/region")
    @login_required
    def region_lookup():
        """Which region is this point in? Used for the camera screen's label."""
        try:
            lat, lon = float(request.args["lat"]), float(request.args["lon"])
        except (KeyError, ValueError):
            return jsonify(region=None)
        return jsonify(region=flow.dex_region(flow.region_at(lat, lon)))

    # ---------- catching ----------

    def _float_or_none(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @app.post("/api/identify")
    @login_required
    def identify_photo():
        photo = request.files.get("photo")
        if photo is None:
            return jsonify(error="No photo was sent."), 400
        result = flow.start_identify(
            g.user_id, photo.read(),
            _float_or_none(request.form.get("lat")), _float_or_none(request.form.get("lon")))
        # 422 = "we understood the request but can't use this photo"
        return jsonify(result), (200 if result["ok"] else 422)

    @app.post("/api/catches")
    @login_required
    def confirm():
        body = request.get_json(silent=True) or {}
        reveal = flow.confirm_catch(g.user_id, str(body.get("pending_id", "")),
                                    str(body.get("species_id", "")))
        if reveal is None:
            return jsonify(error="That catch has expired. Please take the photo again."), 400
        return jsonify(reveal)

    @app.get("/api/photos/<int:catch_id>")
    @login_required
    def photo(catch_id):
        catch = store.get_catch(db, catch_id)
        # Only the owner can load a photo. Same answer for "not yours" and
        # "does not exist", so ids cannot be probed.
        photo_bytes = None
        if catch is not None and catch["user_id"] == g.user_id:
            photo_bytes = store.read_photo(db, catch)
        if photo_bytes is None:
            return jsonify(error="Photo not found."), 404
        return send_file(io.BytesIO(photo_bytes), mimetype="image/jpeg", max_age=3600)

    @app.errorhandler(413)
    def too_big(_error):
        return jsonify(ok=False, error={
            "code": "too_big", "title": "That file is too big",
            "message": "Photos need to be under 15 MB.",
            "tip": "Take the photo again with the camera."}), 413

    @app.errorhandler(supabase_store.SupabaseError)
    @app.errorhandler(requests.RequestException)
    def storage_down(error):
        # Supabase was unreachable or refused. Log the detail for us (it never
        # contains a location), and give the user a plain message.
        app.logger.error("Supabase problem: %s", error)
        return jsonify(ok=False, error={
            "code": "storage", "title": "Your journal couldn't be reached",
            "message": "TexDex couldn't save or load your journal just now.",
            "tip": "Check your signal and try again in a moment."}), 503

    return app
