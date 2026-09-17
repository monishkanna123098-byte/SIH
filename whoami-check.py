#!/usr/bin/env python3
"""Why won't the login work? Reports state, never a password.

    python3 whoami-check.py

Prints lengths and yes/no only -- safe to paste into a chat window.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db                                  # noqa: E402


def describe(name):
    raw = os.environ.get(name)
    if raw is None:
        return "not set in this process"
    if not raw.strip():
        return "set but empty or whitespace only -- treated as not set"
    extra = []
    if raw != raw.strip():
        extra.append("HAD surrounding whitespace, stripped")
    return "set, %d chars after stripping%s" % (
        len(raw.strip()), " (" + "; ".join(extra) + ")" if extra else "")


print("environment")
for n in ("LM_OFFICER_PASSWORD", "LM_SUPERVISOR_PASSWORD"):
    print("  %-24s %s" % (n, describe(n)))
print("  %-24s %s" % ("LM_HOST", os.environ.get("LM_HOST") or "not set (127.0.0.1)"))

print("\ndatabase: %s" % db.DB_PATH)
if not os.path.exists(db.DB_PATH):
    print("  does not exist yet -- it is created when the app first starts")
    raise SystemExit(0)

con = db.connect(db.DB_PATH)
try:
    rows = con.execute("SELECT username, role, password_hash FROM users "
                       "ORDER BY username").fetchall()
finally:
    con.close()

if not rows:
    print("  no user rows at all")
    raise SystemExit(1)

for r in rows:
    configured = db._seed_password_is_set(r["username"]) \
        if r["username"] in db._SEED_ENV else False
    committed = db._SEED_DEFAULT.get(r["username"])
    on_default = bool(committed) and db.verify_password(
        committed, r["password_hash"])
    if on_default:
        state = "the COMMITTED default (officer-2026 / supervisor-2026)"
    elif configured and db.verify_password(
            db._seed_password(r["username"]), r["password_hash"]):
        state = "the password currently in the environment"
    else:
        state = ("something else -- neither the committed default nor what is "
                 "in the environment now")
    print("  %-11s role=%-10s password is %s" % (r["username"], r["role"], state))

print("\nwhat to type")
for r in rows:
    if r["username"] not in db._SEED_ENV:
        continue
    committed = db._SEED_DEFAULT[r["username"]]
    if db.verify_password(committed, r["password_hash"]):
        print("  %-11s %s" % (r["username"], committed))
    elif db._seed_password_is_set(r["username"]):
        print("  %-11s the value of %s" % (r["username"],
                                           db._SEED_ENV[r["username"]]))
    else:
        print("  %-11s unknown -- rotated earlier, and %s is not set now. "
              "Set it and restart to take the account back."
              % (r["username"], db._SEED_ENV[r["username"]]))
