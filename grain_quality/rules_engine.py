"""Rules Engine: Producto + Rubro + Valor válido -> ajuste (SDD sección 11).

El motor no contiene números fijos de ninguna norma: ejecuta la regla
parametrizada que recibe desde la configuración (``norms/*.json``). Cada
rubro declara un tipo de cálculo (``calc.type``) y sus parámetros.

Tipos de cálculo soportados:

    sin_ajuste
        El rubro es informativo, no genera ajuste.

    rebaja_por_exceso
        Si valor > base + tolerancia, rebaja = (valor - base) * factor.
        Parámetro opcional ``max_pct`` limita la rebaja.

    bonificacion_rebaja_lineal
        Sobre la base bonifica (valor - base) * bonif_factor;
        bajo la base rebaja (base - valor) * rebaja_factor.
        (ej.: materia grasa de girasol).

    escala
        Tabla de rangos [from, to) con tipo y porcentaje fijos
        (ej.: peso hectolítrico de trigo).

    merma_por_exceso
        Igual a rebaja_por_exceso pero el resultado se clasifica como
        MERMA (se informa separada de bonificaciones/rebajas comerciales).
        Parámetro opcional ``manipuleo`` suma un porcentaje fijo cuando
        hay exceso (merma por manipuleo/secado).

Agregar un nuevo tipo de cálculo = registrar una función en ``_CALC_TYPES``.
"""

from __future__ import annotations

from typing import Callable, Optional

from .models import AdjustmentType, ResolvedValue, RubroResult


class UnknownCalcTypeError(Exception):
    pass


def _round(x: float) -> float:
    return round(x + 1e-12, 4)


def _calc_sin_ajuste(calc: dict, value: float) -> tuple[AdjustmentType, float]:
    return AdjustmentType.SIN_AJUSTE, 0.0


def _calc_rebaja_por_exceso(calc: dict, value: float) -> tuple[AdjustmentType, float]:
    base = float(calc["base"])
    tolerance = float(calc.get("tolerance", 0.0))
    factor = float(calc.get("factor", 1.0))
    if value > base + tolerance:
        pct = (value - base) * factor
        max_pct = calc.get("max_pct")
        if max_pct is not None:
            pct = min(pct, float(max_pct))
        return AdjustmentType.REBAJA, _round(pct)
    return AdjustmentType.SIN_AJUSTE, 0.0


def _calc_merma_por_exceso(calc: dict, value: float) -> tuple[AdjustmentType, float]:
    base = float(calc["base"])
    tolerance = float(calc.get("tolerance", 0.0))
    factor = float(calc.get("factor", 1.0))
    if value > base + tolerance:
        pct = (value - base) * factor + float(calc.get("manipuleo", 0.0))
        max_pct = calc.get("max_pct")
        if max_pct is not None:
            pct = min(pct, float(max_pct))
        return AdjustmentType.MERMA, _round(pct)
    return AdjustmentType.SIN_AJUSTE, 0.0


def _calc_bonif_rebaja_lineal(calc: dict, value: float) -> tuple[AdjustmentType, float]:
    base = float(calc["base"])
    if value > base:
        pct = (value - base) * float(calc.get("bonif_factor", 1.0))
        max_pct = calc.get("max_bonif_pct")
        if max_pct is not None:
            pct = min(pct, float(max_pct))
        return AdjustmentType.BONIFICACION, _round(pct)
    if value < base:
        pct = (base - value) * float(calc.get("rebaja_factor", 1.0))
        max_pct = calc.get("max_rebaja_pct")
        if max_pct is not None:
            pct = min(pct, float(max_pct))
        return AdjustmentType.REBAJA, _round(pct)
    return AdjustmentType.SIN_AJUSTE, 0.0


def _calc_escala(calc: dict, value: float) -> tuple[AdjustmentType, float]:
    for rng in calc["ranges"]:
        lo = rng.get("from")
        hi = rng.get("to")
        if (lo is None or value >= float(lo)) and (hi is None or value < float(hi)):
            tipo = AdjustmentType(rng.get("tipo", "SIN_AJUSTE"))
            return tipo, _round(float(rng.get("pct", 0.0)))
    return AdjustmentType.SIN_AJUSTE, 0.0


_CALC_TYPES: dict[str, Callable[[dict, float], tuple[AdjustmentType, float]]] = {
    "sin_ajuste": _calc_sin_ajuste,
    "rebaja_por_exceso": _calc_rebaja_por_exceso,
    "merma_por_exceso": _calc_merma_por_exceso,
    "bonificacion_rebaja_lineal": _calc_bonif_rebaja_lineal,
    "escala": _calc_escala,
}


def apply_rule(
    rubro_cfg: dict,
    resolved: ResolvedValue,
    norm_reference: str = "",
    norm_version: str = "",
) -> RubroResult:
    """Aplica la regla configurada de un rubro sobre su valor válido.

    Con valor válido NULL (RN-004) no se calcula ajuste: si el rubro es
    obligatorio se registra una advertencia; el cero sí es un valor válido.
    """
    calc = rubro_cfg.get("calc", {"type": "sin_ajuste"})
    calc_type = calc.get("type", "sin_ajuste")
    if calc_type not in _CALC_TYPES:
        raise UnknownCalcTypeError(
            f"Tipo de cálculo desconocido '{calc_type}' en rubro {rubro_cfg.get('code')}"
        )

    base: Optional[float] = calc.get("base")
    tolerance: Optional[float] = calc.get("tolerance")
    warnings: list[str] = []

    if resolved.value is None:
        adjustment, pct = AdjustmentType.SIN_DATO, 0.0
        if rubro_cfg.get("required"):
            warnings.append(
                f"Rubro obligatorio '{rubro_cfg.get('name', resolved.rubro)}' sin análisis "
                "(ni Planta ni Cámara)."
            )
    else:
        vmin, vmax = rubro_cfg.get("min"), rubro_cfg.get("max")
        if (vmin is not None and resolved.value < float(vmin)) or (
            vmax is not None and resolved.value > float(vmax)
        ):
            warnings.append(
                f"Valor {resolved.value} fuera de rango lógico "
                f"[{vmin}, {vmax}] para '{rubro_cfg.get('name', resolved.rubro)}'."
            )
        adjustment, pct = _CALC_TYPES[calc_type](calc, resolved.value)

    return RubroResult(
        rubro=rubro_cfg["code"],
        rubro_name=rubro_cfg.get("name", rubro_cfg["code"]),
        unit=rubro_cfg.get("unit", "%"),
        plant_value=resolved.plant_value,
        chamber_value=resolved.chamber_value,
        selected_value=resolved.value,
        selected_source=resolved.source,
        base=float(base) if base is not None else None,
        tolerance=float(tolerance) if tolerance is not None else None,
        adjustment_type=adjustment,
        percentage=pct,
        rule_description=calc.get("formula", calc_type),
        norm_reference=norm_reference,
        norm_version=norm_version,
        warnings=warnings,
    )
