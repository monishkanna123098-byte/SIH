# SIH26034 — the five slides, and what you say over them

**What this document is.** The presentation narrative for the college internal round,
**postponed to 2026-09-15** (was Wednesday 2026-09-09 — corrected 2026-09-09, do not say
the old date out loud). Five slides, a verbatim script, and the lines not to say. It is
the *outward-facing* document.

**Why it exists, stated plainly because it matters.** `SIH26034-team-brief.md` is an
internal notebook. It contains an uncertainty budget, an unverified-claims list, a
defect log and a patch queue, because that is what an honest internal document contains.
When an outside reviewer was handed the brief with no other context, they graded **the
notebook as the submission** and scored it 5.5/10 — every "modelled", "not built" and
"unverified" read as a weakness rather than as disclosure. That was not a flaw in the
brief. It was the absence of this file. **Show this one. Keep that one.**

**Time, and the earlier numbers in this file were wrong.** The per-slide timings an earlier
draft carried were guesses, and they were optimistic by roughly forty percent. Counted as
words and divided by 150 a minute — a realistic rate for someone standing up, not a
read-aloud rate — the five scripts run about **30, 55, 90, 80 and 80 seconds: five and a
half minutes**, not three. With the live demo in §10 of the brief at about three and a half
minutes, the full thing is **about nine minutes.** And **nobody has confirmed the internal
round's time limit** — that is one message to the SPOC and it is still unsent.

A team that rehearses against a wrong number finds out at the podium, so rehearse against
these and know which tier you are giving before you stand up:

- **Ten-minute slot** — everything as written, ~9:00.
- **Seven-minute slot** — drop slide 2, drop slide 4's *first* spoken paragraph, drop slide
  5's second. That is ~3:20 of slides and ~6:50 in total. Each of those three cuts is
  justified where it sits; none of them removes a claim.
- **Five-minute slot** — slides 1, 3 and 5 only, with slide 3 cut to its first and last
  paragraphs and slide 5 to its first. ~2:05 of slides, demo trimmed to ~2:30, ~4:35 total.
- **Three minutes or less** — the sixty-second version at the end of this document, then the
  refusal, and nothing else.

The one thing that never gets cut in any tier is the live refusal.

---

## The one sentence everything hangs on

> The Rules specify character heights in **millimetres**. A photograph contains
> **pixels**. OCR can locate the text, but pixel coordinates do not become millimetres
> without a physical scale reference — and nothing in an OCR pipeline supplies one.

Say it in that order: statute, photograph, gap. If you only get one sentence out in the
whole pitch, this is the one.

**Do not upgrade it.** An earlier draft said "no operation in the text domain produces a
length." That is false and anyone who has used an OCR library can refute it in one
breath — recover a scale from a barcode of known width and you have millimetres. The
claim is about a **missing scale reference**, not a missing capability. The narrow
version is the one that survives contact with a judge who knows the field.

---

## The one exception to "never say a number", stated so nobody has to improvise it

The standing rule in this project is that no statutory threshold is spoken as law: say "the
Rules" and "the minimum height table", never a value and never a rule number. The reason is
that our table is transcribed from a secondary aggregator and nobody here has read the
Gazette original.

But the deck as written does put two numbers in the room — slide 3 says the requirement runs
"from about one millimetre on a small packet to about six on a large one", and slide 4 draws
its decision bands against a 1 mm limit. That is deliberate, and it is bounded by three
conditions. The values are the **ends** of the range, not the contested middle. They are
spoken as a **range**, never as a lookup for a named bracket. And slide 4's bands are
illegible without a limit to draw them against, because what that slide is showing is the
decision arithmetic, not the statute.

**If anyone asks where the 1 mm came from, the answer is one sentence and you should want
the question.** It is our transcription of the table from a secondary source, we have not
yet checked it against the Gazette, and that check is sitting in the Next column of slide 5.
This costs nothing to say because slide 5 says it anyway — and a team that volunteers the
provenance of its own numbers is doing the thing the whole pitch claims to be about.

**Never said, in any version, under any question:** a value for any middle bracket, either
candidate value for the contested cell, or a rule number.

**The test to apply at the podium, when you are unsure whether a number is safe:** am I
stating what the law requires, or what our instrument was measured against? The first needs
a primary source we do not have. The second needs only a specimen on the table.

---

## Slide 1 — The gap

**On the slide:** one diagram. Left: a photograph of a label with a pixel grid over it.
Right: the statutory requirement written as `? mm`. An arrow between them with a question
mark on it. Title: *A requirement in millimetres, a photograph in pixels.*

