# SIH26034 — Legal Metrology Letter-Height Compliance
## Team brief, build plan and demo script

**Written 2026-09-05 (Saturday). Internal round: postponed by the college to 2026-09-15.**

> **Corrected 2026-09-06, per redteam section 5: this table was stale in three of six rows,
> all understating, and it is the first thing an evaluator reads with no other context —
> which has already produced a 5.5/10 once. Read the version/hash and check counts off a
> running program, never off this row.**

> **Corrected again 2026-09-09: the version pin below goes stale every time the file is
> touched, which is often — this table gave 7.3 when the real file had already moved to
> 7.9. Read VERSION off the running program; treat any version number written in a
> document, including this one, as already possibly out of date.**

| Item | Status |
|---|---|
| Problem statement | SIH26034, Ministry of Consumer Affairs, Food & Public Distribution. Confirmed genuine, one of 226 in the 2026 list |
| Core software | Built, `lm_metrology_v7.py`, at least through VERSION 7.9 (legal-model integration complete, all 3 call sites), twenty-plus rounds of adversarial review |
| Live camera capture | Written, `lm_capture.py`, self-tests at 114 checks (0 failed) — the capture functions (`open_camera`, `run_chessboard_scale_session`, `capture_specimen`) exist and their logic is verified against synthetic data; **no camera has ever actually been attached.** That's the real remaining gap now — not missing glue, an untested one |
| Statutory table | Rule number resolved to primary-source confidence (Rule 7(2), height; 7(3) is width) via an actual Gazette-notification compilation, not a summary. The full current Table-I is transcribed and corroborated by a third independent source. One bracket (50–100cm², ordinary) remains `disputed=True` pending the Gazette + corrigendum itself |
| Uncertainty budget | Complete; five of eight terms entirely *modelled*, three height-scaled (`relative=True`). Not citeable until the stage-micrometer run |
| Physical rig | Status as of last check: not assembled — confirm current status before the 15th |

Read sections 3 and 4 before writing any slide. Everything in this document marked
"unverified" must not appear on a slide or in a rehearsed answer.

---

## 1. The problem statement

The Ministry wants software that inspects a packaged commodity — the product, its
images, and its label — and checks whether the label complies with the **Legal
Metrology (Packaged Commodities) Rules, 2011**.

Those Rules require a set of declarations on the principal display panel: name and
address of the manufacturer or packer, common or generic name of the commodity, net
quantity, month and year of manufacture or packing, retail sale price (MRP,
inclusive of all taxes), and consumer care details.

Crucially, the Rules do not only require that these declarations *exist*. They
specify **how large the characters must be, in millimetres.** A declaration that is
present but printed too small is non-compliant.

## 2. Why this is not an OCR problem — the core insight

Most of SIH26034 is a text problem. "Is the MRP declared?" is answered by reading
the label. Any team can do that with OCR plus a checklist, and at least one already
has (see section 12).

One requirement is not a text problem at all. **The statute is written in
millimetres. A photograph contains pixels.** Converting pixels to millimetres
requires a *physical scale reference* — a calibrated rig, a fiducial marker of known
size, or a reference artifact in the frame.

Say it this way, and only this way: **OCR can locate text in pixels; pixel coordinates
do not become millimetres without a physical scale, and nothing in an OCR pipeline
supplies one.** That sentence is true and defensible. The stronger-sounding version —
"no operation in the text domain produces a length" — is false, and any judge who has
ever recovered a scale factor from a known-width barcode or a standard-size cap will
say so in one breath. What the competing architectures lack is a **scale reference**,
not a capability. Overclaiming here trades a solid point for a refutable one.

So the single requirement that is genuinely hard to check is the one that every
competing architecture structurally cannot reach. That is our project.

### 2.1 Where our claim sits, and where it does not

Added 2026-09-05, from the corpus audits. Compliance checking under these Rules decomposes
into five layers, and being explicit about which one we own is what keeps the pitch
honest: **applicability** (is this a retail package under these Rules at all — industrial,
medical device, exempt), **required declarations** (which items must appear), **location
and layout** (panel membership, placement, legibility), **dimensional compliance** (panel
area → height threshold → width → measurement → uncertainty), and **evidence**
(notification, effective date, image, measurement, verdict, operator, timestamp).

Layers one to three are text and rule-book work, and a competent OCR-plus-checklist team
will do them. **Our claim is layer four, and layer four is the only one that needs a
physical scale reference.** Layer five is cheap for us and awkward for them, because an
audit record is only worth what the measurement inside it is worth.

Say that division out loud rather than implying we do everything. A team that names the
one layer it owns and owns it completely reads as more credible than one that gestures at
all five.

### 2.2 The dataset the problem statement gives us is the statute itself

The dataset link on the SIH26034 problem statement is the Ministry's Legal Metrology
page — notifications, amendments and rules. **It is not a corpus of labelled label
images, and there is no ground truth in it.**

This is worth understanding properly because it is a structural advantage, not a
grievance. Any team that reaches for a learned model has to bootstrap its own training
set and its own labels in four days, from photographs it takes itself, with no
independent verification of the heights it is training against. **A calibrated instrument
needs no training set at all** — it needs a scale reference, an uncertainty budget and a
decision rule, and all three are things we can show a judge.

The corollary is a discipline, not a boast: since the statute *is* the dataset, reading it
badly is the same class of failure as training on mislabelled data. Section 3 is where
that reading is recorded, and section 15 is where the parts we have not verified are kept
out of the presentation.

---

## 3. The legal model — READ THIS BEFORE ANY SLIDE

**Rewritten 2026-09-05 after two external audits of the DoCA corpus. The section it
replaced was built on a net-quantity-indexed model that is now believed wrong.** This is
still the weakest part of the project and still the only part that can make a correct
measurement produce a wrong verdict — but the failure mode has changed. It is no longer
"we do not know the shape of the table." It is "we have the table from a secondary
source and two of its cells are contested."

### 3.1 What we are reasonably confident about

- Character heights are specified **in millimetres**, not in points or as font sizes.
  Never say "font size" — say **letter height** or **character height**.
- **The table is indexed on PRINCIPAL DISPLAY PANEL AREA, not on declared net
  quantity.** This resolves a dispute that was open for six review rounds. It is the
  single most consequential change to the design, because it moves the index from
  something OCR could read off the label to something an operator must declare.
- **Five area brackets, two columns.** The columns are ordinary printed/applied
  characters versus **blown, formed, moulded, embossed or perforated** — the axis we
  already had. The thresholds rise with panel area across a range of roughly 1 mm to
  6 mm.
- **The 1 mm / 2 mm pair we have been building against is the smallest-panel row of
  that table**, applicable to panels of 50 cm² or less — about a 7 × 7 cm packet. It was
  never the whole rule, and treating it as the whole rule would give a confidently wrong
  verdict on every larger package.
- **Medical devices are carved out.** For medical-device packages the Medical Devices
  Rules 2017 govern the declarations and their height. The PCR height table does not
  apply. This is a hard branch, not an edge case.
- **A rule being notified is not the same as a rule being in force.** The 2022 unit-sale-
  price provision was deferred seven times across 2022 and 2023. So the applicable
  threshold is a function of the **inspection date**, and "why this threshold?" is
  answerable as an audit trail rather than as an assertion.
- **Some required information may lawfully be supplied by QR code** rather than printed
  on the panel. Absent-from-visible-print therefore does **not** imply a violation. This
  is a genuine false-positive guard and we should say so.

### 3.2 What is genuinely disputed — do not assert any of it

The disputes are now smaller and much more specific. Two are about single numbers.

1. **The 50–100 cm² ordinary cell: we cannot establish its value.** Note the wording, it is
   load-bearing. The audit reports the cell as 1.5 and separately reports that a corrigendum
   to the notification changed a value from 1.5 to 2.0. Our transcription shows that cell as
   the only 1.5 in the table, which invites the inference that the corrigendum is about this
   cell — but the inference is weaker than it looks and it fails in two ways. **(a)** If the
   quoted table predates its own corrigendum, this cell is really 2.0. **(b)** If the table
   already postdates it, the changed cell reads 2.0 somewhere else, the 1.5 the corrigendum
   describes sat in a different cell we transcribed as something else, and **this cell is
   fine as we hold it** — in which case we are blocking a sound cell and the wrong cell is
   the one we are not looking at. On top of that, the "only 1.5 in the table" step assumes
   our own transcription is complete, which is exactly what is in question.
   So **do not write or say "either 1.5 or 2.0"**: that states a candidate set, and the set
   is what we cannot establish. The code encodes this cell as `disputed` and **refuses to
   give a verdict** for packages that fall in it — as a conservative choice under an
   unresolved reading, not as a demonstrated conflict. It is a 33% swing on a very common
   package size either way, which is why it is first on the verification list.
   *(These two values appear here because this document is internal. They appear in the
   code only in `internal_note`, which nothing prints. They never appear on a slide, in the
   script, or in Q&A.)*
2. **The largest bracket is the only row where the two columns carry the same value.**
   Every other row has the formed column strictly greater. The column ratios run 2×, 2×,
   1.6×, 1.5×, 1× — consistent with the formed column capping out, so the value is
   probably real, but it is also exactly what a carried-down transcription error looks
   like. The code **warns** here rather than blocking, because a suspicion is not a
   documented conflict.
3. **Rule and sub-rule number.** Still open, and the new material made it worse rather
   than better: the two audits **contradict each other** on which amendment introduced
   the panel-area framework. Our own code comments still say `"r.9"`. **Say "the Rules"
   and "the minimum height table". Never a rule number, on any slide, in any answer.**
   The code now enforces the same rule on itself: no refusal message and no refusal report
   names a notification number, only the instrument. The number is printed when a threshold
   is actually applied — that is the audit trail for a verdict — and it is printed marked
   *(identifier unconfirmed)*, a marker that retires itself the moment someone promotes the
   table to `VERIFIED` by reading the Gazette.
4. **Whether letters and numerals are governed by one table or two.** The audits say
   one, covering numerals and letters together. We have **not** deleted the separate-axis
   design on that evidence, because it is a claim that something does *not* exist drawn
   from secondary material, which is the weakest possible warrant for removing a planned
   feature. The axis is absent from the data and documented as a decision in the code.

### 3.3 The verification job — highest priority, one person, one hour

The transcription job is done. What replaces it is smaller and sharper: **read the
Gazette PDF of the amendment that carries the height table, and its corrigendum, side by
side.** One cell above is blocked by the code and one is flagged; both are settled by the
same hour of reading.

Source must be **egazette.gov.in or the Ministry's own notification PDF**. Not a blog,
not a compliance consultancy, not `indiacode`, not a tax-news site — the current table
came from an aggregator and that is precisely why we are in this position. The
Ministry's consolidated "book with all amendments" is **stale**: the corpus runs to a
Third Amendment of May 2026 and the book predates the 2023–2026 changes.

Answer these in writing and screenshot the table:

1. What is the value in the 50–100 cm² ordinary cell in the Gazette text, and is that text
   before or after the corrigendum?
2. **Which cell does the corrigendum change**, what does it change it to, and what is its
   date? Do not assume the answer to the first half — that assumption is the whole problem.
3. Are the two columns really equal in the largest bracket?
4. Is there one table for letters and numerals, or two?
5. What is the notification number, the notification date, and the **commencement**
   date — three separate facts, all three recorded.
6. What rule and sub-rule number does the table sit under?

**What is no longer true:** it used to be the case that nothing downstream was correct
until this was done. The code now runs, adjudicates the brackets it can, and refuses the
one it cannot. That is the whole point of encoding the dispute rather than picking a
number. But **no threshold from this table may be presented as settled law** until item
1 is answered, and the `UNVERIFIED` confidence flag in the code exists to make that
impossible to forget.

---

## 4. The proposed solution

A measuring instrument for statutory character height: **architected for a traceable
scale, reporting a stated uncertainty, and disciplined enough to refuse when it cannot
decide.**

Read *architected for* literally. The scale path is built so that traceability **can**
be established — a fiducial of declared size, one scale factor carried explicitly
through to millimetres, and a budget term reserved for it. The missing piece is the
last link: a **certified** reference artifact. Until one is measured the chain
terminates in an uncertified glass stage micrometer, so the claim that survives
cross-examination is *"traceable by construction, not yet traceable in fact."*

Do **not** fix this by deleting the word *traceable*. Strike it and what remains is "a
camera that measures letters" — which is exactly the competitor's position, and
concedes the one thing that makes this project different. State the architecture, then
state the open link, in that order.

### Layer 1 — the rule model

**Rewritten 2026-09-05. This layer now lives in its own module, `lm_legal_model.py`,
rather than as constants inside the measurement engine.** That separation is the main
structural change the audits produced, and the reason for it is that the two layers fail
differently: a measurement fails by being imprecise, a legal lookup fails by being
confidently wrong. The second failure is worse and much harder to see, so it gets its own
file, its own vocabulary of refusals, and its own tests.

Section 8 records what the code actually contains. If these two sections ever disagree,
section 8 is the fact and this one is the design intent.

The lookup takes four declared inputs and returns either a threshold or a reason it
cannot give one:

- **Commodity class** → which *instrument* governs. General commodities go to the PCR
  height table; **medical devices go to the Medical Devices Rules 2017**, which this tool
  does not implement and says so. An undeclared class refuses rather than defaulting to
  PCR.
- **Package category** → which *column*. Ordinary printed/applied versus blown/formed/
  moulded/embossed/perforated. An undeclared category refuses; the formed category also
  refuses downstream on measurand grounds — see section 7, and note carefully that these
  are two different refusals.
- **Principal display panel area** → which *row*. Five brackets, exclusive lower bound
  and inclusive upper bound. An undeclared area refuses, because the threshold ranges
  1 mm to 6 mm across the table and there is nothing sensible to default to.
- **Inspection date** → whether the rule was *in force*. An unread commencement date
  refuses; it is never treated as "presumably yes".

Every one of these is a **declared operator input, never an inference.** The software does
not guess at law. Panel area in particular is declared rather than measured: determining
it from the image needs panel segmentation, shape classification and the fractional
formulae the Rules give for cylindrical and irregular containers, which is a separate
project with its own uncertainty. Declaring it is not a limitation to apologise for — it
is the same discipline as declaring the fiducial length.

**Two things are named and deliberately not implemented**, because a system claiming to
check the statutory dimensional requirement must not silently mean "the half we built":

- **A minimum character width relative to height.** Reported to exist, with exceptions
  for certain glyphs. Those per-glyph exceptions are the problem: applying the rule
  requires knowing *which character* you are looking at, so width makes OCR load-bearing
  *inside* the dimensional check rather than beside it. Different architecture, a new
  uncertainty term, its own validation set. Not implemented, not estimated, not claimed.
