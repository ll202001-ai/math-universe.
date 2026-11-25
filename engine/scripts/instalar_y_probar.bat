@echo off
setlocal
REM ============================================================
REM MATH UNIVERSE - validacion completa en Windows 10/11 (64 bits)
REM Ejecutar con doble clic o desde CMD/PowerShell. Requiere Python 3.11+ (python.org) e Internet para pip (solo la primera vez).
REM ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0.."

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro el lanzador "py". Instale Python 3.11 o superior desde https://www.python.org/downloads/ y marque "Add python.exe to PATH".
  exit /b 1
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo [ERROR] Se requiere Python 3.11 o superior. Version encontrada:
  py -3 --version
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creando entorno virtual .venv ...
  py -3 -m venv .venv
  if errorlevel 1 goto :fallo
)
call ".venv\Scripts\activate.bat"

echo [2/4] Instalando dependencias (sympy, mpmath, numpy, scipy, jsonschema, pytest) ...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip no pudo instalar las dependencias. Compruebe la conexion a Internet o use un cache local: ver docs\WINDOWS.md
  exit /b 1
)
python -m pip freeze > requirements-lock.txt

echo [3/4] Versiones instaladas:
python -c "import sys,sympy,mpmath,numpy,scipy; print('Python',sys.version.split()[0]); print('SymPy',sympy.__version__); print('mpmath',mpmath.__version__); print('NumPy',numpy.__version__); print('SciPy',scipy.__version__)"
if errorlevel 1 goto :fallo

echo [4/4] Ejecutando TODAS las pruebas (incluye tests\test_08_sympy.py) y la comparacion con SymPy ...
python tools\validar_todo.py --estricto
set RC=%ERRORLEVEL%
echo.
echo Diagnostico del comparador (evidencia reproducible): validacion\diagnostico_comparador.txt
python tools\diagnosticar_comparador.py > nul 2>&1
echo.
echo Informe: %CD%\INFORME_VALIDACION.md
echo Datos:   %CD%\validacion\resultados.json  y  %CD%\validacion\entorno.json
if "%RC%"=="0" (echo RESULTADO: VALIDACION COMPLETA) else (echo RESULTADO: INCOMPLETA O CON HALLAZGOS - lea el informe y envielo)
exit /b %RC%

:fallo
echo [ERROR] Fallo la preparacion del entorno.
exit /b 1
