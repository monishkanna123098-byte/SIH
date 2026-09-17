# CLAUDE.md — briefing for Claude Code

Read this before writing any code in this repository.

## What this project is

SIH 2026, problem statement **SIH26034** — a compliance system for the Legal
Metrology (Packaged Commodities) Rules, 2011. Internal round **15 September
2026**.

There are ~94 public repositories on this exact problem statement. Nearly all
of them are the same architecture: OCR, a regex or LLM rule engine, a PDF, a
dashboard. **Matching them is table stakes, not the goal.**

What makes this project different is one thing: it measures character height
against a scale reference in frame, with a stated uncertainty, and it refuses
to answer when an image cannot settle the question. Searches of those ~94 repos
found **zero** doing scale-referenced measurement. The two teams sophisticated
enough to notice the problem exists both deferred it to a "future phase".

Every instruction below exists to stop that difference being accidentally
erased. It is easy to erase, because erasing it makes the app look more
decisive.

---

## NON-NEGOTIABLE INVARIANTS

Violating any of these is a defect, however good the code is otherwise.

### 1. Three states per finding, never two
`PASS` / `FAIL` / `CANNOT_DETERMINE`. A declaration the software could not read
is **not** a violation. Do not add a binary compliant/non-compliant toggle
anywhere, at any layer, for any reason.

### 2. Software never asserts absence
A photograph establishes that a declaration was **not in frame**. It cannot
establish that it is **not on the package**. Only `Coverage` with
`operator_examined_package=True` *and* a named `operator_id` unlocks an absence
claim. `vision_extract()` sets `asserts_absent=False` unconditionally — even
under full coverage. There are tests asserting this. Do not "improve" it.

