# SIH26034 — checklist to 15 September

**Today is Saturday 12 September. The round is Tuesday 15 September.**
Three working days: Sat 12, Sun 13, Mon 14.

Print this. Put names in it. A box with no name against it does not get done.

---

## FIRST HOUR — nothing else starts until these are moving

These are the only items on this page that can end the project rather than
cost it points, and all three have been unowned since 5 September.

- [ ] **Resolve the portal deadline.** Your own §16 says *"20 or 30 September.
      Two sources disagree."* Message the SPOC today. If it is the 20th, the
      submission window opens the day after the internal round.
      Owner: `_____`
- [ ] **Confirm the internal round's time limit and rubric.** Everything about
      which cut tier to rehearse depends on this and it is still an assumption.
      Owner: `_____`
- [ ] **Confirm team registration status** on the portal and the team
      composition rules against *current* SIH guidelines, not last year's.
      Owner: `_____`
- [ ] **Put six names in the §13 owner table.** It has read `_____` in all six
      slots for a week.
      Owner: whoever reads this first

---

## THE PRIORITY ORDER CHANGED TODAY — read this before planning

Earlier advice was *camera first*. **That was right on Thursday and is wrong
now.** `naive_vs_calibrated.py` runs the entire differentiator argument on
synthetic renders, from a laptop, with no rig attached. The camera is no longer
load-bearing for the 15th.

That means:

| | before today | now |
|---|---|---|
| Differentiator narrative | needs a working rig | **runs from the laptop** |
| Camera path | must-have | **nice-to-have for the 15th, must-have for nationals** |
| Parity web app | competing for time with the rig | **the critical path** |

If you cannot staff everything: **build the app, rehearse the comparison demo,
and let the rig slip.** The rig is the better demo if it works and it is the
single most likely thing to fail in a room you have not tested in.

---

## SATURDAY 12 — parity build starts, differentiator locked

**Web app (2 people)**
- [ ] Lovable project created, auth working, two roles (officer, supervisor)
- [ ] Image upload + stored with the scan record
- [ ] Vision extraction returning structured JSON for the six Rule 6(1)
      declarations
- [ ] Data model per BUILD-SPEC §4 — `findings` and `measurements` stay
      separate tables

**Differentiator (1 person, ~1 hour — it is already built)**
- [ ] Run `python3 naive_vs_calibrated.py` and read the output end to end
- [ ] Rehearse the two attacks printed at the bottom of that output. Both.
      They are the only two ways this beat loses.
- [ ] Memorise the non-benchmark sentence verbatim. If anyone implies on stage
      that we tested a competitor's system, one question ends it.

**Statute (1 person, 1–2 hours — job 1, still not done)**
- [ ] Read G.S.R. 629(E) and its corrigendum together from the Gazette
- [ ] Record notification / publication / commencement as three separate dates
- [ ] Settle the 50–100 cm² cell. If it stays unsettled, `disputed=True` stays
      and that is a legitimate outcome — do not resolve it by preference
- [ ] While you have the Gazette open: **does Rule 9 carry a legibility or
      prominence provision separate from Rule 7(2)?** The competing entry cites
      Rule 9(3) for font. Our §15 flagged 7-vs-9(3) as unresolved and we closed
      it to 7(2). Both may exist. Do not assert either way without the text

**Rig (1 person — optional for the 15th, start it anyway)**
- [ ] `python3 demo_script.py` against a real camera for the first time ever
- [ ] `select_roi()` is new code written 12 Sep with no self-test behind it.
      Test it or use the typed-coordinate fallback
- [ ] Log the result in `DAILY_LOG.md` either way

---

## SUNDAY 13 — parity finished, corrections applied

**Web app (2 people)**
- [ ] Rule 6(1) checks: present / absent per declaration, three states each
      (`PASS` / `FAIL` / `CANNOT DETERMINE` — never two)
