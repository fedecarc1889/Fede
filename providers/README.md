# Plantillas de proveedores

Cada archivo `.json` en este directorio es una plantilla que le dice a
`remito_extractor.py` qué campos extraer de los remitos de un proveedor
determinado, y cómo reconocer automáticamente ese proveedor a partir del
texto OCR.

El nombre del archivo (sin `.json`) es el **ID del proveedor**, usado con
`--provider <id>` y mostrado por `--list-providers`.

## Esquema

```json
{
  "label": "Nombre legible del proveedor",
  "match": ["REGEX_1", "REGEX_2"],
  "fields": {
    "nombre_del_campo": {
      "regex": ["REGEX con un grupo de captura", "REGEX alternativa"],
      "page": 0,
      "bbox": [0.75, 0.03, 0.98, 0.10]
    }
  }
}
```

- **`label`**: nombre descriptivo, se muestra en `--list-providers`.
- **`match`**: lista de expresiones regulares (case-insensitive). Si alguna
  aparece en el texto OCR del remito, la plantilla suma puntos para la
  detección automática de proveedor. La plantilla con más coincidencias
  gana. Dejar `[]` en plantillas que solo se usarán con `--provider`
  explícito (como `generic.json`, el fallback).
- **`fields`**: diccionario de `nombre_de_campo -> definición`. Cada campo
  soporta dos métodos de extracción, evaluados en este orden:
  - **`regex`** (recomendado, por defecto): una regex o lista de regex
    (se prueban en orden, se usa la primera que matchee) aplicadas sobre
    el texto OCR completo. Si tiene un grupo de captura `(...)`, se usa
    ese grupo como valor; si no, se usa el match completo.
    - **`page`** (opcional): índice de página (0 = primera) para limitar
      la búsqueda a esa página en vez de todo el documento.
  - **`bbox`**: `[x0, y0, x1, y1]`, coordenadas normalizadas (0.0 a 1.0,
    origen arriba-izquierda) de una región fija de la página. Se recorta
    esa región de la imagen renderizada y se corre OCR solo ahí. Útil para
    campos en una posición fija del formulario (sellos, numeración
    pre-impresa, recuadros) donde una regex sobre el texto completo no es
    confiable. Requiere `page` (por defecto 0).
    Se usa como respaldo si `regex` no encuentra nada, o como único método
    si el campo no define `regex`.

## Agregar un nuevo proveedor

1. Copiá `proveedor_ejemplo.json` con un nuevo nombre, por ejemplo
   `acme_sa.json` (el nombre del archivo será el ID `acme_sa`).
2. Corré el OCR completo del remito para ver el texto crudo:
   ```
   python3 ocr_reader.py remito_acme.pdf -l spa
   ```
3. Ajustá `match` con alguna frase o CUIT que identifique inequívocamente
   a ese proveedor en el texto OCR.
4. Definí los `fields` que te interesan, con regex basadas en las
   etiquetas reales que aparecen en el texto (ej. "Nº Remito", "Fecha",
   "Sr(es)").
5. Probá con:
   ```
   python3 remito_extractor.py remito_acme.pdf --provider acme_sa
   ```

Los archivos cuyo nombre empieza con `_` no se cargan automáticamente
(útil para plantillas en borrador).
