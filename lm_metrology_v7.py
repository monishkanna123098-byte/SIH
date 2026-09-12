#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lm_metrology_v7.py
==================
Letter-height measurement for Legal Metrology (Packaged Commodities) Rules, 2011,
plus the audit harness that characterises it.

WHAT THIS IS
  A dimensional-metrology instrument, not an OCR system. It reports a height, an
  expanded uncertainty, a conformity band, and -- often -- a refusal.

STANDING RULES ENCODED HERE (each one is a bug that was found the hard way)
  R1  Ground truth is derived FROM the rendered array, never from the parameters
      that were requested.  (v6 declared 1.040 mm and rendered 1.050 mm; the
      +0.010 mm difference was reported as a measurement bias in every table.)
  R2  Every physical threshold is in millimetres.  Any parameter in pixel units
      inside a sweep over pixels-per-mm makes that sweep uninterpretable.
      Where an integer floor binds, the row is flagged FLOOR-LIMITED and is a
      statement about the detector, not about sampling.
  R3  A sensitivity test must be solvable by hand on its own scene.  If the
      estimator's answer is independent of the swept variable, the scene is
      wrong.  See notes in exposure_test().
  R4  The refusal layer lives in the library.  A check recomputed inside a test
      cannot fire in production.
  R5  A limit relaxed to characterise must not become a default.  Use
      CaptureLimits.for_characterisation() and say so in the output.
  R6  One-sided systematic terms are ADDED.  RSS is for independent random terms.
  R7  Report n_unique alongside n.  Five seeds with noise=0 are one sample.
  R8  Detected spans are matched to truth by column overlap.  A dropped glyph
      must show up as an unmatched truth, never as a silent re-alignment.

CONFORMITY (JCGM 106:2012)
  The limit is a number in a statute and is EXACT.  Only the measurement carries
  uncertainty.  Do not apply a guard band to the limit as well as to the
  measurement -- see NOTE_ON_GUARD_BAND.

DEPENDENCIES: numpy (required); scipy, cv2, PIL (harness only).
"""

from __future__ import annotations

import hashlib
import math
import os
import sys
from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, Optional, Sequence

import numpy as np

# Soft dependency on the statutory layer (lm_legal_model.py's own INTEGRATION
# block specifies this wiring). Everything above this line, and every existing
# caller of measure()/measure_with_category() that does not declare a
# commodity_class, must keep working with this import absent or failed --
# self-tests and the rendered-target demo do not need it. It is only required
# by measure_with_category's integrated path, and that path fails loudly with
# its own refusal code if the import did not succeed, not with an ImportError
# at module load time.
try:
    import lm_legal_model as _legal
    _LEGAL_MODEL_AVAILABLE = True
except ImportError:
    _legal = None
    _LEGAL_MODEL_AVAILABLE = False

VERSION = "7.9-call-site-3-2026-09-07"

# CHANGES (7.8 -> 7.9):
#   1. Call site 3 from lm_legal_model.py's INTEGRATION block, implemented as
#      a standalone legal_report_lines(v) function rather than inlined into
#      measure_with_category (which returns a Verdict and does not print, per
#      that block's own instruction). res is now stashed in
#      diagnostics["legal_resolution"] at every return point on the
#      integrated path, refusal or not -- MeasurementConvention.report_lines
#      is written to handle threshold_mm=None on purpose, and a refusal has
#      as much right to an audit trail as a verdict does. Verified against
#      three cases: a resolved measurement, a disputed-bracket refusal, and
#      the legacy path (returns () rather than erroring, since there is no
#      res to report on).
#   2. max_supported vs plain-extreme: confirmed by running convention_bakeoff
#      that they print identical figures on every rendered scene, because
#      those scenes never contain an isolated one-column defect. Added a
#      direct test of _supported_extreme's actual mechanism (an isolated
#      excursion against a real cluster) to harness_self_checks rather than
#      changing the renderer -- proves the guard works without touching the
#      bakeoff's scene generation four days from a moved deadline.

# CHANGES (7.7 -> 7.8):
#   1. Found an actual Gazette compilation (thc.nic.in, hosting sequential
#      amendment notifications, not a summary) while looking for something
#      else. It resolves the 7(3)-vs-Table-I disagreement v7.7 flagged as
#      unresolved: G.S.R. 778(E) (23.10.2025) amends "rule 7, sub-rule (2)"
#      for height and "sub-rule (3)" for width, in as many words. Citation
#      updated to Rule 7(2). Still not primary-sourced: the actual figures in
#      the Table-I that 7(2) now points to, and anything from G.S.R. 629(E)
#      itself (this compilation doesn't reach back that far) -- the disputed
#      50-100cm2 bracket in lm_legal_model.py is unaffected by this change and
#      remains exactly as unresolved.

# CHANGES (7.5 -> 7.6):
#   1. [lm_legal_model.py's own INTEGRATION block, implemented as specified]
#      measure_with_category() now has two paths. Legacy (commodity_class=None,
#      the default): v7's own flat ruleset.table_for(category) lookup,
#      UNCHANGED CODE -- confirmed by running this file and diffing against
#      the v7.5 baseline: every line of output is byte-identical except the
#      version string and hash. Integrated (commodity_class given): resolves
#      the threshold via lm_legal_model.resolve_threshold() instead of the
#      flat 1.0/2.0mm constants, gated in the exact precedence that file's
#      INTEGRATION block specifies -- category declared -> category
#      recognised -> can we measure this surface -> threshold -- and verified
#      by execution against 8 scenarios: legacy-path equivalence (integrated
#      lookup at PDP 40cm2 returns TL=1.0/2.0mm, matching the legacy constants
#      exactly), category-not-declared, PDP-area-not-declared, the measurand
#      gate correctly outranking a missing PDP area for a formed package
#      (fires MEASURAND_UNDEFINED even with no pdp_area_cm2 at all), the
#      disputed 50-100cm2 bracket refusing THRESHOLD_DISPUTED with no leaked
#      value, and a wiring-fault category correctly reporting CATEGORY_UNKNOWN
#      rather than a routine-looking refusal. measure() gained external_TL to
#      carry the resolved number without re-deriving it; existing callers that
#      don't pass it are unaffected.
#   2. [found while implementing #1, not in any prior document]
#      lm_legal_model.Provenance.is_in_force(as_of) raised TypeError when
#      as_of=None met a set effective_from -- comparing None to a date is
#      undefined in Python. This is exactly the case the integration's own
#      spec calls for (as_of defaults to None so a forgetful caller gets a
#      refusal, not a guess) and exactly the case that crashed instead of
#      refusing. Fixed in lm_legal_model.py: as_of=None now returns False
#      (not in force / unknown), same as an unset effective_from. Re-ran that
#      file's self-test after the fix: 81 of 81, unchanged.
#   3. Import of lm_legal_model is soft (try/except at module load). Every
#      caller that does not declare a commodity_class is unaffected whether or
#      not the import succeeds; the integrated path fails with its own
#      LEGAL_MODEL_UNAVAILABLE refusal if it did not.

# CHANGES (7.4 -> 7.5):
#   1. [today's Gazette research, redteam section 7 job 1] RULES_2011.citation
#      upgraded from "rule number unresolved" to "Rule 7(3)", sourced to a
#      government-hosted copy of the 2011 notification (wbconsumers.gov.in) plus
#      three independent secondary legal analyses of current law, all agreeing.
#      NOT the certified Gazette original -- still hedged as such in the string
#      itself. Separately: the numeral-height table (Rule 7(2)/Table-I/Table-II,
#      which lives in lm_legal_model.py, NOT here) appears to have been
#      restructured by the 2017 amendment (G.S.R. 629(E)) -- Table-II reportedly
#      omitted and merged into a single Table-I. This file's letter-height rule
#      is unaffected, but the area-indexed numeral table in the legal model
#      should be re-checked against the post-2017 Table-I specifically -- flagged
#      for that file's own owner, not fixed here.

# CHANGES (7.3 -> 7.4):
#   1. [redteam section 5] Budget.report()'s caveat said "2 s.f." for a value
#      formatted to 2 decimal places. The two coincide only when the value
#      starts with 0. (U=0.17 mm); Verdict.report() prints h and TL to the same
#      .2f/.3f formatting and those routinely exceed 1mm (h=1.40 is 3 s.f.),
#      so the label was wrong the moment a height crossed 1mm. Now says "2 d.p."

# CHANGES (7.0 -> 7.1):
#   1. Measurand gate: CATEGORY_FORMED refuses (MEASURAND_UNDEFINED) instead of
#      returning a verdict -- relief characters have no ink edge to measure.
#   2. Three budget terms added (lens distortion, defocus asymmetry, fiducial
#      localisation); U rises 0.1513 -> 0.16634 mm.
#   3. U and Verdict report at 2 s.f. when any budget term is unmeasured; raw
#      value kept visible in Budget.report().
#   4. max_supported's effective support width is pixel-floor-limited below
#      ~75 px/mm; now surfaced as a diagnostic warning instead of silently
#      discarded (never a refusal -- it fires at the declared 30 px/mm floor).
#   5. Governing glyph index/extent and dropped-glyph indices recorded in
#      diagnostics; h is bit-identical to 7.0 (argmin vs min on the same list).
#
# CHANGES (7.1 -> 7.3; there is no 7.2 -- that label belongs to the patch
# *document* this file was checked against, which was never applied as-is):
#   1. [patch v7.2 #1, applied as specified] The three "r.9" label/citation
#      strings are gone. Confirmed by grep they were never used as a dict key,
#      so this is display-only. Confirmed by grep of main_run_output_v7.1_final
#      .log that they never actually reached printed output -- this closes a
#      latent risk, not a live leak.
#   2. [patch v7.2 #2, NOT applied -- the bug it targets does not exist here]
#      gradient_limit_from_budget() already prints the "DO NOT set
#      max_illum_gradient from this number" caveat, byte-for-byte identical to
#      the archived v7.1 run. Patch v7.2 was written against an earlier,
#      unfixed paste of this function; applying it as specified would either
#      no-op (str_replace finds no match) or, if done by hand, overwrite a
#      caveat that is already more complete than the one it proposes.
#   3. [patch v7.2 #3, applied, NOT as specified] scale_calibration,
#      fiducial_localisation and lens_distortion_field_position are now
#      BudgetTerm(..., relative=True) and scale with h_mm/H_REF_MM.
#      Budget.expanded(h_mm) now REQUIRES the measured height -- no default,
#      by design, so a stale call site fails loudly instead of quietly
#      reporting the 1 mm budget forever. Budget.report() takes an optional
#      h_mm for the same reason. measure() now computes TL before U and
#      evaluates U at max(h, TL), never the smaller of the two (section 7.1).
#      Patch v7.2's own proposed dataclass used field names (half_width_mm /
#      basis / provenance) that do not match this file's real fields
#      (value_mm / source / note); this version keeps the real names, so the
#      eight existing BudgetTerm(...) calls in provisional_budget() did not
#      need to change. expanded(1.0) is unchanged at 0.16634 -- the anchor
#      holds. Patch v7.2's hand-computed values for expanded(2.0/2.5/4.0/6.0)
#      (0.18486/0.19566/0.23206/0.28578) were independently verified correct.
#   4. [patch v7.2 #4, applied as a new field, not a line edit] No existing
#      "convention: ..." report line was found anywhere in this file,
#      lm_capture.py or lm_legal_model.py to extend, in either the archived
#      or current copies -- patch v7.2 assumed one existed. measure() now sets
#      diag["convention_line"], printing convention_bias_mm (default 0.0,
#      confirmed unchanged) next to the convention it qualifies. Whoever wires
#      up the field-facing report should treat this as a starting point, not
#      a finished design.
#   NOTE: the hash below is stale the moment any further edit is made -- read
#   VERSION/hash off the running program during a demo, never off a document.


def _self_hash() -> str:
    try:
        with open(os.path.abspath(__file__), "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except Exception as exc:                                    # pragma: no cover
        return f"<unavailable: {exc}>"


# =============================================================================
# PART 1 -- CONFORMITY / LEGAL LAYER
# =============================================================================

NOTE_ON_GUARD_BAND = """\
JCGM 106:2012.  TL is exact; only h carries uncertainty.

    h - U >= TL   -> COMPLIANT
    h + U <  TL   -> DEFICIENT
    otherwise     -> REQUIRES_PHYSICAL_VERIFICATION

