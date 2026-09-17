#!/usr/bin/env python3
"""Why is the Gemini branch returning 404? Diagnostic only; changes nothing.

    python3 diag_gemini.py --list          what the key can actually call
    python3 diag_gemini.py                 one instrumented call per model
    python3 diag_gemini.py <model> [...]   one instrumented call per named model

Reads LM_VISION_API_KEY from the environment. The key is never printed.

Background, established earlier: Google validates the API key BEFORE it
resolves the model name -- a bogus key returns 400 INVALID_ARGUMENT for every
model, including one that does not exist. So a 404 proves the key
authenticated. It is not a credential problem; it is that the model does not
serve generateContent on this API version for this key. --list settles which
models do.
"""
import io
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"


def key_or_exit() -> str:
    key = os.environ.get("LM_VISION_API_KEY", "").strip()
    if not key:
        print("LM_VISION_API_KEY is not set in this shell; nothing to call.")
        raise SystemExit(2)
    print("key: %d chars (an AI Studio key is 39)\n" % len(key))
    return key


def list_models(key: str) -> int:
    """Every model this key can reach, and which ones can be used here."""
    models, page = [], None
    while True:
        url = ENDPOINT + "?pageSize=1000" + (("&pageToken=" + page) if page else "")
        req = urllib.request.Request(url, headers={"x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode())
        except Exception as exc:                       # noqa: BLE001 - reporting
            detail = ""
            if hasattr(exc, "read"):
                try:
                    detail = exc.read().decode()[:400]
                except Exception:                      # noqa: BLE001
                    pass
            print("could not list models: %s %s\n%s"
                  % (type(exc).__name__, exc, detail))
            return 1
        models += body.get("models", [])
        page = body.get("nextPageToken")
        if not page:
            break

    usable = [m for m in models
              if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    print("%d models visible, %d support generateContent.\n" % (len(models), len(usable)))
    print("USABLE -- put one of these in LM_VISION_MODEL:")
    for m in sorted(x["name"].split("/")[-1] for x in usable):
        print("   ", m)

    others = sorted(set(m["name"].split("/")[-1] for m in models)
                    - set(x["name"].split("/")[-1] for x in usable))
    if others:
        print("\nVISIBLE BUT NOT USABLE here (listed, but no generateContent --")
        print("asking one of these for an extraction is exactly the 404):")
        for m in others:
            print("   ", m)
    return 0


def call_models(key: str, names: list[str]) -> int:
    os.environ.setdefault("LM_VISION_DEBUG", "1")
    from app import vision
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 32), (255, 255, 255)).save(buf, format="PNG")
    png, prompt = buf.getvalue(), "Reply with the single word OK."

    for name in names:
        print("=" * 72)
        print("MODEL:", name)
        print("=" * 72)
        try:
            out = vision.make_call("gemini", key, name)(png, prompt)
            print("RESULT ok, %d chars: %r" % (len(out), out[:200]))
        except vision.VisionUnavailable as exc:
            print("RESULT VisionUnavailable:", exc)
        except vision.VisionTransportError as exc:
            print("RESULT VisionTransportError:", exc)
        except Exception as exc:                       # noqa: BLE001 - reporting
            print("RESULT unmapped %s: %s" % (type(exc).__name__, str(exc)[:300]))
        print()
    return 0


def main() -> int:
    args = sys.argv[1:]
    key = key_or_exit()
    if args and args[0] in ("--list", "-l"):
        return list_models(key)
    configured = os.environ.get("LM_VISION_MODEL", "").strip()
    return call_models(key, args or [configured or "gemini-2.0-flash"])


if __name__ == "__main__":
    sys.exit(main())
