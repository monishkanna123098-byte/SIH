# ACCEPTANCE PASS — 2026-09-13

Chunk 7a. Adversarial verification of chunks 4, 5 and 6.
**Nothing in this pass was fixed.** Four defects are recorded in section G2
with proposed fixes, not applied.

Run on the committed tree at `587ed30` (chunk 6), branch
`claude/adoring-meitner-gczaml`. Working tree clean at the start of the pass.

---

## A. Regression

| # | Result | Detail |
|---|---|---|
| A1 | **PASS** | `81 / 114 / 39 / 34 / 26`, and `27` integration checks. All `0 failed`. |
| A2 | **PASS** | Byte-identical. Compared against a run of `naive_vs_calibrated.py` executed from a **pristine extraction of the original zip** — a genuine pre-chunk-4 state, not a saved copy from later. 6543 bytes, 112 lines, md5 `f3a14d36b82dceda0cae784d850878c5` both sides; `cmp` reports no difference. |
| A3 | **PASS** | `git status --porcelain` empty. `data/inspections.db` and `data/session.key` exist on disk but are gitignored and untracked; `git ls-files` matches nothing under `data/`, no `*.db`, no `*.key`, no `.env`. |

Additionally: all nine engine and demo modules (`lm_metrology_v7`, `lm_capture`,
`lm_legal_model`, `lm_declarations`, `lm_extract`, `lm_report`,
`test_integration`, `naive_vs_calibrated`, `demo_script`) are md5-identical to
the original zip. Nothing underneath moved.

---

## B. Invariant probes

| # | Result | Detail |
|---|---|---|
| B1 | **PASS** | Six blank, unticked, no operator ID → `PASS 0 · FAIL 0 · CANNOT_DETERMINE 6`. Zero FAIL. |
| B2 | **PASS** | Same, ticked + operator ID `LM-OFF-114` → `PASS 0 · FAIL 6 · CANNOT_DETERMINE 0`. The coverage form reaches `Coverage`. |
| B3 | **PASS** | Ticked with a blank operator ID is **refused at the form** (HTTP 200, "Operator ID is required when you confirm you examined the physical package") so the incoherent state is never stored. Probed the engine path directly as well: `Coverage(examined=True, operator_id="")` → `CANNOT_DETERMINE 6 · FAIL 0`. `can_assert_absence()` requires both halves. |
| B4 | **PASS** | px/mm blank → **0 rows in `measurements`**, state `no_scale`, panel reads "No scale reference / Height cannot be measured from this image". Regex for `\d+\.\d+\s*mm` across the whole `[tier: MEASURED]` section returns **nothing**. No height appeared, so the naive method has not reappeared. |
| B5 | **PASS** | 75.0 cm², general/general, px/mm 120 → band `REQUIRES_PHYSICAL_VERIFICATION`, refusal `THRESHOLD_DISPUTED`, height `not measured`, threshold `not resolved`. Grepped (not eyeballed) for `1.5` and `2.0` in the **rendered page**, the **decompressed PDF text**, and the **DOCX `word/document.xml`**: `{'page': [], 'pdf': [], 'docx': []}`. Nothing leaked. |
| B6 | **PASS** | Near-threshold → HTTP **200**, cream `[tier: MEASURED]` panel, headline `INDETERMINATE -- physical verification required`, reason "The measured band [0.84, 1.17] mm straddles the 1.00 mm requirement…", next action "Refer for physical verification." No `class="error"`, no `--fail-bg`, no `v-FAIL`, no `color:red`, no toast, no traceback, and no standalone word "error" in the panel. See G3 note 1 — my first probe false-positived on the string "exception". |
| B7 | **PASS** | Direct `sqlite3` inserts all refused with `IntegrityError: CHECK constraint failed` — `verdict='NON_COMPLIANT'`, `verdict='COMPLIANT'`, `verdict='true'`, `source_tier='AI'`, `source_tier='OCR'`. A legal row (`CANNOT_DETERMINE`/`MEASURED`) still inserts, so the constraint is discriminating rather than rejecting everything. Invariants 1 and 3 are enforced by the database. |
| B8 | **PASS** | `accuracy`/`accurate`: **no matches**. `progress-bar|ring|donut|gauge`: **no matches**. `compliance (score\|rate\|grade)` matches three lines, all of which are the project stating it does *not* do this: two source comments (`app.css:165`, `dashboard.html:6`) and the user-visible footer "It issues no compliance score, percentage or grade." No score is computed or displayed: `service.dashboard()` returns only `total, any_fail, any_cannot, clean`, and `/dashboard`, `/history`, `/upload` render **no percentage figure at all**. Jinja comments do not reach the browser. |
| B9 | **PASS** | No `is_compliant`, `non_compliant`, boolean verdict flag, `✓`, `✔`, `✗` or `✘` anywhere in `app/`. The only grep hit is the word "passed" inside a docstring ("passed straight through"). No boolean coupled to `verdict` in `service.py`. |

