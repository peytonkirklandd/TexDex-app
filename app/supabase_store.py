"""Supabase storage: the same functions as store.py, but the data lives in
Supabase, so accounts and catches survive the web server restarting.

Supabase gives us three things over plain HTTP, and this file only talks
to them with `requests`:
  - Auth     (/auth/v1)      sign-up, log-in, "who owns this token?"
  - Database (/rest/v1)      the tables in app/supabase/schema.sql
  - Storage  (/storage/v1)   the private "photos" bucket

Row-level security: every database and photo call is made WITH the
logged-in user's token (read from flask.g, which the server fills in at the
start of each request). Supabase then applies the rules in schema.sql, so
even if our code forgot a "where user_id = ..." filter, the database would
still only hand back that user's own rows.

Sign-up uses a made-up username, not an email. Supabase Auth needs an
email, so we turn the username into a placeholder address that nobody
reads ("Confirm email" must be switched off in the Supabase dashboard).

`db` in every function is a SupabaseDB (the project's address and public
key) instead of a file path; otherwise the functions match store.py, so
the rest of the app does not care which one it is using.
"""
from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from pathlib import Path

import requests
from flask import g

COOKIE = "texdex_session"          # the short-lived access token (about 1 hour)
REFRESH_COOKIE = "texdex_refresh"  # used to get a new access token when it runs out
EMAIL_DOMAIN = "texdex.example"    # ".example" is reserved: these addresses can never be real
BUCKET = "photos"
TIMEOUT = 15  # seconds to wait for Supabase before giving up


@dataclass(frozen=True)
class SupabaseDB:
    url: str  # e.g. https://abcd1234.supabase.co
    key: str  # the PUBLIC key (publishable / anon). Safe on a server; RLS still applies.


class SupabaseError(RuntimeError):
    """Supabase answered with an error we did not expect."""


def email_for(username: str) -> str:
    return f"{username}@{EMAIL_DOMAIN}"


# ---------- low-level helpers ----------

def _headers(db: SupabaseDB, token: str | None = None, **extra) -> dict:
    """apikey says which project; Authorization says which user."""
    headers = {"apikey": db.key, **extra}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _user_token() -> str:
    token = getattr(g, "access_token", None)
    if not token:
        raise SupabaseError("No logged-in user for this request.")
    return token


def _check(response: requests.Response) -> requests.Response:
    if response.status_code >= 400:
        raise SupabaseError(f"{response.status_code}: {response.text[:300]}")
    return response


def _rows(db: SupabaseDB, table: str, params: dict) -> list[dict]:
    """SELECT from a table (as the logged-in user). params use Supabase's
    filter syntax, e.g. {"user_id": "eq.<id>", "order": "id.asc"}."""
    return _check(requests.get(f"{db.url}/rest/v1/{table}", params=params,
                               headers=_headers(db, _user_token()), timeout=TIMEOUT)).json()


def _session(body: dict) -> dict:
    """Turn Supabase's log-in answer into what the server needs."""
    return {"user_id": body["user"]["id"], "token": body["access_token"],
            "cookies": {COOKIE: body["access_token"], REFRESH_COOKIE: body["refresh_token"]}}


def init_db(db) -> None:
    """Nothing to do: the tables are created once with schema.sql."""


# ---------- accounts and log-in sessions ----------

def sign_up(db: SupabaseDB, username: str, password: str, display_name: str) -> dict | None:
    """Create the account and its profile, and log in. None if the username is taken."""
    r = requests.post(f"{db.url}/auth/v1/signup", headers=_headers(db), timeout=TIMEOUT,
                      json={"email": email_for(username), "password": password,
                            "data": {"username": username}})
    if r.status_code in (400, 422) and "already" in r.text.lower():
        return None
    body = _check(r).json()
    if "access_token" not in body:
        # Supabase is waiting for an email confirmation that can never arrive.
        raise SupabaseError('Turn off "Confirm email" in Supabase: Authentication > Sign In / Providers > Email.')
    session = _session(body)
    _check(requests.post(f"{db.url}/rest/v1/profiles", timeout=TIMEOUT,
                         headers=_headers(db, session["token"]),
                         json={"id": session["user_id"], "username": username,
                               "display_name": display_name}))
    return session


def log_in(db: SupabaseDB, username: str, password: str) -> dict | None:
    """None when the username or password is wrong (Supabase answers 400)."""
    r = requests.post(f"{db.url}/auth/v1/token", params={"grant_type": "password"},
                      headers=_headers(db), timeout=TIMEOUT,
                      json={"email": email_for(username), "password": password})
    if r.status_code == 400:
        return None
    return _session(_check(r).json())


def who_is(db: SupabaseDB, cookies) -> dict | None:
    """Who sent this request? Asks Supabase whether the access token is valid.
    If it has expired (they last an hour), swaps the refresh token for a new
    pair and returns them in "cookies" so the server can update the browser."""
    token = cookies.get(COOKIE)
    if token:
        r = requests.get(f"{db.url}/auth/v1/user", headers=_headers(db, token), timeout=TIMEOUT)
        if r.status_code == 200:
            return {"user_id": r.json()["id"], "token": token, "cookies": {}}
    refresh = cookies.get(REFRESH_COOKIE)
    if refresh:
        r = requests.post(f"{db.url}/auth/v1/token", params={"grant_type": "refresh_token"},
                          headers=_headers(db), json={"refresh_token": refresh}, timeout=TIMEOUT)
        if r.status_code == 200:
            return _session(r.json())
    return None


