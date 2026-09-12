#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lm_declarations.py -- the Rule 6(1) mandatory-declaration checks.

WHAT THIS IS. The other nine of the problem statement's ten Key Functional
Requirements need a layer that answers "is each mandatory declaration present,
and does it look right". This is that layer. It is the SHALLOW problem -- the
team brief says so and the team brief is correct -- and being shallow is not
a licence to be sloppy, because this module decides what a report ACCUSES a
packer of.

THREE COMMITMENTS, ALL OF WHICH COST FEATURES:

  1. THREE STATES, NEVER TWO. Every finding is PASS, FAIL or CANNOT_DETERMINE.
     A declaration this software could not read is NOT a violation. Collapsing
     "absent from the label" into the same bucket as "our OCR missed it" is how
     an enforcement tool generates false accusations at scale, and it is the
     single easiest way for a system like this to do real harm.

  2. THE SUB-CLAUSE LETTERS ARE NOT ASSERTED. Rule 6(1) is certain. Which
     LETTER within it carries which declaration is not -- sources conflict, and
     nobody on this team has opened the Gazette (job 1, still not done as of
     2026-09-12). So the letter is stored with its own provenance and is NOT
     PRINTED while unverified. A citation is a legal claim. `Rule 6(1)` is a
     claim we can defend; `Rule 6(1)(a)` currently is not.

  3. FORMAT CHECKS FAIL SOFT. Where a format check cannot distinguish "wrong"
     from "written in a way we did not anticipate", it returns
     CANNOT_DETERMINE. The unit list below is incomplete by admission. An
     incomplete list that refuses is safe; an incomplete list that accuses is
     not.

WHAT THIS MODULE DOES NOT DO, DELIBERATELY:
  - It does not compute penalties. The problem statement asks for compliance
    reports and violation summaries, not rupee amounts. Attaching a penalty to
    a finding this layer produced would give a number the weight of a
    measurement, and nothing here is a measurement.
  - It does not detect "misleading" declarations. That is a judgement, not a
    check, and the officer makes it.
  - It does not touch character height. That is `lm_metrology_v7.py`, it is a
    MEASUREMENT rather than an extraction, and the whole point of the source
    tiers below is that the two never look alike on a report.

NO I/O, NO NETWORK, NO IMAGE HANDLING. Pure logic over a dict, so it is fully
testable and its self-test is the thing that says whether it works.

RUN: python3 lm_declarations.py      (self-test)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Reuse the existing vocabulary rather than minting a parallel one. Two
# spellings of "where did this come from" in one codebase is how the drift
# starts.
from lm_legal_model import (
    CONF_DISPUTED,
    CONF_UNVERIFIED,
    CONF_VERIFIED,
    SOURCE_AGGREGATOR,
    SOURCE_PRIMARY_GAZETTE,
    SOURCE_UNREAD,
)

VERSION = "1.0-chunk1-2026-09-12"

# --------------------------------------------------------------------------
# Verdicts. Three, and the third is the one that matters.
# --------------------------------------------------------------------------
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_CANNOT_DETERMINE = "CANNOT_DETERMINE"

VERDICTS = (VERDICT_PASS, VERDICT_FAIL, VERDICT_CANNOT_DETERMINE)

# --------------------------------------------------------------------------
# Source tiers for a FINDING -- how the software came to know the thing it is
# reporting. Distinct from the SOURCE_* tiers imported above, which describe
# where a LEGAL RULE came from. Both axes are needed and conflating them is
# exactly the error the legal model's header warns about.
# --------------------------------------------------------------------------
TIER_EXTRACTED = "EXTRACTED"     # read off the image by OCR/vision. Unverified.
TIER_MEASURED = "MEASURED"       # produced by the metrology engine, with U.
TIER_DETERMINED = "DETERMINED"   # the officer's own call. Overrides both.

TIERS = (TIER_EXTRACTED, TIER_MEASURED, TIER_DETERMINED)


# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Citation:
    """A rule reference, carrying how much of itself is defensible.

    `sub_clause` is separate from `rule` because they have different
    confidence. Everyone agrees the mandatory declarations live in Rule 6(1)
    of the 2011 Rules. Which letter carries which declaration is asserted
    differently by different secondary sources, and this project's whole
    argument is that it does not repeat a legal claim it has not sourced.
    """

    rule: str                          # e.g. "Rule 6(1)" -- the defensible part
    instrument: str = "LMPC 2011"
    sub_clause: Optional[str] = None   # e.g. "(a)" -- often NOT defensible yet
    sub_clause_confidence: str = CONF_UNVERIFIED
    sub_clause_source: str = SOURCE_UNREAD
    note: str = ""

    def printable(self) -> str:
        """What may appear on a report or in front of a judge.

        The sub-clause is appended ONLY when it has been read from a primary
        source. Until then the report says `Rule 6(1)` and is correct, rather
        than `Rule 6(1)(a)` and unsupported.
        """
        if (self.sub_clause
                and self.sub_clause_confidence == CONF_VERIFIED
                and self.sub_clause_source in (SOURCE_PRIMARY_GAZETTE,)):
            return f"{self.instrument}, {self.rule}{self.sub_clause}"
        return f"{self.instrument}, {self.rule}"

    def provenance_line(self) -> str:
        """The row that goes in the report's provenance column."""
        if self.sub_clause is None:
            return f"{self.rule}: sub-clause not tracked"
        if self.sub_clause_confidence == CONF_VERIFIED:
            return (f"{self.rule}{self.sub_clause}: {self.sub_clause_confidence}"
                    f" ({self.sub_clause_source})")
        return (f"{self.rule}: sub-clause {self.sub_clause_confidence.lower()}"
                f" -- not printed. Candidate held internally pending the "
                f"Gazette read.")


# --------------------------------------------------------------------------
# The six declarations
#
# Sub-clause letters below are CANDIDATES held for the Gazette read, not
# claims. They are marked UNVERIFIED and `printable()` will not emit them.
# Two secondary sources consulted on 2026-09-12 disagreed about the ordering,
# which is precisely why they are not asserted. When job 1 is done, set the
# confidence and source on the ones that were confirmed -- and only those.
# --------------------------------------------------------------------------
DECL_NAME_ADDRESS = "name_and_address"
DECL_COMMON_NAME = "common_or_generic_name"
DECL_NET_QUANTITY = "net_quantity"
DECL_RETAIL_PRICE = "retail_sale_price"
DECL_DATE = "month_and_year"
DECL_CONSUMER_CARE = "consumer_care"


@dataclass(frozen=True)
class Declaration:
    key: str
    label: str
    citation: Citation
    expected: str            # plain-language statement of what the rule wants
    format_check: Optional[str] = None   # name of the extra check, if any


DECLARATIONS: tuple[Declaration, ...] = (
    Declaration(
        key=DECL_NAME_ADDRESS,
        label="Name and address of manufacturer / packer / importer",
        citation=Citation("Rule 6(1)", sub_clause="(a)",
                          sub_clause_source=SOURCE_AGGREGATOR,
                          note="secondary sources conflict on ordering"),
        expected="Name and complete address must appear on the package."),
    Declaration(
        key=DECL_COMMON_NAME,
        label="Common or generic name of the commodity",
        citation=Citation("Rule 6(1)", sub_clause="(b)",
                          sub_clause_source=SOURCE_AGGREGATOR,
                          note="secondary sources conflict on ordering"),
        expected="The common or generic name of the commodity must be declared."),
    Declaration(
        key=DECL_NET_QUANTITY,
        label="Net quantity",
        citation=Citation("Rule 6(1)", sub_clause="(c)",
                          sub_clause_source=SOURCE_AGGREGATOR,
                          note="secondary sources conflict on ordering"),
        expected="Net quantity in standard units of weight, measure or number.",
        format_check="legal_unit"),
    Declaration(
        key=DECL_DATE,
        label="Month and year of manufacture / packing / import",
        citation=Citation("Rule 6(1)", sub_clause="(d)",
                          sub_clause_source=SOURCE_AGGREGATOR,
                          note="secondary sources conflict on ordering"),
        expected="Month and year must be declared and be readable as a date.",
        format_check="month_year"),
    Declaration(
        key=DECL_RETAIL_PRICE,
        label="Retail sale price (MRP)",
        citation=Citation("Rule 6(1)", sub_clause="(e)",
                          sub_clause_source=SOURCE_AGGREGATOR,
                          note="secondary sources conflict on ordering"),
        expected="Retail sale price declared as maximum retail price, "
                 "inclusive of all taxes.",
        format_check="inclusive_of_taxes"),
    Declaration(
        key=DECL_CONSUMER_CARE,
        label="Consumer care details",
        citation=Citation("Rule 6(1)", sub_clause="(f)",
                          sub_clause_source=SOURCE_AGGREGATOR,
                          note="secondary sources conflict on ordering"),
        expected="Consumer care contact (name, address, phone or email)."),
)

