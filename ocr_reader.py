#!/usr/bin/env python3
"""
OCR Reader - Extrae texto de imágenes y PDFs usando Tesseract.
Uso:
    python3 ocr_reader.py <archivo>               # procesa un archivo
    python3 ocr_reader.py <archivo> -l spa        # idioma español
    python3 ocr_reader.py <archivo> -o salida.txt # guarda resultado
    python3 ocr_reader.py <directorio>            # procesa todos los archivos
"""

import argparse
import sys
import os
from pathlib import Path

import pytesseract
from PIL import Image

# Extensiones soportadas
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
PDF_EXTS = {".pdf"}


def ocr_image(path: Path, lang: str) -> str:
    """Extrae texto de una imagen."""
    img = Image.open(path)
    return pytesseract.image_to_string(img, lang=lang)


def ocr_pdf(path: Path, lang: str) -> str:
    """Extrae texto de un PDF convirtiendo cada página a imagen."""
    try:
        import fitz  # pymupdf
    except ImportError:
        print("ERROR: pymupdf no instalado. Ejecuta: pip install pymupdf", file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(path)
    texts = []
    total = len(doc)

    for i, page in enumerate(doc, 1):
        print(f"  Procesando página {i}/{total}...", end="\r", flush=True)
        # Renderizar página a imagen (2x resolución para mejor OCR)
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang=lang)
        texts.append(f"--- Página {i} ---\n{text}")

    print()  # nueva línea tras el progreso
    doc.close()
    return "\n\n".join(texts)


def process_file(path: Path, lang: str) -> str:
    """Procesa un archivo (imagen o PDF) y retorna el texto extraído."""
    ext = path.suffix.lower()

    if ext in IMAGE_EXTS:
        return ocr_image(path, lang)
    elif ext in PDF_EXTS:
        return ocr_pdf(path, lang)
    else:
        supported = ", ".join(sorted(IMAGE_EXTS | PDF_EXTS))
        raise ValueError(f"Formato '{ext}' no soportado. Formatos válidos: {supported}")


def process_directory(directory: Path, lang: str, output_dir: Path | None) -> None:
    """Procesa todos los archivos soportados en un directorio."""
    supported = IMAGE_EXTS | PDF_EXTS
    files = [f for f in sorted(directory.iterdir()) if f.suffix.lower() in supported]

    if not files:
        print(f"No se encontraron archivos soportados en '{directory}'.")
        return

    print(f"Encontrados {len(files)} archivos para procesar.\n")

    for file in files:
        print(f"Procesando: {file.name}")
        try:
            text = process_file(file, lang)
            if output_dir:
                out_path = output_dir / (file.stem + ".txt")
                out_path.write_text(text, encoding="utf-8")
                print(f"  Guardado en: {out_path}")
            else:
                print(f"\n{'='*60}")
                print(f"Archivo: {file.name}")
                print("="*60)
                print(text)
        except Exception as e:
            print(f"  ERROR procesando {file.name}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="OCR Reader - Extrae texto de imágenes y PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 ocr_reader.py foto.jpg
  python3 ocr_reader.py documento.pdf -l spa
  python3 ocr_reader.py scan.png -o resultado.txt
  python3 ocr_reader.py ./carpeta_documentos -l eng+spa
  python3 ocr_reader.py ./carpeta_documentos --output-dir ./textos

Idiomas disponibles (requieren paquetes tesseract):
  eng  - Inglés (instalado por defecto)
  spa  - Español (tesseract-ocr-spa)
  fra  - Francés (tesseract-ocr-fra)
  deu  - Alemán (tesseract-ocr-deu)
  por  - Portugués (tesseract-ocr-por)
  Múltiples: -l eng+spa
        """,
    )
    parser.add_argument("input", help="Archivo (imagen/PDF) o directorio a procesar")
    parser.add_argument(
        "-l", "--lang",
        default="eng",
        help="Idioma(s) para OCR (default: eng). Ej: spa, eng+spa",
    )
    parser.add_argument(
        "-o", "--output",
        help="Archivo de salida para guardar el texto extraído",
    )
    parser.add_argument(
        "--output-dir",
        help="Directorio de salida al procesar un directorio completo",
    )
    parser.add_argument(
        "--list-langs",
        action="store_true",
        help="Lista los idiomas de Tesseract instalados",
    )

    # Permitir --list-langs sin argumento posicional
    if "--list-langs" in sys.argv:
        langs = pytesseract.get_languages()
        print("Idiomas instalados en Tesseract:")
        for lang in langs:
            print(f"  {lang}")
        return

    args = parser.parse_args()

    if args.list_langs:
        langs = pytesseract.get_languages()
        print("Idiomas instalados en Tesseract:")
        for lang in langs:
            print(f"  {lang}")
        return

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"ERROR: '{input_path}' no existe.", file=sys.stderr)
        sys.exit(1)

    # Procesar directorio
    if input_path.is_dir():
        output_dir = Path(args.output_dir) if args.output_dir else None
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
        process_directory(input_path, args.lang, output_dir)
        return

    # Procesar archivo individual
    print(f"Procesando: {input_path.name} (idioma: {args.lang})")
    try:
        text = process_file(input_path, args.lang)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR inesperado: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(text, encoding="utf-8")
        print(f"Texto guardado en: {out_path}")
    else:
        print("\n" + "="*60)
        print("TEXTO EXTRAÍDO:")
        print("="*60)
        print(text)


if __name__ == "__main__":
    main()
