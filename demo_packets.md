# Demo Packets

Fill this in BEFORE running any packet through the system — a prediction you
check against, not a description you write after the fact. That's the whole
point of this file per the plan.

Criteria: ≥3 in the A≤50cm² bracket, clean printed text, no decimal point in
the ROI; ≥1 embossed/moulded item (to demonstrate MEASURAND_UNDEFINED); ≥1
where the digit region isolates cleanly.

---

## Packet 1
- **Product name:**
- **Declared PDP area (cm²):**
- **Declared category:** (general / blown_formed_moulded_embossed_perforated)
- **Commodity class:**
- **Expected verdict:** (COMPLIANT / DEFICIENT / REQUIRES_PHYSICAL_VERIFICATION / MEASURAND_UNDEFINED / refusal — name the code)
- **Why you expect that:**
- **Actual verdict (fill in after running):**
- **Match?**

## Packet 2
- **Product name:**
- **Declared PDP area (cm²):**
- **Declared category:**
- **Commodity class:**
- **Expected verdict:**
- **Why you expect that:**
- **Actual verdict (fill in after running):**
- **Match?**

## Packet 3
- **Product name:**
- **Declared PDP area (cm²):**
- **Declared category:**
- **Commodity class:**
- **Expected verdict:**
- **Why you expect that:**
- **Actual verdict (fill in after running):**
- **Match?**

## Packet 4 (embossed/moulded — for MEASURAND_UNDEFINED)
- **Product name:**
- **Declared PDP area (cm²):**
- **Declared category:** blown_formed_moulded_embossed_perforated
- **Commodity class:**
- **Expected verdict:** MEASURAND_UNDEFINED
- **Why you expect that:** no ink edge to find on formed/embossed characters
- **Actual verdict (fill in after running):**
- **Match?**

## Packet 5 (clean digit isolation)
- **Product name:**
- **Declared PDP area (cm²):**
- **Declared category:**
- **Commodity class:**
- **Expected verdict:**
- **Why you expect that:**
- **Actual verdict (fill in after running):**
- **Match?**

---

**If actual ≠ expected on any packet:** that's the finding, not a bug to
quietly fix before anyone sees it. Log it in `DAILY_LOG.md` with the packet
number and both verdicts, and figure out which one was wrong — the
prediction or the instrument — before moving on.
