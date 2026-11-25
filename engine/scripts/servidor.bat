@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."
call ".venv\Scripts\activate.bat"
REM Lee una solicitud JSON por linea de la entrada estandar y escribe una respuesta por linea.
python -I run_server.py
