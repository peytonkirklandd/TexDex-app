"""Local storage: accounts, log-in sessions, pending IDs and catches.

This is a small SQLite database in one file, used for local development and
the class demo. The Supabase version of the same tables (with row-level
security) is in app/supabase/schema.sql; this file is what gets swapped out
when the Supabase project exists. Every function takes the database path, so
tests can use a throwaway file.

The "collection" is not a table. It is worked out from the catches table
whenever it is needed (see dex.py), so the two can never disagree.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    display_name  TEXT NOT NULL,
    avatar        TEXT NOT NULL DEFAULT '🤠',
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending (
    id         TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    photo_file TEXT NOT NULL,
    photo_hash TEXT NOT NULL,
    latitude   REAL,
    longitude  REAL,
    guesses    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS catches (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    species_id TEXT NOT NULL,
    photo_file TEXT NOT NULL,
    photo_hash TEXT NOT NULL,
    latitude   REAL,
    longitude  REAL,
    region     TEXT NOT NULL DEFAULT '',
    tier       TEXT NOT NULL,
    confidence REAL NOT NULL,
    xp         INTEGER NOT NULL,
    caught_at  TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path):
    """Open the database, hand it over, then save and close. One short-lived
    connection per call keeps things simple and safe with Flask's threads."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


# ---------- accounts ----------

def hash_password(password: str, salt: str) -> str:
    """We never store the password itself, only a scrambled version.
    PBKDF2 repeats the scrambling 200,000 times so guessing is slow, and the
    random per-user salt means two users with the same password get
    different results."""
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return digest.hex()


def create_user(db_path, username: str, password: str, display_name: str) -> int | None:
    """Returns the new user's id, or None if the username is taken."""
    salt = secrets.token_hex(16)
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO users (username, display_name, password_hash, salt, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, display_name, hash_password(password, salt), salt, now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def check_login(db_path, username: str, password: str) -> int | None:
    """Returns the user's id if the password is right, else None."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        return None
    # compare_digest takes the same time whether the guess is close or not,
    # so timing the response does not leak anything.
    if hmac.compare_digest(row["password_hash"], hash_password(password, row["salt"])):
        return row["id"]
    return None


def get_user(db_path, user_id: int) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, display_name, avatar, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def update_profile(db_path, user_id: int, display_name: str, avatar: str) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE users SET display_name = ?, avatar = ? WHERE id = ?",
                     (display_name, avatar, user_id))


# ---------- log-in sessions ----------

def create_session(db_path, user_id: int) -> str:
    token = secrets.token_urlsafe(32)  # long random string, impossible to guess
    with connect(db_path) as conn:
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (token, user_id, now()))
    return token


def user_for_session(db_path, token: str | None) -> int | None:
    if not token:
        return None
    with connect(db_path) as conn:
        row = conn.execute("SELECT user_id FROM sessions WHERE token = ?", (token,)).fetchone()
    return row["user_id"] if row else None


def delete_session(db_path, token: str) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---------- pending IDs (photo identified, waiting for the user to confirm) ----------

def add_pending(db_path, user_id, photo_file, photo_hash, latitude, longitude, guesses) -> str:
    pending_id = secrets.token_urlsafe(12)
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO pending VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pending_id, user_id, photo_file, photo_hash, latitude, longitude,
             json.dumps(guesses), now()),
        )
    return pending_id


def clear_pending(db_path, user_id: int) -> list[str]:
    """Delete a user's unconfirmed IDs and return their photo files so the
    caller can delete those too. Called before each new photo: a user only
    has one ID in flight, and an abandoned one still holds an exact location
    that we do not want lying around (it may be a protected species)."""
    with connect(db_path) as conn:
        rows = conn.execute("SELECT photo_file FROM pending WHERE user_id = ?", (user_id,)).fetchall()
        conn.execute("DELETE FROM pending WHERE user_id = ?", (user_id,))
    return [r["photo_file"] for r in rows]


def take_pending(db_path, user_id: int, pending_id: str) -> dict | None:
    """Fetch AND remove a pending ID, so it can only be confirmed once.
    Only the user who took the photo can take it."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM pending WHERE id = ? AND user_id = ?",
                           (pending_id, user_id)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM pending WHERE id = ?", (pending_id,))
    result = dict(row)
    result["guesses"] = json.loads(result["guesses"])
    return result


# ---------- catches ----------

def add_catch(db_path, *, user_id, species_id, photo_file, photo_hash, latitude, longitude,
              region, tier, confidence, xp) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO catches (user_id, species_id, photo_file, photo_hash, latitude, "
            "longitude, region, tier, confidence, xp, caught_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, species_id, photo_file, photo_hash, latitude, longitude, region, tier,
             confidence, xp, now()),
        )
        return cur.lastrowid


def catches_for_user(db_path, user_id: int) -> list[dict]:
    """Oldest first."""
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM catches WHERE user_id = ? ORDER BY id",
                            (user_id,)).fetchall()
    return [dict(r) for r in rows]


def get_catch(db_path, catch_id: int) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM catches WHERE id = ?", (catch_id,)).fetchone()
    return dict(row) if row else None


def photo_already_used(db_path, user_id: int, photo_hash: str) -> bool:
    with connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM catches WHERE user_id = ? AND photo_hash = ?",
                           (user_id, photo_hash)).fetchone()
    return row is not None


def all_catch_points(db_path) -> list[dict]:
    """Every user's catches for the shared map. The coordinates in the table
    are already blurred for protected species (see privacy.py)."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, user_id, species_id, latitude, longitude, region, tier, caught_at "
            "FROM catches WHERE latitude IS NOT NULL ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]
