#!/usr/bin/env bash
# Local only. Nothing is fetched at runtime: no CDN fonts, no CDN CSS, no icon
# library. This runs on a laptop with networking disabled.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
