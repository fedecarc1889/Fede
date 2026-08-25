# Calculadora de Calidad de Granos — versión Excel + VBA

Implementación del SDD íntegramente en Excel con macros VBA. La misma
arquitectura que la versión Python, dentro de un libro:

| Componente del SDD | En el libro |
|---|---|
| Frontend | Hojas `CargaManual` (cálculo individual) y `Datos` (importación masiva) con botones |
| Importador | `modImportacion.bas` (validación por fila, filas rechazadas → hoja `Errores`) |
| Quality Resolver | `modMotor.bas` → `ResolverValor` (Cámara > Planta, rubro por rubro) |
| Rules Engine | `modMotor.bas` → `AplicarRegla` (ejecuta la regla parametrizada, sin números fijos) |
| Persistencia / Trazabilidad | Hoja `Trazabilidad` (registro append-only de cada cálculo) |
| Normas parametrizadas y versionadas | Hojas `Config_Productos`, `Config_Normas`, `Config_Escalas` |

La carga manual y la importación llaman al **mismo** `CalcularCTG`
(CA-006/CA-007). Cada CTG se calcula independiente (CA-004) y el contrato
se consolida **ponderando por toneladas** (nunca promedio simple con
cantidades distintas). Las mermas se informan separadas de las
bonificaciones/rebajas comerciales.

## Armado (una sola vez, ~2 minutos)

El código VBA se distribuye como texto (`src/*.bas` y `src/*.cls`) porque
un proyecto VBA compilado no puede generarse fuera de Excel. Para armar el
libro definitivo:

1. Abrir `CalculadoraCalidadGranos.xlsx` en Excel (Windows o Mac).
2. Habilitar la pestaña **Programador** si no está visible
   (Archivo → Opciones → Personalizar cinta → ✔ Programador).
3. Abrir el editor VBA con **Alt+F11**.
4. En el panel de proyecto, clic derecho sobre *VBAProject
   (CalculadoraCalidadGranos)* → **Importar archivo…** e importar los
   **9 archivos** de la carpeta `src/` (los 7 `.bas` y los 2 `.cls`).
   Se pueden importar uno por uno; el orden no importa.
5. Volver a Excel y guardar como **Libro de Excel habilitado para macros
   (`*.xlsm`)** — Archivo → Guardar como → tipo `.xlsm`.
6. Ejecutar la macro **`Inicializar`** (**Alt+F8** → Inicializar →
   Ejecutar). Crea los botones y la lista desplegable de productos.

> Si al abrir el `.xlsm` Excel bloquea las macros ("contenido
> deshabilitado"), presionar **Habilitar contenido**. Si el archivo vino
> de Internet: clic derecho → Propiedades → ✔ Desbloquear.

## Uso

**Cálculo individual** (hoja `CargaManual`):
1. Elegir el producto en la celda C2 (desplegable).
2. Botón **Cargar rubros**: trae los rubros de la norma vigente.
3. Completar los valores Planta y/o Cámara (celdas amarillas). Vacío =
   sin análisis; `0` es un valor válido. Opcional: contrato, CTG,
   toneladas, fecha de análisis.
4. Botón **Calcular**: muestra valor válido, origen (CÁMARA/PLANTA) y
   ajuste por rubro, más los totales (bonificaciones, rebajas, neto y
   merma separada). El cálculo queda registrado en `Trazabilidad`.

**Importación masiva** (hoja `Datos`):
1. Pegar las filas directamente o usar **Importar archivo…** para traer
   la primera hoja de otro `.xlsx`.
2. Encabezados esperados (fila 1): `Contrato | CTG | Producto |
   Toneladas | <Rubro> Planta | <Rubro> Camara | …` — mayúsculas y
   acentos indistintos; se aceptan abreviaturas (`ME`, `MG`, `PH`,
   `Kilos` en lugar de `Toneladas`, decimales con coma o punto).
3. Botón **Procesar datos**: calcula cada CTG, consolida por contrato y
   completa `Resumen Contratos`, `Resultados CTG`, `Detalle Calidad` y
   `Errores` (filas rechazadas con número de fila y motivo — un error en
   una fila no frena el resto).
4. Botón **Exportar resultados**: guarda esas 4 hojas en un libro nuevo
   junto al archivo actual.

La hoja `Datos` trae filas de ejemplo, algunas con errores a propósito
para mostrar la hoja `Errores`. Borrarlas antes de cargar datos reales.

## Administrar normas (sin tocar código)

- **Agregar un producto**: fila en `Config_Productos` + sus rubros en
  `Config_Normas` (y rangos en `Config_Escalas` si usa tipo `ESCALA`).
- **Cambiar una norma**: agregar filas con una **nueva versión** y su
  `VigenciaDesde`, cerrando la `VigenciaHasta` de la anterior. Las
  versiones históricas no se sobrescriben: un cálculo con fecha de
  análisis anterior sigue usando la versión vigente en esa fecha.
- Tipos de cálculo: `REBAJA_POR_EXCESO`, `MERMA_POR_EXCESO` (columna
  `Manipuleo` opcional), `BONIFICACION_REBAJA_LINEAL` (columnas
  `FactorBonif`/`FactorRebaja`), `ESCALA` (rangos en `Config_Escalas`),
  `SIN_AJUSTE`.

> ⚠️ Los valores precargados son configuración de referencia inspirada en
> las normas argentinas de comercialización de granos. Validarlos contra
> la norma vigente antes de uso comercial.

## Regenerar el libro base

`CalculadoraCalidadGranos.xlsx` se genera desde las mismas normas JSON de
la versión Python (única fuente de verdad):

```bash
python excel_vba/build_template.py
```

## Archivos

```
excel_vba/
├── CalculadoraCalidadGranos.xlsx   ← libro base (importar los módulos aquí)
├── build_template.py               ← regenera el libro desde grain_quality/norms/
├── INSTRUCCIONES.md
└── src/
    ├── modUtiles.bas        utilidades (normalización, parseo; vacío ≠ cero)
    ├── modNormas.bas        acceso a Config_* con versionado y vigencia
    ├── modMotor.bas         Quality Resolver + Rules Engine + CalcularCTG
    ├── modCargaManual.bas   módulo 1: carga manual
    ├── modImportacion.bas   módulo 2: importación, consolidación, exportación
    ├── modTrazabilidad.bas  registro de auditoría
    ├── modInicio.bas        macro Inicializar (botones y desplegable)
    ├── clsRubro.cls         configuración de un rubro
    └── clsResultadoRubro.cls resultado de un rubro con trazabilidad
```

Los `.bas`/`.cls` están codificados en Windows-1252 (ANSI), el formato que
espera el editor VBA al importar.
