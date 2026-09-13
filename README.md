# SIH26034 — Legal Metrology compliance system

Smart India Hackathon 2026 · Problem Statement **SIH26034**
Ministry of Consumer Affairs, Food & Public Distribution (DoCA)

Scans packaged commodity labels and checks them against the Legal Metrology
(Packaged Commodities) Rules, 2011 — including a **scale-referenced measurement
of character height with a stated uncertainty**, which is the part a photograph
alone cannot give you.

## Quick start

```bash
python3 -m pip install -r requirements.txt
for f in lm_legal_model lm_capture lm_declarations lm_extract lm_report; do
  python3 $f.py | grep -i "self-test"
done
python3 test_integration.py | tail -3
python3 naive_vs_calibrated.py      # the demo beat, no camera needed
```

Expected: 81 / 114 / 39 / 34 / 26 self-test checks, 0 failed; 27 integration
checks, 0 failed.

## The web application

A single local FastAPI app that imports the modules directly -- not a separate
frontend and backend. No HTTP between layers, no CORS, no build step, no
hosting. "Web application" is satisfied by a browser pointed at localhost.

```bash
./run.sh                 # http://localhost:8000
python3 test_webapp.py   # 175 checks, 0 failed
```

Seeded users, one per role: `officer` / `officer-2026` and
`supervisor` / `supervisor-2026`.

`app/service.py` is the only file permitted to import `lm_*`. Routes call
`service`; `service` calls the engines, so the invariants stay enforceable in
one reviewable file rather than scattered through request handlers.

The two cases that matter, both covered by `test_webapp.py`: six blank
declarations from images alone are six CANNOT_DETERMINE; the same six blanks
are six FAIL only once a named operator states they examined the physical
package. That difference is invariant 2, and it is the whole reason the
coverage block sits above the submit button.

### The pipeline strip

Five stages across the top of every results page:

```
01 CAPTURE -> 02 CALIBRATE -> 03 EXTRACT -> 04 MEASURE -> 05 ADJUDICATE
```

Server-rendered from the stored record -- each stage shows what is actually on
the record, never a timer. A stage that was skipped reads `pending`, not
`done`; a refused measurement reads `refused` in cream, never red.

`02 CALIBRATE` gets the same width as every other stage and is never hidden
when empty, which is most of the time: a scale reference is the thing most
inspections lack. "No scale reference -- height cannot be measured" is a true
statement, and it is the one stage nothing else on this problem statement can
draw at all.

### The measurement

The `[tier: MEASURED]` box carries a real scale-referenced height, or a real
refusal. It needs a pixels-per-millimetre factor from a completed scale
session, entered on the upload form with the artifact it came from and that
artifact's tier. **There is no DPI fallback**: without a scale reference the
box says so and no measurement is recorded, which is a correct outcome rather
than a gap. `naive_vs_calibrated.py` is the argument for why.

The region handed to the engine is drawn by the operator on the stored image
and posted in image pixels. Where that boundary goes changes the measured
height by ~0.0064 mm (`AUDIT-2026-09-12.md` §2.1), biased toward compliant.
That is not in the uncertainty budget and is not folded into one; the region is
recorded as a declared input instead, drawn on a copy of the evidence image,
labelled "operator-declared region", and every re-measurement is appended
rather than overwritten.

## Why this is not another OCR compliance app

A height in pixels becomes a height in millimetres only through a
pixels-per-millimetre factor. With nothing of known size in the frame, that
factor must be assumed — and when the camera moves, the true factor changes
while the assumed one does not.

`naive_vs_calibrated.py` demonstrates it: one packet, three camera distances.
A calibrated-once estimator spreads **0.42 mm** and flips its verdict from
COMPLIANT to DEFICIENT. A scale-referenced measurement spreads **0.0012 mm**
and returns the same answer every time.

This is a geometric fact, not a claim about anyone's software.

## Reading order

1. `CLAUDE.md` — invariants. Read before changing anything.
2. `AUDIT-2026-09-12.md` — what was found, what was fixed, what is still open.
3. `BUILD-SPEC-parity.md` — what to build and what not to.
4. `CHECKLIST-to-15-Sep.md` — the plan to the internal round.

## Status

The measurement, statutory, declaration, extraction and report layers are
built and self-tested. **No part of this has met a camera.**

The web application (chunks 4, 5, 6 and 8) is built: login, upload, a
five-stage pipeline strip, results in three tiers, region selection,
scale-referenced character-height measurement with its uncertainty, PDF/DOCX
export, history with search, and a counts-only dashboard.

**Automated extraction** reads the six Rule 6(1) declarations from an uploaded
image, and is gated behind a review step. Every machine-filled field is marked
`read from image — unconfirmed`; a declaration the model could not read shows
`not found in image` rather than an empty box; and the coverage checkbox — the
only thing that can turn a blank into a violation — stays disabled until the
officer has edited or confirmed all six. That gate is enforced server-side, not
just in the browser. An optional OCR cross-check marks any value no OCR engine
on the same image saw, which the declaration layer downgrades to
CANNOT_DETERMINE before any format check runs. With no API key configured the
feature is simply absent and the manual path — a first-class input, not a
fallback — is unchanged.

Still true, and unchanged by any of it: **no part of this has met a camera.**
The scale factor is operator-entered from a session the rig has not yet run.
