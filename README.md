# OCR Reader / Extractor de remitos

Herramientas de línea de comandos para OCR sobre imágenes y PDFs, y para
extraer campos estructurados de remitos escaneados con plantillas
configurables por proveedor.

## Requisitos

- Tesseract OCR instalado en el sistema (con los paquetes de idioma que
  necesites, ej. `tesseract-ocr-spa`).
- Dependencias de Python: `pip install -r requirements.txt`

## `ocr_reader.py` — OCR genérico

Extrae texto plano de imágenes o PDFs.

```
python3 ocr_reader.py remito.pdf -l spa
python3 ocr_reader.py foto.jpg -o resultado.txt
python3 ocr_reader.py ./carpeta_remitos -l spa --output-dir ./textos
```

## `remito_extractor.py` — extracción dinámica de campos por proveedor

Además del texto crudo, permite extraer campos puntuales de un remito
(número, fecha, cliente, etc.) según una **plantilla por proveedor**: cada
proveedor de remitos tiene su propio formato, así que las reglas de
extracción (regex, o región fija de la página) se definen por separado en
`providers/*.json` y se seleccionan de forma dinámica:

- **Automáticamente**: se detecta el proveedor comparando el texto OCR
  contra los marcadores (`match`) de cada plantilla.
- **Manualmente**: con `-p/--provider <id>`.
- Si no se detecta ningún proveedor conocido, se usa `providers/generic.json`
  como plantilla de respaldo con reglas genéricas.

También se puede elegir qué campos extraer con `-f/--fields` (selector de
campos), en vez de extraer todos los definidos en la plantilla.

```
# Detección automática de proveedor, todos los campos de su plantilla
python3 remito_extractor.py remito.pdf

# Forzar una plantilla de proveedor específica
python3 remito_extractor.py remito.pdf -p acme_sa

# Extraer solo ciertos campos
python3 remito_extractor.py remito.pdf -f numero_remito,fecha,cliente

# Guardar el resultado en JSON
python3 remito_extractor.py remito.pdf -o resultado.json

# Ver qué proveedores hay disponibles
python3 remito_extractor.py --list-providers

# Ver qué campos define la plantilla de un proveedor
python3 remito_extractor.py --list-fields -p acme_sa
```

La salida es JSON:

```json
{
  "archivo": "remito.pdf",
  "proveedor": "acme_sa",
  "campos": {
    "numero_remito": "0001-00012345",
    "fecha": "15/03/2026",
    "cliente": "Juan Pérez"
  }
}
```

Un valor `null` significa que ninguna regla de ese campo encontró una
coincidencia en el documento (probablemente hay que ajustar la plantilla).

### Agregar un proveedor nuevo

Ver [`providers/README.md`](providers/README.md) para el esquema completo
de las plantillas (regex vs. región fija de página) y el paso a paso para
sumar un proveedor nuevo.

## Estructura

```
ocr_core.py           Núcleo de OCR compartido (render de páginas PDF, OCR de imagen/región)
ocr_reader.py          CLI de OCR genérico (texto plano)
remito_extractor.py    CLI de extracción de campos por plantilla de proveedor
providers/             Plantillas de proveedores (una por archivo .json)
  generic.json          Plantilla de respaldo con reglas genéricas
  proveedor_ejemplo.json  Ejemplo de plantilla con regex y campo bbox
  README.md             Esquema de las plantillas
```
