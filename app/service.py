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

import numpy as np
from PIL import Image, ImageDraw

import lm_declarations as dec
import lm_extract as ex
import lm_legal_model as legal
import lm_metrology_v7 as lm
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
    f"lm_metrology_v7 {lm.VERSION}",
)

# --------------------------------------------------------------------------
# Measurement -- the differentiator
# --------------------------------------------------------------------------
COMMODITY_CLASSES = (legal.COMMODITY_GENERAL, legal.COMMODITY_MEDICAL_DEVICE,
                     legal.COMMODITY_NOT_DECLARED)

# The engineering target below which RESOLUTION refuses every specimen. Read
# from the dataclass rather than restated, so the form's warning cannot drift
# away from the gate that actually fires.
MIN_PX_PER_MM = lm.CaptureLimits().min_px_per_mm

# Refusals that are about the IMAGE, not about the package. These get a
# re-capture remedy instead of a compliance outcome -- the gates already exist
# and are self-tested in lm_metrology_v7; this only surfaces them.
QUALITY_CODES = ("CONTRAST", "CLIPPED", "ILLUMINATION_GRADIENT", "RESOLUTION")

_REMEDY = {
    "CONTRAST": "Re-light and rescan: the ink-to-substrate contrast in this "
                "region is too low to locate the transition.",
    "CLIPPED": "Re-light and rescan at a lower exposure: highlights in this "
               "region are clipped, so the substrate level cannot be estimated.",
    "ILLUMINATION_GRADIENT": "Re-light and rescan: the illumination across this "
                             "region is uneven enough to move the transition.",
    "RESOLUTION": "Recapture closer, or re-run the scale session: there are too "
                  "few pixels per millimetre to support a height at this "
                  "uncertainty.",
}

# What the operator does next. Refusal-specific, because "refer for physical
# verification" is wrong advice for a threshold nobody has settled.
_NEXT_ACTION = {
    legal.BLOCK_THRESHOLD_DISPUTED:
        "The applicable minimum height is not settled in the sources this "
        "instrument holds. Resolve the rule before ruling on the package.",
    "MEASURAND_UNDEFINED":
        "Height on a blown, formed, moulded, embossed or perforated surface is "
        "not a defined measurand for this instrument. Verify physically.",
    legal.BLOCK_COMMODITY_NOT_DECLARED:
        "Declare the commodity class on the inspection and measure again.",
    legal.BLOCK_PDP_AREA_NOT_DECLARED:
        "Declare the principal display panel area on the inspection and "
        "measure again.",
}
_NEXT_DEFAULT = "Refer for physical verification."

# AUDIT-2026-09-12 Sec.2.1. Recorded on every measurement rather than folded
# into U: the number cannot be derived before the internal round, and a term
# invented under deadline is exactly what the uncertainty discipline exists to
# prevent. The region is made a visible declared input instead.
ROI_NOTE = ("The measured height depends on where this region was drawn: the "
            "ink and substrate levels are estimated from the region's own "
            "pixels. Measured spread on synthetic scenes is 0.0064 mm, biased "
            "toward the compliant direction. This is NOT in the uncertainty "
            "budget. The region is recorded as an operator-declared input.")


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
                      image_path: Optional[str] = None,
                      scale_ppm: Optional[float] = None,
                      scale_artifact: str = "", scale_artifact_tier: str = "",
                      declared_commodity_class: str = "",
                      declared_glyph_count: Optional[int] = None) -> str:
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
                                  coverage_note, headline, scale_ppm,
                                  scale_artifact, scale_artifact_tier,
                                  declared_commodity_class, declared_glyph_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (inspection_id, user["id"], datetime.datetime.now().isoformat(timespec="seconds"),
             image_path, product_name.strip(), declared_category or "",
             declared_pdp_area_cm2, ",".join(coverage.panels),
             1 if coverage.operator_examined_package else 0,
             coverage.operator_id, coverage.note, summary["headline"],
             scale_ppm, (scale_artifact or "").strip(),
             (scale_artifact_tier or "").strip(),
             (declared_commodity_class or "").strip(), declared_glyph_count))
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


def _measurement_headline(m) -> str:
    """The first line of the cream box. A refusal reads as deliberate, not broken."""
    if m.band == rep.BAND_COMPLIANT:
        return "COMPLIANT -- meets the minimum height"
    if m.band == rep.BAND_DEFICIENT:
        return "DEFICIENT -- below the minimum height"
    if m.refusal_code in QUALITY_CODES:
        return "IMAGE QUALITY -- this image cannot support a height"
    if m.refusal_code:
        return "INDETERMINATE -- no verdict from this image"
    return "INDETERMINATE -- physical verification required"


