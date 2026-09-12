# Q&A Card

Answer from this card. Don't improvise on the ones marked **hold the line** —
that's where a confident ad-lib turns a known limitation into an accidental
overclaim.

---

**"What's your accuracy?"**
U(k=2) = 0.17mm at a 1mm requirement, rising with the requirement because
three of eight budget terms are fractional errors that scale with height.
All eight terms are modelled, not measured yet — say that before anyone asks.

**"Why does it only check letter height? The rules require six other things
too."** — **hold the line**
Because height is the one requirement that needs real metrology — a scale
reference, an uncertainty budget, a decision under ambiguity. Checking
whether a manufacturer's address is *present* is a different, much shallower
problem. We went deep on the hard part instead of wide across the easy ones.

**"Has this run on a real camera?"**
No. `lm_capture.py` — the scale-reference layer — is self-tested at 114 of
114 checks and has never been connected to a physical sensor. Say the number,
say the gap, in that order.

**"What happens if the measurement is ambiguous?"**
It says so. `REQUIRES_PHYSICAL_VERIFICATION` isn't a failure state — it's what
the instrument returns when the uncertainty band straddles the legal
threshold, which is the honest answer when the honest answer is "can't tell
from this image alone." A tool that always picks a side in that band is wrong
exactly as often as the band is wide.

**"What if I hand you a price label with a decimal point?"** — **hold the
line, do not improvise**
This is the project's own known limitation, not a trick question, and the
honest answer is short: the current version measures the shortest ink mark in
the selected region, which can be a decimal point rather than a digit, and
that can produce a false DEFICIENT on a compliant label. We know about it,
it's the single largest risk in the project, and it isn't fixed, because the
correct fix needs a statutory definition of which characters carry a height
requirement at all — that's a legal question, not a code one, and we're not
willing to guess at law to make a demo look finished. If asked what
mitigates it today: operator discipline in region selection, and a
dispersion-based guard that exists in code but is deliberately left off,
because turning it on without knowing its false-refusal rate on real
packaging would trade one unmeasured risk for another.

**"Is this AI-powered?"**
It's applied measurement science — a calibrated optical instrument with a
JCGM 106 uncertainty budget, not a machine-learning model. That's a
deliberate choice: the hard part of this problem is metrology, not pattern
recognition, and a classifier wouldn't produce a defensible verdict where
this system's math does.

**"What rule are you actually enforcing?"**
Legal Metrology (Packaged Commodities) Rules 2011, Rule 7(2) — confirmed
2026-09-07 against an actual Gazette notification (G.S.R. 778(E), 2025), not
a summary. Full detail on the provenance sheet.

**"Are your legal citations verified?"** — **hold the line**
Partially, and we say exactly which part. The rule number and sub-rule are
now sourced to an actual Gazette notification. The specific height figures in
the current table are sourced to a secondary aggregator, and one bracket is
flagged disputed in our own code — the system refuses to give a verdict for
that bracket rather than guess. We are not going to state a table value more
confidently than we've actually verified it.

**"Why should we trust a system that admits this many open problems?"**
Because it admits them. Every refusal code, every "modelled not measured"
label, every disputed bracket is something we found and chose to disclose
rather than paper over — including in this card. The alternative is a system
that looks more finished and is less honest about where it could be wrong,
which is a worse thing to hand to an enforcement context, not a better one.
