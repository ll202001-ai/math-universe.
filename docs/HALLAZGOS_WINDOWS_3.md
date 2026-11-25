# Hallazgos de la 3.ª validación en Windows (comparación real motor ↔ SymPy)

**Resultado original conservado (reportado por el usuario):** Windows 11, Python 3.15.2, SymPy real. `test_comparacion_motor_vs_sympy_corpus_completo`:
**1 fallada** (la prueba exige 0 hallazgos) · 20 deseleccionadas · 326.79 s. Hallazgos del comparador:

| # | Caso | Veredicto original |
|---|---|---|
| 1 | `simplify(x/x)` | DIFERENCIA_DOMINIO (motor y SymPy dan `1`) |
| 2 | `solve(5=5)` | DIFERENCIA (motor `success_exact Verdadero`; SymPy `None`) |
| 3 | `differentiate(abs(x))` | DIFERENCIA (motor `x/abs(x)`; SymPy `sign(x)`; coinciden en 16 puntos, simbólico no confirmado) |
| 4 | `integrate(sqrt(x))`, `integrate(tan(x))`, `integrate(1/x)` | ERROR_COMPARADOR (excepciones al evaluar condiciones relacionales) |

Esta ronda **no tocó ninguna expectativa para que pasara**: el comparador sigue marcando como hallazgo toda discrepancia que no esté probada de forma independiente.

## 0. Sesgo del comparador descubierto al investigar (el más importante)
`test_08` quita `MATH_UNIVERSE_DISABLE_SYMPY` (para probar el respaldo). El comparador llamaba a `handle()` **con el respaldo SymPy activo**: cuando el motor propio no podía (`sqrt(x)`, `tan(x)`…), la «respuesta del motor» era **la de SymPy** y se comparaba **SymPy contra SymPy**. Eso no valida nada y además infla el acuerdo.
**Corrección:** `_motor()` fuerza `MATH_UNIVERSE_DISABLE_SYMPY=1` mientras compara (y restaura el entorno). Lo que el motor propio no resuelve queda como `LIMITACION_MOTOR`, que es lo que es. El respaldo se prueba aparte (`test_11`, `test_08`). Prueba: `test_el_motor_se_ejecuta_sin_respaldo_sympy_en_la_comparacion`.

## 1. `simplify(x/x)` — DIFERENCIA_DOMINIO
- **Matemática:** `x/x = 1` solo para `x ≠ 0`; en `x = 0` la expresión original no existe. El motor devuelve `1` con `x ≠ 0`: **correcto**.
- **Causa:** SymPy reduce `x/x → 1` *al construir la expresión* (autoevaluación), así que `singularities()` la ve como la constante 1 y reporta dominio vacío. Se pierde una singularidad evitable.
- **Clasificación:** diferencia de dominio donde **el motor es el riguroso**; no es error del motor. No es «convención»: es pérdida de información de SymPy.
- **Cambio en el comparador:** el motor puede excluir puntos que SymPy no excluye **solo si** la expresión original (parseada con `evaluate=False`, sin autosimplificar) es realmente indefinida allí. Veredicto nuevo y visible: `SYMPY_AMPLIA_DOMINIO` (aparece en el informe en su propia sección, no se mezcla con «equivalente»). Si el motor inventa una restricción (`x ≠ 3` para `x`) → `DIFERENCIA_DOMINIO`; si omite una singularidad de SymPy → `DIFERENCIA_DOMINIO` (sin cambios).
- **Regresión:** `test_x_sobre_x_es_uno_solo_donde_x_no_es_cero` (oráculo en Python: `x/x` lanza `ZeroDivisionError` en 0), `test_singularidad_evitable_perdida_por_sympy_...`.

