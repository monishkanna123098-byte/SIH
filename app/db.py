"""SQLite storage for the inspection app.

Stdlib `sqlite3` only. No ORM, no migration framework -- the schema is small
enough to read in one sitting, and reading it is the point: the CHECK
constraints on `verdict` and `source_tier` are how invariants 1 and 3 are
enforced by the database rather than by convention.

`findings` and `measurements` are separate tables deliberately (BUILD-SPEC
Sec.4). A measurement carries an uncertainty, a convention and a capture
manifest that a presence-check never has; collapsing them into one table is
how the distinction gets lost.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "inspections.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
REPORT_DIR = os.path.join(DATA_DIR, "reports")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('officer','supervisor'))
);
CREATE TABLE IF NOT EXISTS scans (
  id INTEGER PRIMARY KEY, inspection_id TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL, image_path TEXT,
  product_name TEXT NOT NULL,
  declared_category TEXT, declared_pdp_area_cm2 REAL,
  coverage_panels TEXT, coverage_examined INTEGER NOT NULL DEFAULT 0,
  coverage_operator_id TEXT, coverage_note TEXT,
  headline TEXT
);
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL REFERENCES scans(id),
  declaration_key TEXT NOT NULL, verdict TEXT NOT NULL
    CHECK(verdict IN ('PASS','FAIL','CANNOT_DETERMINE')),
  source_tier TEXT NOT NULL CHECK(source_tier IN ('EXTRACTED','MEASURED','DETERMINED')),
  detected TEXT, why TEXT, citation TEXT, extractor TEXT,
  verbatim_confirmed INTEGER
);
CREATE TABLE IF NOT EXISTS measurements (
  id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL REFERENCES scans(id),
  band TEXT NOT NULL, height_mm REAL, u_mm REAL, threshold_mm REAL,
  convention TEXT, refusal_code TEXT, refusal_detail TEXT,
  threshold_source_tier TEXT, manifest TEXT, roi_box TEXT
);
CREATE TABLE IF NOT EXISTS determinations (
  id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL REFERENCES scans(id),
  officer_id TEXT NOT NULL, verdict TEXT NOT NULL, note TEXT, determined_on TEXT
);
CREATE INDEX IF NOT EXISTS ix_findings_scan ON findings(scan_id);
CREATE INDEX IF NOT EXISTS ix_measurements_scan ON measurements(scan_id);
CREATE INDEX IF NOT EXISTS ix_determinations_scan ON determinations(scan_id);
CREATE INDEX IF NOT EXISTS ix_scans_created ON scans(created_at DESC);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


# --------------------------------------------------------------------------
# Passwords -- stdlib PBKDF2. No bcrypt wheel to fail to install on the day.
# --------------------------------------------------------------------------
_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, want = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt_hex), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), want)


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------
# The two demo accounts. Their passwords are in this file and therefore in the
# repository, which is fine for a laptop reachable only from itself and NOT
# fine the moment a forwarded port is made public: anyone who can read the repo
# can then sign in. Override both before sharing a URL. Defaults are unchanged
# so the local run, the self-tests and the offline demo behave exactly as
# before with nothing set.
_SEED_ENV = {"officer": "LM_OFFICER_PASSWORD",
             "supervisor": "LM_SUPERVISOR_PASSWORD"}
_SEED_DEFAULT = {"officer": "officer-2026", "supervisor": "supervisor-2026"}


def _seed_password(username: str) -> str:
    return os.environ.get(_SEED_ENV[username]) or _SEED_DEFAULT[username]


def _seed_password_is_set(username: str) -> bool:
    """Whether an operator explicitly chose this account's password."""
    return bool(os.environ.get(_SEED_ENV[username]))


SEED_USERS = tuple((u, _seed_password(u), r)
                   for u, r in (("officer", "officer"),
                                ("supervisor", "supervisor")))


def seeded_passwords_are_default() -> bool:
    """True while either demo account still has its committed password."""
    return not all(_seed_password_is_set(u) for u in _SEED_ENV)


# Columns added after chunk 4 shipped. Applied with ALTER TABLE rather than by
# editing SCHEMA, so a database created by chunk 4 keeps its rows -- and applied
# by inspection rather than by a version counter, so the two cannot drift.
# `measurements` needed no change: chunk 4 wrote that table to the BUILD-SPEC
# contract and chunk 5 only fills it.
MIGRATIONS = {
    "scans": (
        ("scale_ppm", "REAL"),                    # operator-entered px/mm
        ("scale_artifact", "TEXT"),               # what was in frame
        ("scale_artifact_tier", "TEXT"),          # how much weight it carries
        ("declared_commodity_class", "TEXT"),
        ("declared_glyph_count", "INTEGER"),
        ("image_annotated_path", "TEXT"),         # copy with the ROI drawn on it
    ),
}


def _migrate(con) -> None:
    for table, columns in MIGRATIONS.items():
        have = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns:
            if name not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init_db(path: str | None = None) -> None:
    """Create directories, schema and the two seeded users. Idempotent."""
    for d in (DATA_DIR, UPLOAD_DIR, REPORT_DIR):
        os.makedirs(d, exist_ok=True)
    con = connect(path)
    try:
        con.executescript(SCHEMA)
        _migrate(con)
        for username, password, role in SEED_USERS:
            row = con.execute("SELECT password_hash FROM users WHERE username=?",
                              (username,)).fetchone()
            if row is None:
                con.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?,?,?)",
                    (username, hash_password(password), role))
            elif (_seed_password_is_set(username)
                  and not verify_password(password, row["password_hash"])):
                # The account already exists from an earlier run. Without this
                # the environment variable would be silently inert on any
                # database that has been opened before -- every Codespace after
                # the first -- and the committed password would keep working
                # while `seeded_passwords_are_default()` reported all clear.
                # Only ever applied when a password was explicitly configured:
                # a deployment that sets nothing never has a password reset
                # underneath it.
                con.execute("UPDATE users SET password_hash=? WHERE username=?",
                            (hash_password(password), username))
        con.commit()
    finally:
        con.close()


def session_secret() -> bytes:
    """Persisted so a reload does not log everyone out. Not in git."""
    os.makedirs(DATA_DIR, exist_ok=True)
    p = os.path.join(DATA_DIR, "session.key")
    if not os.path.exists(p):
        with open(p, "wb") as fh:
            fh.write(secrets.token_bytes(32))
        os.chmod(p, 0o600)
    with open(p, "rb") as fh:
        return fh.read()