**Write `? mm`, not `1 mm`.** An earlier version of this slide showed `1 mm` as though it
were the requirement. It is not — it is the smallest-panel row of a table that runs to
about 6 mm, and a judge who knows that will read the slide as evidence we have not read
the Rules. The question mark is also better rhetoric: the requirement being a *lookup*
rather than a constant is the point slide 3 makes.

**What you say, ~30 seconds:**

> The Legal Metrology Packaged Commodities Rules require the mandatory declarations on a
> package — net quantity, price, the packer's name — to be printed at or above a minimum
> character height, and that height is specified in millimetres. Enforcement happens in
> the market, on shelf stock, where an inspector holds a packet and has to decide whether
> the printing is legal. There is no field instrument for that. The Rules impose a
> physical measurement, and nobody has built the thing that takes it.

**Why the harm framing, not the scale framing.** Do not open on "millions of SKUs." That
is a size claim, and the panel will hear it as marketing. Open on the inspector holding
the packet — that is a *harm* claim and it is the one a Consumer Affairs ministry cares
about. It also pre-empts the sharpest question anyone has asked about this project:
*why photograph a package when the manufacturer's artwork file already has exact letter
heights?* Answer, ready but unspoken unless asked: enforcement happens on shelf stock
that is often imported, relabelled, or from an unregistered packer, where no artwork file
exists — and a pre-market file check cannot catch print that differs from the file.

**Do not say a rule number.** Say "the Rules" and "the minimum height table." The height
provision has moved between rule numbers across amendments, the two external audits of the
corpus disagree with each other about which amendment introduced the panel-area indexing,
and a wrong provision number in front of a Consumer Affairs judge is the most expensive
single error available to us. If asked directly, see the Q&A in §12 of the brief.

---

## Slide 2 — What everybody builds, and where it stops

**On the slide:** two stacked rows. Top row: `photo → OCR → text → rule engine → verdict`,
with a small tag under it reading *everything in this row is text*. Bottom row:
`photo → scale reference → rectify → sub-pixel edge → height in mm ± U → verdict`, tagged
*this row is a measurement*. Title: *Both rows read the label. Only one of them measures.*

**What you say, ~55 seconds:**

> The standard architecture for this problem is optical character recognition feeding a
> rule engine, and it is the right architecture for most of the requirement — expiry
> dates, the packer's address, whether a mandatory field is missing at all. We use it too.
> But every stage in that pipeline lives in the text domain, and the height requirement is
> dimensional. To answer it you need millimetres per pixel, and to get millimetres per
> pixel you need something of known physical size in the frame. If a system accepts an
> arbitrary uploaded label photograph, it does not have that, so its font check is
> comparing pixel heights or inferred point sizes. It can flag a label as *looking* small.
> It cannot state a height in millimetres, and a height in millimetres is what the statute
> is written in.

**Name no competitor.** There is a live project on this exact problem statement and its
public feature list includes a legibility-and-font check. That confirms our prediction
about what the field builds, which is why we are not worried about it — but attacking a
named product reads badly in an SIH room, and it loses badly if a judge knows something
about it that you do not. State the requirement generally and let it apply to everyone,
us included. If asked directly about a specific competitor, answer narrowly and factually:
we have not audited their system, and the general point stands regardless of who is asked.

**Retire this line: "nobody else noticed that font size matters."** It is now falsifiable
in the room. Somebody else did notice. What they cannot do is convert pixels to
millimetres, and *that* is the claim to make.

**The sharpest attack on this slide, and the concession that defuses it.** Someone will
point out that the two rows are not disjoint: our measurement row has to know *which*
characters are the mandatory declarations, and that is the text row's job. They are right,
and the answer is to agree immediately — **OCR tells us what to measure; it cannot tell us
how tall it is.** The rows are sequential, not rival. If the diagram's tags make them look
like alternatives, add one arrow from the top row into the bottom row labelled *which
characters* and let the picture make the concession for you.

**This is the slide to cut if you are short on time.** The distinction survives inside
slide 3.

---

## Slide 3 — The instrument

**On the slide:** two rows, because the instrument has two halves and conflating them is
the mistake everyone else makes.

Top row, *what does the law require?* — three declared inputs (**panel area**, **package
category**, **inspection date**) feeding one box: *statutory minimum height*.

Bottom row, *how tall is it actually?* — four boxes left to right: *scale reference* →
*rectify to millimetre space* → *sub-pixel edge location* → *uncertainty budget*.

The two rows meet in a decision box branching four ways, exactly these words:

