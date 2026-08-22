"""Tests del Quality Resolver (RN-001..RN-004, SDD sección 6)."""

from grain_quality.models import MeasurementInput, Source
from grain_quality.resolver import resolve


def test_rn001_prioridad_camara():
    r = resolve(MeasurementInput("humedad", plant_value=14.2, chamber_value=13.8))
    assert r.value == 13.8
    assert r.source == Source.CAMARA


def test_rn002_solo_planta():
    r = resolve(MeasurementInput("materias_extranas", plant_value=1.5))
    assert r.value == 1.5
    assert r.source == Source.PLANTA


def test_rn003_solo_camara():
    r = resolve(MeasurementInput("granos_quebrados", chamber_value=3.2))
    assert r.value == 3.2
    assert r.source == Source.CAMARA


def test_rn004_sin_analisis_es_null_no_cero():
    r = resolve(MeasurementInput("granos_danados"))
    assert r.value is None
    assert r.source is None


def test_cero_es_valor_valido():
    """El 0 es un análisis válido, no ausencia de dato (SDD sección 19)."""
    r = resolve(MeasurementInput("materias_extranas", plant_value=1.5, chamber_value=0.0))
    assert r.value == 0.0
    assert r.source == Source.CAMARA

    r = resolve(MeasurementInput("materias_extranas", plant_value=0.0))
    assert r.value == 0.0
    assert r.source == Source.PLANTA


def test_prioridad_es_por_rubro():
    """Ejemplo completo de la sección 6 del SDD."""
    casos = [
        (MeasurementInput("humedad", 14.2, 13.8), 13.8, Source.CAMARA),
        (MeasurementInput("materias_extranas", 1.5, None), 1.5, Source.PLANTA),
        (MeasurementInput("danados", 2.1, 1.8), 1.8, Source.CAMARA),
        (MeasurementInput("quebrados", None, 3.2), 3.2, Source.CAMARA),
    ]
    for entrada, valor, origen in casos:
        r = resolve(entrada)
        assert r.value == valor
        assert r.source == origen
