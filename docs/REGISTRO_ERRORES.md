# Registro de errores corregidos

| # | Defecto | Cómo se detectó | Corrección | Prueba que lo cubre |
|---|---|---|---|---|
| 1 | `2..3` se interpretaba **en silencio** como 0.6 (multiplicación implícita entre dos números) | Prueba de sintaxis inválida | El parser rechaza dos números seguidos sin operador | `test_sintaxis_invalida[2..3]` |
| 2 | La factorización perdía la constante principal: `6x²+5x+1` → `(1/6)(2x+1)(3x+1)` | **La propia verificación independiente** lo marcó `failed` y bloqueó el resultado | Se conserva la constante residual tras extraer factores lineales | `test_factor[6x^2+5x+1…]`, `test_un_resultado_que_falla…` |
| 3 | Funciones como `floor`/`ceil` se convertían en átomos y la segunda vía las marcaba `failed` (falso fallo) | Pruebas exactas | Funciones no soportadas simbólicamente lanzan `NOT_IMPLEMENTED`; la verificación pasa a `not_possible` | `test_exact[floor…]`, `test_nunca_se_marca_passed…` |
| 4 | `sqrt(3)*sqrt(3)` y `(sqrt(2))^2` no se reducían a enteros | Pruebas exactas | Reducción `sqrt(d)^k` en la cancelación | `test_exact[(sqrt(2))^2-2]`, `[sqrt(12)*sqrt(3)-6]` |
| 5 | `assumptions`, `precision` y `timeout_ms` se aceptaban pero **no se aplicaban** | Revisión contra el pedido | Aplicados (soluciones, simplificación, decimales, plazo cooperativo y proceso hijo) | tests 03, 05, 06 |
| 6 | Pérdida de restricciones: `(x²−1)/(x−1)` devolvía `x+1` sin `x≠1` | Requisito obligatorio | Condiciones recogidas del árbol original (denominadores, potencias negativas, ln, sqrt, tan) | test 03 completo |
| 7 | Aviso espurio «precision > 15» con la precisión por defecto | Pruebas de aproximación | Solo se avisa si el usuario pidió la precisión | `test_irracionales_se_mantienen…` |
| 8 | Representación `(-1/2)*sqrt(3)*i` para números complejos | Revisión de salida | Formato con signo correcto | `test_supuestos_en_soluciones` |
| 9 | Línea sin sentido en `Poly.__mul__` (comprobación de tamaño) | Revisión de código | Eliminada; el tope se aplica sobre el resultado | `test_limite_de_terminos` |
| 10 | Inversión de series con precisión sin acotar (O(n²) con n=4096) | Prueba de rendimiento de límites | Precisión relativa acotada por el orden pedido | `test_limites` |
| 11 | Fase anterior: respuestas con `status: "error"` fuera del contrato | Adaptación al PDF | Estados del PDF + validación del esquema de respuesta | `conftest.call` valida cada respuesta |
| 12 | Raíces «extrañas» (`x=1` en `(x²−1)/(x−1)=0`) no se informaban | Pruebas de dominio | Advertencia explícita de raíz excluida | `test_ecuacion_raiz_extrana_excluida` |

Límites todavía conocidos: ver `FUNCIONES.md` (sección Pendiente).

## Etapa de validación (motor 0.3.0): errores hallados por la auditoría independiente
Detalle y clasificación (error / limitación / representación / convención) en `AUDITORIA.md`. Cada uno tiene prueba de regresión en `engine/tests/test_09_auditoria.py` (o la indicada).

