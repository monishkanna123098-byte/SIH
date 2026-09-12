#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
naive_vs_calibrated.py — the thirty-second demo beat.

WHAT THIS SHOWS
  One packet. One physical character height. Three photographs taken from three
  camera distances. A pixel-based height estimate returns three different
  confident answers and flips the legal verdict between them. A scale-referenced
  measurement returns the same answer at every distance.

WHAT THIS IS NOT, AND THE SCRIPT SAYS SO IN ITS OWN OUTPUT SO IT CANNOT BE
DROPPED FROM THE NARRATION:
  This is NOT a benchmark of any other team's system. Nobody here has run
  SatyaLabel, Gemini Vision, Tesseract or any other pipeline and measured what
  it outputs. Claiming otherwise on stage would be exactly the kind of
  unverified assertion this project spent three weeks removing from its own
  documents, and it would be destroyed by one question: "did you actually test
  ours?"

  What this demonstrates is a GEOMETRIC FACT that binds any method, ours
  included: a height in pixels becomes a height in millimetres only through a
  pixels-per-millimetre factor, and if nothing of known size is in the frame,
  that factor has to be assumed. When the camera moves, the true factor changes
  and the assumed one does not. The error is the ratio of the two.

  Say it that way. It is stronger than an accusation because it is not
  arguable — and it applies to us too, which is the whole reason we put a
  calibration artifact in the frame.

FAIRNESS NOTE — READ BEFORE USING THIS
  The naive estimator below is given the BEST possible version of its own
  approach: it is calibrated correctly, once, at the reference distance, and
  then used unchanged. That is more generous than most OCR pipelines, which
  assume a fixed DPI and are never calibrated at all (that weaker case is shown
  too, for contrast). Building a strawman here would be cheating and it would
  also be less convincing. The generous version still fails, and that is the
  point worth making.

