"""FastAPI routes.

A single local application that imports the engines directly -- not a frontend
talking to a backend. There is no HTTP between layers, no CORS, no build step
and nothing fetched at runtime. "Web application" is satisfied by a browser
pointed at localhost:8000.

This file must not import `lm_*`. Routes call `service`; `service` calls the
engines. See app/service.py.
"""
from __future__ import annotations

import io
import math
import os
import uuid
from urllib.parse import quote
from typing import Optional

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image

from . import auth, db, service

_HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Legal Metrology inspection record", docs_url=None,
              redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(_HERE, "static")),
          name="static")
templates = Jinja2Templates(directory=os.path.join(_HERE, "templates"))

ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


def _render(request: Request, template: str, user: Optional[dict],
            status_code: int = 200, **ctx):
    return templates.TemplateResponse(
        request, template, {"user": user, **ctx}, status_code=status_code)


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


# --------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if auth.current_user(request):
        return RedirectResponse("/upload", status_code=303)
    return _render(request, "login.html", None)


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(""), password: str = Form("")):
    user = auth.authenticate(username, password)
    if user is None:
        return _render(request, "login.html", None,
                       error="Username or password not recognised.")
    resp = RedirectResponse("/upload", status_code=303)
    resp.set_cookie(auth.COOKIE_NAME, auth.make_cookie(user["id"]),
                    httponly=True, samesite="lax", max_age=auth.MAX_AGE)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/")
def index():
    return RedirectResponse("/upload", status_code=303)


# --------------------------------------------------------------------------
# Upload -- new inspection
# --------------------------------------------------------------------------
@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    return _render(request, "upload.html", user,
                   fields=service.declaration_fields(),
                   panels=service.PANELS, categories=service.CATEGORIES,
                   commodity_classes=service.COMMODITY_CLASSES,
                   min_ppm=service.MIN_PX_PER_MM, values={}, form={},
                   extraction=service.extraction_available())


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request,
                 product_name: str = Form(""),
                 declared_category: str = Form(""),
                 declared_pdp_area_cm2: str = Form(""),
                 operator_id: str = Form(""),
                 coverage_note: str = Form(""),
                 declared_commodity_class: str = Form(""),
                 declared_glyph_count: str = Form(""),
                 scale_ppm: str = Form(""),
                 scale_artifact: str = Form(""),
                 scale_artifact_tier: str = Form(""),
                 image: UploadFile | None = File(None)):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()

    form = await request.form()
    values = {k: (form.get(k) or "") for k in service.FIELD_KEYS}
    panels = [p for p in form.getlist("panels") if p in service.PANELS]
    examined = form.get("operator_examined_package") is not None

    # Automated-extraction state, carried on the form so a validation error
    # cannot silently downgrade machine values into officer-typed ones.
    vision_model = (form.get("vision_model") or "").strip()
    used_vision = bool(vision_model)
    machine_values = ({k: (form.get(f"{k}__machine") or "") for k in service.FIELD_KEYS}
                      if used_vision else None)
    machine_confirmed = ({k: (form.get(f"{k}__ocr") or "") for k in service.FIELD_KEYS}
                         if used_vision else None)
    reviewed_keys = {k for k in service.FIELD_KEYS if form.get(f"{k}__reviewed")}

    def again(error: str):
        return _render(request, "upload.html", user,
                       fields=service.declaration_fields(),
                       panels=service.PANELS, categories=service.CATEGORIES,
                       commodity_classes=service.COMMODITY_CLASSES,
                       min_ppm=service.MIN_PX_PER_MM,
                       extraction=service.extraction_available(),
                       values=values, error=error,
                       form={"product_name": product_name,
                             "declared_category": declared_category,
                             "declared_pdp_area_cm2": declared_pdp_area_cm2,
                             "operator_id": operator_id,
                             "coverage_note": coverage_note,
                             "declared_commodity_class": declared_commodity_class,
                             "declared_glyph_count": declared_glyph_count,
                             "scale_ppm": scale_ppm,
                             "scale_artifact": scale_artifact,
                             "scale_artifact_tier": scale_artifact_tier,
                             "panels": panels, "examined": examined,
                             "vision_model": vision_model,
                             "machine": machine_values or {},
                             "ocr": machine_confirmed or {},
                             "reviewed": sorted(reviewed_keys)})

    if not product_name.strip():
        return again("Product name is required.")

    area: Optional[float] = None
    if declared_pdp_area_cm2.strip():
        try:
            area = float(declared_pdp_area_cm2)
        except ValueError:
            return again("Declared PDP area must be a number, in cm2.")
        # nan and inf both survive float(), and `area <= 0` is False for both
        # (every nan comparison is False). An infinite panel area travelling
        # down to the legal model is nonsense on a confident-looking path, so
        # it is refused here rather than guessed at or coerced to a default.
        if not math.isfinite(area):
            return again("Declared PDP area must be a finite number, in cm2.")
        if area <= 0:
            return again("Declared PDP area must be greater than zero.")

    if declared_category and declared_category not in service.CATEGORIES:
        return again("Unrecognised declared category.")

    if (declared_commodity_class
            and declared_commodity_class not in service.COMMODITY_CLASSES):
        return again("Unrecognised commodity class.")

    glyphs: Optional[int] = None
    if declared_glyph_count.strip():
        try:
            glyphs = int(declared_glyph_count)
        except ValueError:
            return again("Expected glyph count must be a whole number.")
        if glyphs <= 0:
            return again("Expected glyph count must be greater than zero.")

    # px/mm. There is no DPI fallback and no default: without a scale reference
    # there is no measurement, and that is a correct outcome rather than a gap.
    ppm: Optional[float] = None
    if scale_ppm.strip():
        try:
            ppm = float(scale_ppm)
        except ValueError:
            return again("Scale must be a number, in pixels per millimetre.")
        if ppm <= 0:
            return again("Scale must be greater than zero pixels per millimetre.")

    # An unticked box with an operator id is coherent; a ticked box without one
    # is not -- `can_assert_absence()` needs both, and silently accepting the
    # tick would leave the officer believing they had unlocked absence claims.
    if examined and not operator_id.strip():
        return again("Operator ID is required when you confirm you examined "
                     "the physical package.")

    # The automation-bias gate. A model's silence must not become an accusation
    # because the checkbox happened to be next to it. service.create_inspection
    # raises ReviewRequired independently -- this is the friendly half.
    if used_vision and examined:
        unreviewed = [k for k in service.FIELD_KEYS if k not in reviewed_keys]
        if unreviewed:
            return again("Review each declaration before stating you examined "
                         "the package.")

    image_path = None
    if image is not None and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_IMAGE:
            return again(f"Unsupported image type '{ext}'. Accepted: "
                         + ", ".join(sorted(ALLOWED_IMAGE)))
        data = await image.read()
        if data:
            # The extension is a claim, not evidence. Verify the bytes actually
            # decode as an image BEFORE anything is written or a scan record is
            # created -- a file that cannot be opened must not become an
            # inspection with an unusable evidence image attached to it.
            try:
                Image.open(io.BytesIO(data)).verify()
            except Exception:
                return again("That file is not a readable image.")
            name = f"{uuid.uuid4().hex}{ext}"
            os.makedirs(db.UPLOAD_DIR, exist_ok=True)
            with open(os.path.join(db.UPLOAD_DIR, name), "wb") as fh:
                fh.write(data)
            image_path = name

    try:
        inspection_id = service.create_inspection(
            user=user, product_name=product_name, values=values, panels=panels,
            examined=examined, operator_id=operator_id, note=coverage_note,
            declared_category=declared_category, declared_pdp_area_cm2=area,
            image_path=image_path, scale_ppm=ppm, scale_artifact=scale_artifact,
            scale_artifact_tier=scale_artifact_tier,
            declared_commodity_class=declared_commodity_class,
            declared_glyph_count=glyphs, machine_values=machine_values,
            reviewed_keys=reviewed_keys, vision_model=vision_model,
            machine_confirmed=machine_confirmed)
    except service.ReviewRequired as exc:
        return again(str(exc))
    return RedirectResponse(f"/scan/{inspection_id}", status_code=303)