- **COMPLIANT**
- **DEFICIENT**
- **REQUIRES PHYSICAL VERIFICATION** — the measurement is indeterminate
- **REQUIREMENT UNRESOLVED** — the *law* is indeterminate

Title: *A measuring instrument, built to a conformity-assessment standard.*

**What you say, ~90 seconds — and this is the slide most likely to overrun, so the three
paragraphs are separable on purpose. Under time pressure, keep the first and the last.**

> Start with the requirement, because it is not a constant. The minimum height comes from a
> table indexed on the area of the principal display panel, and it runs from about one
> millimetre on a small packet to about six on a large one. So the operator declares the
> panel area, the package category and the inspection date, and the software looks the
> requirement up — it never infers it from the image, because a guess hidden inside a legal
> threshold is the worst possible place to put one.
>
> Then the measurement. A known physical artifact in the frame establishes millimetres per
> pixel. We rectify the image into millimetre space, locate each character's edges to
> sub-pixel precision against a declared intensity criterion, and produce a height with an
> uncertainty attached. The verdict follows the international standard for conformity
> decisions under measurement uncertainty, JCGM 106: compliant only if the height minus our
> uncertainty still clears the limit, deficient only if the height plus our uncertainty
> still falls short, and otherwise this package needs physical verification.
>
> And there is a fourth outcome, which is the one I would point at. If the requirement
> itself cannot be resolved — an undeclared panel area, or a bracket where an unread
> corrigendum leaves us unable to establish the requirement — the system refuses **before**
> it measures. It declines because the law is unresolved, not because the pixels were bad.

**Four words to get exactly right on this slide.**

- The middle outcome is **DEFICIENT**, never *FAIL*. A photograph triggers an inspection;
  it does not deliver a legal finding. An earlier draft said FAIL and it contradicts the
  entire doctrine of the project.
- **"Traceable"** may appear only as *architected for traceability*. Standing alone it is
  a claim we have not earned — our scale chain currently terminates in an uncalibrated
  artifact. Do not fix this by deleting the word either: strike it and what is left is
  "a camera that measures letters," which is the position we are arguing against.
- Say **"printed letter and numeral height"**, never "font size." Font size is a
  typesetting parameter; the statute regulates the mark on the package.
- **Never say a threshold for the 50-to-100-square-centimetre bracket.** That is the bracket
  the software blocks as unresolved. Saying *that we cannot establish the value* is the strong
  move; saying either candidate number is the one way to lose the credibility the rest of the
  slide buys. Note the shape of the strong move: it is a claim about the state of our
  knowledge, which we can back, not a claim about the state of the statute, which we cannot.

**Do not say a rule number here either.** "The table in the Rules, indexed on panel area"
is accurate and safe. The two external audits of the corpus contradict each other on which
amendment introduced that indexing, which is exactly why the number stays unspoken.

---

## Slide 4 — A number with an uncertainty attached

**On the slide:** the decision bands drawn to scale against a 1 mm limit. A bar from 0 to
0.83 labelled DEFICIENT, a bar from 0.83 to 1.17 labelled REQUIRES PHYSICAL VERIFICATION,
a bar above 1.17 labelled COMPLIANT, and `U(k=2) = 0.17 mm` printed once. Label the limit
**`1 mm — smallest-panel bracket`**, and put one line under the diagram:

> double the requirement and this band halves

Title: *What follows from carrying an uncertainty.*

**Two decimal places on this slide and nowhere more, matching U (corrected 2026-09-06: this
was called "significant figures," but 1.17 has three of those -- it is two decimal places).**
The band edges are 0.834 and
1.166 in the working notes. Printing three decimals derived from a budget whose every term
is modelled is precisely the fake-precision habit this project has caught itself in four
times. **0.83 and 1.17.**

**Label the limit, do not leave it bare.** Slide 1 now says `? mm` precisely because the
requirement is a lookup; a bare `1 mm` here reintroduces the constant we just spent slide 3
removing. Worse, it hands the panel our weakest cell as though it were our typical one.

**What you say, ~80 seconds — and the first paragraph is the first thing to cut in the whole
deck.** It restates the JCGM band that slide 3 has already explained; the diagram on this
slide carries that content visually. Cutting it costs ~40 seconds and loses no claim. The
second paragraph is the one that must survive, because it is the one nobody else will say.

