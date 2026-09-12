# CHUNK 5 — wiring the measurement in

Paste this whole file as your message to Claude Code, **after** you have clicked
through chunk 4 yourself and confirmed its seven done-conditions.

---

## Before you write any code

1. Re-read `CLAUDE.md`. Invariants 3, 5 and 6 are the ones this chunk can break.
2. Read `AUDIT-2026-09-12.md` §2 — three findings there change what you build.
3. Run every self-test and confirm **81 / 114 / 39 / 34 / 26** and **27**, all
   `0 failed`. If any differs, stop and report.
4. Confirm chunk 4's two invariant cases still behave: photo-only upload with
   blank fields → six `CANNOT_DETERMINE`, zero `FAIL`; same with the coverage
   checkbox ticked → six `FAIL`.

---

## What you are building

The `measurements` table gets populated. The cream `[tier: MEASURED]` box on the
results page starts carrying a real number, a real uncertainty, or a real
refusal.

**This is the differentiator.** Searches of ~94 public repositories on this
problem statement found zero doing scale-referenced measurement. Everything else
in this application is parity work; this chunk is the reason the project exists.

---

## The call

`service.py` is still the only module permitted to import `lm_*`.

```python
import numpy as np, lm_metrology_v7 as lm

verdict = lm.measure_with_category(
    roi,                       # np.ndarray, grayscale float, the CROPPED region
    ppm,                       # float, pixels per millimetre — see below
    lm.RULES_2011,
    declared_category,         # lm.CATEGORY_GENERAL or lm.CATEGORY_FORMED
    limits=lm.CaptureLimits(expected_glyphs=declared_glyph_count),
    budget=lm.provisional_budget(),
    convention="max_supported",
    convention_bias_mm=0.0,
    commodity_class=declared_commodity_class,
    pdp_area_cm2=declared_pdp_area_cm2,
    as_of=datetime.date.today(),
)
```

`Verdict` fields: `band`, `h_mm`, `U_mm`, `threshold_mm`, `refusals`,
`rule_candidates`, `diagnostics`, `U_all_measured`.
Each `Refusal` has `.code` and `.detail` (note: `lm_capture.CaptureRefusal`
uses `.cause` — different class, different field, this has bitten the project
before).

Bands are `COMPLIANT`, `DEFICIENT`, `REQUIRES_PHYSICAL_VERIFICATION`.

### Map to the storage contract

`lm_report.Measurement` fields are exactly:
`band · height_mm · u_mm · threshold_mm · convention · refusal_code ·
refusal_detail · threshold_source_tier · manifest · roi_box`

`Measurement.__post_init__` **raises** if `height_mm` and `u_mm` are not both
present or both absent. Do not catch that and substitute a default — invariant
6 says a height without an uncertainty is never printed, and the exception is
how that is enforced.

Use `lm.legal_report_lines(verdict)` for the threshold's provenance. On the
legacy path it returns `()`; handle that.

---

## px/mm — where the number comes from

Without a scale reference, **there is no measurement.** A pixel height divided
by an assumed DPI is precisely the naive method `naive_vs_calibrated.py` exists
to discredit; do not implement it as a fallback, do not offer it as an option,
do not let a form default to one.

Three acceptable sources, in order:

1. **A chessboard scale session** via `lm_capture.run_chessboard_scale_session`
   — requires a camera, and `demo_script.py` covers it. Out of scope here.
2. **An operator-entered px/mm** from a completed scale session, typed into the
   form with the artifact tier recorded alongside it.
3. **No scale → no measurement.** The section shows *"No scale reference —
   height cannot be measured from this image."* This is a correct outcome.

Implement 2 and 3 in this chunk. Add a "Scale reference" group to the upload
form: px/mm (float), artifact description, artifact tier. If px/mm is blank,
skip measurement entirely and record nothing in `measurements`.

Guard: if px/mm is below `lm.CaptureLimits().min_px_per_mm` (30.0), warn on the
form that `RESOLUTION` will refuse every specimen — but still attempt it and let
the engine issue its own refusal. Do not pre-empt the engine's gates.

---

## ROI selection

The engine measures whatever array it is handed. Hand it a full frame and it
hunts for ink across the platen and the packet edges. Chunk 4 stored an image;
this chunk crops it.