@app.post("/extract-declarations")
async def extract_declarations(request: Request,
                               image: UploadFile | None = File(None)):
    """Run the configured vision provider over one image and return its values.

    Returns JSON, fills the form in place, and creates NOTHING. No scan record,
    no finding, no absence claim -- the officer reviews the six values first.
    Every failure below leaves the manual path usable and the upload intact.
    """
    user = auth.current_user(request)
    if user is None:
        return JSONResponse({"ok": False, "error": "Your session has expired. "
                             "Sign in again."}, status_code=401)
    if service.extraction_available() is None:
        return JSONResponse({"ok": False, "error": "No extraction service is "
                             "configured."}, status_code=400)
    if image is None or not image.filename:
        return JSONResponse({"ok": False, "error": "Choose an image first."},
                            status_code=400)
    ext = os.path.splitext(image.filename)[1].lower()
    if ext not in ALLOWED_IMAGE:
        return JSONResponse({"ok": False, "error": f"Unsupported image type "
                             f"'{ext}'."}, status_code=400)
    data = await image.read()
    if not data:
        return JSONResponse({"ok": False, "error": "That file is empty."},
                            status_code=400)
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        return JSONResponse({"ok": False,
                             "error": "That file is not a readable image."},
                            status_code=400)

    try:
        result = service.extract_from_image(data)
    except service.vision.VisionUnavailable:
        return JSONResponse({"ok": False, "error": "No extraction service is "
                             "configured."}, status_code=400)
    except service.vision.VisionTransportError as exc:
        # Could not reach it, or it timed out. Message names the remedy.
        return JSONResponse({"ok": False, "error":
                             f"Could not reach the extraction service ({exc}). "
                             f"Enter the declarations manually."},
                            status_code=502)
    except service.ex.ExtractionError:
        # It ANSWERED, with something unusable. Deliberately a different
        # message from the one above: six CANNOT_DETERMINE caused by a broken
        # pipeline must not read as a bad photograph.
        return JSONResponse({"ok": False, "error":
                             "The extraction service returned an unusable "
                             "response. Enter the declarations manually."},
                            status_code=502)
    except Exception:
        # Nothing else may reach the browser as a traceback, and no path may
        # reach a message (FIX 1a).
        return JSONResponse({"ok": False, "error":
                             "The extraction service could not be used. Enter "
                             "the declarations manually."}, status_code=500)
    return JSONResponse({"ok": True, "model": result["model"],
                         "values": result["values"],
                         "confirmed": result.get("confirmed", {}),
                         "ocr_available": result.get("ocr_available", False)})


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
@app.get("/scan/{inspection_id}", response_class=HTMLResponse)
def scan_results(request: Request, inspection_id: str):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    view = service.results_view(inspection_id)
    if view is None:
        return _render(request, "not_found.html", user, status_code=404,
                       inspection_id=inspection_id)
    return _render(request, "results.html", user, v=view,
                   may_determine=auth.may_determine(user, view["scan"]["user_id"]))


