"""Genera un archivo Excel de ejemplo para probar la importación.

Uso: python scripts/generar_ejemplo.py [salida.xlsx]
"""

import sys
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).parent.parent))


def build(path: str = "ejemplo_importacion.xlsx") -> str:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Datos"
    sheet.append([
        "Contrato", "CTG", "Producto", "Toneladas",
        "Humedad Planta", "Humedad Camara",
        "Materias extranas Planta", "Materias extranas Camara",
        "Granos danados Planta", "Granos danados Camara",
        "Materia grasa Planta", "Materia grasa Camara",
    ])
    rows = [
        # Contrato 10001 – Soja, 3 CTG (ejemplo del SDD sección 9)
        ["10001", "CTG01", "SOJA", 30, 14.2, 13.8, 1.5, 1.1, 2.0, None, None, None],
        ["10001", "CTG02", "SOJA", 28, 13.7, None, 0.8, None, None, None, None, None],
        ["10001", "CTG03", "SOJA", 32, 14.5, 14.0, 1.2, None, None, None, None, None],
        # Contrato 10002 – Maíz
        ["10002", "CTG04", "MAIZ", 25, 15.2, 14.9, 1.4, None, 3.5, 3.1, None, None],
        # Contrato 10003 – Girasol con materia grasa (bonificación)
        ["10003", "CTG05", "GIRASOL", 20, 10.5, None, None, None, None, None, 44.0, 45.0],
        # Filas con errores para demostrar el rechazo por fila
        ["10004", "", "SOJA", 10, 13.0, None, None, None, None, None, None, None],
        ["10004", "CTG06", "CEBADA", 10, 13.0, None, None, None, None, None, None, None],
        ["10001", "CTG01", "SOJA", 30, 14.2, None, None, None, None, None, None, None],
        ["10005", "CTG07", "SOJA", 15, "abc", None, None, None, None, None, None, None],
    ]
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    return path


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "ejemplo_importacion.xlsx"
    print(f"Ejemplo generado: {build(target)}")
