# Lo que el motor NO soporta o resuelve de forma incompleta (motor 0.5.0)

**Este archivo se genera ejecutando `audit/no_soportado.py` (`python tools/generar_no_soportado.py`).** Cada fila es un caso real ejecutado;
una prueba (`tests/test_12_no_soportado.py`) falla si el comportamiento cambia sin actualizar este documento.

## A. No soportado: el motor responde `unsupported` y NO entrega resultado

| Área | Operación | Entrada | Qué falta | Estado | Mensaje del motor |
|---|---|---|---|---|---|
| Ecuaciones | solve | `sqrt(x)=x-2` | ecuaciones radicales | `unsupported` | Ecuación con funciones no polinómicas de x (sqrt(x)): radicales, valor absoluto, exponenciales, logaritmos y t |
| Ecuaciones | solve | `abs(x)=3` | valor absoluto | `unsupported` | Ecuación con funciones no polinómicas de x (abs(x)): radicales, valor absoluto, exponenciales, logaritmos y tr |
| Ecuaciones | solve | `exp(x)=2` | exponenciales | `unsupported` | Ecuación con funciones no polinómicas de x (exp(x)): radicales, valor absoluto, exponenciales, logaritmos y tr |
| Ecuaciones | solve | `2^x=8` | exponenciales con base numérica | `unsupported` | Ecuación con funciones no polinómicas de x (2^x): radicales, valor absoluto, exponenciales, logaritmos y trigo |
| Ecuaciones | solve | `ln(x)=0` | logaritmos | `unsupported` | Ecuación con funciones no polinómicas de x (ln(x)): radicales, valor absoluto, exponenciales, logaritmos y tri |
| Ecuaciones | solve | `sin(x)=0` | trigonométricas | `unsupported` | Ecuación con funciones no polinómicas de x (sin(x)): radicales, valor absoluto, exponenciales, logaritmos y tr |
| Ecuaciones | solve | `x^3-2=0` | cúbicas irreducibles sobre Q (radicales cúbicos) | `unsupported` | Ecuación de grado >= 3 sin factorización racional/cuadrática: no soportada por el motor propio |
| Ecuaciones | solve | `x^3+x+1=0` | cúbicas irreducibles sobre Q | `unsupported` | Ecuación de grado >= 3 sin factorización racional/cuadrática: no soportada por el motor propio |
| Sistemas | solve | `x^2+y^2=1; x=y` | sistemas no lineales | `unsupported` | El sistema no es lineal |
| Sistemas | solve | `x*y=1; x+y=2` | sistemas no lineales | `unsupported` | El sistema no es lineal |
| Despeje | solve | `x^2=a` | despeje de grado ≥ 2 en la variable | `unsupported` | Despeje literal solo implementado para grado 1 en 'x' (grado 2) |
| Despeje | solve | `A=pi*r^2` | despeje de grado ≥ 2 en la variable | `unsupported` | Despeje literal solo implementado para grado 1 en 'r' (grado 2) |
| Integrales | integrate | `sin(x)^2` | potencias/productos de funciones trascendentes | `unsupported` | Producto/potencia de funciones no soportado por el integrador propio |
| Integrales | integrate | `sin(x)*cos(x)` | productos de funciones trascendentes | `unsupported` | Producto/potencia de funciones no soportado por el integrador propio |
| Integrales | integrate | `sqrt(x)` | integral de raíces/potencias fraccionarias | `unsupported` | Integral de sqrt no implementada |
| Integrales | integrate | `1/sqrt(x)` | integral de raíces/potencias fraccionarias | `unsupported` | Cociente con funciones trascendentes: no implementado |
| Integrales | integrate | `tan(x)` | tan | `unsupported` | Integral de tan no implementada |
| Integrales | integrate | `exp(x^2)` | argumento no lineal en funciones trascendentes | `unsupported` | Argumento no lineal en integrando trascendente |
| Integrales | integrate | `sin(x)/x` | cocientes con funciones trascendentes | `unsupported` | Cociente con funciones trascendentes: no implementado |
| Integrales | integrate | `x^n` | exponente simbólico | `unsupported` | Integral de ^ no implementada |
| Integrales | integrate | `2^x` | exponenciales con base distinta de e | `unsupported` | Integral de ^ no implementada |
| Integrales | integrate | `x^(1/3)` | potencias fraccionarias | `unsupported` | Integral de ^ no implementada |
| Integrales | integrate | `abs(x)` | valor absoluto | `unsupported` | Integral de abs no implementada |
| Integrales | integrate | `1/x` | integrales impropias (singularidad interior) | `unsupported` | El integrando tiene una singularidad en el intervalo: integral impropia no implementada |
| Integrales | integrate | `x*ln(x)` | integrales impropias (extremo singular) | `unsupported` | Integral impropia (la primitiva no está definida en un extremo): no implementada |
| Límites | limit | `(1+1/x)^x` | exponentes variables | `unsupported` | Exponente no entero en límite |
| Límites | limit | `x^x` | exponentes variables | `unsupported` | Exponente no entero en límite |
| Límites | limit | `x*sin(1/x)` | argumentos singulares de funciones trascendentes | `unsupported` | Argumento sin término constante nulo: función no desarrollable aquí |
| Límites | limit | `exp(x)/x` | exp en infinito | `unsupported` | Argumento sin término constante nulo: función no desarrollable aquí |
| Límites | limit | `ln(x)/x` | ln en infinito / en 0 | `unsupported` | ln de una serie con término constante 0: no desarrollable |
| Límites | limit | `x*ln(x)` | ln en 0 | `unsupported` | ln de una serie con término constante 0: no desarrollable |
| Límites | limit | `sqrt(x^2+x)-x` | raíces con término constante nulo | `unsupported` | sqrt de una serie con término constante 0: no desarrollable |
| Límites | limit | `(x-1)/abs(x-1)` | valor absoluto | `unsupported` | Función 'abs' sin desarrollo en serie implementado |
| Aritmética | evaluate | `sqrt(-4)` | números complejos fuera de ecuaciones con supuesto complex | `unsupported` | Raíz de negativo requiere complejos |
| Aritmética | evaluate | `(-1)^(1/2)` | raíz de índice par de un negativo | `unsupported` | Potencia de un negativo con raíz de índice par: requiere complejos |
| Simbólico | simplify | `foo(x)` | funciones desconocidas | `unsupported` | Función 'foo' no soportada en expresiones simbólicas |

