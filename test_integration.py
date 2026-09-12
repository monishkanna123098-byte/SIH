#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_integration.py -- the re-runnable form of two claims this project has been
making in prose.

WHY THIS FILE EXISTS. Two separate assertions were sitting in documents with no
executable backing:

  1. lm_metrology_v7.py's own 7.9 changelog says the legal-model integration was
     "verified against three cases: a resolved measurement, a disputed-bracket
     refusal, and the legacy path". harness_self_checks() does not exercise
     measure_with_category() with a commodity_class at ALL -- it tests hard-step
     exactness, homography reprojection and the supported-extreme guard, and
     nothing else. So that verification, if it happened, happened in a scratch
     buffer that was not kept. A claim whose test was not kept is a claim that
     cannot be re-checked after the next edit.

  2. The team brief section 13a scores ten v7.1 regression assertions and finds
     five of them "not exercised", "not verified" or "cannot be checked from
     this output" -- and then names the exact repair: five additions, none of
     which touches a measurement path. Those five are items 1, 3, 6, 9 and 10.

This file is that repair, plus the missing integration test. It is DIAGNOSTIC
ONLY. It calls the library; it does not modify it; every number it prints is
read off the same code paths main() already runs. If a number here disagrees
with a number from `python3 lm_metrology_v7.py`, the library changed underneath
one of them and you should stop rather than pick a favourite.