RUN: python3 naive_vs_calibrated.py
"""
from __future__ import annotations

import sys

import lm_metrology_v7 as lm

# --- THE SCENARIO ----------------------------------------------------------
# A character height chosen deliberately close to the 1 mm statutory floor,
# because that is where enforcement decisions actually get made and where a
# scale error changes the outcome instead of just the number.
TRUE_HEIGHT_MM = 1.15
THRESHOLD_MM = 1.0          # Rule 7(2), A <= 50 cm2, ordinary category

# Three camera distances, expressed as the px/mm each one produces. px/mm is
# inversely proportional to standoff, so 144 / 120 / 100 px/mm is the same
# camera at roughly 0.83x, 1.0x and 1.2x the reference working distance —
# a hand's width of movement on a copy stand.
REFERENCE_PPM = 120.0
SHOTS = (
    ("A  camera moved CLOSER  (~0.83x standoff)", 144.0),
    ("B  reference distance", 120.0),
    ("C  camera moved BACK    (~1.20x standoff)", 100.0),
)

# The weak-case assumption: a pipeline built for scanned images assumes a DPI.
ASSUMED_DPI = 300.0
ASSUMED_PPM_FROM_DPI = ASSUMED_DPI / 25.4      # 11.81 px/mm


def naive_verdict(h_mm: float) -> str:
    """What a system with no uncertainty budget does: compare and commit.

    No band, no refusal, no 'cannot determine'. This is not a caricature — it
    is what comparing a number against a threshold looks like when the number
    carries no stated uncertainty. Any pipeline that prints PASS or FAIL from a
    single height is doing exactly this.
    """
    return "COMPLIANT" if h_mm >= THRESHOLD_MM else "DEFICIENT"


def shoot(ppm: float):
    """Render the packet as photographed at this px/mm, and measure it.

    Same physical packet every time: TRUE_HEIGHT_MM does not change between
    shots. Only the sampling does, which is what moving a camera does.
    """
    sc = lm.make_glyphs(ppm, target_ref_mm=TRUE_HEIGHT_MM)
    img = lm.blur_noise(sc.img, 1.8, 0.010, 0)
    g = lm.measure_glyphs(img, ppm, rule="max_supported", local_levels=True)
    valid = [h for h in g.heights if h is not None]
    h_mm_true_scale = min(valid)            # governing glyph, per the shortest rule
    h_px = h_mm_true_scale * ppm            # what the detector actually saw, in pixels
    return sc, img, h_px, h_mm_true_scale


def main() -> int:
    print("=" * 78)
    print("WHY A PHOTOGRAPH DOES NOT CONTAIN A MILLIMETRE")
    print("=" * 78)
    print(f"One packet. Character height is {TRUE_HEIGHT_MM} mm and never changes.")
    print(f"Statutory threshold: {THRESHOLD_MM} mm  (Rule 7(2), A <= 50 cm2, ordinary)")
    print(f"Three photographs, three camera distances.")
    print()

    rows = []
    for label, ppm in SHOTS:
        sc, img, h_px, h_true_scale = shoot(ppm)

        # --- METHOD 1: fixed-DPI assumption (the common case) --------------
        naive_dpi_mm = h_px / ASSUMED_PPM_FROM_DPI

        # --- METHOD 2: calibrated once at the reference distance, then
        #               reused unchanged. The GENEROUS case.
        naive_cal_mm = h_px / REFERENCE_PPM

        # --- METHOD 3: this instrument. A scale reference is in the frame,
        #               so px/mm is recovered per shot, not assumed.
        bud = lm.provisional_budget()
        v = lm.measure_with_category(
            img, ppm, lm.RULES_2011, lm.CATEGORY_GENERAL,
            limits=lm.CaptureLimits(), budget=bud,
            convention="max_supported", convention_bias_mm=0.0)

        rows.append((label, ppm, h_px, naive_dpi_mm, naive_cal_mm, v))

    # ---- THE TABLE --------------------------------------------------------
    print("-" * 78)
    print("WHAT THE DETECTOR SEES (identical physical packet every time)")
    print("-" * 78)
    print(f"{'shot':<42} {'px/mm':>7} {'glyph height in px':>20}")
    for label, ppm, h_px, _, _, _ in rows:
        print(f"{label:<42} {ppm:>7.1f} {h_px:>20.2f}")
    print()
    print("  The pixel count changes because the camera moved. Nothing about")
    print("  the packet changed. Every method below starts from these pixels.")
    print()

    print("-" * 78)
    print("METHOD 1 — fixed DPI assumption (no calibration at all)")
    print(f"           assumes {ASSUMED_DPI:.0f} dpi = {ASSUMED_PPM_FROM_DPI:.2f} px/mm")
    print("-" * 78)
    for label, ppm, h_px, ndpi, _, _ in rows:
        print(f"  {label:<42} -> {ndpi:7.3f} mm   {naive_verdict(ndpi):<10}")
    print("  Every reading is wrong by an order of magnitude and every verdict")
    print("  is confident. This is the weak case and we lead with the next one.")
    print()

    print("-" * 78)
    print("METHOD 2 — calibrated ONCE at the reference distance, then reused")
    print("           THE GENEROUS CASE. This is the best version of the")
    print("           no-reference approach, and it is the one to show.")
    print("-" * 78)
    base = None
    for label, ppm, h_px, _, ncal, _ in rows:
        if base is None:
            base = ncal
        err = ncal - TRUE_HEIGHT_MM
        pct = 100.0 * err / TRUE_HEIGHT_MM
        print(f"  {label:<42} -> {ncal:7.3f} mm   {naive_verdict(ncal):<10} "
              f"error {err:+.3f} mm ({pct:+.1f}%)")
    verdicts = {naive_verdict(r[4]) for r in rows}
    print()
    if len(verdicts) > 1:
        print("  *** THE VERDICT FLIPPED. Same packet, same day, same operator. ***")
        print("  One of these photographs issues a penalty notice against a packet")
        print("  the other two clear. Nothing about the packet decided that.")
        print("  The camera position did.")
    print()

    print("-" * 78)
    print("METHOD 3 — this instrument: a calibration artifact is IN THE FRAME,")
    print("           so px/mm is recovered from every shot, not assumed")
    print("-" * 78)
    for label, ppm, h_px, _, _, v in rows:
        if v.h_mm is None:
            codes = ", ".join(r.code for r in v.refusals)
            print(f"  {label:<42} -> REFUSED [{codes}]")
            continue
        lo, hi = v.h_mm - v.U_mm, v.h_mm + v.U_mm
        print(f"  {label:<42} -> {v.h_mm:7.3f} mm  +/- {v.U_mm:.3f} (k=2)")
        print(f"  {'':<42}    band [{lo:.3f}, {hi:.3f}] vs TL {THRESHOLD_MM:.2f}")
        print(f"  {'':<42}    {v.band}")
    heights = [r[5].h_mm for r in rows if r[5].h_mm is not None]
    bands = {r[5].band for r in rows}
    if heights:
        spread = max(heights) - min(heights)
        print()
        print(f"  Spread across all three camera distances: {spread:.5f} mm")
        print(f"  Method 2's spread across the same three:  "
              f"{max(r[4] for r in rows) - min(r[4] for r in rows):.5f} mm")
    if len(bands) == 1:
        print(f"  Verdict is the SAME at every distance: {bands.pop()}")
    print()

    # ---- THE POINT --------------------------------------------------------
    print("=" * 78)
    print("WHAT TO SAY")
    print("=" * 78)
    print("""
  "A photograph carries pixels. The requirement is in millimetres. Nothing in
   an image supplies the conversion unless something of known size is in the
   frame with the label. Move the camera and the conversion changes. That is
   not a flaw in anyone's code — it is geometry, and it binds us too. It is
   why there is a calibration artifact in our frame, and why, when we still
   cannot tell, this instrument says so instead of picking a side."

  AND THE SENTENCE THAT MUST NOT BE DROPPED:

  "We have not benchmarked anyone else's system and we are not claiming to.
   What you just watched is a property of measuring without a reference,
   demonstrated on our own renderer."
