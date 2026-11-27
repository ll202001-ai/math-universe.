# Contrato del motor · versión de API 1.1 (motor 0.4.0)

> **1.1 es ADITIVA respecto de 1.0:** todo cliente 1.0 sigue funcionando (mismas operaciones, mismos campos). Novedades: operaciones `matrix_*`, `determinant` operativa y `structured_input` con `a`/`b`.

Basado en la **Corrección arquitectónica rectora §7** del PDF definitivo. Esquemas formales y validados en ejecución:
`engine/schema/request.schema.json` y `engine/schema/response.schema.json`. **Toda respuesta se valida contra el esquema antes de enviarse**; si no cumple, se devuelve `internal_error`.

## Solicitud
| Campo | Tipo | Notas |
|---|---|---|
| `request_id` | string/int/null | Se devuelve igual en la respuesta |
| `operation` | enum | `ping, capabilities, parse, evaluate, simplify, expand, factor, solve, differentiate, integrate, limit, determinant` y `matrix_add, matrix_sub, matrix_mul, matrix_transpose, matrix_det, matrix_inverse, matrix_rank, matrix_rref, matrix_solve` |
| `expression` | string ≤ 5000 | Ecuaciones con `=`; sistemas separados por `;` o salto de línea |
| `structured_input` | objeto | Solo operaciones `matrix_*`/`determinant`: `{"a": M, "b": M}` (ver §Álgebra lineal). Otros campos → `invalid_input` |
| `variables` | [string] | Incógnita(s) o variable de derivación/integración/límite |
| `assumptions` | {var: real/positive/negative/nonzero/integer/complex} | **Se aplica** en simplify/expand/factor/solve (ver §Supuestos) |
| `precision` | 1–1000 | **Se aplica** (cifras significativas) a `approximate_result`. Racionales y radicales cuadráticos: cifras exactas (aritmética entera). `pi`, `e`, funciones trascendentes: ~15 cifras con aviso (mpmath pendiente) |
| `timeout_ms` | 1–600000 | **Se aplica** (plazo cooperativo en el motor propio; proceso hijo terminable para SymPy). Por defecto 10000 |
| `engine_version` | string | Si la versión mayor no coincide → `invalid_input` / `VERSION_MISMATCH` |
| `point`, `direction`, `lower`, `upper`, `order` | — | Ampliaciones compatibles: límites (`point`: racional, `+oo`, `-oo`; `direction`: both/+/-), integral definida, orden de derivada |

`determinant` es alias de `matrix_det` (la matriz puede ir en `expression` como `[[1,2],[3,4]]`).

## Respuesta
`request_id, api_version, status, parsed_input, exact_result, approximate_result, conditions[], warnings[], method, verification{status,method}, data{}, error{code,message,details}, elapsed_ms`.

### Estados (`status`)
| Estado | Significado en esta implementación |
|---|---|
| `success_exact` | Resultado exacto. Incluye conjuntos finitos de soluciones (varias raíces) |
| `success_approximate` | Reservado (no se emite todavía) |
| `multiple_solutions` | **Familia infinita** de soluciones (sistema indeterminado o identidad) |
| `no_solution` | Conjunto solución vacío (incl. «los límites laterales difieren») |
| `unsupported` | No implementado o no resuelto por el motor (**no** implica que no exista solución) |
| `invalid_input` | Sintaxis, esquema, tamaño o versión |
| `domain_error` | División por cero, 0^0, factorial de negativo… |
| `timeout` | Plazo agotado; nunca se entrega un resultado parcial como final |
| `cancelled` | Reservado (la cancelación la ejecuta el anfitrión terminando el proceso) |
| `internal_error` | Defecto del motor o **verificación independiente fallida** (`VERIFICATION_FAILED`, el resultado no verificado va solo en `error.details.unverified_result`) |

### Verificación (`verification.status`)
`passed` · `failed` · `not_possible` · `not_performed`. Solo se emite `passed` tras una comprobación que **no repite el algoritmo** (ver `FUNCIONES.md`). Si falla, el resultado no se entrega.

### Condiciones (`conditions`)
Restricciones de dominio del problema **original** (denominadores `x ≠ 1`, argumentos `x > 0` de ln, `x+1 >= 0` de raíces…), conservadas aunque la expresión se simplifique. Los supuestos del usuario eliminan solo las condiciones que realmente garantizan.

