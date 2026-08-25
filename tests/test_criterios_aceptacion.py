"""Criterios de aceptación CA-001 a CA-009 (SDD sección 21)."""

import json

import pytest

from grain_quality.calculator import calculate_ctg, consolidate_contracts
from grain_quality.models import MeasurementInput, Source
from grain_quality.norms_registry import NormNotFoundError, NormsRegistry


def _rubro(result, code):
    return next(r for r in result.rubros if r.rubro == code)


def test_ca001_usa_camara_cuando_hay_ambos():
    result = calculate_ctg("SOJA", [
        MeasurementInput("humedad", plant_value=14.2, chamber_value=13.8),
    ])
    humedad = _rubro(result, "humedad")
    assert humedad.selected_value == 13.8
    assert humedad.selected_source == Source.CAMARA


def test_ca002_usa_planta_cuando_camara_vacio():
    result = calculate_ctg("SOJA", [
        MeasurementInput("materias_extranas", plant_value=1.5),
    ])
    me = _rubro(result, "materias_extranas")
    assert me.selected_value == 1.5
    assert me.selected_source == Source.PLANTA


def test_ca003_camara_en_un_rubro_no_invalida_planta_en_otros():
    result = calculate_ctg("SOJA", [
        MeasurementInput("humedad", plant_value=14.2, chamber_value=13.8),
        MeasurementInput("materias_extranas", plant_value=1.5),
        MeasurementInput("granos_danados", plant_value=2.1, chamber_value=1.8),
    ])
    assert _rubro(result, "humedad").selected_source == Source.CAMARA
    assert _rubro(result, "materias_extranas").selected_source == Source.PLANTA
    assert _rubro(result, "materias_extranas").selected_value == 1.5
    assert _rubro(result, "granos_danados").selected_source == Source.CAMARA


def test_ca004_ca005_ctg_independientes_y_consolidacion():
    ctg1 = calculate_ctg("SOJA", [MeasurementInput("materias_extranas", 2.0)],
                         contract="10001", ctg="CTG01", weight_tn=30)
    ctg2 = calculate_ctg("SOJA", [MeasurementInput("materias_extranas", 0.5)],
                         contract="10001", ctg="CTG02", weight_tn=28)
    # cada CTG se calcula de forma independiente
    assert ctg1.total_rebaja == pytest.approx(1.0)
    assert ctg2.total_rebaja == pytest.approx(0.0)
    # y luego se consolida por contrato
    contratos = consolidate_contracts([ctg1, ctg2])
    assert len(contratos) == 1
    assert contratos[0].contract == "10001"
    assert len(contratos[0].ctgs) == 2


def test_ca006_ca007_mismo_motor_mismo_resultado():
    """La carga manual y la importación invocan calculate_ctg con los mismos
    datos; ante la misma entrada el resultado es idéntico."""
    entradas = [
        MeasurementInput("humedad", plant_value=14.2, chamber_value=13.8),
        MeasurementInput("materias_extranas", plant_value=1.5),
    ]
    a = calculate_ctg("SOJA", entradas)
    b = calculate_ctg("SOJA", entradas)
    assert [(r.rubro, r.adjustment_type, r.percentage) for r in a.rubros] == \
           [(r.rubro, r.adjustment_type, r.percentage) for r in b.rubros]
    assert a.neto == b.neto and a.total_merma == b.total_merma


def test_ca008_trazabilidad_de_origen_y_regla():
    result = calculate_ctg("SOJA", [
        MeasurementInput("materias_extranas", plant_value=2.5, chamber_value=2.0),
    ])
    me = _rubro(result, "materias_extranas")
    assert me.plant_value == 2.5
    assert me.chamber_value == 2.0
    assert me.selected_value == 2.0
    assert me.selected_source == Source.CAMARA
    assert me.rule_description  # regla aplicada visible
    assert me.norm_reference and me.norm_version
    assert result.calculated_at is not None


def test_ca009_versionado_no_altera_calculos_historicos(tmp_path):
    """Una nueva versión de norma convive con la histórica: el cálculo con
    fecha anterior sigue usando la versión vigente en esa fecha."""
    norms_dir = tmp_path / "norms"
    norms_dir.mkdir()
    (norms_dir / "soja.json").write_text(json.dumps({
        "product": {"code": "SOJA", "name": "Soja"},
        "versions": [
            {
                "version": "1",
                "norm_reference": "Norma vieja",
                "valid_from": "2020-01-01", "valid_to": "2025-12-31",
                "rubros": [{
                    "code": "materias_extranas", "name": "ME", "unit": "%",
                    "calc": {"type": "rebaja_por_exceso", "base": 1.0, "factor": 1.0},
                }],
            },
            {
                "version": "2",
                "norm_reference": "Norma nueva",
                "valid_from": "2026-01-01", "valid_to": None,
                "rubros": [{
                    "code": "materias_extranas", "name": "ME", "unit": "%",
                    "calc": {"type": "rebaja_por_exceso", "base": 1.0, "factor": 2.0},
                }],
            },
        ],
    }), encoding="utf-8")
    registry = NormsRegistry(norms_dir)

    from datetime import date
    entrada = [MeasurementInput("materias_extranas", plant_value=2.0)]
    historico = calculate_ctg("SOJA", entrada, analysis_date=date(2025, 6, 1),
                              registry=registry)
    actual = calculate_ctg("SOJA", entrada, analysis_date=date(2026, 6, 1),
                           registry=registry)
    assert historico.norm_version == "1"
    assert historico.total_rebaja == pytest.approx(1.0)   # factor 1
    assert actual.norm_version == "2"
    assert actual.total_rebaja == pytest.approx(2.0)      # factor 2

    with pytest.raises(NormNotFoundError):
        registry.get_norm("SOJA", date(2019, 1, 1))