---

## C. Robustness

| # | Result | Detail |
|---|---|---|
| C1 | **PASS** | Under `unshare -n` with all proxy vars unset and outbound confirmed dead (`OSError` to 1.1.1.1:53): full inspection created with image, measured (`1.40 mm ± 0.17 mm (k=2)`, band PASS), determination recorded, **PDF 7088 B (`%PDF-`) and DOCX 39365 B (`PK`) both generated**, history and dashboard render. |
| C2 | **PASS** | Empty directory → `init_db()` creates all five tables (`users, scans, findings, measurements, determinations`) and both seeded users (`officer`/officer, `supervisor`/supervisor) without error. |
| C3 | **FAIL** | See **Defect 1**. A text file renamed `.jpg` is **accepted** (extension-only validation), stored, and served back as `image/jpeg`. No traceback reaches the browser and `measure` fails closed — but the results page then reads "Next: draw the region to measure, below" while **no region selector is rendered**, the error message is **never displayed**, and the message itself is a raw PIL string containing an **absolute server filesystem path**. |
| C4 | **PASS** | 5200×4000 (**20.8 MP**, 3.4 MB PNG). Upload < 0.1 s, results page < 0.1 s, **measurement 8.6 s**, PDF 0.1 s. Completes cleanly with band PASS, no refusal, no error. Timing noted in G3 note 3 for demo purposes. |
| C5 | **PASS** | Four hostile regions, all rejected with `measure_error` and **zero rows written**: larger than the image (99999×99999), zero-area (0×0), negative origin (−5,−5), and one pixel too tall. No crash, and **no silent full-frame fallback** — the measurements table stayed empty throughout. |
| C6 | **PASS** | Report for a scan with no measurement: PDF 4357 B, DOCX 38147 B, both HTTP 200. **No `Character height` section is fabricated.** (`k=2` does appear in the DOCX, but via the `TIER_NOTE[MEASURED]` explanation — "a stated uncertainty (k=2)" — not via a height. Verified at source.) |
| C7 | **PASS** | 8 sequential → 8 distinct. **40 simultaneous uploads against the live server → 40 × HTTP 303, 40 distinct IDs, zero duplicates, zero 500s.** See G3 note 2: the allocator is read-then-write without a transaction guard, so the race exists in code even though it did not reproduce. |
| C8 | **PASS** | Zero scans: `/history`, `/dashboard`, `/history?q=nothingmatches` all HTTP 200, no traceback. `dashboard()` returns `total=0, any_fail=0, any_cannot=0, clean=0`. No divide-by-zero, because there is no division anywhere — counts only. |
| C9 | **PASS** | Logged out, every protected route redirects `303 → /login`: `/upload`, `/history`, `/dashboard`, `/scan/{id}`, `/report.pdf`, `/image`, `/image.roi`, and POST `/determination`, `/measure`. An officer POSTing a determination **or a measurement** on a supervisor's scan is sent to `?denied=1`. A supervisor may act on an officer's scan (HTTP 303). Note: there is no supervisor-*only* route by design — the rule is supervisor-or-owner, set in chunk 4. |
| C10 | **PASS** | Server stopped by PID and restarted. All **56** inspections still listed, identical set. Reports still downloadable (PDF 200 / 4466 B, DOCX 200 / 38222 B). A measured scan still shows its height, and both the evidence image and the annotated ROI copy still serve HTTP 200. |

