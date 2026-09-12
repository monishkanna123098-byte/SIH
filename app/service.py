"""The only module permitted to import `lm_*`.

Routes call `service`; `service` calls the engines. The invariants are then
enforceable in one reviewable file instead of scattered through request
handlers -- which is the whole reason for the rule.

Three of them live here in particular:
  * absence is only ever claimed through `Coverage.can_assert_absence()`
    (invariant 2). This module never constructs an `ExtractedField` by hand;
    it goes through `lm_extract.manual_extract`, which owns that decision.
  * verdicts and tiers are whatever the engines returned (invariants 1 and 3).
    Nothing here maps three states onto two.
  * `summarise()` has no score field and nothing here invents one (invariant 4).
"""
from __future__ import annotations

import datetime
import os
from typing import Optional

import lm_declarations as dec
import lm_extract as ex
import lm_report as rep

from . import db

# Re-exported so routes and templates never need to import lm_* themselves.
FIELD_KEYS = ex.FIELD_KEYS
TIER_NOTE = rep.TIER_NOTE
TIER_ORDER = (dec.TIER_EXTRACTED, dec.TIER_MEASURED, dec.TIER_DETERMINED)
VERDICT_PASS = dec.VERDICT_PASS
VERDICT_FAIL = dec.VERDICT_FAIL
VERDICT_CANNOT_DETERMINE = dec.VERDICT_CANNOT_DETERMINE
HASH_NOTE = rep.HASH_NOTE

PANELS = ("front", "back", "top", "bottom", "side")
CATEGORIES = ("general", "blown_formed_moulded_embossed_perforated")

ENGINE_VERSIONS = (
    f"lm_declarations {dec.VERSION}",
    f"lm_extract {ex.VERSION}",
    f"lm_report {rep.VERSION}",
)


def declaration_fields() -> list[dict]:
    """(key, label, expected) for the six inputs on the upload form."""
    return [{"key": d.key, "label": d.label, "expected": d.expected}
            for d in dec.DECLARATIONS]


# --------------------------------------------------------------------------
# Creating an inspection
# --------------------------------------------------------------------------
def _next_inspection_id(con) -> str:
    today = datetime.date.today().strftime("%Y%m%d")
    n = con.execute(
        "SELECT COUNT(*) AS c FROM scans WHERE inspection_id LIKE ?",
        (f"LM-{today}-%",)).fetchone()["c"]
    while True:
        n += 1
        candidate = f"LM-{today}-{n:04d}"
        if con.execute("SELECT 1 FROM scans WHERE inspection_id=?",
                       (candidate,)).fetchone() is None:
            return candidate


def build_coverage(panels, examined: bool, operator_id: str,
                   note: str) -> ex.Coverage:
    return ex.Coverage(panels=tuple(p for p in panels if p in PANELS),
                       operator_examined_package=bool(examined),
                       operator_id=(operator_id or "").strip(),
                       note=(note or "").strip())


def create_inspection(*, user: dict, product_name: str, values: dict,
                      panels, examined: bool, operator_id: str, note: str,
                      declared_category: str = "",
                      declared_pdp_area_cm2: Optional[float] = None,
                      image_path: Optional[str] = None) -> str:
    """Run the extraction + declaration checks and persist the result.

    `values` maps declaration key -> the text the officer read off the package,
    blank for "not found". Whether a blank becomes FAIL or CANNOT_DETERMINE is
    decided by `Coverage`, inside `manual_extract` -- never here.
    """
    coverage = build_coverage(panels, examined, operator_id, note)
    fields = ex.manual_extract(values, coverage, operator=user["username"])
    findings = dec.check_declarations(fields)
    summary = dec.summarise(findings)

    con = db.connect()
    try:
        inspection_id = _next_inspection_id(con)
        cur = con.execute(
            """INSERT INTO scans (inspection_id, user_id, created_at, image_path,
                                  product_name, declared_category,
                                  declared_pdp_area_cm2, coverage_panels,
                                  coverage_examined, coverage_operator_id,
                                  coverage_note, headline)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (inspection_id, user["id"], datetime.datetime.now().isoformat(timespec="seconds"),
             image_path, product_name.strip(), declared_category or "",
             declared_pdp_area_cm2, ",".join(coverage.panels),
             1 if coverage.operator_examined_package else 0,
             coverage.operator_id, coverage.note, summary["headline"]))
        scan_id = cur.lastrowid
        for f in findings:
            ef = fields.get(f.key)
            con.execute(
                """INSERT INTO findings (scan_id, declaration_key, verdict,
                                         source_tier, detected, why, citation,
                                         extractor, verbatim_confirmed)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (scan_id, f.key, f.verdict, f.source_tier, f.detected, f.why,
                 f.citation.printable(), f.extractor,
                 None if ef is None or ef.verbatim_confirmed is None
                 else int(ef.verbatim_confirmed)))
        con.commit()
    finally:
        con.close()
    return inspection_id


