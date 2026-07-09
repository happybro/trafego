@echo off
REM ============================================================
REM  (OPCIONAL) Gera um executavel unico "JV Ads.exe" que roda
REM  sem precisar de Python instalado. Use isto se quiser levar
REM  o programa para outro computador num pen drive.
REM
REM  Rode este arquivo UMA vez; o resultado aparece na pasta
REM  "dist" com o nome "JV Ads.exe".
REM ============================================================
chcp 65001 >nul
title Gerar executavel do JV Ads
cd /d "%~dp0"

set "PY="
py --version >nul 2>nul && set "PY=py"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
    echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo Instalando o PyInstaller...
".venv\Scripts\python.exe" -m pip install pyinstaller

echo Gerando o executavel (pode demorar alguns minutos)...
".venv\Scripts\python.exe" -m PyInstaller --onefile --console ^
    --name "JV Ads" ^
    --collect-all google.ads ^
    --collect-all googleapiclient ^
    executavel.py

echo.
echo Pronto! O executavel esta em: dist\JV Ads.exe
echo Coloque o "JV Ads.exe" na mesma pasta do google-ads.yaml e do config.yaml.
echo.
pause