> Because the system carries an uncertainty, there are packages it will not adjudicate,
> and it says so. At our present expanded uncertainty of 0.17 millimetres, against a one
> millimetre floor, anything between 0.83 and 1.17 comes back as needs-physical-
> verification. That band is not a weakness we are disclosing; it is the output of a
> budget, and it is why the verdicts outside it mean something. A heuristic font checker
> always returns an answer. An instrument sometimes declines — and the decline is the part
> you can watch working in three minutes.
>
> And one thing about that band, because it is easy to read the wrong way. One millimetre
> is the smallest requirement in the table — it applies to a panel of fifty square
> centimetres or less, roughly a seven-centimetre packet. That is the hardest cell in the
> statute and it is the one we designed against. The uncertainty is set by the instrument,
> not by the packet, so the band is a fixed 0.17 either side wherever you are in the table:
> double the requirement and the shortfall we can call halves, and at the top of the table
> it is under three percent. What you are looking at is our worst case.

**Then the line that lands, if you say only one more thing:**

> A flag prioritises an inspection. A measurement supports enforcement. Only one of those
> can go into a legal notice.

**Do not title this slide "refusal is our differentiator."** The differentiator is the
budget behind the refusal; refusal is merely its visible consequence. And concede the
cheap version before anyone raises it: any program can print "unsure" below a confidence
threshold. What is not cheap is a stated physical cause for each refusal and an
uncertainty that was derived rather than tuned. If asked, say that.

**Then expect the follow-up, because it is the better question: *where did the thresholds
that make it refuse come from?* The answer is written out in §12 of the brief — give that
one.** The short form is that the capture path's gates are three derived and five
placeholders, the file records which is which, and its self-test fails if anyone adds a gate
without classifying it. Two things about saying it. **Never call a placeholder "tuned"** —
tuned sounds better and is worse, because a tuned limit is one fitted to the outcome we
wanted, which is the exact opposite of the sentence you just said. And do not improvise a
tidier split than the real one: a named gap in our own numbers is the same move slide 5
makes with the budget, and it works for the same reason.

**The honest framing of the band, if a judge pushes on its width:** a 0.33 mm band around
a 1 mm limit means the smallest shortfall we can currently call is about 17 percent. That
is a real limitation. Two separate things shrink it, and they are worth keeping apart. One
is the requirement: the smallest callable shortfall is `U/TL`, so a larger requirement is
genuinely easier — **but not proportionally, and the earlier version of this line said
"double the requirement and it halves, exactly," which is false.** It halves only if `U` is
a constant, and three of the eight budget terms are scale errors that grow with the
character being measured. The true improvement from 1 mm to 2 mm is a factor of 1.8, and
climbing further it flattens onto a floor of about **three percent of the requirement,
which no bracket ever beats.** §6a of the brief has the derivation. The other is the budget
itself, which is dominated by one term; slide 5 says which one and what closes it. Do not
defend the number
— say which of the two you are talking about, and explain what shrinks it.

**Say the relation, not the rungs — and the relation changed on 2026-09-06.** The internal
arithmetic is **16.6 percent at a 1 mm requirement, 9.2 at 2, 7.8 at 2.5, 5.8 at 4, 4.8 at
6**, flattening onto a floor near 3.0. Those are the honest figures from §6a of the brief;
the numbers previously on this line — 6.7 at 2.5, 4.2 at 4, 2.8 at 6 — came from holding `U`
constant, which is what the program still does and what the physics does not. **That table is
for your own head, and it is not for the room.** Spoken, it is *"the larger the requirement,
the easier it gets — but it flattens out, and it never gets below about three percent."*
Same content, no rung said aloud, and it commits us to no aggregator-sourced value for any
middle bracket. One and six are the ends of the range and are already permitted by the
exception at the top of this document; 2, 2.5 and 4 are not, and reading the ladder aloud is
the likeliest way anyone slips. **The corrected version is also the safer one to say**: the
old spoken line promised "under three percent," which was both wrong and pointed at the one
number the design cannot deliver.

**The caveat that must travel with that ladder every single time.** `U/TL` improves across
the table *only at constant millimetres-per-pixel*. A 2500 cm² panel does not fit the
field of view that a 50 cm² packet fits, and widening the field lowers px/mm, which
inflates `U` and gives the gain straight back. The honest form is: **on a fixed rig
measuring a crop at the same scale, the larger requirement is genuinely easier; measured by
backing the camera off, it is not.** Say the caveat unprompted. A judge who spots that
the ladder assumes constant scale and hears it from you first has learned that we audit our
own good news; the same judge who spots it after we have banked the claim has caught us.

**The two caveats stack, and the corrected ladder still only carries one of them.** §6a's
figures — 16.6, 9.2, 7.8, 5.8, 4.8 — are computed **at constant millimetres-per-pixel**, so
they already answer "does `U` grow with the character?" and they do **not** answer "does the
field of view have to grow to see a bigger panel?" The second effect pushes the same
direction. **So treat the corrected ladder as an optimistic bound, not as the answer**, and
if you only have breath for one caveat in the room, give the field-of-view one — it is the
one a judge can construct from first principles while you are still talking.

