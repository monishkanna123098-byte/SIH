# Deploying through GitHub Codespaces

What this is: a way to **share** the instrument — a link a teammate, mentor or
judge can open — and a backup if the demo laptop fails.

What it is not: a hosted service. The design position in `CLAUDE.md` stands.
The app is local-first, runs with networking disabled, and stores its records
on local disk. A Codespace is a machine that happens to be somewhere else; it
does not change any of that, which is exactly why it was chosen over a PaaS.

---

## One-time setup

### 1. Add the secrets

GitHub → Settings → Codespaces → **Repository secrets**, scoped to this repo.
They arrive as environment variables; nothing is read from a file and nothing
is committed.

| Secret | Needed | Why |
|---|---|---|
| `LM_OFFICER_PASSWORD` | before any public link | `app/db.py` seeds `officer-2026`, which is in the repo |
| `LM_SUPERVISOR_PASSWORD` | before any public link | same, for `supervisor-2026` |
| `LM_VISION_API_KEY` | only for automated extraction | absent → the button does not render, manual path unchanged |
| `LM_VISION_PROVIDER` | with the key | `anthropic` or `gemini` |
| `LM_VISION_MODEL` | optional | e.g. `gemini-2.5-flash` |

Never paste a key into a form, a template, a commit or a chat window.

Generate the two passwords locally so the value never travels through a chat
window or a shell history you keep:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Run it twice, paste one value into each secret. `token_urlsafe` gives
URL-safe characters only, so nothing needs shell quoting if you ever export it
by hand.

Changing a secret takes effect on the codespace's next start, and **is applied
to the existing database** -- `init_db()` updates the stored hash when the
variable is set, so the committed password stops working even on a codespace
that was created before you set it. Stop and start the codespace after
changing a secret; a running one keeps the old value.

### 2. Open the Codespace

Code → Codespaces → **Create codespace on
`claude/adoring-meitner-gczaml`**.

`.devcontainer/setup.sh` runs once on create: installs the `tesseract` binary
via apt, pip-installs `requirements.txt`, then imports every dependency and
prints the tesseract version so a broken image fails loudly instead of at the
first inspection.

Provisioning takes a few minutes, most of it scipy and opencv.

---

## Running it

```bash
./run.sh
```

The devcontainer sets `LM_HOST=0.0.0.0` and `LM_RELOAD=0`. Outside a
Codespace, `run.sh` is unchanged: `127.0.0.1:8000` with `--reload`.

VS Code raises a notification for port 8000; the **Ports** panel has the URL.

### Port visibility

Forwarded ports are **private by default** — only your GitHub account can open
them. That is the right setting for working on it alone.

To share, set the port's visibility to **Public** in the Ports panel. Anything
with the URL can then reach the login page, so set the two password secrets
first. If you serve on a non-loopback interface while either is still the
committed default, the app prints a warning to stderr at startup.

---

## "Username or password not recognised"

Run this in the Codespace terminal. It prints lengths and yes/no only -- no
password -- so the output is safe to paste anywhere:

```bash
python3 whoami-check.py
```

It says which password each account is actually on, and what to type. The three
causes, in the order they happen:

1. **The secrets were added after the codespace was created.** They only reach
   the container at start. Stop and start the codespace -- not just the server.
2. **The account rotated and you are typing the old password.** Once
   `LM_OFFICER_PASSWORD` is set, `officer-2026` stops working by design. Type
   the value you put in the secret.
3. **You no longer have the value.** Set the secret again to something you do
   have, stop and start the codespace, and the account rotates to it.

## Cost

GitHub Pro includes 180 Codespaces core-hours and 20 GB storage per month. A
2-core machine spends 2 core-hours per wall-clock hour, so roughly 90 hours.

**Stop the codespace when you are not demoing** — Code → Codespaces → ⋯ → Stop.
It idles out on its own after 30 minutes by default, but stopping is
immediate. Storage is billed while it exists, so delete codespaces you have
finished with.

---

## Where the data goes

`data/` — SQLite, uploaded images, generated PDFs and DOCXs, `session.key` —
lives on the codespace volume. It is gitignored and never committed.

- Survives stop/start.
- **Lost when the codespace is deleted.**

Inspection records carry a SHA-256 content hash and the report calls itself
tamper-evident. If a record matters, download the PDF or DOCX before deleting
the codespace. Do not treat the codespace as the archive.

---

## Confirming it is intact

Run all seven suites inside the Codespace before demoing:

```bash
for f in lm_legal_model lm_capture lm_declarations lm_extract lm_report; do
  python3 $f.py | grep -i "self-test"
done
python3 test_integration.py | tail -3
python3 test_webapp.py | tail -3
```

Expected: **81 / 114 / 83 / 34 / 26**, **27** integration, **334** webapp, all
`0 failed`. The OCR cross-check needs the tesseract binary; `setup.sh` installs
it, and `tesseract --version` confirms it.

---

## One thing that does not change

Run one process. The read-then-write inspection-ID race recorded in
`ACCEPTANCE-2026-09-13.md` was judged acceptable at a single process and was
not reproducible at 40 concurrent requests. Do not start a second worker
(`--workers`) to make it feel faster.
