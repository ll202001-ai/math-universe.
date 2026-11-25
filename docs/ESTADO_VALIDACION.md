# Estado de validación · MATH UNIVERSE motor 0.3.0

Los 489 tests aprobados son una buena señal, **no una certificación**. Los tres estados:

## 1. Comprobado (ejecutado en el entorno de desarrollo: Linux, Python 3.13.18, NumPy 2.5.3, SciPy 1.18.1)
| Qué | Resultado |
|---|---|
| Suite pytest | 489 aprobadas · 0 falladas · **1 omitida** (`test_08_sympy.py`, no cuenta como aprobada) |
| Oráculo independiente (208 casos) | 200 correctos · 8 no soportados (declarados) · 0 fallos |
| Pruebas aleatorias, 6 semillas (≈1 770 simplificaciones, ≈1 780 derivadas, 1 500 factorizaciones, 1 500 expansiones, 720 integrales) | 0 fallos |
| Verificación independiente del resultado (sustitución exacta, diferencias finitas, Simpson adaptativo, reexpansión) y rechazo de resultados falsos | `test_07`, `test_11` |
| Catálogo de lo no soportado ejecutado (el motor lo declara `unsupported`, no devuelve un resultado) | `test_12` (46) |
| Mecánica del comparador motor↔SymPy (con adaptador falso, incluidas trampas anti-sesgo) | `test_10` (15) |
| Portabilidad estática a Windows (UTF-8, CRLF/ASCII de .bat, sin módulos Unix) | `test_13` |

## 1b. Primera validación en Windows (Python 3.15.2, SymPy 1.14.0) — aportada por el usuario
379 aprobadas · 3 falladas · 1 deseleccionada. Las 3 fallas eran expectativas obsoletas de `test_08` (no matemáticas): ver `HALLAZGOS_WINDOWS_1.md`. **Corregidas aquí, pendientes de re-ejecutar en Windows.**

## 1c. Segunda validación en Windows (fase 5, SymPy real)
391 aprobadas · 1 falla · 1 deseleccionada. La falla era una hipótesis equivocada del comparador (x complejo); la primitiva es correcta (`HALLAZGOS_WINDOWS_2.md`). Se halló además un defecto real: integrales indefinidas sin condiciones de dominio — corregido. **Pendiente de re-ejecutar en Windows.**

## 1d. Comparación real con SymPy (Windows 11, Python 3.15.2)
Primera ejecución del corpus completo: 1 prueba fallada con 6 hallazgos (`simplify(x/x)`, `solve(5=5)`, `differentiate(abs(x))`, `integrate` de `sqrt`, `tan`, `1/x`). Análisis en `HALLAZGOS_WINDOWS_3.md`: **no se encontró ningún error matemático del motor**; sí un sesgo del comparador (comparaba SymPy consigo mismo) y diferencias de dominio/convención. **`integrate(1/x)` sigue ABIERTO** (causa del error del comparador no identificada). Todo lo corregido está pendiente de re-ejecución en Windows.

## 1e. Fase 7 en Windows (434 aprobadas; 2 hallazgos pendientes de revisión)
`(x^3-8)/(x-2)`: el motor conserva `x ≠ 2` (probado con evidencia independiente). `1/(x^3+1)`: primitiva demostrada exactamente; `equals=False` es limitación del comparador, ahora cubierta con una demostración exacta por ramas. Detalle: `HALLAZGOS_WINDOWS_4.md`. **El código SymPy nuevo del comparador está sin ejecutar: pendiente de la corrida en Windows.**

## 2. Pendiente de validación (no se pudo ejecutar aquí)
- Re-ejecución en Windows de `test_08_sympy.py` modificado y de la comparación diferencial completa (`-k corpus_completo`, aún no corrida).
- Comparación **real** motor vs SymPy (165 casos): SymPy no está instalado en el entorno de desarrollo → `test_08_sympy.py` omitida. Hasta correrla no se sabe cuántas diferencias son error / limitación / representación / convención.
- Respaldo SymPy: probado solo con backend simulado.
- mpmath: no probado.
- Flujo de instalación `.bat` y servidor en **Windows real**; Flutter/Android sin tocar.
- Auditoría independiente de terceros (la ejecutará el usuario con el informe de Windows).

## 3. Con limitaciones (declaradas; devuelven `unsupported`, no resultados)
Ver `NO_SOPORTADO.md` (generado y verificado por `test_12`). Resumen: ecuaciones con radicales/abs/exp/ln/trig, cúbicas irreducibles, sistemas no lineales,
integrales de sin², √x, tan, exp(x²), xⁿ, 2ˣ, x^(1/3), impropias; límites con exp/ln/xˣ; factorización multivariante no homogénea; identidades trigonométricas;
racionalización; cifras de constantes trascendentes más allá de ≈15; matrices/determinantes (integrados en 0.4.0; ver INFORME_ENTREGA_FASE10.md).

## Cómo reproducir
`cd engine` → `scripts\instalar_y_probar.bat` (Windows) o `python tools/validar_todo.py --estricto`. El veredicto solo dice **COMPLETA** con 0 fallos, 0 omitidas, SymPy y mpmath instalados y comparación sin hallazgos.
