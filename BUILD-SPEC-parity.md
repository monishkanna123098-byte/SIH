# SIH26034 — parity build spec

**Written 2026-09-12. Internal round 2026-09-15, three days.**

The goal of this build is NOT to be better than the median submission at the
things the median submission does. It is to be *indistinguishable* from it on
those things, so that the one place we are not comparable is the only place
anyone looks.

---

## 0. The one-line strategy

> Anyone can flag a violation. We built the one that survives being challenged.

Every decision below serves that sentence. If a feature does not either (a)
reach parity so we are not dismissed, or (b) make the defensibility claim
visible, it is not in this build.

---

## 1. Two surfaces, one story — the architecture call

**Do not deploy the Python engine behind the web app.** Three days is not enough
to stand up a FastAPI service, host it, handle image upload latency, and debug
it, while the camera path is *also* unbuilt.

| Surface | What runs there | Who operates it in the demo |
|---|---|---|
| **Web app** (Lovable) | Declaration extraction, Rule 6 presence checks, report, history, dashboard, auth | Operator on a laptop, projected |
| **Rig + Python** (local) | Height measurement, uncertainty, refusal, legal threshold resolution | Second operator at the camera stand |

They are narrated as one system. The handoff is spoken, not wired:
*"The app has flagged that a height check is required. That goes to the
instrument."* A judge does not care that it is two processes. A judge cares
enormously if the deployed one 502s on stage.

**If, and only if, the app is finished and stable by end of Day 2**, wire the
engine in behind a local endpoint. Not before.

---

## 2. Parity scope — mapped to the PS's own ten requirements

Build exactly these. The PS numbering is kept so the mapping is checkable.

| # | PS Key Functional Requirement | Build | Notes |
|---|---|---|---|
| 1 | Image upload and product scanning | **Yes** | Drag-drop + camera capture on mobile |
| 2 | Extraction of declarations + detection of mandatory declarations | **Yes** | Vision LLM → structured JSON. See §3 |
| 3 | Font size and readability analysis | **Yes — the instrument** | This is ours. See §5 |
| 4 | Detection of missing/misleading/non-standard declarations | **Yes** | Presence + format checks, §3 |
| 5 | Compliance/non-compliance reports | **Yes** | On-screen + PDF |
| 6 | Photographs and supporting evidence | **Yes** | Store the source image with the record |
| 7 | Repository of scanned products and history | **Yes** | Table + search |
| 8 | Role-based access and authentication | **Yes, thin** | Two roles only. See §4 |
| 9 | Dashboard for enforcement officials | **Yes, thin** | Four counters and a recent-scans list |
| 10 | Export to PDF and editable formats | **Yes** | PDF + **DOCX**. See §3a — CSV was the wrong read |

---

## 3. The declaration checks — Rule 6(1)

Six mandatory declarations. Presence first, format second. **Every field on
screen shows how it was obtained.** This is not decoration; it is the whole
differentiator rendered in UI.

| Declaration | Check | Source label shown in UI |
|---|---|---|
| Name and address of manufacturer/packer/importer | present / absent | `EXTRACTED — OCR, unverified` |
| Common or generic name of commodity | present / absent | `EXTRACTED — OCR, unverified` |
| Net quantity | present / absent + unit is a legal unit | `EXTRACTED — OCR, unverified` |
| Retail sale price | present + carries an inclusive-of-taxes statement | `EXTRACTED — OCR, unverified` |
| Month and year of manufacture/packing/import | present + parses as a date | `EXTRACTED — OCR, unverified` |
| Consumer care details | present / absent | `EXTRACTED — OCR, unverified` |
| **Character height (Rule 7(2))** | **measured** | **`MEASURED — U(k=2), scale-referenced`** |

That last row looking different from the six above it is the product. Do not
let a designer normalise it.

**Three states per row, never two:** `PASS` / `FAIL` / `CANNOT DETERMINE`.
A field the OCR could not read is not a violation, and saying so is the same
discipline the instrument already applies.

---

## 3a. Report layout — patterns worth adopting, and how to beat them

Derived from reading competing repos' READMEs on 12 Sep. **Ideas only — no
code, no text, nothing lifted.** These are teams competing on the same PS and
this project's entire argument is provenance; shipping their work would end
that argument faster than losing would.

**DOCX, not CSV.** This spec said CSV for "editable formats" and that was
wrong. The PS says *"PDF and editable formats"*; DOCX is the literal reading
and at least one competing entry does it. Use `python-docx`.

**Three source tiers on the report, not two.** A competing entry separates
*AI-assisted findings* from *officer determination* — two tiers, and it is good.
We have a third that nobody else can populate:

| tier | applies to | label on the report |
|---|---|---|
| `EXTRACTED` | the six Rule 6(1) declarations | AI-assisted, unverified |
| `MEASURED` | character height | scale-referenced, U(k=2) stated |
| `DETERMINED` | the officer's final call | officer determination |

The middle row existing at all is the differentiator, printed.

**The explainability chain.** A competing entry runs
`Checked → Detected → Expected → Why Flagged → Legal Citation` per finding.
Adopt the shape and add a column nobody else can fill:
`→ Source tier of the threshold`. On the disputed 50–100 cm² bracket that
column reads *"unverified — this instrument refuses to rule"*.

