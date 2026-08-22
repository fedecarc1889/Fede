"""Calculadora de Calidad de Mercadería de Granos.

Motor parametrizable de liquidación de calidad de granos:

    Producto -> rubros -> regla por rubro -> Cámara/Planta -> valor válido
    -> motor de cálculo -> resultado por CTG -> consolidación por contrato.

Componentes (ver SDD sección 17):
    - importer:      lectura y validación de archivos Excel
    - resolver:      selección del valor válido (Cámara > Planta, por rubro)
    - rules_engine:  aplicación de la norma parametrizada
    - calculator:    orquestación del cálculo por CTG y contrato
    - exporter:      exportación de resultados a Excel
    - persistence:   almacenamiento y trazabilidad (SQLite)
    - webapp:        interfaz web (carga manual e importación)
"""

__version__ = "1.0.0"