DECLARATION_BY_KEY = {d.key: d for d in DECLARATIONS}


# --------------------------------------------------------------------------
# Input contract
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ExtractedField:
    """One declaration as the extraction layer reports it.

    `asserts_absent` is the whole reason this is a dataclass and not a plain
    string. There is a real difference between:

        "we captured the full principal display panel, searched it, and this
         declaration is not on it"          -> asserts_absent=True   -> FAIL

        "we did not find it, and we do not claim to have seen everything"
                                            -> asserts_absent=False  -> CANNOT_DETERMINE

    An extraction layer that cannot tell those apart must pass
    asserts_absent=False. That is not a cop-out; it is the truthful setting for
    a single photograph of one face of a package, which is what the demo
    actually has. Chunk 2 inherits this contract and must not quietly default
    it to True to make the output look decisive.
    """

    value: Optional[str] = None
    asserts_absent: bool = False
    extractor: str = "unspecified"
    # None = no cross-check was run. True = a second engine saw these
    # characters. False = no OCR engine on this image saw them, which is
    # consistent with a hallucinated value AND with OCR simply being worse than
    # the vision model on glossy or curved packaging. Because it cannot
    # distinguish those, a False DOWNGRADES to CANNOT_DETERMINE and is never
    # reported as evidence against anyone. See `lm_extract.crosscheck_verbatim`.
    verbatim_confirmed: Optional[bool] = None


@dataclass(frozen=True)
class Finding:
    """One row of the report. The explainability chain is the row.

    Field order mirrors the chain a report prints:
        Checked -> Detected -> Expected -> Why -> Citation -> Source tier
    """

    key: str
    label: str
    verdict: str
    source_tier: str
    detected: Optional[str]
    expected: str
    why: str
    citation: Citation
    extractor: str = "unspecified"

    def chain(self) -> tuple[str, ...]:
        """The explainability chain, as lines. Used by the report layer."""
        return (
            f"Checked:   {self.label}",
            f"Detected:  {self.detected if self.detected is not None else '(nothing read)'}",
            f"Expected:  {self.expected}",
            f"Why:       {self.why}",
            f"Citation:  {self.citation.printable()}",
            f"Source:    {self.source_tier}"
            + (f" via {self.extractor}" if self.source_tier == TIER_EXTRACTED else ""),
            f"Rule prov: {self.citation.provenance_line()}",
        )


# --------------------------------------------------------------------------
# Format checks. Every one of these fails SOFT.
# --------------------------------------------------------------------------

