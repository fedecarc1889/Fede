#!/usr/bin/env python3
"""
Extractor dinámico de campos de remitos en PDF.

Cada proveedor tiene su propia plantilla (en providers/*.json) que define
qué campos extraer y con qué reglas (regex sobre el texto OCR, o una región
fija de la página). La plantilla se puede seleccionar manualmente
(-p/--provider) o detectar automáticamente a partir de marcadores de texto
propios de cada proveedor.

También acepta una carpeta con varios PDFs (de proveedores iguales o
distintos) y puede exportar el resultado consolidado a Excel, con una
fila por remito y una columna por campo.

Uso:
    python3 remito_extractor.py remito.pdf
    python3 remito_extractor.py remito.pdf -p acme_sa
    python3 remito_extractor.py remito.pdf -f numero_remito,fecha,cliente
    python3 remito_extractor.py remito.pdf -o resultado.json
    python3 remito_extractor.py ./carpeta_remitos -o resultados.xlsx
    python3 remito_extractor.py --list-providers
    python3 remito_extractor.py --list-fields -p acme_sa
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import ocr_core

PROVIDERS_DIR = Path(__file__).parent / "providers"


def load_providers(providers_dir: Path = PROVIDERS_DIR) -> dict[str, dict]:
    """Carga todas las plantillas *.json de un directorio (los archivos que
    empiezan con '_' se ignoran, para poder tener borradores)."""
    providers = {}
    if not providers_dir.is_dir():
        return providers
    for f in sorted(providers_dir.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            providers[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"AVISO: no se pudo leer la plantilla '{f.name}': {e}", file=sys.stderr)
    return providers


def detect_provider(full_text: str, providers: dict[str, dict]) -> str | None:
    """Detecta el proveedor cuyos marcadores ('match') más coinciden con el
    texto OCR. Retorna None si ningún proveedor tiene al menos una coincidencia."""
    best_id, best_score = None, 0
    for pid, cfg in providers.items():
        score = sum(
            1 for marker in cfg.get("match", [])
            if re.search(marker, full_text, re.IGNORECASE)
        )
        if score > best_score:
            best_score, best_id = score, pid
    return best_id


def _extract_regex(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            value = m.group(1) if m.groups() else m.group(0)
            return value.strip()
    return None


def extract_fields(
    pdf_path: Path,
    pages_text: list[str],
    provider_cfg: dict,
    lang: str,
    fields_filter: set[str] | None = None,
) -> dict[str, str | None]:
    """Aplica las reglas de campos de una plantilla al texto OCR ya obtenido
    (y, si hace falta, corre OCR adicional sobre regiones bbox del PDF)."""
    full_text = "\n".join(pages_text)
    field_defs = provider_cfg.get("fields", {})
    if fields_filter is not None:
        field_defs = {k: v for k, v in field_defs.items() if k in fields_filter}

    result: dict[str, str | None] = {}
    for field_name, field_cfg in field_defs.items():
        value = None

        if "regex" in field_cfg:
            patterns = field_cfg["regex"]
            if isinstance(patterns, str):
                patterns = [patterns]
            page_idx = field_cfg.get("page")
            text = full_text
            if page_idx is not None and 0 <= page_idx < len(pages_text):
                text = pages_text[page_idx]
            value = _extract_regex(text, patterns)

        if not value and "bbox" in field_cfg:
            page_idx = field_cfg.get("page", 0)
            bbox = tuple(field_cfg["bbox"])
            value = ocr_core.ocr_pdf_region(pdf_path, page_idx, bbox, lang).strip() or None

        result[field_name] = value

    return result


def _slugify_label(label: str) -> str:
    """Convierte una etiqueta ('Número:', 'Pat. Chasis:') en un nombre de
    campo válido ('numero', 'pat_chasis')."""
    label = label.rstrip(":").strip()
    ascii_label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_label).strip("_").lower()
    return slug or "campo"


def _is_label_qualifier(token: str) -> bool:
    """True si `token` es candidato a ser la primera palabra de una etiqueta
    de dos palabras (ej. 'Pat.' en 'Pat. Chasis:', 'Kilos' en 'Kilos
    Brutos:'): corta, sin dígitos, y no un valor en mayúsculas (nombres
    propios, siglas) que casualmente precede a una etiqueta."""
    core = token.rstrip(".")
    if not core or not core.isalpha():
        return False
    if len(core) >= 3 and core.isupper():
        return False
    return len(core) <= 6


def suggest_fields(pages_text: list[str]) -> dict[str, dict]:
    """Propone un borrador de campos analizando pares 'Etiqueta: valor' en el
    texto (ya en orden de lectura). Es un punto de partida para revisar y
    ajustar, no un resultado definitivo: etiquetas repetidas (ej. 'CUIT:' de
    remitente y de transportista) quedan numeradas (cuit, cuit_2, ...) y hay
    que renombrarlas, y en tablas de dos columnas sin una etiqueta clara que
    corte el valor, puede arrastrar texto de la columna vecina."""
    fields: dict[str, dict] = {}
    name_counts: dict[str, int] = {}

    for page_text in pages_text:
        for line in page_text.splitlines():
            tokens = line.split(" ")
            anchors = [
                i for i, t in enumerate(tokens)
                if t.endswith(":") and len(t) > 1 and re.search(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]", t)
            ]
            if not anchors:
                continue

            spans = []
            for i in anchors:
                start = i
                if i > 0 and _is_label_qualifier(tokens[i - 1]) and (not spans or spans[-1][1] <= i - 1):
                    start = i - 1
                spans.append((start, i + 1))

            for pos, (start, end) in enumerate(spans):
                label_text = " ".join(tokens[start:end])
                next_start = spans[pos + 1][0] if pos + 1 < len(spans) else len(tokens)
                value = " ".join(tokens[end:next_start]).strip()
                if not value:
                    continue

                base_name = _slugify_label(label_text)
                name_counts[base_name] = name_counts.get(base_name, 0) + 1
                name = base_name if name_counts[base_name] == 1 else f"{base_name}_{name_counts[base_name]}"

                # \b evita que, p. ej., 'Calidad:' matchee como substring
                # dentro de 'Localidad:'.
                head = r"\b" + re.escape(label_text)
                if pos + 1 < len(spans):
                    tail = re.escape(" ".join(tokens[spans[pos + 1][0]:spans[pos + 1][1]]))
                    pattern = f"{head}\\s*(.+?)\\s*{tail}"
                else:
                    pattern = f"{head}\\s*(.+)"

                fields[name] = {"regex": [pattern]}

    return fields


def process_pdf(
    pdf_path: Path,
    providers: dict[str, dict],
    provider_override: str | None,
    lang: str,
    fields_filter: set[str] | None,
) -> dict:
    """Corre OCR + extracción de campos sobre un PDF. Nunca levanta
    excepciones: los errores quedan en el resultado bajo la clave 'error',
    para que el modo carpeta pueda seguir con los demás archivos."""
    try:
        pages_text = ocr_core.get_pdf_pages_text(pdf_path, lang)
    except RuntimeError as e:
        return {"archivo": pdf_path.name, "error": str(e)}

    full_text = "\n".join(pages_text)

    provider_id = provider_override
    if provider_id:
        if provider_id not in providers:
            return {"archivo": pdf_path.name, "error": f"Proveedor '{provider_id}' no encontrado."}
    else:
        detected = detect_provider(full_text, providers)
        if detected:
            provider_id = detected
            print(f"{pdf_path.name}: proveedor detectado automáticamente -> {provider_id}", file=sys.stderr)
        elif "generic" in providers:
            provider_id = "generic"
            print(f"{pdf_path.name}: no se detectó proveedor, usando plantilla genérica.", file=sys.stderr)
        else:
            return {
                "archivo": pdf_path.name,
                "error": "No se detectó proveedor y no hay plantilla 'generic'. Usa -p/--provider.",
            }

    campos = extract_fields(pdf_path, pages_text, providers[provider_id], lang, fields_filter)
    return {"archivo": pdf_path.name, "proveedor": provider_id, "campos": campos}


def write_excel(results: list[dict], path: Path) -> None:
    """Escribe los resultados como una fila por remito, con una columna por
    campo (unión de todos los campos vistos, en el orden en que aparecen)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    columns = ["archivo", "proveedor"]
    seen = set(columns)
    for r in results:
        for key in r.get("campos", {}):
            if key not in seen:
                seen.add(key)
                columns.append(key)
    if any("error" in r for r in results):
        columns.append("error")

    wb = Workbook()
    ws = wb.active
    ws.title = "Remitos"
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for r in results:
        campos = r.get("campos", {})
        row = []
        for col in columns:
            if col == "archivo":
                row.append(r.get("archivo"))
            elif col == "proveedor":
                row.append(r.get("proveedor"))
            elif col == "error":
                row.append(r.get("error"))
            else:
                row.append(campos.get(col))
        ws.append(row)

    for i, col in enumerate(columns, start=1):
        cell_values = [str(ws.cell(row=r, column=i).value or "") for r in range(2, ws.max_row + 1)]
        width = max([len(col)] + [len(v) for v in cell_values]) + 2
        ws.column_dimensions[get_column_letter(i)].width = min(width, 50)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extractor dinámico de campos de remitos en PDF, con "
        "selección de plantilla por proveedor.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 remito_extractor.py remito.pdf
  python3 remito_extractor.py remito.pdf -p acme_sa
  python3 remito_extractor.py remito.pdf -f numero_remito,fecha,cliente
  python3 remito_extractor.py remito.pdf -o resultado.json
  python3 remito_extractor.py ./carpeta_remitos -o resultados.xlsx
  python3 remito_extractor.py --list-providers
  python3 remito_extractor.py --list-fields -p acme_sa
  python3 remito_extractor.py remito.pdf --suggest-template -o providers/proveedor_nuevo.json

