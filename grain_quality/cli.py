"""CLI para procesar archivos Excel por lotes.

Uso:
    python -m grain_quality.cli entrada.xlsx -o resultados.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .exporter import export_results
from .importer import import_excel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calcula bonificaciones/rebajas de calidad desde un Excel."
    )
    parser.add_argument("input", help="Archivo .xlsx de entrada")
    parser.add_argument(
        "-o", "--output", default="resultados.xlsx",
        help="Archivo .xlsx de salida (default: resultados.xlsx)",
    )
    args = parser.parse_args(argv)

    if not Path(args.input).exists():
        print(f"No existe el archivo: {args.input}", file=sys.stderr)
        return 1

    result = import_excel(args.input)
    export_results(result.contract_results, result.errors, args.output)

    print(f"CTG procesados:  {len(result.ctg_results)}")
    print(f"Contratos:       {len(result.contract_results)}")
    print(f"Filas rechazadas: {len(result.errors)}")
    for error in result.errors:
        row = f"fila {error.row_number}" if error.row_number else "archivo"
        print(f"  - [{row}] {error.reason}", file=sys.stderr)
    for contract in result.contract_results:
        print(
            f"Contrato {contract.contract or '(sin contrato)'}: "
            f"bonif +{contract.total_bonificacion:.2f}% / "
            f"rebaja -{contract.total_rebaja:.2f}% / "
            f"neto {contract.neto:+.2f}% / merma {contract.total_merma:.2f}%"
        )
    print(f"Resultados exportados a: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
