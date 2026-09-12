"""Session cookie and the two roles.

Thin on purpose (BUILD-SPEC Sec.2 item 8: "Yes, thin"). Two roles, one cookie,
no password reset, no registration screen. The cookie is HMAC-signed with a
key held in `data/session.key`, so a restart does not invalidate sessions and
a forged cookie does not authenticate.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import time
from typing import Optional

from fastapi import Request

from . import db

COOKIE_NAME = "lm_session"
MAX_AGE = 8 * 60 * 60          # one working day, near enough

ROLE_OFFICER = "officer"
ROLE_SUPERVISOR = "supervisor"


def _sign(payload: str) -> str:
    mac = hmac.new(db.session_secret(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def make_cookie(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time())}"
    return f"{payload}.{_sign(payload)}"


def read_cookie(raw: Optional[str]) -> Optional[int]:
    """Return the user id if the cookie is well-formed, signed and fresh."""
    if not raw:
        return None
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    uid_s, issued_s, sig = parts
    payload = f"{uid_s}.{issued_s}"
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        uid, issued = int(uid_s), int(issued_s)
    except ValueError:
        return None
    if time.time() - issued > MAX_AGE:
        return None
    return uid


def current_user(request: Request) -> Optional[dict]:
    uid = read_cookie(request.cookies.get(COOKIE_NAME))
    if uid is None:
        return None
    con = db.connect()
    try:
        row = con.execute(
            "SELECT id, username, role FROM users WHERE id=?", (uid,)).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def authenticate(username: str, password: str) -> Optional[dict]:
    con = db.connect()
    try:
        row = con.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username=?",
            (username.strip(),)).fetchone()
    finally:
        con.close()
    if row is None:
        # Spend the same work on an unknown user so the response time does not
        # advertise which usernames exist.
        db.verify_password(password, db.hash_password("x"))
        return None
    if not db.verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def may_determine(user: dict, scan_owner_id: int) -> bool:
    """Who may record an officer determination: a supervisor, or the owner."""
    return user["role"] == ROLE_SUPERVISOR or user["id"] == scan_owner_id
