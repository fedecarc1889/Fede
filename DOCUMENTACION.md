# Documentación completa

Extractor dinámico de campos de remitos en PDF, con OCR y plantillas
configurables por proveedor. Este documento cubre qué se construyó, cómo
instalarlo y cómo usar cada pieza.

---

## 1. Resumen del proyecto

El objetivo es leer remitos escaneados (PDF) de distintos proveedores —
cada uno con su propio formato— y extraer campos estructurados (número de
remito, fecha, cliente, etc.) de forma automática. Como cada proveedor
ubica y etiqueta esos datos de manera distinta, la extracción no está
"hardcodeada": se define mediante **plantillas** (una por proveedor) que
el sistema selecciona dinámicamente, ya sea detectando automáticamente al
proveedor a partir del texto OCR, o indicándolo manualmente.

Existen dos formas de trabajar con las plantillas: editando los archivos
JSON a mano, o mediante una interfaz web que permite probarlas visualmente
contra un PDF de ejemplo antes de guardarlas.

---

## 2. Qué se desarrolló

### Etapa 1 — OCR base

`ocr_reader.py`: CLI que extrae texto plano de imágenes (PNG, JPG, BMP,
TIFF, GIF, WEBP) y de PDFs, usando Tesseract (vía `pytesseract`) como
motor de OCR y PyMuPDF (`fitz`) para renderizar cada página de un PDF
como imagen antes de pasarla por OCR. Soporta procesar un archivo o un
directorio completo, con selección de idioma.

### Etapa 2 — Núcleo de OCR compartido

`ocr_core.py`: se extrajo la lógica común de renderizado de páginas PDF y
OCR (que antes vivía solo en `ocr_reader.py`) a un módulo reutilizable,
para que tanto `ocr_reader.py` como el nuevo extractor de campos la
compartan sin duplicar código. Expone:
- `ocr_image(img, lang)` — OCR de una imagen ya cargada en memoria.
- `render_pdf_page(doc, page_index, zoom)` — renderiza una página de un
  PDF abierto (fitz) a imagen PIL.
- `ocr_pdf_pages(path, lang, zoom, progress_callback)` — OCR de todas las
  páginas de un PDF, retorna una lista de strings (uno por página).
- `ocr_pdf(path, lang, zoom)` — igual que la anterior pero como un único
  string con separadores de página.
- `ocr_pdf_region(path, page_index, bbox, lang, zoom)` — OCR de solo una
  región (rectángulo) de una página, dado un bbox normalizado (0.0–1.0).
  Es la pieza que permite leer campos en una posición fija del formulario
  (sellos, numeración pre-impresa) cuando una regex sobre el texto
  completo no es confiable.

### Etapa 3 — Extractor dinámico de campos (`remito_extractor.py`)

CLI que:
1. Corre OCR sobre el PDF de entrada (reutilizando `ocr_core`).
2. Determina qué **plantilla de proveedor** usar:
   - **Automáticamente**, comparando el texto OCR contra los marcadores
     regex (`match`) definidos en cada plantilla — gana la plantilla con
     más coincidencias.
   - **Manualmente**, con `-p/--provider <id>`.
   - Si no se detecta ninguna, cae en `providers/generic.json` como
     respaldo.
3. Aplica las reglas de cada campo de la plantilla elegida: una o más
   regex sobre el texto (con reintento en orden hasta que una matchee), o
   una región `bbox` de una página específica.
4. Permite filtrar qué campos extraer con `-f/--fields` en vez de todos
   los de la plantilla.
5. Imprime (o guarda) el resultado como JSON:
   `{"archivo", "proveedor", "campos": {...}}`, con `null` en los campos
   que no matchearon nada (señal de que hay que ajustar la plantilla).

Comandos de exploración: `--list-providers` (qué plantillas hay) y
`--list-fields -p <id>` (qué campos define una plantilla puntual).

### Etapa 4 — Plantillas de proveedor (`providers/`)

Cada plantilla es un archivo `providers/<id>.json`:

```json
{
  "label": "Nombre legible",
  "match": ["regex que identifica al proveedor en el texto OCR"],
  "fields": {
    "numero_remito": { "regex": ["Remito[^\\d]{0,12}([0-9][0-9\\-]{3,})"] },
    "zona_sello":    { "bbox": [0.75, 0.03, 0.98, 0.10], "page": 0 }
  }
}
```

Se incluyen `generic.json` (plantilla de respaldo con reglas laxas para
campos comunes de remito) y `proveedor_ejemplo.json` (ejemplo con ambos
métodos de extracción). El esquema completo está en
[`providers/README.md`](providers/README.md). Los archivos que empiezan
con `_` se ignoran al cargar (útil para borradores).

