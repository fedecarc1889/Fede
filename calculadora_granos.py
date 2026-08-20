#!/usr/bin/env python3
"""
Calculadora de Calidad de Granos - Basada en las Normas de Comercialización
de uso habitual en el mercado de granos argentino (BCR / Bolsa de Cereales).

Calcula mermas por humedad, descuentos por materias extrañas/granos
dañados/quebrados/verdes y rebajas por peso hectolítrico, obteniendo el
peso neto comercial de un lote (y su valor, si se indica un precio base).

Uso:
    # Cálculo manual de un lote
    python3 calculadora_granos.py --grano trigo --peso 30000 --humedad 14.8 \\
        --materias-extranas 2.2 --danados 3.1 --quebrados 1.5 --ph 76.5 \\
        --precio 220000

    # Importar una planilla Excel con varios lotes
    python3 calculadora_granos.py --excel lotes.xlsx --output resultado.xlsx

    # Generar una planilla de ejemplo con el formato esperado
    python3 calculadora_granos.py --plantilla plantilla.xlsx

    # Ver los granos y parámetros base disponibles
    python3 calculadora_granos.py --listar-granos
"""

import argparse
import sys

from normas_bcr import GRANOS, calcular_lote, granos_disponibles


def imprimir_resultado(resultado: dict) -> None:
    print(f"\nGrano: {resultado['grano']}")
    print(f"Peso bruto: {resultado['peso_bruto_kg']:.2f} kg")
    print("\nDesglose de rebajas:")
    for item in resultado["desglose"].values():
        print(
            f"  - {item['label']}: real={item['valor_real']:.2f}  "
            f"base/tolerancia={item['base_o_tolerancia']:.2f}  "
            f"descuento={item['descuento_pct']:.2f}%"
        )
    print(f"\nDescuento total: {resultado['descuento_total_pct']:.2f}%")
    print(f"Peso neto comercial: {resultado['peso_neto_kg']:.2f} kg")
    print(f"Clasificación orientativa: {resultado['grado_orientativo']}")
    if "valor_neto" in resultado:
        print(f"Precio base: {resultado['precio_base']:.2f} $/tn")
        print(f"Valor neto del lote: {resultado['valor_neto']:.2f} $")


def listar_granos() -> None:
    print("Granos disponibles y parámetros base configurados:\n")
    for clave, grano in GRANOS.items():
        print(f"[{clave}] {grano.label}")
        print(f"  Humedad base: {grano.humedad_base}%")
        if grano.peso_hectolitrico_base is not None:
            print(
                f"  Peso hectolítrico base: {grano.peso_hectolitrico_base} kg/hl "
                f"(rebaja {grano.factor_ph_pct_por_kg}% por kg/hl faltante)"
            )
        for factor in grano.factores.values():
            print(f"  {factor.label}: tolerancia {factor.tolerancia}%")
        print()
    print(
        "Nota: estos valores son los de uso habitual en el mercado y pueden "
        "diferir de la norma vigente publicada por la BCR según campaña. "
        "Ajustar normas_bcr.py si es necesario antes de usar en una operación real."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculadora de calidad de granos según Normas de Comercialización (BCR)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("--grano", choices=granos_disponibles(), help="Tipo de grano")
    parser.add_argument("--peso", type=float, help="Peso bruto del lote en kg")
    parser.add_argument("--humedad", type=float, help="Humedad de recibo en %%")
    parser.add_argument("--materias-extranas", type=float, default=0.0, help="Materias extrañas en %%")
    parser.add_argument("--danados", type=float, default=0.0, help="Granos dañados en %%")
    parser.add_argument("--verdes", type=float, default=0.0, help="Granos verdes en %% (soja)")
    parser.add_argument("--quebrados", type=float, default=0.0, help="Granos quebrados/partidos en %%")
    parser.add_argument("--ph", type=float, help="Peso hectolítrico en kg/hl")
    parser.add_argument("--precio", type=float, help="Precio base en $/tonelada (opcional)")

    parser.add_argument("--excel", help="Ruta a un Excel con datos de calidad de varios lotes")
    parser.add_argument("--output", help="Ruta de salida del Excel con los resultados (usar con --excel)")
    parser.add_argument("--hoja", default=0, help="Nombre o índice de la hoja a leer (usar con --excel)")

    parser.add_argument("--plantilla", help="Genera un Excel de ejemplo en la ruta indicada y termina")
    parser.add_argument("--listar-granos", action="store_true", help="Lista los granos y parámetros base disponibles")

    args = parser.parse_args()

    if args.listar_granos:
        listar_granos()
        return

    if args.plantilla:
        from excel_granos import generar_plantilla

        generar_plantilla(args.plantilla)
        print(f"Plantilla generada en: {args.plantilla}")
        return

    if args.excel:
        from excel_granos import exportar_resultado, procesar_excel

        try:
            hoja = int(args.hoja)
        except (TypeError, ValueError):
            hoja = args.hoja

        try:
            df_resultado = procesar_excel(args.excel, hoja=hoja)
        except Exception as e:
            print(f"ERROR procesando el Excel: {e}", file=sys.stderr)
            sys.exit(1)

        if args.output:
            exportar_resultado(df_resultado, args.output)
            print(f"Resultados guardados en: {args.output}")
        else:
            print(df_resultado.to_string(index=False))
        return

    # Modo manual: requiere grano, peso y humedad como mínimo
    if not args.grano or args.peso is None or args.humedad is None:
        parser.error(
            "Para el cálculo manual son obligatorios --grano, --peso y --humedad "
            "(o usar --excel / --plantilla / --listar-granos)."
        )

    factores = {
        "materias_extranas": args.materias_extranas,
        "granos_danados": args.danados,
        "granos_verdes": args.verdes,
        "granos_quebrados": args.quebrados,
    }

    try:
        resultado = calcular_lote(
            grano_key=args.grano,
            peso_kg=args.peso,
            humedad=args.humedad,
            factores=factores,
            ph=args.ph,
            precio_base=args.precio,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    imprimir_resultado(resultado)


if __name__ == "__main__":
    main()
