"""Orquestador del cálculo de calidad (SDD secciones 13 y 14).

La carga manual y la importación Excel usan exactamente este mismo módulo
(CA-006 / CA-007): entrada -> resolver -> norma vigente -> motor de reglas
-> resultado por CTG -> consolidación por contrato.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from . import resolver, rules_engine
from .models import ContractResult, CTGResult, MeasurementInput
from .norms_registry import NormsRegistry, _normalize, default_registry


def calculate_ctg(
    product_code: str,
    measurements: list[MeasurementInput],
    contract: str = "",
    ctg: str = "",
    weight_tn: Optional[float] = None,
    analysis_date: Optional[date] = None,
    registry: Optional[NormsRegistry] = None,
) -> CTGResult:
    """Calcula bonificaciones, rebajas y mermas de un CTG.

    La prioridad Cámara/Planta se evalúa rubro por rubro: la existencia de
    Cámara en un rubro no invalida los valores de Planta de otros rubros
    del mismo CTG (CA-003).
    """
    registry = registry or default_registry()
    norm = registry.get_norm(product_code, analysis_date)
    norm_ref = norm.get("norm_reference", "")
    norm_version = str(norm.get("version", ""))

    by_rubro = {_normalize(m.rubro): m for m in measurements}
    warnings: list[str] = []
    unknown = set(by_rubro) - {_normalize(r["code"]) for r in norm["rubros"]}
    for code in sorted(unknown):
        warnings.append(f"Rubro desconocido para {product_code}: {code} (ignorado).")

    rubro_results = []
    for rubro_cfg in norm["rubros"]:
        measurement = by_rubro.get(
            _normalize(rubro_cfg["code"]), MeasurementInput(rubro=rubro_cfg["code"])
        )
        resolved = resolver.resolve(measurement)
        result = rules_engine.apply_rule(rubro_cfg, resolved, norm_ref, norm_version)
        warnings.extend(result.warnings)
        rubro_results.append(result)

    return CTGResult(
        contract=str(contract or ""),
        ctg=str(ctg or ""),
        product_code=_normalize(product_code),
        product_name=registry.product_name(product_code),
        weight_tn=weight_tn,
        rubros=rubro_results,
        norm_reference=norm_ref,
        norm_version=norm_version,
        warnings=warnings,
    )


def consolidate_contracts(ctg_results: list[CTGResult]) -> list[ContractResult]:
    """Consolida resultados de CTG por contrato (SDD sección 14).

    Cada CTG se calcula de forma independiente (CA-004); la consolidación
    pondera por toneladas cuando todos los CTG informan peso. Si alguno no
    lo informa, se usa promedio simple y se deja constancia en advertencias
    (nunca se mezclan silenciosamente pesos parciales).
    """
    by_contract: dict[str, list[CTGResult]] = {}
    for res in ctg_results:
        by_contract.setdefault(res.contract, []).append(res)

    contracts = []
    for contract, ctgs in by_contract.items():
        weights = [c.weight_tn for c in ctgs]
        weighted = all(w is not None and w > 0 for w in weights)
        contract_warnings = []
        if not weighted and len(ctgs) > 1:
            contract_warnings.append(
                "No todos los CTG informan toneladas: la consolidación usa "
                "promedio simple en lugar de ponderado."
            )
        contracts.append(
            ContractResult(
                contract=contract,
                ctgs=ctgs,
                weighted=weighted,
                warnings=contract_warnings,
            )
        )
    return contracts