---

## D. The pipeline strip

| # | Result | Detail |
|---|---|---|
| D1 | **PASS** | Brand-new scan: `CAPTURE pending` (awaiting image), `CALIBRATE pending`, `EXTRACT done`, `MEASURE pending` (not measured), `ADJUDICATE pending` (awaiting determination). Five stages in markup. EXTRACT is `done` because extraction genuinely ran and reported "0 of 6 declarations read" — see G3 note 4. |
| D2 | **PASS** | No scale reference → `CALIBRATE pending` with "no scale reference -- height cannot be measured" rendered on the page. **Not hidden, not shrunk, not skipped**: browser-computed stage widths are `201 · 201 · 201 · 201 · 200 px`, equal within 1 px; `display: list-item`, `visibility: visible`. |
| D3 | **PASS** | Refused measurement → `MEASURE refused`, line `THRESHOLD_DISPUTED`, note naming the unsettled rule. Browser-computed `background-color: rgb(243, 240, 231)` = `#F3F0E7` cream, `border-top-color: rgb(10, 22, 40)` = navy. No `v-FAIL`, no `fail-bg`, no `error` class in the strip. Not red. |
| D4 | **PASS** | No stage reads `done` without its data. Skipped steps read `pending` in every case checked (no image, no scale, no measurement, no determination). |
| D5 | **PASS** | Inside the strip markup: no percentage figure, no `<progress>`, no "ring", no `✓✔✗✘✕`. |
| D6 | **PASS** | At 700 px the strip stacks vertically, full width (5 × 644 px), value font 11.5 px, **no horizontal overflow of the strip or the page**. Also clean at 680 px. (At 420 px the *page* overflows — not the strip — see **Defect 2**.) |
| D7 | **PASS** | Nothing in the strip animates: no `transition`, `animation`, or `@keyframes` in its rules (checked with comments stripped). `prefers-reduced-motion` therefore has nothing to suppress. |

---

## E. Dashboard

| # | Result | Detail |
|---|---|---|
| E1 | **PASS** | Exactly four counters. |
| E2 | **PASS** | Counts, not rates. No percentage figure renders anywhere on the page. |
| E3 | **PASS** | Exactly 10 rows after the header, and the order matches `SELECT inspection_id FROM scans ORDER BY created_at DESC, id DESC LIMIT 10` exactly. |
| E4 | **PASS** | Reconciles against the database with no discrepancy. SQL truth on 56 scans: `total=56, any_fail=2, CD-and-no-FAIL=54, clean=0`. Dashboard: `total=56, any_fail=2, any_cannot=54, clean=0`. The three outcome buckets sum to 56, which equals `COUNT(DISTINCT scan_id) FROM findings`. |
| E5 | **PASS** | **Exclusive buckets were chosen, and the labels say so** — as the item permits. Rendered labels: "inspections recorded", "with at least one FAIL", "with at least one CANNOT DETERMINE **and no FAIL**", "with **no FAIL and none undetermined**". In the current data no scan has both a FAIL and a CANNOT_DETERMINE, so the two readings do not diverge here; the labels are what makes the choice honest when they do. |

---

## F. The report artifact