- **The letters-versus-numerals axis.** See 3.2 item 4. Absent from the data, present as
  a documented decision in the code, and one field away from existing if a primary source
  turns out to carry a second table.

### Layer 1b — the legal-uncertainty gate

**New, and no competing team will have it.** The measurement engine already declines when
the *measurement* is indeterminate. This applies the identical idea to the *law*: a
verdict is blocked by any unresolved legal input, because a threshold you had to guess at
makes the uncertainty budget behind it irrelevant.

The blockers are separate codes rather than one generic refusal, because "we declined" is
useless to an operator while "you did not declare the panel area" is actionable:
undeclared or unrecognised commodity class, a different instrument governing, undeclared
or unrecognised package category, undeclared or implausible panel area, an area that fell
through every bracket, an unresolved rule version, and a **disputed threshold**. Check
order is fixed and tested: a misspelt category must report *category unknown*, not a
downstream complaint about panel area.

The disputed-threshold blocker is worth its own sentence, because it is the one that
turns a sourcing embarrassment into a feature. Two specimens with identical print, one
declared at 40 cm² and one at 75 cm², produce a verdict and a refusal respectively — and
the refusal reads *"we cannot establish the statutory minimum for this bracket. UNRESOLVED:
a corrigendum to the amendment that carries this height table is reported to alter one value
in it, nobody here has read that corrigendum at source, and we cannot establish whether this
bracket is the cell it alters."* That is a system that declines because **the law** is
unresolved, which is a strictly stronger claim than declining because the pixels were noisy.

Three things about that string are deliberate, and each one was a defect first.

It **names no candidate value**. An earlier draft said the threshold "is either 1.5 mm or
2.0 mm", which sounds more informative and is in fact an overclaim: it asserts a candidate
set we cannot establish. See §3.2.

It **names no notification number**. The identifier belongs to the audit trail of a
threshold the tool *applied*, and there is no applied threshold in a refusal — nothing to
justify, so the citation is unbacked. It is also the wrong number to be confident about:
our two audits of the ministry page do not agree on which amendment carries this table
(§3.2 item 3). A refusal therefore names the instrument, whose title nobody disputes. When
a threshold *is* applied the number is printed, marked *(identifier unconfirmed)* until
someone has read the Gazette.

It says **"is reported to alter"**, not "alters". We have a secondary report of a
corrigendum, not a corrigendum.

One rule follows for the demo, the same one that applies to the version hash: **read the
refusal off the running program, not off this document.** These strings have been rewritten
three times in two days, always in the direction of claiming less, and a quote that no
longer matches the code is exactly the kind of small false claim this project exists to
avoid making.

### Layer 2 — the measurement

1. Rectify the region of interest to a known millimetres-per-pixel scale.
2. Locate each character's top and bottom edges to sub-pixel precision at a
   **declared 50%-of-ink-to-substrate intensity criterion**.
3. Measure per-glyph vertical extent on a declared **extreme-ink-extent convention** —
   *not* a cap-height convention, which would require knowing the typeface and which this
   step wrongly claimed until 2026-09-06 — combining per-column extremes with the
   `max_supported` rule. **§7.1a is the definition of record**; if this line and §7.1a ever
   disagree again, §7.1a wins and this one is the bug.
4. Report the **smallest required character of the governing glyph class** as the
   regulated quantity. *Designed, not shipped:* with the glyph-class axis absent, the
   code reports the smallest character it succeeded in **measuring** — which is not the
   same set as the smallest character the statute **requires**. Section 8 records this
   as a coupling defect, because the glyphs hardest to measure are also the ones most
   likely to set the minimum.
5. Accumulate an uncertainty budget across every stage.

### Layer 3 — the verdict, per JCGM 106:2012

The statutory limit is **exact**; only the measurement carries uncertainty. This is
the standard's own framework for acceptance decisions under measurement uncertainty,
and it is exactly on point.

| Condition | Verdict |
|---|---|
| `h − U ≥ TL` | **COMPLIANT** |
| `h + U < TL` | **DEFICIENT** |
| otherwise | **REQUIRES_PHYSICAL_VERIFICATION** |

Note carefully: the guard band applies to the **measurement only**. Writing
`h + U < TL − U` double-counts it, which is a mistake an earlier revision of our own
plan made and had to correct.

### The refusal layer

Above the verdict sits a set of capture checks that abort the measurement rather than
degrade it: non-planar presentation, insufficient geometric redundancy for the
homography, glyph count mismatch (a missing *or* merged character), incomplete
measurement (a character detected but never measured), specular glare, illumination
gradient, and resolution below the floor.

---

## 5. Why refusal is evidence, not a limitation

**A heuristic always returns an answer. An instrument sometimes declines.** Refusal is
the one behaviour in a three-minute demo that cannot be faked, and it is the clearest
available evidence that what is on the table is a measurement rather than an estimate.

Be precise about what it is evidence *of*. Refusal is a **visible consequence of an
uncertainty-aware architecture**. The architecture is the product; refusal is the part
of it a judge can watch working in ninety seconds. Do not let it become the whole pitch,
because on its own it is cheap: anyone can write `if confidence < 0.7: return "unsure"`
and demo that too. What is not cheap is the chain standing behind the refusal — a
declared threshold, an uncertainty budget with named terms, and a decision rule taken
from JCGM 106 instead of invented. So if the questioning turns into *"your product is
that it doesn't answer?"*, the reply is: **the product is a number with an uncertainty
attached; refusing is what an instrument does when that number cannot be produced
honestly.**

The enforcement framing, which is the one that matters to the sponsoring ministry:
**a flag prioritises inspection; a measurement supports enforcement. Only one of
those can go into a legal notice.**

### 5.1 Two kinds of refusal, and the second one is the rarer claim

Added 2026-09-05. Everything above concerns **metrological** indeterminacy: the pixels
did not support a verdict. There is a second, independent reason to decline, and it is
the one no competing team will have — **the law was unresolved.** An unknown rule
version, an undeclared panel area, an undeclared commodity category and a disputed
threshold all block a verdict just as firmly as a noisy edge does, because a threshold
you had to guess at makes the uncertainty budget behind it irrelevant.

Say it in that order, because the second half is the surprising half: *"it declines when
the measurement is indeterminate, and it also declines when the statute is."*

**And keep three refusals verbally distinct, because merging any two of them is a false
statement about the law:**

- `MEASURAND_UNDEFINED` — embossed or moulded characters. **The requirement applies in
  full;** our instrument has no ink edge to find. The words are *"legal requirement
  applicable, measurement method not validated."*
- `RULESET_NOT_APPLICABLE` — medical devices. A **different instrument** governs.
- `THRESHOLD_DISPUTED` — the requirement applies, we can measure it, and **we do not
  know the number.**

Calling an embossed package "not applicable" tells an inspector that the law imposes no
height requirement on it. That is false, and it is the single place in this design where a
careless label causes real under-enforcement rather than mere noise.

## 6. The numbers — and what they are worth

Current modelled expanded uncertainty: **U(k=2) ≈ 0.17 mm**.

**Quote two significant figures and no more.** The arithmetic gives 0.16634 mm, but
every term feeding it is `modelled`, so digits past the second are arithmetic, not
accuracy. Writing `0.1663 mm` claims a precision the budget does not have, and it is
the first thing a metrology-literate judge will circle.

**No physical reference has been measured yet.** The number is honest and internally
consistent, and it is **not citeable as a performance claim**. Say *"our modelled budget
gives about 0.17 mm, and closing it against a physical reference is the next step"* —
never *"our accuracy is 0.17 mm."*

> **Provenance, read this before reusing an old slide.** This supersedes the previously
> circulated **0.1513 mm**, which came from a five-term budget. Three terms that were
> genuinely absent have been added (below). U got *larger*, which is the correct
> direction for an omission. The figure and every band derived from it are **hand-
> computed; the program has not been re-run since the budget changed.** Any slide still
> showing 0.15 mm is stale.

### The eight terms

| Term | Half-width, mm | Kind | Basis |
|---|---|---|---|
| `ink_spread_and_cap_ambiguity` | 0.080 | systematic | edge criterion plus cap/x-height ambiguity |
| `repeatability_pose` | 0.030 | random | re-presentation of the same specimen |
| `edge_localisation` | 0.010 | random | sub-pixel crossing estimate |
| `scale_calibration` | 0.010 | random | millimetres-per-pixel recovery |
| `lens_distortion_field_position` | 0.010 | systematic | **new** — ~1% radial at field edge, on a 1 mm glyph |
| `defocus_psf_asymmetry` | 0.005 | systematic | **new** — residual after the symmetry argument below |
| `convention_bias_residual` | 0.005 | systematic | leftover after the declared bias correction |
| `fiducial_localisation` | 0.0005 | random | **new** — 0.2 px over a 600 px baseline |

All eight are `modelled`. Not one is measured.

### How the eight terms combine

Random terms combine in quadrature: `√(0.010² + 0.030² + 0.010² + 0.0005²) = 0.03317`,
doubled for `k = 2` gives **0.06634**. Systematic terms are one-sided and therefore
**added**: `0.080 + 0.010 + 0.005 + 0.005` = **0.100**. Total **0.16634 mm**. Do not
quadrature the systematic block to make the number smaller — RSS is valid only for
independent random terms, and these are bounded biases.

Read what the arithmetic says: the systematic block is 0.100 of the 0.16634 total, and
±0.08 mm of that is ink spread and cap-height ambiguity by itself — **one term is
roughly half of U.** Everything optical put together contributes less.

**Defocus is a designed-in strength, not a gap.** A symmetric point-spread function
preserves a 50% intensity crossing exactly, and the top and bottom edges of a 1 mm
character are far enough apart not to interact, so character *height* is first-order
immune to symmetric blur. Only PSF **asymmetry** — coma, off-axis astigmatism — moves
the reading, which is why that term is 0.005 mm and not 0.05 mm. Say this out loud in
Q&A: a system that sharpens or thresholds its way to an edge has no such argument
available to it.

### 6a. Three of the eight terms are relative, and the table stores them as absolute

Added 2026-09-06. **This is a correction to what the budget *means*, not to any number the
program prints, and no figure above changes.** Read it before anyone says the words "double
the requirement and it halves."

Five of the eight terms are absolute: they are fixed distances in the image plane and do
not care how tall the character is. Ink spread and cap ambiguity, defocus asymmetry, the
convention-bias residual, pose repeatability and edge localisation are all of that kind —
a half-pixel edge error is a half-pixel edge error on a 1 mm glyph and on a 6 mm one.

**Three are not.** `scale_calibration` is a millimetres-per-pixel error, which is purely
multiplicative. `fiducial_localisation` is 0.2 px of pointing error over a 600 px baseline,
which is also a scale error — 0.033%, entered in the table as 0.0005 mm because the table
is evaluated on a 1 mm glyph. `lens_distortion_field_position` is stated in the table as
"~1% radial at field edge, **on a 1 mm glyph**", and what reaches the height is the
*difference* in radial displacement between the top and bottom of the character, which
grows with the character. All three are percentages wearing millimetre clothing.

So the honest budget is a function of height, not a constant:

`U(h) = [0.090 + 0.010·h] + 2·√(0.030² + 0.010² + (0.010·h)² + (0.0005·h)²)`

with `h` in millimetres — the absolute systematic block 0.090, plus the relative systematic
term, plus twice the quadrature sum of two absolute and two relative random terms. At
`h = 1` it returns **0.16634 mm exactly**, which is the published figure. That is precisely
why nobody caught this: the whole budget was built and checked at a 1 mm glyph, where a
relative term and an absolute term of the same size are indistinguishable.

| Requirement | `U` as the program computes it | `U(h)` honestly | Callable shortfall, program | Honest |
|---|---|---|---|---|
| 1.0 mm | 0.16634 | 0.16634 | 16.6% | **16.6%** |
| 2.0 mm | 0.16634 | 0.18486 | 8.3% | **9.2%** |
| 2.5 mm | 0.16634 | 0.19566 | 6.7% | **7.8%** |
| 4.0 mm | 0.16634 | 0.23206 | 4.2% | **5.8%** |
| 6.0 mm | 0.16634 | 0.28578 | 2.8% | **4.8%** |

**The rungs are the transcribed brackets and nothing here confirms them as law** — §3.3 and
§15 still govern that, and the two middle rungs remain the ones that are never said aloud.

**What the right-hand column kills.** The claim "`U` is fixed by the instrument and not by
the packet, so the smallest callable shortfall is inversely proportional to the requirement
— double it and it halves, exactly" is **false, and the word "exactly" is what makes it
indefensible.** 16.6% to 9.2% is a factor of 1.80, not 2, and it gets worse as you climb:
the relative terms eventually dominate and the curve flattens onto an asymptote of
**3.0%** — `0.010 + 2·√(0.010² + 0.0005²)`, in units of `h`. **There is a floor on how
small a shortfall this instrument can ever call, and it is about three percent of the
requirement, no matter how large the requirement is.** That is a better sentence than the
one it replaces: it is true, it is a real property of the design rather than a lucky ratio,
and it is the kind of statement a metrologist recognises as having come from someone who
differentiated their own budget.

**Now the part that decides what we do about it: nothing, until after Wednesday.** The
table below and every band in this document are what the *program* computes, and the
program treats all eight half-widths as absolute. Rewriting the document to the honest
model while the code keeps the flat one would put the brief and the program into
disagreement, which is a worse defect than the one being fixed — the document's job is to
say what the instrument does. So the numbers stay, the caveat travels with them, and the
scaling goes in the v7.2 patch as a post-Wednesday change with its own regression list.

**Does the internal round care? No, and this is checkable rather than hopeful.** The demo
measures `h = 1.402 mm` against `TL = 1.000 mm`. Flat model: `U = 0.16634`, so
`h − U = 1.2357 ≥ 1.000` → COMPLIANT. Honest model at `h = 1.402`: `U = 0.17322`, so
`h − U = 1.2288 ≥ 1.000` → COMPLIANT, same verdict, and **both round to `U(k=2) = 0.17` at
the two significant figures we report.** The demo output is bit-for-bit unaffected. This is
a claims correction, not a demo risk.

**Where it does bite, and it is the direction that should worry us.** Understating `U`
narrows the indeterminate band, so the program calls verdicts it has not earned — in *both*
directions. Take the largest bracket: a packet measuring 5.80 mm against a 6.00 mm
requirement. The program computes `h + U = 5.966 < 6.000` and prints **DEFICIENT**. The
honest budget, evaluated at the requirement rather than at the reading — which is the
conservative convention the v7.2 patch prescribes — gives `U = 0.28578` and
`h + U = 6.086 ≥ 6.000`, which is *indeterminate*: we cannot tell.
**A false DEFICIENT is the one error an enforcement instrument must not make**, because it
puts a notice on a compliant packer, and §7.1 already commits us to erring the other way.
The flat budget breaks that commitment at exactly the brackets we have not tested. Nothing
in the internal-round demo goes near a 6 mm requirement, so this is Thursday's work — but
it is written here so that the first person to run a large-bracket packet knows what they
are looking at.

