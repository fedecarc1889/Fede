# OCR Reader / Extractor de remitos

Herramientas de línea de comandos (y una interfaz web) para OCR sobre
imágenes y PDFs, y para extraer campos estructurados de remitos
escaneados con plantillas configurables por proveedor.

> Guía completa (desarrollo, instalación paso a paso, uso y resolución de
> problemas): [`DOCUMENTACION.md`](DOCUMENTACION.md).

## Instalación

Automática (instala Tesseract, crea un entorno virtual e instala las
dependencias de Python):
```bash
./install.sh
source venv/bin/activate
```

Manual: Tesseract OCR debe estar instalado en el sistema (ej.
`sudo apt-get install tesseract-ocr tesseract-ocr-spa` en Ubuntu/Debian, o
`brew install tesseract tesseract-lang` en macOS), y las dependencias de
Python con `pip install -r requirements.txt`. Ver el paso a paso completo
en [`DOCUMENTACION.md`](DOCUMENTACION.md#4-instalación-paso-a-paso).

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
campos), en vez de extraer todos los definidos en la plantilla. Y además
de un PDF individual, `input` puede ser una **carpeta** con varios
remitos (de uno o varios proveedores) para procesarlos todos juntos.

```
# Detección automática de proveedor, todos los campos de su plantilla
python3 remito_extractor.py remito.pdf

# Forzar una plantilla de proveedor específica
python3 remito_extractor.py remito.pdf -p acme_sa

# Extraer solo ciertos campos
python3 remito_extractor.py remito.pdf -f numero_remito,fecha,cliente

# Guardar el resultado en JSON
python3 remito_extractor.py remito.pdf -o resultado.json

# Procesar una carpeta entera y consolidar todo en un Excel
python3 remito_extractor.py ./carpeta_remitos -o resultados.xlsx

# Ver qué proveedores hay disponibles
python3 remito_extractor.py --list-providers

# Ver qué campos define la plantilla de un proveedor
python3 remito_extractor.py --list-fields -p acme_sa
```

Por defecto la salida es JSON:

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

### Exportar a Excel

Si `-o` termina en `.xlsx` (o `.xls`), en vez de JSON se genera una
planilla Excel con **una fila por remito** y **una columna por campo**
(unión de los campos de todos los proveedores procesados, con `archivo` y
`proveedor` como primeras columnas). Sirve tanto para un único PDF como
para una carpeta entera con remitos de distintos proveedores:

```
python3 remito_extractor.py remito.pdf -o remito.xlsx
python3 remito_extractor.py ./carpeta_remitos -o resultados.xlsx
```

### Agregar un proveedor nuevo

Ver [`providers/README.md`](providers/README.md) para el esquema completo
de las plantillas (regex vs. región fija de página) y el paso a paso para
sumar un proveedor nuevo a mano. También se puede hacer visualmente con
la interfaz web (ver abajo).

## Interfaz gráfica (`webapp/`)

Miniapp Flask para configurar las plantillas de proveedor sin editar JSON
a mano:

```
pip install -r requirements.txt
python3 webapp/app.py
# abrir http://127.0.0.1:5000
```

Permite:

- Subir un PDF de ejemplo del remito y ver su texto OCR y la imagen de
  cada página.
- Elegir una plantilla existente para editarla, o crear una nueva
  (ID + nombre + marcadores de detección automática).
- Por cada campo: escribir una o más regex y probarlas en vivo contra el
  texto OCR, **o** dibujar con el mouse una región (bbox) sobre la imagen
  de la página para campos en una posición fija (sellos, numeración
  pre-impresa).
- Probar la extracción completa de la plantilla contra el PDF de ejemplo
  antes de guardar, y **descargarla como Excel** con un botón.
- Guardar, lo que escribe/actualiza `providers/<id>.json` — el mismo
  archivo que usa `remito_extractor.py` por línea de comandos.

## Estructura

```
ocr_core.py           Núcleo de OCR compartido (render de páginas PDF, OCR de imagen/región)
ocr_reader.py          CLI de OCR genérico (texto plano)
remito_extractor.py    CLI de extracción de campos por plantilla de proveedor
providers/             Plantillas de proveedores (una por archivo .json)
  generic.json          Plantilla de respaldo con reglas genéricas
  proveedor_ejemplo.json  Ejemplo de plantilla con regex y campo bbox
  README.md             Esquema de las plantillas
webapp/                Interfaz gráfica (Flask) para configurar plantillas
  app.py                 Backend: subida de PDF, OCR, guardado/prueba de plantillas
  templates/, static/    Frontend (HTML/CSS/JS, sin dependencias externas)
install.sh             Instalación automática (Tesseract + entorno virtual + dependencias)
DOCUMENTACION.md       Documentación completa (desarrollo, instalación, uso, troubleshooting)
```