Implement browser-side box selection on the stored image — a canvas overlay,
drag to draw, vanilla JS, no library. Post `x, y, w, h` in **image pixel
coordinates**, not display coordinates; scale for any CSS resizing or the region
will be wrong in a way that is hard to see and silently changes the number.

Crop with PIL or numpy slicing, convert to grayscale float, pass as `roi`.

Store the box in `measurements.roi_box` and **draw it on the stored evidence
image**, saved as a separate file so the original is untouched.

### Why the box must be visible

From `AUDIT-2026-09-12.md` §2.1: the measured height depends on where the box is
drawn — not only through which marks are inside it, but because
`levels_iterative` estimates ink and substrate levels from the region's own
pixels. More blank substrate raises the substrate level, moves the 50% crossing,
and changes the height. Measured spread: **0.0064 mm**, larger than three of the
eight budget terms, and biased **toward COMPLIANT**.

It is not in the uncertainty budget. Do not add a budget term for it — that
number cannot be derived in three days. Make the region a **visible declared
input** instead, and label it "operator-declared region" wherever it appears.

---

## Pre-flight quality checks

`CONTRAST`, `CLIPPED` and `ILLUMINATION_GRADIENT` already exist as refusal gates
in `lm_metrology_v7`. **Do not reimplement them.** Surface them: run the
measurement, and if the verdict carries one of those codes, present it as an
image-quality problem with a remedy ("re-light and rescan") rather than as a
compliance outcome.

Competing entries advertise blur/contrast/orientation analysis as a headline
feature. You already have it, fully self-tested. It costs nothing to show.

---

## Refusal is a UI state, not an error

Invariant 5, and the easiest way to lose the internal round. A red error toast
reads "broken". The internal round is judged by non-specialists.

Render every refusal in the cream `[tier: MEASURED]` box, same styling as a
successful measurement, in this shape:

```
INDETERMINATE — physical verification required
Measured 1.15 mm ± 0.17 mm (k=2) against a 1.00 mm requirement.
The uncertainty band straddles the threshold, so this instrument
will not issue a verdict from an image.
Next: refer for physical verification.
```

`Measurement.band_explanation()` already generates the middle sentences for
every band and refusal. Use it rather than writing your own.

### The disputed bracket — test this one explicitly

A `THRESHOLD_DISPUTED` refusal must print **no height** and must not contain
either candidate threshold value. The legal model deliberately withholds them;
there are tests in `lm_legal_model` and `test_integration` covering it. Confirm
the UI does not reintroduce them by, say, rendering `rule_candidates`.

---

## Three things that will not work, and must not be faked

1. **`PLANARITY` and `NO_REDUNDANCY` cannot fire on this path.** Both sit inside
   `if src_mm is not None` in `capture_checks`, and no fiducials are passed.
   Job 2's "done when" criterion in the team brief is not met. Do not claim
   either in the UI, do not add a green "planarity verified" row.
2. **`FLOOR_LIMITED` is unreachable in production.** It stops firing at exactly
   30.0 px/mm, which is exactly `min_px_per_mm`. Below that, `RESOLUTION` fires
   too; above, neither does. Do not expect it in logs or build UI for it.
3. **Do not say "accuracy".** This system has never measured a reference
   standard. `§15` of the team brief forbids the word until it has. "Uncertainty",
   "repeatability" and "band" are the available vocabulary.

---

## Definition of done

1. An inspection with a px/mm value produces a populated `measurements` row and
   a rendered cream box.
2. An inspection **without** px/mm records no measurement and says so plainly.
3. A near-threshold case renders `REQUIRES_PHYSICAL_VERIFICATION` as a calm
   panel — not an error, not a toast, not red.
4. A `THRESHOLD_DISPUTED` refusal prints no height and neither candidate value.
5. The ROI box is stored, drawn on a copy of the evidence image, and labelled
   "operator-declared region".
6. The exported PDF and DOCX carry the measurement, its uncertainty, its
   convention and its threshold source tier.
7. Every self-test still passes at its original count.
8. `python3 naive_vs_calibrated.py` still produces identical output to before
   this chunk. If it does not, something underneath moved.

Report what you built, which conditions you verified, and anything you could
not do. **Then stop.**

---

## If you disagree

The px/mm requirement is the one that will feel most wrong — it makes the
feature unusable without extra input, and an assumed DPI would make the demo
smoother. That is exactly the trade this project refuses. Say so and stop
rather than adding a fallback.
