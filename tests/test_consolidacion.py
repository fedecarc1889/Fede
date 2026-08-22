"""Consolidación por contrato ponderada por toneladas (SDD sección 14)."""

import pytest

from grain_quality.calculator import calculate_ctg, consolidate_contracts
from grain_quality.models import MeasurementInput


def _ctg(ctg, me_value, weight):
    return calculate_ctg(
        "SOJA", [MeasurementInput("materias_extranas", plant_value=me_value)],
        contract="10001", ctg=ctg, weight_tn=weight,
    )


def test_ponderacion_por_toneladas_no_promedio_simple():
    # CTG01: ME 3.0 -> rebaja 2.0% con 90 tn; CTG02: ME 1.0 -> 0% con 10 tn
    contratos = consolidate_contracts([_ctg("CTG01", 3.0, 90), _ctg("CTG02", 1.0, 10)])
    contrato = contratos[0]
    assert contrato.weighted
    # ponderado: (2.0*90 + 0*10) / 100 = 1.8 ; promedio simple daría 1.0
    assert contrato.total_rebaja == pytest.approx(1.8)
    assert contrato.neto == pytest.approx(-1.8)
    assert contrato.total_weight == pytest.approx(100)


def test_sin_toneladas_promedio_simple_con_advertencia():
    contratos = consolidate_contracts([
        _ctg("CTG01", 3.0, None), _ctg("CTG02", 1.0, 20),
    ])
    contrato = contratos[0]
    assert not contrato.weighted
    assert contrato.total_rebaja == pytest.approx(1.0)  # promedio simple
    assert contrato.warnings


def test_contratos_separados():
    a = calculate_ctg("SOJA", [], contract="A", ctg="1", weight_tn=10)
    b = calculate_ctg("SOJA", [], contract="B", ctg="2", weight_tn=10)
    contratos = consolidate_contracts([a, b])
    assert sorted(c.contract for c in contratos) == ["A", "B"]
