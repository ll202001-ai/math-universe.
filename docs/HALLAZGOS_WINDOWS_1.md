# Hallazgos de la 1.ª validación en Windows (Python 3.15.2, SymPy 1.14.0)

**Resultado original conservado (reportado por el usuario):** 379 aprobadas · **3 falladas** · 1 deseleccionada (`-k "not corpus_completo"`) · 139.70 s.
Los tres fallos estaban en `tests/test_08_sympy.py`, el módulo que **nunca pude ejecutar** en mi entorno (sin SymPy). Es información real que mis pruebas internas no podían dar.

| # | Prueba | Causa | ¿Diferencia matemática? | Clasificación |
|---|---|---|---|---|
| 1 | `test_backend_sympy[differentiate-x^3-3*x**2]` | SymPy imprime `3*x**2`; `symbolic.run()` traduce a sintaxis del motor (`3*x^2`) vía `from_sympy_text`, para que el resultado se pueda volver a analizar. Esa traducción la añadí en una fase anterior y **no actualicé la expectativa** de esta prueba (estaba omitida, así que no lo vi). | **No.** `3*x^2` = `3*x**2` | Representación. Error mío en la prueba, no del motor |
| 2 | `test_backend_sympy[expand-(x+1)^2-...]` | Idéntica: `x**2 + 2*x + 1` vs `x^2 + 2*x + 1`. | **No.** | Representación (misma causa) |
| 3 | `test_respaldo_integral_cuando_el_motor_propio_no_puede[1/(x^3+1)]` | La prueba suponía que el motor propio no integra `1/(x^3+1)`. **Sí puede**: factoriza `x³+1=(x+1)(x²−x+1)` y usa fracciones parciales con cuadrático irreducible (`ln` + `atan`). Como el motor propio resolvió, **el respaldo SymPy no debía activarse** y no se activó (`method = integracion_simbolica_propia`). | **No.** Resultado verificado: `(1/3)ln|x+1| − (1/6)ln(x²−x+1) + (1/√3)·atan((2x−1)/√3)` (se comprobó a mano que coincide con la primitiva clásica); el verificador independiente (diferencias finitas) dio `passed`, y la integral definida 0→2 coincide con `scipy.quad` a 1e-9. | Expectativa obsoleta de la prueba. El comportamiento del motor era el correcto y el deseado (primero el motor propio) |

## Qué se cambió (y qué NO)
- **No se tocó el motor.** No hacía falta: no hay defecto de cálculo.
- Las pruebas no se «relajaron» para aprobar. Se **endurecieron**:
  - 1 y 2: ahora comprueban (a) que SymPy produce exactamente el crudo observado en Windows, (b) el contrato de representación (`res == "3*x^2"` y sin `**`) y (c) **equivalencia algebraica contra SymPy puro** (`simplify(res − ref) == 0`), no solo texto.
  - 3: se separó en dos pruebas: las integrales que el motor propio **no** puede (`sin(x)^2`, `x*atan(x)`, `sqrt(x)`) siguen exigiendo el respaldo; las que sí puede **prohíben** el respaldo (se sustituye `symbolic.run` por una función que falla si se llama) y se compara la primitiva propia con la de SymPy (derivada idéntica al integrando y diferencia constante).
- Nuevo `tests/test_14_hallazgos_windows.py` (9 pruebas, **sin SymPy**): traducción de sintaxis `**`/`Abs`/`log`/`E`/`I`, no tocar identificadores como `Exp1`, `1/(x^3+1)` contra `scipy.quad`, y que el respaldo no se invoque cuando el motor propio puede.

## Qué NO está probado aún
Las pruebas de `test_08` modificadas **no las pude ejecutar aquí** (sin SymPy). Pasan a validación en Windows: si fallan, es un hallazgo más.
Observación: que la comparación diferencial completa (`corpus_completo`) quedó deseleccionada en esa corrida; sigue pendiente ejecutarla (`pytest tests/test_08_sympy.py -k corpus_completo`; ≈5–10 min) y enviar `validacion\comparacion_sympy.json`.
