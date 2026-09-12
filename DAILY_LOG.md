# Daily Log

One entry per day. Date, self-test counts, any code version bump, any
`_GATE_PROVENANCE` change and why. This is what answers "what changed since
Tuesday" — keep it short, keep it every day.

---

## 2026-09-09

- **lm_metrology_v7.py version:** 7.9-call-site-3-2026-09-07
- **lm_capture.py self-test:** 114 / 114
- **lm_legal_model.py self-test:** 81 / 81
- **`_GATE_PROVENANCE` changes today:** none
- **What ran green:**
- **What failed, and why:**
- **What tomorrow depends on:**
- **New blockers found:**

---

## 2026-09-10

- **lm_metrology_v7.py version:**
- **lm_capture.py self-test:**
- **lm_legal_model.py self-test:**
- **`_GATE_PROVENANCE` changes today:**
- **What ran green:**
- **What failed, and why:**
- **What tomorrow depends on:**
- **New blockers found:**

---

## 2026-09-11

- **lm_metrology_v7.py version:**
- **lm_capture.py self-test:**
- **lm_legal_model.py self-test:**
- **`_GATE_PROVENANCE` changes today:**
- **What ran green:**
- **What failed, and why:**
- **What tomorrow depends on:**
- **New blockers found:**

---

## 2026-09-12  — external code audit

- **lm_metrology_v7.py version:** 7.9-call-site-3-2026-09-07 (UNCHANGED)
- **sha256:** `7be71979c2d260674cfc623246aec7965cd60f16cc2bc90212abc90c94cd6fa2`
  — identical before and after today's work. **No measurement path was touched.**
- **lm_capture.py self-test:** 114 / 114
- **lm_legal_model.py self-test:** 81 / 81
- **NEW `test_integration.py`:** 27 / 27
- **`_GATE_PROVENANCE` changes today:** none

- **What ran green:** all four entry points. Every number in the v7.9 harness run
  reappeared unchanged — 4-pt RMS 2.716e-13, 5-pt RMS 0.353, raw U 0.16634,
  h = 1.40 / U = 0.17 / TL = 1.00 in the conformity demo. The repair added prints
  and tests only, exactly as §13a specified it should.

- **What failed, and why:** `demo_script.py` had never executed once. Four faults,
  all found today, all fixed:
  1. imported `lm_metrology_v7` while the file on disk was `lm_metrology_v7.9.py`
     — died at line 18. Fixed by restoring the canonical filename.
  2. read `r.detail` off a `CaptureRefusal`, which carries `.cause` — would have
     died in BEAT 1.
  3. passed no `limits=`, so `expected_glyphs` was None and **GLYPH_COUNT was
     silently off for the entire demo** — the gate the counting-rule sign exists
     for and job 4's predicted top offender.
  4. passed the whole camera frame as the ROI. No ROI mechanism existed anywhere
     outside the synthetic `Scene` class.

- **New blockers found:**
  - **ROI-boundary sensitivity is an unbudgeted NINTH error term.** Same glyphs,
    same pixels; only how much blank substrate the operator's box includes.
    Measured spread **0.0064 mm** — bigger than three of the eight budget terms,
    3.8% of U — and it moves the reading **upward, toward COMPLIANT**, which is
    the one direction §7.1 commits us not to err in. Mechanism: `levels_iterative`
    estimates ink/substrate levels from the ROI's own pixel population, so a
    generous box raises the substrate level and moves the 50% crossing. Not in
    the eight terms, not in §15, not on the Q&A card.
  - **`FLOOR_LIMITED` is unreachable in production.** It stops firing at exactly
    30.0 px/mm, which is exactly `min_px_per_mm`. Below that, RESOLUTION fires
    too; above it, neither does. It can never fire alone. Slide 5's "may be a
    second confirmed firing" should be struck — the answer is no, and structurally
    so. §13a item 9's contradiction is also resolved: the sweep's FLOOR-LIMITED
    *label* is a `mm_to_px` return value, not a Refusal. Different quantities.
  - **Slide 5's refusal count drifted again.** It says nineteen codes; the file
    holds **twenty**. `LEGAL_MODEL_UNAVAILABLE` arrived with the 7.9 integration
    and was never re-counted — the same failure the slide already documents
    happening at "eight", one version later.
  - **The gate ledger count in §8 and §15 is wrong.** Both say eight gates,
    three derived. `_GATE_PROVENANCE` actually holds **nine: five placeholder,
    four derived.** `_FIDUCIAL_PICK_PX` is the uncounted derived one.
  - **PLANARITY and NO_REDUNDANCY still cannot fire on the demo path** — no
    fiducials are passed, so both sit inside an `if src_mm is not None` that is
    never true. Job 2's "done when" criterion is not met and is not close.
  - **Two different U values both print as `0.17` on one screen.** The verdict
    line carries U at max(h,TL) = 0.17321; the budget report carries U at
    H_REF = 0.16634. 4.1% apart, indistinguishable at 2 d.p.

- **What tomorrow depends on:** the internal round is **2026-09-15**, three days
  out. Portal deadline still unresolved (20 vs 30 September, §16, unticked).