| # | Defecto | Corrección | Prueba |
|---|---|---|---|
| 13 | `ln(0)`, `tan(pi/2)`, `asin(2)`, `1/(sqrt(2)-sqrt(2))` devolvían éxito con condición incumplida | Condiciones constantes se evalúan: violadas → `domain_error`; verdaderas → se omiten | `test_dominio_constante_violado_es_domain_error` |
| 14 | Trigonometría exacta ausente (`sin(pi)`, `cos(pi/3)`…) | Tabla exacta para múltiplos de π/6 y π/4 | `test_trig_exacta` |
| 15 | `3!!` se evaluaba como `(3!)!` sin avisar | Error de sintaxis explicativo | `test_doble_factorial_ambiguo_rechazado` |
| 16 | Factorización multivariante ausente (`x^2-y^2`) | Deshomogeneización para polinomios homogéneos de 2 variables | `test_factor_homogeneo` |
| 17 | `5=5` / `5=6` → `invalid_input` | `Verdadero`/`Falso` exacto; `1/0=1` → `domain_error` | `test_ecuacion_sin_incognita` |
| 18 | Falso fallo de verificación con funciones de magnitud enorme | Cota del redondeo del esquema de diferencias | pruebas aleatorias (semilla 1), `test_07` sigue detectando derivadas falsas |
| 19 | Falso fallo de verificación de integrales con picos | Simpson adaptativo | `test_integral_con_pico_estrecho_se_verifica` |
| 20 | Integral impropia / integrando indefinido mal clasificados | `unsupported` vs `domain_error` | `test_integral_impropia_no_se_inventa`, `test_integrando_indefinido_en_el_intervalo_es_domain_error` |
| 21 | Canal JSON fallaba con consola cp1252 (Windows) | UTF-8 forzado | `test_servidor_utf8_aunque_la_consola_sea_cp1252` |
| 22 | Resultados de pruebas dependían de si SymPy estaba instalado | `MATH_UNIVERSE_DISABLE_SYMPY` | `test_interruptor_de_entorno` |
| 23 | Resultados de SymPy sin verificación independiente | Misma verificación (derivada numérica, primitiva) | `test_11_respaldo_simulado.py` |
| 24 | Versión inconsistente (0.1.0 vs 0.2.0) | Única fuente 0.3.0 | — |
| 25 | `1/2/sqrt(x)` y `(x)^(x)` ambiguos/feos | Impresión `1/(2*sqrt(x))`, `x^x` | `test_impresion_derivadas` |
| 26 | `(-8)^(1/3)` sin evaluar con condición falsa | Raíz real de índice impar (convención documentada) | `test_raiz_real_de_negativo_impar` |

## Fase de validación (motor 0.3.0, ronda final)
- **E-27 `∫x^n dx` → `x*x^n + C` (falso).** Introducido por mí al cambiar la impresión de átomos; detectado por el verificador antes de salir. Corregido (ahora `unsupported`) + prueba de regresión.
- **E-28 `(x^a)^2` → `x^a^2`.** Ambigüedad de impresión; corregida con paréntesis de átomos de potencia.
- **E-29 Falso fallo del verificador cerca de singularidades** (`sin(2^a/(a-x))`). Corregido con consistencia h / h/2.
- **E-30 Oráculo contaba «no soportado» como correcto** (208/208). Corregido: 200 correctos, 8 no soportados, 0 fallos.
- **E-31 Catálogo de no soportados con una entrada errónea** (`floor(7/2)` bajo «simplify»; es `evaluate`, éxito con verificación `not_possible`). Corregido y ahora el catálogo se **ejecuta** en `test_12`.
- **E-32 Mi creencia de que `x^7+x+1` era reducible era falsa**; el motor acertó (irreducible sobre Q).

## Validación en Windows nº1 (SymPy 1.14.0, Python 3.15.2)
- **W-1, W-2** Expectativas de `test_backend_sympy` desactualizadas (`**` vs `^`): defecto de la prueba, sin diferencia matemática. Endurecidas con equivalencia contra SymPy puro.
- **W-3** `1/(x^3+1)`: el motor propio sí integra; la prueba esperaba el respaldo. Defecto de la prueba. Ahora se verifica que el respaldo NO se use y que el resultado coincida con SymPy y `scipy.quad`.
- Detalle y resultado original: `HALLAZGOS_WINDOWS_1.md`. Lección: un módulo omitido no se puede dar por bueno; mis cambios previos de `from_sympy_text` dejaron una prueba rota que solo Windows pudo revelar.