Un detalle de diseño no evidente: las regex de `numero_remito` evitan
depender del carácter "°" (grado) porque Tesseract lo reconoce de forma
muy inconsistente según la fuente (a veces "N°", a veces "N*", "N9",
etc.); en cambio, matchean "Remito" seguido de hasta N caracteres
no-numéricos y luego el número, sin importar cómo se OCR-ee el símbolo de
por medio.

### Etapa 5 — Interfaz gráfica (`webapp/`)

Miniapp Flask para crear y editar plantillas sin tocar JSON a mano:

- **Backend** (`webapp/app.py`): recibe un PDF de ejemplo, lo procesa con
  `ocr_core` y guarda el resultado (texto OCR por página + ruta del PDF)
  en una sesión en memoria identificada por un `session_id`. Expone
  endpoints para: listar/cargar/guardar plantillas (mismo formato que usa
  `remito_extractor.py`), servir la imagen renderizada de cada página,
  probar un campo individual (regex y/o bbox) contra la sesión activa, y
  correr la extracción completa de una plantilla (guardada o un borrador
  en el navegador) para previsualizar el resultado antes de guardar.
- **Frontend** (`webapp/templates/`, `webapp/static/`): HTML/CSS/JS sin
  dependencias externas (sin frameworks, sin CDN). Permite subir el PDF,
  navegar sus páginas, ver el texto OCR, agregar/quitar campos, escribir
  regex y probarlas en vivo, o dibujar con el mouse un rectángulo sobre la
  imagen de la página (se traduce a coordenadas normalizadas para el
  campo `bbox`), y guardar todo con un botón.

Reutiliza directamente `ocr_core` y `remito_extractor` (los importa desde
la raíz del repo) — no duplica ninguna lógica de OCR ni de extracción.

### Etapa 6 — Instalación simplificada

`install.sh`: automatiza la instalación de Tesseract (detecta `apt-get` o
`brew`), crea un entorno virtual de Python en `./venv` e instala
`requirements.txt`.

---

## 3. Estructura de archivos

```
ocr_core.py             Núcleo de OCR compartido (render de páginas PDF, OCR de imagen/región)
ocr_reader.py            CLI de OCR genérico (texto plano de imágenes/PDFs)
remito_extractor.py      CLI de extracción de campos por plantilla de proveedor
providers/               Plantillas de proveedores (una por archivo .json)
  generic.json             Plantilla de respaldo con reglas genéricas
  proveedor_ejemplo.json   Ejemplo de plantilla con regex y campo bbox
  README.md                Esquema de las plantillas
webapp/                  Interfaz gráfica (Flask) para configurar plantillas
  app.py                    Backend: subida de PDF, OCR, guardado/prueba de plantillas
  templates/index.html      Estructura de la página
  static/app.js             Lógica de la interfaz (subida, canvas de bbox, tests, guardado)
  static/style.css          Estilos
install.sh               Script de instalación automática
requirements.txt         Dependencias de Python
README.md                Guía rápida
DOCUMENTACION.md         Este documento
```

---

## 4. Instalación paso a paso

### Requisitos previos

- Python 3.10 o superior.
- Tesseract OCR instalado en el sistema (es un programa nativo, no una
  librería de Python).

### Opción A — instalación automática (recomendada)

```bash
git clone <url-del-repo>
cd Fede
./install.sh
source venv/bin/activate
```

`install.sh` detecta el gestor de paquetes del sistema (`apt-get` en
Linux, `brew` en macOS) e instala Tesseract si hace falta, además de crear
el entorno virtual e instalar las dependencias de Python.

### Opción B — instalación manual

**1. Clonar el repositorio y entrar a la carpeta:**
```bash
git clone <url-del-repo>
cd Fede
```

**2. Instalar Tesseract OCR (dependencia de sistema):**

Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
```

macOS (Homebrew):
```bash
brew install tesseract tesseract-lang
```

Windows: instalador en https://github.com/UB-Mannheim/tesseract/wiki
(tildar el paquete de idioma "Spanish" durante la instalación).

Verificar:
```bash
tesseract --version
```

**3. Crear un entorno virtual de Python (recomendado, no obligatorio):**
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

**4. Instalar las dependencias de Python:**
```bash
pip install -r requirements.txt
```

Con esto queda todo instalado: `pytesseract`, `Pillow`, `pymupdf` y
`Flask`.

---

## 5. Uso

### 5.1. OCR de un archivo o carpeta (`ocr_reader.py`)

```bash
python3 ocr_reader.py remito.pdf -l spa
python3 ocr_reader.py foto.jpg -o resultado.txt
python3 ocr_reader.py ./carpeta_remitos -l spa --output-dir ./textos
python3 ocr_reader.py --list-langs        # idiomas de Tesseract instalados
```

### 5.2. Extracción de campos por línea de comandos (`remito_extractor.py`)

```bash
# detección automática de proveedor, todos los campos de su plantilla
python3 remito_extractor.py remito.pdf