Writing `h + U < TL - U` applies the guard band twice and doubles the accuracy
requirement for no reason.  With TL = 1.0 mm and a non-overlap requirement, the
correct condition gives U < 0.4 mm, not U < 0.2 mm.
"""

BAND_COMPLIANT = "COMPLIANT"
BAND_DEFICIENT = "DEFICIENT"
BAND_REFER = "REQUIRES_PHYSICAL_VERIFICATION"


@dataclass(frozen=True)
class Refusal:
    """A refusal is a product output, not an error.  `detail` must name a
    physical cause the operator can act on."""
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass(frozen=True)
class HeightRule:
    """One row of a statutory height table.

    `index_low`/`index_high` bound the indexing quantity (net quantity in g/ml,
    or principal-display-panel area in cm^2) for this row.  `index_by == 'flat'`
    means there is no table: one minimum applies to everything.
    """
    min_height_mm: float
    index_low: Optional[float] = None
    index_high: Optional[float] = None
    label: str = ""


@dataclass
class RuleTable:
    """Branch-agnostic on purpose.

    Whether the 2011 Rules index letter height by declared net quantity, by
    measured principal-display-panel area, or not at all, is UNRESOLVED.  The
    code must not wait on that question, so all three branches are supported and
    an ambiguous index returns every candidate row.
    """
    index_by: str                       # 'flat' | 'net_quantity' | 'panel_area_cm2'
    rows: Sequence[HeightRule]
    citation: str = "Legal Metrology (Packaged Commodities) Rules, 2011"

    def candidates(self, index_value: Optional[float],
                   index_u: float = 0.0) -> list[HeightRule]:
        if self.index_by == "flat":
            return list(self.rows)
        if index_value is None:
            return list(self.rows)
        out = []
        for r in self.rows:
            low = -math.inf if r.index_low is None else r.index_low
            high = math.inf if r.index_high is None else r.index_high
            # Straddle test: keep the row unless the interval [v-u, v+u] is
            # entirely outside it.  An uncertain index must not silently pick one row.
            if not (index_value + index_u < low or index_value - index_u >= high):
                out.append(r)
        return out

    def governing_threshold(self, index_value: Optional[float],
                            index_u: float = 0.0) -> tuple[float, list[HeightRule]]:
        """The threshold to test against, plus the rows that produced it.

        When the index is ambiguous the STRICTEST candidate governs, and the
        ambiguity must be reported -- it is a reason to refer, not to guess.
        """
        cands = self.candidates(index_value, index_u)
        if not cands:
            raise ValueError("no rule row matches the index value")
        return max(r.min_height_mm for r in cands), cands


# ------------------------------------------------------------------ category
# The floor depends on HOW the mark was made (statutory rule number unresolved
# -- see brief section 3.3; do not restate "r.9" here, that is the claim patch
# v7.3 removed).
# Nothing in this pipeline measures that. Putting it on the `index_by` axis is
# what made RULE_INDEX_AMBIGUOUS fire unconditionally -- a "flat" table returns
# every row, so len(candidates) > 1 forever, and every embossed package went to
# a human no matter how good the measurement was.
CATEGORY_GENERAL = "general"                                   # printed/applied: 1 mm
CATEGORY_FORMED  = "blown_formed_moulded_embossed_perforated"  # 2 mm
CATEGORIES = (CATEGORY_GENERAL, CATEGORY_FORMED)

CATEGORY_PROMPT = (
    "operator must declare the package category: is the marking blown, formed, "
    "moulded, embossed or perforated (2 mm floor), or printed/applied (1 mm floor)?"
)

# Which categories have a DEFINED optical measurand.
#
# This is a MEASUREMENT fact, not a legal one. The statute is unambiguous that relief
# characters must reach 2 mm; it is our instrument that has no edge to find on them. The
# declared 50%-of-ink-to-substrate criterion presupposes ink. Relief characters have none:
# what the sensor sees is a shadow boundary that moves with illumination direction and is
# displaced by the moulding draft angle. Height is therefore not a quantity this
# instrument can report for them at all.
#
# Default is False for anything unlisted, so a category added to RULES_2011 without a
# corresponding entry here fails CLOSED.
MEASURAND_DEFINED = {
    CATEGORY_GENERAL: True,   # printed / applied ink on a flat substrate
    CATEGORY_FORMED:  False,  # blown / formed / moulded / embossed / perforated
}

MEASURAND_UNDEFINED_PROMPT = (
    "relief characters (blown/formed/moulded/embossed/perforated) carry no "
    "ink-to-substrate transition, so the declared 50% edge criterion does not define an "
    "edge for them; apparent height varies with illumination direction and draft angle. "
    "Optical height measurement is outside the declared envelope -- refer for physical "
    "verification. Pass allow_undefined_measurand=True only to characterise this failure "
    "deliberately; it is not a production path."
)


def measurand_is_defined(category) -> bool:
    """True only for categories this instrument has a defined measurand for."""
    return bool(MEASURAND_DEFINED.get(category, False))


@dataclass(frozen=True)
class RuleSet:
    """One RuleTable per DECLARED category.

    Declared, never inferred. No measurement here distinguishes embossed glass
    from printed card, so inferring it would report a legal category we did not
    measure. Refuse and ask instead.
    """
    tables: dict
    citation: str = ("PC Rules 2011, Rule 7(2) -- height of numerals and letters. "
                      "CORRECTED 2026-09-07, this time against an actual Gazette "
                      "compilation (thc.nic.in's hosted run of amendment "
                      "notifications through G.S.R. 778(E), 23.10.2025), not a "
                      "secondary summary: that filing amends 'rule 7, sub-rule (2)' "
                      "for 'the height of any numeral and letter' and 'sub-rule (3)' "
                      "for 'the width of any numeral and letter' -- so 7(2) is "
                      "height, 7(3) is width, full stop, primary-sourced. This "
                      "retires the 7(3)-vs-Table-I disagreement in the prior version "
                      "of this string: both readings had the right neighbourhood and "
                      "the wrong sub-rule. STILL NOT SOURCED: the actual height "
                      "figures in the current Table-I referenced by 7(2) -- this "
                      "compilation shows what changed, not the table's present "
                      "contents, and does not reach back to G.S.R. 629(E)/2017 at "
                      "all, so the 50-100cm2 disputed bracket is exactly as "
                      "unresolved as before. Also confirmed, and worth having: "
                      "packages containing medical devices are carved out of both "
                      "7(2) and 7(3) as of G.S.R. 778(E), deferring to the Medical "
                      "Devices Rules, 2017 instead -- consistent with this project's "
                      "own existing decision to scope medical devices out. "
                      "See brief section 3.3.")

    def table_for(self, category):
        if category is None:
            return None, Refusal("CATEGORY_NOT_DECLARED", CATEGORY_PROMPT)
        if category not in self.tables:
            return None, Refusal(
                "CATEGORY_UNKNOWN",
                f"no rule table for {category!r}; known: {tuple(self.tables)}")
        return self.tables[category], None


RULES_2011 = RuleSet(tables={
    CATEGORY_GENERAL: RuleTable(
        rows=[HeightRule(min_height_mm=1.0, label="printed/applied")],
        index_by="flat"),
    CATEGORY_FORMED: RuleTable(
        rows=[HeightRule(min_height_mm=2.0, label="blown/formed/moulded/"
                                                    "embossed/perforated")],
        index_by="flat"),
})


def band(h_mm: float, U_mm: float, threshold_mm: float) -> str:
    if not np.isfinite(h_mm) or not np.isfinite(U_mm):
        return BAND_REFER
    if U_mm < 0:
        raise ValueError("U must be non-negative")
    if h_mm - U_mm >= threshold_mm:
        return BAND_COMPLIANT
    if h_mm + U_mm < threshold_mm:
        return BAND_DEFICIENT
    return BAND_REFER


# ----------------------------------------------------------------------------
# Uncertainty budget.  R6: classify before combining.
# ----------------------------------------------------------------------------

_KINDS = ("random", "systematic")
_SOURCES = ("measured", "modelled", "observed")


H_REF_MM = 1.0   # the height at which every relative value_mm below is quoted


@dataclass(frozen=True)
class BudgetTerm:
    name: str
    value_mm: float             # standard uncertainty (random) or half-width (systematic)
    kind: str                   # 'random' -> RSS ; 'systematic' -> added
    source: str                 # 'measured' | 'modelled' | 'observed'
    note: str = ""
    relative: bool = False      # True -> value_mm is quoted AT H_REF_MM and scales
                                 # with the measured height (a px/mm-type error);
                                 # False -> value_mm is a fixed distance in the
                                 # image plane regardless of glyph height.
                                 # v7.2's patch 3 proposed this field under different
                                 # names (half_width_mm/basis/provenance) that do not
                                 # match this dataclass; this version keeps the real
                                 # field names so the 8 existing positional
                                 # BudgetTerm(...) call sites below stay correct.

    def __post_init__(self):
        if self.kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}")
        if self.source not in _SOURCES:
            raise ValueError(f"source must be one of {_SOURCES}")
        if self.value_mm < 0:
            raise ValueError("uncertainty terms are non-negative")


@dataclass
class Budget:
    terms: list[BudgetTerm] = field(default_factory=list)
    k: float = 2.0

    def add(self, *t: BudgetTerm) -> "Budget":
        self.terms.extend(t)
        return self

    def expanded(self, h_mm: float) -> float:
        """U = k * sqrt(sum of random^2)  +  sum of |systematic|, AT A STATED HEIGHT.

        h_mm is required, with no default. Three terms (scale_calibration,
        fiducial_localisation, lens_distortion_field_position) are fractional
        errors quoted at H_REF_MM and must scale with the measured height; the
        other five are fixed distances in the image plane and do not. A default
        of H_REF_MM would let every old call site keep compiling while silently
        reporting the 1 mm budget forever -- which was the bug this signature
        exists to make impossible to reintroduce. See brief section 6a.

        Systematic one-sided terms are ADDED, never RSS'd.  RSS of a term you
        cannot argue is independent understates the budget, and the plan RSS'd
        everywhere before this was noticed.
        """
        if not (h_mm > 0.0):
            raise ValueError("expanded() needs the measured height; there is no "
                             "height-free U in this budget")
        s = h_mm / H_REF_MM
        rnd = math.sqrt(sum((t.value_mm * (s if t.relative else 1.0)) ** 2
                            for t in self.terms if t.kind == "random"))
        sys_ = sum(t.value_mm * (s if t.relative else 1.0)
                   for t in self.terms if t.kind == "systematic")
        return self.k * rnd + sys_

    def provenance(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {s: [] for s in _SOURCES}
        for t in self.terms:
            out[t.source].append(t.name)
        return out

    def all_measured(self) -> bool:
        """True only if every term has been measured. Governs display precision."""
        return bool(self.terms) and all(t.source == "measured" for t in self.terms)

    def report(self, h_mm: Optional[float] = None) -> str:
        at = H_REF_MM if h_mm is None else h_mm
        U = self.expanded(at)
        at_note = "" if h_mm is not None else f" [at reference height {H_REF_MM:g} mm]"
        if self.all_measured():
            lines = [f"  U(k={self.k:g}) = {U:.4f} mm{at_note}"]
        else:
            lines = [f"  U(k={self.k:g}) = {U:.2f} mm"
                     f"   [2 d.p.: not all terms are measured, so further digits are"
                     f" arithmetic, not accuracy; raw {U:.5f}]{at_note}"]
        rnd = [t for t in self.terms if t.kind == "random"]
        sy = [t for t in self.terms if t.kind == "systematic"]
        if rnd:
            lines.append("  random (RSS, then x k):")
            for t in rnd:
                lines.append(f"    {t.name:28s} {t.value_mm:8.4f}  [{t.source}] {t.note}")
        if sy:
            lines.append("  systematic (added):")
            for t in sy:
                lines.append(f"    {t.name:28s} {t.value_mm:8.4f}  [{t.source}] {t.note}")
        p = self.provenance()
        if p["modelled"] or p["observed"]:
            lines.append("  NOT MEASURED -- these terms are not yet entitled to a decimal place:")
            if p["modelled"]:
                lines.append(f"    modelled: {', '.join(p['modelled'])}")
            if p["observed"]:
                lines.append(f"    observed: {', '.join(p['observed'])}")
        return "\n".join(lines)


def provisional_budget() -> Budget:
    """The current budget, honestly labelled.

    Nothing here is 'measured' yet.  That is the whole point of the label: this
    U is not citeable until the stage-micrometer run replaces the modelled terms.
    """
    return Budget(k=2.0).add(
        BudgetTerm("edge_localisation", 0.010, "random", "modelled",
                   "sub-pixel crossing scatter; synthetic only"),
        BudgetTerm("repeatability_pose", 0.030, "random", "modelled",
                   "PLACEHOLDER -- requires re-seating the package on the rig"),
        BudgetTerm("scale_calibration", 0.010, "random", "modelled",
                   "PLACEHOLDER -- requires the glass stage micrometer",
                   relative=True),
        BudgetTerm("convention_bias_residual", 0.005, "systematic", "modelled",
                   "UNCORRECTED -- convention_bias_mm is 0.0 in production; this "
                   "is the convention's raw noise-induced bias, not a post-"
                   "correction residual. Rename once correction is wired in."),
        BudgetTerm("ink_spread_and_cap_ambiguity", 0.080, "systematic", "modelled",
                   "irreducible under any optical convention; dominates the budget"),
        # --- v7.1 additions -------------------------------------------------
        BudgetTerm("lens_distortion_field_position", 0.010, "systematic", "modelled",
                   "~1% radial distortion at the field edge of an uncorrected "
                   "small-format lens; 1% of a 1 mm glyph = 0.010 mm. Systematic "
                   "for a fixed ROI position -- MEASURE: stage micrometer at field "
                   "centre plus four corners, spread in recovered ppm across them.",
                   relative=True),
        BudgetTerm("defocus_psf_asymmetry", 0.005, "systematic", "modelled",
                   "first order is ZERO -- a symmetric PSF preserves a 50% crossing "
                   "exactly, and the two edges of a 1mm character don't interact. "
                   "Only PSF ASYMMETRY (coma, off-axis astigmatism) moves the "
                   "reading, hence 0.005 not 0.05. MEASURE: sweep focus, watch it move."),
        BudgetTerm("fiducial_localisation", 0.0005, "random", "modelled",
                   "genuinely negligible: 0.2px centroid over a 20mm fiducial "
                   "baseline at 30px/mm is 0.033% relative scale error = 0.00033mm "
                   "on a 1mm glyph, rounded up to 0.0005.",
                   relative=True),
    )


@dataclass
class Verdict:
    band: str
    h_mm: Optional[float]
    U_mm: Optional[float]
    threshold_mm: Optional[float]
    refusals: list[Refusal]
    rule_candidates: list[HeightRule] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    U_all_measured: bool = False

    @property
    def refused(self) -> bool:
        return bool(self.refusals)

    def report(self) -> str:
        if self.refused:
            head = "REFUSED (no measurement reported)"
            body = "\n".join(f"    {r}" for r in self.refusals)
            return f"{head}\n{body}"
        prec = 3 if self.U_all_measured else 2
        return (f"{self.band}\n"
                f"    h = {self.h_mm:.{prec}f} mm,  U = {self.U_mm:.{prec}f} mm (k=2),  "
                f"TL = {self.threshold_mm:.{prec}f} mm")


# =============================================================================
# PART 2 -- GEOMETRY
# =============================================================================

def _normalise(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    c = pts.mean(axis=0)
    d = np.sqrt(((pts - c) ** 2).sum(axis=1)).mean()
    s = math.sqrt(2.0) / d if d > 0 else 1.0
    T = np.array([[s, 0, -s * c[0]], [0, s, -s * c[1]], [0, 0, 1]], float)
    q = (T @ np.c_[pts, np.ones(len(pts))].T).T
    return q[:, :2], T


def homography_dlt(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Normalised DLT.  src/dst are (N,2), N >= 4.

    WARNING, encoded as a refusal elsewhere: with N == 4 the fit is exact and the
    reprojection residual is ZERO BY CONSTRUCTION.  A zero residual from four
    points is not evidence of planarity, it is arithmetic.  Use >= 5 features.
    """
    src = np.asarray(src, float)
    dst = np.asarray(dst, float)
    if src.shape != dst.shape or src.shape[0] < 4:
        raise ValueError("need matching point sets with N >= 4")
    s, Ts = _normalise(src)
    d, Td = _normalise(dst)
    A = []
    for (x, y), (u, v) in zip(s, d):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, Vt = np.linalg.svd(np.asarray(A, float))
    Hn = Vt[-1].reshape(3, 3)
    H = np.linalg.inv(Td) @ Hn @ Ts
    return H / H[2, 2]