## 2. `solve(5=5)` — DIFERENCIA
- **Causa 1 (comparador):** la rama «todo el dominio» exigía `multiple_solutions`, y el detalle imprimía `SymPy None` porque esa referencia no llevaba texto. El `None` era un defecto del informe.
- **Causa 2 (convención del motor):** una ecuación **sin incógnita** es una *proposición*: el motor responde `Verdadero` (`success_exact`) y `Falso` (`no_solution`) —decisión ya documentada y probada en `test_04`—, mientras SymPy devuelve el conjunto solución (todo el dominio). Es el mismo hecho matemático en dos representaciones.
- **Clasificación:** diferencia legítima de **convención/representación**, documentada. No se oculta: se acepta como `CONVENCION_DOCUMENTADA` **solo** si la ecuación no tiene letras y el motor dice exactamente `Verdadero`. Con incógnita (`x=x`) el motor debe dar `multiple_solutions`; si diera `Verdadero` sería `DIFERENCIA`.
- **Regresión:** `test_ecuacion_constante_...` (test_10 y test_14).
- *Observación honesta:* es una asimetría de diseño (la falsa → `no_solution`, la verdadera → `success_exact`); se puede unificar en el contrato si prefieres `multiple_solutions` también para `5=5`.

## 3. `differentiate(abs(x))` — DIFERENCIA
- **Matemática:** d|x|/dx vale −1 para x<0 y +1 para x>0; **en x=0 no existe** (cocientes laterales −1 y +1). `x/|x|` = `sign(x)` para x≠0 y es indefinida en 0. SymPy fija `sign(0)=0`, una convención de la función signo, no una derivada.
- **Causa del hallazgo:** `Expr.equals` global dio `False` por el punto x=0 (donde `sign(0)=0` y `0/|0|` no existe) aunque coinciden en todo x≠0.
- **Clasificación:** diferencia de dominio con convención de SymPy; **el motor es correcto**. No hay error matemático.
- **Cambio en el comparador:** si `equals` global falla, se reintenta demostrando la igualdad **por separado en x>0 y x<0** (símbolos positivo/negativo); si no se demuestra, sigue siendo `DIFERENCIA` (no se esconde). Para el valor de SymPy en el punto excluido, se exige evidencia independiente: cocientes incrementales laterales de la función original con límites distintos (`no_derivable_por_cocientes`). Si se cumple → `SYMPY_AMPLIA_DOMINIO`; si no (función derivable allí) → `DIFERENCIA_DOMINIO`.
- **Mejora real del motor:** la condición se imprimía `abs(x) ≠ 0`; ahora `x ≠ 0` (mismo conjunto de puntos; `_norm_cond`).
- **Regresión (oráculo propio, sin SymPy):** derivada numérica en 8 puntos de ambos lados de 0, cocientes laterales en 0 (−1 y +1), condición `x ≠ 0`.

## 4. `integrate(sqrt(x))`, `integrate(tan(x))`, `integrate(1/x)` — ERROR_COMPARADOR
- **sqrt(x), tan(x):** el motor propio no las integra; con el respaldo activo (ver §0) la «respuesta del motor» venía de SymPy y se comparaba con SymPy. Con el respaldo desactivado quedan `LIMITACION_MOTOR` (probado: ambas son `unsupported` en el catálogo, `test_12`).
- **1/x:** el motor propio sí lo resuelve (`ln(abs(x)) + C`, condición `x ≠ 0`, verificado; derivada numérica correcta en ambos lados de 0). **No pude reproducir ni identificar la causa exacta de la excepción** sin SymPy aquí ni la traza de Windows: ni el texto del motor ni mi código lo explican con certeza.
  Lo que hice: (a) el evaluador del comparador ahora **falla con la expresión exacta** (`srepr` y símbolos libres) en vez de un `TypeError` relacional opaco, y (b) `ERROR_COMPARADOR` incluye la **traza**. Si el error persiste en Windows, el nuevo informe traerá la causa; no lo daré por resuelto hasta verlo.
- **Estado:** `sqrt`/`tan` resueltos por la corrección del sesgo; **`1/x` queda ABIERTO** hasta repetir la corrida.

## Qué NO está probado
Nada de lo anterior sobre SymPy se pudo ejecutar aquí (sin SymPy): la lógica se probó con un adaptador falso (`test_10`, 22 pruebas) y con oráculos propios (`test_14`). Las nuevas rutas `indefinida_en`, `no_derivable_en` e `igual_simbolico_por_signo` del adaptador real están **sin ejecutar**; son lo primero que debe confirmar la nueva corrida.
