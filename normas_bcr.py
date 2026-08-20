#!/usr/bin/env python3
"""
normas_bcr.py - Parámetros base y lógica de cálculo de calidad de granos
según las Normas de Comercialización de uso habitual en el mercado de
granos argentino (criterios aplicados por la Bolsa de Comercio de Rosario
y la Bolsa de Cereales de Buenos Aires).

IMPORTANTE:
Los valores base (humedad, peso hectolítrico, tolerancias) configurados
en GRANOS son los de uso más extendido en el mercado, pero las normas se
actualizan por resolución y pueden variar según campaña, grado y destino
comercial. Antes de usar estos cálculos para liquidar una operación real,
verificar los valores contra la norma vigente publicada por la BCR
(https://www.bcr.com.ar) y ajustar este archivo si corresponde.
"""

from dataclasses import dataclass, field


@dataclass
class Factor:
    """Un factor de descuento por tolerancia (materias extrañas, dañados, etc.)."""
    label: str
    tolerancia: float  # % admitido sin descuento


@dataclass
class Grano:
    key: str
    label: str
    humedad_base: float  # % de humedad de recibo, base comercial
    peso_hectolitrico_base: float | None  # kg/hl, None si no aplica al grano
    factor_ph_pct_por_kg: float  # % de rebaja por cada kg/hl bajo la base
    factores: dict[str, Factor] = field(default_factory=dict)


# Tabla de granos soportados. Claves de "factores" usadas como nombres de
# columna/atributo en el resto de la calculadora.
GRANOS: dict[str, Grano] = {
    "trigo": Grano(
        key="trigo",
        label="Trigo pan",
        humedad_base=13.5,
        peso_hectolitrico_base=79.0,
        factor_ph_pct_por_kg=1.0,
        factores={
            "materias_extranas": Factor("Materias extrañas", tolerancia=1.5),
            "granos_danados": Factor("Granos dañados", tolerancia=2.0),
            "granos_quebrados": Factor("Granos quebrados/partidos", tolerancia=2.0),
        },
    ),
    "maiz": Grano(
        key="maiz",
        label="Maíz",
        humedad_base=14.5,
        peso_hectolitrico_base=75.0,
        factor_ph_pct_por_kg=0.5,
        factores={
            "materias_extranas": Factor("Materias extrañas", tolerancia=1.5),
            "granos_danados": Factor("Granos dañados", tolerancia=3.0),
            "granos_quebrados": Factor("Granos quebrados/partidos", tolerancia=3.0),
        },
    ),
    "soja": Grano(
        key="soja",
        label="Soja",
        humedad_base=13.5,
        peso_hectolitrico_base=None,
        factor_ph_pct_por_kg=0.0,
        factores={
            "materias_extranas": Factor("Materias extrañas", tolerancia=1.0),
            "granos_danados": Factor("Granos dañados", tolerancia=5.0),
            "granos_verdes": Factor("Granos verdes", tolerancia=5.0),
            "granos_quebrados": Factor("Granos quebrados", tolerancia=20.0),
        },
    ),
    "sorgo": Grano(
        key="sorgo",
        label="Sorgo granífero",
        humedad_base=14.5,
        peso_hectolitrico_base=None,
        factor_ph_pct_por_kg=0.0,
        factores={
            "materias_extranas": Factor("Materias extrañas", tolerancia=1.5),
            "granos_danados": Factor("Granos dañados", tolerancia=3.0),
        },
    ),
    "girasol": Grano(
        key="girasol",
        label="Girasol",
        humedad_base=11.0,
        peso_hectolitrico_base=None,
        factor_ph_pct_por_kg=0.0,
        factores={
            "materias_extranas": Factor("Materias extrañas", tolerancia=1.0),
            "granos_danados": Factor("Granos dañados", tolerancia=4.0),
            "granos_quebrados": Factor("Semillas partidas", tolerancia=4.0),
        },
    ),
    "cebada": Grano(
        key="cebada",
        label="Cebada cervecera",
        humedad_base=13.5,
        peso_hectolitrico_base=62.0,
        factor_ph_pct_por_kg=1.0,
        factores={
            "materias_extranas": Factor("Materias extrañas", tolerancia=1.0),
            "granos_danados": Factor("Granos dañados", tolerancia=2.0),
        },
    ),
}


def granos_disponibles() -> list[str]:
    return list(GRANOS.keys())