def apply_h(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    pts = np.atleast_2d(np.asarray(pts, float))
    q = (H @ np.c_[pts, np.ones(len(pts))].T).T
    return q[:, :2] / q[:, 2:3]


def reproject_rms(H: np.ndarray, src: np.ndarray, dst: np.ndarray) -> float:
    e = apply_h(H, src) - np.asarray(dst, float)
    return float(np.sqrt((e ** 2).sum(axis=1).mean()))


def effective_px_per_mm(H: np.ndarray, at_mm: Sequence[float]) -> float:
    """Local isotropic scale of the mm->px map at a point, sqrt|det J|."""
    x, y = float(at_mm[0]), float(at_mm[1])
    h = H.ravel()
    w = h[6] * x + h[7] * y + h[8]
    u = h[0] * x + h[1] * y + h[2]
    v = h[3] * x + h[4] * y + h[5]
    J = np.array([[(h[0] * w - u * h[6]), (h[1] * w - u * h[7])],
                  [(h[3] * w - v * h[6]), (h[4] * w - v * h[7])]]) / (w * w)
    return float(math.sqrt(abs(np.linalg.det(J))))


def polygon_area_mm2(pts: Sequence[Sequence[float]]) -> float:
    p = np.asarray(pts, float)
    x, y = p[:, 0], p[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def rect_area_u_mm2(w_mm: float, h_mm: float, u_w: float, u_h: float) -> tuple[float, float]:
    """Area and its standard uncertainty for independent side uncertainties.

    Relative RSS: u_A/A = sqrt((u_w/w)^2 + (u_h/h)^2).  This is the one place RSS
    is correct here, because the two side measurements are independent.
    """
    A = w_mm * h_mm
    rel = math.sqrt((u_w / w_mm) ** 2 + (u_h / h_mm) ** 2)
    return A, A * rel


# =============================================================================
# PART 3 -- MEASUREMENT PRIMITIVES
# =============================================================================

def levels_percentile(roi: np.ndarray, lo: float = 2.0, hi: float = 98.0
                      ) -> tuple[float, float]:
    """Percentile endpoints.  Kept for comparison only.

    Failure mode: the endpoints sit a fixed ABSOLUTE noise-tail distance inside
    the true levels, and the two classes have different occupancy (ink is a
    minority of the ROI), so the displacements are ASYMMETRIC.  The midpoint
    therefore shifts toward the substrate by an amount ~ proportional to the
    noise and independent of contrast -- which, divided by an edge slope
    proportional to contrast, is exactly a 1/contrast bias.  Use levels_iterative.
    """
    f = roi[np.isfinite(roi)]
    if f.size == 0:
        return 0.0, 0.0
    return float(np.percentile(f, lo)), float(np.percentile(f, hi))


def levels_iterative(roi: np.ndarray, iters: int = 3) -> tuple[float, float]:
    """Two-class means, seeded from percentiles.

    Class means are biased toward the midpoint, but that bias scales WITH
    contrast, so the CONTRAST DEPENDENCE cancels in the 50% criterion -- it does
    not produce a 1/C term.  It does not fully cancel: a contrast-independent
    class-occupancy offset of ~1.5 um (a scene-geometry effect, not photometric)
    remains at noise=0.  Baseline-correct against that offset before treating
    exposure_test's `inv = bias*C/noise` as meaningful; the raw statistic
    conflates the offset's 1/noise contribution with genuine noise-driven drift.
    """
    f = roi[np.isfinite(roi)]
    if f.size == 0:
        return 0.0, 0.0
    ink, sub = float(np.percentile(f, 2)), float(np.percentile(f, 98))
    for _ in range(iters):
        t = 0.5 * (ink + sub)
        lo, hi = f[f < t], f[f >= t]
        if lo.size < 8 or hi.size < 8:
            break
        ink, sub = float(lo.mean()), float(hi.mean())
    return ink, sub


@dataclass(frozen=True)
class Crossing:
    top: float
    bot: float
    clipped_top: bool
    clipped_bot: bool

    @property
    def extent_px(self) -> float:
        return self.bot - self.top


def crossings(profile: np.ndarray, level: float) -> Optional[Crossing]:
    """First and last sub-pixel crossing of `level` in a 1-D profile.

    Linear interpolation between the bracketing samples.  Hand-check on a hard
    step with `level` at the exact midpoint of ink and substrate:
        top = (i0-1) + (sub-level)/(sub-ink) = (i0-1) + 0.5
        bot =  i1    + (level-ink)/(sub-ink) =  i1    + 0.5
        extent = i1 - i0 + 1  == the rendered pixel count, for ANY (ink, sub).
    That identity is why exposure_test() must use a RESOLVED edge and noise: on
    an unblurred bar the answer is exposure-invariant by algebra and the test can
    neither confirm nor falsify anything.
    """
    p = np.asarray(profile, float)
    below = p < level
    if not below.any():
        return None
    idx = np.flatnonzero(below)
    i0, i1 = int(idx[0]), int(idx[-1])
    ct = cb = False
    if i0 == 0:
        top, ct = -0.5, True
    else:
        a, b = p[i0 - 1], p[i0]
        top = (i0 - 1) + ((a - level) / (a - b) if a != b else 0.5)
    if i1 == len(p) - 1:
        bot, cb = float(i1) + 0.5, True
    else:
        a, b = p[i1], p[i1 + 1]
        bot = i1 + ((level - a) / (b - a) if b != a else 0.5)
    return Crossing(float(top), float(bot), ct, cb)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    m = np.asarray(mask, bool).astype(np.int8)
    d = np.diff(np.concatenate(([0], m, [0])))
    a = np.flatnonzero(d == 1)
    b = np.flatnonzero(d == -1) - 1
    return list(zip(a.tolist(), b.tolist()))


def mm_to_px(mm: float, ppm: float, floor_px: int = 2) -> tuple[int, bool]:
    """R2: a millimetre threshold in pixels, plus whether the floor is binding.

    When the floor binds, the effective physical threshold is NOT the millimetre
    value you asked for, and any sweep over ppm is testing integer arithmetic.
    """
    px = mm * ppm
    v = int(round(px))
    if v < floor_px:
        return floor_px, True
    return v, False


def detect_spans(colmask: np.ndarray, ppm: float,
                 min_width_mm: float = 0.05,
                 min_gap_mm: float = 0.06) -> tuple[list[tuple[int, int]], bool]:
    min_w, f1 = mm_to_px(min_width_mm, ppm, 2)
    min_g, f2 = mm_to_px(min_gap_mm, ppm, 1)
    r = _runs(colmask)
    if not r:
        return [], (f1 or f2)
    merged = [list(r[0])]
    for a, b in r[1:]:
        if a - merged[-1][1] - 1 < min_g:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if (b - a + 1) >= min_w], (f1 or f2)


def span_levels(work: np.ndarray, spans: Sequence[tuple[int, int]], ppm: float,
                pad_mm: float = 0.075) -> list[tuple[float, float]]:
    """Per-span ink/substrate levels from a neighbourhood defined in MILLIMETRES.

    v6 used pad=6 PIXELS: 0.75 mm of support at 8 px/mm and 0.075 mm at 80 px/mm.
    A level estimator whose physical support changes with the swept variable makes
    a resolution sweep meaningless, and it did.
    """
    pad, _ = mm_to_px(pad_mm, ppm, 2)
    H, W = work.shape
    out = []
    for c0, c1 in spans:
        a, b = max(0, c0 - pad), min(W, c1 + 1 + pad)
        out.append(levels_iterative(work[:, a:b]))
    return out


def column_extents(work: np.ndarray, span: tuple[int, int], level: float
                   ) -> list[Optional[Crossing]]:
    c0, c1 = span
    return [crossings(work[:, c], level) for c in range(c0, c1 + 1)]


def combine_extents(cx: Sequence[Optional[Crossing]], ppm: float,
                    rule: str = "max_supported",
                    min_support_mm: float = 0.02,
                    tol_mm: float = 0.02,
                    bin_mm: float = 0.10,  # cols_per_bin = ppm*bin_mm; need >=2 at
                                            # min_px_per_mm=30 -> bin_mm >= 0.067;
                                            # 0.10 gives 3.0 cols/bin at the floor
                    report: Optional[dict] = None) -> Optional[float]:
    """Reduce per-column edge fits to one height, under a NAMED convention.

    Measured on real letterforms (A B M O V W 1 4 8), three axes that matter
    (clean-condition spread, noise-decomposed repeatability, noise-induced bias
    shift; see convention_bakeoff, which now also characterises max_binned):

        rule           letterform spread   repeatability sd   noise -> bias
        q5  (intensity)     0.00214            0.00062           +0.00037
        p95 (position)      0.00214            0.00053           +0.00028
        max (position)      0.00114            0.00052           +0.00137

    'max' is ~1.9x the most letterform-independent, but "most repeatable" overstates
    it: decomposed against the noise-free row, its repeatability edge over q5 is
    ~1.2x, not the multiple the pooled sd above implies (that number mixes 9
    glyph morphologies with 5 seeds).  Its real advantage is letterform
    independence at ~1.9x, and its real cost is ~3.7x the noise-induced bias
    shift.  Every one of these deltas is <=0.003 mm against the 0.08 mm
    irreducible ink-spread floor, so this table does not license ranking the
    conventions -- choose on legal grounds, measure the bias, correct it.  Its
    noise term appears as a PREDICTABLE BIAS SHIFT rather than as scatter
    -- a bias can be measured and corrected, scatter cannot.  Its one real
    weakness is that a single stray ink pixel would define the height, in the
    flattering direction.  That is a defect-rejection problem, so it is fixed in
    defect rejection: 'max_supported' takes the extreme reach but requires it to
    be supported by a contiguous run of columns.

    Declare it as "the letter's maximum ink extent, excluding artifacts narrower
    than <min_support_mm>".  Do NOT declare "the 95th percentile of the letter":
    no statute regulates a percentile of a letter, and the phrase will not
    survive being read aloud.

    'median' is rejected outright: -0.301 mm on letterforms, spread 0.61 mm.
    """
    good = [c for c in cx if c is not None]
    if not good:
        return None
    tops = np.array([c.top for c in good], float)
    bots = np.array([c.bot for c in good], float)
    if rule == "median":
        t, b = float(np.median(tops)), float(np.median(bots))
    elif rule == "p95":
        t, b = float(np.percentile(tops, 5.0)), float(np.percentile(bots, 95.0))
    elif rule == "max":
        t, b = float(tops.min()), float(bots.max())
    elif rule == "max_supported":
        sup, sup_floored = mm_to_px(min_support_mm, ppm, 2)
        effective_support_mm = sup / float(ppm)
        if report is not None:
            report.update(support_floored=sup_floored,
                          effective_support_mm=effective_support_mm)
        tol = tol_mm * ppm
        t = _supported_extreme(tops, sup, tol, take_min=True)
        b = _supported_extreme(bots, sup, tol, take_min=False)
        if t is None or b is None:
            t, b = float(tops.min()), float(bots.max())
    elif rule == "max_binned":
        # Extreme over fixed MILLIMETRE bins, so the number of draws entering
        # the extreme is a property of the letterform, not the sensor.
        # nb is computed in mm (len(good)//w was ppm-dependent in practice),
        # and array_split means nothing is discarded -- the old floor-divide
        # dropped 0 of 4 columns at 30 px/mm and 6 of 22 at 160 px/mm, a
        # ppm-dependent artefact inside the patch whose entire purpose was
        # scale invariance.
        nb = max(1, int(round((len(good) / ppm) / bin_mm)))
        nb = min(nb, len(good))
        per_bin = len(good) / nb
        if report is not None:
            report.update(n_bins=nb, cols_used=len(good),
                          cols_per_bin=per_bin,
                          bin_starved=bool(per_bin < 2.0))
        tb = np.array([b.mean() for b in np.array_split(tops, nb)])
        bb = np.array([b.mean() for b in np.array_split(bots, nb)])
        t, b = float(tb.min()), float(bb.max())
    else:
        raise ValueError(f"unknown rule {rule!r}")
    return float(b - t) / ppm


def _supported_extreme(vals: np.ndarray, support_cols: int, tol_px: float,
                       take_min: bool) -> Optional[float]:
    """The most extreme value that sits in a contiguous run of >= support_cols
    columns all within tol_px of it.  Rejects isolated excursions (a hot pixel,
    a dust speck) without blunting the estimator the way a percentile does."""
    n = len(vals)
    if n == 0:
        return None
    order = np.argsort(vals) if take_min else np.argsort(-vals)
    for i in order:
        v = vals[i]
        lo = hi = int(i)
        cmp = (lambda x: x <= v + tol_px) if take_min else (lambda x: x >= v - tol_px)
        while lo - 1 >= 0 and cmp(vals[lo - 1]):
            lo -= 1
        while hi + 1 < n and cmp(vals[hi + 1]):
            hi += 1
        if (hi - lo + 1) >= support_cols:
            return float(v)
    return None


@dataclass
class GlyphRead:
    """`heights` is PARALLEL TO `spans` and holds None where no measurement was
    possible (R8).  This is deliberate: v6 appended only successful heights, so a
    dropped glyph silently re-aligned every downstream comparison."""
    heights: list[Optional[float]]
    spans: list[tuple[int, int]]
    levels: list[tuple[float, float]]
    global_levels: tuple[float, float]
    work: np.ndarray
    floor_limited: bool
    edge_clipped: bool
    per_column: list[list[Optional[Crossing]]]

    @property
    def valid(self) -> list[float]:
        return [h for h in self.heights if h is not None]


def measure_glyphs(roi: np.ndarray, ppm: float,
                   rule: str = "max_supported",
                   profile_q: Optional[float] = None,
                   local_levels: bool = True,
                   min_width_mm: float = 0.05,
                   min_gap_mm: float = 0.06,
                   pad_mm: float = 0.075,
                   level_override: Optional[float] = None,
                   reports: Optional[list] = None) -> GlyphRead:
    """Measure every detected glyph in a rectified ROI.

    Two paths.  `profile_q` selects the intensity path (percentile across a
    span's columns, then one crossing).  Otherwise the position path is used
    (per-column crossings, then `combine_extents`).  On real letterforms the
    intensity q=5 path and the position p95 path agree to 3e-7 mm because both
    lock onto the same few extreme columns -- the position path buys diagnostics,
    not accuracy.  q=50 does not merely under-measure: it DELETES glyphs whose
    median column never crosses the level (the open letterforms), which is why
    the glyph-count check below is not optional.
    """
    work = np.asarray(roi, float)
    g_ink, g_sub = levels_iterative(work)
    g_level = 0.5 * (g_ink + g_sub) if level_override is None else float(level_override)
    colmask = np.any(work < g_level, axis=0)
    spans, floored = detect_spans(colmask, ppm, min_width_mm, min_gap_mm)
    levels = (span_levels(work, spans, ppm, pad_mm) if local_levels
              else [(g_ink, g_sub)] * len(spans))

    heights: list[Optional[float]] = []
    percol: list[list[Optional[Crossing]]] = []
    clipped = False
    for (c0, c1), (ink, sub) in zip(spans, levels):
        lev = 0.5 * (ink + sub) if level_override is None else float(level_override)
        if profile_q is not None:
            prof = np.percentile(work[:, c0:c1 + 1], profile_q, axis=1)
            cx = crossings(prof, lev)
            percol.append([cx])
            if cx is None:
                heights.append(None)
            else:
                clipped |= (cx.clipped_top or cx.clipped_bot)
                heights.append(cx.extent_px / ppm)
        else:
            cols = column_extents(work, (c0, c1), lev)
            percol.append(cols)
            clipped |= any(c is not None and (c.clipped_top or c.clipped_bot)
                           for c in cols)
            heights.append(combine_extents(cols, ppm, rule=rule,
                                           report=(reports.append({}) or reports[-1])
                                           if reports is not None else None))
    return GlyphRead(heights, spans, levels, (g_ink, g_sub), work,
                     floored, clipped, percol)


def illumination_profile(work: np.ndarray) -> np.ndarray:
    """Per-column substrate estimate."""
    return np.percentile(np.asarray(work, float), 90, axis=0)


def illumination_gradient(work: np.ndarray) -> float:
    p = illumination_profile(work)
    return float(p.max() - p.min())


def clipped_fraction_in_spans(work: np.ndarray, spans: Sequence[tuple[int, int]],
                              level: float = 0.995) -> float:
    """Clipping WHERE IT DOES DAMAGE.

    A whole-ROI clipped fraction is the wrong shape: a 0.2 mm specular spot that
    erases a stroke is 0.25% of a small ROI and 0.01% of a large one, so the
    criterion weakens as the field of view grows.  Measure inside the columns
    that carry glyphs.  (This still cannot see a spot that erases a glyph
    completely -- that is what the count check is for.  You cannot detect a
    missing thing by inspecting the things you found.)
    """
    w = np.asarray(work, float)
    if not spans:
        return float(np.mean(w >= level))
    cols = np.concatenate([np.arange(c0, c1 + 1) for c0, c1 in spans])
    return float(np.mean(w[:, cols] >= level))


# =============================================================================
# PART 4 -- REFUSAL LAYER (R4: it lives here, not in a test)
# =============================================================================

@dataclass
class CaptureLimits:
    min_px_per_mm: float = 30.0                 # engineering target; NOT a proven minimum
    min_feature_count: int = 5                   # 4 gives a zero residual by construction
    max_homography_rms_px: float = 1.0
    min_contrast: float = 0.15
    max_clipped_fraction_in_spans: float = 0.002
    max_illum_gradient: float = 0.10             # derive this: see gradient_limit_from_budget()
    expected_glyphs: Optional[int] = None        # operator-entered; None disables
    check_extent_spread: bool = False            # OFF by default -- see note
    max_glyph_spread_mm: float = 0.15
    allow_floor_limited: bool = False
    characterisation: bool = False

    @classmethod
    def for_characterisation(cls, **kw) -> "CaptureLimits":
        """R5.  Disabling a limit to CHARACTERISE is legitimate; disabling it to
        VALIDATE is not, and a characterisation override must never become the
        dataclass default.  v6 shipped min_px_per_mm=0.0 as the default."""
        base = dict(min_px_per_mm=0.0, min_feature_count=0,
                    max_illum_gradient=math.inf,
                    max_clipped_fraction_in_spans=math.inf,
                    allow_floor_limited=True, characterisation=True)
        base.update(kw)
        return cls(**base)


def measurement_completeness(reads, min_frac: float = 1.0) -> Optional[Refusal]:
    """A detection is not a measurement.

    GLYPH_COUNT compares detections against the expected count and is blind to
    a glyph that was found, matched, and then produced no crossing -- the q50
    failure: spans 9/9 and silent, heights 7/9. A count cannot see a missing
    value, so check the values.
    """
    total = dropped = 0
    for g in reads:
        for h in g.heights:
            total += 1
            if h is None or not np.isfinite(h):
                dropped += 1
    if total == 0:
        return Refusal("NO_MEASURAND", "no glyph produced a height")
    if dropped and (total - dropped) < min_frac * total:
        return Refusal(
            "MEASUREMENT_DROPPED",
            f"{dropped} of {total} detected glyphs produced no crossing at the "
            f"declared 50% level; the {total - dropped} survivors are a "
            f"self-selected subset -- the glyphs that fail are the thin-stroke "
            f"and low-contrast ones, i.e. the ones nearest the limit -- so "
            f"their mean is not an estimate of the population")
    return None


def capture_checks(g: GlyphRead, ppm: float, lim: CaptureLimits,
                   H: Optional[np.ndarray] = None,
                   src_mm: Optional[np.ndarray] = None,
                   dst_px: Optional[np.ndarray] = None) -> list[Refusal]:
    out: list[Refusal] = []

    if ppm < lim.min_px_per_mm:
        out.append(Refusal("RESOLUTION",
                           f"{ppm:.1f} px/mm below the declared operating floor "
                           f"{lim.min_px_per_mm:.1f}; move closer or use a longer lens"))

    if src_mm is not None:
        n = len(src_mm)
        if n < lim.min_feature_count:
            out.append(Refusal("NO_REDUNDANCY",
                               f"{n} fiducials: a 4-point homography fits exactly, so its "
                               f"reprojection residual is zero by construction and cannot "
                               f"evidence planarity. Print >= {lim.min_feature_count}."))
        elif H is not None and dst_px is not None:
            rms = reproject_rms(H, src_mm, dst_px)
            if rms > lim.max_homography_rms_px:
                out.append(Refusal("PLANARITY",
                                   f"reprojection RMS {rms:.2f} px > "
                                   f"{lim.max_homography_rms_px:.2f}; surface is not planar "
                                   f"or a fiducial is misidentified"))

    ink, sub = g.global_levels
    if (sub - ink) < lim.min_contrast:
        out.append(Refusal("CONTRAST",
                           f"ink/substrate separation {sub - ink:.3f} < {lim.min_contrast:.3f}; "
                           f"the 50% criterion has no edge to sit on"))

    if not g.spans:
        out.append(Refusal("NO_GLYPH", "no character-like column runs detected in the ROI"))

    cf = clipped_fraction_in_spans(g.work, g.spans)
    if cf > lim.max_clipped_fraction_in_spans:
        out.append(Refusal("CLIPPED",
                           f"{100 * cf:.3f}% of glyph-column pixels at or above saturation; "
                           f"specular highlight -- re-light, do not re-shoot from the same angle"))

    grad = illumination_gradient(g.work)
    if grad > lim.max_illum_gradient:
        out.append(Refusal("ILLUMINATION_GRADIENT",
                           f"substrate level varies by {grad:.3f} across the ROI "
                           f"(limit {lim.max_illum_gradient:.3f})"))

    if lim.expected_glyphs is not None and len(g.spans) != lim.expected_glyphs:
        # '!=' and not '<': a split character RAISES the count, and a split is
        # just as much a failure as a deletion.  This check was written for
        # glare and it caught an algorithm defect instead (q=50 deleting open
        # letterforms).  A count is the only check that can see a deletion --
        # every consistency check operates on the survivors.
        out.append(Refusal("GLYPH_COUNT",
                           f"detected {len(g.spans)} characters, operator declared "
                           f"{lim.expected_glyphs}; a character has been deleted, split "
                           f"or merged"))

    if g.edge_clipped:
        out.append(Refusal("ROI_EDGE",
                           "a glyph's ink touches the ROI boundary; its extent is truncated"))

    if g.floor_limited and not lim.allow_floor_limited:
        out.append(Refusal("FLOOR_LIMITED",
                           "detection thresholds are pinned to their integer pixel floors, "
                           "so the effective physical criteria are not the declared ones"))

    if lim.check_extent_spread:
        # OFF by default.  On real packaging the characters legitimately differ
        # in height (caps vs x-height vs digits vs round-glyph overshoot), so a
        # spread limit only makes sense on a reference target of nominally equal
        # characters.  Enabling it in production manufactures refusals.
        v = g.valid
        if len(v) >= 2 and (max(v) - min(v)) > lim.max_glyph_spread_mm:
            out.append(Refusal("EXTENT_SPREAD",
                               f"glyph heights span {max(v) - min(v):.3f} mm "
                               f"> {lim.max_glyph_spread_mm:.3f}"))
    return out


# =============================================================================
# PART 5 -- TOP-LEVEL MEASUREMENT
# =============================================================================

def measure(roi: np.ndarray, ppm: float, table: Optional[RuleTable],
            index_value: Optional[float] = None, index_u: float = 0.0,
            limits: Optional[CaptureLimits] = None,
            budget: Optional[Budget] = None,
            convention: str = "max_supported",  # max_binned reverted: bin_mm sized for
                                                 # the resolution floor wrecks letterform
                                                 # independence (spread 0.039mm vs 0.001mm) --
                                                 # worse than the problem it fixed. Opt in only.
            convention_bias_mm: float = 0.0,
            H: Optional[np.ndarray] = None,
            src_mm: Optional[np.ndarray] = None,
            dst_px: Optional[np.ndarray] = None,
            external_TL: Optional[float] = None) -> Verdict:
    """One package, one capture, one verdict.

    `convention_bias_mm` is SUBTRACTED from the reading.  The order is:
    define the measurand -> choose the convention on legal grounds -> measure its
    bias against a reference -> correct -> carry the correction's residual in the
    budget.  Never: choose the convention that makes the bias smallest.  Zeroing
    a bias by changing the measurand is how you end up unable to say what you
    measured.

    `external_TL`, added for the lm_legal_model integration: when given, this
    IS the threshold, full stop -- table.governing_threshold() is not called,
    and `table` may be None. Resolving which bracket applies (dispute checks,
    rule-version checks, the PDP-area table) is lm_legal_model's job now for
    any caller that goes through measure_with_category's integrated path;
    this parameter is how that resolved number reaches the pixel-measurement
    code without this function re-deriving it. Existing callers that pass a
    `table` and no `external_TL` are completely unaffected -- this branch is
    additive.
    """
    if external_TL is None and table is None:
        raise ValueError("measure() needs either table or external_TL")
    lim = limits or CaptureLimits()
    bud = budget or provisional_budget()
    reports: list = []
    g = measure_glyphs(roi, ppm, rule=convention, reports=reports)
    refusals = capture_checks(g, ppm, lim, H=H, src_mm=src_mm, dst_px=dst_px)
    drop = measurement_completeness([g])
    if drop is not None:
        refusals.append(drop)
    starved = sum(1 for r in reports if r.get("bin_starved"))
    if starved:
        refusals.append(Refusal("BIN_STARVED",
            f"{starved} of {len(reports)} glyphs had fewer than 2 columns per "
            f"bin, so the realised convention is a per-column extreme, not the "
            f"declared binned extreme"))

    warnings: list[str] = []
    support_floored = [r for r in reports if r.get("support_floored")]
    if support_floored:
        eff = support_floored[0].get("effective_support_mm")
        warnings.append(
            f"SUPPORT_WIDTH_FLOORED: min_support_mm is pixel-floor-limited at this "
            f"ppm; effective support is {eff:.4f} mm, not the declared value. This "
            f"is a warning, not a refusal -- at ppm near the 30 px/mm operating "
            f"floor this fires on essentially every capture, and refusing on it "
            f"would make the tool unusable at its own declared floor.")

    diag = dict(n_spans=len(g.spans),
                levels=g.global_levels,
                illum_gradient=illumination_gradient(g.work),
                clipped_in_spans=clipped_fraction_in_spans(g.work, g.spans),
                floor_limited=g.floor_limited,
                convention=convention,
                heights_mm=list(g.heights),
                glyph_reports=reports,
                warnings=warnings)

    if refusals:
        return Verdict(BAND_REFER, None, None, None, refusals, [], diag)

    v = g.valid
    if not v:
        return Verdict(BAND_REFER, None, None, None,
                       [Refusal("NO_MEASUREMENT", "no glyph produced a usable edge pair")],
                       [], diag)

    # The regulated quantity is the height of the SMALLEST required character.
    # v is a plain list (GlyphRead.valid), so plain min()/argmin, no numpy needed.
    gov_idx = min(range(len(v)), key=lambda i: v[i])
    h = float(v[gov_idx]) - convention_bias_mm
    diag["governing_glyph_index"] = gov_idx
    diag["governing_glyph_extent_mm"] = float(v[gov_idx])
    diag["glyph_extents_mm"] = [float(x) for x in v]
    diag["dropped_glyph_indices"] = [i for i, hh in enumerate(g.heights) if hh is None]
    if external_TL is not None:
        # Already deterministic -- resolve_threshold() picked exactly one
        # bracket, or measure_with_category() refused before reaching here.
        # No row ambiguity is possible, so no RULE_INDEX_AMBIGUOUS check.
        TL, cands = external_TL, []
    else:
        TL, cands = table.governing_threshold(index_value, index_u)
        if len(cands) > 1:
            refusals.append(Refusal("RULE_INDEX_AMBIGUOUS",
                                    f"{len(cands)} table rows are consistent with the index "
                                    f"value; the strictest ({TL:.1f} mm) has been applied"))
    # Evaluate U at max(h, TL), never at the smaller of the two: for a packet
    # measuring below its requirement, U(h) < U(TL), which narrows the band and
    # makes a confident DEFICIENT easier to reach -- the one direction section
    # 7.1 commits this project not to err in. See brief section 6a.
    U_at_mm = max(h, TL)
    U = bud.expanded(U_at_mm)
    diag["U_breakdown"] = bud.report(U_at_mm)
    diag["convention_line"] = (
        f"convention: 50% ink-to-substrate crossing, "
        f"declared bias correction = {convention_bias_mm:.4f} mm")
    return Verdict(band(h, U, TL), h, U, TL, refusals, cands, diag,
                   U_all_measured=bud.all_measured())


def measure_with_category(roi: np.ndarray, ppm: float, ruleset: RuleSet,
                          category: Optional[str], *,
                          allow_undefined_measurand: bool = False,
                          pdp_area_cm2: Optional[float] = None,
                          commodity_class: Optional[str] = None,
                          as_of=None,
                          **kwargs) -> Verdict:
    """Product entry point: resolve the legal table, then gate on the measurand.

    TWO PATHS.

    Legacy path (commodity_class is None, the default): v7's own flat
    ruleset.table_for(category) lookup, exactly as before this function was
    integrated with lm_legal_model -- this branch is untouched code, so every
    existing caller (the demo, the self-test harness) is byte-identical and
    unaffected by anything below.

    Integrated path (commodity_class given): resolves the threshold through
    lm_legal_model.resolve_threshold() instead of the flat constant, per the
    precedence lm_legal_model.py's own INTEGRATION block specifies:
    category declared -> category recognised -> can we measure this surface
    -> threshold. See that file for the full reasoning; this implements call
    sites 1 and 2 from that block. Call site 3 (the report) is left for
    whoever builds the operator-facing report, per that block's own
    instruction that convention lines must stay separate from the
    requirement line -- this function returns a Verdict, it does not print.

    Known hole, stated rather than hidden: calling measure() directly bypasses
    both paths' gates entirely. measure() is the primitive; anything on the
    demo path must go through this function.
    """
    if commodity_class is None:
        table, ref = ruleset.table_for(category)
        if ref is not None:
            return Verdict(BAND_REFER, None, None, None, [ref], [], {})
        if not measurand_is_defined(category) and not allow_undefined_measurand:
            return Verdict(BAND_REFER, None, None, None,
                           [Refusal("MEASURAND_UNDEFINED", MEASURAND_UNDEFINED_PROMPT)],
                           [], {"category": category, "measurand_defined": False})
        return measure(roi, ppm, table, **kwargs)

    if not _LEGAL_MODEL_AVAILABLE:
        return Verdict(BAND_REFER, None, None, None,
                       [Refusal("LEGAL_MODEL_UNAVAILABLE",
                                "commodity_class was declared, which asks for the "
                                "integrated legal lookup, but lm_legal_model could "
                                "not be imported")],
                       [], {})

    res = _legal.resolve_threshold(
        commodity_class=commodity_class,
        package_category=category,
        pdp_area_cm2=pdp_area_cm2,
        as_of=as_of,
        ruleset=_legal.PCR_2011,
    )

    # Category-level blockers win regardless of measurand or PDP area --
    # "category declared -> category recognised" is first in the specified
    # order. THIS MODULE (lm_legal_model) OWNS CATEGORY_NOT_DECLARED now;
    # ruleset.table_for's own branch for it is unreachable on this path and is
    # NOT deleted from the legacy path above -- it is v7's second line of
    # defence for anyone calling the legacy path directly.
    _CATEGORY_LEVEL = {_legal.BLOCK_COMMODITY_NOT_DECLARED, _legal.BLOCK_COMMODITY_UNKNOWN,
                       _legal.BLOCK_RULESET_NOT_APPLICABLE, _legal.BLOCK_CATEGORY_NOT_DECLARED,
                       _legal.BLOCK_CATEGORY_UNKNOWN}
    cat_blockers = [b for b in res.blockers if b.code in _CATEGORY_LEVEL]
    if cat_blockers:
        return Verdict(BAND_REFER, None, None, None,
                       [Refusal(b.code, b.cause) for b in cat_blockers], [],
                       {"commodity_class": commodity_class, "category": category,
                        "legal_resolution": res})

    # Category is now known and recognised. "Can we measure this surface"
    # comes next, before threshold resolution: MEASURAND_UNDEFINED is v7's
    # gate, conditional only on category, so it must not wait on pdp_area_cm2
    # -- a formed/embossed pack is unmeasurable whether or not its panel area
    # was declared, and that is the more fundamental refusal of the two.
    if not measurand_is_defined(category) and not allow_undefined_measurand:
        return Verdict(BAND_REFER, None, None, None,
                       [Refusal("MEASURAND_UNDEFINED", MEASURAND_UNDEFINED_PROMPT)],
                       [], {"category": category, "measurand_defined": False,
                            "commodity_class": commodity_class,
                            "legal_resolution": res})

    # Threshold resolution: PDP area, rule-version, and dispute blockers.
    if not res.resolved:
        return Verdict(BAND_REFER, None, None, None,
                       [Refusal(b.code, b.cause) for b in res.blockers], [],
                       {"commodity_class": commodity_class, "category": category,
                        "legal_warnings": list(res.warnings),
                        "legal_resolution": res})

    v = measure(roi, ppm, None, external_TL=res.threshold_mm, **kwargs)
    v.diagnostics["legal_resolution"] = res
    return v


def legal_report_lines(v: Verdict) -> tuple[str, ...]:
    """Call site 3 from lm_legal_model.py's INTEGRATION block, as a function
    rather than inline duplication at every caller.

    Builds the operator-facing legal report for any Verdict that went through
    measure_with_category's integrated path -- refusal or not, since
    MeasurementConvention.report_lines() is explicitly written to handle
    threshold_mm=None. Returns an empty tuple for a Verdict from the legacy
    path (no commodity_class declared) or from calling measure() directly,
    since there is no `res` to report on; this is a silent no-op by design,
    not a refusal -- a caller not using the integrated path was not asking
    for this report.

    Deliberately NOT merged into measure_with_category's return value: that
    function returns a Verdict and does not print, per this block's own
    instruction that convention lines must stay separate from the
    requirement line. This function is what a caller building an actual
    operator-facing report -- lm_capture.py's manifest, a demo screen, a
    saved record -- calls next, on its own schedule, not v7's.
    """
    res = v.diagnostics.get("legal_resolution")
    if res is None or not _LEGAL_MODEL_AVAILABLE:
        return ()
    lines = list(_legal.DEFAULT_CONVENTION.report_lines(res.threshold_mm, res))
    lines.append(_legal.width_check_status())
    lines.extend(res.warnings)
    return tuple(lines)


# =============================================================================
# PART 6 -- SYNTHETIC SCENES.  R1 throughout: truth comes from the render.
# =============================================================================

def _gaussian_blur(img: np.ndarray, sigma_px: float) -> np.ndarray:
    if sigma_px <= 0:
        return img.copy()
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(img, sigma_px, mode="nearest")


def blur_noise(img: np.ndarray, sigma_px: float, noise: float, seed: int) -> np.ndarray:
    out = _gaussian_blur(img, sigma_px)
    if noise > 0:
        out = out + np.random.default_rng(seed).normal(0.0, noise, out.shape)
    return np.clip(out, 0.0, 1.0)


@dataclass
class Scene:
    img: np.ndarray
    ppm: float
    roi_box: tuple[int, int, int, int]          # x0, y0, x1, y1 inclusive
    truth: list[tuple[str, float, int, int]]    # label, height_mm, col0, col1 (ROI-local)

    def roi(self) -> np.ndarray:
        x0, y0, x1, y1 = self.roi_box
        return self.img[y0:y1 + 1, x0:x1 + 1]


def make_bars(ppm: float = 80.0, h_mm: float = 1.0, stroke_mm: float = 0.6,
              contrast: tuple[float, float] = (0.10, 0.85), n: int = 5,
              spread_mm: float = 0.02, canvas_w_mm: float = 22.0,
              canvas_h_mm: float = 6.0, pitch_mm: Optional[float] = None) -> Scene:
    """Rectangular bars on a hard pixel grid.

    R1: `truth` is (yb - ya)/ppm, the number of rows actually inked, NOT
    h_mm + 2*spread_mm.  v6 declared 1.040 while rendering 84 rows at 80 px/mm =
    1.050, and that +0.010 mm was ~98% of every 'bias' the exposure table
    reported.  Its own repeatability line printed 1.04999995 next to a 1.04
    truth and nobody read it.
    """
    ink, sub = contrast
    W = int(round(canvas_w_mm * ppm))
    H = int(round(canvas_h_mm * ppm))
    img = np.full((H, W), float(sub))
    pitch = pitch_mm if pitch_mm is not None else max(1.8 * stroke_mm, 0.36)
    y_base = canvas_h_mm / 2.0 + h_mm / 2.0
    ya = int(round((y_base - h_mm - spread_mm) * ppm))
    yb = int(round((y_base + spread_mm) * ppm))
    x0 = 2.0
    cols: list[tuple[int, int]] = []
    for i in range(n):
        xa = int(round((x0 + i * pitch) * ppm))
        xb = int(round((x0 + i * pitch + stroke_mm + 2 * spread_mm) * ppm))
        img[ya:yb, xa:xb] = float(ink)
        cols.append((xa, xb - 1))
    truth_mm = (yb - ya) / ppm
    m = int(round(0.5 * ppm))
    box = (max(0, cols[0][0] - m), max(0, ya - m),
           min(W - 1, cols[-1][1] + m), min(H - 1, yb - 1 + m))
    truth = [(f"bar{i}", truth_mm, c0 - box[0], c1 - box[0])
             for i, (c0, c1) in enumerate(cols)]
    return Scene(img, ppm, box, truth)


def _font(font_path: Optional[str], size: int):
    from PIL import ImageFont
    cands = [font_path] if font_path else []
    cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]
    for c in cands:
        if c and os.path.exists(c):
            return ImageFont.truetype(c, size)
    raise RuntimeError("no TrueType font found; pass font_path=")