**One thing to check by reading, not by assuming.** This correction was written on the
premise that `BudgetTerm` has no scaling field — that each term stores one absolute
half-width. That premise is **unverified**: it came from reading the patch document and the
term table, not the dataclass. The strongest evidence for it is v7.1 regression assertion 7,
where `expanded()` returned `0.16634` exactly while the demo was measuring 1.402 mm; a
height-scaled budget would have had to return `0.17322` unless `expanded()` is a no-argument
call reporting the reference budget, which is itself possible. **Open the dataclass before
anyone writes the scaling patch.** If a scaling field already exists and is simply unused,
this becomes a three-line change instead of a redesign, and the honest column above becomes
what the program already could have printed all along.

### The two terms that are missing rather than modelled

Both are **pure scale errors**, so both belong to the relative family above, and neither is
in the eight. **Neither is being added to the table** — adding a ninth term recomputes `U`
and every band derived from it three days before a demo, which is the recompute cascade this
project has logged twice.

**Fiducial plane.** If the scale artifact and the printed characters are not in the same
plane, every millimetre-per-pixel figure is wrong by the ratio of the plane separation to
the standoff. A graticule on the baseboard beside a 2 mm-thick packet at 150 mm gives
`Δz/d ≈ 1.33%` — on a 1 mm character that is 0.0133 mm, larger than any optical term in the
budget and larger than the two "new" terms added on 2026-09-05 put together. **The fix is
the fixture, not the budget:** shim the graticule up to the printed face, keep the residual
height difference under 0.2 mm, and the error falls under 0.15% where it is genuinely
negligible. §13 job 3 now requires that difference to be measured with calipers and written
down. A term you have designed out is better than a term you have quantified.

**Artifact pitch.** The graticule's own graduations carry a pitch uncertainty, and it
propagates straight into `px_per_mm` as another multiplicative error. **We cannot model this
one honestly** — its value comes from the artifact's calibration certificate, and we do not
have the artifact yet, let alone the certificate. So it goes to §15 as a term whose value is
pending a document, not a term we have estimated. An uncertainty budget that quotes a scale
reference without its certificate is doing the thing this whole project exists to criticise.

### Decision bands, recomputed at U = 0.16634 mm

| | `TL = 1.000 mm` | `TL = 2.000 mm` |
|---|---|---|
| COMPLIANT | `h ≥ 1.166` | `h ≥ 2.166` |
| DEFICIENT | `h < 0.834` | `h < 1.834` |
| Indeterminate band | 0.834 – 1.166 mm | 1.834 – 2.166 mm |
| Band width | 0.333 mm = **33.3% of TL** | 0.333 mm = 16.6% of TL |
| Smallest callable shortfall | **16.6%** | 8.3% ‡ |

**‡ Both `TL = 2.000 mm` figures in this table are flat-model values — what the program
computes, not what the physics gives.** Honestly, `U = 0.18486` at a 2 mm requirement, the
band is 1.815–2.185 mm, 18.5% of `TL`, and the smallest callable shortfall is 9.2%. See §6a.
The `TL = 1.000 mm` column is exact under both models, and it is the only column the
internal round uses.

### The 33% figure is our worst case, not our typical case

Added 2026-09-05, and it is the one piece of good news the corpus audit produced. `U` is
fixed by the instrument and does not depend on `TL`, so the indeterminate band `2U/TL`
shrinks as a *fraction* of the requirement as the requirement grows. Across the table:

**Corrected 2026-09-06 (redteam section 5): the "Which cell" column welded a safe
arithmetic figure to an unsafe statutory attribution -- the paragraph below already says
these bracket-to-area mappings are aggregator transcriptions that must not be read out, but
the table above is what a presenter actually studies. Column replaced with ordinals; the
capability figures are arithmetic and are unchanged.**

| `TL` (mm) | Indeterminate band | Smallest callable shortfall | Row |
|---|---|---|---|
| 1.0 | 33.3% of TL | **16.6%** | 1st |
| 2.0 | 16.6% | 8.3% | 2nd |
| 2.5 | 13.3% | 6.7% | 3rd |
| 3.0 | 11.1% | 5.5% | 4th |
| 4.0 | 8.3% | 4.2% | 5th |
| 6.0 | 5.5% | **2.8%** | 6th |

*The 1.5 mm row is deliberately omitted: that is the disputed cell, and putting a
capability figure against it would smuggle the unsettled number onto a slide sideways.*

So **the 1 mm case we have been designing against is the worst cell in the entire table**,
and it applies only to panels of 50 cm² or less — roughly a 7 × 7 cm packet. Most retail
packaging sits in brackets where the band is proportionally two to five times tighter.
Slide 4 now presents 33% as the worst case rather than the headline; that edit is made.

**This table is internal, and its spoken form is a relation, not a list of rungs.** Every
value in the middle rows — 2.0, 2.5, 3.0, 4.0 — is an aggregator transcription, and reading
them out attributes threshold values to specific brackets on evidence we do not have. The
deck's rule, and it should be this section's rule too: say *"the smallest callable shortfall
is `U/TL`, so double the requirement and it halves, exactly; at the top of the table it is
under three percent."* That is the same content, it is arithmetic rather than statute, and
1 mm and 6 mm are the ends of the range we are already permitted to state.

**The caveat must travel with the number, every time.** This holds at **constant
millimetres-per-pixel only.** A 2500 cm² panel either needs a wider field of view, which
lowers px/mm and inflates `U`, or a crop-and-stitch capture. The benefit is real on a
fixed rig measuring a crop of a large panel; it is not free, and quoting the 2.8% without
the caveat would be a fresh overclaim of exactly the kind this section exists to prevent.
Derive these rows from `capability_table()` rather than retyping them.

Moving from the 2 mm case to the real (printed, general-category) 1 mm floor **doubles
the relative indeterminate band** — trivially so, since the band is `2U/TL` and U does
not depend on TL. We pass a 20%-shortfall detection target with **1.20× margin**, down
from 1.32× before the budget was completed. A 10% target needs `U ≤ 0.100 mm`, which is
a **40% reduction** in U.

**Consequence, and it is sharper than it used to read.** That 40% cannot come from
optics. The random block contributes only 0.066 mm expanded, so driving every random term
to zero still leaves 0.100 mm. The reduction has to come out of the systematic block, and
0.080 of that 0.100 is the ink-spread and cap-height term. A 10% detection target is
therefore reachable **only** by measuring the convention bias against a physical
reference and correcting for it — and if that one term were eliminated, U would fall to
about 0.086 mm, which does clear it. The glass stage micrometer is **load-bearing**, not
optional: it is the only route to a 10% target that exists.

Do **not** re-derive the capture resolution target from this requirement. That cascade
was a documented error in an earlier revision. The 30 px/mm floor stands on its own
grounds.

**The field-position experiment that retires the newest term.** The distortion figure
above is an estimate, not a measurement, and it is cheap to replace with a real one: put
the stage micrometer at the **centre of the field and then at each of the four corners**,
five captures, and compare the recovered millimetres-per-pixel. The spread across those
five is the distortion term, measured. Same session, same rig, ten minutes. Until it is
done, `lens_distortion_field_position` is a placeholder of exactly the same standing as
the other seven.

### Verified supporting figures

- Relative uncertainty of a sample standard deviation at n = 12 is
  `1/√(2(n−1)) = 1/√22 = 21.3%`. This is why a 12-package survey cannot produce a
  tight uncertainty estimate on its own.
- Cylindrical parallax, 60 mm bottle at 150 mm working distance: depth offset
  `R(1−cos θ)` = 4.02 mm at 30°, 8.79 mm at 45°. As a scale error that is 0.054 mm
  and 0.117 mm on a 2 mm glyph. Because it is a *relative* scale error it halves with
  glyph height — **0.027 mm at 30° on a 1 mm glyph** (30x(1-cos30 deg)/150 = 0.02679, corrected 2026-09-06 -- was rounded the flattering way), which is small against U.

---

## 7. Declared scope boundaries — where we refuse by design

Three surface types, three different answers. Surface type is a **declared operator
input**, exactly like package category, commodity class, panel area and inspection date.
Nothing about the law is inferred from the image anywhere in this system.

**Flat printed stock — the validated envelope.** Labels, cartons, printed film lying
flat on the platen. This is what the rig measures and what every number we quote
refers to. Demo everything here.

**Printed label wrapped on a cylinder — designed, not built.** Restrict the ROI to
±30° of the camera-facing generatrix, recover the radius from the silhouette, and
correct the scale using `D + R(1 − cos θ)`. The uncorrected error on a 60 mm bottle at
150 mm is only 0.027 mm at 30° on a 1 mm glyph (corrected 2026-09-06), so **curvature is not the binding
limitation.** If asked, say "designed, not built."

**Moulded, embossed, blown, formed or perforated relief — we refuse, on measurand
grounds.** This is the honest answer and also the interesting one. Our edge criterion
is declared as **50% of the ink-to-substrate intensity transition**. Relief characters
have no ink. What the camera sees is a shadow edge whose position moves with the
illumination direction and is displaced by the moulding draft angle. There is no
defined measurand — the quantity is not specified, let alone measured badly. Worth
saying out loud: **the Rules put their stricter requirement on exactly the geometry
that is hardest to measure.**

The code **now refuses** `CATEGORY_FORMED`. The refusal code is `MEASURAND_UNDEFINED`
and it fires before any measurement is attempted, so no path exists from a declared
relief package to a compliance verdict. A deliberate characterisation override
(`allow_undefined_measurand=True`) exists for research use and is not reachable from the
demo path. Defining the relief measurand properly needs raking-illumination or
structured-light depth recovery, which is a research project, not a four-day job.
**Do not demo a relief package as a measurement — demo it as a refusal.**

Phrase that refusal carefully, every single time: **the requirement applies in full and
our method is not validated for it.** Not "the rule doesn't apply here." The formed column
of the table carries the *higher* thresholds, so anything that sounds like an exemption is
the opposite of the truth.

### Three further boundaries, added 2026-09-05

**Character width — declared, not implemented.** The Rules impose a minimum width relative
to height as well as a minimum height, with exceptions for certain glyphs. We check height
only. Say so before anyone asks, because a system claiming to check "the statutory
dimensional requirement" must not silently mean half of it. Then say *why* it is not a
weekend's work, because the reason is interesting: the per-glyph exceptions mean you have
to know **which character** you are looking at to apply the rule at all, so width makes OCR
load-bearing *inside* the dimensional check rather than beside it. That is a different
architecture, a new uncertainty term and its own validation set. Neither the width
fraction nor the exception list has been read from a primary source, so do not state
either — `WIDTH_RULE_NOTE` in the code ends *"not implemented, not estimated, not
claimed"* and that is the line to use.

**Medical devices — a different instrument governs.** For medical-device packages the
Medical Devices Rules 2017 govern the declarations and their dimensions; the PCR height
table does not apply. The code refuses with `RULESET_NOT_APPLICABLE`, which is a *different
refusal* from `MEASURAND_UNDEFINED` and must never be described in the same words. Caveat
for the team: the audit's citation for the height-and-width specifics is a file named
"Draft Amendment", and **this project has already been burned once by treating a draft as
notified law** — the >25 kg provision. The carve-out itself is separately attributed to a
notified amendment so it probably exists; the specifics are unverified. Implement the
branch, cite nothing.

**Absence of printed information is not evidence of a violation.** Certain product
information may lawfully be supplied by **QR code** rather than printed on the panel. Any
"missing declaration" check built on visible print alone therefore has a false-positive
mode that its authors may not know about. We do not do presence checks, so this is not our
bug — but it is a good question to have ready, and it is a fair thing to raise about a
checklist-based competitor without being unpleasant about it.

Also out of scope, and say so plainly: handheld capture with no scale reference,
retail-shelf photography, transparent or strongly specular substrates, and any claim
about declarations other than character height. Presence checks are OCR's job, and
OCR is a component we compose with, not a rival.

### 7.1 The measurand inside the validated envelope

This is the attack that matters most, and note where it lands: not on the surfaces we
already refuse, but on the flat printed stock we call **validated**. Put plainly — *the
statute says a character shall be at least 1 mm in height; where does it say that
"height" means the extreme extent of ink at a 50% intensity crossing, supported over a
contiguous run of columns?*

It does not. Almost certainly no statute anywhere does. That is the point to make rather
than the one to hide.

1. **Ink has no sharp boundary.** At the resolution a 1 mm floor demands, the
   ink-to-substrate transition is a ramp several pixels wide, produced by dot gain,
   substrate absorption and the imaging PSF. There is no edge to find — only a criterion
   to declare. **Every** dimensional measurement of a printed character needs such a
   declaration, including one made by an inspector with a loupe and a graticule. The
   inspector's criterion is simply undocumented.
2. **So the defensible claim is a declared convention with a bounded cost**, not a
   discovered truth: *"the statute does not specify an edge criterion; we declare 50% of
   the ink-to-substrate transition; the cost of that choice is bounded at ±0.08 mm, and
   it is the largest single term in our budget."*
3. **That ±0.08 mm term is the answer, not an embarrassment.** It is already in the
   budget as `ink_spread_and_cap_ambiguity`. It **is** the sensitivity-to-convention
   figure — how far the reported height could move if a court preferred a different
   defensible criterion. A system that reports a height with no such term has not solved
   this problem; it has failed to notice it. Never present that term as the answer to
   "how accurate are you" — it is the answer to "what if your convention is wrong."

**On the direction of the bias.** `max_supported` takes the extreme extent that persists
across a contiguous run of columns, so outward print defects — a spur, a stray fibre, a
satellite dot — push the reading **up**, toward COMPLIANT. That asymmetry is real, and it
is the legally safer direction: an enforcement instrument should err against over-calling
deficiency, because a false DEFICIENT puts a notice on a compliant packer while a false
COMPLIANT merely fails to catch one. Present it as a design choice with a reason. A judge
who spots the asymmetry unprompted will otherwise read it as a bug.

Two caveats, so nobody is caught out later. First, the support width meant to reject
narrow defects is **declared** as 0.02 mm but is quantised to whole pixels, so at the
30 px/mm floor it is actually enforced at roughly 0.067 mm, and at 120 px/mm at roughly
0.017 mm — a convention parameter that silently changes with resolution. Section 8 lists
it as a defect with its fix. Second, the ±0.08 mm term **bundles** the edge criterion
together with cap-height/x-height ambiguity; separating the two requires the physical
reference, and until then we cannot say which half dominates.

### 7.1a The measurand, written down once

Added 2026-09-06, because three sections of this brief described three different quantities
and none of them was the one the code computes. **If a judge asks "what exactly do you
measure?", this paragraph is the answer and nothing else in the document is:**

