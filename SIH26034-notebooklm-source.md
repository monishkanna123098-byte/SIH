# SIH26034 — Camera-Based Legal Metrology Compliance Checker

*A complete project reference, current as of 2026-09-06. Written as a single narrative
rather than a dated audit log, specifically so that a tool summarizing it doesn't have to
reconcile superseded statements against their corrections — every statement below is the
current one.*

## 1. The problem this solves

SIH26034 is an official Smart India Hackathon 2026 problem statement, sponsored by
India's Ministry of Consumer Affairs, Food & Public Distribution: build a software system
that checks whether a packaged commodity complies with the Legal Metrology (Packaged
Commodities) Rules, 2011, by scanning the product, its image, or its label.

Those Rules require several declarations on every retail package: the manufacturer's name
and address, the common name of the commodity, the net quantity, the month and year of
manufacture, the retail sale price, and consumer-care contact details. Beyond requiring
that these exist, the Rules also specify **how large the printed characters must be**, in
millimetres. That second requirement — character height — is what this project checks. It
deliberately does not attempt to verify that all six declarations are present and worded
correctly; that is closer to a template-matching problem. Height compliance is the part
that requires genuine physical measurement, with a real uncertainty budget behind it, and
that is the hard, defensible sub-problem this project goes deep on rather than wide.

The specific rule is **Rule 7(2)** of the 2011 Rules (as amended in 2017): the height of
numerals and letters in a declaration must not be less than 1 mm, rising through a table
indexed by the package's principal display panel area, up to 6 mm for panels over 2500
cm² — and not less than double the applicable figure if the characters are blown, formed,
moulded, embossed, or perforated into the package rather than printed in ink. (An earlier
version of this document cited Rule 7(3); that sub-rule was confirmed, against an actual
Gazette-notification compilation, to govern character *width* — one-third of height — not
height. This project's own citation had the right rule and the wrong sub-rule for several
days before that was caught.) A separate provision carves packages containing medical
devices out of both sub-rules entirely, deferring to the Medical Devices Rules, 2017.

## 2. Why this is a measurement problem, not a font-size lookup

A photograph of a label does not directly report a physical height in millimetres — it
reports a height in pixels, and pixels only become millimetres once you know the scale of
the image, which requires something of a known physical size to appear in the same frame.
Get the scale wrong and every downstream number is wrong by the same factor. This project
treats that conversion as a first-class measurement problem, not an assumption: it will
not report a height in millimetres unless something of a known size is visible in the
image to calibrate against, and it refuses outright rather than guessing when that
reference is missing.

Once a height is measured, the second problem is uncertainty. No measurement is exact, and
a system that reports "1.02 mm" against a "1 mm" requirement without saying how confident
it is in that number is making a claim it cannot support. This project builds an explicit,
JCGM 106-style expanded uncertainty budget: eight identified sources of error (things like
sub-pixel edge-finding noise, scale-calibration error, lens distortion, and — the largest
single term — the ambiguity in exactly where a character's ink "edge" is, since ink
naturally spreads and different type designs use different conventions for cap height vs.
x-height). Combined at a 95%-confidence coverage factor of k=2, the current budget is
U ≈ 0.17 mm. A measured height h is then compared against the legal threshold TL in three
ways, not two:

- If h − U is still at or above TL, the package is **COMPLIANT** — even accounting for the
  worst-case measurement error, it clears the bar.
- If h + U is still at or below TL, the package is **DEFICIENT** — even accounting for the
  best-case measurement error, it falls short.
- If the uncertainty band straddles TL, the verdict is **indeterminate**: the instrument
  says so explicitly and asks for physical verification, rather than picking a side.

This three-way logic is the core design decision of the project. A binary compliant/
non-compliant tool would have to silently pick a side inside that grey band, and would be
wrong exactly as often as the band is wide. Making "I can't tell" a legitimate, named
output is what makes the other two verdicts trustworthy.

## 3. System architecture — three modules, three separate jobs

- **`lm_metrology_v7.py`** (currently version 7.9) is the measurement engine. It finds
  character edges in an image, computes their height, carries the uncertainty budget
  described above, and holds the height-threshold rule tables. It is also where every
  "refusal" is defined — fifteen distinct conditions under which the instrument declines to
  report a height at all rather than report an untrustworthy one, covering everything from
  insufficient image resolution to a package category (formed/moulded characters) that this
  instrument's measurement convention cannot honestly measure at all.

- **`lm_capture.py`** is the camera-facing layer that sits between a physical camera and
  the measurement engine. Its job is establishing scale: given a calibration artifact of
  known size in frame — a graduated glass graticule or a printed target — it derives a
  pixels-per-millimetre conversion and its own uncertainty, and it refuses to hand off a
  frame at all if no such reference is present. Its self-test suite currently passes 114 of
  114 checks. It has never yet been connected to an actual camera; everything so far has
  been validated against rendered or declared inputs.

- **`lm_legal_model.py`** is a separate statutory-citation layer, deliberately split out
  from the measurement engine. Early in the project's review process, the biggest single
  finding was that conflating "how tall is this character" (a measurement, properly
  uncertain) with "how tall must it legally be" (a lookup, which must never be presented as
  uncertain in the same way) was itself a source of risk. This module owns rule citations,
  provenance tracking (is a given threshold sourced to a verified Gazette text, or to a
  secondary aggregator?), and ten distinct "blocker" conditions for legal-side problems like
  an undeclared package category. Its self-test suite currently passes 81 of 81 checks.

