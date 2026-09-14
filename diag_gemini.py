"""Temporary diagnostic: one real call per model name, fully instrumented.

Reads the key from LM_VISION_API_KEY. The key is never printed. Run:

    LM_VISION_DEBUG=1 LM_VISION_API_KEY=... python3 diag_gemini.py
"""
import io, os, sys
sys.path.insert(0, "/home/user/SIH")
os.environ.setdefault("LM_VISION_DEBUG", "1")

from app import vision

MODELS = sys.argv[1:] or ["gemini-2.5-flash", "gemini-flash-latest"]

key = os.environ.get("LM_VISION_API_KEY", "").strip()
if not key:
    print("LM_VISION_API_KEY is not set; nothing to call.")
    raise SystemExit(2)
print("key: %d chars, prefix %r" % (len(key), key[:4]))
print("AI Studio API keys are 39 chars with prefix 'AIza'.\n")

from PIL import Image
buf = io.BytesIO()
Image.new("RGB", (64, 32), (255, 255, 255)).save(buf, format="PNG")
PNG = buf.getvalue()
PROMPT = "Reply with the single word OK."

for m in MODELS:
    print("=" * 72)
    print("MODEL:", m)
    print("=" * 72)
    try:
        call = vision.make_call("gemini", key, m)
        out = call(PNG, PROMPT)
        print("RESULT ok, %d chars: %r" % (len(out), out[:200]))
    except vision.VisionUnavailable as e:
        print("RESULT VisionUnavailable:", e)
    except vision.VisionTransportError as e:
        print("RESULT VisionTransportError:", e)
    except Exception as e:
        print("RESULT unmapped %s: %s" % (type(e).__name__, str(e)[:300]))
    print()