## Códigos de error
`INVALID_REQUEST, PARSE_ERROR, DOMAIN_ERROR, NOT_IMPLEMENTED, DEPENDENCY_MISSING, LIMIT_EXCEEDED, NOT_SOLVED, VERSION_MISMATCH, TIMEOUT, VERIFICATION_FAILED, INTERNAL_ERROR`.

## Límites de recursos (aplicados)
Expresión ≤ 5000 caracteres · anidamiento ≤ 100 · exponente de polinomio ≤ 500 · ≤ 20000 términos · factorial ≤ 5000 · exponentes racionales grandes rechazados · línea JSON ≤ 100000 bytes.

## Ejemplos
```json
{"request_id":1,"operation":"simplify","expression":"(x^2-1)/(x-1)"}
→ {"status":"success_exact","exact_result":"x + 1","conditions":["x ≠ 1"],"verification":{"status":"passed","method":"evaluacion_en_puntos_exactos_del_original_vs_resultado"}, ...}

{"operation":"solve","expression":"2x+y=5; x-y=1"}
→ exact_result "x = 2, y = 1"; data.coefficient_matrix [[2,1],[1,-1]], augmented_matrix, rank_A=2, rank_augmented=2

{"operation":"solve","expression":"V=I*R","variables":["R"]}
→ "R = V/I", conditions ["I ≠ 0"]
```

## Decisiones propuestas (ADR provisionales)
- ADR-1: motor exacto propio (Python puro) como primera vía; SymPy como respaldo **experimental** solo para simplify/expand/factor/differentiate/integrate cuando el motor propio no puede, y su resultado pasa por la misma verificación independiente. Condición de revisión: cuando SymPy esté probado en Android/Windows.
- ADR-2: dominio por defecto de las ecuaciones = reales; `assumptions: {x: complex}` habilita raíces complejas.
- ADR-3: `log` = logaritmo natural (igual que `ln`).


## Cambios de la etapa de validación (0.3.0)
- **Enunciados sin incógnita** (`5=5`): `success_exact` con `exact_result: "Verdadero"`, o `no_solution` con `"Falso"`; `data.truth_value` booleano. División por cero → `domain_error`.
- **Condiciones de dominio constantes**: si una condición sin variables se incumple (`ln(0)`, `tan(pi/2)`, `asin(2)`) → `domain_error`; si se cumple, no se lista.
- **Convención real**: `(-8)^(1/3)` = `-2` (raíz real de índice impar); raíz de índice par de un negativo → `unsupported` (complejos solo con `assumptions: {"x": "complex"}` en ecuaciones).
- **`approximate`** en soluciones usa `precision` si el usuario la envía (15 cifras por defecto).
- **Variable de entorno** `MATH_UNIVERSE_DISABLE_SYMPY=1`: desactiva el respaldo SymPy (resultados del motor propio puro y reproducibles). Por defecto, si SymPy está instalado, el respaldo está activo y **su resultado pasa por la verificación independiente**; `method: "sympy_respaldo_experimental"`.
- **Canal JSON Lines**: UTF-8 forzado en `stdin/stdout` (Windows).
- **Sintaxis**: `3!!` y la coma decimal se rechazan con mensaje explicativo.
- Los esquemas `request.schema.json` / `response.schema.json` no cambiaron (compatibles).

## Campos añadidos en 0.3.0
- `data.factorization_complete` (bool, operación `factor`): `true` si la factorización es exhaustiva sobre Q; `false` si se agotó el tope de candidatos o el caso no está cubierto (el resultado sigue verificándose por re-expansión, pero puede no estar completamente factorizado; se emite aviso).
- Aviso `La variable '<v>' no aparece en la expresión: la derivada es 0` en `differentiate`.
- Verificación fallida: `status=internal_error`, `error.code=VERIFICATION_FAILED`, candidato en `error.details.unverified_result` (nunca presentado como resultado).
- `integrate` indefinido: `conditions` contiene el dominio del **integrando** (p. ej. `x ≠ -1`); la primitiva vale en cada intervalo de continuidad y `C` puede diferir entre intervalos.
- `conditions` normaliza `abs(u) ≠ 0` a `u ≠ 0` (mismo conjunto de puntos).


