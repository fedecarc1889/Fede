"""Quality Resolver: selección del valor válido por rubro (SDD secciones 6 y 19).

Regla central del sistema, evaluada de forma independiente para cada rubro
de cada CTG:

    RN-001  Existen Planta y Cámara      -> se usa Cámara
    RN-002  Existe solo Planta           -> se usa Planta
    RN-003  Existe solo Cámara           -> se usa Cámara
    RN-004  No existe ninguno            -> valor válido NULL (nunca cero)

Conceptualmente: ``valor_valido = valor_camara ?? valor_planta``.

El valor 0 (cero) es un valor válido de análisis y jamás debe interpretarse
como ausencia de dato.
"""

from __future__ import annotations

from typing import Optional

from .models import MeasurementInput, ResolvedValue, Source


def resolve(measurement: MeasurementInput) -> ResolvedValue:
    """Determina el valor válido y su origen para un rubro."""
    value: Optional[float]
    source: Optional[Source]

    if measurement.chamber_value is not None:
        value, source = measurement.chamber_value, Source.CAMARA
    elif measurement.plant_value is not None:
        value, source = measurement.plant_value, Source.PLANTA
    else:
        value, source = None, None

    return ResolvedValue(
        rubro=measurement.rubro,
        plant_value=measurement.plant_value,
        chamber_value=measurement.chamber_value,
        value=value,
        source=source,
    )
