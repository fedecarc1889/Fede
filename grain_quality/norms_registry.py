"""Registro de normas parametrizadas con versionado (SDD secciones 11 y 12).

Las normas viven en archivos JSON dentro de ``grain_quality/norms/``.
Cada producto posee una lista de versiones con vigencia (``valid_from`` /
``valid_to``). Las versiones históricas nunca se sobrescriben: un cambio de
norma se implementa agregando una nueva versión con su propia vigencia, lo
que permite reproducir cálculos históricos (CA-009).

Agregar un producto nuevo = agregar un archivo JSON. El motor de cálculo no
requiere modificaciones.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date
from pathlib import Path
from typing import Optional

NORMS_DIR = Path(__file__).parent / "norms"


class NormNotFoundError(Exception):
    """No existe norma vigente para el producto/fecha solicitados."""


def _normalize(text: str) -> str:
    """Normaliza códigos: mayúsculas, sin acentos ni espacios sobrantes."""
    text = unicodedata.normalize("NFKD", str(text).strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.upper()


class NormsRegistry:
    """Carga y consulta de normas por producto y fecha de vigencia."""

    def __init__(self, norms_dir: Path | str = NORMS_DIR):
        self._products: dict[str, dict] = {}
        norms_dir = Path(norms_dir)
        for path in sorted(norms_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            code = _normalize(data["product"]["code"])
            self._products[code] = data

    def product_codes(self) -> list[str]:
        return sorted(self._products.keys())

    def products(self) -> list[dict]:
        return [self._products[c]["product"] for c in self.product_codes()]

    def has_product(self, product_code: str) -> bool:
        return _normalize(product_code) in self._products

    def product_name(self, product_code: str) -> str:
        code = _normalize(product_code)
        if code not in self._products:
            raise NormNotFoundError(f"Producto inexistente: {product_code}")
        return self._products[code]["product"]["name"]

    def versions(self, product_code: str) -> list[dict]:
        code = _normalize(product_code)
        if code not in self._products:
            raise NormNotFoundError(f"Producto inexistente: {product_code}")
        return self._products[code]["versions"]

    def get_norm(self, product_code: str, on_date: Optional[date] = None) -> dict:
        """Devuelve la versión de norma vigente para el producto en la fecha dada.

        Si hay más de una versión vigente, se usa la de ``valid_from`` más
        reciente. Si ninguna está vigente se lanza NormNotFoundError
        (validación "imposibilidad de determinar la norma vigente").
        """
        on_date = on_date or date.today()
        candidates = []
        for version in self.versions(product_code):
            valid_from = date.fromisoformat(version["valid_from"])
            valid_to = (
                date.fromisoformat(version["valid_to"])
                if version.get("valid_to")
                else None
            )
            if valid_from <= on_date and (valid_to is None or on_date <= valid_to):
                candidates.append((valid_from, version))
        if not candidates:
            raise NormNotFoundError(
                f"No hay norma vigente para {product_code} al {on_date.isoformat()}"
            )
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]

    def rubros(self, product_code: str, on_date: Optional[date] = None) -> list[dict]:
        """Rubros de calidad configurados para el producto en la fecha dada."""
        return self.get_norm(product_code, on_date)["rubros"]


_default_registry: Optional[NormsRegistry] = None


def default_registry() -> NormsRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = NormsRegistry()
    return _default_registry