| # | Result | Detail |
|---|---|---|
| F1 | **PASS** | PDF and DOCX generated from one fully-populated scan agree on the headline (`NO NON-COMPLIANCE DETECTED`), on `PASS 6` and `FAIL 0`, on every finding label and verdict, and on the measurement (`1.40`, `k=2`) — every token checked present in both or absent from both. |
| F2 | **PASS** | All **13** structural markers present in both `inspection-record-sample.pdf` and our export: title, `INSPECTION RECORD`, `Mandatory declarations`, `[tier: EXTRACTED]`, `Character height`, `[tier: MEASURED]`, `Officer determination`, `[tier: DETERMINED]`, `How each finding was obtained`, the tier notes, `Coverage`, `Record digest (SHA-256)`, `Engine:`. (Chunk 4 reported this partially unverified because that record carried no measurement and no determination; with both present the structures match completely.) |
| F3 | **PASS** | `content_hash()` identical across two generations (`47e07c2ffe03c50bc45e200a…`), the 64-hex digest printed in the PDF is identical between the two renders, and the printed digest equals `content_hash()`. |
| F4 | **PASS** | Mutating one finding's verdict and `why` directly in the database changes the digest: `47e07c2f…` → `79ba874f…`. |
| F5 | **PASS** | `HASH_NOTE` still reads "…a tamper-evident check, **NOT a digital signature**…", present in both PDF and DOCX. Nothing anywhere claims the document is digitally signed. |
| F6 | **PASS** | `LMPC 2011, Rule 6(1)` prints in both. **No sub-clause letter `(a)`–`(f)` is printed** in the PDF, the DOCX, or the page. The Gazette read has not happened, so `Citation.printable()` correctly withholds them. |

---

## G1. Extra probes (not on the checklist)

Run because the instruction was to try to break it, not to confirm it works.

| Probe | Result | Detail |
|---|---|---|
| Session-cookie forgery | **PASS** | Rejected: swapped user id, missing signature, garbage, empty. A **valid signature with the user id edited** is also rejected (the id is inside the signed payload). A genuine cookie still works. |
| Path traversal | **PASS** | Setting `image_path` to `../../../etc/passwd` directly in the database → the image route redirects instead of serving; `root:` does not appear in the response. `realpath` confinement holds. |
| SQL injection | **PASS** | `declared_category` = `general'; DROP TABLE scans;--` rejected by the allow-list; `scans` intact. All queries are parameterised. |
| XSS | **PASS** | `<script>alert(1)</script>` in the product name and `<img src=x onerror=alert(2)>` in a declaration are both escaped (`&lt;script&gt;`, `&lt;img src=x`). **Raw `<img src=x` and raw `<script>` are absent**, so neither payload is executable. Jinja autoescaping is on. |
| Hostile numerics | **partial** | `-5` area, `0` and `-1` px/mm, `-3` glyphs all refused with clear messages. `NaN` is stored as NULL by SQLite and renders as `—`. **`inf` is accepted and renders as "inf cm²"** — see **Defect 3**. |

---

## G2. Defects — recorded, NOT fixed

### Defect 1 — a non-image upload produces a silent dead end, and leaks a server path
**Severity:** medium. Demo-visible.
**Invariant touched:** none of the eight directly. It touches invariant 5's
*spirit*: this state reads neither as working nor as a deliberate refusal — it
reads as nothing happening.

**What breaks.** `app/main.py` validates the upload by **file extension only**
(`ALLOWED_IMAGE`). A text file renamed `notes.jpg` is accepted, stored, and
later served back with `Content-Type: image/jpeg`. Three consequences:

1. `service.image_size()` returns `None`, so the ROI selector block
   (`{% if may_determine and m.image_w and m.scale_ppm %}`) is **not rendered** —
   while the measured panel simultaneously says *"Next: draw the region to
   measure, below."* The instruction points at something that does not exist.
2. The `measure_error` message is **never shown**, because the error block lives
   inside the `roi-picker` div that was just suppressed.
