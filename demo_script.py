#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIH26034 demo script — sequences the capture and measurement layers for a live run.

=============================================================================
READ THIS BEFORE RUNNING. The previous version of this file claimed it "wires
the ALREADY-EXISTING pipeline together" and that "nothing new was built to make
this work". That was not true, and the file had never executed even once. Four
faults were found on 2026-09-12 by static and runtime audit:

  1. It imported `lm_metrology_v7`, while the file on disk was named
     `lm_metrology_v7.9.py`. Import failed at line 18 — the script had never run
     past its own imports. FIXED by restoring the module filename (every other
     document in the project already calls it `lm_metrology_v7.py`, and a dotted
     filename is not importable by Python anyway).

  2. It read `r.detail` off a `CaptureRefusal`. That class carries `.cause`;
     it is `lm_metrology_v7.Refusal` that carries `.detail`. This would have
     raised AttributeError in BEAT 1, the first beat of the demo. FIXED.

  3. It passed no `limits=`, so `expected_glyphs` stayed None and GLYPH_COUNT —
     the gate the counting-rule sign is about, and the predicted top offender in
     job 4 — was silently disabled for the whole demo. FIXED: the count is now a
     required operator declaration, see OPERATOR DECLARATIONS below.

  4. It passed the ENTIRE camera frame as the ROI. Every synthetic test in this
     project crops to `Scene.roi_box` first; `roi_box` exists only on the
     synthetic scene class, and `lm_capture.py` contains no ROI mechanism at
     all. So the measurement engine would have been asked to find glyphs across
     a whole 1920x1080 frame — platen, packet edges, shadows and all. ADDRESSED
     below, but read the warning on `select_roi`: that function is NEW CODE
     written on 2026-09-12 and is the one part of this file with no self-test
     behind it.

STILL BROKEN BY DESIGN, AND NOT PAPERED OVER: this script passes no homography
and no fiducial coordinates, so `PLANARITY` and `NO_REDUNDANCY` CANNOT FIRE —
both live inside `if src_mm is not None` in `capture_checks`. Job 2's "done
when" criterion in the team brief says those two must be able to fire. They
cannot, on this path. That is rectification work, not a line of wiring, and
inventing it four days out would be worse than saying so. Say so.
=============================================================================