## Álgebra lineal (API 1.1)
Entrada: `structured_input.a` (y `.b`) como lista de listas `[[1,"1/2"],[0.25,3]]` o como texto `"[[1,1/2],[1/4,3]]"`. Entradas = **racionales exactos** (enteros, fracciones, decimales, constantes racionales como `(1+2)/6`); hasta **40×40**. Con símbolos o irracionales → `invalid_input`/`PARSE_ERROR` (nunca un resultado aproximado en silencio).
| Operación | Entradas | `exact_result` | `data` | Verificación independiente |
|---|---|---|---|---|
| `matrix_add`, `matrix_sub` | a, b (misma forma) | matriz | `matrix` | inversa de la operación |
| `matrix_mul` | a (m×n), b (n×p) | matriz | `matrix` | Freivalds exacto |
| `matrix_transpose` | a | matriz | `matrix` | índice a índice |
| `matrix_det` / `determinant` | a cuadrada | número | `determinant`, `invertible` | Bareiss + Laplace (n≤6) + det(Aᵀ) |
| `matrix_inverse` | a cuadrada | matriz | `matrix` | A·A⁻¹=I y A⁻¹·A=I. Singular → `domain_error` |
| `matrix_rank` | a | entero | `rank`, `pivot_columns`, `nullity` | menor r×r no nulo + núcleo |
| `matrix_rref` | a | matriz | `matrix`, `pivot_columns`, `rank` | forma reducida válida |
| `matrix_solve` | a (m×n), b (m×1) | texto | `kind` (`unique`/`infinite`/`none`), `particular`, `nullspace_basis`, certificado | A·x=b y A·v=0; sin solución: certificado de Farkas |
`matrix_solve`: estado `success_exact` (única), `multiple_solutions` (infinitas) o `no_solution`.
Los archivos golden del contrato están en `engine/tests/golden/matrices/` (regresión; los valores conocidos se comprueban a mano en `test_21`).

## Operaciones añadidas en API 1.3 (motor 0.7.0, aditivas)
Todas devuelven `verification.status = passed` solo si la comprobación independiente cuadra; si no, `VERIFICATION_FAILED`.
| Operación | Entradas | Ejemplo → `exact_result` | Verificación independiente |
|---|---|---|---|
| `sum`, `product` | `expression`, `params.var`, `params.from`, `params.to` (`oo` = ∞) | `k`, k=1..10 → `55`; `1/k^2`, 1..oo → `pi^2/6` | suma directa de términos, o sumas parciales mpmath para series; divergentes → `diverge` con `not_possible` |
| `substitute` | `expression`, `params.values` `{x: "2", y: "a+1"}` | `x^2+y` → `a + 5` | evaluador propio en puntos |
| `matrix_symbolic` | `structured_input.a` (y `.b`), `params.op` ∈ det, inverse, transpose, mul, charpoly, eigen (hasta 8×8) | `[[a,b],[c,d]]` det → `a*d - b*c` | A·A⁻¹=I simplificado, det por dos métodos, evaluación en puntos racionales |
| `logic` | `expression` con `& | ~ -> <->`, `∧ ∨ ¬ → ↔`, «y/o/no» | `~(p & q)` → `¬p ∨ ¬q`; `data.classification`, `data.truth_table` | tabla de verdad completa (parser propio) |
| `sets` | `expression` con intervalos `[a,b]`, `(a,b)`, conjuntos `{…}` y `∪ ∩ \` | `[0,2] ∪ [1,3]` → `[0, 3]` | pertenencia en puntos de prueba |
| `implicit_diff` | `expression` = ecuación en x, y | `x^2+y^2=1` → `-x/y` | coincide con −F_x/F_y (teorema de la función implícita, vía distinta de idiff) |
Funciones añadidas al parser: `%` (postfijo, /100), `log(x,b)`, `cbrt`, `root(x,n)`, `sec csc cot`, `asinh acosh atanh`,
`gamma erf erfc beta zeta besselj floor ceil`. `evaluate` usa SymPy como respaldo verificado; `zoo`/`nan`/`oo` → `domain_error`.

## Operación `resolver`

Entrada: `{"operation":"resolver","expression":"<enunciado en texto libre>","latex":true,"steps":true,"timeout_ms":60000}`. Salida: la respuesta estándar (`status`, `exact_result`, `approximate_result`, `steps`, `verification`, `warnings`). El primer paso es «Interpretación: …» con lo que el motor entendió; si no se reconoce, `status: unsupported` y la lista de intentos.