> **The measurand is the vertical extent of ink of a single printed character, in
> millimetres, in the plane of the printed surface, bounded by the outermost rows at which
> the ink-to-substrate intensity profile crosses 50% of its local transition, counted only
> where that crossing persists across a contiguous run of columns of declared width, less a
> declared convention bias.** Reported for one glyph per panel — currently the shortest the
> instrument succeeded in measuring, which is a known defect, not the design.

Everything contestable in that sentence is contestable *on purpose*: the 50% crossing is
declared rather than discovered, the support width is declared, the bias is declared, and
the choice of governing glyph is named as defective. **A measurand definition that contains
no declarations is hiding them.**

**The three wordings, reconciled.** §4 Layer 2 step 3 said a *"cap-height convention"*; §6
names the dominant term `ink_spread_and_cap_ambiguity`, basis *"edge criterion plus
cap/x-height ambiguity"*; §7.1 says *"the extreme extent of ink at a 50% intensity
crossing."* Those are not three phrasings of one thing. A cap-height convention is a
**nominal typographic distance** from baseline to cap line — a property of the typeface,
which you cannot observe on a packet without knowing the font. An extreme ink extent is an
**observation**, and it includes overshoot, dot gain and any descender that falls in the
window. **§4 is the wrong one, and it has been corrected** — the code has never implemented
a cap-height convention and could not, so claiming one was a claim we would have lost.

The budget term keeps its name and keeps its value, and this is not a fudge: once you accept
that we measure ink extent rather than cap height, *cap/x-height ambiguity is exactly the
thing that remains unresolved* — the residual uncertainty about which typographic feature
the statute's "height" refers to, which no edge criterion can settle. The term was never
double-counting a resolved ambiguity. It was correctly named and wrongly introduced.

**`convention_bias_mm`: a correction applied to every reported height, whose value appears
in no document.** `h = extent − convention_bias_mm` runs on every measurement; §6 carries
`convention_bias_residual = 0.005 mm` as "leftover after the declared bias correction", so
the *residual* is published while the *correction* is not. **Read its default off the file
and write it in §15 today**, and print it next to the convention line in the report. If it
turns out to be `0.0`, that is fine and must still be written down — a correction of zero is
a decision, and an undocumented zero is indistinguishable from an undocumented anything.

**The overshoot term nobody has costed.** Round and pointed capitals — `O`, `0`, `8`, and
the apexes of `A`, `V`, `W` — are cut 1–1.5% above the cap line by design, so they measure
taller than `H`, `E` or `X` in the same font at the same size. On a 1 mm character that is
0.010–0.015 mm, the same size as `edge_localisation` and `scale_calibration`, and it is in
neither the eight terms nor §15. It is also **relative**, so it belongs to §6a's family. It
cannot be fixed by adding a fixed half-width, because whether it enters the answer at all
depends on which glyph governs.

**And the two biases must never be presented as cancelling.** `max_supported` takes a
per-column extreme, so outward print defects push the reading **up**, toward COMPLIANT —
§7.1 says so and defends it. But `min(v)` selects the *shortest* glyph, which is
systematically a flat-topped one, so the reported height systematically **excludes**
overshoot and reads **down**, toward DEFICIENT. Two known biases, opposite directions,
neither quantified. **If anyone in Q&A is tempted to say they cancel, the honest answer is
that we know the sign of each and the magnitude of neither, and a cancellation you cannot
compute is a coincidence you are hoping for.** Fixing the governing-glyph selection is the
post-Wednesday change tracked in §8 and in the v7.2 patch; the glyph-class axis it needs is
blocked on the statutory transcription, not on code.

---

## 8. The program we have built

**Reference build:** `lm_metrology_v7.py` · `VERSION = "7.0-corrected-2026-09-04"` ·
sha256 `60374c478da4e2c501c5060c980324661a7b64eb0553727f8bc707238f66babe`

**Pending build:** v7.1, specified block-for-block in `SIH26034-patch-v7.1.md` — the
measurand gate, three added budget terms, two-significant-figure reporting, and the
support-width defect.

**Also pending, and of a different kind:** `SIH26034-patch-v7.2.md`, written 2026-09-06.
Four corrections that could not be applied here because **`lm_metrology_v7.py` is not on the
disk the patch was written from** — so unlike v7.1, nothing in it has been run and every
quoted line is a reconstruction to be checked against real source before replacement. Two are
for before Wednesday (the three `r.9` label strings; the deletion of the program's own
falsified `max_illum_gradient` recommendation) and two are for after (the relative-term
scaling from §6a; printing `convention_bias_mm`, whose *document* half needs no patch and is
owed to §15 today).

**New module, unrun:** `lm_legal_model.py`, written 2026-09-05, the statutory layer
described in Layer 1. It is a **separate file rather than a patch into v7** for three
reasons: the v7 source was not available on the machine it was written on, so patching
meant guessing at anchor context; a new file matches nothing and therefore cannot
mis-apply; and it cannot break the working measurement path. Its integration surface is
three call sites, named in a comment block at the bottom of the file. **Nothing in it has
been executed.** It carries a `self_test()` of about seventy checks — bracket boundaries at
exactly 50, 100 and 2500 cm², every refusal code, check ordering, commencement-date
handling, hashability, a block of leak tests on the strings a human actually reads, and two
invariants that fail if anyone promotes the table to `VERIFIED` without reading a Gazette
PDF. Run that first, before any integration, and before believing anything in this section
about it.

**Second new module, also unrun:** `lm_capture.py`, written 2026-09-05, the fixed-rig
capture path — scale artifacts and their tiers, the rig session, the capture gates, and a
`SpecimenCapture` that cannot be constructed without a `ScaleReference`. Its decision layer
is camera-free and OpenCV-free on purpose, so its `self_test()` of about seventy checks
runs on a laptop with no camera attached, and so the demo has a stills fallback if the
rig misbehaves on the day. Same status as the legal layer: written, never run.

**And it now carries a ledger of its own numbers, which produced a finding worth owning.**
`_GATE_PROVENANCE` classifies every numeric constant in that file as *derived* — the value
follows from a stated allowance by an argument written above it — or *placeholder*, meaning
nobody derived it and it was set to something plausible to get the file running. The split
came out **three derived, five placeholders.** Derived: `LENS_FIELD_TERM_REL`,
`MIN_BASELINE_PX`, `ABS_MIN_BASELINE_PX`. Placeholders: `MIN_PX_PER_MM` (inherited from v7,
which already says it is not a proven minimum), `SCALE_SESSION_FRAMES`,
`SCALE_SPREAD_REJECT_REL`, `FOCUS_FLOOR_FRACTION`, `_SCALE_STALE_SECONDS`. A `self_test()`
check fails if a numeric constant is missing from the ledger, so a gate cannot be added
without someone deciding which kind it is, and a second check fails if the ledger keeps
asserting a derivation for a constant that has been deleted.

Say the split plainly if the capture path comes up: **the refusals are real behaviour; most
of the numbers behind them are not yet derived.** That is the same disclosure as the
eight-term budget one column over, at a different layer — and the ledger is what makes it a
disclosure rather than something a reviewer extracts. Two of the five have a route to
derivation on this rig (`FOCUS_FLOOR_FRACTION` by measuring where edge location starts to
move, `MIN_PX_PER_MM` by asking what the edge model actually needs); one cannot be derived
from the budget at all, because `_SCALE_STALE_SECONDS` answers a procedural question — how
long this rig stays put and whether anyone bumps the table.

Two things follow from this, and the second one bites. Version identity is part of a
measurement record, so quoting a hash when a judge asks which build produced a result is
the right instinct. But **that hash belongs to 7.0, and 7.0 is the build that produced
the run log below.** Applying the v7.1 patch changes the version string and the hash
together, and `_self_hash()` recomputes at runtime, so the moment anyone edits the file
the number above stops matching. Rule for the demo: **read the version and hash off the
running program, never off this document.** A stale hash quoted confidently is worse than
no hash at all, because it is a false claim about provenance — exactly the failure mode
this project exists to prevent.

### Structure — seven parts

1. **Conformity and legal.** In v7 this is `HeightRule`, `RuleTable`, `RuleSet`,
   `RULES_2011`, `governing_threshold()` — a flat model returning 1 mm or 2 mm by
   category, with `RULE_INDEX_AMBIGUOUS` when an index value straddles a bracket
   boundary. **That model is now known to be the smallest-panel row of a five-row table
   and nothing else**, so it is superseded by `lm_legal_model.py`. Until the three call
   sites are wired in, v7 still returns the flat thresholds: correct for a package
   declared at 50 cm² or under, wrong above it.
2. **Geometry.** Planar homography by normalised DLT with SVD; scale recovery.
3. **Measurement primitives.** Sub-pixel edge location at the declared 50% criterion;
   per-column extremes; the `max_supported` convention.
4. **Refusal layer.** `CaptureLimits` and `capture_checks` — planarity, geometric
   redundancy, glyph count, incomplete measurement, glare, illumination gradient,
   resolution floor.
5. **Top-level `measure()`.** Returns `h`, `U`, `TL`, verdict, and the refusal reason.
6. **Synthetic scene generation.** Renders glyph arrays at known heights. **Ground
   truth is derived from the rendered array, never from the requested parameters** —
   otherwise the test validates the request, not the renderer.
7. **Audit experiments.** Convention bake-off, sampling sweep, exposure sweep.

### What the run log establishes

Self-checks pass: 4-point homography RMS `2.716e-13 px`, 5-point `0.353 px`. The
4-point case fits exactly, so its residual is zero by construction and carries no
information — which is precisely why `NO_REDUNDANCY` requires **five or more**
features before it will trust a homography.

Conformity, on the same measured `h = 1.402 mm`. Two columns now, because the budget
change in section 6 moves U and the v7.1 patch changes one of the verdicts:

| Declared category | `TL` | v7.0 as run, `U = 0.151` | v7.1 as specified, `U = 0.166` |
|---|---|---|---|
| `general` | 1.000 | COMPLIANT (`1.402 − 0.151 = 1.251 ≥ 1.000`) | COMPLIANT (`1.402 − 0.166 = 1.236 ≥ 1.000`) |
| `blown_formed_…_perforated` | 2.000 | DEFICIENT (`1.402 + 0.151 = 1.553 < 2.000`) | REFUSED, `MEASURAND_UNDEFINED` |
| not declared | — | REFUSED, `CATEGORY_NOT_DECLARED` | unchanged |

The COMPLIANT verdict is **robust to the budget change** — the margin narrows from
0.251 mm to 0.236 mm without crossing, so the demo does not depend on the old number.
The formed-category row is the patch doing its job: v7.0 returned a *correct-looking*
DEFICIENT for a package whose measurand is undefined, which is the worst class of wrong
answer because nothing about it looks wrong. **The right-hand column was hand-computed
until 2026-09-05; v7.1 has now been run and its conformity demo reproduces all three rows —
`general` → COMPLIANT at `h = 1.40 mm, U = 0.17 mm, TL = 1.00 mm`, the formed category →
REFUSED `MEASURAND_UNDEFINED`, and an undeclared category → REFUSED
`CATEGORY_NOT_DECLARED`.** One caveat survives the run rather than being cleared by it: the
demo prints `h` at two significant figures, so it shows `1.40` where the pre-patch figure
was `1.402`, and the regression item that asked whether `h` moved *at all* under patch 5
cannot be answered by reading this output. See §13a.

**What the new legal model does to this table.** `TL = 1.000` is no longer a constant —
it is the value the table returns for a panel of 50 cm² or less. So the rendered targets
must be **declared** as small-panel specimens, at which point 1.000 mm is genuinely the
right threshold and every verdict above stands unchanged. Nothing built is invalidated.
What changes is what we say while showing it: *"panel area 40 cm², which is the A ≤ 50
bracket, so the requirement is 1.0 mm"* is a strictly better sentence than a hardcoded
constant, and it costs nothing to say.

Convention bake-off, clean-row spread: `max_supported` **0.001143 mm** versus
`max_binned` **0.039330 mm** — a 34× penalty, so `max_binned` is reverted and opt-in
only. The mechanism is deterministic apex attenuation, not extreme-value statistics,
so no choice of bin size rescues it.

### What is missing — the one outstanding build item

**There is no live-capture path.** No frame grab, no fiducial detection, no
rectification of a real image, no ROI selection. `capture_checks` accepts `H`,
`src_mm` and `dst_px` from outside, which means `PLANARITY` and `NO_REDUNDANCY`
**cannot fire in any path that exists today.** Everything demonstrated so far runs on
synthetic scenes.

This is roughly thirty lines and it is the reason to unfreeze the file. Shape of it —
**this sketch has not been run by anyone, treat it as a specification, not as code:**

```python
def capture_and_measure(cam_index, table, index_value, category, glyph_class):
    frame = grab_frame(cam_index)              # cv2.VideoCapture, discard first N frames
    pts_px, pts_mm = detect_fiducials(frame)   # >=5 corners of a known-size target
    H, ppm = rectify(pts_px, pts_mm)           # normalised DLT + SVD, then mm/px scale
    roi = select_roi(warp(frame, H))           # operator drags a box, or fixed window
    return measure(roi, ppm, table, index_value=index_value, ...)
```

Two hard requirements on that path, both already argued for elsewhere in this
document: **at least five fiducial features**, so the reprojection residual is
informative; and a **≥ 30 px/mm** effective sampling rate, which the resolution-floor
check enforces rather than assumes.

### The patch list

**Owed to the legal model.** Item 3 below is done; 1 and 2 are not, and are the real
remaining work:

1. Add the **glyph-class axis** to `RULES_2011`. Both tables are currently flat and
   single-row, with no letters-versus-numerals distinction.
2. Thread a **declared glyph class** through `measure()`. Today it takes one global
   `min(v)` and compares it to one threshold. Because lining figures sit at cap height
   while lowercase sits at x-height, on any mixed line `min(v)` **is** a lowercase
   letter — so comparing it against a numeral threshold fails systematically, not
   occasionally, and it can err in either direction.
3. ~~Fix the `HeightRule.label` strings, which still read "r.9"~~ — **DONE.** Applied as
   patch v7.2's Patch 1, verified in v7.3: all three sites fixed (both labels and
   `RuleSet.citation`). The citation has since gone further — it's now sourced to Rule
   7(2), confirmed 2026-09-07 against an actual Gazette-notification compilation, not
   left merely un-hardcoded. See the legal-provenance sheet for the current citation.

**Owed to the measurement layer.** Two further defects, both found while auditing the
v7.1 patch rather than by running anything:

