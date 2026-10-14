@echo off
setlocal
cd /d "%~dp0"
title WebSnapshot

set "PYTHON=%~dp0.venv313\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [FEHLER] Python-Umgebung .venv313 nicht gefunden.
  echo Bitte im Projektordner einmalig ausfuehren:
  echo   py -3.13 -m venv .venv313
  echo   .venv313\Scripts\python.exe -m pip install -e ".[dev]"
  pause
  exit /b 1
)

"%PYTHON%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
  echo [FEHLER] Streamlit ist in .venv313 nicht installiert.
  echo Bitte einmalig ausfuehren:
  echo   .venv313\Scripts\python.exe -m pip install -e ".[dev]"
  pause
  exit /b 1
)

echo Starte WebSnapshot unter http://localhost:8501
echo Zum Beenden dieses Fenster schliessen oder Strg+C druecken.
"%PYTHON%" -m streamlit run "src\websnapshot\app.py" --server.address 127.0.0.1
if errorlevel 1 (
  echo.
  echo [FEHLER] WebSnapshot konnte nicht gestartet werden.
  pause
  exit /b 1
)
endlocal