- [ ] Every field shows its source label. `EXTRACTED — OCR, unverified` on the
      six; `MEASURED — U(k=2), scale-referenced` on height. **Do not let this
      get visually normalised.** It is the product
- [ ] Refusal renders as a calm panel with a next action, not a red error
- [ ] PDF export + CSV export
- [ ] Scan history table with search
- [ ] Dashboard: four counters and a recent-scans list. Thin is fine

**Document corrections (1 person, ~1 hour) — all four found in the 12 Sep audit**
- [ ] Slide 5: strike *"`FLOOR_LIMITED` may be a second [confirmed firing]"*.
      It cannot fire in production — it stops firing at exactly 30.0 px/mm,
      which is exactly `min_px_per_mm`. Replace with the finding, it is stronger
- [ ] Slide 5: refusal code count is **20**, not nineteen.
      `LEGAL_MODEL_UNAVAILABLE` arrived with 7.9 and was never re-counted
- [ ] §8 and §15: gate ledger is **nine — five placeholder, four derived**, not
      eight/three. The uncounted derived gate is `_FIDUCIAL_PICK_PX`
- [ ] §15 and the Q&A card: add the **ROI-boundary sensitivity** disclosure.
      0.0064 mm, unbudgeted ninth term, biases toward COMPLIANT. Draft answer is
      in `AUDIT-2026-09-12.md` §5
- [ ] §13a item 9 can be closed. The contradiction was never real — the
      sampling sweep's label is a `mm_to_px` return value, not a `Refusal`

**Demo packets (1 person)**
- [ ] Fill `demo_packets.md` **before** running anything through the system.
      Predictions first. That is the entire point of the file
- [ ] Include ≥1 embossed/moulded item for `MEASURAND_UNDEFINED`
- [ ] Record the ROI box drawn for each packet — new, from the 12 Sep finding

---

## MONDAY 14 — rehearsal, and nothing new gets built

**Hard rule: no new features Monday.** A feature added the night before a
demo is a feature nobody has watched fail.

- [ ] Pick the cut tier from the **confirmed** time limit (First Hour item 2)
- [ ] Full run-through with a stopwatch, twice
- [ ] Second run-through with someone playing a hostile judge
- [ ] Q&A answers said out loud, not read. Especially:
      - the decimal-point limitation (`hold the line`, do not improvise)
      - *"are your legal citations verified?"* (`hold the line`)
      - the two attacks on the comparison demo
      - **the two different `0.17`s** — the verdict line carries U at
        max(h,TL) = 0.17321; the budget report carries U at 1 mm = 0.16634.
        4.1% apart, identical at 2 d.p. Rehearse the answer to *"is that the
        same 0.17?"*, because it is no
- [ ] Failure drill: rig dies → app still stands alone at parity, and the
      comparison demo still runs off saved output. Practise that transition
- [ ] Laptop charged, files on it, `python3 lm_metrology_v7.py` runs clean on
      the actual demo machine

---

## THE CUT LINE — if you are behind on Monday morning

Cut in this order. Do not improvise the ordering on the day.

1. **Dashboard** — four counters. Say "monitoring view is stubbed"
2. **Role-based access** — one role. Say it
3. **CSV export** — PDF only
4. **The physical rig entirely** — the comparison demo carries the
   differentiator without it

**Never cut:** the six Rule 6 checks with their source labels, the height
module's uncertainty and refusal states, the comparison demo, or the
non-benchmark disclaimer.

---

## WHAT "READY" LOOKS LIKE ON TUESDAY MORNING

- A judge photographs a packet they brought; the app returns six findings, each
  labelled with how it was obtained
- One row says a height check is required
- The height result carries an uncertainty and either a verdict or a refusal —
  and the refusal, if it comes, is narrated as the point, not apologised for
- The comparison demo runs: same packet, three camera distances, verdict flips
  on one method and not the other
- A PDF comes out with the threshold's source tier printed on it
- Nobody says the word "accuracy" about this system, and nobody claims to have
  benchmarked anyone else's