def _render_char(ch: str, size: int, font_path: Optional[str]) -> np.ndarray:
    """Tight binary bitmap of one character."""
    from PIL import Image, ImageDraw
    f = _font(font_path, size)
    pad = size
    im = Image.new("L", (size * 3 + 2 * pad, size * 3 + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad, pad), ch, fill=255, font=f)
    a = np.asarray(im) > 127
    ys, xs = np.nonzero(a)
    if ys.size == 0:
        raise RuntimeError(f"character {ch!r} rendered empty")
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def make_glyphs(ppm: float = 120.0, text: str = "ABMOVW148",
                ref_char: str = "M", target_ref_mm: float = 1.0,
                ss: int = 8, contrast: tuple[float, float] = (0.10, 0.85),
                pitch_mm: float = 0.35, margin_mm: float = 0.6,
                font_path: Optional[str] = None) -> Scene:
    """Real letterforms, rendered at ss x ppm and area-downsampled.

    Two corrections to v6:
      - the nominal cap height is pinned to a FLAT-TOPPED reference letter ('M'),
        not to max() over all glyphs, which picks a round glyph and silently
        bakes optical overshoot into the scale;
      - truth per glyph is its extent in the ss-supersampled grid, so truth
        quantisation is +/- 1/(2*ss*ppm) = 0.0005 mm at ss=8, ppm=120 -- four
        times finer than the biases being reported, rather than 2.7x coarser as
        INTER_NEAREST at ppm made it.
    """
    import cv2
    hppm = ss * ppm
    probe = 900
    ref = _render_char(ref_char, probe, font_path)
    size = max(16, int(round(probe * (target_ref_mm * hppm) / ref.shape[0])))
    bmps = {ch: _render_char(ch, size, font_path) for ch in dict.fromkeys(text)}

    gw = [bmps[c].shape[1] for c in text]
    gh = [bmps[c].shape[0] for c in text]
    pitch_px = int(round(pitch_mm * hppm))
    mar = int(round(margin_mm * hppm))
    W = mar * 2 + sum(gw) + pitch_px * (len(text) - 1)
    H = mar * 2 + max(gh)
    canvas = np.zeros((H, W), bool)

    truth_hi: list[tuple[str, int, int, int, int]] = []     # ch, y0, y1, x0, x1
    x = mar
    baseline = H - mar
    for ch in text:
        b = bmps[ch]
        h, w = b.shape
        y0 = baseline - h
        canvas[y0:y0 + h, x:x + w] |= b
        truth_hi.append((ch, y0, y0 + h - 1, x, x + w - 1))
        x += w + pitch_px

    ink, sub = contrast
    hi = np.where(canvas, float(ink), float(sub))
    out_w = int(round(W / ss))
    out_h = int(round(H / ss))
    img = cv2.resize(hi, (out_w, out_h), interpolation=cv2.INTER_AREA).astype(float)

    box = (0, 0, out_w - 1, out_h - 1)
    truth = [(ch, (y1 - y0 + 1) / hppm, int(round(x0 / ss)), int(round(x1 / ss)))
             for ch, y0, y1, x0, x1 in truth_hi]
    return Scene(img, ppm, box, truth)


