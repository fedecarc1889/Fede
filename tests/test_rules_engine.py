"""Tests del Rules Engine (SDD sección 11)."""

import pytest

from grain_quality.models import AdjustmentType, MeasurementInput
from grain_quality.resolver import resolve
from grain_quality.rules_engine import UnknownCalcTypeError, apply_rule


def _resolved(rubro, plant=None, chamber=None):
    return resolve(MeasurementInput(rubro, plant_value=plant, chamber_value=chamber))


REBAJA_CFG = {
    "code": "materias_extranas", "name": "Materias extrañas", "unit": "%",
    "calc": {"type": "rebaja_por_exceso", "base": 1.0, "factor": 1.0},
}


def test_rebaja_por_exceso():
    r = apply_rule(REBAJA_CFG, _resolved("materias_extranas", plant=2.5))
    assert r.adjustment_type == AdjustmentType.REBAJA
    assert r.percentage == pytest.approx(1.5)
    assert r.signed_percentage == pytest.approx(-1.5)


def test_rebaja_dentro_de_base_sin_ajuste():
    r = apply_rule(REBAJA_CFG, _resolved("materias_extranas", plant=0.9))
    assert r.adjustment_type == AdjustmentType.SIN_AJUSTE
    assert r.percentage == 0.0


def test_merma_por_exceso_con_manipuleo():
    cfg = {
        "code": "humedad", "name": "Humedad", "unit": "%",
        "calc": {"type": "merma_por_exceso", "base": 13.5,
                 "factor": 1.0, "manipuleo": 0.25},
    }
    r = apply_rule(cfg, _resolved("humedad", chamber=14.5))
    assert r.adjustment_type == AdjustmentType.MERMA
    assert r.percentage == pytest.approx(1.25)


def test_bonificacion_rebaja_lineal():
    cfg = {
        "code": "materia_grasa", "name": "Materia grasa", "unit": "%",
        "calc": {"type": "bonificacion_rebaja_lineal", "base": 42.0,
                 "bonif_factor": 2.0, "rebaja_factor": 2.0},
    }
    bonif = apply_rule(cfg, _resolved("materia_grasa", chamber=44.0))
    assert bonif.adjustment_type == AdjustmentType.BONIFICACION
    assert bonif.percentage == pytest.approx(4.0)

    rebaja = apply_rule(cfg, _resolved("materia_grasa", plant=41.0))
    assert rebaja.adjustment_type == AdjustmentType.REBAJA
    assert rebaja.percentage == pytest.approx(2.0)

    neutro = apply_rule(cfg, _resolved("materia_grasa", plant=42.0))
    assert neutro.adjustment_type == AdjustmentType.SIN_AJUSTE


def test_escala():
    cfg = {
        "code": "peso_hectolitrico", "name": "Peso hectolítrico", "unit": "kg/hl",
        "calc": {"type": "escala", "base": 76.0, "ranges": [
            {"from": 78.0, "to": None, "tipo": "BONIFICACION", "pct": 1.0},
            {"from": 76.0, "to": 78.0, "tipo": "SIN_AJUSTE", "pct": 0.0},
            {"from": None, "to": 76.0, "tipo": "REBAJA", "pct": 0.5},
        ]},
    }
    assert apply_rule(cfg, _resolved("ph", plant=79.0)).adjustment_type \
        == AdjustmentType.BONIFICACION
    assert apply_rule(cfg, _resolved("ph", plant=76.5)).adjustment_type \
        == AdjustmentType.SIN_AJUSTE
    r = apply_rule(cfg, _resolved("ph", plant=74.0))
    assert r.adjustment_type == AdjustmentType.REBAJA
    assert r.percentage == pytest.approx(0.5)


def test_sin_dato_obligatorio_genera_advertencia():
    cfg = {
        "code": "humedad", "name": "Humedad", "unit": "%", "required": True,
        "calc": {"type": "merma_por_exceso", "base": 13.5, "factor": 1.0},
    }
    r = apply_rule(cfg, _resolved("humedad"))
    assert r.adjustment_type == AdjustmentType.SIN_DATO
    assert r.warnings


def test_valor_cero_no_es_sin_dato():
    r = apply_rule(REBAJA_CFG, _resolved("materias_extranas", chamber=0.0))
    assert r.adjustment_type == AdjustmentType.SIN_AJUSTE
    assert r.selected_value == 0.0


def test_fuera_de_rango_logico():
    cfg = dict(REBAJA_CFG, min=0, max=100)
    r = apply_rule(cfg, _resolved("materias_extranas", plant=150.0))
    assert any("fuera de rango" in w for w in r.warnings)


def test_tipo_de_calculo_desconocido():
    cfg = {"code": "x", "name": "X", "unit": "%", "calc": {"type": "magico"}}
    with pytest.raises(UnknownCalcTypeError):
        apply_rule(cfg, _resolved("x", plant=1.0))
