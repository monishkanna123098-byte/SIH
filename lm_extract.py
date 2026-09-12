#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lm_extract.py -- image (or officer) to structured declarations.

WHAT THIS IS. The adapter between a photograph and `lm_declarations.py`. It
produces `ExtractedField` objects and nothing else; it makes no compliance
judgements, cites no rules, and has no opinion about whether a packet passes.

THREE COMMITMENTS, AND THE FIRST ONE IS THE WHOLE MODULE:

  1. SOFTWARE NEVER ASSERTS ABSENCE. A photograph of one face of a package can
     establish that a declaration was NOT IN FRAME. It cannot establish that
     the declaration is NOT ON THE PACKAGE. Those are different claims and only
     the second one is a violation. So `asserts_absent` is driven by an
     explicit human COVERAGE DECLARATION -- never by model confidence, never by
     "we looked hard", never by a threshold. See `Coverage`.

     Every competing approach gets this wrong in the same direction, because
     asserting absence is what makes a demo look decisive. It is also what
     turns a missed OCR read into an accusation against a packer.

  2. NO NETWORK, NO SDK, AT IMPORT TIME. The vision backend takes a CALLABLE.
     This module imports and self-tests on a machine with no API key, no
     internet and no vision library installed. That is not tidiness -- it is
     the mitigation for the likeliest demo-day failure, which is venue wifi.
     The manual path below is a first-class input, not a fallback.

  3. A VALUE THE OCR NEVER SAW IS SUSPECT. If a vision model reports an MRP of
     "Rs. 250" and a plain OCR dump of the same image contains no "250"
     anywhere, the model may have read it -- or may have produced it. This
     module cannot tell which, so it marks the field unconfirmed and lets the
     declaration layer downgrade it. See `crosscheck_verbatim`.

WHAT THIS MODULE DOES NOT DO:
  - It does not do OCR itself. Pass it text from whatever engine you have.
  - It does not measure anything. Character height is the metrology engine's,
    and the separation is the point.
  - It does not retry, cache, or rate-limit. That belongs to the caller.

RUN: python3 lm_extract.py      (self-test, fully offline)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Callable, Optional

from lm_declarations import (
    DECL_COMMON_NAME,
    DECL_CONSUMER_CARE,
    DECL_DATE,
    DECL_NAME_ADDRESS,
    DECL_NET_QUANTITY,
    DECL_RETAIL_PRICE,
    DECLARATIONS,
    ExtractedField,
)

VERSION = "1.0-chunk2-2026-09-12"

# The keys the vision model is asked to return. Kept identical to the
# declaration keys so there is no translation table to drift out of sync.
FIELD_KEYS = tuple(d.key for d in DECLARATIONS)


# --------------------------------------------------------------------------
# Coverage -- the only thing that can unlock an absence claim
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Coverage:
    """What was actually examined, declared by a human.

    `operator_examined_package` is the ONLY route to asserting absence, and it
    means something specific: a person had the physical package in their hands,
    turned it over, and looked. Not "we uploaded four photos". Not "the model
    reported high confidence". A person looked.

    Why so strict: the failure this prevents is silent and one-directional. If
    absence can be asserted by software, then every OCR miss becomes a recorded
    non-compliance against a named packer, at whatever scale the system runs.
    There is no symmetric error -- refusing to assert absence costs a
    CANNOT_DETERMINE, which is a true statement about what we know.

    `panels` is recorded for the report and deliberately does NOT unlock
    absence, however many panels it lists. Software cannot certify that the set
    of panels it was handed is the complete set.
    """

    panels: tuple[str, ...] = ()
    operator_examined_package: bool = False
    operator_id: str = ""
    note: str = ""

    def can_assert_absence(self) -> bool:
        return bool(self.operator_examined_package and self.operator_id)

    def describe(self) -> str:
        p = ", ".join(self.panels) if self.panels else "unspecified"
        if self.can_assert_absence():
            return (f"panels captured: {p}; physical package examined by "
                    f"{self.operator_id} -- absence may be asserted")
        return (f"panels captured: {p}; physical package NOT examined -- "
                f"absence cannot be asserted, missing fields report as "
                f"CANNOT_DETERMINE")


