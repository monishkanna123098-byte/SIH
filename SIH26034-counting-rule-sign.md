# COUNTING RULE — POST WHERE THE SURVEY RUNS

## What counts as a glyph in the measured region:

# EVERY INK MARK.

Letters. Numerals. The currency symbol. The decimal point.

## What does NOT count:

Whitespace only.

---

**This is the rule as already decided in the project brief — this sign
exists so it's visible during the survey, not so it gets re-decided by
whoever's running the camera that day.**

**Known consequence, already documented, not a reason to change the
rule mid-survey:** a decimal point is a tiny ink mark, and the current
version of the code can pick it as the "governing" (shortest) glyph in a
region, which can print DEFICIENT on a compliant price label. If a survey
result looks wrong, check whether the ROI included a decimal point or
other punctuation before assuming the package failed — **log it either
way**, and note in `DAILY_LOG.md` whether the ROI included punctuation.
That data is useful either way: it's evidence for how often this known
limitation actually bites on real packaging.
