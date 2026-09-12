"""Self-test for the web application (chunk 4).

Drives the real app over HTTP through Starlette's TestClient -- routes,
templates, database and the engines together, against a throwaway database.
Offline; nothing here reaches the network.

The two cases that matter are 4.1 and 4.2. They are invariant 2 made visible:
the SAME six blank declarations are six CANNOT_DETERMINE from images alone and
six FAIL only once a named person states they had the package in hand. A
photo-only upload that produces a FAIL is a defect.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="lm-webapp-test-")

from app import db                                    # noqa: E402
db.DATA_DIR = _TMP
db.DB_PATH = os.path.join(_TMP, "inspections.db")
db.UPLOAD_DIR = os.path.join(_TMP, "uploads")
db.REPORT_DIR = os.path.join(_TMP, "reports")

from fastapi.testclient import TestClient              # noqa: E402
from app.main import app                               # noqa: E402
from app import service                                # noqa: E402

checks = 0
fails: list[str] = []


def ck(name: str, cond: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if not cond:
        fails.append(f"{name}{(': ' + detail) if detail else ''}")


BLANK = {k: "" for k in service.FIELD_KEYS}
FULL = {
    "name_and_address": "Acme Foods Pvt Ltd, 14 Industrial Estate, Pune 411019",
    "common_or_generic_name": "Roasted almonds",
    "net_quantity": "200 g",
    "month_and_year": "03/2026",
    "retail_sale_price": "MRP Rs.450/- (inclusive of all taxes)",
    "consumer_care": "care@acmefoods.example, 1800-000-000",
}


def login(client, username, password="") -> bool:
    pw = password or {"officer": "officer-2026",
                      "supervisor": "supervisor-2026"}[username]
    r = client.post("/login", data={"username": username, "password": pw},
                    follow_redirects=False)
    return r.status_code == 303


def create(client, **over) -> str:
    """Post an inspection; return its inspection_id from the redirect."""
    data = {"product_name": "Test product", **BLANK}
    data.update(over)
    r = client.post("/upload", data=data, follow_redirects=False)
    assert r.status_code == 303, r.status_code
    return r.headers["location"].rsplit("/", 1)[-1]


def counts_of(inspection_id: str) -> dict:
    return service.results_view(inspection_id)["counts"]


def main() -> int:
    db.init_db()
    client = TestClient(app)

    # ---- 1. auth ---------------------------------------------------------
    for path in ("/upload", "/history", "/dashboard"):
        r = client.get(path, follow_redirects=False)
        ck(f"1.x {path} requires a session", r.status_code == 303
           and r.headers.get("location") == "/login")
    ck("1.4 bad password rejected",
       not login(client, "officer", "wrong-password"))
    ck("1.5 officer signs in", login(client, "officer"))
    ck("1.6 supervisor seeded",
       db.connect(db.DB_PATH).execute(
           "SELECT COUNT(*) c FROM users WHERE role='supervisor'"
       ).fetchone()["c"] == 1)

    # ---- 2. the schema keeps the invariants ------------------------------
    con = db.connect(db.DB_PATH)
    try:
        ck("2.1 findings/measurements stay separate tables",
           {r["name"] for r in con.execute(
               "SELECT name FROM sqlite_master WHERE type='table'")}
           >= {"users", "scans", "findings", "measurements", "determinations"})
        sql = con.execute("SELECT sql FROM sqlite_master WHERE name='findings'"
                          ).fetchone()["sql"]
        ck("2.2 verdict CHECK constraint kept", "CHECK(verdict IN" in sql)
        ck("2.3 source_tier CHECK constraint kept", "CHECK(source_tier IN" in sql)
        scan_id = con.execute(
            "INSERT INTO scans (inspection_id,user_id,created_at,product_name)"
            " VALUES ('X-1',1,'2026-09-12','x')").lastrowid
        bad = False
        try:
            con.execute("INSERT INTO findings (scan_id,declaration_key,verdict,"
                        "source_tier) VALUES (?,?,?,?)",
                        (scan_id, "k", "COMPLIANT", "EXTRACTED"))
        except Exception:
            bad = True
        ck("2.4 database refuses a two-state verdict", bad,
           "a binary COMPLIANT verdict was accepted")
        con.rollback()
    finally:
        con.close()

    # ---- 3. measurements are left unpopulated in this chunk --------------
    con = db.connect(db.DB_PATH)
    try:
        ck("3.1 measurements table empty in chunk 4",
           con.execute("SELECT COUNT(*) c FROM measurements").fetchone()["c"] == 0)
    finally:
        con.close()

    # ---- 4. THE TWO CASES ------------------------------------------------
    photo_only = create(client, product_name="Photo-only, nothing read",
                        panels=["front"])
    c = counts_of(photo_only)
    ck("4.1a photo-only, six blank -> six CANNOT_DETERMINE",
       c["CANNOT_DETERMINE"] == 6, str(c))
    ck("4.1b photo-only, six blank -> zero FAIL", c["FAIL"] == 0, str(c))

    examined = create(client, product_name="Examined in hand, nothing on pack",
                      panels=["front", "back"],
                      operator_examined_package="1", operator_id="LM-OFF-114")
    c2 = counts_of(examined)
    ck("4.2a examined + operator id, six blank -> six FAIL",
       c2["FAIL"] == 6, str(c2))
    ck("4.2b examined + operator id -> zero CANNOT_DETERMINE",
       c2["CANNOT_DETERMINE"] == 0, str(c2))

    # The tick alone must not unlock absence: can_assert_absence() needs both.
    r = client.post("/upload", data={"product_name": "Ticked, no operator id",
                                     "operator_examined_package": "1",
                                     "operator_id": "", **BLANK},
                    follow_redirects=False)
    ck("4.3 tick without an operator ID is refused, not silently accepted",
       r.status_code == 200 and "Operator ID is required" in r.text)

    # ---- 5. a full inspection -------------------------------------------
    full = create(client, product_name="Acme roasted almonds",
                  declared_category="general", declared_pdp_area_cm2="120",
                  panels=["front", "back"], operator_examined_package="1",
                  operator_id="LM-OFF-114", **FULL)
    cf = counts_of(full)
    ck("5.1 a complete package passes its six checks",
       cf["PASS"] == 6, str(cf))

    page = client.get(f"/scan/{full}").text
    ck("5.2 results page renders", "Mandatory declarations" in page)
    ck("5.3 EXTRACTED tier labelled", "[tier: EXTRACTED]" in page)
    ck("5.4 MEASURED section present even with no measurement",
       "[tier: MEASURED]" in page and "Not yet measured" in page)
    ck("5.5 DETERMINED tier labelled", "[tier: DETERMINED]" in page)
    ck("5.6 measured section is the cream/navy box, not the plain table",
       'class="measured"' in page)
    ck("5.7 tier notes printed below all three",
       service.TIER_NOTE["MEASURED"][:40] in page)
    ck("5.8 coverage described", "absence may be asserted" in page)
    ck("5.9 extraction provenance printed", "via manual:officer" in page)
    ck("5.10 record digest shown", "Record digest" in page)
    ck("5.11 hash is not called a signature",
       "NOT a digital signature" in page or "not a digital signature" in page)
    ck("5.12 unverified sub-clause not printed",
       "Rule 6(1)" in page and "Rule 6(1)(a)" not in page)

    # ---- 6. no score anywhere -------------------------------------------
    # Checked as "is a score RENDERED", not "does the word appear" -- the
    # footer says in words that this instrument issues no score, and a naive
    # substring test would flag that disclaimer as the violation.
    dash = client.get("/dashboard").text
    pct = re.compile(r"\d+(?:\.\d+)?\s*%")
    ck("6.1 dashboard renders no percentage figure",
       not pct.search(dash), str(pct.findall(dash)))
    ck("6.2 results page renders no percentage figure",
       not pct.search(page), str(pct.findall(page)))
    ck("6.3 history renders no percentage figure",
       not pct.search(client.get("/history").text))
    ck("6.4 no progress element anywhere",
       "<progress" not in dash and "<progress" not in page)
    ck("6.5 dashboard shows counters", "inspections recorded" in dash)
    ck("6.6 the no-score position is stated in words",
       "no compliance score, percentage or grade" in dash)

    # ---- 7. reports ------------------------------------------------------
    rp = client.get(f"/scan/{full}/report.pdf")
    ck("7.1 PDF exports", rp.status_code == 200
       and rp.content[:5] == b"%PDF-", str(rp.status_code))
    rd = client.get(f"/scan/{full}/report.docx")
    ck("7.2 DOCX exports", rd.status_code == 200
       and rd.content[:2] == b"PK", str(rd.status_code))
    ck("7.3 PDF is not empty", len(rp.content) > 2000, str(len(rp.content)))

    # ---- 8. determination ------------------------------------------------
    r = client.post(f"/scan/{full}/determination",
                    data={"verdict": "Referred for physical verification",
                          "note": "Height not yet measured."},
                    follow_redirects=False)
    ck("8.1 owner may record a determination", r.status_code == 303)
    page2 = client.get(f"/scan/{full}").text
    ck("8.2 determination shown on the record",
       "Referred for physical verification" in page2)
    ck("8.3 blank determination refused",
       client.post(f"/scan/{full}/determination", data={"verdict": " "},
                   follow_redirects=False).headers["location"].endswith("blank=1"))

    # A second officer who does not own the scan may not determine on it.
    other = TestClient(app)
    login(other, "supervisor")
    sup = create(other, product_name="Supervisor's own scan")
    client2 = TestClient(app)
    login(client2, "officer")
    r = client2.post(f"/scan/{sup}/determination", data={"verdict": "x"},
                     follow_redirects=False)
    ck("8.4 a non-owner officer is refused",
       r.headers["location"].endswith("denied=1"))
    r = other.post(f"/scan/{photo_only}/determination",
                   data={"verdict": "Supervisor override"},
                   follow_redirects=False)
    ck("8.5 a supervisor may determine on another officer's scan",
       r.status_code == 303)

    # ---- 9. history and dashboard ---------------------------------------
    hist = client.get("/history").text
    ck("9.1 history lists inspections", full in hist and photo_only in hist)
    ck("9.2 search by product narrows",
       "Acme roasted almonds" in client.get("/history?q=Acme").text
       and "Photo-only" not in client.get("/history?q=Acme").text)
    ck("9.3 search by inspection id",
       full in client.get(f"/history?q={full}").text)
    ck("9.4 search by officer", full in client.get("/history?q=officer").text)
    d = service.dashboard()
    ck("9.5 dashboard counts total", d["total"] == 4, str(d["total"]))
    ck("9.6 dashboard counts a FAIL scan", d["any_fail"] == 1, str(d["any_fail"]))
    ck("9.7 dashboard has no score field",
       not any(k in d for k in ("score", "percentage", "rate", "grade")))

    # ---- 10. record reprints identically ---------------------------------
    ck("10.1 content hash is stable across rebuilds",
       service.build_record(full).content_hash()
       == service.build_record(full).content_hash())
    ck("10.2 rebuilt record keeps three tiers available",
       service.TIER_ORDER == ("EXTRACTED", "MEASURED", "DETERMINED"))

    # ---- 11. the measurement path, which chunk 5 fills -------------------
    # Chunk 4 leaves `measurements` empty, so this inserts one row directly to
    # prove the read path works and chunk 5 only has to INSERT. It also checks
    # the refusal case renders as a stated reason rather than an error.
    con = db.connect(db.DB_PATH)
    try:
        sid = con.execute("SELECT id FROM scans WHERE inspection_id=?",
                          (full,)).fetchone()["id"]
        con.execute(
            """INSERT INTO measurements (scan_id, band, height_mm, u_mm,
                    threshold_mm, convention, refusal_code, refusal_detail,
                    threshold_source_tier, manifest, roi_box)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, "REQUIRES_PHYSICAL_VERIFICATION", 1.15, 0.17, 1.00,
             "cap-height, ascender to baseline", None, "",
             "VERIFIED (primary)", "scale: NIST-traceable rule\nk=2", "10,20,30,40"))
        con.commit()
    finally:
        con.close()

    mv = service.results_view(full)["measurement"]
    ck("11.1 measurement is read back", mv is not None)
    ck("11.2 refusal band maps to CANNOT_DETERMINE, not FAIL",
       mv["verdict"] == "CANNOT_DETERMINE", str(mv["verdict"]))
    ck("11.3 height never printed without its uncertainty",
       "1.15 mm ± 0.17 mm (k=2)" == mv["stated"], mv["stated"])
    ck("11.4 refusal states a reason", "straddles" in mv["basis"], mv["basis"])
    ck("11.5 ROI box surfaced as a declared input", mv["roi_box"] == (10, 20, 30, 40))
    page3 = client.get(f"/scan/{full}").text
    ck("11.6 measured section renders the value", "1.15 mm ± 0.17 mm" in page3)
    ck("11.7 capture manifest surfaced", "NIST-traceable rule" in page3)
    ck("11.8 measured box still visually distinct", 'class="measured"' in page3
       and "Not yet measured" not in page3)
    pdf2 = client.get(f"/scan/{full}/report.pdf")
    ck("11.9 PDF carries the measured section once a measurement exists",
       pdf2.status_code == 200 and len(pdf2.content) > len(rp.content),
       f"{len(rp.content)} -> {len(pdf2.content)}")

    # A height without an uncertainty must be impossible, not merely discouraged.
    import lm_report as _rep
    raised = False
    try:
        _rep.Measurement(band="COMPLIANT", height_mm=1.2, u_mm=None)
    except ValueError:
        raised = True
    ck("11.10 a height without an uncertainty is rejected", raised)

    print("=" * 74)
    for f in fails:
        print("FAIL:", f)
    print(f"webapp self-test: {checks} checks, {len(fails)} failed")
    print("=" * 74)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