4. **`min(v)` is coupled to the population the refusal layer distrusts.** The reported
   height is the minimum over *measured* glyph extents. But `measurement_completeness()`
   drops glyphs it cannot measure, and its own docstring names those as "the thin-stroke
   and low-contrast ones, i.e. the ones nearest the limit" — the very glyphs most likely
   to set the minimum. The failure mode is therefore **selection bias toward COMPLIANT**:
   the characters that would have produced a DEFICIENT verdict are the ones most likely
   to vanish before `min()` runs. `MEASUREMENT_DROPPED` already refuses whenever any
   glyph is dropped, which contains the bug — but the containment is *accidental*, which
   makes that refusal load-bearing rather than merely cautious. Cheap fix: record
   `governing_glyph_index` and the dropped indices in the diagnostics, so an operator can
   see whether the reported minimum sat next to a dropped neighbour. The real fix arrives
   with the glyph-class axis.
5. **The support width is quantised, and therefore resolution-dependent.**
   `_supported_extreme()` converts `min_support_mm = 0.02` to pixels via
   `mm_to_px(..., floor=2)` and **discards the floor-limited flag it is handed.** At
   30 px/mm, 0.02 mm is 0.6 px, floors to 2 px, and the convention is really enforced at
   0.067 mm — over three times its declared value. At 120 px/mm it lands near 0.017 mm.
   A declared convention parameter that changes silently with sampling rate violates this
   file's own standing rule that conventions must not depend on capture settings. Fix:
   capture the flag, publish the **effective** support width in the diagnostics, and warn
   when it is floor-limited.

**Owed to the measurement layer, found in the v7.1 run itself.** Four more. Items 6 to 8
were located **by execution rather than by reading**, which is a first for this project;
item 9 needed only the file, which had been missing from every previous round.

6. **The shipped level estimator is the worse of the two, on this run's own evidence.**
   `levels_iterative` is the default and `levels_percentile`'s docstring says it is "kept
   for comparison only". The exposure sweep compares them across four contrasts and four
   noise levels, and **the percentile estimator has the smaller bias in 11 of the 12 noisy
   cells.** The twelfth (noise 0.020, C = 0.35) is 0.01477 against 0.01453 mm — a 0.24 µm
   difference, well inside the scatter of both columns, i.e. a tie. Worse, at **noise = 0 the
   percentile estimator is exactly zero at all four contrasts while the iterative one sits
   at +0.00149 mm** and stays there regardless of contrast. That offset is predicted in the
   docstring, correctly, as a contrast-independent class-occupancy effect — blurred edge
   pixels join a class and drag its mean — so the mechanism is understood. What is new is
   that nobody appears to have compared the two columns and noticed that the estimator
   carrying a floor of 1.5 µm loses to the one that carries none.
   **Keep the default for Wednesday.** Switching the level estimator moves every number in
   the run four days before a demo, and neither estimator has been exercised on a real
   photograph, so this is a post-Wednesday decision with a written finding attached rather
   than a fix. Two things to do now, both cheap: **print which estimator produced any number
   that gets quoted**, and note that 1.5 µm against the 80 µm convention systematic is 1.9%
   of one term — **this is not a budget problem.** It is an evidence problem, and item 7 is
   why.
7. **The exposure experiment still cannot attribute its own signal — and the instrument
   that would let it has been built and never used.** The sweep reports
   `inv = bias × C / noise` and treats a constant value as evidence that the bias comes from
   percentile tail asymmetry, which scales as noise/C. The percentile column does behave that
   way: `inv` holds near 0.206 at low noise, drifting to 0.259 at noise 0.020. But subtract
   the 1.5 µm offset from the iterative column, as its own docstring instructs, and **the
   iterative estimator shows the same 1/C signature — corrected `inv` of 0.169 to 0.228, and
   at noise 0.010 a bias ratio of 2.93× across a 2.51× contrast ratio, against the percentile
   estimator's 2.80×.** Class means have no tail asymmetry. If tail asymmetry were the cause,
   replacing the estimator should have attenuated the term; it did not.
   **So the level estimator is largely exonerated and the 1/C almost certainly comes from
   somewhere both estimators share.** The candidate is the extreme-value combiner:
   `max_supported` takes an extreme over columns, per-column crossing jitter scales as
   noise ÷ edge slope ∝ noise/C, and the extreme of N such draws inherits that scale. That
   reproduces the observed signature without invoking percentiles at all. **Stated as a
   hypothesis, not a finding** — what the run establishes is the negative half, that the
   level estimator is not the driver.
   The discriminator is a one-line experiment and the hook for it **already exists**:
   `measure_glyphs` accepts `level_override`, which kills the level mechanism outright by
   feeding the true level, and sweeping N at fixed px/mm moves only the combiner. Reading the
   v7.1 source as pasted, **no experiment in the harness passes `level_override`** — it is
   plumbed through the function and called by nothing. A discriminator that exists as a
   keyword argument and is never passed is the same defect as a fix that is correct, tested
   and off the shipped path, and it has now cost rounds of argument about a question the file
   was already equipped to answer. Verify with a grep on disk before acting, since the
   file is not in my workspace and I am reading a paste.
8. **The convention's name asserts a capability its audit has never tested.**
   `max_supported` exists to reject an extreme that rests on too few pixels — stray ink, a
   hot pixel, a dust speck. In the convention bake-off, **`max` and `max_supported` print
   identical figures in every row** — on the clean scene both give +0.001701 mm, sd 0.000429,
   spread 0.001143, and on the realistic scene both give +0.003075 mm with sd and spread
   likewise matching to every printed digit. The support test
   never rejected anything, which is correct behaviour on synthetic glyphs that contain no
   defects, and it means **the feature the convention is named after has never fired in any
   test.** The scenes exercise noise, blur, glare and resolution; none of them contains a
   defect of the kind `min_support_mm` exists to catch. One synthetic case fixes this: add a
   two-pixel bright speck a few pixels above a glyph's cap line and assert that `max` picks it
   up while `max_supported` does not. Until that test exists, the honest description of the
   shipped convention is "an extreme, with an untested guard", and it should not be described
   on a slide as defect-resistant. A smaller instance of the same drift: harness self-check 1
   proves the hard-step extraction exact to 1e-6 mm using `rule="max"`, **not** the shipped
   `max_supported`. On a hard step every column is identical so the two agree, which is why it
   passes — but the exactness guarantee the team will quote is guaranteed for a convention the
   product does not use. Change the self-check to the shipped default and it should still pass.
9. **The bake-off's audit denominator is hard-coded**, and by a construction that works by
   accident: `matched={matched}/{len(make_glyphs.__defaults__ and 'ABMOVW148')}`. The
   `__defaults__` tuple is truthy, so the expression collapses to `len('ABMOVW148')` and
   prints 9. Change the default glyph string and the denominator silently keeps saying 9
   while the numerator tracks the new text — the audit drifts off the thing it audits, which
   is a failure this project keeps repeating: slide 5's stale refusal count and §13's
   restatement of the gate-kind split were both the same shape. It should read
   `len(sc.truth)`. Low severity, thirty seconds, do it while the file is open.

Known-open and deliberately left alone: `CaptureLimits.max_illum_gradient = 0.10` is
decorative — it never fires before `GLYPH_COUNT` does. **Do not wire in 0.0319**, and the
v7.1 run has now turned that instruction from a judgement into a finding, because **the run
falsifies its own recommendation two tables above the line that prints it.** The gradient
sweep walks one highlight width (σ = 0.45), finds the 0.008 mm crossing at gradient 0.0319,
and prints "set `max_illum_gradient` just below 0.0319". The glare table immediately above it
sweeps three widths, and in it:

- **σ = 0.25, scale 0.3 → gradient 0.0142, error +0.0094 mm.** Above the 0.008 mm target at
  less than half the recommended limit. A limit of 0.0319 passes this capture.
- **σ = 0.70, scale 0.3 → gradient 0.0400, error +0.0053 mm.** Above the recommended limit
  at two thirds of the target error. A limit of 0.0319 refuses this capture.

Both errors, in both directions, in one table. At a gradient near 0.04 the damage ranges from
0.0053 mm to about 0.018 mm depending only on how wide the highlight is — **so the metric is
not merely a loose proxy for the harm, it is not single-valued in it**, and no threshold on a
quantity that maps one value to a 3.4× range of damage can be derived by finding a crossing.
The sweep also never reaches a second width: it breaks at scale 0.80 on a SPLIT
(`spans=6, expected=5`), which is the correct behaviour and confirms the split-versus-deletion
labelling works, but it means the printed recommendation rests on a single curve. The fix is
unchanged: replace the global `ptp` metric with a per-span substrate variation, derive it
across highlight scales, and take the minimum crossing. Until then the number the program
prints is a number the program's own data contradicts, and **the recommendation line should be
deleted from the output rather than left for someone to act on.** Also open: the 8 px/mm
sampling row reports `n=5` where the rest of the sweep reports `n=25`.

---

## 9. Components — bill of materials

Total **≈ ₹10,000, excluding the laptop.** Say "excluding the laptop" when you quote
it; an earlier revision of our own plan quoted the figure as if it included one.

| Item | Spec / note | Approx cost |
|---|---|---|
| Webcam | 1920-px horizontal. **Tighten the field of view to ~55 mm**, giving `1920/55 ≈ 35 px/mm`, above the 30 px/mm floor. No purchase needed if an existing 1080p camera is used | ₹0 – 2,500 |
| Copy stand / fixed mount | Rigid, repeatable working distance. Any camera stand or a clamped arm | ₹800 – 2,000 |
| Platen | Flat matte board, mid-grey, to hold labels flat | ₹100 |
| Diffuse illumination | Two LED panels or a ring light with diffuser. Even, non-specular | ₹1,000 – 2,000 |
| **Glass stage micrometer** | **Load-bearing, not optional** — the only reference *standard* in the kit. Read the third note below before claiming what it certifies | ₹1,000 – 2,000 |
| Flatbed scanner | **1200 dpi optical**, not interpolated. Measures what the press actually printed | borrowed |
| Printed graded targets | Character heights **0.70 / 1.00 / 1.30 mm** nominal — respaced for the larger U, see section 10. These are *specimens*, not standards: they exercise the decision bands, they do not establish accuracy | ₹200 |
| Torch or phone LED | To force a deliberate `GLARE` refusal on demand | ₹0 |
| Moulded/embossed bottle | To force the out-of-envelope refusal | ₹0 |
| 10–15 ordinary retail packets | Refusal-rate rehearsal on real stock | ₹500 |
| Laptop | Python 3, OpenCV, NumPy | already owned |

Three notes that matter more than the prices.

**The 55 mm field of view is a free decision, not a purchase.** Cropping the frame to
a narrower field raises px/mm without spending anything. Note that a 75 mm field on
the same sensor gives `1920/75 = 25.6 px/mm`, which is **below our own floor** — that
error is in the record from an earlier revision, so check the arithmetic before
committing to a working distance.

**The scanner does not close the calibration loop by itself.** There are three
distinct quantities: the *design* height we asked the press for, the *scanner's*
measurement of what the press actually produced, and the *rig's* measurement of that
same physical sheet. Only the third closes the loop, and it requires photographing the
scanned reference sheet **on the demo rig**. Be aware of the trap: the camera and the
scanner share ink spread and share the 50% edge criterion, so those error terms are
common-mode and cancel — an agreement between them flatters the instrument and does
not validate the dominant systematic.

**A reference standard and a reference specimen are not the same thing, and the kit
contains one of each.** Get this vocabulary right, because it is the distinction a
metrology-literate judge is listening for.

A **reference standard** carries a value with a stated uncertainty from an authority
outside the experiment. The glass stage micrometer is the only such item here: its ruled
divisions are what let us claim a millimetre is a millimetre. A **reference specimen** is
an artifact whose value we do not independently know — the printed graded targets are
specimens. They were *asked* for at 0.70, 1.00 and 1.30 mm, and what the press delivered
is unknown until something measures it.

The consequence is narrow and important: **graded targets exercise the decision bands;
they cannot demonstrate accuracy.** Showing that 0.70 comes back DEFICIENT, 1.00 refuses,
and 1.30 comes back COMPLIANT proves the decision logic is wired correctly and the bands
sit where section 6 says they do. It proves nothing about whether the rig reports true
millimetres. Only the micrometer can support that claim. Do not blur the two in the demo
narration.

And be straight about where the chain ends. A ₹1,000–2,000 stage micrometer ships
**uncertified** — no calibration certificate, no stated uncertainty, no traceable link to
a national standard. So even after it is measured, the chain terminates in an uncertified
artifact. That is a perfectly normal position for a four-day prototype, and it is exactly
why section 4 says *traceable by construction, not yet traceable in fact.* If a judge
presses, the answer is that closing the last link is a purchase order and a calibration
lab, not a research problem — which is the correct thing for a prototype to be able to
say.

---

## 10. Internal round demo — step by step

**Postponed to 2026-09-15** (was Wednesday 2026-09-09 — corrected 2026-09-09; do not say
the old date on stage). The time limit and the rubric were **still not confirmed** as of
this project's last check — that message to the SPOC matters more with the extra runway,
not less; confirm it before finalizing which cut tier to rehearse. Plan for a
**three-minute measurement demo** inside whatever total slot we get, and rehearse it to
fit six minutes if the slot is longer.

**The slides are longer than this document has been assuming.** A word count of the five
scripts in `SIH26034-five-slides.md` puts them at about **five and a half minutes**, not the
three an earlier draft of that file claimed — the per-slide timings there were optimistic by
roughly forty percent and have been corrected. So slides plus this demo is about nine
minutes, a six-minute demo only fits a twelve-minute slot, and the deck now carries four
explicit cut tiers. **Pick the tier and the demo length together, once, from the confirmed
limit.** Cutting the demo while someone else rehearses the full deck is how a team runs out
of time mid-refusal.

The organising principle, and it is the whole reason this demo works: **the judge
supplies the ground truth, in the room, and the system is visibly able to fail.**
Anything we can pre-arrange, a judge is right to discount.

### Setup, before anyone walks in — 15 minutes

1. Mount the camera on the stand, fix the working distance, and **do not touch it
   again.** The scale calibration is only valid for the geometry it was measured at.
2. Photograph the calibration target and confirm the recovered `ppm` against the
   value from the last calibration. If it has moved, recalibrate before proceeding.
3. Confirm `ppm ≥ 30`. If it is below, tighten the field of view and recalibrate.
4. Lay out, in this order, left to right: the three graded targets face-down, an
   ordinary retail packet, the torch, the moulded bottle.
5. Run one throwaway measurement end to end. If anything is going to break, it breaks
   now and not in front of the panel.

### Run of show