""")
    print("  Note what Method 3 does at the near-threshold height: it does NOT")
    print("  declare the packet compliant. Its band straddles the limit, so it")
    print("  refers for physical verification -- three times out of three. A")
    print("  system that issues a penalty notice here is not more capable than")
    print("  ours. It is less willing to admit what an image cannot settle.")
    print()
    print("=" * 78)
    print("TWO ATTACKS ON THIS DEMO, AND THE ANSWERS. REHEARSE BOTH.")
    print("=" * 78)
    print("""
  ATTACK 1 -- "You handed Method 3 the exact true px/mm. A real calibration
               artifact has its own error, so you rigged it."

  CORRECT, AND ANSWERED IN THE BUDGET. This simulation gives Method 3 the true
  scale for each shot, which is what recovering px/mm from an artifact in frame
  approximates -- not what it achieves. The allowance for the difference is the
  `scale_calibration` term, 0.010 mm, and it is already inside the +/- shown
  above. It is also a PLACEHOLDER pending the stage micrometer, which we say
  before anyone asks. The honest claim is not "our scale is perfect". It is
  "our scale error is bounded and budgeted; an assumed scale's error is
  unbounded and invisible."

  ATTACK 2 -- "So your instrument is 350x more repeatable. Is that its accuracy?"

  NO, AND DO NOT LET THIS NUMBER DRIFT INTO AN ACCURACY CLAIM. The spread above
  is repeatability across three sampling densities on synthetic renders at a
  FIXED noise seed. It is not measured on a rig, not against a reference
  standard, and not a property of any physical instrument. Section 15 of the
  brief forbids the word "accuracy" for this system until a reference standard
  has been measured on the rig, and that has not happened. What this comparison
  shows is that one method's answer MOVES WITH THE CAMERA and the other's does
  not. That is a statement about scale references, not about accuracy, and it
  is the only statement this demo supports.
""")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
