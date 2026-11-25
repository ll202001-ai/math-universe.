# Funciones: implementado · probado · pendiente (motor 0.3.0)

**Implementado** = existe código. **Probado** = lo cubren pruebas reproducibles (`engine/tests`, `engine/audit`) y se indica con qué oráculo.
**No probado** se dice explícitamente. Ninguna función se da por terminada por tener estructura.

| Función | Implementado (alcance real) | Probado con | Límites conocidos |
|---|---|---|---|
| Parser seguro | + − × ÷ ^ ** ! paréntesis, multiplicación implícita (`2x`, `2(x+1)`), funciones elementales, `pi`, `e`; rechaza `2..3`, `3 4`, `3!!`, coma decimal. Sin `eval`/`exec` (prueba estática) | tests 01, 05, 06, 09 | Identificadores de varias letras son símbolos únicos (`at` ≠ `a*t`); `%` no admitido (usar `mod`) |
| Aritmética exacta | Racionales, radicales cuadráticos `a+b√d`, factorial, mcd, mcm, mod, floor, ceil, potencias racionales | tests 01, 05; `decimal` (cifras) | `floor/ceil/gcd/lcm/mod` sin segunda vía de verificación → `not_possible` |
| Aproximación decimal | **Radicales cuadráticos: cifras significativas arbitrarias exactas** (entero). Racionales exactos. `pi`, `e`, `sin(1)`…: ~15 cifras con aviso | test_09 vs módulo `decimal` | `mpmath` (precisión arbitraria de trascendentes) **no integrado todavía**; `mpmath` no estaba instalado donde se probó |
| Simplificación racional + dominio | Multivariante: monomios, contenido, divisores exactos; univariante: MCD completo; condiciones de denominadores, `ln`, `sqrt`, `tan`, `asin/acos`; `sqrt(x²)`→`abs(x)`; `exp(ln x)`, `ln(exp x)`; trigonometría exacta en ángulos notables | tests 02, 03, 09; oráculo (15 casos + 1 770 aleatorios) | Sin identidades trigonométricas (`sin²+cos²`), sin racionalizar denominadores, MCD multivariante limitado (aviso) |
| Expansión | Polinomios multivariantes | tests 02; 1 500 aleatorios | tope de 20 000 términos |
| Factorización | Univariante sobre Q: raíces racionales + Kronecker por grados 2..n/2 con tope (`factorization_complete` indica si es exhaustiva); **bivariante homogénea** (deshomogeneización); contenido y monomio común | tests 02, 09; 26 casos + 1 500 aleatorios (re-expansión) | **No** factoriza multivariantes no homogéneos (`x²-y²+x-y`) ni sobre extensiones; grado ≥ 6 con aviso |
| Ecuaciones de una variable | Polinómicas y racionales: raíces racionales + cuadrática exacta (radicales; complejas solo con `assumptions: complex`); excluye raíces que anulan denominadores; enunciados sin incógnita → `Verdadero/Falso` | tests 04, 09; 23 casos vs `numpy.roots` | **No** resuelve: cúbicas/cuárticas irreducibles, radicales, valor absoluto, exp/ln, trigonométricas, inecuaciones |
| Sistemas lineales | m×n sobre Q: matriz de coeficientes y aumentada, RREF, rangos, único/infinito/incompatible, operaciones de fila, sustitución exacta | tests 04; 25 sistemas aleatorios vs `numpy.linalg.solve` + 8 singulares | No lineales ni con parámetros → `unsupported` |
| Despeje literal | Grado 1 en la variable; condiciones del divisor | tests 04; 14 fórmulas | Grado ≥ 2 en la variable → `unsupported` |
| Dominio y supuestos | `positive/negative/nonzero/integer/real/complex` aplicados en simplify/expand/factor/solve | tests 03 | No se aplican a derivadas, integrales ni límites (aviso) |
| Derivadas | Suma, producto, cociente, cadena, potencias generales, funciones elementales, orden n | tests 02, 07; 21 casos + 1 780 aleatorios vs diferencias finitas | Orden ≥ 2 sin verificación (`not_possible`) |
| Integrales | Polinomios, racionales (fracciones parciales lineales y cuadráticas), poly·{exp,sin,cos}(ax+b), xᵏ ln x; definidas con detección de singularidades | tests 02; 39 casos vs `scipy.quad` + 720 aleatorios | Sin `sin²`, `sqrt`, `tan`, `exp(x²)`, argumentos no lineales, integrales impropias |
| Límites | Series de Laurent exactas: finitos, ±∞, laterales, no existencia | tests 02; 26 casos | Sin `exp(x)`/`ln` en puntos singulares, `(1+1/x)^x`, `x^x`, oscilantes |
| Verificación independiente | Segunda vía distinta del algoritmo productor; si falla, el resultado no se entrega | test_07 (negativas), oráculo, aleatorias | `not_possible` cuando no hay segunda vía (se informa) |
| `precision`, `timeout_ms`, `assumptions`, versión | Aplicados | tests 03, 05, 06 | Timeout cooperativo (no mata el proceso propio); sí mata el hijo de SymPy |
| Respaldo SymPy | Implementado como camino experimental con verificación independiente y traducción de sintaxis | **Cableado probado con backend SIMULADO (test_11). SymPy real: NO probado aquí** → `test_08_sympy.py` | Solo simplify/expand/factor/differentiate/integrate |
| Comparación motor vs SymPy | Comparador de 165 casos con 7 veredictos | **Mecánica probada (test_10); ejecución real contra SymPy pendiente** | — |
| Canal JSON Lines UTF-8 | `python -I run_server.py` | test_06 (incluye cp1252) | — |

## Pendiente (no implementado)
Matrices y álgebra lineal (siguiente módulo, **no iniciado** por instrucción) · autovalores/autovectores · ecuaciones trascendentes y radicales · cúbicas/cuárticas con radicales ·
inecuaciones · identidades trigonométricas · factorización multivariante general · integrales avanzadas e impropias · límites con exp/ln · EDO · estadística · unidades ·
módulo eléctrico · procedimiento paso a paso (solo operaciones de fila reales en sistemas) · `mpmath` integrado (trascendentes a precisión arbitraria) · `success_approximate`, `cancelled` ·
SQLite · interfaz Flutter.