# forzar una plantilla puntual
python3 remito_extractor.py remito.pdf -p proveedor_ejemplo

# extraer solo ciertos campos
python3 remito_extractor.py remito.pdf -f numero_remito,fecha,cliente

# guardar el resultado en JSON
python3 remito_extractor.py remito.pdf -o resultado.json

# explorar plantillas disponibles
python3 remito_extractor.py --list-providers
python3 remito_extractor.py --list-fields -p proveedor_ejemplo
```

Salida:
```json
{
  "archivo": "remito.pdf",
  "proveedor": "proveedor_ejemplo",
  "campos": {
    "numero_remito": "0001-00012345",
    "fecha": "15/03/2026",
    "cliente": "Juan Pérez"
  }
}
```

### 5.3. Interfaz gráfica (`webapp/`)

```bash
python3 webapp/app.py
```
Abrir **http://127.0.0.1:5000**.

Flujo típico para dar de alta un proveedor nuevo:

1. **Subir un PDF de ejemplo** de un remito real de ese proveedor (con
   idioma OCR, por defecto `spa`).
2. Elegir **"-- nueva plantilla --"** o una existente para editarla.
3. Completar **ID** (identificador corto, sin espacios, ej. `acme_sa`),
   **nombre visible** y, opcionalmente, **marcadores de detección
   automática** (regex que identifiquen al proveedor en su texto OCR, ej.
   su razón social o CUIT).
4. Por cada campo: **"+ Agregar campo"**, ponerle un nombre, y elegir:
   - **Regex**: escribir una o más expresiones (una por línea, con un
     grupo de captura) y apretar **"Probar campo"** para ver el valor
     extraído en vivo contra el PDF subido.
   - **Región (bbox)**: apretar **"Dibujar región sobre la imagen"** y
     arrastrar el mouse sobre la zona de la página donde está el dato
     (útil para sellos o numeración impresa que la regex no capta bien).
5. **"Probar extracción completa"** para ver el JSON final con todos los
   campos antes de guardar.
6. **"Guardar plantilla"** → se escribe/actualiza `providers/<id>.json`.

A partir de ahí, ese proveedor queda disponible tanto en la interfaz
gráfica como en `remito_extractor.py` (por `-p <id>` o por detección
automática si sus `match` coinciden con un remito nuevo).

---

## 6. Esquema de las plantillas de proveedor

Ver el detalle completo en [`providers/README.md`](providers/README.md).
En resumen, cada campo admite:

- `regex`: una regex o lista de regex (se prueban en orden). Si tiene un
  grupo `(...)`, se usa ese grupo; si no, el match completo. Opcionalmente
  `page` para restringir la búsqueda a una página puntual.
- `bbox`: `[x0, y0, x1, y1]` normalizado (0.0–1.0) más `page`, para OCR-ear
  solo esa región de la imagen renderizada. Se usa si `regex` no matcheó,
  o como único método si el campo no define `regex`.

---

## 7. Resolución de problemas

- **`ERROR: pymupdf no instalado`** → `pip install -r requirements.txt`
  dentro del entorno virtual activado.
- **Texto OCR vacío o con muchos errores** → probar con `-l spa+eng` o el
  idioma correcto; verificar que el paquete de idioma de Tesseract esté
  instalado (`python3 ocr_reader.py --list-langs`).
- **Un campo da `null`** → la regex no matcheó nada del texto OCR real.
  Correr `python3 ocr_reader.py <pdf> -l spa` para ver el texto crudo y
  ajustar la regex a como quedó (Tesseract puede introducir errores en
  símbolos como "°", tildes o mayúsculas).
- **La región `bbox` da un texto incorrecto** → las coordenadas están mal
  ubicadas o el zoom de renderizado es bajo; volver a dibujar el
  rectángulo desde la interfaz gráfica, que ajusta las coordenadas
  automáticamente al tamaño real de la página.
- **La interfaz web no encuentra la sesión ("Sesión no encontrada")** →
  la sesión vive en memoria del proceso Flask; si se reinició el servidor
  hay que volver a subir el PDF de ejemplo.
