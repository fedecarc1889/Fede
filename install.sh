#!/usr/bin/env bash
# Instalación automática de OCR Reader / Extractor de remitos.
#
# Instala Tesseract OCR (dependencia de sistema), crea un entorno virtual
# de Python en ./venv e instala las dependencias de requirements.txt.
#
# Uso:
#   ./install.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "== Instalación de OCR Reader / Extractor de remitos =="
echo

# 1. Tesseract OCR (motor de OCR, no es un paquete de Python)
if command -v tesseract >/dev/null 2>&1; then
    echo "OK: tesseract ya está instalado ($(tesseract --version 2>&1 | head -1))"
elif command -v apt-get >/dev/null 2>&1; then
    echo "Instalando tesseract-ocr vía apt-get (puede pedir contraseña de sudo)..."
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
elif command -v brew >/dev/null 2>&1; then
    echo "Instalando tesseract vía Homebrew..."
    brew install tesseract tesseract-lang
else
    echo "No se detectó apt-get ni brew."
    echo "Instalá Tesseract manualmente antes de continuar:"
    echo "  https://github.com/tesseract-ocr/tesseract#installing-tesseract"
    echo "(en Windows: https://github.com/UB-Mannheim/tesseract/wiki)"
    exit 1
fi
echo

# 2. Entorno virtual de Python
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual en ./venv ..."
    python3 -m venv venv
else
    echo "Ya existe ./venv, se reutiliza."
fi

echo "Instalando dependencias de Python..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

echo
echo "== Instalación completa =="
echo
echo "Para usarlo, primero activá el entorno virtual:"
echo "  source venv/bin/activate"
echo
echo "Después:"
echo "  python3 ocr_reader.py remito.pdf -l spa"
echo "  python3 remito_extractor.py remito.pdf"
echo "  python3 webapp/app.py            # interfaz gráfica en http://127.0.0.1:5000"
echo
echo "Ver DOCUMENTACION.md para la guía completa."
