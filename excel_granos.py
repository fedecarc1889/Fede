#!/usr/bin/env python3
"""
excel_granos.py - Importación/exportación de planillas Excel con datos de
calidad de granos para calcularlos en lote con normas_bcr.py.

Columnas reconocidas en el Excel de entrada (no hace falta que estén todas;
las que falten se toman como 0 o se omiten si no aplican al grano):

    Lote, Grano, Peso_kg, Humedad, Materias_Extranas, Granos_Danados,
    Granos_Verdes, Granos_Quebrados, Peso_Hectolitrico, Precio_Base

Los nombres de columna admiten variantes razonables (mayúsculas, espacios,
tildes, guiones) gracias a la normalización en _normalizar_columna().
"""

import unicodedata

import pandas as pd

from normas_bcr import GRANOS, calcular_lote, granos_disponibles

# Alias de encabezados -> clave interna
ALIAS_COLUMNAS = {
    "lote": "lote",
    "id": "lote",
    "identificacion": "lote",
    "grano": "grano",
    "cereal": "grano",
    "cultivo": "grano",
    "peso": "peso_kg",
    "peso_kg": "peso_kg",
    "peso_bruto": "peso_kg",
    "peso_bruto_kg": "peso_kg",
    "humedad": "humedad",
    "materias_extranas": "materias_extranas",
    "impurezas": "materias_extranas",
    "cuerpos_extranos": "materias_extranas",
    "granos_danados": "granos_danados",
    "danados": "granos_danados",
    "granos_verdes": "granos_verdes",
    "verdes": "granos_verdes",
    "granos_quebrados": "granos_quebrados",
    "quebrados": "granos_quebrados",
    "partidos": "granos_quebrados",
    "peso_hectolitrico": "peso_hectolitrico",
    "ph": "peso_hectolitrico",
    "peso_especifico": "peso_hectolitrico",
    "precio_base": "precio_base",
    "precio": "precio_base",
}

FACTOR_KEYS = {"materias_extranas", "granos_danados", "granos_verdes", "granos_quebrados"}


def _normalizar_columna(nombre: str) -> str:
    nombre = str(nombre).strip().lower()
    nombre = "".join(
        c for c in unicodedata.normalize("NFKD", nombre) if not unicodedata.combining(c)
    )
    nombre = nombre.replace(" ", "_").replace("-", "_")
    while "__" in nombre:
        nombre = nombre.replace("__", "_")
    return nombre


def _mapear_columnas(df: pd.DataFrame) -> pd.DataFrame:
    mapeo = {}
    for col in df.columns:
        clave = _normalizar_columna(col)
        clave = ALIAS_COLUMNAS.get(clave, clave)
        mapeo[col] = clave
    return df.rename(columns=mapeo)


def procesar_excel(ruta_entrada: str, hoja: str | int = 0) -> pd.DataFrame:
    """Lee un Excel de lotes, calcula rebajas/peso neto para cada fila y
    devuelve un DataFrame con los datos originales más las columnas
    calculadas."""
    df = pd.read_excel(ruta_entrada, sheet_name=hoja)
    df = _mapear_columnas(df)

    requeridas = {"grano", "peso_kg", "humedad"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(
            f"Faltan columnas obligatorias en el Excel: {', '.join(sorted(faltantes))}. "
            f"Columnas encontradas: {', '.join(df.columns)}"
        )

    filas_resultado = []
    for idx, fila in df.iterrows():
        grano_key = str(fila["grano"]).strip().lower()
        if grano_key not in GRANOS:
            raise ValueError(
                f"Fila {idx + 2}: grano '{fila['grano']}' no reconocido. "
                f"Disponibles: {', '.join(granos_disponibles())}"
            )

        factores = {}
        for clave in FACTOR_KEYS:
            if clave in df.columns and pd.notna(fila.get(clave)):
                factores[clave] = float(fila[clave])

        ph = float(fila["peso_hectolitrico"]) if "peso_hectolitrico" in df.columns and pd.notna(fila.get("peso_hectolitrico")) else None
        precio_base = float(fila["precio_base"]) if "precio_base" in df.columns and pd.notna(fila.get("precio_base")) else None

        resultado = calcular_lote(
            grano_key=grano_key,
            peso_kg=float(fila["peso_kg"]),
            humedad=float(fila["humedad"]),
            factores=factores,
            ph=ph,
            precio_base=precio_base,
        )

        fila_resultado = {
            "Lote": fila["lote"] if "lote" in df.columns else idx + 1,
            "Grano": resultado["grano"],
            "Peso_Bruto_kg": resultado["peso_bruto_kg"],
            "Humedad_%": humedad_de(resultado),
            "Descuento_Total_%": resultado["descuento_total_pct"],
            "Peso_Neto_kg": resultado["peso_neto_kg"],
            "Grado_Orientativo": resultado["grado_orientativo"],
        }
        for clave, item in resultado["desglose"].items():
            fila_resultado[f"Rebaja_{item['label']}_%"] = item["descuento_pct"]

        if "valor_neto" in resultado:
            fila_resultado["Precio_Base"] = resultado["precio_base"]
            fila_resultado["Valor_Neto"] = resultado["valor_neto"]

        filas_resultado.append(fila_resultado)

    return pd.DataFrame(filas_resultado)


def humedad_de(resultado: dict) -> float:
    return resultado["desglose"]["humedad"]["valor_real"]


def exportar_resultado(df_resultado: pd.DataFrame, ruta_salida: str) -> None:
    df_resultado.to_excel(ruta_salida, index=False)


def generar_plantilla(ruta_salida: str) -> None:
    """Crea un Excel de ejemplo con el formato esperado para importar."""
    filas = [
        {
            "Lote": "L001",
            "Grano": "trigo",
            "Peso_kg": 30000,
            "Humedad": 14.8,
            "Materias_Extranas": 2.2,
            "Granos_Danados": 3.1,
            "Granos_Quebrados": 1.5,
            "Peso_Hectolitrico": 76.5,
            "Precio_Base": 220000,
        },
        {
            "Lote": "L002",
            "Grano": "maiz",
            "Peso_kg": 28000,
            "Humedad": 16.0,
            "Materias_Extranas": 1.0,
            "Granos_Danados": 2.0,
            "Granos_Quebrados": 4.5,
            "Peso_Hectolitrico": 73.0,
            "Precio_Base": 190000,
        },
        {
            "Lote": "L003",
            "Grano": "soja",
            "Peso_kg": 32000,
            "Humedad": 14.2,
            "Materias_Extranas": 1.3,
            "Granos_Danados": 6.0,
            "Granos_Verdes": 3.0,
            "Granos_Quebrados": 12.0,
            "Peso_Hectolitrico": "",
            "Precio_Base": 350000,
        },
    ]
    pd.DataFrame(filas).to_excel(ruta_salida, index=False)
