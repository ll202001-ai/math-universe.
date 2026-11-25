"""Catálogo EJECUTABLE de lo que el motor NO soporta o resuelve de forma incompleta.
La documentación (docs/NO_SOPORTADO.md) se GENERA ejecutando estos casos (tools/generar_no_soportado.py) y una prueba
comprueba que sigue al día: si el motor mejora y un caso empieza a funcionar, la prueba falla y obliga a actualizar el catálogo.
Dos secciones:
  A) NO_SOPORTADO: el motor responde status 'unsupported' (o equivalente) y NO entrega un resultado.
  B) INCOMPLETO: el motor entrega un resultado correcto pero NO completo / no simplificado al máximo (se indica qué falta)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# (área, operación, expresión, extras, qué falta)
NO_SOPORTADO = [
    ("Ecuaciones", "solve", "sqrt(x)=x-2", {}, "ecuaciones radicales"),
    ("Ecuaciones", "solve", "abs(x)=3", {}, "valor absoluto"),
    ("Ecuaciones", "solve", "exp(x)=2", {}, "exponenciales"),
    ("Ecuaciones", "solve", "2^x=8", {}, "exponenciales con base numérica"),
    ("Ecuaciones", "solve", "ln(x)=0", {}, "logaritmos"),
    ("Ecuaciones", "solve", "sin(x)=0", {}, "trigonométricas"),
    ("Ecuaciones", "solve", "x^3-2=0", {}, "cúbicas irreducibles sobre Q (radicales cúbicos)"),
    ("Ecuaciones", "solve", "x^3+x+1=0", {}, "cúbicas irreducibles sobre Q"),
    ("Sistemas", "solve", "x^2+y^2=1; x=y", {}, "sistemas no lineales"),
    ("Sistemas", "solve", "x*y=1; x+y=2", {}, "sistemas no lineales"),
    ("Despeje", "solve", "x^2=a", {"variables": ["x"]}, "despeje de grado ≥ 2 en la variable"),
    ("Despeje", "solve", "A=pi*r^2", {"variables": ["r"]}, "despeje de grado ≥ 2 en la variable"),
    ("Integrales", "integrate", "sin(x)^2", {"variables": ["x"]}, "potencias/productos de funciones trascendentes"),
    ("Integrales", "integrate", "sin(x)*cos(x)", {"variables": ["x"]}, "productos de funciones trascendentes"),
    ("Integrales", "integrate", "sqrt(x)", {"variables": ["x"]}, "integral de raíces/potencias fraccionarias"),
    ("Integrales", "integrate", "1/sqrt(x)", {"variables": ["x"]}, "integral de raíces/potencias fraccionarias"),
    ("Integrales", "integrate", "tan(x)", {"variables": ["x"]}, "tan"),
    ("Integrales", "integrate", "exp(x^2)", {"variables": ["x"]}, "argumento no lineal en funciones trascendentes"),
    ("Integrales", "integrate", "sin(x)/x", {"variables": ["x"]}, "cocientes con funciones trascendentes"),
    ("Integrales", "integrate", "x^n", {"variables": ["x"]}, "exponente simbólico"),
    ("Integrales", "integrate", "2^x", {"variables": ["x"]}, "exponenciales con base distinta de e"),
    ("Integrales", "integrate", "x^(1/3)", {"variables": ["x"]}, "potencias fraccionarias"),
    ("Integrales", "integrate", "abs(x)", {"variables": ["x"], "lower": "-1", "upper": "1"}, "valor absoluto"),
    ("Integrales", "integrate", "1/x", {"variables": ["x"], "lower": "-1", "upper": "1"}, "integrales impropias (singularidad interior)"),
    ("Integrales", "integrate", "x*ln(x)", {"variables": ["x"], "lower": "0", "upper": "1"}, "integrales impropias (extremo singular)"),
    ("Límites", "limit", "(1+1/x)^x", {"variables": ["x"], "point": "+oo"}, "exponentes variables"),
    ("Límites", "limit", "x^x", {"variables": ["x"], "point": "0", "direction": "+"}, "exponentes variables"),
    ("Límites", "limit", "x*sin(1/x)", {"variables": ["x"], "point": "0"}, "argumentos singulares de funciones trascendentes"),
    ("Límites", "limit", "exp(x)/x", {"variables": ["x"], "point": "+oo"}, "exp en infinito"),
    ("Límites", "limit", "ln(x)/x", {"variables": ["x"], "point": "+oo"}, "ln en infinito / en 0"),
    ("Límites", "limit", "x*ln(x)", {"variables": ["x"], "point": "0", "direction": "+"}, "ln en 0"),
    ("Límites", "limit", "sqrt(x^2+x)-x", {"variables": ["x"], "point": "+oo"}, "raíces con término constante nulo"),
    ("Límites", "limit", "(x-1)/abs(x-1)", {"variables": ["x"], "point": "1"}, "valor absoluto"),
    ("Aritmética", "evaluate", "sqrt(-4)", {}, "números complejos fuera de ecuaciones con supuesto complex"),
    ("Aritmética", "evaluate", "(-1)^(1/2)", {}, "raíz de índice par de un negativo"),
    ("Simbólico", "simplify", "foo(x)", {}, "funciones desconocidas"),
]

# (área, operación, expresión, extras, qué falta, comprobación del resultado entregado)
INCOMPLETO = [
    ("Factorización", "factor", "x^2-y^2+x-y", {}, "polinomios multivariantes NO homogéneos: se devuelve sin factorizar (con aviso)",
     lambda r: r["status"] == "success_exact" and r["exact_result"] == "x^2 - y^2 + x - y" and bool(r["warnings"])),
    ("Simplificación", "simplify", "sin(x)^2+cos(x)^2", {}, "identidades trigonométricas: no se reduce a 1",
     lambda r: r["status"] == "success_exact" and r["exact_result"] != "1"),
    ("Simplificación", "simplify", "1/(sqrt(2)-1)", {}, "racionalización de denominadores: no se transforma en sqrt(2)+1",
     lambda r: r["status"] == "success_exact" and r["exact_result"] == "1/(sqrt(2) - 1)"),
    ("Simplificación", "simplify", "sqrt(x)*sqrt(x)", {}, "sqrt(x)^2 no se reduce a x (con condición x ≥ 0)",
     lambda r: r["status"] == "success_exact" and r["exact_result"] == "sqrt(x)^2"),
    ("Aritmética", "evaluate", "atan(1)", {}, "valores exactos de funciones trigonométricas inversas (atan(1) no se reduce a pi/4)",
     lambda r: r["status"] == "success_exact" and r["exact_result"] == "atan(1)"),
    ("Derivadas", "differentiate", "x^3*sin(x)", {"variables": ["x"], "order": 2}, "verificación independiente de derivadas de orden ≥ 2 (verification = not_possible)",
     lambda r: r["status"] == "success_exact" and r["verification"]["status"] == "not_possible"),
    ("Aritmética", "evaluate", "floor(7/2)", {}, "gcd/lcm/mod/floor/ceil: sin segunda vía de verificación (verification = not_possible)",
     lambda r: r["status"] == "success_exact" and r["verification"]["status"] == "not_possible"),
]


def ejecutar():
    os.environ["MATH_UNIVERSE_DISABLE_SYMPY"] = "1"
    from math_universe_engine.dispatcher import handle
    A, B = [], []
    for area, op, expr, extra, falta in NO_SOPORTADO:
        r = handle({"operation": op, "expression": expr, **extra})
        A.append({"area": area, "op": op, "expr": expr, "falta": falta, "status": r["status"],
                  "mensaje": (r.get("error") or {}).get("message", ""), "devolvio_resultado": r.get("exact_result") is not None})
    for area, op, expr, extra, falta, chk in INCOMPLETO:
        r = handle({"operation": op, "expression": expr, **extra})
        B.append({"area": area, "op": op, "expr": expr, "falta": falta, "status": r["status"], "resultado": r.get("exact_result"),
                  "aprox": r.get("approximate_result"), "verificacion": r["verification"]["status"], "avisos": r["warnings"], "cumple": bool(chk(r))})
    return A, B


def generar_markdown():
    from math_universe_engine import __version__
    A, B = ejecutar()
    L = [f"# Lo que el motor NO soporta o resuelve de forma incompleta (motor {__version__})", "",
         "**Este archivo se genera ejecutando `audit/no_soportado.py` (`python tools/generar_no_soportado.py`).** Cada fila es un caso real ejecutado;",
         "una prueba (`tests/test_12_no_soportado.py`) falla si el comportamiento cambia sin actualizar este documento.", "",
         "## A. No soportado: el motor responde `unsupported` y NO entrega resultado", "",
         "| Área | Operación | Entrada | Qué falta | Estado | Mensaje del motor |", "|---|---|---|---|---|---|"]
    for x in A:
        L.append(f"| {x['area']} | {x['op']} | `{x['expr']}` | {x['falta']} | `{x['status']}` | {x['mensaje'][:110]} |")
    L += ["", "## B. Incompleto: el motor entrega un resultado CORRECTO pero no completo", "",
          "| Área | Operación | Entrada | Qué falta | Resultado entregado | Verificación |", "|---|---|---|---|---|---|"]
    for x in B:
        res = x["resultado"] if x["resultado"] is not None else x["aprox"]
        L.append(f"| {x['area']} | {x['op']} | `{x['expr']}` | {x['falta']} | `{res}` | `{x['verificacion']}` |")
    L += ["", "## C. Otras limitaciones de alcance (no son casos de entrada única)",
          "- Factorización univariante: exhaustiva (Kronecker por grado) con tope de candidatos; si se agota, `data.factorization_complete = false` y aviso explícito. Puede ser **lenta** para grado alto (segundos a decenas de segundos).",
          "- Verificación: toda comprobación numérica usa puntos de muestra; **no es una demostración formal**.",
          "- Sistemas lineales: sin parámetros simbólicos. Ecuaciones: dominio real por defecto; complejas solo con `assumptions: {x: complex}`.",
          "- `assumptions` no se aplican a derivadas, integrales ni límites (se avisa).",
          "- Identificadores de varias letras son símbolos únicos (`at` ≠ `a*t`).",
          "- Respaldo SymPy: **no probado con SymPy real** hasta ejecutar `test_08_sympy.py` en un entorno con SymPy.",
          "- Cualquier entrada fuera de estas tablas **no está garantizada**: «no aparece aquí» no significa «soportado»."]
    return "\n".join(L) + "\n"