**And the numbers that are never said at all.** A corrigendum **is reported to alter** a value
in this height table — that wording is not throat-clearing, we have a secondary report *of* a
corrigendum, not a corrigendum. We have read neither the amendment nor the corrigendum at
source, and — this is the
part that is easy to state too strongly — **we cannot establish which cell it alters.** Two
readings both fit what we have: either the table we transcribed predates its corrigendum, in
which case one cell we hold is wrong, or it postdates it, in which case the corrected value is
already in the table and the cell described by the corrigendum is a different one we may have
transcribed as something else. So do not say "the amendment and the corrigendum disagree about
that bracket" — that asserts we know which cell is in play, and we do not.

What the software does is block one bracket, the one immediately above the smallest, and it
blocks it as a **conservative choice under an unresolved reading**, not as a demonstrated
dispute. **No candidate value for it is ever said aloud** — not in the script, not in Q&A, not
in the corridor afterwards. Naming two candidates would claim we know the candidate set, which
is the same overstatement one level down.

If someone asks what that bracket requires, the answer is: a corrigendum is reported to change
a value in that table, we have not read the Gazette original or the corrigendum at source, we
cannot yet establish which cell is affected, and so the software returns no verdict for that
bracket. That is the behaviour we would want from it, and it is the only reason we know the
problem is there at all.

**And do not name the notification in that answer either** — not because it is secret, but
because the two external audits of the ministry page do not agree on which amendment carries
this table, so any number said here is a claim we cannot back. "The Rules, and the amendment
that carries the height table" is true under either audit. The software follows the same rule:
its refusals name the instrument, never the notification.

---

## Slide 5 — Status, honestly

**On the slide:** three columns, short. *Built* / *Modelled or unverified* / *Next*.

| Built | Modelled or unverified | Next |
|---|---|---|
| Measurement engine, panel-area-indexed rule model, JCGM 106 decision logic, **fifteen distinct measurement refusal paths — one confirmed firing, the rehearsal on real packets exercises the rest** — and ten legal blockers †  | Eight-term uncertainty budget, `U(k=2) = 0.17 mm` — **all eight terms modelled, none yet measured**. Statutory table encoded from a secondary source, **one bracket blocked as unresolved**. Capture path written, **never run against a camera**. **Height only — a width requirement is reported to exist and is not implemented** (added 2026-09-06; a system claiming to check "the statutory dimensional requirement" must not silently mean half of it) | Measure a graduated glass artifact to close the dominant term; read the Gazette original and its corrigendum together and record both dates |

† **Conditional fragment.** "Ten legal blockers" is the legal layer, and the legal layer only
belongs in **Built** if its self-test has been re-run green in the form being shipped. If it has
not, strike the four words from this cell and add *rule model and ten legal blockers written,
self-test not re-run* to the middle column, where an unconfirmed thing goes. Do not leave the
fragment in Built while the note below says the layer is conditional — that contradiction is on
one slide, and it is the kind a judge reads out.

**Why the Built cell now qualifies its own refusal count.** The earlier wording put "fifteen
measurement refusals" in **Built** while the two cells beside it were held to the rule *code
whose tests have never executed is not a built feature.* Thirteen or fourteen of the fifteen
have never been observed to execute, so the strict standard was being applied to the camera
path and the legal layer and not to the number three words to their left. The prose below the
slide was already honest about it; the prose is not what gets photographed. The qualifier is
eight words and it removes the single most extractable overstatement on the most important
slide — which is the move this slide exists to make.

Title: *What is built, what is modelled, what is next.*

**The refusal count, and the rule behind it.** Fifteen is a count of distinct refusal codes the
measurement module can raise: eleven in `capture_checks` (RESOLUTION, NO_REDUNDANCY, PLANARITY,
CONTRAST, NO_GLYPH, CLIPPED, ILLUMINATION_GRADIENT, GLYPH_COUNT, ROI_EDGE, FLOOR_LIMITED,
EXTENT_SPREAD), two in `measurement_completeness` (NO_MEASURAND, MEASUREMENT_DROPPED), and two in
`measure` (BIN_STARVED, NO_MEASUREMENT). **One of the fifteen, EXTENT_SPREAD, is off by default**,
so if anyone asks for the number that fires on a stock configuration the answer is fourteen. The
same file raises four more that are legal rather than metrological — RULE_INDEX_AMBIGUOUS,
CATEGORY_NOT_DECLARED, CATEGORY_UNKNOWN, MEASURAND_UNDEFINED — which are counted under the rule
model, not here, because they are about which row of the table applies rather than about whether
the image can be measured. Nineteen codes in the file, fifteen of them about the measurement.
**This slide said "eight" until 2026-09-05.** That number was carried from a version before the
completeness and category gates existed and nobody re-counted; it was an understatement, which is
the harmless direction, but it was still false. If you are working from an older printout, the
count is the thing to fix.

