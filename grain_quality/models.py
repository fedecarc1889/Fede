"""Modelo de datos del sistema (ver SDD secciones 4 y 18)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Source(str, Enum):
    """Origen de un valor de análisis de calidad."""

    PLANTA = "PLANTA"
    CAMARA = "CAMARA"


class AdjustmentType(str, Enum):
    """Tipo de ajuste que produce una regla sobre un rubro."""

    BONIFICACION = "BONIFICACION"
    REBAJA = "REBAJA"
    MERMA = "MERMA"
    SIN_AJUSTE = "SIN_AJUSTE"
    SIN_DATO = "SIN_DATO"


@dataclass
class MeasurementInput:
    """Valores de análisis de un rubro para un CTG (Planta y/o Cámara).

    Un campo en None significa "sin análisis". El valor 0 (cero) es un
    valor válido y nunca debe confundirse con la ausencia de dato (RN-004).
    """

    rubro: str
    plant_value: Optional[float] = None
    chamber_value: Optional[float] = None


@dataclass
class ResolvedValue:
    """Resultado del Quality Resolver para un rubro (RN-001..RN-004)."""

    rubro: str
    plant_value: Optional[float]
    chamber_value: Optional[float]
    value: Optional[float]
    source: Optional[Source]


@dataclass
class RubroResult:
    """Resultado del cálculo de un rubro, con trazabilidad completa."""

    rubro: str
    rubro_name: str
    unit: str
    plant_value: Optional[float]
    chamber_value: Optional[float]
    selected_value: Optional[float]
    selected_source: Optional[Source]
    base: Optional[float]
    tolerance: Optional[float]
    adjustment_type: AdjustmentType
    percentage: float  # magnitud, siempre >= 0
    rule_description: str = ""
    norm_reference: str = ""
    norm_version: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def signed_percentage(self) -> float:
        """Porcentaje con signo: bonificación positiva, rebaja/merma negativa."""
        if self.adjustment_type == AdjustmentType.BONIFICACION:
            return self.percentage
        if self.adjustment_type in (AdjustmentType.REBAJA, AdjustmentType.MERMA):
            return -self.percentage
        return 0.0


@dataclass
class CTGResult:
    """Resultado consolidado de un CTG (SDD sección 13)."""

    contract: str
    ctg: str
    product_code: str
    product_name: str
    weight_tn: Optional[float]
    rubros: list[RubroResult]
    norm_reference: str
    norm_version: str
    calculated_at: datetime = field(default_factory=datetime.now)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_bonificacion(self) -> float:
        return sum(
            r.percentage
            for r in self.rubros
            if r.adjustment_type == AdjustmentType.BONIFICACION
        )

    @property
    def total_rebaja(self) -> float:
        return sum(
            r.percentage
            for r in self.rubros
            if r.adjustment_type == AdjustmentType.REBAJA
        )

    @property
    def total_merma(self) -> float:
        """Las mermas se informan separadas de bonificaciones/rebajas comerciales."""
        return sum(
            r.percentage
            for r in self.rubros
            if r.adjustment_type == AdjustmentType.MERMA
        )

    @property
    def neto(self) -> float:
        return self.total_bonificacion - self.total_rebaja


@dataclass
class ContractResult:
    """Resultado consolidado por contrato (SDD sección 14).

    Si todos los CTG informan toneladas, la consolidación es un promedio
    ponderado por peso; nunca un promedio simple con cantidades distintas.
    """

    contract: str
    ctgs: list[CTGResult]
    weighted: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def total_weight(self) -> Optional[float]:
        weights = [c.weight_tn for c in self.ctgs if c.weight_tn is not None]
        return sum(weights) if weights else None

    def _consolidate(self, attr: str) -> float:
        values = [(getattr(c, attr), c.weight_tn) for c in self.ctgs]
        if not values:
            return 0.0
        if self.weighted:
            total_w = sum(w for _, w in values)
            if total_w > 0:
                return sum(v * w for v, w in values) / total_w
        return sum(v for v, _ in values) / len(values)

    @property
    def total_bonificacion(self) -> float:
        return self._consolidate("total_bonificacion")

    @property
    def total_rebaja(self) -> float:
        return self._consolidate("total_rebaja")

    @property
    def total_merma(self) -> float:
        return self._consolidate("total_merma")

    @property
    def neto(self) -> float:
        return self.total_bonificacion - self.total_rebaja


@dataclass
class ImportError_:
    """Fila rechazada durante una importación, con su motivo (SDD sección 16)."""

    row_number: Optional[int]
    contract: str
    ctg: str
    reason: str