def _next_action(m) -> str:
    if m.band in (rep.BAND_COMPLIANT, rep.BAND_DEFICIENT):
        return ""
    if m.refusal_code in QUALITY_CODES:
        return _REMEDY[m.refusal_code]
    return _NEXT_ACTION.get(m.refusal_code, _NEXT_DEFAULT)


def _measurement_view(rec, scan: dict) -> dict:
    """The cream box, in every state it can be in.

    `state` is one of: measured, no_image, no_scale, not_measured. There is no
    fifth state in which a height is assumed from a DPI -- a pixel height
    divided by an assumed DPI is the naive method `naive_vs_calibrated.py`
    exists to discredit, and it is not offered here as a fallback, an option,
    or a form default.
    """
    m = rec.measurement
    size = image_size(scan)
    base = {
        "state": "measured" if m is not None else
                 ("no_image" if not scan["image_path"] else
                  ("no_scale" if scan["scale_ppm"] is None else "not_measured")),
        "image_w": size[0] if size else None,
        "image_h": size[1] if size else None,
        "scale_ppm": scan["scale_ppm"],
        "scale_artifact": scan["scale_artifact"] or "",
        "scale_artifact_tier": scan["scale_artifact_tier"] or "",
        "annotated": bool(scan["image_annotated_path"]),
        "attempts": 0, "earlier_regions": [],
    }
    con = db.connect()
    try:
        rows = con.execute(
            "SELECT roi_box FROM measurements WHERE scan_id=? ORDER BY id",
            (scan["id"],)).fetchall()
    finally:
        con.close()
    base["attempts"] = len(rows)
    base["earlier_regions"] = [r["roi_box"] for r in rows[:-1]]

    if m is None:
        return base
    base.update({
        "headline": _measurement_headline(m),
        "next_action": _next_action(m),
        "is_quality": m.refusal_code in QUALITY_CODES,
        "verdict": m.verdict(),
        "stated": m.stated(),
        "threshold": ("%.2f mm" % m.threshold_mm) if m.threshold_mm is not None
                     else "not resolved",
        "threshold_source_tier": m.threshold_source_tier or "not stated",
        "basis": m.band_explanation(),
        "convention": m.convention,
        "refusal_code": m.refusal_code,
        "refusal_detail": m.refusal_detail,
        "manifest": list(m.manifest),
        "roi_box": m.roi_box,
        "roi_note": ROI_NOTE,
    })
    return base


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
        "measurement": _measurement_view(rec, scan),
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


# --------------------------------------------------------------------------
# The measurement
# --------------------------------------------------------------------------
def _image_abspath(name: str) -> str:
    root = os.path.realpath(db.UPLOAD_DIR)
    path = os.path.realpath(os.path.join(root, os.path.basename(name)))
    if not path.startswith(root + os.sep):
        raise ValueError("image path escapes the upload directory")
    return path


def image_size(scan: dict) -> Optional[tuple[int, int]]:
    if not scan.get("image_path"):
        return None
    try:
        with Image.open(_image_abspath(scan["image_path"])) as im:
            return im.size
    except (OSError, ValueError):
        return None


def _crop_roi(scan: dict, box: tuple[int, int, int, int]) -> np.ndarray:
    """The CROPPED region, grayscale float in 0..1 -- what the engine measures.

    The engine measures whatever array it is handed; hand it a full frame and it
    hunts for ink across the platen and the packet edges. The crop is the point.
    """
    x, y, w, h = box
    with Image.open(_image_abspath(scan["image_path"])) as im:
        gray = im.convert("L")
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > gray.width or y + h > gray.height:
            raise ValueError("the selected region falls outside the image")
        arr = np.asarray(gray.crop((x, y, x + w, y + h)), dtype=np.float64)
    return arr / 255.0


def _annotate(scan: dict, box: tuple[int, int, int, int]) -> Optional[str]:
    """Draw the region on a COPY. The original evidence image is untouched."""
    x, y, w, h = box
    src = _image_abspath(scan["image_path"])
    stem = os.path.splitext(os.path.basename(src))[0]
    out_name = f"{stem}.roi.png"
    try:
        with Image.open(src) as im:
            canvas = im.convert("RGB")
        d = ImageDraw.Draw(canvas)
        width = max(2, round(min(canvas.size) / 400))
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=(10, 22, 40), width=width)
        label = "operator-declared region"
        ty = y - 12 if y >= 12 else y + h + 2
        if ty + 10 > canvas.height:
            ty = max(0, y + 2)
        d.text((x + 2, ty), label, fill=(10, 22, 40))
        canvas.save(os.path.join(db.UPLOAD_DIR, out_name))
    except (OSError, ValueError):
        return None
    return out_name


