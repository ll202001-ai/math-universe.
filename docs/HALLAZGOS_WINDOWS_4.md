# Hallazgos pendientes del INFORME_VALIDACION.md de la fase 7 (Windows)

**Resultado original conservado (reportado por el usuario):** 434 pruebas aprobadas; el informe declara dos hallazgos pendientes de revisión:
1. `simplify((x^3-8)/(x-2))` — comprobar que se conserva `x ≠ 2` (no basta la equivalencia algebraica).
2. `integrate(1/(x^3+1))` — verificación simbólica rigurosa de la primitiva; `SymPy.equals` devuelve `False`.

> No tuve el texto del informe de Windows: trabajo con la descripción del usuario. Lo que sigue distingue **lo comprobado aquí** de **lo que solo se confirma ejecutando en Windows**.

## 1. `simplify((x^3-8)/(x-2))`
**Comprobado (sin SymPy):**
- El motor devuelve `x^2 + 2*x + 4` con `conditions = ["x ≠ 2"]`, también en `expand` y `factor`, y la condición sobrevive a sumas, potencias, productos y a otras singularidades (`x ≠ 2`, `x ≠ -1`).
- Verificación **independiente de la equivalencia algebraica** (`test_la_cancelacion_conserva_la_condicion_x_distinto_de_a`, 60 casos: `(x^n − a^n)/(x − a)`, n=2..6, a∈{−3,−1,2,5}, ×3 operaciones): (1) la función original **no existe** en x=a (`ZeroDivisionError` con `Fraction` exactas); (2) el resultado simplificado **sí está definido** en a (por eso la condición es imprescindible, no decorativa); (3) igualdad exacta con el original en 12 racionales; (4) `x ≠ a` está en `conditions`.
- Defecto menor hallado: `expand((x^3-8)/(x-2) − (x^2+2x+4))` devolvía `0/(x - 2)`; ahora `0` (con `x ≠ 2`). Corregido en `rf_str`.

**Causa raíz del «hallazgo pendiente»:** no es un error del motor. SymPy reduce o ignora la singularidad evitable (el motor la excluye con razón: la expresión original no existe en x=2, aunque el límite sea 12). El comparador lo clasifica `SYMPY_AMPLIA_DOMINIO` solo si evidencia **independiente** confirma que la original es indefinida allí (`indefinida_en`, parseada con `evaluate=False`), y desde esta ronda añade el **límite** en el punto (singularidad evitable) al detalle. Seguirá apareciendo en una sección «REVISAR» del informe por diseño: es una diferencia real de dominio entre ambos sistemas, no se esconde en «equivalente».
**Pendiente en Windows:** `test_singularidad_evitable_x3_menos_8_sobre_x_menos_2_con_sympy_real` (indefinida_en, límite 12, veredicto).

## 2. `integrate(1/(x^3+1))`
**Demostración exacta (aritmética racional, sin SymPy ni flotantes)** — `test_derivada_de_la_primitiva_clasica_es_exactamente_el_integrando`:
G(x) = ⅓ln|x+1| − ⅙ln(x²−x+1) + (1/√3)·atan((2x−1)/√3). Con d/dx ln|u| = u'/u (a ambos lados de u=0) y d/dx atan v = v'/(1+v²):
G' = 1/(3(x+1)) − (2x−1)/(6(x²−x+1)) + 1/(2(x²−x+1)) = 1/(3(x+1)) + (2−x)/(3(x²−x+1)) = [(x²−x+1) + (2−x)(x+1)] / (3(x³+1)) = 3/(3(x³+1)) = **1/(x³+1)**
porque (x²−x+1)+(2−x)(x+1) = 3 (polinomio de grado ≤ 2 igual a 3 en ≥ 3 puntos). Se comprueba además con `Fraction` en 598 racionales de ambos lados de −1. La primitiva del motor difiere de G solo en una constante por intervalo (12 puntos, ambos lados). **La primitiva es correcta.**

**Causa raíz de `equals = False`:** *hipótesis, no confirmada aquí* (no tengo SymPy). `Expr.equals` es un procedimiento **heurístico** (simplificación + muestreo numérico). La derivada de la primitiva contiene `sign(x+1)/Abs(x+1)`, que SymPy **no** reduce a `1/(x+1)` automáticamente; con esos términos `equals` puede responder `False`/`None` aunque la identidad sea exacta. Dos hechos descartan «diferencia matemática real»: la demostración exacta de arriba, y que el comparador ya había verificado la coincidencia en 16 puntos racionales a 40 cifras antes de consultar `equals`. Para fijar la causa con datos, `tools/diagnosticar_comparador.py` (se ejecuta al final de `instalar_y_probar.bat`) vuelca `srepr(a−b)`, `equals`, `simplify`, `is_zero` y valores a 60 cifras → `validacion\diagnostico_comparador.txt`.

**Corrección del comparador (no del motor):** un `False/None` de `equals` ya no se toma por prueba ni por refutación. Nuevo `igual_simbolico_por_ramas`: **demostración exacta** — se parte la recta en los intervalos que delimitan las raíces de los argumentos de `Abs`/`sign`, en cada uno el signo es constante (evaluado exactamente en un racional interior), se sustituye `Abs(u)=±u`, `sign(u)=±1` y se decide `cancel(together(a−b)) = 0`. Si demuestra → `EQUIVALENTE` y el detalle dice «SymPy.equals=False; DEMOSTRADO exactamente por ramas» (aparece en su sección del informe, no oculto). Si no demuestra y `equals` fue `False` → sigue siendo `DIFERENCIA`. Pruebas negativas: una primitiva incompleta (`ln|x+1|/3`) o `x/|x|` vs `1` **no** se «demuestran» (`test_08`, `test_10`).
**Riesgo reconocido:** que una demostración propia sobrescriba a `equals=False` podría ocultar una diferencia si mi demostración tuviera un error; por eso exige antes ≥ 6 puntos racionales exactos a 40 cifras, queda registrada en el informe y tiene pruebas negativas.
**Pendiente en Windows:** `test_comparador_demuestra_por_ramas_la_derivada_de_la_primitiva` y `test_comparador_registra_ambos_resultados_de_equals_y_demostracion` (código SymPy nuevo, **no ejecutado**).

## Sobre «comparación real sin que el respaldo resuelva los casos por el motor»
Ya corregido en la ronda anterior (W-5): el motor corre con `MATH_UNIVERSE_DISABLE_SYMPY=1` durante la comparación; `test_el_motor_se_ejecuta_sin_respaldo_sympy_en_la_comparacion` lo fija. El informe de Windows debe mostrar `sqrt(x)` y `tan(x)` como `LIMITACION_MOTOR`.
