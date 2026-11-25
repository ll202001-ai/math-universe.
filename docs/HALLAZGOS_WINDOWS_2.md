# Hallazgos de la 2.ª validación en Windows (fase 5; SymPy real)

**Resultado original conservado (reportado por el usuario):** 391 aprobadas · **1 fallada** · 1 deseleccionada · 142.78 s.
Fallo: `tests/test_08_sympy.py::test_integral_propia_de_1_sobre_x3_mas_1_coincide_con_sympy` — «la derivada de la primitiva propia no coincide con 1/(x^3+1); SymPy devuelve Piecewise con re(x), im(x) y Abs(x+1)».
(Los 3 fallos de la ronda anterior quedaron resueltos: 379→391 aprobadas.)

## Las cinco preguntas
| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿x debe declararse real? | **Sí.** `sympy.Symbol("x")` es *complejo*. La primitiva contiene `ln|x+1|`; para x complejo SymPy deriva `Abs` con `re/im` (`Abs'(z)` no es analítica) y devuelve expresiones `Piecewise` que `simplify` no reduce. Era una hipótesis equivocada **de la prueba que escribí yo**, no un problema de la primitiva. |
| 2 | ¿La derivada coincide con 1/(x³+1) en los reales, x ≠ −1? | **Sí**, comprobado sin SymPy: derivada numérica central de la primitiva del motor vs `1/(x³+1)` en x = −100, −50, −5, −2, −1.5, −0.5, 0, 0.3, 1, 4, 100 (error < 1e-9, salvo redondeo de la diferencia finita). `test_14`. Se verificó también por la derivación a mano: d/dx ln\|x+1\| = 1/(x+1) en **ambos** lados de −1. |
| 3 | ¿Se puede demostrar simbólicamente bajo las hipótesis correctas? | Con x real y **por ramas**: en x>−1, \|x+1\|=x+1; en x<−1, \|x+1\|=−(x+1); en cada rama `simplify(F' − 1/(x³+1)) == 0`. Está en la prueba corregida. *Esta demostración no la pude ejecutar aquí (sin SymPy): queda para Windows.* |
| 4 | ¿Confirma la comparación numérica independiente en (−∞,−1) y (−1,∞)? | Sí (ver 2). La prueba de SymPy añade evaluación a 30 dígitos en ambos intervalos y cerca de la singularidad (−1.001, −0.999), sin pasar por `simplify`. |
| 5 | ¿Error real en la primitiva o hipótesis del comparador? | **La primitiva es correcta.** El fallo era de hipótesis del comparador. |

## Defecto real encontrado al investigar (distinto del fallo)
Las integrales **indefinidas no informaban el dominio**: `∫1/(x^3+1)` devolvía `conditions: []` (y lo mismo `∫1/x`, `∫ln(x)`), mientras `differentiate` sí daba `x ≠ 0`. La primitiva solo vale en cada intervalo donde el integrando es continuo, y la prueba debía haber exigido `x ≠ -1`.
Clasificación: **error de omisión de dominio** (no de cálculo). Corregido en `op_integrate` (condiciones del integrando). Ahora: `1/(x^3+1)` → `x ≠ -1`, `x² − x + 1 ≠ 0`; `1/x` → `x ≠ 0`; `ln(x)` → `x > 0`; `x²`, `sin x`, `exp x` → sin condiciones.
Límite conocido: sigue sin avisarse que la constante `C` puede ser distinta en cada intervalo (p. ej. a ambos lados de x = −1).

## Cambios
- Prueba corregida (no eliminada, no rebajada): x real, demostración por ramas, comprobación numérica a 30 dígitos en ambos intervalos, comparación con SymPy salvo constante en x>−1.
- Regresiones sin SymPy en `test_14_hallazgos_windows.py`: derivada de la primitiva en 11 puntos de ambos intervalos; condiciones de dominio en integrales; ausencia de condiciones inventadas.
