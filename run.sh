#!/usr/bin/env bash
# Local by default. Nothing is fetched at runtime: no CDN fonts, no CDN CSS, no
# icon library. This runs on a laptop with networking disabled.
#
# The three variables below exist so the same script works inside a Codespace,
# whose port-forwarding agent needs the server on all interfaces. Unset, the
# behaviour is exactly what it has always been: 127.0.0.1:8000 with --reload.
set -euo pipefail
cd "$(dirname "$0")"

reload=()
[ "${LM_RELOAD:-1}" = "1" ] && reload=(--reload)

exec python3 -m uvicorn app.main:app "${reload[@]}" \
     --host "${LM_HOST:-127.0.0.1}" --port "${LM_PORT:-8000}"