# --------------------------------------------------------------------------
# Reading one back
# --------------------------------------------------------------------------
def get_scan(inspection_id: str) -> Optional[dict]:
    con = db.connect()
    try:
        row = con.execute(
            """SELECT s.*, u.username AS officer_username, u.role AS officer_role
               FROM scans s JOIN users u ON u.id = s.user_id
               WHERE s.inspection_id=?""", (inspection_id,)).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def _coverage_of(scan: dict) -> ex.Coverage:
    panels = tuple(p for p in (scan["coverage_panels"] or "").split(",") if p)
    return ex.Coverage(panels=panels,
                       operator_examined_package=bool(scan["coverage_examined"]),
                       operator_id=scan["coverage_operator_id"] or "",
                       note=scan["coverage_note"] or "")


def _rows(con, table: str, scan_id: int):
    return con.execute(f"SELECT * FROM {table} WHERE scan_id=? ORDER BY id",
                       (scan_id,)).fetchall()


def _rebuild(scan: dict, con):
    """Reconstruct engine objects from stored rows.

    Findings are rebuilt against the canonical `DECLARATIONS`, so the label,
    the expected-text and the `Citation` -- with its unverified sub-clause
    still unprinted (invariant 7) -- come from the legal layer rather than
    from whatever was stored. The stored citation string is the audit trail of
    what was printed at the time; it is not the source of truth for reprints.
    """
    coverage = _coverage_of(scan)
    can_assert = coverage.can_assert_absence()
    findings, fields = [], {}
    for r in _rows(con, "findings", scan["id"]):
        d = dec.DECLARATION_BY_KEY.get(r["declaration_key"])
        if d is None:
            continue
        vc = None if r["verbatim_confirmed"] is None else bool(r["verbatim_confirmed"])
        findings.append(dec.Finding(
            key=d.key, label=d.label, verdict=r["verdict"],
            source_tier=r["source_tier"], detected=r["detected"],
            expected=d.expected, why=r["why"] or "", citation=d.citation,
            extractor=r["extractor"] or "unspecified"))
        fields[d.key] = dec.ExtractedField(
            value=r["detected"], asserts_absent=(not r["detected"]) and can_assert,
            extractor=r["extractor"] or "unspecified", verbatim_confirmed=vc)

    # Chunk 4 leaves `measurements` empty; chunk 5 fills it. Reading the table
    # here rather than hard-coding None means chunk 5 only has to INSERT.
    measurement = None
    mrow = _rows(con, "measurements", scan["id"])
    if mrow:
        m = mrow[-1]
        roi = None
        if m["roi_box"]:
            try:
                roi = tuple(int(x) for x in m["roi_box"].split(","))
            except ValueError:
                roi = None
        measurement = rep.Measurement(
            band=m["band"], height_mm=m["height_mm"], u_mm=m["u_mm"],
            threshold_mm=m["threshold_mm"], convention=m["convention"] or "",
            refusal_code=m["refusal_code"], refusal_detail=m["refusal_detail"] or "",
            threshold_source_tier=m["threshold_source_tier"] or "",
            manifest=tuple((m["manifest"] or "").splitlines()),
            roi_box=roi if roi and len(roi) == 4 else None)

    determination = None
    drow = _rows(con, "determinations", scan["id"])
    if drow:
        d_ = drow[-1]
        on = None
        if d_["determined_on"]:
            try:
                on = datetime.date.fromisoformat(d_["determined_on"])
            except ValueError:
                on = None
        determination = rep.OfficerDetermination(
            officer_id=d_["officer_id"], verdict=d_["verdict"],
            note=d_["note"] or "", determined_on=on)

    return coverage, tuple(findings), fields, measurement, determination


def build_record(inspection_id: str) -> Optional[rep.InspectionRecord]:
    scan = get_scan(inspection_id)
    if scan is None:
        return None
    con = db.connect()
    try:
        coverage, findings, fields, measurement, determination = _rebuild(scan, con)
    finally:
        con.close()
    try:
        inspected_on = datetime.datetime.fromisoformat(scan["created_at"]).date()
    except ValueError:
        inspected_on = datetime.date.today()
    return rep.InspectionRecord(
        inspection_id=scan["inspection_id"], inspected_on=inspected_on,
        officer_id=scan["officer_username"], product_name=scan["product_name"],
        findings=findings, coverage_description=coverage.describe(),
        extraction_provenance=ex.extraction_provenance_lines(fields, coverage),
        measurement=measurement, determination=determination,
        declared_category=scan["declared_category"] or "",
        declared_pdp_area_cm2=scan["declared_pdp_area_cm2"],
        engine_versions=ENGINE_VERSIONS)