## B. Incompleto: el motor entrega un resultado CORRECTO pero no completo

| Área | Operación | Entrada | Qué falta | Resultado entregado | Verificación |
|---|---|---|---|---|---|
| Factorización | factor | `x^2-y^2+x-y` | polinomios multivariantes NO homogéneos: se devuelve sin factorizar (con aviso) | `x^2 - y^2 + x - y` | `passed` |
| Simplificación | simplify | `sin(x)^2+cos(x)^2` | identidades trigonométricas: no se reduce a 1 | `cos(x)^2 + sin(x)^2` | `passed` |
| Simplificación | simplify | `1/(sqrt(2)-1)` | racionalización de denominadores: no se transforma en sqrt(2)+1 | `1/(sqrt(2) - 1)` | `passed` |
| Simplificación | simplify | `sqrt(x)*sqrt(x)` | sqrt(x)^2 no se reduce a x (con condición x ≥ 0) | `sqrt(x)^2` | `passed` |
| Aritmética | evaluate | `atan(1)` | valores exactos de funciones trigonométricas inversas (atan(1) no se reduce a pi/4) | `atan(1)` | `passed` |
| Derivadas | differentiate | `x^3*sin(x)` | verificación independiente de derivadas de orden ≥ 2 (verification = not_possible) | `-sin(x)*x^3 + 6*cos(x)*x^2 + 6*sin(x)*x` | `not_possible` |
| Aritmética | evaluate | `floor(7/2)` | gcd/lcm/mod/floor/ceil: sin segunda vía de verificación (verification = not_possible) | `3` | `not_possible` |

## C. Otras limitaciones de alcance (no son casos de entrada única)
- Factorización univariante: exhaustiva (Kronecker por grado) con tope de candidatos; si se agota, `data.factorization_complete = false` y aviso explícito. Puede ser **lenta** para grado alto (segundos a decenas de segundos).
- Verificación: toda comprobación numérica usa puntos de muestra; **no es una demostración formal**.
- Sistemas lineales: sin parámetros simbólicos. Ecuaciones: dominio real por defecto; complejas solo con `assumptions: {x: complex}`.
- `assumptions` no se aplican a derivadas, integrales ni límites (se avisa).
- Identificadores de varias letras son símbolos únicos (`at` ≠ `a*t`).
- Respaldo SymPy: **no probado con SymPy real** hasta ejecutar `test_08_sympy.py` en un entorno con SymPy.
- Cualquier entrada fuera de estas tablas **no está garantizada**: «no aparece aquí» no significa «soportado».
