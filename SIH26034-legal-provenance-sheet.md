# Legal Provenance — One Page

**The governing rule, confirmed against a primary source on 2026-09-07:**
Legal Metrology (Packaged Commodities) Rules, 2011, **Rule 7(2)** — height of

**The full chain back to the Act, fetched today from the primary source
(indiacode.nic.in's current consolidated text, updated to 7 May 2026):**
the Rules exist under the **Legal Metrology Act, 2009 (Act No. 1 of 2010),
Section 18** ("Declarations on pre-packaged commodities" — no package may be
sold unless it "bears thereon such declarations... as may be prescribed"),
with the rule-making power itself at **Section 52(2)(j)**, which specifically
authorises rules on "the standard quantities or number and the manner in
which the packages shall bear the declarations and the particulars under
sub-section (1) of section 18." That is the complete, primary-sourced chain:
Act s.18 + s.52(2)(j) → PC Rules 2011 → Rule 7(2). Worth having ready if a
judge asks "under what law," since it's now fully backed, unlike the
table values below it.

numerals and letters. (Not Rule 7(3): that sub-rule governs *width*, one-third
of height, with exceptions for numeral "1" and letters i/I/l. An earlier
version of this project's citation had the right rule, wrong sub-rule.)

**How we know this:** a Gazette-notification compilation hosted by the
Tripura High Court (thc.nic.in), running sequential amendment notifications
through **G.S.R. 778(E), dated 23 October 2025**, which amends "rule 7,
sub-rule (2)" for height and "sub-rule (3)" for width in as many words. This
is closer to primary than anything cited earlier in this project — it's the
actual notification text, not a law-firm summary of it — but it is still not
the certified Gazette PDF itself.

**What that same amendment also settled:** packages containing medical
devices are carved out of both 7(2) and 7(3), deferring instead to the
Medical Devices Rules, 2017. This matches this project's own existing
decision to scope medical devices out — good corroboration, not new scope.

**What is still NOT resolved, and must not be presented as settled:**

- **The actual height figures in the current Table-I** that Rule 7(2) points
  to. The 2025 compilation shows what changed, not the table's present
  contents. Our working table is transcribed from a secondary aggregator,
  source tier `AGGREGATOR`, confidence `UNVERIFIED` — printed as such on
  every report line this project produces, on purpose.
- **The 50–100 cm² ordinary-category bracket** is flagged `disputed=True` in
  code. A corrigendum to the 2017 amendment (G.S.R. 629(E), 23.6.2017) is
  reported to change one cell in the table from 1.5mm to 2.0mm; nobody on
  this project has read that corrigendum, so which cell it touches is
  unconfirmed. **Do not guess at this on stage.** The system refuses
  (`THRESHOLD_DISPUTED`) rather than print an unverified number for that
  bracket, and does not leak either candidate value into the refusal message.
  **New evidence, 2026-09-09, not a resolution:** found the complete current
  Table-I from a third independent source (a law firm's dated analysis,
  legalculinary.com). Every cell matches what's already encoded, including
  A≤50/formed already reading 2.0mm — consistent with the corrigendum having
  already been applied elsewhere in that table, which would mean the
  50–100/ordinary cell (1.5mm) was never the disputed one. This shifts the
  balance of evidence but doesn't settle it — that source doesn't discuss a
  corrigendum at all, so its agreement could mean "already correct" or just
  "didn't check." `disputed=True` stays until the Gazette itself is read.
  **The full table, for reference** (A = principal display panel area, cm²):

  | Area | Normal (mm) | Formed/blown/moulded (mm) |
  |---|---|---|
  | A ≤ 50 | 1.0 | 2.0 |
  | 50 < A ≤ 100 | 1.5 *(disputed)* | 3.0 |
  | 100 < A ≤ 500 | 2.5 | 4.0 |
  | 500 < A ≤ 2500 | 4.0 | 6.0 |
  | A > 2500 | 6.0 | 6.0 *(the one bracket where both columns match — flagged for a second look in code, not a refusal)* |
- **A specific citation "G.S.R. 1373(E), dated 7.11.2017"** surfaced in an
  internal planning document this week does not appear to exist — searched
  multiple ways, found nothing connecting that number to Legal Metrology or
  to India at all. Do not spend time looking for it; do not cite it.

**The one sentence for Q&A:** *"We can tell you exactly which rule and which
sub-rule govern this, sourced to an actual Gazette notification. We can't yet
tell you the certified figure for every bracket, and we say so on the
instrument's own output rather than guessing — including refusing to give a
verdict on the one bracket we know is disputed."*
