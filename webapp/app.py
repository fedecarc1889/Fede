#!/usr/bin/env python3
"""
Miniapp Flask para configurar visualmente las plantillas de proveedores de
remito_extractor.py.

Subís un PDF de ejemplo, ves su texto OCR y la imagen de cada página,
agregás campos probando regex en vivo o dibujando una región (bbox) sobre
la imagen, y guardás el resultado como providers/<id>.json (el mismo
formato que ya usa remito_extractor.py).

Uso:
    python3 webapp/app.py
    (por defecto en http://127.0.0.1:5000)
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ocr_core  # noqa: E402
import remito_extractor  # noqa: E402

PROVIDERS_DIR = ROOT / "providers"
UPLOAD_ROOT = Path(tempfile.gettempdir()) / "remito_extractor_sessions"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    return jsonify({"description": e.description}), e.code


# session_id -> {"pdf_path": Path, "pages_text": list[str], "lang": str, "num_pages": int}
SESSIONS: dict[str, dict] = {}


def _session_or_404(session_id: str) -> dict:
    session = SESSIONS.get(session_id or "")
    if not session:
        abort(404, "Sesión no encontrada o expirada. Volvé a subir el PDF de ejemplo.")
    return session


def _valid_provider_id(provider_id: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z0-9_\-]+", provider_id or ""))


@app.get("/favicon.ico")
def favicon():
    return "", 204


@app.get("/")
def index():
    providers = remito_extractor.load_providers(PROVIDERS_DIR)
    return render_template("index.html", providers=providers)


@app.post("/upload")
def upload():
    file = request.files.get("pdf")
    lang = (request.form.get("lang") or "spa").strip()
    if not file or not file.filename.lower().endswith(".pdf"):
        abort(400, "Subí un archivo PDF válido.")

    session_id = uuid.uuid4().hex
    session_dir = UPLOAD_ROOT / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = session_dir / "documento.pdf"
    file.save(pdf_path)

    try:
        pages_text = ocr_core.get_pdf_pages_text(pdf_path, lang)
    except RuntimeError as e:
        abort(500, str(e))

    SESSIONS[session_id] = {
        "pdf_path": pdf_path,
        "pages_text": pages_text,
        "lang": lang,
        "num_pages": len(pages_text),
        "original_name": file.filename,
    }

    providers = remito_extractor.load_providers(PROVIDERS_DIR)
    detected = remito_extractor.detect_provider("\n".join(pages_text), providers)

    return jsonify({
        "session_id": session_id,
        "num_pages": len(pages_text),
        "pages_text": pages_text,
        "detected_provider": detected,
    })


@app.get("/page-image/<session_id>/<int:page_idx>")
def page_image(session_id: str, page_idx: int):
    session = _session_or_404(session_id)
    if not (0 <= page_idx < session["num_pages"]):
        abort(404)

    img_path = session["pdf_path"].parent / f"page-{page_idx}.png"
    if not img_path.exists():
        import fitz

        doc = fitz.open(session["pdf_path"])
        try:
            img = ocr_core.render_pdf_page(doc, page_idx, zoom=2.0)
            img.save(img_path)
        finally:
            doc.close()
    return send_file(img_path, mimetype="image/png")


@app.get("/providers")
def list_providers():
    providers = remito_extractor.load_providers(PROVIDERS_DIR)
    return jsonify({
        pid: {"label": cfg.get("label", pid)}
        for pid, cfg in providers.items()
    })


@app.get("/providers/<provider_id>")
def get_provider(provider_id: str):
    providers = remito_extractor.load_providers(PROVIDERS_DIR)
    cfg = providers.get(provider_id)
    if not cfg:
        abort(404, f"Proveedor '{provider_id}' no encontrado.")
    return jsonify({"id": provider_id, **cfg})


@app.post("/providers/<provider_id>")
def save_provider(provider_id: str):
    if not _valid_provider_id(provider_id):
        abort(400, "El ID del proveedor solo puede tener letras, números, '_' y '-'.")

    body = request.get_json(force=True, silent=False) or {}
    cfg = {
        "label": body.get("label") or provider_id,
        "match": [m for m in body.get("match", []) if m],
        "fields": body.get("fields", {}),
    }

    PROVIDERS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROVIDERS_DIR / f"{provider_id}.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return jsonify({"ok": True, "id": provider_id})


@app.post("/test-field")
def test_field():
    """Prueba un único campo (regex y/o bbox) contra la sesión actual, sin guardar nada."""
    body = request.get_json(force=True, silent=False) or {}
    session = _session_or_404(body.get("session_id"))

    field_cfg: dict = {}
    patterns = [p for p in body.get("regex", []) if p]
    if patterns:
        field_cfg["regex"] = patterns
    if body.get("page") not in (None, ""):
        field_cfg["page"] = int(body["page"])
    if body.get("bbox"):
        field_cfg["bbox"] = body["bbox"]

    if not field_cfg:
        return jsonify({"value": None, "error": "Definí al menos una regex o una región."})

    try:
        result = remito_extractor.extract_fields(
            session["pdf_path"],
            session["pages_text"],
            {"fields": {"_test": field_cfg}},
            session["lang"],
        )
    except re.error as e:
        return jsonify({"value": None, "error": f"Regex inválida: {e}"})

    return jsonify({"value": result.get("_test")})


@app.post("/extract-all")
def extract_all():
    """Corre todos los campos de una plantilla (guardada o borrador) contra la sesión actual."""
    body = request.get_json(force=True, silent=False) or {}
    session = _session_or_404(body.get("session_id"))

    provider_id = body.get("provider_id")
    fields = body.get("fields")

    if fields is not None:
        cfg = {"fields": fields}
    elif provider_id:
        providers = remito_extractor.load_providers(PROVIDERS_DIR)
        cfg = providers.get(provider_id)
        if not cfg:
            abort(404, f"Proveedor '{provider_id}' no encontrado.")
    else:
        abort(400, "Falta 'provider_id' o 'fields'.")

    result = remito_extractor.extract_fields(
        session["pdf_path"], session["pages_text"], cfg, session["lang"]
    )
    return jsonify({"campos": result})


@app.post("/extract-all/excel")
def extract_all_excel():
    """Igual que /extract-all, pero devuelve el resultado como un Excel de
    una fila descargable, para tener 'la salida en Excel' sin pasar por la
    línea de comandos."""
    body = request.get_json(force=True, silent=False) or {}
    session = _session_or_404(body.get("session_id"))

    provider_id = body.get("provider_id")
    fields = body.get("fields")

    if fields is not None:
        cfg = {"fields": fields}
    elif provider_id:
        providers = remito_extractor.load_providers(PROVIDERS_DIR)
        cfg = providers.get(provider_id)
        if not cfg:
            abort(404, f"Proveedor '{provider_id}' no encontrado.")
    else:
        abort(400, "Falta 'provider_id' o 'fields'.")

    campos = remito_extractor.extract_fields(
        session["pdf_path"], session["pages_text"], cfg, session["lang"]
    )
    row = {
        "archivo": session.get("original_name") or session["pdf_path"].name,
        "proveedor": provider_id or "(borrador)",
        "campos": campos,
    }

    excel_path = session["pdf_path"].parent / "extraccion.xlsx"
    remito_extractor.write_excel([row], excel_path)

    return send_file(
        excel_path,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="remito.xlsx",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
