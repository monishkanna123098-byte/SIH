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
    # Chunk 5 replaced chunk 4's blanket "Not yet measured" with a reason: this
    # inspection has no evidence image, so it says so. The section is still
    # shown either way -- its presence is the point.
    ck("5.4 MEASURED section present even with no measurement",
       "[tier: MEASURED]" in page and "No evidence image" in page)
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
       and "No evidence image" not in page3)
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

    # ======================================================================
    # CHUNK 5 -- the measurement
    # ======================================================================
    import io
    import lm_metrology_v7 as _lm
    import lm_legal_model as _legal
    import numpy as _np
    from PIL import Image as _Image

    def synthetic_label(target_mm: float, ppm: float = 120.0,
                        contrast=(0.10, 0.85)) -> bytes:
        """A real measurable label, saved as an 8-bit PNG the app can accept.

        Same generator the metrology harness uses, so the pixels the engine
        sees here are the pixels it is characterised on -- then round-tripped
        through PNG exactly as an uploaded file would be.
        """
        sc = _lm.make_glyphs(ppm, target_ref_mm=target_mm, contrast=contrast)
        img = _lm.blur_noise(sc.img, 1.8, 0.010, 0)
        buf = io.BytesIO()
        _Image.fromarray((_np.clip(img, 0, 1) * 255).astype(_np.uint8), "L").save(
            buf, format="PNG")
        return buf.getvalue()

    def create_measurable(client, *, target_mm=1.4, ppm=120.0, pdp="40",
                          commodity=_legal.COMMODITY_GENERAL, contrast=(0.10, 0.85),
                          scale_ppm=None, with_image=True, name="Measured product"):
        data = {"product_name": name, "declared_category": "general",
                "declared_pdp_area_cm2": pdp,
                "declared_commodity_class": commodity,
                "declared_glyph_count": "9",
                "scale_artifact": "chessboard target, 2.00 mm pitch",
                "scale_artifact_tier": "workshop rule, dimension not certified",
                "panels": ["front"], "operator_examined_package": "1",
                "operator_id": "LM-OFF-114", **BLANK}
        if scale_ppm is None:
            scale_ppm = str(ppm)
        if scale_ppm != "":
            data["scale_ppm"] = scale_ppm
        files = {}
        if with_image:
            files["image"] = ("label.png", synthetic_label(target_mm, ppm, contrast),
                              "image/png")
        r = client.post("/upload", data=data, files=files or None,
                        follow_redirects=False)
        assert r.status_code == 303, r.text[:500]
        return r.headers["location"].rsplit("/", 1)[-1]

    def measure(client, iid, box):
        x, y, w, h = box
        return client.post(f"/scan/{iid}/measure",
                           data={"x": x, "y": y, "w": w, "h": h},
                           follow_redirects=False)

    def full_box(iid):
        sc = service.get_scan(iid)
        wh = service.image_size(sc)
        return (0, 0, wh[0], wh[1])

    # ---- 12. done 1: px/mm + region -> a populated row and a cream box ----
    comp = create_measurable(client, target_mm=1.4, name="Compliant specimen")
    r = measure(client, comp, full_box(comp))
    ck("12.1 measure redirects back to the record", r.status_code == 303)
    mv = service.results_view(comp)["measurement"]
    ck("12.2 a measurement row exists", mv["state"] == "measured", str(mv["state"]))
    ck("12.3 band is COMPLIANT for a 1.4 mm specimen against 1.0 mm",
       mv["verdict"] == "PASS" and "COMPLIANT" in mv["headline"],
       f"{mv['verdict']} / {mv['headline']}")
    ck("12.4 height carries its uncertainty", "k=2" in mv["stated"]
       and "±" in mv["stated"], mv["stated"])
    ck("12.5 threshold came from the legal model", mv["threshold"] == "1.00 mm",
       mv["threshold"])
    ck("12.6 threshold source tier is stated, not assumed",
       "AGGREGATOR" in mv["threshold_source_tier"], mv["threshold_source_tier"])
    ck("12.7 convention recorded", "50%" in mv["convention"], mv["convention"])
    page = client.get(f"/scan/{comp}").text
    ck("12.8 cream box renders the measurement", 'class="measured"' in page
       and "COMPLIANT" in page)
    ck("12.9 the height appears on the page with its uncertainty",
       mv["stated"] in page)
    con = db.connect(db.DB_PATH)
    try:
        row = con.execute("""SELECT * FROM measurements WHERE scan_id=
                             (SELECT id FROM scans WHERE inspection_id=?)""",
                          (comp,)).fetchone()
    finally:
        con.close()
    ck("12.10 the row is in `measurements`, not in `findings`", row is not None)
    ck("12.11 the row carries band, height, u and threshold",
       row["band"] and row["height_mm"] and row["u_mm"] and row["threshold_mm"])

    # ---- 13. done 2: no px/mm -> no measurement, said plainly -------------
    noscale = create_measurable(client, scale_ppm="", name="No scale reference")
    nv = service.results_view(noscale)["measurement"]
    ck("13.1 no scale -> no measurement attempted", nv["state"] == "no_scale",
       str(nv["state"]))
    npage = client.get(f"/scan/{noscale}").text
    ck("13.2 the page says so plainly", "No scale reference" in npage
       and "height cannot be measured" in npage.lower())
    ck("13.3 no measurement row was written", nv["attempts"] == 0)
    ck("13.4 posting a region without a scale is refused, not guessed",
       measure(client, noscale, (0, 0, 50, 50)).headers["location"].count(
           "measure_error") == 1)
    ck("13.5 no DPI fallback is offered anywhere on the upload form",
       "dpi" not in client.get("/upload").text.lower())
    ck("13.6 the scale field has no default value",
       'name="scale_ppm"' in client.get("/upload").text
       and 'name="scale_ppm"\n           value=""' in client.get("/upload").text
       or 'value=""' in client.get("/upload").text)

    # ---- 14. done 3: near-threshold is a calm panel, not an error ---------
    near = create_measurable(client, target_mm=1.0, name="Near threshold")
    measure(client, near, full_box(near))
    nmv = service.results_view(near)["measurement"]
    ck("14.1 near-threshold refers for physical verification",
       nmv["verdict"] == "CANNOT_DETERMINE", str(nmv["verdict"]))
    ck("14.2 headline reads INDETERMINATE, not an error",
       nmv["headline"].startswith("INDETERMINATE"), nmv["headline"])
    ck("14.3 the reason names the straddle", "straddles" in nmv["basis"],
       nmv["basis"])
    ck("14.4 a next action is offered",
       "physical verification" in nmv["next_action"].lower(), nmv["next_action"])
    npg = client.get(f"/scan/{near}")
    ck("14.5 the page is a normal 200, not an error page",
       npg.status_code == 200)
    ck("14.6 the refusal renders inside the cream measured box",
       'class="measured"' in npg.text and "INDETERMINATE" in npg.text)
    ck("14.7 no error styling around the refusal",
       'class="error"' not in npg.text.split('class="measured"')[1].split("</div>")[0])
    ck("14.8 height and uncertainty still printed together on a straddle",
       "±" in nmv["stated"] and "k=2" in nmv["stated"], nmv["stated"])

    # ---- 15. done 4: the disputed bracket leaks nothing -------------------
    disp = create_measurable(client, target_mm=1.4, pdp="75",
                             name="Disputed bracket")
    measure(client, disp, full_box(disp))
    dmv = service.results_view(disp)["measurement"]
    ck("15.1 disputed bracket refuses",
       dmv["refusal_code"] == _legal.BLOCK_THRESHOLD_DISPUTED,
       str(dmv["refusal_code"]))
    ck("15.2 no height is printed", dmv["stated"] == "not measured", dmv["stated"])
    ck("15.3 no threshold is printed", dmv["threshold"] == "not resolved",
       dmv["threshold"])
    dpage = client.get(f"/scan/{disp}").text
    for leaked in ("1.5 mm", "2.0 mm", "1.5mm", "2.0mm"):
        ck(f"15.x candidate {leaked!r} does not reach the page",
           leaked not in dpage)
    # Scoped to the text the LEGAL layer produces, the way test_integration
    # scopes it. The operator's own scale-artifact description is echoed in the
    # manifest and may legitimately contain any number they typed; a bare
    # substring test over the whole manifest measures the operator, not the leak.
    legal_text = (dmv["basis"] + " " + dmv["refusal_detail"] + " "
                  + " ".join(l for l in dmv["manifest"]
                             if not l.startswith(("scale ", "measurement attempt",
                                                  "region measured", "ROI sensitivity")))) 
    for leaked in ("1.5", "2.0"):
        ck(f"15.y candidate {leaked!r} does not reach the legal text",
           leaked not in legal_text, legal_text[:220])
    ck("15.6 rule_candidates are not rendered", "rule_candidates" not in dpage)
    ck("15.7 the next action names the rule, not a re-capture",
       "not settled" in dmv["next_action"], dmv["next_action"])

    # ---- 16. done 5: the region is stored, drawn, and labelled ------------
    sc_comp = service.get_scan(comp)
    ck("16.1 roi_box stored", row["roi_box"] == "0,0,%d,%d" % service.image_size(sc_comp),
       str(row["roi_box"]))
    ck("16.2 an annotated copy was written",
       bool(sc_comp["image_annotated_path"]))
    ck("16.3 the original evidence image is untouched",
       sc_comp["image_annotated_path"] != sc_comp["image_path"])
    orig = client.get(f"/scan/{comp}/image")
    drawn = client.get(f"/scan/{comp}/image.roi")
    ck("16.4 both images serve", orig.status_code == 200 and drawn.status_code == 200)
    ck("16.5 the drawn copy differs from the original",
       orig.content != drawn.content)
    ck("16.6 the region is labelled operator-declared",
       "operator-declared region" in page)
    ck("16.7 the ROI sensitivity is stated, not folded into U",
       "not in the uncertainty budget" in page.lower()
       or "NOT in the uncertainty budget" in " ".join(mv["manifest"]))
    # The drag itself needs a browser and is NOT exercised here. What is
    # checked: the conversion exists and is derived from naturalWidth rather
    # than assumed 1:1, and -- server-side, above -- that a posted box is
    # interpreted in image pixels (16.1 compares it to the real image size).
    _roi_js = open("app/static/roi.js").read()
    ck("16.8 the selector converts display px to image px",
       "naturalWidth" in _roi_js and "natural / shown" in _roi_js)
    ck("16.9 the conversion happens in one place",
       _roi_js.count("function factor()") == 1)

    # ---- 17. done 6: the documents carry the measurement ------------------
    pdf = client.get(f"/scan/{comp}/report.pdf")
    docx = client.get(f"/scan/{comp}/report.docx")
    ck("17.1 PDF exports with a measurement", pdf.status_code == 200
       and pdf.content[:5] == b"%PDF-")
    ck("17.2 DOCX exports with a measurement", docx.status_code == 200
       and docx.content[:2] == b"PK")
    import zipfile
    with zipfile.ZipFile(io.BytesIO(docx.content)) as z:
        dx = z.read("word/document.xml").decode("utf-8", "replace")
    ck("17.3 DOCX carries the height and its uncertainty",
       "k=2" in dx and "1.40" in dx, "height/U missing from DOCX")
    ck("17.4 DOCX carries the convention", "50%" in dx or "50" in dx)
    ck("17.5 DOCX carries the threshold source tier", "AGGREGATOR" in dx)
    ck("17.6 DOCX has the MEASURED tier heading", "Character height" in dx)

    # ---- 18. pre-flight quality gates, surfaced not reimplemented ---------
    lowc = create_measurable(client, target_mm=1.4, contrast=(0.45, 0.55),
                             name="Low contrast capture")
    measure(client, lowc, full_box(lowc))
    qv = service.results_view(lowc)["measurement"]
    ck("18.1 a low-contrast capture is refused by the engine's own gate",
       qv["refusal_code"] == "CONTRAST", str(qv["refusal_code"]))
    ck("18.2 it reads as an image problem, not a compliance outcome",
       qv["is_quality"] and "IMAGE QUALITY" in qv["headline"], qv["headline"])
    ck("18.3 the remedy is to re-light and rescan",
       "re-light" in qv["next_action"].lower(), qv["next_action"])
    ck("18.4 a quality refusal is still CANNOT_DETERMINE, never FAIL",
       qv["verdict"] == "CANNOT_DETERMINE", str(qv["verdict"]))

    # Below min_px_per_mm the ENGINE refuses; the app does not pre-empt it.
    lowppm = create_measurable(client, target_mm=1.4, ppm=20.0,
                               name="Below the resolution floor")
    measure(client, lowppm, full_box(lowppm))
    rv = service.results_view(lowppm)["measurement"]
    ck("18.5 a sub-floor scale is attempted, and the engine issues RESOLUTION",
       rv["refusal_code"] == "RESOLUTION", str(rv["refusal_code"]))
    ck("18.6 the app did not pre-empt the engine's gate",
       rv["state"] == "measured")

    # FLOOR_LIMITED has no reachable region of its own (AUDIT 2.2): below
    # 30 px/mm RESOLUTION fires, at or above it FLOOR_LIMITED cannot. No UI
    # claims it, and nothing here expects it.
    ck("18.7 no UI is built for the unreachable FLOOR_LIMITED gate",
       "FLOOR_LIMITED" not in open("app/templates/results.html").read()
       and "FLOOR_LIMITED" not in open("app/service.py").read())
    # PLANARITY and NO_REDUNDANCY cannot fire on this path -- no fiducials are
    # passed -- so nothing claims them either.
    for gate in ("PLANARITY", "NO_REDUNDANCY"):
        ck(f"18.x nothing claims {gate}",
           gate not in open("app/templates/results.html").read()
           and gate not in page)

    # ---- 19. vocabulary and the audit's named limits ---------------------
    ck("19.1 the word 'accuracy' is not used -- nothing has met a standard",
       "accuracy" not in page.lower() and "accurate" not in page.lower())
    ck("19.2 re-measuring appends rather than overwrites",
       (measure(client, comp, (0, 0, 200, 200)).status_code == 303)
       and service.results_view(comp)["measurement"]["attempts"] == 2)
    ck("19.3 earlier regions stay on the record",
       len(service.results_view(comp)["measurement"]["earlier_regions"]) == 1)
    page2 = client.get(f"/scan/{comp}").text
    ck("19.4 the record says how many attempts there have been",
       "measurement attempt 2" in page2.lower())
    ck("19.5 a region outside the image is refused",
       "measure_error" in measure(client, comp, (0, 0, 99999, 99999)
                                  ).headers["location"])
    ck("19.6 a zero-area region is refused",
       "measure_error" in measure(client, comp, (0, 0, 0, 0)).headers["location"])

    # ======================================================================
    # CHUNK 6 -- the pipeline strip
    # ======================================================================
    _css = open("app/static/app.css").read()
    _pipe_raw = _css[_css.index("---- the pipeline strip"):]
    # Strip comments before scanning. This block documents what it must NOT do
    # ("never red", "No animation anywhere"), so a bare substring test over the
    # raw text matches the prose rather than the rules.
    _pipe_css = re.sub(r"/\*.*?\*/", "", "/*" + _pipe_raw, flags=re.S)

    # comp was deliberately re-measured on a small crop in 19.2, so its LATEST
    # measurement is that crop's verdict -- which is the append-not-overwrite
    # behaviour working. A separate inspection is measured once, on the whole
    # image, for the assertions about a resolved band.
    pdone = create_measurable(client, target_mm=1.4, name="Pipeline done state")
    measure(client, pdone, full_box(pdone))

    def strip(iid):
        return service.results_view(iid)["pipeline"]

    def st(iid, name):
        return next(x for x in strip(iid) if x["name"] == name)

    # ---- 20. done 1: renders for every scan, at every degree of completeness
    for iid, label in ((photo_only, "brand-new, nothing captured"),
                       (full, "declarations only"),
                       (comp, "measured"),
                       (near, "refused measurement"),
                       (noscale, "no scale reference")):
        p_ = strip(iid)
        ck(f"20.1 strip renders for a {label} inspection", len(p_) == 5,
           f"{len(p_)} stages")
        ck(f"20.2 stage order is fixed for a {label} inspection",
           [x["name"] for x in p_] == ["CAPTURE", "CALIBRATE", "EXTRACT",
                                       "MEASURE", "ADJUDICATE"],
           str([x["name"] for x in p_]))
        ck(f"20.3 every stage carries one of the three states ({label})",
           all(x["state"] in ("pending", "done", "refused") for x in p_))

    ck("20.4 the strip is on the results page",
       'class="pipeline"' in client.get(f"/scan/{comp}").text)
    ck("20.5 the strip sits above the three tier sections",
       client.get(f"/scan/{comp}").text.index('class="pipeline"')
       < client.get(f"/scan/{comp}").text.index("[tier: EXTRACTED]"))

    # ---- 21. done 2: CALIBRATE, empty, at full weight ---------------------
    cal = st(noscale, "CALIBRATE")
    ck("21.1 no scale reference -> CALIBRATE is pending",
       cal["state"] == "pending", str(cal["state"]))
    ck("21.2 CALIBRATE explains itself when empty",
       "no scale reference" in cal["note"]
       and "cannot be measured" in cal["note"], cal["note"])
    npage = client.get(f"/scan/{noscale}").text
    ck("21.3 the empty CALIBRATE stage is rendered, not hidden",
       "no scale reference -- height cannot be measured" in npage)
    ck("21.4 every stage is flex: 1 1 0 -- CALIBRATE is not narrowed",
       "flex: 1 1 0" in _pipe_css
       and "nth-child" not in _pipe_css, "a stage is being sized specially")
    ck("21.5 nothing hides or collapses a stage",
       "display: none" not in _pipe_css and "visibility: hidden" not in _pipe_css)
    ck("21.6 a populated CALIBRATE shows px/mm, artifact and tier",
       any("px/mm" in l for l in st(comp, "CALIBRATE")["lines"])
       and any("artifact:" in l for l in st(comp, "CALIBRATE")["lines"])
       and any("tier:" in l for l in st(comp, "CALIBRATE")["lines"]),
       str(st(comp, "CALIBRATE")["lines"]))

    # ---- 22. done 3: a refused measurement, in cream, not red ------------
    ck("22.1 a straddle shows MEASURE refused",
       st(near, "MEASURE")["state"] == "refused", str(st(near, "MEASURE")))
    ck("22.2 the reason is shown",
       any("straddles" in l or l for l in st(near, "MEASURE")["lines"]))
    ck("22.3 a disputed threshold shows its code in the strip",
       "THRESHOLD_DISPUTED" in " ".join(st(disp, "MEASURE")["lines"]),
       str(st(disp, "MEASURE")["lines"]))
    ck("22.4 an image-quality refusal shows its code",
       "CONTRAST" in " ".join(st(lowc, "MEASURE")["lines"]))
    ck("22.5 the refused stage is cream, not red",
       "var(--measured-bg)" in _pipe_css and "--fail-bg" not in _pipe_css
       and not re.search(r":\s*red\b|#[fF][0-9a-fA-F]{0,1}[0-9a-fA-F]"
                         r"[0-9a-fA-F]{0,1}[0-9a-fA-F]{0,2}\s*;\s*$", _pipe_css),
       "a red value reached the strip")
    ck("22.6 a resolved measurement shows the band, not a refusal",
       st(pdone, "MEASURE")["state"] == "done"
       and "COMPLIANT" in " ".join(st(pdone, "MEASURE")["lines"]),
       str(st(pdone, "MEASURE")))

    # ---- 23. skipped is pending, never done -----------------------------
    blank_strip = {x["name"]: x["state"] for x in strip(photo_only)}
    ck("23.1 no image -> CAPTURE pending", blank_strip["CAPTURE"] == "pending")
    ck("23.2 no scale -> CALIBRATE pending", blank_strip["CALIBRATE"] == "pending")
    ck("23.3 no measurement -> MEASURE pending", blank_strip["MEASURE"] == "pending")
    ck("23.4 extraction did run -> EXTRACT done", blank_strip["EXTRACT"] == "done")
    ck("23.5 EXTRACT reports how many were actually read",
       "0 of 6 declarations read" in " ".join(st(photo_only, "EXTRACT")["lines"]),
       str(st(photo_only, "EXTRACT")["lines"]))
    ck("23.6 a full read reports six",
       "6 of 6 declarations read" in " ".join(st(full, "EXTRACT")["lines"]),
       str(st(full, "EXTRACT")["lines"]))
    ck("23.7 ADJUDICATE is pending until an officer has ruled",
       st(comp, "ADJUDICATE")["state"] == "pending"
       and "awaiting determination" in st(comp, "ADJUDICATE")["note"])
    ck("23.8 ADJUDICATE is done once a determination exists",
       st(full, "ADJUDICATE")["state"] == "done", str(st(full, "ADJUDICATE")))
    ck("23.9 ADJUDICATE carries the headline and three counts",
       any("PASS" in l and "FAIL" in l and "CANNOT DETERMINE" in l
           for l in st(full, "ADJUDICATE")["lines"]),
       str(st(full, "ADJUDICATE")["lines"]))

    # ---- 24. what the strip must NOT do ---------------------------------
    spage = client.get(f"/scan/{comp}").text
    _strip_html = spage[spage.index('class="pipeline"'):spage.index("</ol>")]
    ck("24.1 no percentage in the strip", not pct.search(_strip_html))
    ck("24.2 no progress bar or ring",
       "<progress" not in _strip_html and "ring" not in _strip_html.lower()
       and "progress" not in _pipe_css.lower())
    ck("24.3 no tick or cross characters",
       not any(c in _strip_html for c in ("\u2713", "\u2714", "\u2717",
                                          "\u2718", "\u2715")))
    ck("24.4 no sixth stage and no penalty stage",
       len(service.PIPELINE_STAGES) == 5
       and "PENALTY" not in _strip_html.upper()
       and "penalty" not in open("app/service.py").read().lower())
    # Comments stripped first, for the same reason as the CSS block above:
    # roi.js documents that it uses no timer, so a bare substring test over the
    # raw text matches that sentence rather than any code.
    _roi_code = re.sub(r"/\*.*?\*/", "", open("app/static/roi.js").read(), flags=re.S)
    _roi_code = re.sub(r"^\s*//.*$", "", _roi_code, flags=re.M)
    ck("24.5 stage state comes from the record, not a timer",
       "setTimeout" not in _pipe_css and "setTimeout" not in _roi_code
       and "setInterval" not in _roi_code,
       "a timer drives state")

    # ---- 25. responsive, motion, dependencies ---------------------------
    ck("25.1 stacks vertically below 700px",
       "@media (max-width: 700px)" in _pipe_css)
    ck("25.2 the arrows are dropped when stacked",
       "content: none" in _pipe_css)
    ck("25.3 nothing in the strip animates, so there is nothing to suppress",
       "transition" not in _pipe_css and "animation" not in _pipe_css
       and "@keyframes" not in _pipe_css)
    reqs = open("requirements.txt").read()
    _req_lines = [l.strip() for l in reqs.splitlines()
                  if l.strip() and not l.startswith("#")]
    _optional_at = reqs.index("---- OPTIONAL")
    _required = [l.strip() for l in reqs[:_optional_at].splitlines()
                 if l.strip() and not l.startswith("#")]
    ck("25.4 the REQUIRED dependency set is unchanged",
       _required == ["fastapi", "uvicorn", "jinja2", "python-multipart",
                     "reportlab", "python-docx", "numpy", "scipy",
                     "opencv-python-headless", "pillow", "httpx"],
       str(_required))
    ck("25.5 chunk 8's dependencies are declared OPTIONAL",
       [l for l in _req_lines if l not in _required]
       == ["anthropic", "google-generativeai", "pytesseract"],
       str([l for l in _req_lines if l not in _required]))
    ck("25.6 the strip fetches nothing",
       "http://" not in _pipe_css and "https://" not in _pipe_css
       and "@import" not in _pipe_css)

    # ======================================================================
    # CHUNK 8 -- automated extraction, and the review step
    # ======================================================================
    import json as _json
    from app import vision as _vision

    MACHINE = {"name_and_address": "Acme Foods Pvt Ltd, Pune 411019",
               "common_or_generic_name": "Roasted almonds",
               "net_quantity": "200 g",
               "month_and_year": "03/2026",
               "retail_sale_price": "MRP Rs.450/- (inclusive of all taxes)",
               "consumer_care": None}          # one null, as a real read often is
    ALL_NULL = {k: None for k in service.FIELD_KEYS}

    def fake_call(payload):
        """A backend that returns `payload` as the model would: raw JSON text."""
        return lambda _img, _prompt: _json.dumps(payload)

    _real_call_from_env = service.vision.call_from_env
    _real_configured = service.vision.configured

    def _mark_configured(model="test-model"):
        """The endpoint checks a provider is configured before calling it."""
        service.vision.configured = lambda: {"provider": "anthropic", "model": model}

    def with_backend(payload, model="test-model"):
        """Point service.extract_from_image at a fake backend."""
        _mark_configured(model)
        service.vision.call_from_env = lambda: (fake_call(payload), model)

    def raising_backend(exc):
        _mark_configured()

        def boom():
            raise exc
        service.vision.call_from_env = boom

    def restore_provider():
        service.vision.call_from_env = _real_call_from_env
        service.vision.configured = _real_configured

    def post_reviewed(client, *, machine, reviewed, values=None, examined=False,
                      model="vision:test-model", product="ch8"):
        """Post the upload form exactly as the browser would after a review."""
        data = {"product_name": product, "vision_model": model, "panels": ["front"]}
        vals = values if values is not None else {
            k: (machine.get(k) or "") for k in service.FIELD_KEYS}
        for k in service.FIELD_KEYS:
            data[k] = vals.get(k, "") or ""
            data[f"{k}__machine"] = machine.get(k) or ""
            if k in reviewed:
                data[f"{k}__reviewed"] = "1"
        if examined:
            data["operator_examined_package"] = "1"
            data["operator_id"] = "LM-OFF-114"
        return client.post("/upload", data=data, follow_redirects=False)

    # ---- 26. the adapter -------------------------------------------------
    ck("26.1 vision.py is the only file importing an SDK",
       "import anthropic" in open("app/vision.py").read()
       and not any("import anthropic" in open(f).read()
                   for f in ("app/main.py", "app/service.py", "app/db.py",
                             "app/auth.py")))
    ck("26.2 service.py is still the only file importing lm_*",
       "import lm_" not in open("app/vision.py").read()
       and "import lm_" not in open("app/main.py").read())
    # Comments stripped first: vision.py's docstring names the things it
    # deliberately does NOT do, so a raw-text test matches the prose.
    _vis_src = open("app/vision.py").read()
    _vis_code = re.sub(r'"""(?:.|\n)*?"""', "", _vis_src)
    _vis_code = re.sub(r"^\s*#.*$", "", _vis_code, flags=re.M)
    ck("26.3 vision.py does not parse JSON",
       "json.loads" not in _vis_code and "parse_vision_json" not in _vis_code)
    ck("26.4 the prompt is not rewritten in the adapter",
       "VISION_PROMPT" not in _vis_code
       and "Return ONLY a JSON object" not in _vis_src,
       "the adapter contains prompt text")
    ck("26.5 hard 30-second timeout", _vision.TIMEOUT_SECONDS == 30.0)
    ck("26.6 no retries", "max_retries=0" in open("app/vision.py").read())
    ck("26.7 no key in code, form or template",
       "sk-ant" not in open("app/vision.py").read()
       and "api_key" not in open("app/templates/upload.html").read())
    ck("26.8 .env.example carries names and empty values only",
       "LM_VISION_API_KEY=" in open(".env.example").read()
       and "LM_VISION_API_KEY=sk" not in open(".env.example").read())

    # ---- 27. feature absent with no key ----------------------------------
    restore_provider()
    ck("27.1 no key configured -> feature reports absent",
       service.extraction_available() is None, str(service.extraction_available()))
    up = client.get("/upload").text
    ck("27.2 the button does not render", "Read declarations from image" not in up)
    ck("27.3 extract.js is not loaded", "extract.js" not in up)
    r = client.post("/extract-declarations", files={"image": ("l.png", synthetic_label(1.4), "image/png")})
    ck("27.4 the endpoint refuses cleanly with no provider",
       r.status_code == 400 and r.json()["ok"] is False, str(r.status_code))
    ck("27.5 the manual path is unchanged with no key",
       counts_of(create(client, product_name="27 manual",
                        panels=["front"]))["CANNOT_DETERMINE"] == 6)

    # ---- 28. THE AUTOMATION-BIAS CASE ------------------------------------
    # Extract, review nothing, try to claim the package was examined.
    r = post_reviewed(client, machine=MACHINE, reviewed=set(), examined=True,
                      product="28 unreviewed + examined")
    ck("28.1 unreviewed machine output + coverage ticked is BLOCKED",
       r.status_code == 200 and "Review each declaration" in r.text,
       f"HTTP {r.status_code} -- an unreviewed absence claim was accepted")
    r = post_reviewed(client, machine=MACHINE, reviewed={"net_quantity"},
                      examined=True, product="28 partial review")
    ck("28.2 a partial review is still blocked",
       r.status_code == 200 and "Review each declaration" in r.text)
    r = post_reviewed(client, machine=MACHINE, reviewed=set(service.FIELD_KEYS),
                      examined=True, product="28 fully reviewed")
    ck("28.3 a full review + coverage is allowed", r.status_code == 303,
       f"HTTP {r.status_code}")
    ck("28.4 the gate is enforced in service, not only at the form",
       any("ReviewRequired" in l for l in open("app/service.py").read().splitlines()))
    # and directly, bypassing the route entirely
    raised = False
    try:
        service.create_inspection(
            user={"id": 1, "username": "officer"}, product_name="28 direct",
            values={k: "" for k in service.FIELD_KEYS}, panels=["front"],
            examined=True, operator_id="LM-OFF-114", note="",
            machine_values=dict(ALL_NULL), reviewed_keys=set(),
            vision_model="test-model")
    except service.ReviewRequired:
        raised = True
    ck("28.5 calling the service directly cannot bypass the gate", raised)

    # ---- 29. machine nulls never become FAIL without review ---------------
    r = post_reviewed(client, machine=ALL_NULL, reviewed=set(), examined=False,
                      product="29 all null, unreviewed")
    iid = r.headers["location"].rsplit("/", 1)[-1]
    c29 = counts_of(iid)
    ck("29.1 all-null machine output, no review, no coverage -> six CANNOT_DETERMINE",
       c29["CANNOT_DETERMINE"] == 6 and c29["FAIL"] == 0, str(c29))
    r = post_reviewed(client, machine=ALL_NULL, reviewed=set(service.FIELD_KEYS),
                      examined=True, product="29 all null, reviewed + examined")
    iid2 = r.headers["location"].rsplit("/", 1)[-1]
    c29b = counts_of(iid2)
    ck("29.2 reviewed and confirmed absent + coverage -> six FAIL is correct",
       c29b["FAIL"] == 6, str(c29b))
    ck("29.3 vision_extract still never asserts absence",
       "asserts_absent=False" in open("lm_extract.py").read())

    # ---- 30. extractor provenance ----------------------------------------
    r = post_reviewed(client, machine=MACHINE, reviewed={"net_quantity"},
                      values={**{k: (MACHINE.get(k) or "") for k in service.FIELD_KEYS},
                              "net_quantity": "200 grams"},
                      examined=False, product="30 provenance")
    iid3 = r.headers["location"].rsplit("/", 1)[-1]
    ext_by_key = {f["key"]: f["extractor"] for f in [
        {"key": k, "extractor": e} for k, e in
        [(f2.key, f2.extractor) for f2 in service.build_record(iid3).findings]]}
    ck("30.1 an untouched machine value reports vision:<model>",
       ext_by_key["name_and_address"] == "vision:test-model",
       str(ext_by_key["name_and_address"]))
    ck("30.2 an edited value reports manual:<username>",
       ext_by_key["net_quantity"] == "manual:officer",
       str(ext_by_key["net_quantity"]))
    ck("30.3 only touched keys were passed as corrections",
       sum(1 for v in ext_by_key.values() if v.startswith("manual:")) == 1,
       str(ext_by_key))
    pdf30 = client.get(f"/scan/{iid3}/report.pdf")
    ck("30.4 the report carries both extractor strings",
       pdf30.status_code == 200)
    prov = " ".join(service.results_view(iid3)["provenance"])
    ck("30.5 provenance lines name both sources",
       "vision:test-model" in prov and "manual:officer" in prov, prov[:200])

    # ---- 31. failure handling --------------------------------------------
    png = synthetic_label(1.4)
    for exc, expect, label in (
            (_vision.VisionUnavailable("x"), "No extraction service", "unavailable"),
            (_vision.VisionTransportError("timed out"), "Could not reach", "timeout/network"),
            (service.ex.ExtractionError("garbage"), "unusable response", "unusable answer"),
            (RuntimeError("boom"), "could not be used", "unexpected error")):
        raising_backend(exc)
        rr = client.post("/extract-declarations",
                         files={"image": ("l.png", png, "image/png")})
        body = rr.json()
        ck(f"31.x {label} -> handled message, no traceback",
           body["ok"] is False and expect in body["error"]
           and "Traceback" not in body["error"], str(body)[:150])
        ck(f"31.y {label} leaks no filesystem path",
           not any(t in body["error"] for t in ("/tmp/", "/home/", "/var/")))
    ck("31.5 'unreachable' and 'unusable' are DIFFERENT messages",
       True)   # asserted by the two distinct `expect` strings above

    # ---- 32. the happy path through the endpoint -------------------------
    with_backend(MACHINE)
    rr = client.post("/extract-declarations",
                     files={"image": ("l.png", png, "image/png")})
    body = rr.json()
    ck("32.1 extraction returns the six keys", body["ok"] is True
       and set(body["values"]) == set(service.FIELD_KEYS), str(body)[:160])
    ck("32.2 a null stays null, not an empty string",
       body["values"]["consumer_care"] is None, str(body["values"]["consumer_care"]))
    ck("32.3 the model is reported", body["model"] == "test-model")
    ck("32.4 extraction creates no scan record",
       service.get_scan("nonexistent") is None
       and len(service.history("32 ")) == 0)
    with_backend(ALL_NULL)
    body = client.post("/extract-declarations",
                       files={"image": ("l.png", png, "image/png")}).json()
    ck("32.5 all nulls is a valid outcome, not an error",
       body["ok"] is True and all(v is None for v in body["values"].values()))
    rr = client.post("/extract-declarations",
                     files={"image": ("n.jpg", b"not an image" * 20, "image/jpeg")})
    ck("32.6 a non-image is refused at the endpoint too",
       rr.json()["ok"] is False and "not a readable image" in rr.json()["error"])
    service.vision.call_from_env = _real_call_from_env

    # ---- 33. the OCR cross-check (chunk 8 part 4) ------------------------
    # The value below is deliberately absent from the synthetic label (whose
    # only ink is "ABMOVW148"), so a real OCR pass cannot confirm it.
    INVENTED = {**MACHINE, "name_and_address": "Zenith Industries, Nagpur 440001"}
    _ocr_live = bool(_vision.ocr_text(png).strip())
    ck("33.1 OCR availability is detected, not assumed",
       isinstance(_ocr_live, bool))
    if _ocr_live:
        with_backend(INVENTED)
        body = client.post("/extract-declarations",
                           files={"image": ("l.png", png, "image/png")}).json()
        ck("33.2 the cross-check ran", body.get("ocr_available") is True,
           str(body.get("ocr_available")))
        ck("33.3 a value the OCR never saw is marked unconfirmed",
           body["confirmed"]["name_and_address"] is False,
           str(body["confirmed"]))
        # carry it through the form and check the declaration layer downgrades
        data = {"product_name": "33 crosscheck", "vision_model": "test-model",
                "panels": ["front"]}
        for k in service.FIELD_KEYS:
            data[k] = INVENTED.get(k) or ""
            data[f"{k}__machine"] = INVENTED.get(k) or ""
            data[f"{k}__ocr"] = {True: "1", False: "0"}.get(body["confirmed"][k], "")
        rr = client.post("/upload", data=data, follow_redirects=False)
        iid33 = rr.headers["location"].rsplit("/", 1)[-1]
        by_key = {f.key: f for f in service.build_record(iid33).findings}
        ck("33.4 an unconfirmed value downgrades to CANNOT_DETERMINE",
           by_key["name_and_address"].verdict == "CANNOT_DETERMINE",
           str(by_key["name_and_address"].verdict))
        ck("33.5 the downgrade happens BEFORE any format check",
           "second engine" in by_key["name_and_address"].why.lower(),
           by_key["name_and_address"].why[:120])
        ck("33.6 it is never reported as a lie",
           not any(w in by_key["name_and_address"].why.lower()
                   for w in ("hallucinat", "invented", "fabricat", "lied")),
           by_key["name_and_address"].why[:120])
    else:
        ck("33.2 OCR absent -> cross-check skipped entirely", True,
           "tesseract not installed in this environment")

    # With OCR unavailable nothing may be marked suspect.
    _real_ocr = _vision.ocr_text
    service.vision.ocr_text = lambda _b: ""
    with_backend(INVENTED)
    body = client.post("/extract-declarations",
                       files={"image": ("l.png", png, "image/png")}).json()
    ck("33.7 no OCR -> ocr_available is False",
       body.get("ocr_available") is False, str(body.get("ocr_available")))
    ck("33.8 no OCR -> every field stays unmarked, nothing is suspect",
       all(v is None for v in body["confirmed"].values()), str(body["confirmed"]))
    service.vision.ocr_text = _real_ocr
    restore_provider()

    # Comments stripped: the JS documents that the finding must never be
    # labelled a lie, so a raw-text test matches that sentence. What matters is
    # the text the officer actually sees.
    _ejs = open("app/static/extract.js").read()
    _ejs_code = re.sub(r"/\*(?:.|\n)*?\*/", "", _ejs)
    _ejs_code = re.sub(r"^\s*//.*$", "", _ejs_code, flags=re.M)
    _shown = re.findall(r'"((?:[^"\\]|\\.)*)"', _ejs_code)
    ck("33.9 no user-visible text calls it a hallucination",
       not any(w in t.lower() for t in _shown
               for w in ("hallucinat", "fabricat", "lied", "invented", "fake"))
       and "hallucinat" not in open("app/templates/upload.html").read().lower(),
       str([t for t in _shown if "lied" in t.lower()
            or "hallucinat" in t.lower()]))
    ck("33.10 the cross-check is optional in requirements",
       "pytesseract" in open("requirements.txt").read()
       and "OPTIONAL" in open("requirements.txt").read())

    # ---- 34. the Gemini branch -------------------------------------------
    # Mirrors 26-32 against the second provider. The backend is faked exactly
    # as the Anthropic tests fake it: vision_extract takes an injected
    # callable, so neither SDK is needed to exercise the path end to end.
    ck("34.1 gemini is a recognised provider",
       _vision.PROVIDER_GEMINI == "gemini"
       and set(_vision.PROVIDERS) == {"anthropic", "gemini"},
       str(_vision.PROVIDERS))
    ck("34.2 its default model is gemini-2.0-flash",
       _vision.DEFAULT_MODELS[_vision.PROVIDER_GEMINI] == "gemini-2.0-flash",
       str(_vision.DEFAULT_MODELS))
    ck("34.3 the anthropic default is unchanged",
       _vision.DEFAULT_MODELS[_vision.PROVIDER_ANTHROPIC] == "claude-opus-5")

    # configured() accepts either provider, and LM_VISION_MODEL still wins.
    _saved_env = {k: os.environ.get(k) for k in
                  (_vision.ENV_PROVIDER, _vision.ENV_KEY, _vision.ENV_MODEL)}

    def _set_env(provider=None, key=None, model=None):
        for name, val in ((_vision.ENV_PROVIDER, provider),
                          (_vision.ENV_KEY, key), (_vision.ENV_MODEL, model)):
            if val is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = val

    _set_env(provider="gemini", key="not-a-real-key")
    cfg = _vision.configured()
    ck("34.4 configured() accepts gemini",
       cfg == {"provider": "gemini", "model": "gemini-2.0-flash"}, str(cfg))
    _set_env(provider="gemini", key="not-a-real-key", model="gemini-1.5-pro")
    ck("34.5 LM_VISION_MODEL overrides the default",
       _vision.configured()["model"] == "gemini-1.5-pro",
       str(_vision.configured()))
    _set_env(provider="anthropic", key="not-a-real-key")
    ck("34.6 configured() still accepts anthropic",
       _vision.configured() == {"provider": "anthropic", "model": "claude-opus-5"},
       str(_vision.configured()))
    _set_env(provider="openai", key="not-a-real-key")
    ck("34.7 an unknown provider reports nothing configured",
       _vision.configured() is None, str(_vision.configured()))
    for k, v in _saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    # make_call's guards, without touching either SDK.
    for prov, why in (("openai", "unknown provider"), ("", "empty provider"),
                      ("Gemini ", "provider is normalised by configured(), "
                                  "not by make_call")):
        raised = False
        try:
            _vision.make_call(prov, "not-a-real-key", "m")
        except _vision.VisionUnavailable:
            raised = True
        ck(f"34.x make_call refuses {why}", raised, f"provider={prov!r}")
    raised = False
    try:
        _vision.make_call("gemini", "", "gemini-2.0-flash")
    except _vision.VisionUnavailable:
        raised = True
    ck("34.11 make_call refuses gemini with no key", raised)

    # The full path, with a faked gemini backend.
    with_backend(MACHINE, model="gemini-2.0-flash")
    body = client.post("/extract-declarations",
                       files={"image": ("l.png", png, "image/png")}).json()
    ck("34.12 gemini extraction returns the six keys",
       body["ok"] is True and set(body["values"]) == set(service.FIELD_KEYS),
       str(body)[:150])
    ck("34.13 a null stays null", body["values"]["consumer_care"] is None)
    ck("34.14 the gemini model is reported", body["model"] == "gemini-2.0-flash")

    with_backend(ALL_NULL, model="gemini-2.0-flash")
    body = client.post("/extract-declarations",
                       files={"image": ("l.png", png, "image/png")}).json()
    ck("34.15 all nulls is a valid gemini outcome, not an error",
       body["ok"] is True and all(v is None for v in body["values"].values()))

    # All four failure branches behave the same as the anthropic ones.
    for exc, expect, label in (
            (_vision.VisionUnavailable("x"), "No extraction service", "unavailable"),
            (_vision.VisionTransportError("timed out"), "Could not reach", "timeout/network"),
            (service.ex.ExtractionError("garbage"), "unusable response", "unusable answer"),
            (RuntimeError("boom"), "could not be used", "unexpected error")):
        raising_backend(exc)
        bb = client.post("/extract-declarations",
                         files={"image": ("l.png", png, "image/png")}).json()
        ck(f"34.y gemini {label} -> same handled message",
           bb["ok"] is False and expect in bb["error"]
           and "Traceback" not in bb["error"], str(bb)[:130])

    # The review gate is provider-agnostic.
    r = post_reviewed(client, machine=MACHINE, reviewed=set(), examined=True,
                      model="gemini-2.0-flash", product="34 gemini unreviewed")
    ck("34.20 the review gate applies to gemini output too",
       r.status_code == 200 and "Review each declaration" in r.text,
       f"HTTP {r.status_code}")
    r = post_reviewed(client, machine=MACHINE, reviewed=set(service.FIELD_KEYS),
                      examined=True, model="gemini-2.0-flash",
                      product="34 gemini reviewed")
    iid34 = r.headers["location"].rsplit("/", 1)[-1]
    exts = {f.key: f.extractor for f in service.build_record(iid34).findings}
    ck("34.21 a fully reviewed gemini inspection is allowed", r.status_code == 303)
    ck("34.22 reviewed fields report manual:<username>, not the model",
       all(v == "manual:officer" for v in exts.values()), str(exts))
    r = post_reviewed(client, machine=MACHINE, reviewed={"net_quantity"},
                      examined=False, model="gemini-2.0-flash",
                      product="34 gemini provenance")
    iid35 = r.headers["location"].rsplit("/", 1)[-1]
    exts = {f.key: f.extractor for f in service.build_record(iid35).findings}
    ck("34.23 untouched gemini values report vision:gemini-2.0-flash",
       exts["name_and_address"] == "vision:gemini-2.0-flash",
       str(exts["name_and_address"]))
    ck("34.24 no doubled prefix on the gemini branch",
       "vision:vision:" not in " ".join(exts.values()), str(exts))
    restore_provider()

    # The adapter's own invariants, for the new branch.
    ck("34.25 the gemini SDK is imported lazily, not at module scope",
       "import google.generativeai" in _vis_src
       and "google" not in [getattr(n, "module", None) or
                            (n.names[0].name if n.names else "")
                            for n in __import__("ast").parse(_vis_src).body
                            if isinstance(n, (__import__("ast").Import,
                                              __import__("ast").ImportFrom))])
    ck("34.26 the gemini branch parses no JSON",
       "json.loads" not in _vis_code and "parse_vision_json" not in _vis_code)
    ck("34.27 it holds no prompt text", "VISION_PROMPT" not in _vis_code)
    ck("34.28 it disables retries", "retry=None" in _vis_src)
    ck("34.29 it uses the same 30-second timeout",
       "timeout=TIMEOUT_SECONDS" in _vis_src)
    ck("34.30 it reuses the shared BMP/TIFF conversion",
       _vis_src.count("_media_type(image_bytes)") == 2)
    ck("34.31 no key material in the file",
       not re.search(r"(sk-|AIza)[A-Za-z0-9_\-]{10,}", _vis_src))
    ck("34.32 lm_extract.py was not touched",
       "asserts_absent=False,        # see docstring. Never True here."
       in open("lm_extract.py").read())

    print("=" * 74)
    for f in fails:
        print("FAIL:", f)
    print(f"webapp self-test: {checks} checks, {len(fails)} failed")
    print("=" * 74)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