### 3. Three source tiers, visually distinct
`EXTRACTED` (OCR/vision, unverified) · `MEASURED` (scale-referenced, with U) ·
`DETERMINED` (the officer's call). **Do not visually normalise these.** A
designer will want the declarations table and the height box to look
consistent. That inconsistency IS the product. The measured row has a heavy
border and its own styling on purpose.

### 4. No compliance score, percentage, or grade
A percentage implies the six declarations are commensurable and that
`CANNOT_DETERMINE` can be averaged with `PASS`. Neither is true. The dashboard
gets **counts**. There are tests asserting no score exists. If a stakeholder
asks for a big green 83%, the answer is no.

### 5. Refusal is a first-class UI state, never an error state
A red error toast reads "broken". A calm panel with a reason and a next action
reads "deliberate". Same behaviour, opposite impression, and the internal round
is judged by non-specialists.

```
INDETERMINATE — physical verification required
Measured 1.15 mm ± 0.17 mm (k=2) against a 1.00 mm requirement.
The uncertainty band straddles the threshold, so this instrument
will not issue a verdict.
Next: refer for physical verification.
```

### 6. Never print a height without its uncertainty
`Measurement.__post_init__` raises if one is present without the other. Keep it.

### 7. Never print an unverified rule sub-clause
`Citation.printable()` emits `LMPC 2011, Rule 6(1)` while the sub-clause letter
is unverified. The letters `(a)`–`(f)` are stored as candidates with
`AGGREGATOR`/`UNVERIFIED` provenance because secondary sources conflict and
nobody has read the Gazette yet. When someone does, flip confidence to
`VERIFIED` on the confirmed ones **only** — the letters then print
automatically.

### 8. The hash is not a signature
`content_hash()` is SHA-256 over the canonical record, not the PDF bytes. The
report says it is tamper-evident and **not** a digital signature. Do not
upgrade that wording.

---

## DO NOT TOUCH

These are audited, their self-tests pass, and their numbers are cited in
documents:

- `lm_metrology_v7.py` — the measurement engine (harness passes)
- `lm_capture.py` — rig and scale session (114 checks)
- `lm_legal_model.py` — statutory layer (81 checks)

If something needs to change in them, say so and stop. Do not edit them to make
an integration easier.

---

## Module map

| File | Role | Self-test |
|---|---|---|
| `lm_metrology_v7.py` | Character height, uncertainty, refusals | harness |
| `lm_capture.py` | Camera, scale artifact, capture manifest | 114 |
| `lm_legal_model.py` | Thresholds, provenance, disputed brackets | 81 |
| `lm_declarations.py` | Rule 6(1) checks, three states, tiers | 83 |
| `lm_extract.py` | Image/officer → declarations, coverage, cross-check | 34 |
| `lm_report.py` | Inspection record, PDF + DOCX, content hash | 26 |
| `test_integration.py` | Cross-module regression | 27 |
| `naive_vs_calibrated.py` | The demo beat. Runs without a camera | — |
| `demo_script.py` | Live rig sequence. **Never met a camera** | — |
| `app/service.py` | The only module permitted to import `lm_*` | — |
| `app/vision.py` | Vision provider adapter. The only module importing an SDK | — |
| `app/main.py` | FastAPI routes. Calls `service`, never `lm_*` | — |
| `test_webapp.py` | The web application, end to end | 334 |

The OCR cross-check needs the **`tesseract` binary** on PATH, not just
`pytesseract`. Without it the cross-check silently skips and every field stays
`verbatim_confirmed=None` — correct behaviour, but the differentiator is
invisible. Debian/Ubuntu: `apt-get install tesseract-ocr`.

Run every self-test before and after any change:
```bash
for f in lm_legal_model lm_capture lm_declarations lm_extract lm_report; do
  python3 $f.py | grep -i "self-test"
done
python3 test_integration.py | tail -3
python3 test_webapp.py | tail -3
```

Expected: **81 / 114 / 83 / 34 / 26**, **27** integration checks and **334**
webapp checks, all `0 failed`.

---

## Where the work stands

The build was split into chunks. This is what they were and what happened.

| # | Chunk | State |
|---|---|---|
| 0 | Admin: portal deadline, rubric, registration, owners | **UNOWNED — can disqualify** |
| 1 | `lm_declarations.py` — Rule 6(1) checks | done, 83 checks |
| 2 | `lm_extract.py` — image/officer → declarations | done, 34 checks |
| 3 | `lm_report.py` — record, PDF + DOCX, hash | done, 26 checks |
| 4 | Web app (FastAPI) — login, upload, three tiers, PDF/DOCX, history, dashboard | **built** |
| 5 | Metrology wired into the app, pre-flight gates surfaced | **built** |
| 6 | Pipeline view: CAPTURE → CALIBRATE → EXTRACT → MEASURE → ADJUDICATE | **built** |
| 7a | Acceptance pass — adversarial verification | done, see `ACCEPTANCE-2026-09-13.md` |
| 7b | Scoped repairs from that pass | done, see `ACCEPTANCE-2026-09-13.md` |
| 8 | Vision extraction, the review gate, the OCR cross-check | **built** |
| 7 | Rehearsal, 14 Sep. No new code that day | — |

**Chunks 4, 5, 6 and 8 are built and self-tested. Do not rebuild them.** The
web application lives in `app/`; run `python3 test_webapp.py` (334 checks)
before assuming otherwise.

Also done, outside the chunk plan: a full code audit (`AUDIT-2026-09-12.md`),
four bugs fixed in `demo_script.py`, and `naive_vs_calibrated.py` — the demo
beat, which runs with no camera and carries the differentiator on its own.

Two defects are recorded in `ACCEPTANCE-2026-09-13.md` and **deliberately left
unfixed**: the phone-width CSS overflow (the strip is fine at 700px) and the
read-then-write inspection-ID race (not reproducible at 40 concurrent). Do not
"fix" either without reading why they were left.

If you fall behind, cut from the bottom: 6 first, then the dashboard inside 4,
then role-based access. **Chunks 1, 3 and 5 are never cut — they are the
differentiator.**

---

## The web application — what it is, and the shape it must keep

**Built** (chunks 4, 5, 6 and 8). This section describes what exists and the
constraints it is held to, not work outstanding.

A **single local FastAPI app** — not a separate frontend and backend. It
imports the modules directly; no HTTP between them, no CORS, no hosting.
"Web application" is satisfied by a browser pointed at localhost.

Screens: upload → ROI selection → results (three tiers) → report download
(PDF/DOCX) → scan history with search → dashboard (counts only) → two roles
(officer, supervisor).

Aesthetic: government-formal. Navy `#0A1628`, serif headings, real tables, no
gradients, no animation, no startup polish.

### Known-unfinished, do not paper over
- `PLANARITY` and `NO_REDUNDANCY` cannot fire on the demo path — no fiducials
  are passed, both sit inside `if src_mm is not None`. Do not fake them.
- `select_roi()` in `demo_script.py` is untested against real hardware.
- `FLOOR_LIMITED` is unreachable in production (stops firing at exactly
  30.0 px/mm, which is exactly `min_px_per_mm`). Don't expect it in logs.
- ROI-boundary choice shifts the measured height by ~0.0064 mm and is **not**
  in the uncertainty budget. Show the ROI box on the evidence image so the
  region is a visible declared input.

---

## Working style

Direct. No flattery. Flag weak spots unprompted. If something in this file is
wrong or a plan won't work, say so rather than building it anyway. Verify
claims before asserting them — this project's recurring failure mode is prose
that no longer matches code, and it has been caught three times.
