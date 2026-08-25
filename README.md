# Calculadora de Calidad de Mercadería de Granos

Motor parametrizable de liquidación de calidad de granos. Calcula
bonificaciones, rebajas y mermas según las normas de comercialización de
cada producto, con carga manual, importación masiva desde Excel y
consolidación por CTG y por contrato.

```
Producto → rubros → regla por rubro → Cámara/Planta → valor válido
→ motor de cálculo → resultado por CTG → consolidación por contrato
```

> **Versión Excel + VBA**: existe una implementación equivalente del SDD
> como libro de Excel con macros, sin necesidad de Python. Ver
> [`excel_vba/INSTRUCCIONES.md`](excel_vba/INSTRUCCIONES.md).

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

**Interfaz web** (carga manual, importación Excel, historial, normas):

```bash
python -m grain_quality.webapp
# abre http://localhost:5000
```

**Línea de comandos** (procesamiento por lotes):

```bash
python scripts/generar_ejemplo.py ejemplo.xlsx   # genera un Excel de prueba
python -m grain_quality.cli ejemplo.xlsx -o resultados.xlsx
```

**Tests** (incluyen los criterios de aceptación CA-001 a CA-009 del SDD):

```bash
python -m pytest tests/
```

## Arquitectura (SDD sección 17)

| Componente | Módulo | Responsabilidad |
|---|---|---|
| Frontend | `grain_quality/webapp.py` + `templates/` | carga manual, carga de Excel, visualización, exportación |
| Importador | `grain_quality/importer.py` | leer Excel, validar columnas y filas, normalizar datos |
| Quality Resolver | `grain_quality/resolver.py` | valor Planta + valor Cámara → valor válido (Cámara > Planta, por rubro) |
| Rules Engine | `grain_quality/rules_engine.py` | Producto + Rubro + Valor → bonificación/rebaja/merma |
| Persistence Layer | `grain_quality/persistence.py` (SQLite) | cálculos y trazabilidad completa |

Módulos de apoyo: `calculator.py` (orquestación por CTG y consolidación
ponderada por contrato — la carga manual y el Excel usan exactamente este
mismo motor), `norms_registry.py` (normas con versionado y vigencia),
`exporter.py` (Excel de salida con hojas *Resumen Contratos*, *Resultados
CTG*, *Detalle Calidad* y *Errores*).

## Normas parametrizadas

Las normas viven en `grain_quality/norms/*.json` — **nunca dentro del
código**. Cada archivo define un producto con sus versiones de norma
(vigencia `valid_from`/`valid_to`) y, por rubro: unidad, base, tolerancia,
tipo de cálculo, parámetros, fórmula descriptiva y obligatoriedad.

- **Agregar un producto** = agregar un archivo JSON. El motor no cambia.
- **Cambiar una norma** = agregar una *nueva versión* con su vigencia. Las
  versiones históricas no se sobrescriben, así los cálculos pasados se
  pueden reproducir (CA-009).

Tipos de cálculo disponibles: `rebaja_por_exceso`, `merma_por_exceso`
(con manipuleo opcional), `bonificacion_rebaja_lineal` (p. ej. materia
grasa de girasol), `escala` (p. ej. peso hectolítrico de trigo) y
`sin_ajuste`. Agregar un tipo nuevo es registrar una función en
`rules_engine._CALC_TYPES`.

> ⚠️ Los valores de base/factores incluidos son **configuración de
> referencia** inspirada en las normas argentinas de comercialización de
> granos. Antes de usar en producción deben validarse contra la norma
> vigente de cada producto y ajustarse en los JSON.

## Regla de prioridad Cámara/Planta (RN-001..RN-004)

Evaluada **rubro por rubro** dentro de cada CTG:

- Existen ambos valores → se usa **Cámara**.
- Solo Planta → Planta. Solo Cámara → Cámara.
- Ninguno → valor válido `NULL` (un campo vacío **no** es cero; el `0` sí
  es un análisis válido). Si el rubro es obligatorio se genera advertencia.

## Formato del Excel de entrada

Primera hoja, encabezados en la fila 1:

| Contrato | CTG | Producto | Toneladas | Humedad Planta | Humedad Camara | Materias extranas Planta | ... |
|---|---|---|---|---|---|---|---|
| 10001 | CTG01 | SOJA | 30 | 14,2 | 13,8 | 1,5 | ... |

- Columnas de rubro: `<Rubro> Planta` / `<Rubro> Camara` (acentos y
  mayúsculas indistintos; se aceptan abreviaturas como `ME`, `MG`, `PH`).
- `Kilos` en lugar de `Toneladas` se convierte automáticamente.
- Decimales con coma o punto.
- Los errores de una fila (CTG vacío, producto inexistente, CTG duplicado,
  valor no numérico, etc.) no impiden procesar el resto: las filas
  rechazadas se informan con número de fila y motivo, y se incluyen en la
  hoja *Errores* de la exportación.

## Consolidación por contrato

Cada CTG se calcula de forma independiente. El consolidado del contrato
pondera por toneladas; si algún CTG no informa peso se usa promedio simple
y se deja constancia mediante una advertencia (nunca se promedia
silenciosamente con cantidades distintas). Las mermas se informan siempre
separadas de las bonificaciones/rebajas comerciales.

## Trazabilidad

Cada cálculo guarda en SQLite (`data/calidad_granos.db`): contrato, CTG,
producto, valores Planta/Cámara por rubro, valor utilizado y su origen,
norma y versión aplicadas, regla, resultado y fecha/hora — consultable
desde la pantalla **Historial** de la web.