def glare(img: np.ndarray, ppm: float, cx_mm: float, cy_mm: float,
          strength: float, sigma_mm: float) -> np.ndarray:
    """Additive-toward-white highlight, applied BEFORE the optical blur."""
    H, W = img.shape
    yy, xx = np.mgrid[0:H, 0:W]
    r2 = (xx - cx_mm * ppm) ** 2 + (yy - cy_mm * ppm) ** 2
    w = strength * np.exp(-0.5 * r2 / ((sigma_mm * ppm) ** 2))
    return img * (1.0 - w) + w


def match_by_overlap(spans: Sequence[tuple[int, int]],
                     truth: Sequence[tuple[str, float, int, int]]
                     ) -> list[Optional[int]]:
    """R8.  Returns, for each truth entry, the index of the best-overlapping
    detected span, or None.  An unmatched truth is a DELETION and must be
    visible as such."""
    out: list[Optional[int]] = []
    for _, _, t0, t1 in truth:
        best, bi = 0, None
        for i, (c0, c1) in enumerate(spans):
            ov = min(c1, t1) - max(c0, t0) + 1
            if ov > best:
                best, bi = ov, i
        out.append(bi)
    return out


# =============================================================================
# PART 7 -- AUDIT EXPERIMENTS
# =============================================================================

