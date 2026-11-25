# Auditoría matemática · motor 0.3.0

Objetivo: comprobar que el motor produce resultados **correctos**, no solo que "ejecuta". Método: oráculos **independientes del motor**
(no usan su parser ni su evaluador): funciones Python escritas a mano, NumPy/SciPy (`linalg.solve`, `quad`), diferencias finitas de orden 4, el módulo
`decimal` de la biblioteca estándar y pruebas aleatorias con semillas fijas. Reproducible con `python tools/validar_todo.py`.

## Resultado en el entorno de desarrollo (Linux, Python 3.13.18; **SymPy y mpmath NO instalados aquí**)
| Área | Casos | Correctos | No soportados (declarados) | Fallos |
|---|---|---|---|---|
| Simplificación y dominio | 15 | 15 | 0 | 0 |
| Factorización | 26 | 26 | 0 | 0 |
| Ecuaciones de una variable | 23 | 23 | 0 | 0 |
| Sistemas lineales | 33 | 33 | 0 | 0 |
| Despeje de fórmulas | 14 | 13 | 1 | 0 |
| Derivadas | 21 | 21 | 0 | 0 |
| Integrales | 39 | 32 | 7 | 0 |
| Límites | 26 | 26 | 0 | 0 |
| Aproximaciones numéricas | 11 | 11 | 0 | 0 |
| **Total** | **208** | **200** | **8** | **0** |

Corrección respecto a la entrega anterior: allí «208/208» contaba como correctos 8 casos que el motor **declaraba no soportados**. Un «no soportado» no es un acierto;
ahora el oráculo tiene tres estados y el informe los separa.

Pruebas aleatorias (6 semillas × 300 expresiones + 250 polinomios + 120 integrales): ≈1 770 simplificaciones, ≈1 780 derivadas, 1 500 factorizaciones,
1 500 expansiones y 720 integrales comparadas con la evaluación numérica independiente → **0 fallos** tras las correcciones de abajo.

**Lo que esto NO demuestra:** no hay pruebas formales; los oráculos son numéricos (puntos de muestra); la comparación **contra SymPy no se ha ejecutado**
(ver `INFORME_VALIDACION.md` tras correr `scripts\instalar_y_probar.bat` en Windows).