**Bounding boxes on the evidence image.** Cosmetic for others. For us it is
load-bearing: **draw the ROI box** so the region is a visible declared input
rather than a hidden one. This is the 12 Sep ROI-sensitivity finding made
visible instead of buried.

**Pre-flight quality checks.** Competing entries advertise blur / contrast /
orientation checks as features. We already have `CONTRAST`, `CLIPPED` and
`ILLUMINATION_GRADIENT` as fully self-tested refusal gates. Surface them.
Zero build cost, and it is a feature others market as a differentiator.

**Hash the report.** `_self_hash()` already exists. A SHA-256 on the emitted
PDF is a few lines and fits the defensibility story exactly.

---

## 4. Data model — minimum that supports §2

```
users        id, email, role            role ∈ {officer, supervisor}
scans        id, user_id, created_at, image_url, product_name,
             declared_pdp_area_cm2, declared_category, status
findings     id, scan_id, rule_ref, declaration, verdict, source, detail
                verdict ∈ {PASS, FAIL, CANNOT_DETERMINE}
                source  ∈ {EXTRACTED, MEASURED}
measurements id, scan_id, height_mm, u_mm, threshold_mm, band,
             convention, refusal_code, manifest_text
```

`measurements` is a separate table from `findings` on purpose. A measurement
carries things a presence-check never does — an uncertainty, a convention, a
capture manifest — and collapsing them into one row is how the distinction
gets lost. For the internal round these rows are entered by the operator from
the instrument's output; the schema does not change when they are wired.

---

## 5. The height module — contract, not integration

The app does not call the engine on Day 1. It accepts what the engine produced.

```
POST /scans/:id/measurement
{
  "height_mm":    1.4019,        // null on refusal
  "u_mm":         0.1732,        // null on refusal
  "threshold_mm": 1.0,           // null if the legal layer refused
  "band":         "COMPLIANT" | "DEFICIENT" |
                  "REQUIRES_PHYSICAL_VERIFICATION",
  "refusal_code": null | "MEASURAND_UNDEFINED" | "THRESHOLD_DISPUTED" | ...,
  "convention":   "50% ink-to-substrate crossing",
  "manifest":     "<the capture manifest lines, verbatim>"
}
```

Everything in that payload already exists in `Verdict` and
`manifest_lines()`. Nothing new is needed in the engine.

**Refusal is a UI state, not an error state.** This is the single easiest way
to lose the internal round. Risk 4 in the team brief says a high refusal rate
reads as "it does not work" to non-specialists. A red error toast confirms
that reading. A calm panel does the opposite:

> **INDETERMINATE — physical verification required**
> Measured 1.03 mm ± 0.17 mm (k=2) against a 1.00 mm requirement.
> The uncertainty band straddles the threshold, so this instrument
> will not issue a verdict.
> *Next: refer for physical verification.*

Same behaviour. Opposite impression. Design it once, use it for every refusal
code including `THRESHOLD_DISPUTED`.

---

## 6. The comparison demo — build this first, it is the cheapest win

A naive pixel-based height estimator, ~20 lines, deliberately built the way an
OCR-only system implicitly works: character bounding box height in pixels
divided by an assumed DPI.

Photograph one label at two camera distances. Run both.

| | naive estimator | this instrument |
|---|---|---|
| shot A | reports a confident number | h ± U, or refuses |
| shot B (moved) | reports a **different** confident number | **same** answer, or refuses |

That is the entire argument about scale references, shown in thirty seconds
without a slide and without naming a competitor. It needs no new metrology and
no rig calibration — only that the same label is photographed twice.

**Build it Day 1.** It is the highest value-per-hour item in this document and
it is the one beat that survives the rig failing.

---

## 7. Do NOT build

- A deployed Python service (see §1)
- Rule 7(3) width checking — blocked on statutory transcription, not on code
- E-commerce listing scraping — real, cheap, and dilutes the story. Not now
- Placement / principal-display-panel geometry — genuinely ours, genuinely not
  a three-day job
- Blockchain, anything. No
- Any new document. This project's own audit found its failure mode is prose
  claims drifting from code. Do not add prose

---

## 8. Ownership — the actual blocker

The §13 table has six slots and all six still read `_____`. Nothing in this
spec happens without names in them. Minimum:

| Job | Owner |
|---|---|
| Web app — screens, auth, history, dashboard | `_____` |
| Web app — extraction + Rule 6 checks + PDF | `_____` |
| Rig: camera path, `demo_script.py`, first real photograph | `_____` |
| The comparison demo (§6) | `_____` |
| Gazette read (job 1, still not done) | `_____` |
| Admin: portal deadline (20 vs 30 Sep, still unresolved), registration | `_____` |

The last two are the ones that fail silently and the ones that can disqualify.
They have been unowned since 5 September.

---

## 9. What "done" looks like on 15 September

- A judge photographs a packet they brought. The app returns six declaration
  findings, each labelled with how it was obtained.
- One row says a height check is required. The packet goes to the rig.
- The rig returns a height, an uncertainty, and either a verdict or a refusal —
  and the refusal, if it comes, is narrated as the point rather than apologised
  for.
- A PDF comes out with both, and with the threshold's source tier printed on it.
- Somewhere in there, the two-distance comparison runs.

If the rig fails entirely: the app still stands alone at parity, and §6 still
runs off two saved photographs. Build in that order.