def _threshold_source_tier(v) -> str:
    """Tier and confidence only.

    `Provenance.corrigendum` describes a value change and therefore contains
    candidate millimetres; it is never read here. lm_legal_model's own self-test
    asserts no report line contains it.
    """
    res = v.diagnostics.get("legal_resolution")
    if res is None or res.bracket is None:
        return ""
    p = res.bracket.provenance
    return f"{p.source_tier} / {p.confidence}"


def _measurement_from_verdict(v, scan: dict, box, attempt: int) -> rep.Measurement:
    """Verdict -> the storage contract in lm_report.Measurement.

    `height_mm` and `u_mm` are passed straight through. If the engine ever
    returned one without the other, `Measurement.__post_init__` raises and this
    call fails loudly -- that exception is how invariant 6 is enforced and it is
    deliberately not caught.
    """
    lines = tuple(lm.legal_report_lines(v))       # () on the legacy path
    convention = next(
        (l.split(":", 1)[1].strip() for l in lines if "MEASUREMENT CONVENTION" in l),
        "max_supported")

    manifest: list[str] = [
        f"measurement attempt      : {attempt}",
        f"scale reference          : {scan['scale_ppm']:.6g} px/mm, operator-entered",
        f"scale artifact           : {scan['scale_artifact'] or 'not described'}",
        f"scale artifact tier      : {scan['scale_artifact_tier'] or 'not stated'}",
        f"region measured          : x={box[0]} y={box[1]} w={box[2]} h={box[3]} px "
        f"(operator-declared region)",
        f"ROI sensitivity          : {ROI_NOTE}",
    ]
    for r in v.refusals:
        manifest.append(f"refusal                  : {r.code}: {r.detail}")
    manifest.extend(lines)

    first = v.refusals[0] if v.refusals else None
    return rep.Measurement(
        band=v.band, height_mm=v.h_mm, u_mm=v.U_mm,
        threshold_mm=v.threshold_mm, convention=convention,
        refusal_code=first.code if first else None,
        refusal_detail=first.detail if first else "",
        threshold_source_tier=_threshold_source_tier(v),
        manifest=tuple(manifest), roi_box=tuple(box))


def measure_scan(inspection_id: str, box) -> tuple[bool, str]:
    """Measure the operator-declared region. Returns (ok, message).

    Rows are APPENDED, never replaced. Re-drawing the region changes the number
    (AUDIT Sec.2.1) and that is precisely the hand this project does not want
    hidden: every attempt stays on the record, and the results page says how
    many there have been.
    """
    scan = get_scan(inspection_id)
    if scan is None:
        return False, "No such inspection."
    if not scan["image_path"]:
        return False, "There is no evidence image on this inspection to measure."
    if scan["scale_ppm"] is None:
        return False, ("No scale reference was recorded for this inspection, so "
                       "there is nothing to convert pixels into millimetres.")
    try:
        box = tuple(int(round(float(b))) for b in box)
        if len(box) != 4:
            raise ValueError
    except (TypeError, ValueError):
        return False, "The selected region was not four numbers."

    try:
        roi = _crop_roi(scan, box)
    except (OSError, ValueError) as exc:
        return False, str(exc) or "The evidence image could not be read."

    ppm = float(scan["scale_ppm"])
    glyphs = scan["declared_glyph_count"] or None
    commodity = scan["declared_commodity_class"] or legal.COMMODITY_NOT_DECLARED

    verdict = lm.measure_with_category(
        roi, ppm, lm.RULES_2011,
        scan["declared_category"] or None,
        limits=lm.CaptureLimits(expected_glyphs=glyphs),
        budget=lm.provisional_budget(),
        convention="max_supported",
        convention_bias_mm=0.0,
        commodity_class=commodity,
        pdp_area_cm2=scan["declared_pdp_area_cm2"],
        as_of=datetime.date.today(),
    )

    con = db.connect()
    try:
        attempt = con.execute("SELECT COUNT(*) c FROM measurements WHERE scan_id=?",
                              (scan["id"],)).fetchone()["c"] + 1
    finally:
        con.close()

    m = _measurement_from_verdict(verdict, scan, box, attempt)
    annotated = _annotate(scan, box)

    con = db.connect()
    try:
        con.execute(
            """INSERT INTO measurements (scan_id, band, height_mm, u_mm,
                    threshold_mm, convention, refusal_code, refusal_detail,
                    threshold_source_tier, manifest, roi_box)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (scan["id"], m.band, m.height_mm, m.u_mm, m.threshold_mm,
             m.convention, m.refusal_code, m.refusal_detail,
             m.threshold_source_tier, "\n".join(m.manifest),
             ",".join(str(b) for b in m.roi_box)))
        if annotated:
            con.execute("UPDATE scans SET image_annotated_path=? WHERE id=?",
                        (annotated, scan["id"]))
        con.commit()
    finally:
        con.close()
    return True, "Measurement recorded."
