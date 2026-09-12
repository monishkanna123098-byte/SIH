# CHUNK 4 — the web application

Paste this whole file as your first message to Claude Code.

---

## Before you write any code

1. Read `CLAUDE.md` in full. The eight invariants in it are not style
   preferences; each one costs a feature on purpose.
2. Read `BUILD-SPEC-parity.md` (§2 requirement map, §3a report patterns,
   §4 data model) and `AUDIT-2026-09-12.md` §4 for what is genuinely unfinished.
3. Run every self-test and confirm these exact counts:

```bash
for f in lm_legal_model lm_capture lm_declarations lm_extract lm_report; do
  python3 $f.py | grep -i "self-test"
done
python3 test_integration.py | tail -3
```

Expected: **81 / 114 / 39 / 34 / 26**, and **27** integration checks, all
`0 failed`. **If any count differs, stop and report it.** Do not build on a
codebase whose documented state and actual state disagree — that is this
project's recurring failure mode and it has been caught three times.

---

## What you are building

A single local FastAPI application that imports the existing modules directly.
**Not** a separate frontend and backend. No HTTP between layers, no CORS, no
hosting, no build step. "Web application" in the problem statement is satisfied
by a browser pointed at `localhost:8000`.

This must run on a laptop with no internet on 15 September. Every dependency is
pip-installable and nothing is fetched at runtime — no CDN fonts, no CDN CSS,
no icon library.

### Stack — locked, do not substitute

| Concern | Choice | Why it is fixed |
|---|---|---|
| Server | FastAPI + uvicorn | already the team's assumption |
| Templates | Jinja2, server-rendered | no build step, works offline |
| DB | stdlib `sqlite3` | zero install, file-backed, inspectable |
| Uploads | `python-multipart` | FastAPI requirement for forms |
| Documents | existing `lm_report` | already written and tested |
| CSS | one hand-written `static/app.css` | no Tailwind, no CDN |
| JS | vanilla, only where required | no framework, no npm |

If any dependency will not install, **stop and report**. Do not work around it
with a CDN.

---

## File layout

```
app/
  main.py            FastAPI app, routes
  db.py              sqlite3 helpers, schema, migrations
  auth.py            session cookie, two roles
  service.py         the only module that touches lm_* — see below
  templates/
    base.html  login.html  upload.html  results.html
    history.html  dashboard.html
  static/
    app.css
data/
  inspections.db     created on first run
  uploads/           stored evidence images
  reports/           generated PDF/DOCX
run.sh               uvicorn app.main:app --reload
```

**`service.py` is the only file permitted to import `lm_*`.** Routes call
`service`, `service` calls the engines. This keeps the invariants enforceable in
one reviewable file instead of scattered through request handlers.

---

## Database schema

Follow BUILD-SPEC §4. `findings` and `measurements` stay **separate tables** —
a measurement carries an uncertainty, a convention and a capture manifest that a
presence-check never has, and collapsing them is how the distinction gets lost.

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('officer','supervisor'))
);
CREATE TABLE scans (
  id INTEGER PRIMARY KEY, inspection_id TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL, image_path TEXT,
  product_name TEXT NOT NULL,
  declared_category TEXT, declared_pdp_area_cm2 REAL,
  coverage_panels TEXT, coverage_examined INTEGER NOT NULL DEFAULT 0,
  coverage_operator_id TEXT, coverage_note TEXT,
  headline TEXT
);
CREATE TABLE findings (
  id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL REFERENCES scans(id),
  declaration_key TEXT NOT NULL, verdict TEXT NOT NULL
    CHECK(verdict IN ('PASS','FAIL','CANNOT_DETERMINE')),
  source_tier TEXT NOT NULL CHECK(source_tier IN ('EXTRACTED','MEASURED','DETERMINED')),
  detected TEXT, why TEXT, citation TEXT, extractor TEXT,
  verbatim_confirmed INTEGER
);
CREATE TABLE measurements (
  id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL REFERENCES scans(id),
  band TEXT NOT NULL, height_mm REAL, u_mm REAL, threshold_mm REAL,
  convention TEXT, refusal_code TEXT, refusal_detail TEXT,
  threshold_source_tier TEXT, manifest TEXT, roi_box TEXT
);
CREATE TABLE determinations (
  id INTEGER PRIMARY KEY, scan_id INTEGER NOT NULL REFERENCES scans(id),
  officer_id TEXT NOT NULL, verdict TEXT NOT NULL, note TEXT, determined_on TEXT
);
```

The `CHECK` constraints on `verdict` and `source_tier` are deliberate: they make
invariants 1 and 3 enforced by the database, not just by convention. Keep them.

**Leave `measurements` unpopulated in this chunk.** Chunk 5 fills it. Build the
results page so an absent measurement renders cleanly — `lm_report` already
handles `measurement=None`.

---

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/login`, `/logout` | session cookie, two roles |
| GET | `/` | redirect to `/upload` |
| GET/POST | `/upload` | new inspection |
| GET | `/scan/{inspection_id}` | results, three tiers |
| POST | `/scan/{id}/determination` | officer's call (supervisor or owner) |
| GET | `/scan/{id}/report.pdf` · `/report.docx` | via `lm_report` |
| GET | `/history` | list + search |
| GET | `/dashboard` | counts only |

---

## The upload screen — this is the load-bearing one

Three groups. Get the third right or invariant 2 is broken.

**1. Product** — product name (required), image upload (optional in this chunk),
declared category (`general` / `blown_formed_moulded_embossed_perforated`),
declared PDP area in cm².

Label the last two **"operator declared"** in the UI. Neither is discoverable
from an image; both are claims the officer is making.