Run: python3 demo_script.py
Stop early with Ctrl+C at any point — nothing here holds a lock past its own call.
"""
from __future__ import annotations

import datetime
import sys

import lm_capture as capture
import lm_metrology_v7 as lm

# --- RIG CONSTANTS ---------------------------------------------------------
CAMERA_INDEX = 0          # try 1, 2... if 0 is the wrong device
INNER_COLS, INNER_ROWS = 9, 6
SQUARE_MM = 5.0

# --- OPERATOR DECLARATIONS -------------------------------------------------
# Fill these in per demo_packets.md BEFORE running, not during. Every one of
# them is a claim the operator is making about the physical packet; none is
# discoverable from the image.
DECLARED_CATEGORY = lm.CATEGORY_GENERAL          # or lm.CATEGORY_FORMED
DECLARED_COMMODITY_CLASS = "general"
DECLARED_PDP_AREA_CM2 = 40.0                     # measure the real packet's panel

# EXPECTED_GLYPHS drives GLYPH_COUNT. The counting rule is already decided and
# posted (SIH26034-counting-rule-sign.md): EVERY INK MARK inside the ROI counts
# — letters, numerals, the currency symbol, the decimal point. Whitespace does
# not. So "Rs.99.00" is 8 and "99.00" is 5. Count it before you run, not after
# you see what the detector found; a count typed to match the output is not a
# check, it is a rubber stamp.
#
# Setting this to None disables GLYPH_COUNT entirely. That is what the previous
# version of this file did by omission. If you ever set it to None deliberately,
# say out loud that the strictest gate in the instrument is off.
EXPECTED_GLYPHS = 5

TODAY = datetime.date.today()


def pause(msg):
    input(f"\n>>> {msg} — press Enter to continue... ")


def select_roi(gray):
    """Ask the operator to draw the measured region on the captured frame.

    ** NEW CODE, 2026-09-12. NO SELF-TEST STANDS BEHIND THIS FUNCTION. **
    Everything else this script calls is covered by lm_capture's 114 checks or
    lm_metrology's harness. This is not. Test it against your camera before the
    round, and if it misbehaves use the MANUAL fallback below rather than
    measuring a whole frame.

    Why it has to exist: the measurement engine treats whatever array it is
    given as the region to measure. Hand it a full frame and it hunts for ink
    across the platen and the packet edges, which is neither what the counting
    rule describes nor what the operator declared a glyph count for.

    Returns the cropped array. Raises SystemExit if the operator selects
    nothing, because continuing with a full frame is the failure this exists to
    prevent.
    """
    import cv2
    try:
        box = cv2.selectROI("Draw the declaration region, then press ENTER",
                            gray, showCrosshair=True, fromCenter=False)
        cv2.destroyAllWindows()
    except cv2.error as exc:
        print(f"  selectROI unavailable on this OpenCV build ({exc}).")
        box = None

    if not box or box[2] == 0 or box[3] == 0:
        # MANUAL FALLBACK. A headless build, or an operator who selected
        # nothing. Typed coordinates are worse ergonomics and identical
        # metrology — the crop is the crop.
        print("  Falling back to typed coordinates.")
        print(f"  Frame is {gray.shape[1]} x {gray.shape[0]} px "
              f"(width x height).")
        try:
            x = int(input("    x0: ")); y = int(input("    y0: "))
            w = int(input("    width: ")); h = int(input("    height: "))
        except (ValueError, EOFError):
            raise SystemExit("No ROI given. Refusing to measure a whole frame.")
        box = (x, y, w, h)

    x, y, w, h = (int(v) for v in box)
    if w <= 0 or h <= 0:
        raise SystemExit("Empty ROI. Refusing to measure a whole frame.")
    roi = gray[y:y + h, x:x + w]
    print(f"  ROI: x={x} y={y} w={w} h={h}  ->  {roi.shape[1]}x{roi.shape[0]} px")
    return roi


def main():
    session = capture.RigSession()
    print("Opening camera...")
    cap, camera_notes = capture.open_camera(CAMERA_INDEX)
    print("Camera opened. Lock notes:", camera_notes or "(all requested locks accepted)")

    # ---- BEAT 1: no artifact in frame -> refuses ---------------------------
    pause("Make sure NOTHING is in frame, then continue")
    try:
        capture.capture_specimen(session, cap, camera_notes)
        print("!! Expected a refusal here and did not get one. Stop and check the rig.")
    except capture.CaptureRefusal as r:
        print(f"REFUSED as expected: {r.code}")
        print(f"  {r.cause}")          # .cause, not .detail — see header note 2

    # ---- BEAT 2: slide the chessboard in -> scale established --------------
    pause("Slide the printed chessboard target into frame, flat, then continue")
    ref = capture.run_chessboard_scale_session(
        session, cap, capture.CHESSBOARD_TARGET_5MM,
        inner_cols=INNER_COLS, inner_rows=INNER_ROWS, square_mm=SQUARE_MM)
    print(f"Scale established: {ref.px_per_mm:.2f} px/mm  (tier: {ref.artifact.tier})")
    print(f"  {ref.artifact.note}")
    # The chessboard is tier PRINTED_SPECIMEN, not a standard. Say this on
    # stage: the scale it gives is repeatable and is not traceable, and the
    # graticule path is the one that carries the (still uncertified) standard.
    if ref.px_per_mm < lm.CaptureLimits().min_px_per_mm:
        print(f"  WARNING: {ref.px_per_mm:.1f} px/mm is below the "
              f"{lm.CaptureLimits().min_px_per_mm:.0f} px/mm operating floor. "
              f"RESOLUTION will refuse every specimen. Tighten the field of "
              f"view before continuing — see the brief's 55 mm figure.")

    # ---- BEAT 3: remove chessboard, place the specimen -> measure ----------
    pause("Remove the chessboard, place the specimen packet, then continue")
    result = capture.capture_specimen(session, cap, camera_notes)
    for line in capture.manifest_lines(result):
        print(" ", line)

    roi = select_roi(result.gray)

    limits = lm.CaptureLimits(expected_glyphs=EXPECTED_GLYPHS)
    print(f"\nGates active: expected_glyphs={EXPECTED_GLYPHS}, "
          f"min_px_per_mm={limits.min_px_per_mm}")
    print("PLANARITY and NO_REDUNDANCY are NOT active on this path "
          "(no fiducials passed) — do not claim them in the narration.")

    bud = lm.provisional_budget()
    verdict = lm.measure_with_category(
        roi, result.px_per_mm, lm.RULES_2011, DECLARED_CATEGORY,
        limits=limits, budget=bud,
        convention="max_supported", convention_bias_mm=0.0,
        commodity_class=DECLARED_COMMODITY_CLASS,
        pdp_area_cm2=DECLARED_PDP_AREA_CM2, as_of=TODAY)

    print("\n=== VERDICT ===")
    print(verdict.report())
    print()
    for line in lm.legal_report_lines(verdict):
        print(" ", line)

    # Full-precision diagnostics. The report prints 2 d.p. by design; these are
    # what let you tell afterwards WHICH mark governed — which is the whole
    # decimal-point limitation, and the thing to log per the counting-rule sign.
    d = verdict.diagnostics
    if "glyph_extents_mm" in d:
        print("\n=== DIAGNOSTICS (log these) ===")
        print(f"  governing glyph index : {d.get('governing_glyph_index')}")
        print(f"  governing extent (mm) : {d.get('governing_glyph_extent_mm')!r}")
        print(f"  all extents (mm)      : "
              f"{[round(x, 5) for x in d.get('glyph_extents_mm', [])]}")
        print(f"  dropped glyph indices : {d.get('dropped_glyph_indices')}")
        print(f"  spans detected        : {d.get('n_spans')}")
        print("  If the governing extent is far below the others, check whether")
        print("  the ROI included a decimal point or other punctuation BEFORE")
        print("  recording this packet as DEFICIENT. Log it either way.")

    cap.release()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
