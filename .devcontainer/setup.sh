#!/usr/bin/env bash
# Codespaces provisioning. Runs once, on container create.
set -euo pipefail
cd "$(dirname "$0")/.."

# The OCR cross-check needs the tesseract BINARY, not just pytesseract. Without
# it the cross-check silently skips and every field stays
# verbatim_confirmed=None -- correct behaviour, but the differentiator becomes
# invisible, which on a demo machine is indistinguishable from it not existing.
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends tesseract-ocr
sudo rm -rf /var/lib/apt/lists/*

python3 -m pip install --upgrade --quiet pip
python3 -m pip install --quiet -r requirements.txt

echo
echo "tesseract: $(tesseract --version 2>&1 | head -1)"
python3 - <<'PY'
import importlib
for m in ("fastapi", "uvicorn", "numpy", "scipy", "cv2", "PIL", "reportlab",
          "docx", "pytesseract"):
    importlib.import_module(m)
print("python dependencies: all import cleanly")
PY
echo
echo "Ready. Start it with:  ./run.sh"
echo "Then open the forwarded port 8000 from the Ports panel."