**Fifteen implemented is not fifteen demonstrated, and someone will ask.** The count above is
a count of refusal codes that exist in the shipped module. The v7.1 run exercises far fewer.
Of the fifteen measurement codes, **`GLYPH_COUNT` is the only one confirmed firing** (the glare
sweep), and `FLOOR_LIMITED` may be a second — the sampling sweep labels its four lowest rows
floor-limited, but whether that label is the refusal or a different quantity is itself
unresolved (§13a, item 9). The other two firings in the run, `MEASURAND_UNDEFINED` and
`CATEGORY_NOT_DECLARED`, are legal codes and are **not** among the fifteen. **So: four of the
nineteen codes in the file have been seen to fire, and only one or two of the fifteen
measurement ones.** If asked whether they all work, the answer is that they are all written and
reachable, **the count we can show output for is one**, and the refusal rehearsal on ten to
fifteen real packets is job 4 — which is the job that will fire the rest. Do not let "fifteen"
drift into "fifteen tested." Said out loud: *"fifteen distinct reasons the measurement module
declines. On synthetic images we have watched one of them fire; the rehearsal on real packets is
what exercises the others, and it happens before the grand finale, not after."*

**The two firing counts on this slide are not in conflict, and do not "fix" one into the other.**
Four of the **nineteen** codes in the file have been seen to fire; one — possibly two — of the
**fifteen measurement** codes has. The table cell counts the fifteen, so the cell says one. Anyone
who raises either number must say which denominator it belongs to in the same breath, because
"four of ours have fired" spoken over a cell that says one is how a judge concludes the slide is
managed rather than measured. The floor is also the safest number: `GLYPH_COUNT` declining the
under-glyph crop is the one firing there is saved output for. Understating by one costs nothing on
Wednesday; overstating by three is the exact failure this slide was built to prevent.

**On "one bracket blocked as unresolved" rather than a count of contested cells.** The count we
can defend is a count of what our software does — it declines on one bracket. How many cells of
the statutory table the corrigendum actually disturbs is not something we know, and a slide
that says "two cells contested" claims we have located them. Keep the claim on our side of the
line: we block one bracket, and we say why.

**The middle column is called "Modelled or unverified" for a reason.** An unmeasured budget
term and a threshold transcribed off an aggregator are the same epistemic object — a number
we are using and have not confirmed — and they belong in the same column. Splitting them
across Built and Modelled is how the rule table quietly acquires the authority of the
measurement engine.

**Both cells below were settled by re-running each file, not by waiting for a
demo-day re-run — and that's the right way to read this pattern generally: a
number in this document is only as fresh as the file it describes, so if
either module is touched again before the (postponed) 2026-09-15 round,
re-run it and update the cell again rather than trusting what's printed
here.**

**A green run from before an edit is not evidence about the file after it.** Both modules below
reported 68 of 68 checks passing on 2026-09-05. Both have been edited since — the capture layer
in three places, the legal layer in seven — and the edits added checks, so the count itself has
moved. That earlier green certifies a file that no longer exists on disk. Neither cell may cite
it. The re-runs below are what settle each cell, not a document claim about them.

*The camera path.* This is written now — `lm_capture.py`, the scale-reference layer that sits
between the camera and the measurement engine. **No camera has ever been attached to it.**
**Re-run 2026-09-06: `self_test()` passes at 114 of 114 checks, 0 failed.** The cell reads
*capture path written, decision logic self-tested at 114 checks, not yet exercised against a
camera* — read off that run, not off this document. **This is a fresh number, not a permanent
one: if `lm_capture.py` is touched again before the 15th, re-run and read the new count off
that run — do not carry 114 forward on the strength of this sentence.** The old 2026-09-05
figure of 68 is superseded and should not be spoken.

The one thing that path buys, and it is worth the sentence: with no scale reference in frame
it **refuses** rather than defaulting. Point it at a packet with nothing of known size in
frame and it declines to produce millimetres; slide the calibration artifact in and it
measures. That refusal is the thesis, enforced at the earliest point it can be violated —
and it is the half a heuristic font checker cannot do.

