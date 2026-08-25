"""Capa de persistencia y trazabilidad (SDD secciones 15 y 18).

Almacena en SQLite cada cálculo realizado con su detalle por rubro:
contrato, CTG, producto, valores Planta/Cámara, valor utilizado y su
origen, norma y versión aplicadas, regla, resultado y fecha/hora. Esto
permite auditar posteriormente por qué el sistema obtuvo cada resultado,
incluso después de un cambio de norma (CA-009: el cálculo histórico queda
registrado con la versión que se aplicó).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Union

from .models import CTGResult

DEFAULT_DB = Path(__file__).parent.parent / "data" / "calidad_granos.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calculation (
    calculation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract        TEXT NOT NULL,
    ctg             TEXT NOT NULL,
    product_code    TEXT NOT NULL,
    product_name    TEXT NOT NULL,
    weight_tn       REAL,
    norm_reference  TEXT NOT NULL,
    norm_version    TEXT NOT NULL,
    bonificacion    REAL NOT NULL,
    rebaja          REAL NOT NULL,
    neto            REAL NOT NULL,
    merma           REAL NOT NULL,
    warnings        TEXT,
    calculated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calculation_detail (
    detail_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    calculation_id  INTEGER NOT NULL REFERENCES calculation(calculation_id),
    rubro_code      TEXT NOT NULL,
    rubro_name      TEXT NOT NULL,
    unit            TEXT NOT NULL,
    plant_value     REAL,
    chamber_value   REAL,
    selected_value  REAL,
    selected_source TEXT,
    base            REAL,
    tolerance       REAL,
    rule            TEXT,
    adjustment_type TEXT NOT NULL,
    percentage      REAL NOT NULL
);
"""


class Repository:
    """Repositorio SQLite para cálculos y su trazabilidad."""

    def __init__(self, db_path: Union[str, Path] = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_calculation(self, result: CTGResult) -> int:
        """Guarda un cálculo completo y devuelve su identificador."""
        cursor = self._conn.execute(
            """INSERT INTO calculation
               (contract, ctg, product_code, product_name, weight_tn,
                norm_reference, norm_version, bonificacion, rebaja, neto,
                merma, warnings, calculated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.contract, result.ctg, result.product_code,
                result.product_name, result.weight_tn,
                result.norm_reference, result.norm_version,
                result.total_bonificacion, result.total_rebaja, result.neto,
                result.total_merma, "; ".join(result.warnings),
                result.calculated_at.isoformat(sep=" ", timespec="seconds"),
            ),
        )
        calculation_id = cursor.lastrowid
        for rubro in result.rubros:
            self._conn.execute(
                """INSERT INTO calculation_detail
                   (calculation_id, rubro_code, rubro_name, unit, plant_value,
                    chamber_value, selected_value, selected_source, base,
                    tolerance, rule, adjustment_type, percentage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    calculation_id, rubro.rubro, rubro.rubro_name, rubro.unit,
                    rubro.plant_value, rubro.chamber_value,
                    rubro.selected_value,
                    rubro.selected_source.value if rubro.selected_source else None,
                    rubro.base, rubro.tolerance, rubro.rule_description,
                    rubro.adjustment_type.value, rubro.signed_percentage,
                ),
            )
        self._conn.commit()
        return calculation_id

    def list_calculations(self, limit: int = 100) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM calculation ORDER BY calculation_id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def get_calculation(self, calculation_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM calculation WHERE calculation_id = ?",
            (calculation_id,),
        ).fetchone()

    def get_details(self, calculation_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM calculation_detail WHERE calculation_id = ? "
            "ORDER BY detail_id",
            (calculation_id,),
        ).fetchall()

    def close(self) -> None:
        self._conn.close()