# Standard units. INCOMPLETE BY ADMISSION -- this list was assembled from
# general knowledge of SI usage, not from the Legal Metrology (General) Rules,
# 2011 or the Act's schedules. That is why an unrecognised unit returns
# CANNOT_DETERMINE and never FAIL: the likeliest explanation for a unit not in
# this list is that the list is short, not that the packer broke the law.
# Completing it from the primary source is a job-1 task.
_LEGAL_UNITS = {
    "g", "gm", "gms", "gram", "grams", "kg", "kgs", "kilogram", "kilograms",
    "mg", "milligram", "milligrams",
    "ml", "millilitre", "millilitres", "milliliter", "milliliters",
    "l", "ltr", "litre", "litres", "liter", "liters", "cl",
    "m", "cm", "mm", "metre", "metres", "meter", "meters",
    "n", "no", "nos", "pc", "pcs", "piece", "pieces", "unit", "units",
}

_QTY_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_TAX_PHRASES = (
    "inclusive of all taxes", "incl. of all taxes", "incl of all taxes",
    "inclusive of taxes", "incl. all taxes", "all taxes included",
    "inclusive all taxes", "max retail price", "maximum retail price",
)


def _check_legal_unit(value: str) -> tuple[str, str]:
    """Net quantity carries a number and a recognised standard unit."""
    m = _QTY_RE.search(value)
    if not m:
        return (VERDICT_CANNOT_DETERMINE,
                "No number-and-unit pair could be parsed from the declared "
                "text. The declaration may still be valid and written in a "
                "form this parser does not recognise.")
    unit = m.group(2).lower().strip(".")
    if unit in _LEGAL_UNITS:
        return (VERDICT_PASS,
                f"Quantity {m.group(1)} with unit '{m.group(2)}', which is a "
                f"standard unit.")
    return (VERDICT_CANNOT_DETERMINE,
            f"Unit '{m.group(2)}' is not in this system's unit list. That "
            f"list is known to be incomplete, so this is reported as "
            f"undetermined rather than as a violation. Officer to confirm.")


def _check_month_year(value: str) -> tuple[str, str]:
    """The date must be readable as a month and a year."""
    v = value.lower()
    yr = re.search(r"(19|20)\d{2}", v)
    num = re.search(r"\b(0?[1-9]|1[0-2])\s*[/\-.]\s*((?:19|20)?\d{2})\b", v)
    if num:
        return (VERDICT_PASS,
                f"Parsed as month {num.group(1)}, year {num.group(2)}.")
    for name, _n in _MONTHS.items():
        if name in v and yr:
            return (VERDICT_PASS,
                    f"Parsed as month '{name}', year {yr.group(0)}.")
    return (VERDICT_CANNOT_DETERMINE,
            "Declared text could not be parsed as a month and year. It may be "
            "a valid date in a format this parser does not handle.")


def _check_inclusive_of_taxes(value: str) -> tuple[str, str]:
    """MRP must be declared as inclusive of all taxes.

    NOTE THE SOFT FAILURE, IT IS DELIBERATE. The inclusive-of-taxes wording is
    frequently printed adjacent to the price rather than inside the same text
    run, so an extractor that captured only the numeral has not established
    that the statement is missing from the PACKAGE -- only that it is missing
    from the STRING. Reporting FAIL here would accuse a packer on the strength
    of a text-segmentation choice.
    """
    v = value.lower()
    if any(p in v for p in _TAX_PHRASES):
        return (VERDICT_PASS,
                "Price is accompanied by an inclusive-of-taxes statement.")
    if re.search(r"(rs\.?|inr|₹)\s*\d", v) or re.search(r"\d+\.\d{2}", v):
        return (VERDICT_CANNOT_DETERMINE,
                "A price was read but no inclusive-of-taxes wording was found "
                "in the same text. The statement may appear elsewhere on the "
                "panel. Officer to confirm on the physical package.")
    return (VERDICT_CANNOT_DETERMINE,
            "No price figure could be parsed from the declared text.")