# --------------------------------------------------------------------------
# The vision prompt
# --------------------------------------------------------------------------
# Written to make NOT ANSWERING the easy path. Most extraction prompts push a
# model toward filling every field; on a compliance tool that pressure turns
# directly into invented declarations.
VISION_PROMPT = """You are reading a photograph of an Indian packaged commodity label.

Return ONLY a JSON object. No preamble, no markdown fences, no explanation.

Keys, all required:
  "name_and_address"        manufacturer/packer/importer name and address
  "common_or_generic_name"  what the commodity is
  "net_quantity"            net quantity with its unit, verbatim
  "month_and_year"          month and year of manufacture/packing/import
  "retail_sale_price"       the MRP line, verbatim, INCLUDING any wording
                            about taxes if it appears next to the price
  "consumer_care"           consumer care contact details

RULES, IN ORDER OF IMPORTANCE:
1. Copy text VERBATIM from the image. Do not normalise, correct, translate,
   expand abbreviations, or reformat. "Rs.250/-" stays "Rs.250/-".
2. If a field is not legible in this image, return null for it. Returning null
   is CORRECT and expected. Do not infer a value from context, from the brand,
   from typical packaging, or from another field.
3. Never guess. An unreadable field is null, not a best effort.
4. Return null rather than a partial value you are unsure of.

Return the JSON object only."""


# --------------------------------------------------------------------------
# Manual entry -- a first-class path, not a fallback
# --------------------------------------------------------------------------
def manual_extract(values: dict, coverage: Coverage,
                   operator: str = "officer") -> dict[str, ExtractedField]:
    """Officer-typed declarations.

    `values` maps declaration key -> the text the officer read off the package,
    or None for "not present". A None only becomes an absence CLAIM if the
    coverage says a human examined the package; otherwise it stays undetermined,
    exactly as if a model had failed to read it.

    This path exists for three reasons and only one of them is demo safety:
      - it works with no network, no key and no vision library;
      - it is what an officer does to CORRECT machine output, which is the
        realistic workflow this software sits inside;
      - it is the only path that can legitimately assert absence.
    """
    out: dict[str, ExtractedField] = {}
    can_assert = coverage.can_assert_absence()
    for key in FIELD_KEYS:
        raw = values.get(key)
        text = raw.strip() if isinstance(raw, str) else None
        out[key] = ExtractedField(
            value=text or None,
            asserts_absent=(not text) and can_assert,
            extractor=f"manual:{operator}",
            verbatim_confirmed=True if text else None)
    return out


# --------------------------------------------------------------------------
# Vision backend -- injectable, so this file never imports an SDK
# --------------------------------------------------------------------------
class ExtractionError(Exception):
    """Raised when a backend returns something unusable.

    Deliberately NOT swallowed into empty fields. A caller that cannot tell
    "the model said nothing was legible" from "the model returned garbage"
    will eventually report the second as the first, and six CANNOT_DETERMINEs
    look like a bad photograph rather than a broken pipeline.
    """