@app.post("/scan/{inspection_id}/determination")
def determination(request: Request, inspection_id: str,
                  verdict: str = Form(""), note: str = Form("")):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    scan = service.get_scan(inspection_id)
    if scan is None:
        return RedirectResponse("/history", status_code=303)
    if not auth.may_determine(user, scan["user_id"]):
        return RedirectResponse(f"/scan/{inspection_id}?denied=1", status_code=303)
    if not verdict.strip():
        return RedirectResponse(f"/scan/{inspection_id}?blank=1", status_code=303)
    service.record_determination(inspection_id, user["username"], verdict, note)
    return RedirectResponse(f"/scan/{inspection_id}", status_code=303)


@app.post("/scan/{inspection_id}/measure")
def measure(request: Request, inspection_id: str,
            x: str = Form(""), y: str = Form(""),
            w: str = Form(""), h: str = Form("")):
    """Measure the operator-declared region.

    The region arrives in IMAGE PIXEL coordinates. The browser scales from
    display coordinates before posting -- getting that wrong shifts the number
    in a way that is hard to see, so the conversion is done once, next to the
    canvas, and the raw values are echoed back on the page.
    """
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    scan = service.get_scan(inspection_id)
    if scan is None:
        return RedirectResponse("/history", status_code=303)
    if not auth.may_determine(user, scan["user_id"]):
        return RedirectResponse(f"/scan/{inspection_id}?denied=1", status_code=303)
    ok, message = service.measure_scan(inspection_id, (x, y, w, h))
    if ok:
        return RedirectResponse(f"/scan/{inspection_id}", status_code=303)
    return RedirectResponse(
        f"/scan/{inspection_id}?measure_error={quote(message)}", status_code=303)


@app.get("/scan/{inspection_id}/image")
def scan_image(request: Request, inspection_id: str):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    scan = service.get_scan(inspection_id)
    if scan is None or not scan["image_path"]:
        return RedirectResponse(f"/scan/{inspection_id}", status_code=303)
    # The stored name is generated server-side, but resolve and confine it
    # anyway so a hand-edited database row cannot read outside the directory.
    root = os.path.realpath(db.UPLOAD_DIR)
    path = os.path.realpath(os.path.join(root, os.path.basename(scan["image_path"])))
    if not path.startswith(root + os.sep) or not os.path.exists(path):
        return RedirectResponse(f"/scan/{inspection_id}", status_code=303)
    return FileResponse(path)


@app.get("/scan/{inspection_id}/image.roi")
def scan_image_roi(request: Request, inspection_id: str):
    """The evidence image with the operator-declared region drawn on it.

    A separate file: the original evidence image is never written to.
    """
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    scan = service.get_scan(inspection_id)
    if scan is None or not scan["image_annotated_path"]:
        return RedirectResponse(f"/scan/{inspection_id}", status_code=303)
    root = os.path.realpath(db.UPLOAD_DIR)
    path = os.path.realpath(
        os.path.join(root, os.path.basename(scan["image_annotated_path"])))
    if not path.startswith(root + os.sep) or not os.path.exists(path):
        return RedirectResponse(f"/scan/{inspection_id}", status_code=303)
    return FileResponse(path)


@app.get("/scan/{inspection_id}/report.{fmt}")
def report(request: Request, inspection_id: str, fmt: str):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    if fmt not in ("pdf", "docx"):
        return RedirectResponse(f"/scan/{inspection_id}", status_code=303)
    path = service.write_report(inspection_id, fmt)
    if path is None:
        return RedirectResponse("/history", status_code=303)
    media = ("application/pdf" if fmt == "pdf" else
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return FileResponse(path, media_type=media,
                        filename=f"{inspection_id}.{fmt}")


# --------------------------------------------------------------------------
# History and dashboard
# --------------------------------------------------------------------------
@app.get("/history", response_class=HTMLResponse)
def history(request: Request, q: str = ""):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    return _render(request, "history.html", user,
                   rows=service.history(q), q=q)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()
    return _render(request, "dashboard.html", user, d=service.dashboard())