| Time | Step | What you say |
|---|---|---|
| 0:00 | **The frame.** One sentence on the statute, one on the gap. | "The Rules specify character heights in millimetres. A photograph contains pixels. OCR can find the text, but pixel coordinates do not become millimetres without a physical scale — and nothing in an OCR pipeline supplies one." |
| 0:30 | **Show the scale reference.** Point at the calibration target in the frame. | "This is why we can answer in millimetres at all. Remove it and the software refuses — it does not guess." |
| 0:50 | **Declare the panel.** Type the panel area in, out loud. **New step, worth the twenty seconds.** | "The requirement is not one number. It comes from a table indexed on principal display panel area, and it runs from about 1 to 6 millimetres. This specimen is 40 square centimetres, which is the smallest bracket, so the requirement is 1.0 millimetres. We declare the area, we don't infer it — inferring it would mean segmenting the panel and guessing at the shape formula, and we would be hiding that guess inside a legal threshold." |
| 1:00 | **Measure the 1.30 mm target.** | Read out `h`, `U`, `TL`, verdict. "COMPLIANT — and note it reports how well it knows, not just what it decided." |
| 1:40 | **Measure the 0.70 mm target.** | "DEFICIENT. `h + U` is still below the 1 mm requirement for this bracket, so the shortfall survives our own uncertainty." |
| 2:20 | **Measure the 1.00 mm target — the refusal.** This is the demo. | "It will not call this one. The specimen sits inside our indeterminate band, so the correct output is REQUIRES_PHYSICAL_VERIFICATION. A heuristic would have given you a confident answer here. That answer would not survive a challenge." |
| 3:00 | **Hand the judge the torch.** Let them create the glare themselves. | "Break it. — That's a GLARE refusal. We would rather return nothing than return a number we cannot defend." |
| 3:30 | **Optional, if time.** The moulded bottle → `MEASURAND_UNDEFINED`. | "The Rules put a stricter requirement on embossed characters, and it applies in full. But embossed characters have no ink, so our 50%-of-ink edge criterion does not define an edge for them. The software refuses before it measures. Note the wording: the legal requirement applies, our measurement method is not validated for it. Those are different sentences and we will not let them collapse into 'not applicable'." |
| 3:45 | **Optional, and the sharpest thirty seconds available.** Re-run the *same* 1.30 mm specimen with the panel declared at 75 cm² instead of 40. | "Identical print, identical measurement, and now it refuses — `THRESHOLD_DISPUTED`. Our source reports a corrigendum altering one value in the height table, we have not read that corrigendum at source, and we cannot establish whether this bracket is the cell it alters. So the requirement here is unresolved and we are not going to pick a number for it. This is a system that declines because **the law** is unresolved, not because the pixels were bad, and I don't believe anything else in this room does that." |

**Neither candidate value is spoken in that step, and that is deliberate.** An earlier
version of this line said "the requirement is either 1.5 or 2.0 millimetres." Do not restore
it. We do not actually know that those are this bracket's two candidates — §3 records the
open reading that the corrigendum's 1.5→2.0 change belongs to some other cell entirely, in
which case naming them here asserts a dispute in a bracket that may not have one. "A value
in the table is altered and we cannot yet place it" is both true and stronger. The deck's
rule is the same one and says so explicitly: two numbers never leave anyone's mouth.

**No notification number is spoken in it either.** The script says "our source reports" and
"the height table", never an amendment number — the two audits of the ministry page disagree
about which amendment carries this table, so a number said here is a claim we cannot back,
and a judge who happens to know the right one has caught us being confident about the wrong
thing. The projected refusal follows the same rule: it names the instrument. If someone asks
which amendment, the answer is that the identifier comes from the same secondary source as
the table, our two audits disagree on it, and reading the Gazette is the first item on the
verification list.

**Say "target" or "specimen", never "known 1.30 mm sample".** Those three heights are what
we asked the press for, not values anybody has verified — see the third note in section 9.
What this sequence demonstrates is that **the decision bands are wired correctly and sit
where section 6 says they sit.** It does not demonstrate accuracy, and if a judge asks
whether it does, the answer is no, and the micrometer is how that changes.

> **This script is now longer than the slot, and that is a decision to make, not a
> problem to ignore.** Two steps were added on 2026-09-05 — the panel declaration at 0:50
> and the disputed-threshold re-run at 3:45 — and the timings above no longer add up:
> 0:30 and 0:50 are twenty seconds apart with a forty-second speech between them, and the
> whole thing now overruns four minutes. **The internal-round time limit is still unknown
> and is an unowned admin item (§16).** Get the limit first, then cut to fit in this
> order: the torch goes last because the judge is holding it, the panel declaration stays
> because everything downstream is a threshold that came from somewhere, and if the slot
> is three minutes then drop the moulded bottle and keep the disputed-threshold re-run —
> it makes the same point about declared boundaries and it is the one nobody else has.

> **Why 0.70 / 1.00 / 1.30 and not 0.80 / 1.00 / 1.20.** The old spacing was chosen
> against `U = 0.1513`, which left 0.049 mm of headroom outside each band edge. At
> `U = 0.16634` that headroom falls to 0.034 mm — less than the print tolerance you should
> expect on a sub-millimetre character, so a nominal 1.20 mm target could easily land
> inside the band and refuse when the script says COMPLIANT. Moving to 0.70 and 1.30
> restores 0.134 mm of headroom on each side, roughly four times the margin. **If targets
> have already been printed at 0.80/1.20, reprint them.** Print all five if the sheet is
> cheap, but demo three.

### If something goes wrong

**A refusal is not a failure.** If the system refuses when you did not plan for it,
read the refusal reason out loud and explain what it caught. That is the product
behaving correctly, and it is more convincing than the scripted path.

**A wrong number is a failure.** If a verdict looks implausible, stop, say the scale
calibration may have moved, and recalibrate on camera. Do not argue with your own
instrument in front of a panel.

**If the live path is not ready by Wednesday**, run on the synthetic scenes and say
exactly that: "this is the measurement engine on rendered targets; the camera path is
the last thirty lines and it is this week's work." An honest gap costs less than a
demo that quietly cannot be reproduced.

### Slides — five, no more

> **The narrative now exists as its own file: `SIH26034-five-slides.md`.** It carries the
> verbatim script, the per-slide timings, the lines not to say, and a sixty-second cut.
> **That is the document to show anyone outside the team.** This brief is the internal
> notebook and should not be handed to an evaluator — when an outside reviewer was given it
> with no other context, they graded the notebook as the submission and read every
> "modelled" and "not built" in §15 as a finding rather than as disclosure. The five slides
> below are the specification; the other file is the built thing. If they ever disagree,
> fix both.

1. **The gap.** The statute is in millimetres; a photograph is in pixels. One diagram.
2. **What everyone else builds, and why it cannot reach this.** No competitor named.
3. **The instrument.** Scale reference → sub-pixel edge location → uncertainty budget
   → JCGM 106 verdict with three outcomes. Label the third **REQUIRES_PHYSICAL_
   VERIFICATION**, and label the second **DEFICIENT** — *not* "FAIL", which is what an
   earlier draft of slide 1 said. If the word *traceable* appears anywhere, it must be
   attached to "architected for" and never left standing alone.
4. **A number with an uncertainty attached — and what follows from it.** Refusal is the
   *visible consequence*, not the claim: a flag prioritises inspection, a measurement
   supports enforcement. Do **not** title this slide "refusal is our differentiator." The
   differentiator is the budget behind the refusal; refusal is merely the part a judge can
   watch working.
5. **Status, honestly.** What is built, what is modelled, what is next. The eight budget
   terms and the sentence "all eight modelled, none measured" belong here, on the slide,
   in our own voice — not extracted from us under questioning.

Nothing from section 15 goes on a slide **as a claim.** Note that the bullet immediately
above deliberately puts a §15 item — the eight modelled budget terms — on slide 5, so the
rule cannot be a blanket ban and never was. It is claim versus disclosure: "all eight
modelled, none measured" is a §15 item stated as a disclosure, in our voice, and it belongs
there. "±0.17 mm accuracy" is the same item stated as a claim, and it is forbidden. Apply the
test in §15's preamble — if the sentence would survive the audience assuming we had verified
it, it is the wrong sentence.

## 11. Grand finale demo — what changes

If we get through, three things change and none of them is "more features."

**The modelled budget becomes a measured one.** Measure the glass stage micrometer,
characterise the ±0.08 mm convention systematic against it, correct for it, and
re-derive `U`. Only then does an accuracy figure become citeable. This single task is
worth more than any feature.

**The statutory table becomes complete and sourced.** Every bracket transcribed from
the Gazette, with the notification number and date recorded next to each row, and the
glyph-class axis wired through `measure()`.

**A survey replaces a demo.** Measure 30–50 real retail packages, report the
distribution of measured heights against thresholds, and report the refusal rate
honestly. Note the statistics: at n = 12 the relative uncertainty of a sample standard
deviation is 21.3%, so a small survey cannot tighten an uncertainty estimate — it can
characterise the *population*, which is the interesting result for a ministry.

Add, if there is time: the cylindrical correction actually implemented, an OCR
front-end supplying the declared net quantity so the operator types less, and a
per-package measurement record with the version hash in it.

---

## 12. The competitor, and how we talk about it

A live project called **SatyaLabel** identifies itself as built for SIH 2026 problem
ID SIH26034. It runs label photographs through vision-based OCR into a rule engine,
flags missing declarations by rule number, and lists a check labelled
"Rule 9(3) — Legibility & Font."

*Provenance caveat: this reached us second-hand through a screenshot. Nobody on this
team has looked at the product directly. Do that before relying on any of it.*

**What it costs us.** The novelty claim is dead. "Nobody has thought of checking
label compliance" was never true and is now visibly not true. Any slide that says
"first of its kind" comes off the deck.

**What it does not cost us.** A font check in a text pipeline still has no
millimetres. Which leads to the **five-minute check somebody should run today**: does
SatyaLabel ask the user for a fiducial marker, a coin, a ruler, a known package
dimension, or any camera calibration step? **If it does not, its font check cannot be
dimensional** — it is comparing pixel heights or inferred point sizes, and it cannot
be tested against a statutory millimetre threshold. Find out before Wednesday; the
answer determines whether we say "different layer" or "same layer, better executed."

**Rules of engagement.** Never name them from the stage. Never disparage them. If a
judge raises it: *"Yes — presence checking is solved, and we treat OCR as a component
we compose with rather than a competitor. The requirement nobody has closed is the one
written in millimetres."* That is generous, accurate, and stronger than a denial.

Note also that their citation is **Rule 9(3)**, which agrees with our own code
comments and disagrees with the Economic Times quote of an official citing Rule 7. We
do not know who is right, and the 2026-09-05 audits made it worse rather than better —
they contradict each other on which amendment introduced the panel-area framework. That
is section 3.3's job. Until it is done, **do not correct them and do not cite a number
either**; the only safe form is "the Rules" and "the minimum height table".

### Q&A preparation

**"How is this different from a legibility flag?"** — A flag prioritises inspection; a
measurement supports enforcement. Only one of those can go into a legal notice.

**"Isn't this just OCR?"** — OCR reads "500 g". We establish that the glyph is 1.0 mm and
not 0.7 mm. The first is a text operation, the second is a length, and pixel coordinates
do not become millimetres without a physical scale that no OCR pipeline carries.

Then concede the part that is true, because it is stronger than dodging it: **OCR is an
input to our system in two places.** It reads the declarations that tell us *which*
characters are the ones the law requires — the smallest character present is not the same
object as the smallest *required* character. And the width requirement, which we have not
built, cannot be applied at all without identifying the glyph, because the rule carries
per-glyph exceptions. So the honest line is *"OCR tells us what to measure; it cannot tell
us how tall it is."* That is a division of labour, not a rivalry, and saying it first is
better than being cornered into it.

**"What exactly are you measuring, and where does the law say to measure that?"** — The
hardest question available. Section 7.1 is the full answer; compressed: *"the statute
specifies a height in millimetres and does not specify an edge criterion. Ink has no sharp
boundary, so no dimensional measurement of a printed character is possible without
declaring one — including one made with a loupe and a graticule. We declare 50% of the
ink-to-substrate transition, and we carry the cost of that choice as a ±0.08 mm term, the
largest in our budget. That term is our sensitivity to the convention."* Do not improvise
past this point.

**"What is your accuracy?"** — "Our modelled expanded uncertainty is about 0.17 mm at
`k = 2`. All eight terms in that budget are modelled, not measured. Closing it against a
physical reference is the next step." **Never** say "our accuracy is 0.17 mm."

**"Is your scale traceable?"** — "Architected for it; not yet traceable in fact. The
scale path is explicit and a budget term is reserved for it, but the chain terminates in
an uncertified stage micrometer. Closing the last link is a calibration lab and a purchase
order, not a research problem." Do not claim traceability — and do not disown the
architecture either.

**"Why does it refuse?"** — Because the alternative is a number we cannot defend. If
someone points out that a confidence threshold does the same thing, concede it: declining
is cheap. Then point at what stands behind ours — a declared edge criterion, eight named
budget terms, and a decision rule taken from JCGM 106 rather than invented.

**"And where did the thresholds that make it refuse come from?"** — This is the follow-up
to the question above and it is the sharper one, so have the answer ready rather than
improvising a better-sounding version. *"Three of the eight numeric gates in the capture
path are derived from the uncertainty budget — I can show you the arithmetic in a comment
above each one. Five are placeholders we have not derived yet, and the file says which are
which; a self-test fails if anyone adds a gate without classifying it. Two of the five we
can close on the rig, and one of them isn't an optical question at all — it's how long the
rig stays put."* Then stop. **Do not upgrade "placeholder" to "empirically tuned"** — tuned
is the worse answer, not the better one, because a tuned limit is a limit fitted to the
outcome we wanted, and the whole pitch is that our numbers are not fitted to outcomes. The
honest split is a stronger answer than a clean one would be, and if the panel takes it as a
weakness, they have taken every unmeasured number in the room as a weakness except ours,
which we named.

**And the escalation of that, which is the one to have ready: "if five of your capture gates
are placeholders, are your eight budget terms round numbers too?"** They are round, and the
answer is that roundness is not the defect being asked about. Each term names a physical
mechanism and states an allowance for it — ink-edge asymmetry, lens distortion at field
position, fiducial localisation — and a modelled allowance is quoted to the precision the
model supports, which is one or two figures. What none of them is, is *measured*, and that
is the gap slide 5 puts on the screen in our own words. **Do not answer this one by
defending the numbers.** Answer it by naming what closes them: one graduated glass artifact
and an afternoon on the rig closes the dominant term, and until that is done the honest
description of the 0.17 is an engineering estimate, not an instrument specification.

**"Which rule is it?"** — "The height table has moved between rule numbers across
amendments, so we cite the provision from the Gazette copy we transcribed, and we
record the notification number next to it." If the transcription is not done yet, say
the requirement in millimetres and do not quote a rule number at all. **A wrong
provision number in front of a Consumer Affairs judge is the most expensive error
available to us.**

