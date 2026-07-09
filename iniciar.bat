@echo off
REM ============================================================
REM  JV Ads - clique duas vezes neste arquivo para abrir.
REM  Na primeira vez ele prepara tudo sozinho (pode demorar
REM  alguns minutos). Nas proximas, abre na hora.
REM ============================================================
chcp 65001 >nul
title JV Ads
cd /d "%~dp0"

REM --- Encontra o Python instalado (py ou python) ---
set "PY="
py --version >nul 2>nul && set "PY=py"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
    echo.
    echo [ERRO] Python nao encontrado.
    echo Instale em https://www.python.org/downloads/
    echo e marque a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

REM --- Prepara o ambiente na primeira execucao ---
if not exist ".venv\Scripts\python.exe" (
    echo Preparando o JV Ads pela primeira vez. Aguarde...
    %PY% -m venv .venv || goto :erro
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :erro
)

REM --- Abre o programa ---
".venv\Scripts\python.exe" -m jv_ads
echo.
pause
exit /b 0

:erro
echo.
echo [ERRO] Nao foi possivel preparar o JV Ads. Verifique sua conexao com a internet.
echo.
pause
exit /b 1