def _stats(vals: Sequence[float]) -> dict:
    """R7.  n_unique is reported next to n so that five identical renders can
    never be presented as five samples."""
    a = np.asarray([v for v in vals if v is not None and np.isfinite(v)], float)
    if a.size == 0:
        return dict(n=0, n_unique=0, mean=float("nan"), sd=float("nan"),
                    spread=float("nan"))
    u = np.unique(np.round(a, 12))
    return dict(n=int(a.size), n_unique=int(u.size), mean=float(a.mean()),
                sd=float(a.std(ddof=1)) if a.size > 1 else 0.0,
                spread=float(a.max() - a.min()))


def harness_self_checks(verbose: bool = True) -> list[str]:
    """Assertions that can FAIL.  If any of these trips, no result below is
    citeable, because the instrument under test is the harness."""
    fails: list[str] = []

    # 1. Hard step, midpoint level: the estimator must return the rendered pixel
    #    count EXACTLY, for every exposure.  This is provable by hand (see
    #    crossings()).  It is also why exposure_test needs blur and noise.
    for c in ((0.06, 0.94), (0.10, 0.85), (0.25, 0.60)):
        s = make_bars(80.0, contrast=c)
        g = measure_glyphs(s.roi(), s.ppm, rule="max_supported",
                           local_levels=True)
        truth = s.truth[0][1]
        err = max(abs(h - truth) for h in g.valid)
        if err > 1e-6:
            fails.append(f"hard-step exactness violated at contrast {c}: {err:.3e} mm")

    # 2. Truth-from-render: the declared truth must equal the inked row count.
    s = make_bars(80.0, h_mm=1.0, spread_mm=0.02)
    rows = int(round(s.truth[0][1] * s.ppm))
    if abs(s.truth[0][1] * s.ppm - rows) > 1e-9:
        fails.append("make_bars truth is not an integer row count")

    # 3. Four points give a zero residual by construction; five do not.
    rng = np.random.default_rng(0)
    src = np.array([[0., 0.], [10., 0.], [10., 6.], [0., 6.], [5., 3.]])
    Htrue = np.array([[80., 3., 20.], [-2., 78., 15.], [0.001, 0.002, 1.]])
    dst = apply_h(Htrue, src) + rng.normal(0, 0.4, (5, 2))
    r4 = reproject_rms(homography_dlt(src[:4], dst[:4]), src[:4], dst[:4])
    r5 = reproject_rms(homography_dlt(src, dst), src, dst)
    if r4 > 1e-6:
        fails.append(f"4-point residual should be ~0 by construction, got {r4:.2e}")
    if r5 <= 1e-6:
        fails.append(f"5-point residual should be non-zero under noise, got {r5:.2e}")

    # 4. max_supported vs plain max/min: convention_bakeoff's rendered glyphs
    #    never contain an isolated one-column defect (a hot pixel, a dust
    #    speck), so on every scene there it has printed identical to the
    #    unguarded extreme, to the last digit -- confirmed by running it.
    #    That is a gap in the bakeoff's SCENES, not in the mechanism: this
    #    tests the mechanism directly, at the level _supported_extreme
    #    actually operates, without needing a renderer change. A cluster of
    #    columns near one row plus a single isolated one-column excursion 8px
    #    away: plain min() is fooled by the excursion, take_min=True with a
    #    3-column support requirement is not.
    cluster = np.array([10.0, 10.1, 9.9, 10.0, 10.2, 9.8, 10.0, 10.1])
    defect = np.insert(cluster, 4, 2.0)   # isolated, 1 column, ~8px off
    naive_min = float(np.min(defect))
    guarded_min = _supported_extreme(defect, support_cols=3, tol_px=0.5, take_min=True)
    if naive_min >= 9.0:
        fails.append(f"test defect not isolated from cluster: naive min={naive_min}")
    if guarded_min is None or guarded_min < 9.0:
        fails.append(f"_supported_extreme did not reject the isolated defect: "
                     f"got {guarded_min}, cluster is ~9.8-10.2")

    if verbose:
        print("HARNESS SELF-CHECKS")
        print(f"  4-pt reprojection RMS = {r4:.3e} px  (zero BY CONSTRUCTION -- "
              f"never cite this as planarity evidence)")
        print(f"  5-pt reprojection RMS = {r5:.3f} px  (this one can fail)")
        print(f"  supported-extreme defect rejection: naive min={naive_min:.2f}, "
              f"guarded min={guarded_min}  (guarded must ignore the 2.0 defect)")
        print("  status:", "PASS" if not fails else "FAIL")
        for f in fails:
            print("   !", f)
    return fails


