# CHUNK 6 — the pipeline view

Paste this as your message to Claude Code, **only if chunks 4 and 5 are done
and stable**.

**This is the cut line.** Chunk 6 is the nicest-looking thing on the list and
the least load-bearing. If it is Sunday evening and chunk 5 is shaky, skip this
entirely and spend the time on rehearsal. Nothing in the pitch depends on it.

---

## Before you write any code

1. Re-read `CLAUDE.md`.
2. Confirm **81 / 114 / 39 / 34 / 26** and **27**, all `0 failed`.
3. Confirm chunk 5's eight conditions still hold, especially the two absence
   cases and the disputed-bracket refusal.

---

## What you are building

A five-stage pipeline strip showing where an inspection is as it runs.

```
01 CAPTURE  →  02 CALIBRATE  →  03 EXTRACT  →  04 MEASURE  →  05 ADJUDICATE
```

### Why, and where it comes from

A competing entry (SatyaLabel) runs a four-stage animated pipeline on its
landing page: `01_PIXELS → 02_EXTRACT → 03_VERIFY → 04_PENALTY`. It is the best
thing on that site — it makes the architecture legible in about four seconds and
lets a judge follow a demo without narration.

**Their pipeline has no CALIBRATE stage, because their system has no scale
reference.** Neither does any of the ~94 repositories on this problem statement.
That stage existing at all is the differentiator, rendered before anyone speaks.

Take the pattern. Take nothing else — no code, no markup, no copy, and none of
their emblem or government branding.

---

## Stage semantics

| Stage | Shows | Idle state |
|---|---|---|
| 01 CAPTURE | image received, panels declared, coverage status | "awaiting image" |
| **02 CALIBRATE** | **px/mm, artifact description, artifact tier** | **"no scale reference — height cannot be measured"** |
| 03 EXTRACT | count of declarations read, extractor used | "awaiting declarations" |
| 04 MEASURE | band, or the refusal code | "not measured" |
| 05 ADJUDICATE | headline + three counts, officer determination if present | "awaiting determination" |

**Stage 02 gets equal visual weight — not less.** It will often be the emptiest
stage, because a scale reference is the thing most inspections will lack. An
empty CALIBRATE stage saying *"no scale reference — height cannot be measured"*
is a true and useful statement, and it is the one stage a competitor cannot
draw at all. Do not shrink it, collapse it, or hide it when empty.

---

## Implementation

Server-rendered from the scan record. **No new dependencies, no npm, no
animation library, no CDN.** Vanilla CSS and, if genuinely needed, a few lines
of vanilla JS.

- Horizontal strip on desktop, vertical stack below ~700px.
- Three states per stage: `pending` (grey, dashed rule), `done` (navy rule,
  values shown), `refused` (cream background, reason shown — never red).
- Place it at the top of the results page, above the three tier sections.
- Same design tokens as chunk 4. Serif stage labels, monospace values.

Animation: none required. If you add a transition, keep it under 200ms and make
it work with `prefers-reduced-motion: reduce`. A pipeline that animates on every
page load is worse than one that does not — it reads as decoration, and on the
fourth demo run it is an irritation.

---

## Do NOT

- Fake progress. Each stage reflects stored record state, not a timer.
- Show a stage as `done` when it was skipped. Skipped is `pending`.
- Add a percentage, progress bar, or completion ring. Invariant 4.
- Use green ticks or red crosses. Same reason as the findings table: two
  colours collapse three states.
- Add a sixth stage for penalties. Outside the problem statement.
- Touch `lm_metrology_v7.py`, `lm_capture.py` or `lm_legal_model.py`.

---

## Definition of done

1. The strip renders on the results page for every scan, including brand-new
   and partially-complete ones.
2. An inspection with no scale reference shows CALIBRATE as pending with its
   explanatory text — **not** hidden, **not** shrunk.
3. A refused measurement shows MEASURE in the refused state with its code, in
   cream, not red.
4. Readable at 700px wide.
5. `prefers-reduced-motion` respected if anything animates.
6. No new dependency in `requirements.txt`.
7. Every self-test still passes at its original count.
8. The app still runs with networking disabled.

Report what you built and what you verified. **Then stop.**

---

## After this

Chunk 7 is rehearsal, on Monday 14 September, and it is not a coding task.
**No new features Monday.** A feature added the night before a demo is a feature
nobody has watched fail. `CHECKLIST-to-15-Sep.md` has the run order, the Q&A
list and the failure drill.