_FORMAT_CHECKS = {
    "legal_unit": _check_legal_unit,
    "month_year": _check_month_year,
    "inclusive_of_taxes": _check_inclusive_of_taxes,
}


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------
def check_declaration(decl: Declaration, ef: Optional[ExtractedField]) -> Finding:
    """One declaration, one finding. Never raises on bad input."""
    if ef is None:
        ef = ExtractedField()

    def make(verdict: str, why: str) -> Finding:
        return Finding(key=decl.key, label=decl.label, verdict=verdict,
                       source_tier=TIER_EXTRACTED, detected=ef.value,
                       expected=decl.expected, why=why,
                       citation=decl.citation, extractor=ef.extractor)

    value = (ef.value or "").strip()

    if not value:
        if ef.asserts_absent:
            return make(VERDICT_FAIL,
                        "The extraction layer asserts it captured the relevant "
                        "panel and this declaration is not present on it.")
        return make(VERDICT_CANNOT_DETERMINE,
                    "Nothing was read for this declaration, and the extraction "
                    "layer does not assert it captured the whole panel. Absence "
                    "of evidence is not recorded as a violation.")

    # A value no OCR engine on this image saw is not evidence of anything yet.
    # This is checked BEFORE the format checks on purpose: running a format
    # check on a possibly-invented string and reporting PASS would launder a
    # hallucination into a compliance finding.
    if ef.verbatim_confirmed is False:
        return make(VERDICT_CANNOT_DETERMINE,
                    "A value was reported for this declaration but a second "
                    "engine reading the same image did not find that text. "
                    "This is consistent with a misread by either engine, so "
                    "the declaration is recorded as undetermined. Officer to "
                    "confirm on the physical package.")

    if decl.format_check is None:
        return make(VERDICT_PASS, "Declaration is present.")

    verdict, why = _FORMAT_CHECKS[decl.format_check](value)
    return make(verdict, why)


def check_declarations(extracted: dict) -> tuple[Finding, ...]:
    """All six declarations, in the order they are declared above.

    `extracted` maps declaration key -> ExtractedField. Missing keys are
    treated as "not reported by the extractor", which is CANNOT_DETERMINE,
    not FAIL. An extractor that crashed must not cause six accusations.
    """
    return tuple(check_declaration(d, extracted.get(d.key))
                 for d in DECLARATIONS)


def summarise(findings: tuple[Finding, ...]) -> dict:
    """Counts for the dashboard, plus the one honest headline.

    There is no "compliance score" here and there will not be one. A percentage
    implies the six declarations are commensurable and that CANNOT_DETERMINE
    can be averaged with PASS. Neither is true. The dashboard gets counts.
    """
    counts = {v: 0 for v in VERDICTS}
    for f in findings:
        counts[f.verdict] += 1
    if counts[VERDICT_FAIL] > 0:
        headline = "NON-COMPLIANCE FOUND"
    elif counts[VERDICT_CANNOT_DETERMINE] > 0:
        headline = "INCOMPLETE -- officer review required"
    else:
        headline = "NO NON-COMPLIANCE DETECTED"
    return {"counts": counts, "headline": headline,
            "n": len(findings), "determinable": counts[VERDICT_PASS]
            + counts[VERDICT_FAIL]}


