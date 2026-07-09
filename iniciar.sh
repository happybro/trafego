#!/usr/bin/env bash
# ============================================================
#  JV Ads - execute este arquivo para abrir o programa
#  (no terminal: ./iniciar.sh   ou   bash iniciar.sh).
#  Na primeira vez ele prepara tudo sozinho.
# ============================================================
set -e
cd "$(dirname "$0")"

# --- Encontra o Python ---
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "[ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/"
    exit 1
fi

# --- Prepara o ambiente na primeira execucao ---
if [ ! -x ".venv/bin/python" ]; then
    echo "Preparando o JV Ads pela primeira vez. Aguarde..."
    "$PY" -m venv .venv
    ".venv/bin/python" -m pip install --upgrade pip
    ".venv/bin/python" -m pip install -r requirements.txt
fi

# --- Abre o programa ---
exec ".venv/bin/python" -m jv_ads
