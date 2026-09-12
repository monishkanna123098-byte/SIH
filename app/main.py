"""FastAPI routes.

A single local application that imports the engines directly -- not a frontend
talking to a backend. There is no HTTP between layers, no CORS, no build step
and nothing fetched at runtime. "Web application" is satisfied by a browser
pointed at localhost:8000.

This file must not import `lm_*`. Routes call `service`; `service` calls the
engines. See app/service.py.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
                   values={}, form={})


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request,
                 product_name: str = Form(""),
                 declared_category: str = Form(""),
                 declared_pdp_area_cm2: str = Form(""),
                 operator_id: str = Form(""),
                 coverage_note: str = Form(""),
                 image: UploadFile | None = File(None)):
    user = auth.current_user(request)
    if user is None:
        return _login_redirect()

    form = await request.form()
    values = {k: (form.get(k) or "") for k in service.FIELD_KEYS}
    panels = [p for p in form.getlist("panels") if p in service.PANELS]
    examined = form.get("operator_examined_package") is not None

    def again(error: str):
        return _render(request, "upload.html", user,
                       fields=service.declaration_fields(),
                       panels=service.PANELS, categories=service.CATEGORIES,
                       values=values, error=error,
                       form={"product_name": product_name,
                             "declared_category": declared_category,
                             "declared_pdp_area_cm2": declared_pdp_area_cm2,
                             "operator_id": operator_id,
                             "coverage_note": coverage_note,
                             "panels": panels, "examined": examined})

    if not product_name.strip():
        return again("Product name is required.")

    area: Optional[float] = None
    if declared_pdp_area_cm2.strip():
        try:
            area = float(declared_pdp_area_cm2)
        except ValueError:
            return again("Declared PDP area must be a number, in cm2.")
        if area <= 0:
            return again("Declared PDP area must be greater than zero.")

    if declared_category and declared_category not in service.CATEGORIES:
        return again("Unrecognised declared category.")

    # An unticked box with an operator id is coherent; a ticked box without one
    # is not -- `can_assert_absence()` needs both, and silently accepting the
    # tick would leave the officer believing they had unlocked absence claims.
    if examined and not operator_id.strip():
        return again("Operator ID is required when you confirm you examined "
                     "the physical package.")

    image_path = None
    if image is not None and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_IMAGE:
            return again(f"Unsupported image type '{ext}'. Accepted: "
                         + ", ".join(sorted(ALLOWED_IMAGE)))
        data = await image.read()
        if data:
            name = f"{uuid.uuid4().hex}{ext}"
            os.makedirs(db.UPLOAD_DIR, exist_ok=True)
            with open(os.path.join(db.UPLOAD_DIR, name), "wb") as fh:
                fh.write(data)
            image_path = name

    inspection_id = service.create_inspection(
        user=user, product_name=product_name, values=values, panels=panels,
        examined=examined, operator_id=operator_id, note=coverage_note,
        declared_category=declared_category, declared_pdp_area_cm2=area,
        image_path=image_path)
    return RedirectResponse(f"/scan/{inspection_id}", status_code=303)


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