def exposure_test(seeds: int = 5) -> None:
    """Is the reading exposure-dependent, and by what mechanism?

    R3.  On an UNBLURRED bar with the level at the exact midpoint, the extent is
    the rendered pixel count for any (ink, sub) -- exposure invariance is true by
    algebra, and v6's exposure test used exactly that scene.  So this test:
      - uses a resolved edge (blur), and
      - sweeps NOISE as well as contrast, because the predicted mechanism is the
        asymmetric noise tail of the two intensity classes.

    PREDICTION, which can fail: for the percentile estimator the bias is
    approximately proportional to noise/contrast, so bias * C / noise should be
    roughly constant across the grid, and the bias should vanish at noise = 0.
    The iterative class-mean estimator should show a materially smaller effect
    because class means have no tail asymmetry.
    """
    print("\nEXPOSURE  (resolved edge, sigma=1.8 px; truth from render)")
    print("  bias vs rendered truth, mm.  'invariant' = bias*C/noise, "
          "constant if the tail-asymmetry model holds")
    for name, lv in (("percentile", levels_percentile), ("iterative", levels_iterative)):
        print(f"  {name}")
        for noise in (0.0, 0.005, 0.010, 0.020):
            row = []
            for ink, sub in ((0.06, 0.94), (0.10, 0.85), (0.15, 0.70), (0.25, 0.60)):
                C = sub - ink
                vals = []
                for s in range(seeds):
                    sc = make_bars(80.0, contrast=(ink, sub))
                    img = blur_noise(sc.img, 1.8, noise, s)
                    roi = img[sc.roi_box[1]:sc.roi_box[3] + 1,
                              sc.roi_box[0]:sc.roi_box[2] + 1]
                    # inject the estimator under test
                    ink_e, sub_e = lv(roi)
                    lev = 0.5 * (ink_e + sub_e)
                    cm = np.any(roi < lev, axis=0)
                    sp, _ = detect_spans(cm, 80.0)
                    for c0, c1 in sp:
                        cx = column_extents(roi, (c0, c1), lev)
                        h = combine_extents(cx, 80.0, rule="max_supported")
                        if h is not None:
                            vals.append(h - sc.truth[0][1])
                st = _stats(vals)
                inv = (st["mean"] * C / noise) if noise > 0 else float("nan")
                row.append((round(C, 2), st["mean"], st["sd"], st["n_unique"], inv))
            print(f"    noise={noise:5.3f}  " + "  ".join(
                f"C={c:.2f}:{m:+.5f}(sd{sd:.5f},u{u})inv={i:+.4f}"
                for c, m, sd, u, i in row))
    print("  read: the noise=0 row must be ~0 (analytic).  If 'inv' is roughly")
    print("        constant within an estimator, the tail-asymmetry model stands;")
    print("        if not, the model is wrong and the 1/C story goes in the bin.")