def parse_vision_json(raw: str) -> dict:
    """Pull a JSON object out of a model response, tolerantly but not loosely.

    Tolerant about: markdown fences, leading prose, trailing prose.
    NOT tolerant about: absent object, unparseable object, non-dict result.
    Those raise, per the note on ExtractionError.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ExtractionError("backend returned an empty response")

    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ExtractionError(
                "no JSON object found in the backend response")
        try:
            obj = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"response was not valid JSON: {exc}") from exc

    if not isinstance(obj, dict):
        raise ExtractionError(
            f"expected a JSON object, got {type(obj).__name__}")
    return obj


def vision_extract(image_bytes: bytes,
                   call: Callable[[bytes, str], str],
                   coverage: Coverage,
                   backend_name: str = "vision") -> dict[str, ExtractedField]:
    """Run a vision backend and normalise its output.

    `call(image_bytes, prompt) -> str` is supplied by the caller. This module
    does not know or care whether that is Gemini, Claude, GPT, or a local
    model, and it never imports one.

    NOTE WHAT IS ABSENT HERE: asserts_absent is False for every field this
    function produces, unconditionally, regardless of coverage. Even when an
    officer HAS examined the package, a null from a model is a null from a
    model -- it is evidence about the image, not about the package. Absence
    claims come from `manual_extract`, where a human typed the None.
    """
    raw = call(image_bytes, VISION_PROMPT)
    obj = parse_vision_json(raw)

    out: dict[str, ExtractedField] = {}
    for key in FIELD_KEYS:
        v = obj.get(key)
        if isinstance(v, (int, float)):
            v = str(v)
        if isinstance(v, str):
            v = v.strip()
            # Models sometimes spell null as text. Treat those as null rather
            # than as a declaration reading "not visible".
            if v.lower() in ("", "null", "none", "n/a", "na", "not visible",
                             "not legible", "unknown", "-"):
                v = None
        elif v is not None:
            v = None      # lists, dicts, bools: unusable as a declaration

        out[key] = ExtractedField(
            value=v,
            asserts_absent=False,        # see docstring. Never True here.
            extractor=backend_name,
            verbatim_confirmed=None)     # unknown until cross-checked
    return out


# --------------------------------------------------------------------------
# Hallucination cross-check
# --------------------------------------------------------------------------
def _norm(s: str) -> str:
    """Lowercase, strip punctuation and whitespace, for loose containment."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def crosscheck_verbatim(fields: dict[str, ExtractedField], ocr_text: str,
                        min_token_len: int = 3) -> dict[str, ExtractedField]:
    """Mark values that a plain OCR dump of the same image never saw.

    METHOD, AND ITS LIMITS. A value is confirmed if enough of its longer tokens
    appear in the OCR text. This is deliberately loose: OCR and a vision model
    disagree constantly about spacing, case and punctuation, and a strict match
    would flag almost everything.

    WHAT A False MEANS, AND WHAT IT DOES NOT. `verbatim_confirmed=False` means
    "no OCR engine on this image saw these characters". That is consistent with
    a hallucination. It is ALSO consistent with OCR being worse than the vision
    model, which is common on curved, glossy and low-contrast packaging -- the
    normal condition of the packets this system is for. So a False downgrades a
    finding to CANNOT_DETERMINE. It must never be reported as evidence that the
    model lied, and it must never be reported to a packer at all.

    An empty `ocr_text` means no cross-check was possible: everything stays
    None, nothing is marked suspect. Absent evidence, again, is not evidence.
    """
    if not ocr_text or not ocr_text.strip():
        return dict(fields)

    hay = _norm(ocr_text)
    out: dict[str, ExtractedField] = {}
    for key, ef in fields.items():
        if not ef.value or ef.verbatim_confirmed is True:
            out[key] = ef
            continue
        tokens = [t for t in re.split(r"\s+", ef.value) if len(_norm(t)) >= min_token_len]
        if not tokens:
            # Value is all short tokens ("5 g"). Too little to judge on.
            out[key] = replace(ef, verbatim_confirmed=None)
            continue
        hits = sum(1 for t in tokens if _norm(t) and _norm(t) in hay)
        out[key] = replace(ef, verbatim_confirmed=(hits >= max(1, len(tokens) // 2)))
    return out


# --------------------------------------------------------------------------
# Merge -- machine first, officer last
# --------------------------------------------------------------------------
def apply_officer_corrections(machine: dict[str, ExtractedField],
                              corrections: dict,
                              coverage: Coverage,
                              operator: str = "officer") -> dict[str, ExtractedField]:
    """Officer edits override machine output, field by field.

    Only keys PRESENT in `corrections` are touched, so an officer who corrects
    one field does not silently re-assert the other five as their own reading.
    A corrected field is marked `manual:` in its extractor string, which is how
    the report can show which rows a human stands behind.

    An officer who blanks a field is claiming it is absent -- but that claim
    still only lands if coverage says they examined the package.
    """
    out = dict(machine)
    can_assert = coverage.can_assert_absence()
    for key, raw in corrections.items():
        if key not in FIELD_KEYS:
            continue
        text = raw.strip() if isinstance(raw, str) else None
        out[key] = ExtractedField(
            value=text or None,
            asserts_absent=(not text) and can_assert,
            extractor=f"manual:{operator}",
            verbatim_confirmed=True if text else None)
    return out


def extraction_provenance_lines(fields: dict[str, ExtractedField],
                                coverage: Coverage) -> tuple[str, ...]:
    """What the report prints about HOW the declarations were obtained."""
    lines = [f"Coverage: {coverage.describe()}"]
    if coverage.note:
        lines.append(f"  note: {coverage.note}")
    for key in FIELD_KEYS:
        ef = fields.get(key)
        if ef is None:
            lines.append(f"  {key}: not reported by any extractor")
            continue
        conf = {True: "verbatim confirmed", False: "NOT found in OCR text",
                None: "not cross-checked"}[ef.verbatim_confirmed]
        lines.append(f"  {key}: via {ef.extractor}; {conf}")
    return tuple(lines)


# --------------------------------------------------------------------------
# Self-test -- fully offline
# --------------------------------------------------------------------------
def _self_test() -> int:
    checks = 0
    fails: list[str] = []

    def ck(name: str, cond: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(name + (f" -- {detail}" if detail else ""))

    no_cov = Coverage(panels=("front",))
    full_cov = Coverage(panels=("front", "back"),
                        operator_examined_package=True, operator_id="INS-01")

    # --- commitment 1: software never asserts absence ---------------------
    ck("photo-only coverage cannot assert absence", not no_cov.can_assert_absence())
    ck("examined-package coverage can", full_cov.can_assert_absence())
    ck("examined but unsigned cannot",
       not Coverage(operator_examined_package=True).can_assert_absence(),
       "an absence claim needs a named operator")
    ck("many panels still cannot assert absence",
       not Coverage(panels=("front", "back", "top", "bottom", "left", "right")
                    ).can_assert_absence(),
       "software must not self-certify that a panel set is complete")

    def fake_null(_img, _p):
        return json.dumps({k: None for k in FIELD_KEYS})

    v = vision_extract(b"x", fake_null, full_cov)
    ck("vision NEVER asserts absence, even with full coverage",
       all(not f.asserts_absent for f in v.values()),
       str([k for k, f in v.items() if f.asserts_absent]))

    m = manual_extract({k: None for k in FIELD_KEYS}, full_cov, "INS-01")
    ck("manual DOES assert absence under full coverage",
       all(f.asserts_absent for f in m.values()))
    m2 = manual_extract({k: None for k in FIELD_KEYS}, no_cov, "INS-01")
    ck("manual does NOT assert absence without examination",
       all(not f.asserts_absent for f in m2.values()))

    # --- JSON parsing ------------------------------------------------------
    ck("plain JSON parses", parse_vision_json('{"a":1}') == {"a": 1})
    ck("fenced JSON parses",
       parse_vision_json('```json\n{"a":1}\n```') == {"a": 1})
    ck("JSON with prose around it parses",
       parse_vision_json('Sure!\n{"a":1}\nHope that helps') == {"a": 1})
    for bad, why in (("", "empty"), ("not json at all", "no object"),
                     ("{broken", "unparseable"), ("[1,2]", "not a dict")):
        try:
            parse_vision_json(bad)
            ck(f"{why!r} must raise", False, "did not raise")
        except ExtractionError:
            ck(f"{why!r} raises ExtractionError", True)

    # --- vision normalisation ---------------------------------------------
    def fake_mixed(_img, _p):
        return json.dumps({
            "name_and_address": "  Acme Foods, Chennai  ",
            "common_or_generic_name": "N/A",
            "net_quantity": 100,
            "month_and_year": ["08", "2025"],
            "retail_sale_price": "MRP Rs.250 inclusive of all taxes",
            "consumer_care": "not visible",
        })

    v = vision_extract(b"x", fake_mixed, no_cov, backend_name="fake-vision")
    ck("whitespace is stripped", v[DECL_NAME_ADDRESS].value == "Acme Foods, Chennai")
    ck("'N/A' becomes null", v[DECL_COMMON_NAME].value is None)
    ck("'not visible' becomes null", v[DECL_CONSUMER_CARE].value is None)
    ck("numbers become text", v[DECL_NET_QUANTITY].value == "100")
    ck("lists become null", v[DECL_DATE].value is None)
    ck("backend name is recorded", v[DECL_NAME_ADDRESS].extractor == "fake-vision")
    ck("vision output starts un-crosschecked",
       all(f.verbatim_confirmed is None for f in v.values()))

    def fake_missing(_img, _p):
        return json.dumps({"name_and_address": "Acme"})

    v = vision_extract(b"x", fake_missing, no_cov)
    ck("missing keys become null fields, not KeyError",
       len(v) == len(FIELD_KEYS) and v[DECL_NET_QUANTITY].value is None)

    # --- cross-check -------------------------------------------------------
    fields = vision_extract(b"x", fake_mixed, no_cov)
    ocr = "ACME FOODS CHENNAI 100 MRP Rs.250 inclusive of all taxes"
    cc = crosscheck_verbatim(fields, ocr)
    ck("a value the OCR saw is confirmed",
       cc[DECL_NAME_ADDRESS].verbatim_confirmed is True)
    ck("a value the OCR never saw is flagged",
       crosscheck_verbatim(
           {"k": ExtractedField(value="Sunfeast Marie Light Biscuits",
                                extractor="v")},
           "totally different text here")["k"].verbatim_confirmed is False)
    ck("no OCR text means no cross-check, not a flag",
       all(f.verbatim_confirmed is None
           for f in crosscheck_verbatim(fields, "").values()))
    ck("manual values are never downgraded by cross-check",
       crosscheck_verbatim(manual_extract({DECL_COMMON_NAME: "Biscuits"}, no_cov),
                           "unrelated")[DECL_COMMON_NAME].verbatim_confirmed is True)

    # --- officer corrections ----------------------------------------------
    base = vision_extract(b"x", fake_mixed, full_cov)
    corr = apply_officer_corrections(base, {DECL_COMMON_NAME: "Biscuits"},
                                     full_cov, "INS-01")
    ck("correction overrides the machine value",
       corr[DECL_COMMON_NAME].value == "Biscuits")
    ck("correction is marked manual",
       corr[DECL_COMMON_NAME].extractor == "manual:INS-01")
    ck("untouched fields keep their machine extractor",
       corr[DECL_NAME_ADDRESS].extractor == base[DECL_NAME_ADDRESS].extractor)
    blanked = apply_officer_corrections(base, {DECL_CONSUMER_CARE: ""},
                                        full_cov, "INS-01")
    ck("an officer blanking a field under full coverage asserts absence",
       blanked[DECL_CONSUMER_CARE].asserts_absent)
    blanked2 = apply_officer_corrections(base, {DECL_CONSUMER_CARE: ""},
                                         no_cov, "INS-01")
    ck("the same blank without examination does not",
       not blanked2[DECL_CONSUMER_CARE].asserts_absent)
    ck("unknown correction keys are ignored",
       apply_officer_corrections(base, {"nonsense": "x"}, full_cov) .keys()
       == base.keys())

    # --- end to end with the declaration layer -----------------------------
    from lm_declarations import check_declarations, summarise
    f_photo = crosscheck_verbatim(vision_extract(b"x", fake_null, no_cov), "some text")
    s = summarise(check_declarations(f_photo))
    ck("a photo-only run with nothing read accuses nobody",
       s["counts"]["FAIL"] == 0, str(s["counts"]))
    f_exam = manual_extract({k: None for k in FIELD_KEYS}, full_cov, "INS-01")
    s2 = summarise(check_declarations(f_exam))
    ck("an examined package with nothing present DOES report non-compliance",
       s2["counts"]["FAIL"] == 6, str(s2["counts"]))

    print(f"extract self-test: {checks} checks, {len(fails)} failed")
    for f_ in fails:
        print("  !", f_)
    return 1 if fails else 0


if __name__ == "__main__":
    print(f"lm_extract  VERSION {VERSION}")
    print()
    rc = _self_test()
    print()
    cov = Coverage(panels=("front",), note="single handheld photo, demo rig")
    demo = manual_extract({
        DECL_NAME_ADDRESS: "Acme Foods Pvt Ltd, Chennai 600001",
        DECL_COMMON_NAME: "Biscuits",
        DECL_NET_QUANTITY: "100 g",
        DECL_DATE: "08/2025",
        DECL_RETAIL_PRICE: "Rs. 250",
        DECL_CONSUMER_CARE: None,
    }, cov, "INS-01")
    for line in extraction_provenance_lines(demo, cov):
        print(line)
    raise SystemExit(rc)
