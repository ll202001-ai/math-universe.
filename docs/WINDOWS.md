# Validación y ejecución en Windows 10/11 (64 bits)

## 1. Requisitos
- Python **3.11 o superior** desde https://www.python.org/downloads/ (marque «Add python.exe to PATH» y deje el lanzador `py`).
- Internet **solo la primera vez** (para `pip`).

## 2. Un solo paso (recomendado)
1. Descomprima `math_universe_fase3.zip` (por ejemplo en `C:\MathUniverse`).
2. Abra **CMD** o **PowerShell** y ejecute:
```
cd C:\MathUniverse\math_universe\engine
scripts\instalar_y_probar.bat
```
El script: crea `.venv` · instala `sympy mpmath numpy scipy jsonschema pytest` · muestra las versiones · guarda `requirements-lock.txt` ·
ejecuta **todas** las pruebas (incluye `tests\test_08_sympy.py`), las pruebas aleatorias, el oráculo independiente y la comparación motor vs SymPy.

Salidas (en `engine\`):
| Archivo | Contenido |
|---|---|
| `INFORME_VALIDACION.md` | Veredicto, versiones, aprobadas/falladas/**omitidas**, aleatorias, oráculo, comparación con SymPy |
| `validacion\entorno.json` | Versiones de Python, SO, SymPy, mpmath, NumPy, SciPy, jsonschema, pytest |
| `validacion\resultados.json` | Todos los datos del informe |
| `validacion\comparacion_sympy.json` | Cada caso: veredicto, detalle, estado y verificación del motor |

El código de salida es 0 solo si la validación es **completa y sin hallazgos**. «Omitida» nunca cuenta como aprobada.

## 3. Comandos manuales (equivalentes)
```
cd engine
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip freeze > requirements-lock.txt
python tools\validar_todo.py --estricto        :: validación completa + informe
python -m pytest tests -v                      :: solo las pruebas (o scripts\ejecutar_pruebas.bat)
python -m pytest tests\test_08_sympy.py -v     :: solo el módulo SymPy
python audit\comparar_sympy.py                 :: solo la comparación motor vs SymPy
```
PowerShell: si bloquea `activate`, use `Set-ExecutionPolicy -Scope Process Bypass` o ejecute `.venv\Scripts\python.exe` directamente.

## 4. Usar el motor
```
python -m math_universe_engine.cli simplify "(x^2-1)/(x-1)"
python -m math_universe_engine.cli solve "2x+y=5; x-y=1"
python -m math_universe_engine.cli solve "V=I*R" --var R
python -m math_universe_engine.cli limit "sin(x)/x" --point 0
python -m math_universe_engine.cli integrate "x^2" --lower 0 --upper 3 --precision 10
python -m math_universe_engine.cli solve "x^2-2=0" --precision 40
```
Canal JSON Lines (el que usará Flutter): `scripts\servidor.bat`, o
```
echo {"request_id":1,"operation":"simplify","expression":"(x^2-1)/(x-1)"} | python -I run_server.py
```
Para ejecutar el motor **solo con el motor propio** (sin respaldo SymPy): `set MATH_UNIVERSE_DISABLE_SYMPY=1`.

## 5. Si algo falla
- **Sin Internet / pip falla**: en otro equipo `pip download -r requirements.txt -d wheels`; aquí `pip install --no-index --find-links wheels -r requirements.txt`.
- **«Omitidas» > 0**: SymPy/mpmath no se instalaron en el entorno activo (revise `validacion\entorno.json`).
- **Una prueba de `test_08_sympy.py` falla**: es información real (estas pruebas no se pudieron ejecutar donde se escribió el código). Envíe `INFORME_VALIDACION.md` y `validacion\comparacion_sympy.json`; cada diferencia se clasifica como error, limitación, representación o convención.
- Caracteres raros en la consola: el script usa `chcp 65001`; el canal JSON siempre es UTF-8.

## 6. Reproducibilidad (qué se garantiza y qué no)
- `requirements.txt` fija **rangos**, no versiones exactas; el instalador genera `requirements-lock.txt` (`pip freeze`) con lo realmente instalado y `validacion\entorno.json`. Reproducir exactamente = reinstalar desde ese lock.
- El flujo del `.bat` (venv → pip → versiones → `tools\validar_todo.py --estricto`) **no se ha ejecutado en Windows**. Lo comprobado aquí es lo estático: `.bat` ASCII/CRLF, UTF-8 explícito en todo `open`, sin módulos solo-Unix (`test_13_windows_lint.py`), y el canal UTF-8 con consola cp1252 simulada.
- `validar_todo` tarda ≈2 min sin SymPy; con la comparación real contra SymPy espere ≈5–10 min.
- Integridad del paquete: `python tools\verificar_paquete.py` compara con `MANIFIESTO_SHA256.txt` (ejecutar desde `engine\`).