def report_lines(findings: tuple[Finding, ...]) -> tuple[str, ...]:
    """Plain-text rendering. The PDF/DOCX layer (chunk 3) formats properly."""
    out: list[str] = []
    s = summarise(findings)
    out.append(f"DECLARATION CHECKS -- Rule 6(1), LMPC 2011")
    out.append(f"  {s['headline']}")
    out.append(f"  PASS {s['counts'][VERDICT_PASS]}   "
               f"FAIL {s['counts'][VERDICT_FAIL]}   "
               f"CANNOT DETERMINE {s['counts'][VERDICT_CANNOT_DETERMINE]}")
    out.append("")
    for f in findings:
        out.append(f"[{f.verdict}] {f.label}")
        for line in f.chain():
            out.append(f"    {line}")
        out.append("")
    return tuple(out)


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------
def _self_test() -> int:
    checks = 0
    fails: list[str] = []

    def ck(name: str, cond: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(f"{name}" + (f" -- {detail}" if detail else ""))

    # --- the three-state commitment ---------------------------------------
    f = check_declaration(DECLARATION_BY_KEY[DECL_COMMON_NAME],
                          ExtractedField(value=None, asserts_absent=False))
    ck("absent + no assertion -> CANNOT_DETERMINE",
       f.verdict == VERDICT_CANNOT_DETERMINE, f.verdict)

    f = check_declaration(DECLARATION_BY_KEY[DECL_COMMON_NAME],
                          ExtractedField(value=None, asserts_absent=True))
    ck("absent + extractor asserts absence -> FAIL",
       f.verdict == VERDICT_FAIL, f.verdict)

    f = check_declaration(DECLARATION_BY_KEY[DECL_COMMON_NAME],
                          ExtractedField(value="Biscuits"))
    ck("present -> PASS", f.verdict == VERDICT_PASS, f.verdict)

    # missing key entirely must not accuse
    fs = check_declarations({})
    ck("empty extraction yields zero FAILs",
       all(x.verdict == VERDICT_CANNOT_DETERMINE for x in fs),
       str([x.verdict for x in fs]))
    ck("empty extraction still returns all six", len(fs) == 6, str(len(fs)))

    # --- citations must not leak an unverified sub-clause -----------------
    for d in DECLARATIONS:
        ck(f"{d.key}: sub-clause not printed while unverified",
           "(" not in d.citation.printable().replace("Rule 6(1)", ""),
           d.citation.printable())
    ck("printable() is the defensible parent rule",
       DECLARATION_BY_KEY[DECL_NET_QUANTITY].citation.printable()
       == "LMPC 2011, Rule 6(1)")
    # and it DOES print once verified
    verified = Citation("Rule 6(1)", sub_clause="(c)",
                        sub_clause_confidence=CONF_VERIFIED,
                        sub_clause_source=SOURCE_PRIMARY_GAZETTE)
    ck("a verified sub-clause IS printed",
       verified.printable() == "LMPC 2011, Rule 6(1)(c)", verified.printable())

    # --- net quantity ------------------------------------------------------
    for val, want in (("100 g", VERDICT_PASS), ("1.5 kg", VERDICT_PASS),
                      ("500ml", VERDICT_PASS), ("12 pieces", VERDICT_PASS),
                      ("1 dozen", VERDICT_CANNOT_DETERMINE),
                      ("net weight", VERDICT_CANNOT_DETERMINE)):
        f = check_declaration(DECLARATION_BY_KEY[DECL_NET_QUANTITY],
                              ExtractedField(value=val))
        ck(f"net qty {val!r} -> {want}", f.verdict == want, f.verdict)

    ck("an unknown unit is never FAIL",
       check_declaration(DECLARATION_BY_KEY[DECL_NET_QUANTITY],
                         ExtractedField(value="1 dozen")).verdict != VERDICT_FAIL)

    # --- dates -------------------------------------------------------------
    for val, want in (("08/2025", VERDICT_PASS), ("8-2025", VERDICT_PASS),
                      ("AUG 2025", VERDICT_PASS), ("Aug 2025", VERDICT_PASS),
                      ("packed recently", VERDICT_CANNOT_DETERMINE)):
        f = check_declaration(DECLARATION_BY_KEY[DECL_DATE],
                              ExtractedField(value=val))
        ck(f"date {val!r} -> {want}", f.verdict == want, f.verdict)

    # --- MRP ---------------------------------------------------------------
    f = check_declaration(DECLARATION_BY_KEY[DECL_RETAIL_PRICE],
                          ExtractedField(value="MRP Rs. 250 inclusive of all taxes"))
    ck("MRP with tax statement -> PASS", f.verdict == VERDICT_PASS, f.verdict)
    f = check_declaration(DECLARATION_BY_KEY[DECL_RETAIL_PRICE],
                          ExtractedField(value="Rs. 250"))
    ck("MRP without tax statement -> CANNOT_DETERMINE (never FAIL)",
       f.verdict == VERDICT_CANNOT_DETERMINE, f.verdict)

    # --- summarise ---------------------------------------------------------
    s = summarise(check_declarations({}))
    ck("all-undetermined headline is not a pass",
       s["headline"] == "INCOMPLETE -- officer review required", s["headline"])
    ck("no compliance percentage is computed", "score" not in s and "%" not in str(s))

    good = {d.key: ExtractedField(value=v) for d, v in zip(
        DECLARATIONS, ["Acme Foods, Chennai 600001", "Biscuits", "100 g",
                       "08/2025", "MRP Rs. 250 inclusive of all taxes",
                       "care@acme.example 1800-000-000"])}
    s2 = summarise(check_declarations(good))
    ck("a clean packet reports no non-compliance",
       s2["headline"] == "NO NON-COMPLIANCE DETECTED", s2["headline"])
    ck("a clean packet has six PASS", s2["counts"][VERDICT_PASS] == 6)

    # --- source tiers ------------------------------------------------------
    ck("every finding from this module is EXTRACTED",
       all(x.source_tier == TIER_EXTRACTED for x in check_declarations(good)))
    ck("this module never emits MEASURED",
       all(x.source_tier != TIER_MEASURED for x in check_declarations(good)),
       "height is the metrology engine's to report, not this module's")

    # --- the chain ---------------------------------------------------------
    ch = check_declarations(good)[0].chain()
    ck("chain has the six explainability rows plus provenance", len(ch) == 7,
       str(len(ch)))

    # --- verbatim cross-check downgrade ------------------------------------
    f = check_declaration(DECLARATION_BY_KEY[DECL_COMMON_NAME],
                          ExtractedField(value="Biscuits", verbatim_confirmed=False))
    ck("unconfirmed value -> CANNOT_DETERMINE, never PASS",
       f.verdict == VERDICT_CANNOT_DETERMINE, f.verdict)
    ck("unconfirmed value is never FAIL either",
       f.verdict != VERDICT_FAIL,
       "a cross-check miss is not evidence against a packer")
    f = check_declaration(DECLARATION_BY_KEY[DECL_NET_QUANTITY],
                          ExtractedField(value="100 g", verbatim_confirmed=False))
    ck("downgrade beats a passing format check",
       f.verdict == VERDICT_CANNOT_DETERMINE, f.verdict)
    f = check_declaration(DECLARATION_BY_KEY[DECL_NET_QUANTITY],
                          ExtractedField(value="100 g", verbatim_confirmed=True))
    ck("a confirmed value still runs its format check",
       f.verdict == VERDICT_PASS, f.verdict)
    f = check_declaration(DECLARATION_BY_KEY[DECL_NET_QUANTITY],
                          ExtractedField(value="100 g", verbatim_confirmed=None))
    ck("no cross-check run means no downgrade",
       f.verdict == VERDICT_PASS, f.verdict)

    print(f"declarations self-test: {checks} checks, {len(fails)} failed")
    for f_ in fails:
        print("  !", f_)
    return 1 if fails else 0


if __name__ == "__main__":
    print(f"lm_declarations  VERSION {VERSION}")
    print()
    rc = _self_test()
    print()
    demo = {
        DECL_NAME_ADDRESS: ExtractedField("Acme Foods Pvt Ltd, Chennai 600001",
                                          extractor="manual"),
        DECL_COMMON_NAME: ExtractedField("Biscuits", extractor="manual"),
        DECL_NET_QUANTITY: ExtractedField("100 g", extractor="manual"),
        DECL_DATE: ExtractedField("08/2025", extractor="manual"),
        DECL_RETAIL_PRICE: ExtractedField("Rs. 250", extractor="manual"),
        # consumer care deliberately absent AND asserted absent
        DECL_CONSUMER_CARE: ExtractedField(None, asserts_absent=True,
                                           extractor="manual"),
    }
    for line in report_lines(check_declarations(demo)):
        print(line)
    raise SystemExit(rc)