def convention_bakeoff(seeds: int = 5) -> None:
    """Which convention, on real letterforms.

    Three axes, and they disagree, which is why all three are printed:
      letterform spread -- measured in the clean condition, where noise=0, so it
                           is PURE morphology (and n_unique exposes that the
                           five seeds are one sample);
      repeatability sd  -- measured in the realistic condition;
      noise -> bias     -- realistic mean minus clean mean.
    A deletion appears as `matched < len(truth)`, never as a re-alignment.
    """
    print("\nCONVENTION BAKE-OFF  (A B M O V W 1 4 8, cap ref 'M', truth from 8x render)")
    rules = [("q5-intensity", dict(profile_q=5.0)),
             ("q25-intensity", dict(profile_q=25.0)),
             ("q50-intensity", dict(profile_q=50.0)),
             ("p95-position", dict(rule="p95")),
             ("max-position", dict(rule="max")),
             ("max_supported", dict(rule="max_supported")),
             ("max_binned", dict(rule="max_binned")),
             ("median-position", dict(rule="median"))]
    for cond, blur, noise in (("clean", 1.8, 0.0), ("realistic", 1.8, 0.010)):
        print(f"  {cond}")
        n_truth = len(make_glyphs(120.0).truth)
        for label, kw in rules:
            biases, matched, counts = [], [], []
            for s in range(seeds):
                sc = make_glyphs(120.0)
                img = blur_noise(sc.img, blur, noise, s)
                g = measure_glyphs(img, sc.ppm, local_levels=True, **kw)
                counts.append(len(g.spans))
                idx = match_by_overlap(g.spans, sc.truth)
                m = 0
                for (ch, th, _, _), j in zip(sc.truth, idx):
                    if j is None or g.heights[j] is None:
                        continue
                    biases.append(g.heights[j] - th)
                    m += 1
                matched.append(m)
            st = _stats(biases)
            print(f"    {label:16s} mean={st['mean']:+.6f} sd={st['sd']:.6f} "
                  f"spread={st['spread']:.6f} n={st['n']} nuniq={st['n_unique']} "
                  f"spans={counts} matched={matched}/{n_truth}")
    print("  read: 'spread' in the clean row is letterform dependence, not noise.")
    print("        A convention whose bias depends on WHICH LETTER you point it")
    print("        at cannot be corrected with one number.")


def sampling_test(seeds: int = 5) -> None:
    """Does sampling density matter, and where does the sweep stop meaning anything?

    Reframed rather than 'fixed'.  A real sensor's PSF is the optical PSF in
    quadrature with the pixel aperture, and the pixel aperture NECESSARILY scales
    with px/mm.  So the honest claim is 'fixed optical PSF plus the pixel
    aperture a real camera would have', which is what INTER_AREA supplies.
    Every row also reports whether a detection threshold is FLOOR-limited: below
    ~40 px/mm a 0.05 mm min-width rounds into a 2-pixel floor, so those rows
    measure integer arithmetic, not sampling.  Three attempts at this experiment
    have now failed for three different reasons (a fixed output grid; domination
    by the convention bias; pixel-unit parameters).  Sampling is a slanted-edge
    measurement on the rig.
    """
    import cv2
    print("\nSAMPLING  (fixed optical PSF 0.045 mm + pixel aperture; noise 0.010)")
    hi = 800.0
    master = make_bars(hi, h_mm=1.0, stroke_mm=0.14, spread_mm=0.0, n=5)
    for ppm in (8, 12, 16, 20, 30, 40, 60, 80):
        _, floored = mm_to_px(0.05, ppm, 2)
        _, f2 = mm_to_px(0.075, ppm, 2)
        vals = []
        for s in range(seeds):
            small = cv2.resize(master.img,
                               (int(round(master.img.shape[1] * ppm / hi)),
                                int(round(master.img.shape[0] * ppm / hi))),
                               interpolation=cv2.INTER_AREA).astype(float)
            img = blur_noise(small, 0.045 * ppm, 0.010, s)
            y0 = int(round(master.roi_box[1] * ppm / hi))
            y1 = int(round(master.roi_box[3] * ppm / hi))
            x0 = int(round(master.roi_box[0] * ppm / hi))
            x1 = int(round(master.roi_box[2] * ppm / hi))
            g = measure_glyphs(img[y0:y1 + 1, x0:x1 + 1], float(ppm),
                               rule="max_supported", local_levels=True)
            vals += [h - master.truth[0][1] for h in g.valid]
        st = _stats(vals)
        flag = "  FLOOR-LIMITED (tests the detector, not sampling)" if (floored or f2) else ""
        print(f"  {ppm:3d} px/mm  bias={st['mean']:+.5f}  sd={st['sd']:.5f}  "
              f"n={st['n']} nuniq={st['n_unique']}{flag}")


def glare_test() -> None:
    """Can the refusal layer see a highlight before the reading is corrupted?

    v6 centred the blob at x=4.20 mm while bar 3 occupied 4.16-4.76 mm -- on the
    bar's EDGE, so part of every bar always survived and no deletion could occur.
    GLYPH_COUNT was reported as unvalidated when in fact it was never provoked.
    Here the blob is centred ON a bar and sigma is swept so that at least one
    condition erases the character entirely.
    """
    print("\nGLARE  (blob centred on bar 3; sigma swept so deletion is reachable)")
    lim = CaptureLimits.for_characterisation(min_px_per_mm=0.0)
    lim = replace(lim, max_illum_gradient=0.10,
                  max_clipped_fraction_in_spans=0.002, expected_glyphs=5)
    ppm = 80.0
    base = make_bars(ppm, h_mm=1.0, stroke_mm=0.6, n=5)
    pitch = max(1.8 * 0.6, 0.36)
    cx = 2.0 + 2 * pitch + (0.6 + 2 * 0.02) / 2.0
    cy = 6.0 / 2.0 + 1.0 / 2.0 - 1.0 / 2.0
    print(f"  bar-3 centre = ({cx:.2f}, {cy:.2f}) mm")
    for sig in (0.25, 0.45, 0.70):
        print(f"  sigma={sig:.2f} mm")
        for s in (0.3, 0.5, 0.7, 0.9, 1.0):
            img = blur_noise(glare(base.img, ppm, cx, cy, s, sig), 1.8, 0.005, 0)
            roi = img[base.roi_box[1]:base.roi_box[3] + 1,
                      base.roi_box[0]:base.roi_box[2] + 1]
            g = measure_glyphs(roi, ppm, rule="max_supported", local_levels=True)
            ref = base.truth[0][1]
            errs = [h - ref for h in g.valid]
            worst = max(errs, key=abs) if errs else float("nan")
            codes = [r.code for r in capture_checks(g, ppm, lim)]
            print(f"    s={s:.1f} spans={len(g.spans)} worst_err={worst:+.4f} "
                  f"grad={illumination_gradient(roi):.4f} "
                  f"clip={100 * clipped_fraction_in_spans(roi, g.spans):.3f}% "
                  f"refusals={codes or ['-']}")
    print("  read: a detector is useful only if it fires BEFORE worst_err matters.")
    print("        Note also that no consistency check can see a deletion -- only")
    print("        the count can, and it must test != because a split raises it.")


def gradient_limit_from_budget(target_err_mm: float = 0.008,
                               sigma_mm: float = 0.45) -> None:
    """Derive max_illum_gradient instead of asserting 0.10.

    A refusal threshold with a derivation behind it is worth more in the room
    than another convention experiment.  Sweep the highlight, record
    (gradient, worst induced height error), and report the gradient at which the
    error crosses a stated fraction of the budget.
    """
    print(f"\nILLUMINATION-GRADIENT LIMIT  (target induced error {target_err_mm:.4f} mm, "
          f"sigma={sigma_mm} mm)")
    ppm = 80.0
    base = make_bars(ppm, h_mm=1.0, stroke_mm=0.6, n=5)
    pitch = max(1.8 * 0.6, 0.36)
    cx = 2.0 + 2 * pitch + (0.6 + 2 * 0.02) / 2.0
    cy = 3.0
    prev = None
    hit = None
    for s in np.arange(0.05, 2.01, 0.05):
        img = blur_noise(glare(base.img, ppm, cx, cy, float(s), sigma_mm), 1.8, 0.005, 0)
        roi = img[base.roi_box[1]:base.roi_box[3] + 1,
                  base.roi_box[0]:base.roi_box[2] + 1]
        g = measure_glyphs(roi, ppm, rule="max_supported", local_levels=True)
        grad = illumination_gradient(roi)
        errs = [abs(h - base.truth[0][1]) for h in g.valid]
        n_obs, n_exp = len(g.spans), 5
        if n_obs != n_exp:
            kind = "SPLIT" if n_obs > n_exp else "DELETION"
            print(f"  s={s:.2f} grad={grad:.4f}  {kind} (spans={n_obs}, expected={n_exp}) "
                  f"-- height error is no longer the right quantity")
            break
        e = max(errs) if errs else float("nan")
        if hit is None and e >= target_err_mm:
            hit = (grad, e, prev)
        prev = (grad, e)
    if hit:
        print(f"  crossing at gradient {hit[0]:.4f} (error {hit[1]:.4f} mm); "
              f"previous point {hit[2]}")
        print(f"  NOTE: this crossing is at ONE highlight width (sigma={sigma_mm} mm).")
        print(f"        glare_test() sweeps three widths and shows gradient is NOT")
        print(f"        single-valued in induced error across them -- e.g. at")
        print(f"        sigma=0.25mm the 0.008mm target is already exceeded at")
        print(f"        gradient 0.0142, well below this crossing, while at")
        print(f"        sigma=0.70mm a gradient of 0.0400 (above this crossing)")
        print(f"        induces only 0.0053mm.  A single crossing on one width")
        print(f"        cannot be turned into a threshold that holds across widths.")
        print(f"        DO NOT set max_illum_gradient from this number.  Replacing")
        print(f"        the whole-ROI gradient with a per-span substrate-variation")
        print(f"        metric, derived across widths, is the open fix.")
    else:
        print("  the target error was never reached within the swept range: the")
        print("  gradient limit is not the binding constraint on this scene, and")
        print("  0.10 is conservative by a wide margin.  Say that, don't assert it.")


def conformity_demo() -> None:
    """The legal layer end to end, on one synthetic capture."""
    print("\nCONFORMITY  (JCGM 106; the limit is exact)")
    print(NOTE_ON_GUARD_BAND)
    sc = make_glyphs(120.0, target_ref_mm=1.4)
    img = blur_noise(sc.img, 1.8, 0.010, 0)
    lim = CaptureLimits(expected_glyphs=len(sc.truth), min_feature_count=5)
    for cat in (CATEGORY_GENERAL, CATEGORY_FORMED, None):
        bud = provisional_budget()
        v = measure_with_category(img, sc.ppm, RULES_2011, cat,
                                  limits=lim, budget=bud,
                                  convention="max_supported", convention_bias_mm=0.0)
        print(f"  category = {cat!r}")
        print("   ", v.report().replace("\n", "\n    "))
    print(provisional_budget().report(H_REF_MM))
    print("  NOTE: every budget term above is 'modelled'.  This U is not citeable")
    print("        until the stage-micrometer run replaces the placeholders, and")
    print("        no convention can be CHOSEN on synthetic evidence, because the")
    print("        difference between candidates is smaller than the disagreement")
    print("        between harness builds.")


def main(argv: Sequence[str] = ()) -> int:
    print("=" * 78)
    print(f"lm_metrology  VERSION {VERSION}")
    print(f"sha256(file)  {_self_hash()}")
    print(f"numpy {np.__version__}  python {sys.version.split()[0]}")
    print("=" * 78)
    fails = harness_self_checks()
    if fails:
        print("\nABORTING: harness self-checks failed. No result below would be citeable.")
        return 1
    exposure_test()
    convention_bakeoff()
    sampling_test()
    glare_test()
    gradient_limit_from_budget()
    conformity_demo()
    print("\n" + "=" * 78)
    print("Reminder: this run cannot close any budget term.  The stage micrometer")
    print("and the camera decision are the critical path.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
