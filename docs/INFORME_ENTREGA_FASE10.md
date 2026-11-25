# Informe de entrega · fase 10 (motor 0.4.0, contrato 1.1, cliente Flutter, CI)

Fecha: 2026-11-24. Entorno de desarrollo: Linux, Python 3.13.18, NumPy 2.5.3, pytest 9.1.1. **SymPy NO instalado aquí.** Sin Windows, sin Flutter, sin Android SDK, sin red.

## 1. Resumen en tres estados
| Comprobado (ejecutado aquí) | Pendiente de ejecución (depende de Windows/Flutter/Android/SymPy) | Limitaciones |
|---|---|---|
| Motor 0.4.0: 822 pruebas aprobadas, 0 falladas, 1 omitida (`test_08_sympy`: SymPy no instalado) | Compilar y ejecutar el cliente Flutter (`flutter analyze`, `flutter test`) | Matrices: solo entradas racionales exactas, hasta 40×40; sin autovalores |
| Fase 8 conservada: ningún archivo cambió salvo 5 declarados (prueba `test_20`) | Pruebas con SymPy real y código nuevo del comparador (se ejecutan en GitHub Actions en Windows y Linux) | Android: sin `jsonschema` (validación estructural mínima de respuestas); versión inicial |
| Matrices integradas en el dispatcher; 9 operaciones + `determinant`; 15 archivos golden; respuesta validada contra el esquema | Compilar Windows (`flutter build windows`), instalador Inno Setup, Python embebido | Instalador sin firma digital (Windows mostrará aviso SmartScreen) |
| H-1 corregido con prueba de regresión | Compilar APK con Chaquopy (el parche Gradle se probó solo sobre plantillas sintéticas) | Rendimiento y tamaño de la app no medidos |
| Parche de Android sobre plantillas Kotlin DSL y Groovy; puente Android probado sin jsonschema ni NumPy | Prueba real cliente Dart ↔ motor (`engine_integration_test.dart`) | Interfaz sin pruebas de usabilidad; sin gráficas, sin ingeniería eléctrica |

**Nada del código Dart/Kotlin se ha compilado ni ejecutado.** Solo se comprobó el balance de paréntesis/llaves. Es probable que la primera compilación en GitHub dé algún error de sintaxis o de versión de paquete; se corrige en la siguiente entrega.

## 2. Cambios en el motor (fase 8 → 0.4.0) y por qué
| Archivo | Cambio | Motivo |
|---|---|---|
| `math_universe_engine/__init__.py` | versión 0.3.0 → 0.4.0 | nueva versión |
| `math_universe_engine/dispatcher.py` | API 1.1; `op_matrix`; registro de `matrix_*` y `determinant`; capacidades | integrar matrices (módulo 9B reutilizado sin reescribir) |
| `math_universe_engine/parser.py` | cota de exponente decimal (|e| ≤ 1000) | **H-1**: `1e999999999` colgaba el proceso e ignoraba `timeout_ms`; `1e100000` daba `internal_error`. Ahora `invalid_input`/`LIMIT_EXCEEDED` al instante |
| `schema/request.schema.json` | operaciones `matrix_*`; `structured_input` con `a`/`b` | contrato 1.1 (aditivo) |
| `audit/no_soportado.py` | se quita `determinant` del catálogo de no soportados | ya está soportado (el catálogo y su documento se regeneraron) |
| `math_universe_linalg/` (nuevo) | módulo 9B + función `compute()` | reutilizado: solo se añadió `compute` (sin plazo propio) para que lo use el dispatcher |
Todo lo demás de la fase 8 es **idéntico byte a byte** (comprobado por `tests/test_20_conservacion_fase8.py` contra el manifiesto de la fase 8 archivado en `versiones_anteriores/`).

## 3. Pruebas ejecutadas aquí
| Grupo | Resultado |
|---|---|
| Fase 8 (14 archivos) | 489 aprobadas (488 + 1 omitida por SymPy); se retiró la expectativa «`determinant` no soportado» porque dejó de ser verdad |
| Álgebra lineal 9B (13 archivos, `tests/linalg`) | 274 aprobadas |
| Conservación de la fase 8 (`test_20`) | 3 aprobadas (archivos intactos salvo los declarados; ZIP anteriores con hash original) |
| Integración de matrices (`test_21`) | 49 aprobadas: valores conocidos a mano, alias, esquema de respuesta, golden, errores, plazo, verificación saboteada, H-1, servidor JSON Lines por subproceso, contra NumPy |
| Android/CI (`test_22`) | 8 aprobadas: parche Gradle (Kotlin DSL y Groovy, idempotente), puente sin jsonschema, coherencia de workflows |
| **Total** | **822 aprobadas · 0 falladas · 1 omitida** (detalle por archivo en `INFORME_PRUEBAS_ENTORNO_DESARROLLO.md`) |
No ejecutado aquí: comparación con SymPy (no instalado), cualquier prueba de Windows, Flutter, Android.

## 4. Qué verificará GitHub por nosotros (primera compilación)
Windows: pruebas del motor con SymPy+NumPy reales → `flutter analyze` → `flutter test` (incluye prueba real Dart↔motor) → compilación → Python embebido + motor + prueba del motor empaquetado (5 solicitudes) → instalador. Android: pruebas del motor → Flutter → parche Chaquopy → APK. Cualquier fallo detiene el trabajo en rojo (no hay `continue-on-error`).

## 5. Riesgos conocidos de la primera compilación
1. Errores de compilación Dart o incompatibilidad de versiones de `sqflite_common_ffi`/`sqlite3_flutter_libs` con el Flutter más reciente.
2. Chaquopy 16.0.0 con la versión de Gradle/AGP que genere el Flutter actual.
3. El Flutter de Windows necesita el runtime de Visual C++ (normalmente ya instalado en Windows 10/11).
4. En la comparación con SymPy siguen abiertos (de la fase 8): `integrate(1/x)` → `ERROR_COMPARADOR` sin causa identificada y el código nuevo del comparador sin ejecutar en Windows. Los resultados saldrán en el registro de Actions.

## 6. Próximo paso
Con el registro de la primera compilación corrijo lo que falle y entrego el ZIP siguiente. Después: pulido de la interfaz, historial/exportación, firma del instalador, y autovalores.