**2. Declarations** — six text inputs, keys exactly:

```
name_and_address  common_or_generic_name  net_quantity
month_and_year    retail_sale_price       consumer_care
```

Blank means "not found". Do not use a placeholder that implies absence.

**3. Coverage declaration — the part that unlocks absence claims**

```
Panels captured:    [ ] front  [ ] back  [ ] top  [ ] bottom  [ ] side
[ ] I have examined the physical package itself, not only these images.
Operator ID: [________]
Note: [________]
```

Map to `lm_extract.Coverage(panels=..., operator_examined_package=...,
operator_id=..., note=...)`.

Put this immediately above the submit button, with this text beneath the
checkbox, verbatim:

> Ticking this means a person had the package in hand and looked. It is what
> allows a missing declaration to be recorded as a violation rather than as
> undetermined. Leave it unticked if you are working from images alone.

**Why it matters:** `Coverage.can_assert_absence()` requires the checkbox **and**
a non-empty operator ID. Without both, a blank declaration becomes
`CANNOT_DETERMINE`, not `FAIL`. A photo-only upload that produces a FAIL is a
defect — there is a self-test in `lm_extract` covering this and you must not
route around it.

Extraction in this chunk is `manual_extract(values, coverage, operator_id)`.
Vision is out of scope here; `vision_extract` exists and takes an injected
callable, wire it later.

---

## The results screen — where the product either shows or disappears

Three sections that must **not** look alike. Follow the sample PDF in the repo
(`inspection-record-sample.pdf`) — open it and match its hierarchy.

**Section 1 — Mandatory declarations, Rule 6(1) · `[tier: EXTRACTED]`**
Plain table, light grey header. Columns: Verdict · Declaration · Detected ·
Why · Citation. One row per finding, from `Finding.chain()`.

Verdict styling: `PASS` neutral · `FAIL` muted red background (`#F6E4E4`) ·
`CANNOT_DETERMINE` neutral with a short reason. **No green ticks, no red
crosses, no traffic lights.** A two-colour icon set silently collapses three
states into two.

**Section 2 — Character height, Rule 7(2) · `[tier: MEASURED]`**
Visually distinct: cream background (`#F3F0E7`), heavy navy border
(`#0A1628`, ~1.5px). Key/value rows, not the same table as section 1.

In this chunk it shows: *"Not yet measured — this inspection has no height
measurement."* Do not hide the section; its presence is the point.

**Section 3 — Officer determination · `[tier: DETERMINED]`**
A form, empty until filled. Free-text verdict plus a note.

**Below all three**, print the three tier explanations from
`lm_report.TIER_NOTE`, the coverage description, and the extraction provenance
from `extraction_provenance_lines()`.

**Header:** the headline from `summarise()` plus three counts. **No
percentage, no score, no grade, no progress ring.** Invariant 4. The
`summarise()` function deliberately has no score field and there is a test
asserting so.

---

## History and dashboard

**History** — table of scans: date, inspection ID, product, officer, headline,
counts. Search across product name, inspection ID and officer. Sort newest
first.

**Dashboard** — four counters (total inspections · with at least one FAIL ·
with at least one CANNOT_DETERMINE · clean), plus the ten most recent scans.

Counters only. No percentages, no charts, no compliance rate. If a chart feels
missing, that is the invariant working.

---

## Visual language

```css
--navy:#0A1628  --ink:#1a1a1a  --grey:#555  --rule:#BBB
--paper:#fff    --measured-bg:#F3F0E7  --fail-bg:#F6E4E4  --head-bg:#E8ECF1
```

Serif headings (Georgia / `'Times New Roman'` / serif), system sans for body.
Real tables with visible rules. Generous whitespace. No gradients, no shadows,
no rounded-corner cards, no animation, no icon font, no emoji.

**Do not use the State Emblem of India, the national flag, or any
"Government of India" / ministry attribution.** A competing entry does; use of
the emblem is restricted under the State Emblem of India (Prohibition of
Improper Use) Act, 2005. A compliance project with a compliance problem on its
own landing page is not a risk worth taking.

---

## Do NOT build

- Any binary compliant/non-compliant flag, anywhere, at any layer
- A compliance score, percentage, grade or rating
- Penalty computation or rupee amounts — outside the problem statement
- Barcode scanning, e-commerce scraping, multilingual OCR — scope creep
- An ORM, a migration framework, a task queue, Docker, npm, Tailwind
- Any edit to `lm_metrology_v7.py`, `lm_capture.py` or `lm_legal_model.py`.
  If one needs changing, **stop and say so**

---

## Definition of done

1. `./run.sh` starts; `localhost:8000` serves login.
2. Two seeded users, one per role.
3. A full inspection can be created, viewed, and exported to PDF and DOCX, and
   the exported PDF matches the sample's structure.
4. **A photo-only upload (checkbox unticked) with all six fields blank produces
   six `CANNOT_DETERMINE` and zero `FAIL`.** Verify this yourself before
   reporting done.
5. **The same upload with the checkbox ticked and an operator ID produces six
   `FAIL`.** Verify this too. These two cases are the invariant made visible.
6. Every self-test still passes at its original count.
7. The app runs with networking disabled.

Report what you built, which of the seven you verified, and anything you could
not do. **Then stop** — do not start chunk 5.

---

## If you disagree

Some of this is deliberately harder than the obvious alternative. Three states
are harder than two. Counts are less impressive than a percentage. A cream box
that does not match the table above it looks unfinished.

If something here is wrong, or will not work, **say so and stop** rather than
building it anyway or quietly simplifying it. But do not resolve an invariant
by implementing the simpler version — those are design decisions made outside
this session, and the reasons are in `CLAUDE.md`.