*The legal layer.* The rule model, the ten blockers and the bracket lookup are written.
**Re-run 2026-09-06: `self_test()` passes at 81 of 81 checks, 0 failed** — the seven fixes
made since the 2026-09-05 run of 68 are included in this count, because this run executed the
file as it now stands. The legal layer is Built. **Same caveat as the capture cell: this
number is only as fresh as the file. Touch `lm_legal_model.py` again before the 15th and this
sentence is stale until it is re-run.** Code whose tests have not executed **in the form being
shipped** is not a built feature; a run this same week, on the file that will actually ship,
is what makes it one.

**If either self-test fails, that is the best thing that happens this week** — it fails on your
laptop on Monday instead of on the projector on Wednesday, and the fix is yours to make in
private. Read the failing check's message before changing anything: several of these checks exist
specifically to catch a fix that relocated a defect rather than removing it, so a failure is more
likely to be pointing at the last edit than at the check.

**Never leave either cell in Built as a hedge.** An honest gap costs less than a demo that
quietly cannot be reproduced.

**What you say, ~80 seconds:**

> Our uncertainty is currently modelled, not measured — all eight terms of it. We are
> saying that ourselves, on a slide, because the difference between a modelled budget and a
> measured one is the difference between an engineering estimate and an instrument, and we
> would rather name the gap than be walked into it. Closing it costs one graduated glass
> artifact and an afternoon on the rig. One term dominates: the printed edge of ink has no
> sharp boundary, so any dimensional measurement of a printed character needs a declared
> edge criterion, and the cost of ours is bounded at about 0.08 millimetres. That is the
> largest thing standing between a modelled number and a measured one.
>
> There is a second gap and it is not metrological. Our height table is transcribed from a
> secondary source, which also reports a corrigendum altering one value in it. We have not
> read that corrigendum, and we cannot establish which cell it touches — so on the one
> bracket where that matters the software declines to return a verdict at all. On one more it
> flags the value as provisional rather
> than declining, because a suspicion about a pattern is not a documented conflict. Settling
> both is a library errand, not a research project. Until it is settled we would rather
> decline than be confidently wrong about what the law requires.

**If the disputed-threshold step is in the demo, cut that second paragraph to one
sentence.** It is the same point twice, and the demo version is the stronger one because
the panel watches it happen. Keep the full version only if the demo has been shortened past
the 3:45 step in §10 of the brief.

**This is the most important slide in the deck and it is counter-intuitive, so here is
why it works.** The reviewer who scored the internal brief at 5.5/10 extracted every
"modelled" and "not built" from it and used them as findings. Every one of those items was
already disclosed *in* the brief — it was disclosed in a document with no narrative
holding it, so disclosure read as exposure. Said in your own voice, in a column headed
*Modelled or unverified*, with the next step named beside it, the same facts read as command
of the problem. **A gap you name is a gap you own.** A gap extracted from you under
questioning is a gap that owns you.

**Claim versus disclosure — the rule this slide runs on:** §15 of the brief is where the
modelled budget lives, and §10 and §15 both now state the rule the same way: nothing from
§15 goes on a slide **as a claim**, and some of it goes on a slide as a disclosure because it
should. (Both sections used to read as blanket bans, which made this slide look like a
violation of the brief rather than an application of it. Fixed 2026-09-05 — if you are
working from a printout older than that, re-read §10.) So: §15's items must never appear as
*claims* — do not put 0.16634 on a slide, do not present the three newest terms as
characterised, do not cite an unverified provision number, and **do not print either
candidate value for the contested bracket.** "Two cells contested" is a disclosure; a number
chosen between them is a claim, and it is a claim about what the law requires, which is the
worst kind to get wrong. Stating that a figure is modelled is not making the claim; it is the
opposite. Slide 5 discloses. That is allowed and it is required.

---

## Then the demo

The slides set up the demo; they do not replace it. Run of show, timings and the exact
lines are in **§10 of `SIH26034-team-brief.md`** and are not duplicated here so there is
only one copy to keep correct. Three things about it that belong in your head before you
walk in:

**Every other team will demo a screen. We demo an instrument on a table.** That is the
asset. A working web app beats an uncertainty budget in front of non-specialist faculty
*unless the depth is physically visible*, and ours is: there is a calibration artifact in
the frame, and you can point at it.

**The refusal is the demo, not the fallback.** The 1.00 mm target sitting exactly on the
statutory limit coming back as REQUIRES PHYSICAL VERIFICATION is the single most
convincing thing in the three minutes, because it is the one behaviour that cannot be
faked and that a heuristic will not produce.