## Validación en Windows nº2 (fase 5, SymPy real)
- **W-4** `test_integral_propia_de_1_sobre_x3_mas_1_coincide_con_sympy`: hipótesis equivocada del comparador (x complejo con `ln|x+1|`). Primitiva correcta. Prueba reescrita (real, por ramas, numérica a 30 dígitos).
- **E-33 (real, del motor)** `integrate` indefinido no devolvía condiciones de dominio (`1/x`, `1/(x^3+1)`, `ln x`). Corregido + pruebas. Hallado al investigar W-4.
- Detalle y resultado original: `HALLAZGOS_WINDOWS_2.md`.

## Validación en Windows nº3 (comparación real con SymPy)
- **W-5 (sesgo del comparador)** El motor se ejecutaba con el respaldo SymPy activo: «motor vs SymPy» podía ser SymPy vs SymPy. Corregido (`_motor` desactiva el respaldo).
- **W-6** `simplify(x/x)`: SymPy pierde `x≠0` al construir la expresión; motor correcto → veredicto `SYMPY_AMPLIA_DOMINIO` con evidencia independiente (función original indefinida).
- **W-7** `solve(5=5)`: proposición vs conjunto solución (convención documentada); además el informe imprimía `SymPy None` (defecto del informe).
- **W-8** `differentiate(abs(x))`: `x/|x|` vs `sign(x)`: iguales en x≠0; |x| no es derivable en 0. Motor correcto. Mejora: condición `x ≠ 0` en vez de `abs(x) ≠ 0`.
- **W-9** `integrate(sqrt x / tan x)`: efecto de W-5. `integrate(1/x)`: **causa no identificada, ABIERTO**; diagnóstico reforzado.
- Detalle y resultado original: `HALLAZGOS_WINDOWS_3.md`.

## Hallazgos pendientes de la fase 7 (informe de Windows, 434 aprobadas)
- **W-10** `(x^3-8)/(x-2)`: el motor conserva `x ≠ 2` (60 casos independientes); el «pendiente» era una diferencia de dominio real con SymPy (singularidad evitable), clasificada `SYMPY_AMPLIA_DOMINIO` por diseño; se añade el límite como evidencia.
- **E-34 (menor, real)** `expand((x^3-8)/(x-2)-(x^2+2x+4))` imprimía `0/(x - 2)`; ahora `0`.
- **W-11** `1/(x^3+1)`: primitiva correcta (demostración exacta con racionales); `equals=False` es limitación del comparador (heurístico con `sign/Abs`, causa exacta por confirmar con `diagnostico_comparador.txt`). Corregido: demostración exacta por ramas, registrada y con pruebas negativas.
- Detalle: `HALLAZGOS_WINDOWS_4.md`.

## Fase 10 (motor 0.4.0)
| ID | Hallazgo | Causa | Corrección | Prueba de regresión |
|---|---|---|---|---|
| H-1 | `evaluate "1e999999999"` colgaba el proceso e ignoraba `timeout_ms`; `1e100000` → `internal_error` | El parser aceptaba exponentes decimales sin cota y calculaba `10**exp` antes de cualquier límite | `parser._to_fraction`: exponente |e| ≤ 1000 (`MAX_EXP10`), si no `LIMIT_EXCEEDED` | `test_21_integracion_matrices.py::test_h1_*` |
| F10-1 | Pruebas de aislamiento 9A recorrían `.venv` (falsos positivos en Windows) | Alcance demasiado amplio | Ya corregido en 9B; en esta fase `tests/linalg` usa `recorrer()` que excluye entornos virtuales | `test_31_windows_lint.py::test_el_alcance_excluye_entornos_virtuales` |