Ver providers/README.md para el esquema de las plantillas y cómo agregar
un nuevo proveedor.
        """,
    )
    parser.add_argument("input", nargs="?", help="PDF del remito a procesar, o una carpeta con varios PDFs")
    parser.add_argument(
        "-p", "--provider",
        help="ID de la plantilla de proveedor a usar (ver --list-providers). "
        "Si se omite, se intenta detectar automáticamente a partir del texto OCR.",
    )
    parser.add_argument(
        "-f", "--fields",
        help="Campos a extraer, separados por coma (por defecto, todos los "
        "definidos en la plantilla). Ver --list-fields.",
    )
    parser.add_argument("-l", "--lang", default="spa", help="Idioma OCR (default: spa)")
    parser.add_argument(
        "-o", "--output",
        help="Archivo de salida. Formato según la extensión: .xlsx/.xls para "
        "Excel (una fila por remito, una columna por campo), cualquier otra "
        "para JSON.",
    )
    parser.add_argument(
        "--providers-dir",
        help=f"Directorio con plantillas de proveedores (default: {PROVIDERS_DIR})",
    )
    parser.add_argument(
        "--list-providers", action="store_true",
        help="Lista las plantillas de proveedores disponibles y termina",
    )
    parser.add_argument(
        "--list-fields", action="store_true",
        help="Lista los campos definidos por una plantilla (usar con -p) y termina",
    )
    parser.add_argument(
        "--suggest-template", action="store_true",
        help="En vez de extraer con una plantilla existente, analiza el PDF y "
        "propone un borrador de plantilla (detecta pares 'Etiqueta: valor'). "
        "Es un punto de partida para revisar y ajustar, no un resultado "
        "definitivo. Se imprime por stdout, o se guarda con -o.",
    )
    args = parser.parse_args()

    providers_dir = Path(args.providers_dir) if args.providers_dir else PROVIDERS_DIR
    providers = load_providers(providers_dir)

    if args.list_providers:
        if not providers:
            print(f"No hay plantillas en '{providers_dir}'.")
            return
        for pid, cfg in providers.items():
            print(f"{pid}: {cfg.get('label', pid)}")
        return

    if args.list_fields:
        if not args.provider:
            parser.error("--list-fields requiere -p/--provider")
        cfg = providers.get(args.provider)
        if not cfg:
            print(f"ERROR: proveedor '{args.provider}' no encontrado. Usa --list-providers.", file=sys.stderr)
            sys.exit(1)
        for name in cfg.get("fields", {}):
            print(name)
        return

    if args.suggest_template:
        if not args.input:
            parser.error("--suggest-template requiere un PDF de ejemplo")
        pdf_path = Path(args.input)
        if not pdf_path.exists() or pdf_path.is_dir():
            print(f"ERROR: '{pdf_path}' no es un archivo PDF válido.", file=sys.stderr)
            sys.exit(1)
        try:
            pages_text = ocr_core.get_pdf_pages_text(pdf_path, args.lang)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        fields = suggest_fields(pages_text)
        draft = {"label": pdf_path.stem, "match": [], "fields": fields}
        text_out = json.dumps(draft, ensure_ascii=False, indent=2)

        print(
            f"Borrador generado con {len(fields)} campo(s) a partir de '{pdf_path.name}'. "
            "Es un punto de partida: completá 'match' con algo que identifique a este "
            "proveedor, revisá los nombres duplicados (sufijo _2, _3...) y los campos "
            "de filas con dos columnas, que pueden traer texto de más.",
            file=sys.stderr,
        )
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text_out, encoding="utf-8")
            print(f"Borrador guardado en: {output_path}")
        else:
            print(text_out)
        return

    if not args.input:
        parser.error("falta el archivo PDF de entrada (o una carpeta con varios PDFs)")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: '{input_path}' no existe.", file=sys.stderr)
        sys.exit(1)

    if args.provider and args.provider not in providers:
        print(f"ERROR: proveedor '{args.provider}' no encontrado. Usa --list-providers.", file=sys.stderr)
        sys.exit(1)

    fields_filter = set(f.strip() for f in args.fields.split(",")) if args.fields else None

    is_batch = input_path.is_dir()
    if is_batch:
        pdf_files = sorted(f for f in input_path.iterdir() if f.suffix.lower() == ".pdf")
        if not pdf_files:
            print(f"No se encontraron PDFs en '{input_path}'.", file=sys.stderr)
            return
        results = [process_pdf(p, providers, args.provider, args.lang, fields_filter) for p in pdf_files]
    else:
        result = process_pdf(input_path, providers, args.provider, args.lang, fields_filter)
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        results = [result]

    output_path = Path(args.output) if args.output else None

    if output_path and output_path.suffix.lower() in (".xlsx", ".xls"):
        write_excel(results, output_path)
        print(f"Excel guardado en: {output_path}")
        return

    payload = results if is_batch else results[0]
    text_out = json.dumps(payload, ensure_ascii=False, indent=2)

    if output_path:
        output_path.write_text(text_out, encoding="utf-8")
        print(f"Resultado guardado en: {output_path}")
    else:
        print(text_out)


if __name__ == "__main__":
    main()