Together, a full pipeline runs: camera frame → `lm_capture` establishes scale or
refuses → `lm_metrology` measures a height and its uncertainty, or refuses → `lm_legal_model`
resolves which legal threshold applies and with what confidence → a three-way verdict.
**This wiring is now complete and verified by execution**, gated in a specific order
(category declared, then recognised, then can the instrument measure this surface at
all, then the threshold itself) and tested against eight scenarios — including the
hardest one, where an undeclared panel area on a formed package correctly reports "can't
measure this surface" rather than "don't know the area." Callers that don't declare a
commodity class are unaffected; the original, simpler lookup still runs for them.

## 4. What is verified right now, and how

Every number in this section was produced by actually running the code, most recently on
2026-09-09, not by reading it or estimating it:

- `lm_metrology_v7.py`, version 7.9: runs cleanly end to end; its internal self-checks
  (geometric homography recovery, a synthetic measurement demo across both package
  categories) all reproduce results that are bit-identical to the project's last fully
  verified run, confirming that recent changes affected only what they were meant to.
- `lm_capture.py`: self-test passes 114 of 114 checks.
- `lm_legal_model.py`: self-test passes 81 of 81 checks.
- The legal-model integration described in section 3 above: tested against 8 scenarios
  by actually running them, including the category/measurand precedence order and a
  disputed-bracket refusal that confirmed no unverified number leaks into its message.
- The uncertainty budget's reference value is U(k=2) = 0.16634 mm at a 1 mm character
  height, rising with height for the three budget terms that are genuinely fractional
  errors (scale calibration, lens distortion, fiducial localisation) rather than fixed
  distances in the image plane — for example, U = 0.28578 mm at a 6 mm character height.
  This height-dependence was added and independently re-verified against hand computation
  on 2026-09-06.
- The height citation, **Rule 7(2)**, is sourced to an actual Gazette-notification
  compilation (not a summary) reaching into late 2025, plus a third independent legal
  analysis giving the complete current table, cell for cell matching what the code
  encodes. One bracket (50–100 cm², ordinary category) remains flagged as disputed
  pending a specific corrigendum that nobody on this project has read at source — the
  system refuses to give a verdict for that one bracket rather than guess, and does not
  leak either candidate value into the refusal it gives instead.

## 5. What is honestly still open

- **The most significant known limitation:** the code currently identifies the governing
  character for a declaration as the *shortest successfully measured mark* in the region an
  operator selects. The project's own recommended counting convention includes every ink
  mark — letters, digits, currency symbols, and punctuation. A decimal point's ink extent is
  a small fraction of a digit's height, so a price like "₹99.00", printed perfectly compliant
  at 1.4 mm, can currently be measured as failing, because the system measures the period
  instead of a digit. This is understood to be the single largest source of risk in the
  project, larger by orders of magnitude than the uncertainty budget itself, and it runs in
  the direction an enforcement tool must not err in — toward false non-compliance. It has not
  been fixed in code, because the correct fix requires a statutory definition of which
  categories of mark actually carry a height requirement under the Rules, and inventing that
  definition in code without a legal basis would trade one unverified assumption for another.
  A statistical guard against this exists in the code (a check on how dispersed the measured
  heights are) but is deliberately left off by default, because on real packaging, legitimate
  characters (capitals, lowercase, digits) vary in height for ordinary typographic reasons,
  and enabling the guard without first measuring how often it would misfire on compliant
  labels would manufacture refusals instead of preventing errors.
- The numeral-height table (as opposed to the letter-height rule) may need re-verification:
  the Rules were amended in 2017 in a way that appears to have restructured how numeral
  height is indexed, and the project's current table has not been fully cross-checked
  against that post-amendment structure.
- The uncertainty budget is complete in structure but still substantially *modelled* rather
  than *measured* — most of its eight terms are engineering estimates, not numbers read off
  an actual calibrated measurement. Converting them requires a physical stage micrometer
  session that has not yet happened. A ninth potential source of error, the calibration
  artifact's own manufacturing tolerance, is known about but not yet added, pending a
  calibration certificate for that artifact.
- No camera has been attached to the system yet. Both `lm_capture.py` and
  `lm_legal_model.py` are self-tested and internally consistent, which demonstrates their
  decision logic is sound, but says nothing about their behaviour against a real sensor.
- The live demonstration of this system has not yet been rehearsed with a stopwatch; time
  estimates for it are currently just estimates.

## 6. The central design philosophy

The project's guiding principle, stated as plainly as possible: **a refusal to report a
number is a legitimate, valuable output — often more valuable than a number produced with
unstated confidence.** An enforcement tool that occasionally says "I need better information
to answer that" is more trustworthy than one that always gives an answer, because the second
kind is silently wrong exactly as often as its unstated assumptions fail. Every refusal
condition in the codebase exists because some specific way of being fooled was identified and
named, rather than papered over. The uncertainty budget exists so that a "COMPLIANT" verdict
means something specific and defensible, not just "the number I measured happened to be
above the line." Where a term in that budget is still an engineering estimate rather than a
lab measurement, the system says so in its own output rather than presenting every number
with the same false uniformity of confidence.

## 7. Project history, briefly

The measurement engine progressed through several versions across early September 2026,
each one adding a specific, deliberate correction: a refusal gate for package categories
this instrument cannot honestly measure at all; three additional identified sources of
uncertainty; explicit lower-precision reporting whenever any budget term is unmeasured
rather than implying false precision. An internal adversarial review on 2026-09-05 audited
the whole project and found, among other things, the decimal-point measurement risk
described above, several places where an unverified or superseded number could reach a
screen or a printed report unlabelled, and one statistical gate that compared the wrong
kind of statistic against its threshold. Most of those findings have since been fixed and
independently re-confirmed by actually executing the corrected code — the specific
exceptions are listed candidly in section 5 above, because the project's own standard is
that a limitation stated once, clearly, is worth more than a limitation quietly designed
around.