def log_out(db: SupabaseDB, cookies) -> None:
    token = cookies.get(COOKIE)
    if token:
        requests.post(f"{db.url}/auth/v1/logout", headers=_headers(db, token), timeout=TIMEOUT)


def get_user(db: SupabaseDB, user_id: str) -> dict | None:
    rows = _rows(db, "profiles", {"id": f"eq.{user_id}",
                                  "select": "id,username,display_name,avatar,created_at"})
    return rows[0] if rows else None


def update_profile(db: SupabaseDB, user_id: str, display_name: str, avatar: str) -> None:
    _check(requests.patch(f"{db.url}/rest/v1/profiles", params={"id": f"eq.{user_id}"},
                          headers=_headers(db, _user_token()), timeout=TIMEOUT,
                          json={"display_name": display_name, "avatar": avatar}))


# ---------- pending IDs ----------
# A pending ID lives only for the seconds between "photo identified" and
# "user picked a guess", so it is kept in this server's memory, not in
# Supabase. That also means the EXACT location of a possibly protected
# animal is never written to the database: only the blurred one is, on
# confirm. If the server restarts in between, the user just retakes the
# photo. (This needs a single server process, which is how we deploy.)

_pending: dict[str, dict] = {}
_pending_lock = threading.Lock()  # Flask answers requests on several threads


def add_pending(db, user_id, photo_file, photo_hash, latitude, longitude, guesses) -> str:
    pending_id = secrets.token_urlsafe(12)
    with _pending_lock:
        _pending[pending_id] = {"id": pending_id, "user_id": user_id, "photo_file": photo_file,
                                "photo_hash": photo_hash, "latitude": latitude,
                                "longitude": longitude, "guesses": guesses}
    return pending_id


def clear_pending(db, user_id) -> list[str]:
    with _pending_lock:
        mine = [pid for pid, p in _pending.items() if p["user_id"] == user_id]
        return [_pending.pop(pid)["photo_file"] for pid in mine]


def take_pending(db, user_id, pending_id: str) -> dict | None:
    with _pending_lock:
        pending = _pending.get(pending_id)
        if pending is None or pending["user_id"] != user_id:
            return None
        return _pending.pop(pending_id)


# ---------- catches and photos ----------

def add_catch(db: SupabaseDB, *, user_id, species_id, photo_file, photo_hash, latitude,
              longitude, region, tier, confidence, xp) -> int:
    """Upload the photo to the private bucket, then save the catch row."""
    local = Path(photo_file)
    stored_as = f"{user_id}/{local.name}"  # the folder name is what the Storage rule checks
    _check(requests.post(f"{db.url}/storage/v1/object/{BUCKET}/{stored_as}",
                         data=local.read_bytes(), timeout=TIMEOUT,
                         headers=_headers(db, _user_token(), **{"Content-Type": "image/jpeg"})))
    local.unlink(missing_ok=True)  # the server keeps no copy
    row = _check(requests.post(
        f"{db.url}/rest/v1/catches", timeout=TIMEOUT,
        headers=_headers(db, _user_token(), Prefer="return=representation"),
        json={"user_id": user_id, "species_id": species_id, "photo_file": stored_as,
              "photo_hash": photo_hash, "latitude": latitude, "longitude": longitude,
              "region": region, "tier": tier, "confidence": confidence, "xp": xp})).json()
    return row[0]["id"]


def catches_for_user(db: SupabaseDB, user_id) -> list[dict]:
    """Oldest first."""
    return _rows(db, "catches", {"user_id": f"eq.{user_id}", "order": "id.asc"})


def get_catch(db: SupabaseDB, catch_id: int) -> dict | None:
    rows = _rows(db, "catches", {"id": f"eq.{catch_id}"})  # RLS: only finds your own
    return rows[0] if rows else None


def photo_already_used(db: SupabaseDB, user_id, photo_hash: str) -> bool:
    return bool(_rows(db, "catches", {"user_id": f"eq.{user_id}",
                                      "photo_hash": f"eq.{photo_hash}", "select": "id"}))


def read_photo(db: SupabaseDB, catch: dict) -> bytes | None:
    r = requests.get(f"{db.url}/storage/v1/object/authenticated/{BUCKET}/{catch['photo_file']}",
                     headers=_headers(db, _user_token()), timeout=TIMEOUT)
    return r.content if r.status_code == 200 else None


def all_catch_points(db: SupabaseDB) -> list[dict]:
    """Pins for the shared map: your own catches (full rows) plus everyone
    else's from the shared_map_points view, which has no user ids or photos."""
    fields = "id,user_id,species_id,latitude,longitude,region,tier,caught_at"
    own = _rows(db, "catches", {"user_id": f"eq.{g.user_id}", "latitude": "not.is.null",
                                "select": fields, "order": "id.desc"})
    others = [{**p, "id": None, "user_id": None}
              for p in _rows(db, "shared_map_points", {"order": "caught_at.desc"})]
    return own + others
