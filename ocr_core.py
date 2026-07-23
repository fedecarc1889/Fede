#!/usr/bin/env python3
"""
Núcleo común de OCR: renderizado de páginas PDF a imagen y extracción de texto
vía Tesseract. Usado tanto por ocr_reader.py (OCR genérico) como por
remito_extractor.py (extracción de campos de remitos).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytesseract
from PIL import Image

BBox = tuple[float, float, float, float]


def ocr_image(img: Image.Image, lang: str) -> str:
    """Extrae texto de una imagen ya cargada en memoria."""
    return pytesseract.image_to_string(img, lang=lang)


def render_pdf_page(doc, page_index: int, zoom: float = 2.0) -> Image.Image:
    """Renderiza una página de un documento fitz (PyMuPDF) ya abierto a imagen PIL."""
    import fitz  # pymupdf

    page = doc[page_index]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def ocr_pdf_pages(
    path: Path,
    lang: str = "spa",
    zoom: float = 2.0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[str]:
    """OCR de un PDF completo. Retorna una lista con el texto de cada página."""
    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise RuntimeError("pymupdf no instalado. Ejecuta: pip install pymupdf") from exc

    doc = fitz.open(path)
    try:
        total = len(doc)
        texts = []
        for i in range(total):
            if progress_callback:
                progress_callback(i + 1, total)
            img = render_pdf_page(doc, i, zoom)
            texts.append(ocr_image(img, lang))
        return texts
    finally:
        doc.close()


def _reconstruct_reading_order(words: list[tuple], y_tolerance: float = 3.0) -> str:
    """Reordena palabras de page.get_text('words') en filas por proximidad
    vertical, ordenadas de izquierda a derecha dentro de cada fila.

    Necesario porque en comprobantes con layout de tabla/formulario el orden
    crudo del contenido del PDF suele agrupar primero todas las etiquetas de
    una sección y recién después todos los valores (ej. "Remitente: Domicilio:
    CUIT: ACME CalleFalsa123 30-11111111-1"), en vez de seguir el orden visual
    de lectura fila por fila.
    """
    if not words:
        return ""
    ordered = sorted(words, key=lambda w: (w[1], w[0]))
    lines: list[list[tuple]] = [[ordered[0]]]
    for w in ordered[1:]:
        if abs(w[1] - lines[-1][-1][1]) <= y_tolerance:
            lines[-1].append(w)
        else:
            lines.append([w])
    return "\n".join(
        " ".join(w[4] for w in sorted(line, key=lambda w: w[0]))
        for line in lines
    )


def get_pdf_pages_text(
    path: Path,
    lang: str = "spa",
    zoom: float = 2.0,
    y_tolerance: float = 3.0,
) -> list[str]:
    """Extrae el texto de cada página de un PDF de la forma más confiable
    posible: si la página tiene texto embebido (PDF "nativo", no escaneado),
    lo usa reconstruyendo el orden de lectura por filas (ver
    `_reconstruct_reading_order`) — más preciso y sin errores de
    reconocimiento que el OCR. Solo recurre a Tesseract sobre la página
    renderizada cuando no hay texto embebido (páginas escaneadas como
    imagen)."""
    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise RuntimeError("pymupdf no instalado. Ejecuta: pip install pymupdf") from exc

    doc = fitz.open(path)
    try:
        texts = []
        for i, page in enumerate(doc):
            words = page.get_text("words")
            if words:
                texts.append(_reconstruct_reading_order(words, y_tolerance))
            else:
                img = render_pdf_page(doc, i, zoom)
                texts.append(ocr_image(img, lang))
        return texts
    finally:
        doc.close()


def ocr_pdf(path: Path, lang: str = "spa", zoom: float = 2.0) -> str:
    """OCR de un PDF completo, con separadores de página, como un único string."""
    texts = ocr_pdf_pages(path, lang, zoom)
    return "\n\n".join(f"--- Página {i} ---\n{t}" for i, t in enumerate(texts, 1))


def ocr_pdf_region(
    path: Path,
    page_index: int,
    bbox: BBox,
    lang: str = "spa",
    zoom: float = 3.0,
) -> str:
    """
    OCR de una región específica de una página del PDF.

    bbox: (x0, y0, x1, y1) como fracciones (0.0 a 1.0) del ancho/alto de la página,
    con origen en la esquina superior izquierda. Útil para campos ubicados en una
    posición fija del formulario (sellos, numeración pre-impresa, recuadros fijos)
    donde una regex sobre el texto completo no es confiable.
    """
    import fitz  # pymupdf

    doc = fitz.open(path)
    try:
        if page_index >= len(doc):
            return ""
        img = render_pdf_page(doc, page_index, zoom)
        w, h = img.size
        x0, y0, x1, y1 = bbox
        crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        return ocr_image(crop, lang)
    finally:
        doc.close()