**"What about the H&M case?"** — Cite the holding and nothing more: *"the H&M case,
Delhi High Court, on the pre-packaged commodity definition."* **Give no provision number
and no year.** Nobody on this team has read the judgment, so neither is verified; the
provision number that used to sit in this answer has been moved to §15 and stays there
until someone reads the judgment. The rule from the previous answer applies with more
force here, not less, because this citation is volunteered rather than demanded: when you
have not read the judgment, cite the holding, never the provision number. This answer
previously stated the number and then told you never to state a number — if you
remembered the number and not the warning, that is the defect working exactly as a defect
works.

**"Can it handle bottles / embossed packs?"** — Answer with section 7 as written: flat
is validated, cylindrical is designed not built, relief we refuse and here is exactly
why the measurand is undefined.

**Do not quote:** any enforcement statistic. The "3.5 lakh verifications, 1.2 lakh
prosecutions" figure implies a 34% prosecution rate, which is implausible for any
inspection regime, and "verification" in legal metrology is a term of art for the
stamping of weighing and measuring instruments — a different population entirely.

## 13. The four-day plan, now a three-day plan

**Written Saturday the 5th as a four-day plan. It is now Sunday the 6th, so three working
days remain: today, Monday 7th, Tuesday 8th, demo Wednesday the 9th.** An earlier version
read "Saturday 6th, Sunday 7th, Monday 8th": the weekdays were off by one against the
calendar and it listed three days while claiming four. **2026-09-09 is a Wednesday, so the
8th is a Tuesday and the 5th was a Saturday.** Both facts are recorded because the same
error twice would be a pattern. Do not renumber this plan again — **re-date the heading,
never the jobs**, or the audit trail of what was promised on which day is lost.

Seven jobs for a team of six, so one person carries two — job 1 and job 1b belong
together anyway, since the same person will have the Gazette open.

**The Owner column below is filled with role slots, not names, because nobody but the team
can put a name in one.** The slot text is deliberately ugly. **Print rule: no version of
this table goes on a screen, into a submission, or in front of a mentor while any slot
still reads `_____`.** A blank owner column reads as a plan; a plan with six names on it is
a commitment, and the two jobs most likely to sink us — the Gazette read and the admin —
are precisely the ones that fail quietly when they belong to everybody.

| # | Job | Owner | Done when |
|---|---|---|---|
| 1 | **Settle the two disputed cells** from the Gazette PDF and its corrigendum. One hour, not two — the table is transcribed, this is verification. **Starts today.** | ▸ **STATUTE** `_____` (also owns 1b) | All six questions in §3.3 answered in writing, the table screenshotted from a Gazette source, and notification / publication / commencement dates recorded as three separate facts |
| 1b | **Run `self_test()` in `lm_legal_model.py`, then wire the three call sites.** The v7.1 patch is applied and the file has been run — **so this job is smaller than it was, but not finished**: five of its ten regression assertions were never exercised or cannot be read off the demo output, and one is contradicted. Add the five print-only lines in §13a and re-run before touching the legal layer, so that a change in the measurement numbers can only have come from the wiring | ▸ **LEGAL LAYER** `_____` (same person as job 1) | `lm_legal_model.py`'s self-test prints zero failures; §13a's ten items all resolve; every number in the v7.1 baseline run reappears unchanged after the prints are added; and a declared panel area of 40 cm² produces `TL = 1.0 mm` through the real code path rather than a constant |
| 2 | **Build the live-capture path** (~30 lines): frame grab, fiducial detection, rectification, ROI, `ppm` | ▸ **CAPTURE PATH** `_____` | A real photograph produces a verdict, and `PLANARITY` / `NO_REDUNDANCY` can actually fire |
| 3 | **Assemble the rig and calibrate.** Mount, illuminate, print the **0.70/1.00/1.30** targets, measure the stage micrometer at field **centre and at all four corners**, photograph the scanned reference sheet **on the rig**. **Shim the graticule up to the packet's printed face — see §6a.** The scale artifact and the characters must sit in one plane; a graticule lying on the baseboard beside a 2 mm packet at 150 mm standoff is measuring a plane 1.33% away from the one the print is in | ▸ **RIG & CALIBRATION** `_____` | `ppm ≥ 30` confirmed, the webcam-versus-scanner loop closed, the spread across the five micrometer positions recorded as a *measured* `lens_distortion_field_position` term, **and the graticule-to-print height difference measured with the calipers and written down** — the number that matters is that difference, not the standoff, and if it is under 0.2 mm the fiducial-plane error is below 0.15% and needs no budget term |
| 4 | **Refusal rehearsal** on 10–15 ordinary retail packets. **First decide, and write down, whether `expected_glyphs` counts punctuation and currency symbols** — `₹99.00` is 6, 7 or 8 depending on the answer, and an unwritten rule becomes a wrong count under pressure. Recommended rule: **count every ink mark inside the ROI — letters, numerals, the currency sign, the decimal point; never whitespace**, which makes `₹99.00` exactly 6 and needs no judgement from the operator. Then expect `GLYPH_COUNT` to be the offender: strictest check, tests `!=` so a merge from tight kerning refuses exactly as a split does, and it depends on a human typing a count under pressure | ▸ **REFUSAL REHEARSAL** `_____` | The counting rule is written on the Q&A card; every refusal in the run is attributed to a named gate; and for each gate that fired, its kind is **read off `_GATE_PROVENANCE` in `lm_capture.py`** — that ledger is the record, not this document — with the firing and whatever was decided written up here and, if a placeholder moved, in §15. Derived stands; a placeholder may be set, but only from a physical argument written down next to the new value. **The rate is recorded, not targeted** — see risks 4a and 4b, which exist because a "below 10–15%" criterion is satisfiable by loosening limits, and that is the one repair not available to us. Also record the workflow identity `t/(1 − refusal rate)`: 45 s at a 30% refusal rate is a 64 s workflow, and that cost is a fact about the demo to state, not a reason to move a gate |
| 5 | **Five slides and the Q&A card.** Nothing from §15 appears as a claim anywhere — see §10 for the claim-versus-disclosure test, because slide 5 discloses two §15 items on purpose. The narrative edits are done — slide 3 has the panel-area row, slide 4 frames 33% as the worst cell, slide 5's table carries the second-hand rule table. What is left is **decisions, not writing**: pick the cut tier from the confirmed time limit, resolve slide 5's two conditional cells (camera path, legal layer) before anything is printed, and drop the numeric capability ladder from anyone's spoken version | ▸ **SLIDES & Q&A** `_____` | Rehearsed twice at the chosen tier, inside the confirmed limit, with §12 answers said out loud |
| 6 | **Admin** — see §16. Unowned as of this writing, and it is the job that can disqualify us | ▸ **ADMIN / SPOC** `_____` | Every line in §16 is ticked |

Jobs 1 and 6 are the ones that fail silently if nobody is named — which is why they now
carry the two ugliest slots. **Put six names in this table today.** Job 1b is on the
critical path for the slides, because slide 3 cannot show a panel-area step that the code
does not perform, and two cells on slide 5 are gated on its self-test being re-run in the
form being shipped.

---

## 13a. The v7.1 regression list, audited against the first real run

**v7.1 has been run.** `VERSION = "7.1-measurand-refusal-2026-09-05"`, sha256
`716dc28e…c389f`, numpy 2.4.4 on Python 3.12.3. **Record that hash somewhere durable**: it
is the only way a later round can tell whether the file that produced the numbers below is
the file in the demo laptop. Everything in this section is read off that run's output. It
does not extend to `lm_legal_model.py` or `lm_capture.py`, which remain unrun.

The patch document ends with ten assertions to run before the patched file goes near the
demo. Scored against the output:

| # | Assertion | Result |
|---|---|---|
| 1 | `h` still `1.402` **to every decimal** | **Cannot be checked from this output.** Patch 3 cut the display to 2 s.f., so it prints `1.40`. Consistent with 1.402, not a confirmation |
| 2 | `category=None` → `CATEGORY_NOT_DECLARED` | **Pass**, printed verbatim |
| 3 | unknown string → `CATEGORY_UNKNOWN`, not `MEASURAND_UNDEFINED` | **Not exercised.** The demo runs `general`, the formed category and `None` — nothing else |
| 4 | self-checks pass; RMS `~2.7e-13` / `0.353 px` | **Pass, exactly**: `2.716e-13` and `0.353` |
| 5 | formed → `BAND_REFER` + `MEASURAND_UNDEFINED`, no `h`/`U`/`TL` | **Pass** |
| 6 | `allow_undefined_measurand=True` → a verdict | **Not exercised** |
| 7 | `expanded()` → `0.16634` | **Pass, exactly** |
| 8 | headline `0.17`, `all_measured()` False | **Pass, inferred.** The eight `[modelled]` markers and the "do not quote the raw figure" suffix are what a False `all_measured()` produces; the boolean itself is not printed |
| 9 | `effective_support_mm ≈ 0.067` at `ppm = 30`, floor-limited warning fires | **Contradicted, or at best ambiguous.** The sampling sweep marks FLOOR-LIMITED at 8, 12, 16 and 20 px/mm and stops. 30 px/mm carries no marker — while patch 4's own worked table says 0.02 mm at 30 px/mm rounds to 1 px, is floored to 2, and *is* floor-limited at 0.067 mm. Both cannot be true |
| 10 | `governing_glyph_index` present, at the minimum | **Not verified.** The demo prints no diagnostics |

**Four exact passes, one inferred, two unexercised, two unverifiable, one contradicted.**

**The pattern is worth more than the score.** Every assertion that passed is one the demo
was already printing. Every assertion that did not is one that needed a print or a call the
demo does not make. The list was written as a set of assertions and the program was run as a
demonstration, and **a demonstration answers the questions it was already answering.** This
is the same shape as the defect where a fix is correct, tested and not on the shipped path:
here the *test* is correct and not on the run path.

**The repair is five additions and none of them changes a measurement.** Dump `diag["glyph_extents_mm"]` and
`diag["governing_glyph_index"]` at full precision (items 1 and 10); add two
`measure_with_category` calls, one with `"banana"` and one with the formed category plus
`allow_undefined_measurand=True` (items 3 and 6); print `diag["effective_support_mm"]` in
the sampling sweep instead of only the FLOOR-LIMITED marker (item 9); print
`bud.all_measured()` (item 8). **None of these touches a measurement path**, so the run just
obtained stays valid as a baseline and every number in it should reappear unchanged. If any
number *does* move, the print was not the only thing that changed and you should stop.

**Item 6 is the one to do first**, ahead of item 3, even though item 3 is the one the patch
document flagged as its worry. `allow_undefined_measurand=True` exists to produce a height
for a category the instrument has just finished declaring unmeasurable. An escape hatch from
a refusal is worth more testing than the refusal, not less, and this one has never been
called.

**Item 9 must be resolved before the sampling table is shown to anyone**, because the
30 px/mm row is the row that carries `min_px_per_mm`, and a disagreement about whether that
row is floor-limited is a disagreement about whether the engineering target is doing what it
was chosen to do.

---

## 14. Risks, in the order they are likely to hurt

**1. The two disputed cells stay unresolved, and someone quotes a number anyway.** The
old form of this risk — an untranscribed table — is closed. The new form is worse in one
specific way: we now *have* numbers, from an aggregator, which makes them much easier to
say out loud than an admitted blank was. If the 50–100 cm² threshold reaches a slide in
either form, and a Consumer Affairs judge holds the corrigendum, the project's entire
credibility argument inverts in one sentence. *Mitigation: job 1 today; the `disputed`
flag in the code, which refuses rather than guesses; and the standing rule that no
threshold from this table is spoken as settled law until the Gazette confirms it.*

**2. Demo polish versus demo depth, judged by non-specialists.** The competitor has a
shipped web application. We have a Python file and no capture path. On a rubric where
presentation carries as much weight as technical merit, a clickable interface can beat
a deeper idea. *Mitigation: the physical rig **is** our polish.* A camera on a stand,
a judge holding a torch, and a system that visibly declines to answer is more
memorable than any web UI — and it cannot be screenshotted by a competitor. Build the
rig for the room, not the interface for the laptop.

**3. The live path is not ready.** Then the demo runs on synthetic scenes and the
refusal checks that need real geometry cannot fire at all. *Mitigation: job 2 is
thirty lines; it is the single highest-value hour of code left in the project.*

**4. Refusal rate too high on real packets.** A demo that declines on everything the
judge hands over reads as "it does not work," not as rigour. *Mitigation: job 4,
measured in advance on real stock, with `GLYPH_COUNT` as the predicted offender —
**and read 4a and 4b before acting on that mitigation**, because the obvious response to
a bad rate is the one response that is not available to us.*

**4a. The mitigation for risk 4 is itself the most dangerous instruction in this
document, so read this before doing job 4.** On Tuesday night, with a rate that looks
bad, the only lever within reach is loosening a limit — and loosening limits until the
refusal rate is comfortable is *tuning*, which makes slide 4's central boast ("an
uncertainty that was derived rather than tuned") false in the room where we say it. The
rate is not the deliverable. **The attribution is.** For every refusal, record which gate
fired; then, for every gate that fired, record which of two things it is:

- **A gate with a derivation.** It stands. If it fires on median stock, the finding is
  that our scope is narrower than we thought, and the honest response is to *say so* —
  narrow the claim, or fix the rig that violates the precondition. Not to move the number.
- **A gate that is a placeholder** — a value nobody derived, set to something plausible to
  get the file to run. `lm_capture.py` now names its own: `MIN_PX_PER_MM`,
  `SCALE_SESSION_FRAMES`, `SCALE_SPREAD_REJECT_REL`, `FOCUS_FLOOR_FRACTION` and
  `_SCALE_STALE_SECONDS`, five of its eight numeric gates. In v7, `max_illum_gradient = 0.10`
  is the flagged case — decorative, never fires before `GLYPH_COUNT` does. Setting a
  placeholder deliberately is not tuning, it is finally doing the work — **but it must be set
  from a physical argument, and the argument has to be one that would have been just as valid
  before you saw the rate.** Write the argument down next to the new value.

**Do not confuse *loose* with *underived*.** `ABS_MIN_BASELINE_PX = 36.0` is loose — its own
comment says it protects nothing plausible and catches one gross misuse of the artifact — and
it is nonetheless *derived*, from a stated negligibility criterion. A loose derived gate may
not be moved to improve a rate any more than a tight one may. The question is never how much
slack a number has; it is whether an argument exists for the number you have.

**The test, and it generalises past this project: a limit you would not have chosen before
seeing the outcome is not a limit, it is a fit.** Applied honestly this means a run can end
with a high refusal rate and nothing changed, and that is a legitimate outcome — see 4b.