3. That message is the raw Pillow exception string and contains an absolute
   server path:
   `cannot identify image file '/tmp/acc-c-ri3imd3r/up/2706c3ed…jpg'`.
   It reaches the redirect URL.

**Reproduce.**
```bash
printf 'not an image\n' > notes.jpg
# upload notes.jpg with a px/mm value, then open the results page
```
Results page renders HTTP 200, tells you to draw a region, and offers none.

**Proposed fix (not applied).** Three small changes, all in existing files:
- `app/main.py` upload handler: after reading the bytes, verify with
  `PIL.Image.open(io.BytesIO(data)).verify()` inside a `try`, and on failure
  return `again("That file is not a readable image…")` so it is rejected at the
  form, where every other bad input is already rejected.
- `app/service.py` `measure_scan()`: replace the raw `str(exc)` for `OSError`
  with a fixed operator-facing sentence, so no internal path can reach a URL.
- `app/templates/results.html`: render the `measure_error` notice outside the
  `roi-picker` block, and give the `not_measured` state a branch for
  "the stored image could not be read".

### Defect 2 — horizontal page overflow at phone width
**Severity:** low. Not required by D6 (which specifies 700 px, and passes).
**Invariant touched:** none.

**What breaks.** At a 420 px viewport the document `scrollWidth` is 565 px
against a 420 px client width. The strip is not the cause. The offenders are
`.roi-stage`, its `img` and its `canvas` (520 px wide at a 420 px viewport),
because `.roi-stage img` sets `max-width: 520px` with no `max-width: 100%`.

**Reproduce.** Open a measured inspection at a 420 px viewport; the page scrolls
sideways.

**Proposed fix (not applied).** In `app/static/app.css`, change
`.roi-stage img { max-width: 520px }` to
`max-width: min(520px, 100%)` and add `.roi-stage { max-width: 100% }`. The
canvas is sized from `img.clientWidth` by `roi.js` and follows automatically.

### Defect 3 — `inf` accepted as a declared PDP area
**Severity:** low.
**Invariant touched:** none.

**What breaks.** `float("inf")` parses and `area <= 0` is False, so an infinite
panel area is stored and rendered as `inf cm²`. (`NaN` also parses, but SQLite
stores it as NULL and it renders as `—`, so it is harmless.)

**Reproduce.** Upload with `declared_pdp_area_cm2 = inf`.

**Proposed fix (not applied).** In `app/main.py`, after `float()`, add
`if not math.isfinite(area): return again("Declared PDP area must be a finite number, in cm2.")`.

### Defect 4 — inspection-ID allocation is read-then-write
**Severity:** low. **Not reproduced.**
**Invariant touched:** none.

**What breaks.** `service._next_inspection_id()` does `SELECT COUNT(*)` then
`SELECT 1 … WHERE inspection_id=?`, and the `INSERT` happens afterwards on the
same connection without an explicit transaction spanning both. Two requests
that interleave between the read and the write would compute the same candidate;
the `UNIQUE` constraint would then turn the loser into an
`sqlite3.IntegrityError` and a 500.

**Reproduce.** Not reproduced. 40 concurrent uploads produced 40 distinct IDs
and zero errors, twice. Recorded because the race is visible in the code, not
because it was observed.

**Proposed fix (not applied).** Wrap allocation and insert in a single
`BEGIN IMMEDIATE` transaction, or catch `IntegrityError` around the insert and
retry the allocation a bounded number of times.

---

## G3. Notes (not defects)

1. **B6's first probe was wrong, not the app.** My substring test flagged
   "exception" in the measured panel. It is `lm_legal_model`'s own
   `CharacterWidthCheck` disclosure — *"…with **exceptions** for certain glyphs…
   Neither the fraction nor the **exception** list has been read from a primary
   source. NOT IMPLEMENTED, NOT ESTIMATED, NOT CLAIMED."* — printed in the
   capture manifest. That is the legal layer being honest, not an error state.
