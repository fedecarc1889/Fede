"""Interfaz web (SDD sección 17, componente Frontend).

Pantallas:
    /            Carga manual: producto -> rubros -> cálculo detallado.
    /importar    Importación de Excel y visualización consolidada.
    /plantilla   Descarga de una plantilla Excel de ejemplo.
    /historial   Trazabilidad de cálculos guardados.

La carga manual y la importación usan exactamente el mismo motor
(``calculator.calculate_ctg``), cumpliendo CA-006 y CA-007.

Ejecución:  python -m grain_quality.webapp
"""

from __future__ import annotations

import io
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import (
    Flask, abort, redirect, render_template, request, send_file, url_for,
)

from .calculator import calculate_ctg, consolidate_contracts
from .exporter import export_results
from .importer import import_excel, parse_number
from .models import MeasurementInput
from .norms_registry import NormNotFoundError, default_registry
from .persistence import Repository

app = Flask(__name__)
registry = default_registry()
repository = Repository()

EXPORTS_DIR = Path(__file__).parent.parent / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
def manual():
    product = request.args.get("producto", "SOJA")
    if not registry.has_product(product):
        product = registry.product_codes()[0]
    rubros = registry.rubros(product)
    norm = registry.get_norm(product)
    return render_template(
        "manual.html",
        products=registry.products(),
        selected=product,
        rubros=rubros,
        norm=norm,
    )


@app.post("/calcular")
def calcular():
    product = request.form["producto"]
    analysis_date = None
    if request.form.get("fecha"):
        analysis_date = date.fromisoformat(request.form["fecha"])

    measurements: list[MeasurementInput] = []
    input_errors: list[str] = []
    for rubro in registry.rubros(product, analysis_date):
        code = rubro["code"]
        values = {}
        for source in ("planta", "camara"):
            raw = request.form.get(f"{code}__{source}", "")
            try:
                values[source] = parse_number(raw)
            except ValueError:
                input_errors.append(
                    f"Valor no numérico '{raw}' en {rubro['name']} ({source})."
                )
                values[source] = None
        if values["planta"] is not None or values["camara"] is not None:
            measurements.append(
                MeasurementInput(
                    rubro=code,
                    plant_value=values["planta"],
                    chamber_value=values["camara"],
                )
            )

    weight_tn = None
    try:
        weight_tn = parse_number(request.form.get("toneladas", ""))
    except ValueError:
        input_errors.append("Toneladas: valor no numérico.")

    try:
        result = calculate_ctg(
            product_code=product,
            measurements=measurements,
            contract=request.form.get("contrato", ""),
            ctg=request.form.get("ctg", ""),
            weight_tn=weight_tn,
            analysis_date=analysis_date,
            registry=registry,
        )
    except NormNotFoundError as exc:
        return render_template(
            "resultado_ctg.html", result=None, error=str(exc),
            input_errors=input_errors, observaciones="", calculation_id=None,
        )

    calculation_id = repository.save_calculation(result)
    return render_template(
        "resultado_ctg.html",
        result=result,
        error=None,
        input_errors=input_errors,
        observaciones=request.form.get("observaciones", ""),
        calculation_id=calculation_id,
    )


@app.get("/importar")
def importar_form():
    return render_template("importar.html", result=None, export_name=None)


@app.post("/importar")
def importar():
    uploaded = request.files.get("archivo")
    if uploaded is None or uploaded.filename == "":
        return render_template(
            "importar.html", result=None, export_name=None,
            upload_error="Debe seleccionar un archivo .xlsx.",
        )
    data = io.BytesIO(uploaded.read())
    result = import_excel(data, registry=registry)

    for ctg_result in result.ctg_results:
        repository.save_calculation(ctg_result)

    export_name = None
    if result.contract_results or result.errors:
        export_name = (
            f"resultados_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.xlsx"
        )
        export_results(result.contract_results, result.errors,
                       EXPORTS_DIR / export_name)

    return render_template(
        "importar.html", result=result, export_name=export_name,
        upload_error=None,
    )


@app.get("/descargar/<name>")
def descargar(name: str):
    path = (EXPORTS_DIR / name).resolve()
    if path.parent != EXPORTS_DIR.resolve() or not path.exists():
        abort(404)
    return send_file(path, as_attachment=True)


@app.get("/plantilla")
def plantilla():
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Datos"
    sheet.append([
        "Contrato", "CTG", "Producto", "Toneladas",
        "Humedad Planta", "Humedad Camara",
        "Materias extranas Planta", "Materias extranas Camara",
        "Granos danados Planta", "Granos danados Camara",
    ])
    sheet.append(["10001", "CTG01", "SOJA", 30, 14.2, 13.8, 1.5, 1.1, 2.0, None])
    sheet.append(["10001", "CTG02", "SOJA", 28, 13.7, None, 0.8, None, None, None])
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer, as_attachment=True, download_name="plantilla_importacion.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/historial")
def historial():
    return render_template("historial.html",
                           calculations=repository.list_calculations())


@app.get("/historial/<int:calculation_id>")
def historial_detalle(calculation_id: int):
    calculation = repository.get_calculation(calculation_id)
    if calculation is None:
        abort(404)
    return render_template(
        "historial_detalle.html",
        calculation=calculation,
        details=repository.get_details(calculation_id),
    )


@app.get("/normas")
def normas():
    data = [
        {
            "product": registry.product_name(code),
            "code": code,
            "versions": registry.versions(code),
        }
        for code in registry.product_codes()
    ]
    return render_template("normas.html", data=data)


def main() -> None:
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