**4b. `GLYPH_COUNT` is the predicted top offender and also the one gate where loosening
does the most damage.** It is not a physical precondition; it compares the operator's
typed count against the detected count, so if it fires the fault is in the detector, in
the human, or in the counting rule — and none of those is repaired by relaxing the
comparison. Relaxing `!=` to a tolerance would silently accept a merged or split glyph,
and a merge that spans an ascender and an x-height letter reports the *taller* box, biasing
toward COMPLIANT, which is the one direction an enforcement instrument must not err in.
There is a real refinement available — replace count-equality with a per-span integrity
check that refuses only when the reconciliation could move the reported statistic — and it
is emphatically not a four-days-out change. **So: do not touch it before Wednesday.** If it
dominates the run, that is presentable as it stands: the gate is conservative by
construction, the run tells us what it costs us on ordinary stock, and the refinement is
named. A high rate attributed to a named, defensible gate is a result. A low rate obtained
by moving gates is a liability that a single question destroys.

**5. An accuracy claim gets challenged.** All eight budget terms are modelled. If we quote
0.17 mm as measured performance and a metrologist on the panel asks what reference it was
measured against, we have nothing. *Mitigation: §15, and the phrasing in §12.*

**6. A wrong rule number, said with confidence.** *Mitigation: state the requirement in
millimetres; cite provisions only from a transcribed source.*

**7. The problem statement gets claimed out from under us**, or we miss the portal
deadline, or the internal shortlist turns out not to include SIH26034 on the software
track. *Mitigation: §16, and it needs an owner today.*

**8. The pattern behind risks 1, 5 and 6.** Our own recorded defect list says the
**model of the rules is the least-audited layer, and the only one that can turn a
correct measurement into a wrong verdict.** Three separate review rounds each found a
missing axis in it — package category, then glyph class, then the relief measurand.
The ordering that matters is: (1) is the threshold right, (2) is the measurand the
regulated quantity, (3) is the measurement good — **and 3 has been getting the
attention that 1 and 2 needed.**

A related trap worth naming, since we walked into it twice: two competent readers of
the same layered statute reached opposite conclusions and each reported "definitive."
Before arbitrating a source conflict, ask **"what breaks if I stay agnostic?"** Here,
nothing did — `index_by` and `index_value` are already runtime inputs.

---

## 15. The unverified list — nothing here may be stated as a claim

A few of these items do reach a slide, and should: `U(k=2) ≈ 0.17 mm` is on slide 5 and the
placeholder split below is answerable in Q&A. The rule is not silence, it is **standing**.
Everything in this section may be said only as a disclosure — *modelled, not measured*;
*placeholder, not derived*; *not yet sourced to a Gazette* — and never as a specification, a
tolerance, or a settled fact. If a sentence would survive the audience assuming we had
verified it, the sentence is wrong.

**Legal claims not yet sourced to a Gazette or ministry document:**

- The rule number for the height provision. Rule 7 versus Rule 9(3), unresolved.
- Whether the numeral table is indexed by declared net quantity or by principal
  display panel area. **Updated 2026-09-05: panel area now has the stronger support** — an
  external reviewer with web access reports Rule 7(5), inserted by the 2016 amendment,
  giving PDP-area formulae per package shape, and a Table-I keyed to that area. **It is
  still not settled, because the table itself was sourced from a Ministry FAQ and from the
  consolidated book that the same reviewer says is stale.** A FAQ is not the statute. The
  most load-bearing object in this project has still not been read from a primary Gazette
  document with a known date.
- Every numeric bracket boundary in either table. Nobody has transcribed them.
  **Updated 2026-09-05: values now exist but are not verified.** A second corpus audit gives
  five PDP-area brackets — `A ≤ 50 cm²`, `50 < A ≤ 100`, `100 < A ≤ 500`, `500 < A ≤ 2500`,
  `A > 2500` — with ordinary heights 1.0 / 1.5 / 2.5 / 4.0 / 6.0 mm and formed heights
  2.0 / 3.0 / 4.0 / 6.0 / 6.0 mm, attributed to the 2017 amendment G.S.R. 629(E).
  **Two cells are actively disputed and must not be quoted:**
  - The **50–100 cm² ordinary cell** is either **1.5 or 2.0 mm.** The same audit says the
    corrigendum to G.S.R. 629(E) changed a value from 1.5 to 2.0, and the only 1.5 in the
    table is that cell — so either the table shown predates its own corrigendum, or the 1.5
    being described sat elsewhere. Both readings are supported by the source we have. This is
    a 33% difference in the threshold for a very common package size.
  - The **`A > 2500` row carries 6.0 mm in both columns**, the only bracket where ordinary and
    formed collapse to the same value. Column ratios run 2×, 2×, 1.6×, 1.5×, 1×, which is
    consistent with the formed column capping at 6.0 — but it is also exactly what a
    carried-down transcription error looks like.

  Encode the table with those two cells flagged. Resolving them needs the Gazette PDF of
  G.S.R. 629(E) **and** its corrigendum, read together, with both dates recorded.
- Whether one table or two are currently in force. **The likeliest reconciliation, and the
  first thing to check:** the general-declarations table is indexed on PDP area while the
  net-quantity declaration carries its own separate size requirement keyed to quantity — two
  tables with two different index variables, which would explain why two careful readers
  disagreed and both had textual support.
- **Rule 7(3), a width requirement, discovered 2026-09-05 and not implemented at all.** A
  minimum character width relative to height, with exceptions for certain glyphs. Unverified
  as to the exact fraction and the exception list. Note what it implies: per-glyph exceptions
  mean the character must be *identified* before the rule can be applied, so this is not a
  drop-in second axis on the existing engine.
- **Whether the letters-versus-numerals axis exists at all.** The same reviewer says the
  statute reads "numerals and letters" as one class and that there is no separate glyph-class
  threshold. That is a claim that something does *not* exist, from secondary material — the
  weakest available warrant for deleting a planned feature. Left open deliberately.
- **How current our reading of the corpus is.** The DoCA page lists 35 documents under PCR
  2011 running to the **Third Amendment Rules 2026 (G.S.R. 418(E), 29 May 2026)**. We had
  been reasoning from 2011/2017/2021 material. Amendment currency is now a known gap rather
  than an unknown one.
- The >25 kg provision — **probably a draft open for comment, not a notified
  amendment.** Downgraded on review.
- ISO/IEC 24790's exact scope and the pan masala exemption. Not reached. **The 2025
  medical-device amendment is no longer unreached** — G.S.R. 778(E), October 2025, provides
  that medical-device packages follow the Medical Devices Rules 2017 for declarations, height
  *and* width. The date is unverified to within one day (the source gives both the 23rd and
  the 24th), so state the month and year only.

- **The H&M case citation.** The case name and the court are safe at the level §12 states
  them. Two specifics are **not** verified and are quarantined here: the year *2023*, and
  the charged provision *Section 13(3)(b)*. Both were sitting in the §12 answer as bare
  assertions until this revision. Nobody has read the judgment. If someone does, verify
  the provision against the Legal Metrology Act, 2009 itself — a subsection cited from
  memory is the single easiest thing in this brief to be confidently wrong about, and it
  is the one place where being wrong is unrecoverable in front of a Consumer Affairs
  judge.

**Measurement claims that are modelled, not measured:**

- `U(k=2) ≈ 0.17 mm` and **all eight** of its terms. **The arithmetic is no longer
  hand-only: v7.1 has now been run and prints `U(k=2) = 0.17 mm (2 s.f.; raw 0.16634)`,
  matching the hand computation to five decimals** — which retires the old caveat that the
  program had not been re-run since the budget changed. What that execution does *not* do is
  change the standing of the figure by one inch. All eight terms still print `[modelled]`.
  The run confirms we can add up eight numbers correctly; it says nothing about whether the
  eight numbers are right. **Arithmetic verified, inputs still modelled** — and it is the
  inputs a metrologist will ask about.
- Every figure in §6's decision-band table, which inherits from that. The band edges
  0.834 mm and 1.166 mm are now execution-confirmed in the same narrow sense: they are
  `1.000 ∓ 0.16634`, and the run's conformity demo lands `h = 1.40 mm` in COMPLIANT against
  `TL = 1.00 mm` exactly as the table predicts.
- The ±0.08 mm convention systematic — and the split between its two causes, edge
  criterion versus cap/x-height ambiguity, which nobody has separated.
- The three newest terms: `lens_distortion_field_position` (0.010),
  `defocus_psf_asymmetry` (0.005) and `fiducial_localisation` (0.0005). These are
  order-of-magnitude estimates with stated reasoning, of exactly the same standing as the
  original five. Their purpose is to stop the budget from *looking* complete while it is
  not.
- The superseded **0.1513 mm** figure, which survives in §8's run-log column only because
  that is what v7.0 actually printed. Do not carry it forward.

**Thresholds that are chosen, not derived:**

This group is unverified in a different way from the one above. A modelled budget term is an
estimate of a real quantity, so measuring that quantity confirms it or moves it. A chosen gate
is mostly not an estimate of anything: no measurement tells you that 12 frames is the right
number of frames. What a measurement can do is supply the *argument* — measure the
frame-to-frame correlation and the independence assumption behind `SCALE_SPREAD_REJECT_REL`
either holds or does not — so the fix here is an argument that a measurement may support, and
never a rate that a threshold was moved to satisfy.

- **Five of the eight numeric gates in `lm_capture.py`** are filed `PLACEHOLDER` in that
  file's `_GATE_PROVENANCE` ledger: `MIN_PX_PER_MM`, `SCALE_SESSION_FRAMES`,
  `SCALE_SPREAD_REJECT_REL`, `FOCUS_FLOOR_FRACTION` and `_SCALE_STALE_SECONDS`. Each carries
  its own honest reason string in the ledger; read those before quoting any of them. The
  other three are `DERIVED` from stated budget allowances.
- The distinction is machine-checked: `self_test()` fails if a numeric constant is missing
  from the ledger, so a gate cannot be added on Tuesday night without someone deciding which
  kind it is. **That check does not audit whether a reason is any good** — no test can — so a
  passing self-test is not a claim that any of the eight reasons has been reviewed.
- `_PDP_AREA_SANITY_MAX_CM2` in `lm_legal_model.py` is also chosen, and is the one
  engineering gate in an otherwise statutory file. Its comment there gives the reason it is
  defensible anyway: the choice is insensitive across four orders of magnitude, and it errs
  in the harmless direction on purpose.

**On saying this out loud:** this group is *disclosable*, in the same way the eight modelled
budget terms are — slide 5 states those openly and is stronger for it. Say the split first;
it survives being volunteered far better than being extracted, and §12 has the scripted
answer. What must not happen is one of these five numbers appearing on a slide as a
tolerance, or the word *tuned* being used for any of them. **Placeholder is the honest word
and it is also the safer one; "empirically tuned" sounds better and describes a worse
machine.**

**Words we have not earned yet:**

- **"Traceable"**, standing alone. Permitted only as *architected for traceability*, or
  *traceable by construction, not yet traceable in fact* — see §4 and §9. The chain
  terminates in an uncertified micrometer.
- **"Validated"** applied to anything but flat printed stock, and even there only to the
  decision logic, never to the accuracy.
- **"Accuracy"** as a property of this system, in any sentence, until a reference standard
  has been measured on the rig.

**Retracted, and not to be revived:** the `√(2 ln N)` mechanism; the
`0.0038 + 0.0030/C` exposure fit; the rectangular-bar-degeneracy explanation for
q5 ≡ p95; the p95-then-max convention rankings; the −0.07 mm glare prediction; the
description of a self-test `sd` as a Type A budget term; "the rig is quoted at
25.6–40 px/mm," which was unsourced; and **"no operation in the text domain produces a
length,"** which is false — a scale factor can be recovered from any object of known
size, so the defensible claim concerns a missing *scale reference*, not a missing
capability.

**Also:** `max_illum_gradient = 0.0319` is not to be wired in. And the phrase "goes
beyond simple OCR" is true socially and false dimensionally — it concedes the frame we
want to reject.

**Added 2026-09-06 — four gaps in the measurand and the budget, all of them ours:**

- **`convention_bias_mm`'s value.** A correction subtracted from every height the instrument
  reports, and its magnitude is in no document — not here, not the deck, not the patch. §6
  publishes the 0.005 mm *residual* of a correction whose size is unpublished. Read the
  default off the file, write it here, print it beside the convention line in the report.
  **Zero is an acceptable answer and still has to be written down.**
- **The artifact-pitch term.** The graticule's own graduation pitch propagates into
  `px_per_mm` as a pure scale error. Its value comes from a calibration certificate we do not
  have, for an artifact we have not bought. **This is not a modelled term — it is a term with
  no value at all**, and it must not be described as small until the certificate says so.
- **Round-letter overshoot, 1–1.5% of character height.** `O`, `0`, `8` and the apexes of
  `A`, `V`, `W` sit above the cap line by design. On a 1 mm character that is 0.010–0.015 mm,
  the size of two terms that *are* in the budget, and it is in neither the eight nor this
  list until now. See §7.1a — it interacts with the governing-glyph defect and cannot be
  costed as a fixed half-width.
- **The budget's flat-model error away from 1 mm.** Three of the eight terms are physically
  relative and are stored as absolute, so every `U` the program prints for a requirement
  above 1 mm is optimistic — 8.3% versus an honest 9.2% at a 2 mm requirement, 2.8% versus
  4.8% at 6 mm, with a floor of about 3.0% that the flat model hides entirely. §6a has the
  derivation and the verdict-flip example. **`U(k=2) = 0.17 mm` remains correct as stated,
  because it is stated at a 1 mm requirement**, which is the only bracket the internal round
  touches. Anyone quoting `U` for a larger bracket is quoting a number the physics does not
  support.

## 16. Admin checklist — unowned, and it can disqualify us

- [ ] Confirm SIH26034 appears on the college's **software** track shortlist.
- [ ] Claim the problem statement with the SPOC. Check the apparent **three-teams-per-
      college** cap and the **500-ideas-per-problem-statement** freeze — both are
      second-hand and both are first-come.
- [ ] Confirm the internal round's **time limit** and **rubric**. Our working
      assumption is Idea / Technical / Presentation / Q&A at 25 marks each with
      relevance to the problem statement scored separately. **Unconfirmed.**
- [ ] Resolve the portal deadline: **20 or 30 September.** Two sources disagree.
- [ ] Confirm team composition requirements against the current SIH guidelines rather
      than last year's memory, including any mandatory-member rules.
- [ ] Team registration and idea submission on the portal, with the abstract matching
      what we actually demo.

---

*Nothing in §15 may be asserted as a claim — on a slide, in a script, or in an answer. Some
of it is deliberately disclosed in all three, which is a different act; §15's preamble and
§10 give the test. Everything else in this document is hand-checked, measured, or written —
and "written" is not "built": both modules are unrun, so read §8's own warning before calling
any of it working software.*