def results_view(inspection_id: str) -> Optional[dict]:
    """Everything the results template needs, as plain data.

    Templates never touch an lm_* object, so a template change cannot quietly
    reinterpret a verdict.
    """
    scan = get_scan(inspection_id)
    if scan is None:
        return None
    rec = build_record(inspection_id)
    s = rec.summary()
    m = rec.measurement
    return {
        "scan": scan,
        "headline": s["headline"],
        "counts": s["counts"],
        "n": s["n"],
        "findings": [{
            "verdict": f.verdict, "label": f.label, "detected": f.detected,
            "why": f.why, "citation": f.citation.printable(),
            "tier": f.source_tier, "extractor": f.extractor,
            "chain": f.chain(),
        } for f in rec.findings],
        "measurement": None if m is None else {
            "verdict": m.verdict(), "stated": m.stated(),
            "threshold": ("%.2f mm" % m.threshold_mm) if m.threshold_mm is not None
                         else "not resolved",
            "threshold_source_tier": m.threshold_source_tier or "not stated",
            "basis": m.band_explanation(), "convention": m.convention,
            "refusal_code": m.refusal_code, "manifest": list(m.manifest),
            "roi_box": m.roi_box,
        },
        "determination": None if rec.determination is None else {
            "officer_id": rec.determination.officer_id,
            "verdict": rec.determination.verdict,
            "note": rec.determination.note,
            "determined_on": (rec.determination.determined_on.isoformat()
                              if rec.determination.determined_on else ""),
        },
        "tier_notes": [(t, TIER_NOTE[t]) for t in TIER_ORDER],
        "coverage_description": rec.coverage_description,
        "provenance": [l for l in rec.extraction_provenance],
        "engine_versions": list(rec.engine_versions),
        "content_hash": rec.content_hash(),
        "hash_note": HASH_NOTE,
    }


# --------------------------------------------------------------------------
# Determination, reports, history, dashboard
# --------------------------------------------------------------------------
def record_determination(inspection_id: str, officer_id: str, verdict: str,
                         note: str) -> bool:
    scan = get_scan(inspection_id)
    if scan is None or not verdict.strip():
        return False
    con = db.connect()
    try:
        con.execute(
            """INSERT INTO determinations (scan_id, officer_id, verdict, note,
                                           determined_on)
               VALUES (?,?,?,?,?)""",
            (scan["id"], officer_id, verdict.strip(), note.strip(),
             datetime.date.today().isoformat()))
        con.commit()
    finally:
        con.close()
    return True


def write_report(inspection_id: str, fmt: str) -> Optional[str]:
    rec = build_record(inspection_id)
    if rec is None:
        return None
    os.makedirs(db.REPORT_DIR, exist_ok=True)
    path = os.path.join(db.REPORT_DIR, f"{inspection_id}.{fmt}")
    if fmt == "pdf":
        return rep.render_pdf(rec, path)
    if fmt == "docx":
        return rep.render_docx(rec, path)
    return None


def history(query: str = "") -> list[dict]:
    """Newest first. Search across product name, inspection id and officer."""
    sql = """SELECT s.*, u.username AS officer_username,
                    (SELECT COUNT(*) FROM findings f
                      WHERE f.scan_id=s.id AND f.verdict='PASS') AS n_pass,
                    (SELECT COUNT(*) FROM findings f
                      WHERE f.scan_id=s.id AND f.verdict='FAIL') AS n_fail,
                    (SELECT COUNT(*) FROM findings f
                      WHERE f.scan_id=s.id AND f.verdict='CANNOT_DETERMINE')
                      AS n_cannot
             FROM scans s JOIN users u ON u.id=s.user_id"""
    args: tuple = ()
    q = (query or "").strip()
    if q:
        sql += (" WHERE s.product_name LIKE ? OR s.inspection_id LIKE ?"
                " OR u.username LIKE ?")
        args = (f"%{q}%", f"%{q}%", f"%{q}%")
    sql += " ORDER BY s.created_at DESC, s.id DESC"
    con = db.connect()
    try:
        return [dict(r) for r in con.execute(sql, args).fetchall()]
    finally:
        con.close()


def dashboard() -> dict:
    """Counts. Not a rate, not a percentage, not a grade -- invariant 4.

    A percentage would imply the six declarations are commensurable and that
    CANNOT_DETERMINE can be averaged with PASS. Neither is true.
    """
    con = db.connect()
    try:
        total = con.execute("SELECT COUNT(*) c FROM scans").fetchone()["c"]

        def with_verdict(v: str) -> int:
            return con.execute(
                """SELECT COUNT(DISTINCT scan_id) c FROM findings
                   WHERE verdict=?""", (v,)).fetchone()["c"]

        any_fail = with_verdict(VERDICT_FAIL)
        any_cannot = con.execute(
            """SELECT COUNT(*) c FROM scans s
               WHERE EXISTS (SELECT 1 FROM findings f WHERE f.scan_id=s.id
                              AND f.verdict='CANNOT_DETERMINE')
                 AND NOT EXISTS (SELECT 1 FROM findings f WHERE f.scan_id=s.id
                                  AND f.verdict='FAIL')""").fetchone()["c"]
        clean = con.execute(
            """SELECT COUNT(*) c FROM scans s
               WHERE EXISTS (SELECT 1 FROM findings f WHERE f.scan_id=s.id)
                 AND NOT EXISTS (SELECT 1 FROM findings f WHERE f.scan_id=s.id
                                  AND f.verdict IN ('FAIL','CANNOT_DETERMINE'))"""
        ).fetchone()["c"]
    finally:
        con.close()
    return {"total": total, "any_fail": any_fail,
            "any_cannot": any_cannot, "clean": clean,
            "recent": history()[:10]}