2. **C7 is a PASS with a caveat**, recorded as Defect 4 above rather than hidden
   in a table cell.
3. **Demo timing:** a 20.8 MP measurement takes **8.6 s**. The route is a sync
   handler so other requests are not blocked, but the operator waits. If the
   demo image is large, this is 8.6 s of silence on stage with no progress
   indication (and a progress indicator is not available — invariant 4).
   Recommend demoing with a smaller capture, or narrating over it.
4. **`EXTRACT` is `done` at "0 of 6 read" by design.** Extraction ran and
   truthfully reported reading nothing. Marking it `pending` would hide that the
   step happened. Flagging it here because it is the one stage state a reviewer
   might read as "faking progress"; it is the opposite.
5. **B5 re-runs need a neutral scale-artifact description.** Operator-typed text
   is echoed verbatim into the manifest, the PDF and the DOCX. An artifact
   described as e.g. "chessboard target, 2.00 mm pitch" puts the characters
   `2.0` into the artifacts legitimately. This pass used a digit-free
   description so the grep tested leakage rather than operator input. A future
   run that skips this will get a false positive.
6. **AUDIT §2.3 is live in the UI and unaddressed.** The verdict line carries U
   at `max(h, TL)`; the budget line carries U at the 1 mm reference. On the
   near-threshold specimen the panel prints `1.00 mm ± 0.17 mm` where the
   underlying U is `0.16638`. Both round to `0.17`. This is correct behaviour
   and was not changed, but it is on a screen a judge can point at — H6's second
   rehearsed answer exists for exactly this.
7. **No supervisor-only route exists.** The role rule is supervisor-*or*-owner
   for both determination and measurement, set in chunk 4. C9 was assessed
   against that design, not against a route that does not exist.
8. **Verification tooling is not a project dependency.** `playwright` was
   installed in this session to check rendered widths and computed colours in a
   real browser. It is **not** in `requirements.txt` and the app does not use
   it.

---

## G4. Cannot fix in time (> 1 hour)

Nothing found in this pass falls here. All four defects are small, local edits
to `app/` — the largest (Defect 1) is three changes in three files and would
need re-running section A plus `test_webapp.py`.

The genuinely unfinished items are the ones the project already knows about and
that no code change can close before the 15th:

- **Nothing has met a camera.** The px/mm factor is operator-entered from a
  scale session the rig has not run. Unchanged by chunks 4–6 and not closable
  by code.
- **The Gazette read (job 1) has not happened**, so sub-clause letters stay
  unprinted. F6 confirms the machinery is correct and waiting.
- **The ROI-boundary term (AUDIT §2.1) is still unbudgeted.** It is disclosed on
  screen, in the manifest and in the PDF, which is the decision the audit asked
  for; deriving a real term is not a three-day job.
- **`PLANARITY` / `NO_REDUNDANCY` cannot fire** on this path — no fiducials are
  passed. Nothing in the UI claims them.
- **The browser drag interaction is still not automatically tested.** Its
  coordinate conversion is verified by code inspection and server-side by the
  stored `roi_box` matching the real image size; the drag itself needs a human
  or a browser-driving test.

---

## Self-test counts at the end of the pass

```
legal model self-test:  81 checks, 0 failed
capture self-test:     114 checks, 0 failed
declarations self-test: 39 checks, 0 failed
extract self-test:      34 checks, 0 failed
report self-test:       26 checks, 0 failed
integration:            27 checks, 0 failed
webapp self-test:      175 checks, 0 failed

naive_vs_calibrated.py  md5 f3a14d36b82dceda0cae784d850878c5
                        (identical to a pristine pre-chunk-4 run)
```

**Totals: A 3/3 · B 9/9 · C 9 PASS 1 FAIL · D 7/7 · E 5/5 · F 6/6.**
One failing item (C3), four recorded defects, none fixed.
