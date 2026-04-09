#!/bin/bash

# Obtener la ruta absoluta del directorio donde está el script
TOOL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
BIN_DIR="$HOME/.local/bin"
VENV_DIR="$TOOL_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_AUTODEV="$VENV_DIR/bin/autodev"

echo "Configurando autodev en: $TOOL_DIR"

# 1. Crear o reparar entorno virtual si no existe o si parece inconsistente
NEED_RECREATE=0
if [ ! -d "$VENV_DIR" ]; then
    NEED_RECREATE=1
elif [ ! -x "$VENV_AUTODEV" ]; then
    NEED_RECREATE=1
elif [ -f "$VENV_DIR/pyvenv.cfg" ] && ! grep -q "$TOOL_DIR" "$VENV_DIR/pyvenv.cfg"; then
    NEED_RECREATE=1
fi

if [ "$NEED_RECREATE" -eq 1 ]; then
    echo "Recreando entorno virtual..."
    rm -rf "$VENV_DIR"
    echo "Creando entorno virtual..."
    python3 -m venv "$VENV_DIR"
fi

# 2. Instalar la herramienta en modo editable dentro del venv
echo "Instalando dependencias..."
"$VENV_PYTHON" -m pip install -q --upgrade pip
"$VENV_PYTHON" -m pip install -q -e "$TOOL_DIR"

# 3. Crear el directorio bin del usuario si no existe
mkdir -p "$BIN_DIR"

# 4. Crear un enlace simbólico al ejecutable generado por setuptools
echo "Creando enlace simbólico en $BIN_DIR/autodev"
if [ ! -x "$VENV_AUTODEV" ]; then
    echo "ERROR: no se generó el ejecutable $VENV_AUTODEV"
    exit 1
fi
ln -sf "$VENV_AUTODEV" "$BIN_DIR/autodev"

# 5. Verificar si el PATH incluye ~/.local/bin
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "⚠️  ATENCIÓN: $BIN_DIR no está en tu PATH."
    echo "Añádelo ejecutando:"
    echo "echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
else
    echo ""
    echo "✅ ¡Listo! Ya puedes usar 'autodev' desde cualquier terminal."
fi