**An unplanned refusal is not a failure — read the reason out loud.** A wrong number is a
failure. If a verdict looks implausible, say the scale calibration may have shifted and
recalibrate on camera. Never argue with your own instrument in front of a panel.

---

## The sixty-second version

If the slot turns out to be shorter than expected, or the panel is running late, cut to
this. It is slides 1, 3 and 5 with the demo compressed to the refusal.

1. *(10 s)* "The Rules specify character heights in millimetres. A photograph contains
   pixels. Converting between them needs a physical scale reference, and OCR does not have
   one."
2. *(20 s)* "So we built a measuring instrument instead of a text pipeline. The requirement
   is a lookup on declared panel area, not a constant. A known artifact in the frame sets the
   scale, we locate character edges to sub-pixel precision, and we report a height with an
   uncertainty."
3. *(20 s)* Measure the 1.00 mm target live. "It refuses. This specimen sits inside our
   indeterminate band, so the correct output is *requires physical verification*. A
   heuristic would have given you a confident answer, and that answer would not survive a
   challenge."
4. *(15 s)* "Our uncertainty is modelled, not measured — we say so on the slide. Closing
   that needs one graduated glass artifact. A flag prioritises an inspection; a measurement
   supports enforcement, and only one of those goes into a legal notice."

**It counts to sixty-five, not sixty.** Item 2 carries twelve words about the lookup that the
earlier version did not have, and they are worth five seconds: without them the pitch sounds
like a device checking a fixed 1 mm floor, and half the panel already knows the requirement
is not fixed. If the slot is hard-stopped at sixty, cut item 4's middle sentence about the
glass artifact — not the lookup, and never the refusal.

**This version omits the contested cell, and that is not a concealment.** Nothing in it
asserts a threshold as law — item 3 states what the *specimen* measures, which needs no
primary source. Sixty seconds is not enough room to open a statutory dispute and close it,
and a half-opened dispute is worse than an unmentioned one. If the panel asks, the answer
from slide 5 is one sentence and you give it.

---

## Before Wednesday

Ordered by what blocks what, not by size.

- [ ] **Run `self_test()` in `lm_legal_model.py`.** Nothing in that file has ever been
      executed. It is the first command anyone types, and it happens before a single v7 call
      site is touched. Slide 5's legal-layer cell depends on the answer.
- [ ] **Apply the v7.1 patch and run its ten-item regression list before wiring the legal
      layer in.** Two unvalidated changes landing together and you cannot tell which one
      broke the measurement. One at a time, in that order.
- [ ] **Read the Gazette original of the amendment and its corrigendum together, and record
      both dates.** This is the one errand that would let a threshold value go on a slide.
      Until it is done, no value does.
- [ ] **Settle slide 5's two conditional cells and then print the slide.** The camera path
      and the legal layer each sit in Built or in Next depending on the two items above.
      Neither one stays in Built as a hedge.
- [ ] Rehearse twice out loud, timed, with the demo attached — not read silently. The slides
      are **five and a half minutes**, not the three an earlier draft of this file claimed.
      Pick your tier from the timing block at the top before the first rehearsal, and
      rehearse that tier, not the full text.
- [ ] Rehearse the Q&A answers in §12 of the brief out loud. Two of them exist to stop
      improvisation on the measurand question; improvising there is how a strength becomes
      an admission.
- [ ] Rehearse the one-sentence answer to "where did the 1 mm come from". It is a documented
      exception to our own no-numbers rule, so it has a documented answer — give that answer,
      do not invent a better-sounding one.
- [ ] Rehearse refusals against a wide range of *boring* packets, and **record which gate
      fired on each one.** An unplanned refusal on an ordinary packet reads to a
      non-technical evaluator as "it does not work," so you want to know the rate before
      Wednesday — but the rate is the thing you measure, not the thing you hit. Do not
      loosen a limit to improve it: a limit you would not have chosen before seeing the
      outcome is a fit, not a limit, and slide 4 says out loud that our uncertainty was
      derived rather than tuned. `GLYPH_COUNT` is the predicted offender and is also the
      one gate that must not move before Wednesday — risks 4a and 4b in §14 of the brief
      say why, and give the answer to use if it does dominate.
- [ ] Confirm the time limit and the internal rubric with the SPOC. Both are still unsent
      and both change this document.
- [ ] Decide who says which slide, and decide it against the tier you are giving. Five
      slides, five and a half minutes of script, and a live demo does not survive being
      negotiated at the podium.
- [ ] Nothing from §15 goes on a slide as a claim. Read slide 5 against that rule once
      more before it is final.