RUN:  python3 test_integration.py
EXIT: 0 if every check passed, 1 otherwise. Nonzero is meant to be noticed.
"""
from __future__ import annotations

import datetime
import sys

import numpy as np

import lm_legal_model as legal
import lm_metrology_v7 as lm

FAILS: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    """One assertion, named, counted, and non-fatal.

    Non-fatal on purpose: a test file that stops at the first failure tells you
    about one problem per run, and this file exists precisely because nobody
    wanted to run things repeatedly.
    """
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        FAILS.append(label)
        print(f"  FAIL  {label}" + (f"\n          {detail}" if detail else ""))


def scene():
    """The same synthetic capture conformity_demo() uses, built the same way.

    Deliberately identical to the demo's scene rather than a new one: the point
    of several checks below is that a number matches what the demo prints, and
    that comparison is only meaningful if the pixels are the same pixels.
    """
    sc = lm.make_glyphs(120.0, target_ref_mm=1.4)
    img = lm.blur_noise(sc.img, 1.8, 0.010, 0)
    lim = lm.CaptureLimits(expected_glyphs=len(sc.truth), min_feature_count=5)
    return sc, img, lim


# =============================================================================
# PART 1 -- the integration claim from the 7.9 changelog, made re-runnable
# =============================================================================

def test_integration_three_cases() -> None:
    print("\n[1] THE 7.9 CHANGELOG'S THREE CASES")
    print("    (claimed verified in a comment; never had a test until now)")
    sc, img, lim = scene()
    today = datetime.date(2026, 9, 12)

    # --- Case A: a resolved measurement through the integrated path ----------
    # 40 cm2 general/general is the bracket the internal round actually
    # touches, and the only one where TL = 1.0 mm.
    v = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, lm.CATEGORY_GENERAL,
        limits=lim, budget=lm.provisional_budget(),
        convention="max_supported", convention_bias_mm=0.0,
        commodity_class=legal.COMMODITY_GENERAL,
        pdp_area_cm2=40.0, as_of=today)
    check("A: integrated path resolves and returns a band",
          v.band in (lm.BAND_COMPLIANT, lm.BAND_DEFICIENT, lm.BAND_REFER),
          f"band={v.band!r}")
    check("A: TL came from the legal model, not v7's flat table",
          v.threshold_mm == 1.0, f"TL={v.threshold_mm!r}, expected 1.0")
    check("A: legal_resolution is stashed in diagnostics",
          v.diagnostics.get("legal_resolution") is not None)
    lines = lm.legal_report_lines(v)
    check("A: legal_report_lines returns a non-empty report",
          len(lines) > 0, f"got {len(lines)} lines")
    print(f"        -> band={v.band}  h={v.h_mm}  U={v.U_mm}  TL={v.threshold_mm}")

    # --- Case B: the disputed bracket refuses, and leaks nothing -------------
    # 75 cm2 general sits in 50 < A <= 100, the cell flagged disputed=True.
    # The refusal must not name either candidate value; the provenance sheet
    # commits to that in as many words and it is the single most quotable
    # failure mode if it were wrong on stage.
    vd = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, lm.CATEGORY_GENERAL,
        limits=lim, budget=lm.provisional_budget(),
        convention="max_supported", convention_bias_mm=0.0,
        commodity_class=legal.COMMODITY_GENERAL,
        pdp_area_cm2=75.0, as_of=today)
    codes = [r.code for r in vd.refusals]
    check("B: disputed bracket refuses", vd.band == lm.BAND_REFER, f"band={vd.band}")
    check("B: refusal code is THRESHOLD_DISPUTED",
          legal.BLOCK_THRESHOLD_DISPUTED in codes, f"codes={codes}")
    check("B: no height reported on a refusal", vd.h_mm is None, f"h={vd.h_mm}")
    blob = " ".join(r.detail for r in vd.refusals) + " ".join(lm.legal_report_lines(vd))
    for leaked in ("1.5", "2.0"):
        check(f"B: candidate value {leaked!r} does NOT leak into operator text",
              leaked not in blob,
              f"found {leaked!r} in refusal/report text -- this is the leak the "
              f"provenance sheet promises cannot happen")

    # --- Case C: the legacy path is untouched and reports nothing ------------
    vl = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, lm.CATEGORY_GENERAL,
        limits=lim, budget=lm.provisional_budget(),
        convention="max_supported", convention_bias_mm=0.0)
    check("C: legacy path (no commodity_class) still produces a verdict",
          vl.h_mm is not None, f"h={vl.h_mm}")
    check("C: legacy path returns () from legal_report_lines, not an error",
          lm.legal_report_lines(vl) == ())
    check("C: legacy and integrated paths agree on h to the last digit",
          vl.h_mm == v.h_mm,
          f"legacy h={vl.h_mm!r} vs integrated h={v.h_mm!r} -- these run the "
          f"same pixels through the same estimator and must not differ")


# =============================================================================
# PART 2 -- the five section-13a items the demo run could not answer
# =============================================================================

def test_13a_item_1_and_10_full_precision() -> None:
    """Items 1 and 10: h at full precision, and governing_glyph_index present.

    The demo prints h to 2 s.f. by design (patch 3), so the run output can be
    CONSISTENT with h = 1.402 without CONFIRMING it. Printing the diagnostic at
    full precision is the whole repair.
    """
    print("\n[2] SECTION 13a ITEM 1 + 10 -- full-precision h and governing glyph")
    sc, img, lim = scene()
    v = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, lm.CATEGORY_GENERAL,
        limits=lim, budget=lm.provisional_budget(),
        convention="max_supported", convention_bias_mm=0.0)
    check("item 10: governing_glyph_index is present in diagnostics",
          "governing_glyph_index" in v.diagnostics)
    check("item 10: the governing glyph IS the minimum extent",
          v.diagnostics.get("governing_glyph_extent_mm")
          == min(v.diagnostics.get("glyph_extents_mm", [float("inf")])),
          "the governing glyph must be the shortest measured mark -- this is "
          "the selection rule the decimal-point limitation is ABOUT, so if it "
          "ever stops being true the known limitation has silently changed")
    print(f"        h (full precision)        = {v.h_mm!r}")
    print(f"        governing_glyph_index     = {v.diagnostics.get('governing_glyph_index')}")
    print(f"        governing_glyph_extent_mm = {v.diagnostics.get('governing_glyph_extent_mm')!r}")
    ext = v.diagnostics.get("glyph_extents_mm", [])
    print(f"        glyph_extents_mm          = {[round(x, 6) for x in ext]}")
    print(f"        dropped_glyph_indices     = {v.diagnostics.get('dropped_glyph_indices')}")


def test_13a_item_3_unknown_category() -> None:
    """Item 3: an unknown category string must give CATEGORY_UNKNOWN, NOT
    MEASURAND_UNDEFINED. Never exercised -- the demo runs general, formed and
    None and nothing else."""
    print("\n[3] SECTION 13a ITEM 3 -- unknown category string")
    sc, img, lim = scene()
    v = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, "banana",
        limits=lim, budget=lm.provisional_budget(),
        commodity_class=legal.COMMODITY_GENERAL,
        pdp_area_cm2=40.0, as_of=datetime.date(2026, 9, 12))
    codes = [r.code for r in v.refusals]
    check("item 3: unknown category -> CATEGORY_UNKNOWN",
          legal.BLOCK_CATEGORY_UNKNOWN in codes, f"codes={codes}")
    check("item 3: and NOT MEASURAND_UNDEFINED",
          "MEASURAND_UNDEFINED" not in codes,
          "a typo'd category reported as an unmeasurable surface would send "
          "the operator to physical verification for a spelling mistake")
    print(f"        codes = {codes}")

    # The same check on the legacy path, which has its own separate branch.
    vlegacy = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, "banana",
        limits=lim, budget=lm.provisional_budget())
    lcodes = [r.code for r in vlegacy.refusals]
    check("item 3: legacy path also refuses an unknown category",
          vlegacy.band == lm.BAND_REFER and bool(lcodes), f"codes={lcodes}")
    print(f"        legacy codes = {lcodes}")


def test_13a_item_6_escape_hatch() -> None:
    """Item 6: allow_undefined_measurand=True. The brief says do this one FIRST,
    and the reasoning is right: it is an escape hatch out of a refusal the
    instrument has just finished issuing, and it has never been called."""
    print("\n[4] SECTION 13a ITEM 6 -- the allow_undefined_measurand escape hatch")
    sc, img, lim = scene()

    blocked = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, lm.CATEGORY_FORMED,
        limits=lim, budget=lm.provisional_budget())
    check("item 6: formed category refuses by default",
          "MEASURAND_UNDEFINED" in [r.code for r in blocked.refusals],
          f"codes={[r.code for r in blocked.refusals]}")

    opened = lm.measure_with_category(
        img, sc.ppm, lm.RULES_2011, lm.CATEGORY_FORMED,
        allow_undefined_measurand=True,
        limits=lim, budget=lm.provisional_budget())
    check("item 6: the escape hatch produces a number instead of a refusal",
          opened.h_mm is not None,
          f"band={opened.band} h={opened.h_mm} -- if this refuses anyway the "
          f"hatch does not do what its name says")
    check("item 6: and the hatch does NOT change the measured height",
          opened.h_mm is None or abs(opened.h_mm - blocked_height(img, sc, lim)) < 1e-12,
          "the escape hatch is supposed to bypass a GATE, not alter the "
          "measurement; if h moves, it is doing something nobody documented")
    print(f"        default  -> band={blocked.band}  h={blocked.h_mm}")
    print(f"        hatch    -> band={opened.band}  h={opened.h_mm!r}  TL={opened.threshold_mm}")
    print("        NOTE: this number is produced for a surface the instrument has")
    print("              just declared unmeasurable. It is a characterisation")
    print("              output. It is not a verdict and must never reach a slide.")


def blocked_height(img, sc, lim) -> float:
    """The height the same pixels produce on the general (measurable) path.

    Used only to check that the escape hatch bypasses the gate without touching
    the estimator.
    """
    v = lm.measure_with_category(img, sc.ppm, lm.RULES_2011, lm.CATEGORY_GENERAL,
                                 limits=lim, budget=lm.provisional_budget())
    return v.h_mm


def test_13a_item_9_effective_support() -> None:
    """Item 9: the contradiction. The brief says the sampling sweep marks 8, 12,
    16 and 20 px/mm FLOOR-LIMITED and stops -- while patch 4's worked table says
    30 px/mm IS floor-limited at 0.067 mm. Both cannot be true, and 30 px/mm is
    the row that carries min_px_per_mm, so this has to be settled before the
    sampling table is shown to anyone.

    This resolves it by printing the actual arithmetic instead of arguing about
    it.
    """
    print("\n[5] SECTION 13a ITEM 9 -- is 30 px/mm floor-limited or not?")
    print("      ppm   0.05mm->px  floored   0.075mm->px  floored   effective support")
    verdicts = {}
    for ppm in (8, 12, 16, 20, 30, 40, 60, 80):
        px_w, f1 = lm.mm_to_px(0.05, ppm, 2)
        px_g, f2 = lm.mm_to_px(0.075, ppm, 2)
        eff = px_w / float(ppm)
        verdicts[ppm] = (f1 or f2)
        flag = "FLOOR-LIMITED" if (f1 or f2) else "-"
        print(f"      {ppm:3d}   {px_w:6d}      {str(f1):5s}     {px_g:6d}"
              f"      {str(f2):5s}     {eff:.4f} mm   {flag}")

    check("item 9: 30 px/mm is NOT floor-limited by detect_spans' own thresholds",
          not verdicts[30],
          "if this fails, the sampling sweep's FLOOR-LIMITED markers are wrong")
    print("\n      RESOLUTION OF THE CONTRADICTION:")
    print("      detect_spans() calls mm_to_px(0.05, ppm, floor_px=2) for min width")
    print("      and mm_to_px(0.06, ppm, floor_px=1) for min gap. At 30 px/mm,")
    print("      0.05*30 = 1.5 -> round() = 2, which EQUALS the floor of 2 and so")
    print("      does NOT trip the `v < floor_px` test. It is a rounding")
    print("      coincidence, not a margin: 0.05 mm at 30 px/mm lands exactly on")
    print("      the floor value without being clamped to it.")
    print("      So the sweep's markers are internally correct AND patch 4's")
    print("      0.067 mm figure is reachable -- 2 px / 30 px/mm = 0.0667 mm is")
    print("      the effective support either way. The two statements were never")
    print("      about the same thing: one asks 'was the value CLAMPED', the")
    print("      other asks 'what is the value IN MM'. Both answers stand.")
    print("      The margin here is ZERO, though: any ppm below 30 clamps. Do not")
    print("      describe 30 px/mm as comfortably above the floor.")


def test_13a_item_8_all_measured() -> None:
    """Item 8: all_measured() was inferred from the presence of [modelled]
    markers, never printed. Print the boolean."""
    print("\n[6] SECTION 13a ITEM 8 -- Budget.all_measured(), printed not inferred")
    bud = lm.provisional_budget()
    am = bud.all_measured()
    check("item 8: all_measured() is False (all eight terms modelled)",
          am is False, f"all_measured()={am!r}")
    print(f"        bud.all_measured() = {am!r}")
    print(f"        U(k=2) @1mm        = {bud.expanded(1.0):.5f} mm")
    print("        If this ever prints True, someone marked a term measured.")
    print("        Check WHICH term and against WHAT reference before believing it.")


# =============================================================================
# PART 3 -- the height-scaling claim, checked against the documents
# =============================================================================

def test_budget_scaling_matches_documents() -> None:
    """The one-pager and the notebooklm source both quote specific U values at
    specific heights. Those are quotable numbers in a public document, so they
    get a test."""
    print("\n[7] U(k=2) SCALING -- documents vs code")
    bud = lm.provisional_budget()
    documented = {1.0: 0.16634, 2.0: 0.18486, 6.0: 0.28578}
    for h, want in documented.items():
        got = bud.expanded(h)
        check(f"U(k=2) at {h} mm == {want} as documented",
              abs(got - want) < 5e-6, f"code gives {got:.5f}")
        print(f"        {h:>4.1f} mm -> {got:.5f} mm   (documents say {want})")
    check("U rises monotonically with the requirement",
          bud.expanded(1.0) < bud.expanded(2.0) < bud.expanded(6.0))


def test_u_evaluated_at_max() -> None:
    """The brief commits to evaluating U at max(h, TL), never the smaller. A
    packet measuring BELOW its requirement must not get a narrower band than one
    measuring above it -- that would make a confident DEFICIENT easier to reach,
    which is the one direction an enforcement tool must not err in.
    """
    print("\n[8] U EVALUATED AT max(h, TL) -- the direction-of-error commitment")
    bud = lm.provisional_budget()
    u_at_1 = bud.expanded(1.0)
    u_at_6 = bud.expanded(6.0)
    check("a 6 mm requirement carries a wider U than a 1 mm one",
          u_at_6 > u_at_1, f"{u_at_6} vs {u_at_1}")
    print(f"        U@1mm = {u_at_1:.5f}   U@6mm = {u_at_6:.5f}")
    print("        A short glyph under a 6 mm requirement must be judged with")
    print("        U(6 mm), not U(h). Verified in measure() by inspection at the")
    print("        U_at_mm = max(h, TL) line; not separately re-derivable here")
    print("        without a 6 mm synthetic scene, which this file does not build.")


# =============================================================================

def main() -> int:
    print("=" * 78)
    print("INTEGRATION + REGRESSION TESTS")
    print(f"lm_metrology VERSION {lm.VERSION}")
    print(f"sha256(lm_metrology) {lm._self_hash()}")
    print(f"legal model available: {lm._LEGAL_MODEL_AVAILABLE}")
    print(f"numpy {np.__version__}  python {sys.version.split()[0]}")
    print("=" * 78)

    test_integration_three_cases()
    test_13a_item_1_and_10_full_precision()
    test_13a_item_3_unknown_category()
    test_13a_item_6_escape_hatch()
    test_13a_item_9_effective_support()
    test_13a_item_8_all_measured()
    test_budget_scaling_matches_documents()
    test_u_evaluated_at_max()

    print("\n" + "=" * 78)
    print(f"{CHECKS} checks, {len(FAILS)} failed")
    for f in FAILS:
        print(f"  ! {f}")
    print("=" * 78)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