## Hallazgos de esta auditoría (clasificados)
| # | Hallazgo | Clasificación | Estado |
|---|---|---|---|
| A1 | `ln(0)`, `tan(pi/2)`, `asin(2)` devolvían **éxito** con una condición de dominio incumplida | **Error** (grave) | Corregido → `domain_error` |
| A2 | `sin(pi)`, `cos(pi/3)`… no se evaluaban (quedaban como átomos) | Limitación | Corregido (ángulos múltiplos de π/6 y π/4) |
| A3 | Condiciones triviales como `sqrt(2) ≠ 0` ensuciaban el resultado | Defecto de presentación | Corregido (se omiten las constantes verdaderas) |
| A4 | `exp(ln x)` y `ln(exp x)` sin simplificar | Limitación | Corregido (con condición `x > 0`) |
| A5 | `(-8)^(1/3)` quedaba sin evaluar con una condición falsa | Error + convención | Corregido: raíz **real** de índice impar (`-2`). SymPy usa la rama compleja principal → **diferencia de convención documentada** |
| A6 | `5=5` / `5=6` devolvían `invalid_input` | Limitación | Corregido: `Verdadero`/`Falso` por aritmética exacta |
| A7 | `x^2-y^2`, `x^3+y^3`, `(x+y)^2` **no se factorizaban** | Limitación | Corregido para polinomios homogéneos de 2 variables. **Sigue sin factorizar** polinomios multivariantes no homogéneos (con aviso explícito) |
| A8 | `3!!` se interpretaba en silencio como `(3!)!` = 720 | **Error** (ambigüedad) | Corregido → error de sintaxis con explicación |
| A9 | `1,5+1` daba un mensaje poco claro | Defecto de presentación | Mensaje explícito (punto decimal) |
| A10 | `1/2/sqrt(x)` y `(x)^(x)` | Defecto de presentación | `1/(2*sqrt(x))`, `x^x` |
| A11 | `x=at+b` con incógnita `t`: "no aparece" (porque `at` es un símbolo de dos letras) | Diseño | Se mantiene (identificadores multiletra); el mensaje ahora indica usar `*` |
| A12 | Verificación de derivadas/primitivas: falso fallo con funciones enormes (`exp(27)`) por redondeo del propio método | **Error de verificación** | Corregido: se acota el redondeo y el punto no informativo no cuenta como evidencia (→ `not_possible`, nunca `passed`) |
| A13 | Integral definida de picos estrechos (`1/(x²+1)` en [-1000,1000]) rechazada por falso fallo del Simpson uniforme | **Error de verificación** | Corregido: Simpson adaptativo |
| A14 | Integral impropia (`x ln x` en [0,1]) respondía `domain_error` | Defecto de clasificación | Ahora `unsupported` (impropia); `ln x` en [-1,1] sigue siendo `domain_error` (integrando indefinido) |
| A15 | Ecuaciones con `sqrt`, `abs`, `exp`, `ln`, trigonométricas: mensaje engañoso ("parámetros libres") | Defecto de mensaje | Mensaje correcto; **siguen sin resolverse** (limitación) |
| A16 | `precision > 15` limitaba también a radicales | Limitación | Radicales cuadráticos: cifras significativas arbitrarias exactas (aritmética entera). Trascendentes (`pi`, `e`, `sin(1)`) siguen en ~15 cifras con aviso (requiere mpmath) |
| A17 | **El respaldo SymPy cambiaba resultados de las pruebas según el entorno** | Defecto de diseño | Interruptor `MATH_UNIVERSE_DISABLE_SYMPY`; las pruebas del motor propio lo activan; `test_08` lo desactiva |
| A18 | Resultado de SymPy (respaldo) se devolvía con verificación `not_possible` para derivar/integrar | Defecto | Ahora pasa por la misma verificación independiente (probado con respaldo **simulado**) |
| A19 | En Windows la consola/`stdin` usa cp1252 y el canal JSON podía fallar con `≠`, `−` | **Error** (plataforma) | Fuerza UTF-8; prueba con `PYTHONIOENCODING=cp1252` |
| A20 | La versión del motor en el código (0.1.0) no coincidía con la documentada (0.2.0) | Error de documentación | `0.3.0` única fuente (`__init__.py`) |
| 27 | **Regresión propia:** `∫ x^n dx` devolvía `x*x^n + C` (falso). Causa: un cambio en la impresión de átomos hizo que `x^n` se tomara por coeficiente. **Lo frenó el verificador** (no salió al usuario) | **Error** (grave, introducido y detectado en esta fase) | Ahora `unsupported`; `test_integral_con_exponente_simbolico_no_devuelve_un_resultado_falso` |
| 28 | `(x^a)^2` se imprimía `x^a^2` (se lee como `x^(a^2)`) | **Error** de representación ambigua | `test_potencia_de_atomo_potencia_no_se_imprime_ambigua` |
| 29 | Falso fallo del verificador de derivadas cerca de singularidades (`sin(2^a/(a-x))`, x≈a) | Falso positivo del verificador | Esquema de h y h/2; punto mal condicionado = sin evidencia; fuzz con parámetros |
| 30 | Factorización por Kronecker limitada al grado 2 | Limitación | Todos los grados 2..n/2 con tope de candidatos; `data.factorization_complete` indica si es exhaustiva |
| 31 | Comparador con SymPy con sesgos (equivalencia vacía, omisiones silenciosas, bandera de convención que ocultaba diferencias, sin tiempo límite, ruido de coma flotante) | Sesgo de método | Reescrito con principios anti-sesgo; `test_10_comparador.py` (15 pruebas con adaptador falso) |

## Diferencias previstas motor ↔ SymPy (hipótesis, **no confirmadas**: hay que ejecutar la comparación)
| Caso | Qué se espera | Clasificación esperada |
|---|---|---|
| `(-8)^(1/3)` | Motor `-2`; SymPy `1 + √3·i` | Convención (dominio real vs rama principal) |
| `ln(abs(x))` vs `log(x)` en primitivas de `1/x` | Primitivas distintas que difieren en dominio | Representación (se compara por derivada) |
| Orden de términos / forma (`(x+1)^2` vs `x**2+2*x+1`) | Equivalentes numéricamente | Representación |
| `sqrt(x^2)` | `abs(x)` en ambos si x es real | Idéntico |
| `exp(ln(x))` | Motor `x` con condición `x>0`; SymPy puede dejar `exp(log(x))` | Representación / diferencia de dominio |
| Integrales no resueltas por el motor (`sin(x)^2`, trigonometría, `exp(x^2)`) | SymPy sí | Limitación del motor |
| Límites con `exp`, `ln`, `x^x` | SymPy sí | Limitación del motor |
| Ecuaciones con `sqrt`, `abs`, `ln`, `exp`, trigonométricas | SymPy (`solveset`) sí | Limitación del motor |

## Limitaciones conocidas (honestas)
Ver `docs/FUNCIONES.md`. Resumen: sin ecuaciones trascendentes/radicales, sin cúbicas/cuárticas irreducibles, sin factorización multivariante no homogénea,
sin identidades trigonométricas generales, límites sin `exp(x)`/`ln` en puntos singulares, integrales sin `sin²`-productos ni impropias, cifras arbitrarias solo para radicales cuadráticos.