def obtener_grano(clave: str) -> Grano:
    clave = clave.strip().lower()
    if clave not in GRANOS:
        disponibles = ", ".join(granos_disponibles())
        raise ValueError(f"Grano '{clave}' no reconocido. Disponibles: {disponibles}")
    return GRANOS[clave]


def calcular_merma_humedad(humedad_real: float, humedad_base: float) -> float:
    """Merma por secado, según la fórmula estándar de regla de tres:
    (Humedad_real - Humedad_base) / (100 - Humedad_base) * 100.
    Devuelve 0 si la humedad real ya está en la base o por debajo.
    """
    if humedad_real <= humedad_base:
        return 0.0
    return (humedad_real - humedad_base) / (100 - humedad_base) * 100


def calcular_descuento_factor(valor_real: float, tolerancia: float) -> float:
    """Descuento 1:1 por sobre la tolerancia admitida sin descuento."""
    return max(0.0, valor_real - tolerancia)


def calcular_ajuste_ph(ph_real: float, ph_base: float, factor_pct_por_kg: float) -> float:
    """Rebaja por peso hectolítrico bajo la base. No se aplica bonificación
    por PH superior a la base (comportamiento conservador por defecto)."""
    diferencia = ph_base - ph_real
    if diferencia <= 0:
        return 0.0
    return diferencia * factor_pct_por_kg


def calcular_lote(
    grano_key: str,
    peso_kg: float,
    humedad: float,
    factores: dict[str, float] | None = None,
    ph: float | None = None,
    precio_base: float | None = None,
) -> dict:
    """Calcula la merma/rebaja total de un lote y el peso (y precio) neto
    comercial resultante, según las Normas de Comercialización configuradas
    para el grano indicado.

    factores: dict con los valores reales de análisis para cada factor de
    calidad del grano (ej. {"materias_extranas": 2.1, "granos_danados": 3.0}).
    Los factores no informados se toman como 0.
    """
    grano = obtener_grano(grano_key)
    factores = factores or {}

    desglose = {}

    merma_humedad = calcular_merma_humedad(humedad, grano.humedad_base)
    desglose["humedad"] = {
        "label": "Merma por humedad",
        "valor_real": humedad,
        "base_o_tolerancia": grano.humedad_base,
        "descuento_pct": round(merma_humedad, 4),
    }

    for clave, factor in grano.factores.items():
        valor_real = factores.get(clave, 0.0)
        descuento = calcular_descuento_factor(valor_real, factor.tolerancia)
        desglose[clave] = {
            "label": factor.label,
            "valor_real": valor_real,
            "base_o_tolerancia": factor.tolerancia,
            "descuento_pct": round(descuento, 4),
        }

    ajuste_ph_pct = 0.0
    if grano.peso_hectolitrico_base is not None and ph is not None:
        ajuste_ph_pct = calcular_ajuste_ph(ph, grano.peso_hectolitrico_base, grano.factor_ph_pct_por_kg)
        desglose["peso_hectolitrico"] = {
            "label": "Rebaja por peso hectolítrico",
            "valor_real": ph,
            "base_o_tolerancia": grano.peso_hectolitrico_base,
            "descuento_pct": round(ajuste_ph_pct, 4),
        }

    descuento_total_pct = sum(item["descuento_pct"] for item in desglose.values())
    peso_neto_kg = peso_kg * (1 - descuento_total_pct / 100)

    # Clasificación orientativa: Grado 1 si todos los factores están dentro
    # de tolerancia y (si aplica) el PH no está por debajo de la base.
    dentro_de_grado_1 = all(
        item["descuento_pct"] == 0 for clave, item in desglose.items() if clave != "humedad"
    )
    grado_orientativo = "Grado 1" if dentro_de_grado_1 else "Fuera de Grado 1 (rebajas aplicadas)"

    resultado = {
        "grano": grano.label,
        "peso_bruto_kg": peso_kg,
        "desglose": desglose,
        "descuento_total_pct": round(descuento_total_pct, 4),
        "peso_neto_kg": round(peso_neto_kg, 2),
        "grado_orientativo": grado_orientativo,
    }

    if precio_base is not None:
        resultado["precio_base"] = precio_base
        resultado["valor_neto"] = round(precio_base * peso_neto_kg / 1000, 2)  # precio por tonelada

    return resultado
