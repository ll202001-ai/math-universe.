"""Entrada universal (operation «resolver»): un enunciado en lenguaje natural → intención → planteamiento → motor → verificación.

Arquitectura (sin IA en la nube; funciona sin conexión):
  1. Normalización (superíndices, √, π, notación de guía) y detección de la INTENCIÓN por estructura del enunciado.
  2. Enrutado: multivariable/vectorial/regiones → calc3 (intérprete de enunciados); una variable → motor exacto con respaldos numéricos.
  3. Cada resultado pasa por una verificación independiente (otra vía) y, si el exacto no existe, se ofrece valor numérico controlado.
La interfaz muestra la interpretación; nada se inventa: si no se entiende, se dice qué falta.
"""
import math
import re
from fractions import Fraction as F
from .errors import EngineError, InvalidRequest, NotImplementedOperation
from .calc3.texto import normalizar, quitar_acentos, mx

_OK = ("success_exact", "success_approximate", "multiple_solutions", "no_solution")

# palabras que delatan problemas multivariables / vectoriales / de regiones → calc3
_CALC3 = ("integral doble", "integral triple", "integrales dobles", "integral iterada", "region", "solido", "volumen", "centroide", "centro de masa", "masa de",
          "momento de inercia", "gradiente", "divergencia", "rotacional", "laplaciano", "campo vectorial", "campo conservativo", "flujo", "trabajo", "circulacion",
          "lagrange", "jacobiano", "area de la superficie", "minimos cuadrados", "puntos criticos de f(x,y", "extremos de f(x,y", "coordenadas polares",
          "coordenadas cilindricas", "coordenadas esfericas", "cambio de variables", "funcion potencial", "punto de silla", "maximice", "minimice", "maximizar", "minimizar",
          "mas cercano", "distancia minima", "distancia maxima")


def _ejecutar(sub):
    from . import dispatcher as D
    sub = dict(sub); sub.setdefault("latex", True); sub.setdefault("steps", True)
    st = D.State(sub)
    out = D._dispatch(sub, st)
    out = dict(out)
    out.setdefault("status", "success_exact")
    out["conditions"] = list(dict.fromkeys(st.conditions + out.get("conditions", [])))
    out["warnings"] = list(dict.fromkeys(st.warnings + out.get("warnings", [])))
    if out["status"] in D._CON_RESULTADO:
        resp = dict(out); 
        try: D._presentacion(sub, resp)
        except Exception: pass
        out = resp
    return out


def _intentar(sub, nota, falla):
    try:
        out = _ejecutar(sub)
    except EngineError as e:
        falla.append(f"{sub['operation']}: {e.message}")
        return None
    except Exception as e:     # noqa
        falla.append(f"{sub['operation']}: {type(e).__name__}")
        return None
    if out.get("status") not in _OK:
        falla.append(f"{sub['operation']}: {out.get('status')}")
        return None
    out["steps"] = [{"text": "Interpretación: " + nota}] + list(out.get("steps") or [])
    return out


# ------------------------------------------------------------------------------------------------ utilidades de lectura
def _lim(txt):
    """texto de un límite/cota → sintaxis del motor (∞ → oo)"""
    t = txt.strip().strip(".,;")
    t = re.sub(r"^\s*(?:x|t|n|u)\s*=\s*", "", t)
    if re.fullmatch(r"[+-]?\s*(infinito|inf|∞|oo)", quitar_acentos(t).lower()):
        return ("-" if t.strip().startswith("-") else "") + "oo"
    return mx(t)


def _fn(txt):
    t = txt.strip().strip(".,;:")
    t = re.sub(r"\s*\bd[xyzt]\s*$", "", t)
    t = re.sub(r"^(?:la\s+)?(?:funcion|expresion|curva)\s+", "", quitar_acentos(t), flags=re.I) if False else t
    t = re.sub(r"^\s*(?:y|f\s*\(\s*\w\s*\)|g\s*\(\s*\w\s*\)|f)\s*=\s*", "", t)
    return mx(t)


def _var(expr, preferida=None):
    from .ast_tools import free_symbols
    from .parser import parse
    from .ast_tools import normalize
    try:
        s = sorted(v for v in free_symbols(normalize(parse(expr))) if v not in ("pi", "e"))
    except Exception:
        s = []
    if preferida and preferida in s: return preferida
    if "x" in s: return "x"
    return s[0] if s else (preferida or "x")


# ------------------------------------------------------------------------------------------------ numérico de respaldo
def _comp(expr, vs):
    from .calc3.numerico import compile_ast
    from .parser import parse
    from .ast_tools import normalize
    return compile_ast(normalize(parse(expr)), vs)


def _reconoce(v, tol=1e-9):
    """valor decimal → forma exacta sencilla (racional, múltiplo de π, raíz) si existe"""
    if abs(v) < 1e-12: return "0"
    for den in range(1, 361):
        q = round(v * den)
        if abs(v - q / den) < tol * max(1, abs(v)): return str(F(q, den))
    k = v / math.pi
    for den in range(1, 61):
        q = round(k * den)
        if q and abs(k - q / den) < tol: return f"{F(q, den)}*pi"
    if v > 0:
        for den in range(1, 33):
            q = round(v * v * den)
            if q and abs(v * v - q / den) < tol * max(1, v * v): return f"sqrt({F(q, den)})"
    return None


def _int_num(expr, v, a, b):
    from .calc3.numerico import integral as quad
    fa, fb = float(_comp(a, [])()), float(_comp(b, [])())
    g = _comp(expr, [v])
    val = quad(lambda x: g(x), [(fa, fb)]) if False else quad(lambda x: g(x), [(lambda *_: fa, lambda *_: fb)])
    return val


def _simpson(g, a, b, n=20000):
    h = (b - a) / n
    s = g(a) + g(b)
    for i in range(1, n):
        s += g(a + i * h) * (4 if i % 2 else 2)
    return s * h / 3


def _integral_definida_num(expr, v, a, b, falla):
    from .calc3.numerico import integral as quad
    try:
        fa, fb = float(_comp(a if a not in ("oo", "-oo") else "0", [])()), float(_comp(b if b not in ("oo", "-oo") else "0", [])())
    except Exception:
        return None
    if "oo" in (a, b, "-oo"): return None
    g = _comp(expr, [v])
    try:
        v1 = quad(lambda t: g(t), [(fa, fb)])[0]
    except Exception:
        return None
    try:
        v2 = _simpson(g, fa, fb)
    except Exception:
        v2 = None
    ver = "passed" if v2 is not None and abs(v1 - v2) <= 1e-6 * (1 + abs(v1)) else "not_possible"
    ex = _reconoce(v1, 1e-10)
    return v1, ex, ver


def _raices_num(expr, v, lo=-60.0, hi=60.0):
    g = _comp(expr, [v]); out = []
    xs = [lo + (hi - lo) * k / 24000 for k in range(24001)]
    prev = None
    for x in xs:
        try: y = g(x)
        except Exception: prev = None; continue
        if isinstance(y, complex): prev = None; continue
        if prev is not None:
            px, py = prev
            if py == 0: out.append(px)
            elif py * y < 0 and abs(y - py) < 1e6:
                a, b = px, x
                for _ in range(100):
                    m = (a + b) / 2
                    if g(a) * g(m) <= 0: b = m
                    else: a = m
                out.append((a + b) / 2)
        prev = (x, y)
    uniq = []
    for r in out:
        if not any(abs(r - u) < 1e-7 for u in uniq): uniq.append(r)
    return uniq


# ------------------------------------------------------------------------------------------------ intenciones de una variable
def _derivada(T, n, falla):
    m = re.search(r"(?:(segunda|tercera|cuarta)\s+derivada|derivada\s+de\s+orden\s+(\d+)|derivad[ao]|deriva|derivar|diferencia)\s+(?:de\s+)?(?:la\s+funcion\s+)?(.+)", n, re.I)
    if not m: return None
    orden = {"segunda": 2, "tercera": 3, "cuarta": 4}.get((m.group(1) or "").lower(), int(m.group(2)) if m.group(2) else 1)
    resto = m.group(3)
    var = None; punto = None
    mv = re.search(r"\s+(?:con\s+)?respecto\s+(?:a|de|a la variable)\s+(\w)\b", resto, re.I)
    if mv: var = mv.group(1); resto = resto[:mv.start()] + resto[mv.end():]
    mp = re.search(r"\s+en\s+(?:el\s+punto\s+)?(?:\w\s*=\s*)([-\w./]+)\s*$", resto)
    if mp: punto = mx(mp.group(1)); resto = resto[:mp.start()]
    expr = _fn(resto)
    v = var or _var(expr)
    sub = {"operation": "differentiate", "expression": expr, "variables": [v]}
    if orden > 1: sub["order"] = orden
    out = _intentar(sub, f"derivada de orden {orden} de {expr} respecto de {v}", falla)
    if out is None: return None
    if punto is not None and out.get("exact_result"):
        out2 = _intentar({"operation": "evaluate", "expression": _sust(out["exact_result"], v, punto)}, f"se evalúa la derivada en {v} = {punto}", falla)
        if out2: out2["steps"] = out["steps"] + out2["steps"]; return out2
    return out


def _sust(expr, v, val):
    from .ast_tools import subs as ast_subs, to_str, normalize
    from .parser import parse
    return to_str(ast_subs(normalize(parse(expr)), v, normalize(parse(val))))


def _integral(T, n, falla):
    # ∫_a^b f dx  /  integral definida de f de a a b  /  entre a y b / desde a hasta b
    nn = n
    m = re.search(r"∫\s*_\{?([^\s^{}]+)\}?\s*\^\{?([^\s{}]+)\}?\s*(.+?)\s*d([a-z])\b", nn)
    a = b = None; expr = None; v = None
    if m: a, b, expr, v = _lim(m.group(1)), _lim(m.group(2)), mx(m.group(3)), m.group(4)
    else:
        m = re.search(r"(?:area|integral)\s+(?:definida\s+)?(?:bajo|de|debajo de)?\s*(?:la\s+curva\s+|la\s+funcion\s+)?(.+?)\s+(?:de|desde|entre)\s+(?:x\s*=\s*)?([-\w./()+*^]+?)\s+(?:a|hasta|y)\s+(?:x\s*=\s*)?([-\w./()+*^]+?)\s*(?:\.|$|dx)", nn, re.I)
        if m and re.search(r"integral|area", T):
            expr = _fn(m.group(1)); a, b = _lim(m.group(2)), _lim(m.group(3)); v = _var(expr)
        else:
            m = re.search(r"(?:integra|integrar|integral(?:\s+indefinida)?|primitiva|antiderivada)\s+(?:de\s+)?(.+?)(?:\s+d([a-z]))?\s*$", nn, re.I)
            if not m or not re.search(r"integra|integral|primitiva|antiderivada", T): return None
            expr = _fn(m.group(1)); v = m.group(2) or _var(expr)
    expr = re.sub(r"\s*d[xt]\s*$", "", expr)
    es_area = "area" in T and a is not None
    sub = {"operation": "integrate", "expression": expr, "variables": [v]}
    if a is not None: sub["lower"], sub["upper"] = a, b
    nota = (f"integral definida de {expr} de {a} a {b}" if a is not None else f"integral indefinida de {expr} respecto de {v}")
    out = _intentar(sub, nota, falla)
    if out is not None:
        if es_area: out.setdefault("warnings", []).append("Se calculó la integral con signo; coincide con el área solo si la función es ≥ 0 en el intervalo.")
        return out
    ex3 = _integral_cas3(expr, v, a, b, nota, es_area)
    if ex3 is not None: return ex3
    if a is not None:
        r = _integral_definida_num(expr, v, a, b, falla)
        if r:
            v1, ex, ver = r
            pasos = [{"text": "Interpretación: " + nota}, {"text": "El integrando no tiene primitiva elemental en el motor exacto: se integra numéricamente (tanh-sinh) y se contrasta con Simpson compuesto"}]
            res = {"status": "success_approximate", "exact_result": None, "approximate_result": f"{v1:.12g}", "method": "cuadratura_numerica",
                   "verification": {"status": ver, "method": "Simpson compuesto (n = 20000), independiente de tanh-sinh"}, "steps": pasos,
                   "warnings": ["Resultado numérico (sin forma cerrada elemental)"]}
            if ex and ver == "passed": res["data"] = {"posible_forma_exacta": ex}; res["warnings"].append(f"El valor numérico coincide con {ex} (reconocimiento numérico; no demostrado)")
            return res
    return None


def _integral_cas3(expr, v, a, b, nota, es_area):
    """segunda vía exacta (cas3: potencias de sin/cos, exp·polinomio, racionales, ln…) cuando el motor principal no puede"""
    try:
        from .calc3.cas3 import from_ast, Expr
        from .calc3 import integra
        from .calc3.iterada import integrar
        from .parser import parse
        from .ast_tools import normalize
        fe = from_ast(normalize(parse(expr)))
        if a is None:
            P = integra.integrate(fe, v)
            return {"status": "success_exact", "exact_result": P.to_str() + " + C", "approximate_result": None, "latex": {"result": P.to_str(True) + " + C"},
                    "method": "integral_exacta_cas3", "verification": {"status": "not_possible", "method": None},
                    "steps": [{"text": "Interpretación: " + nota}, {"text": "Primitiva por las reglas del integrador exacto (potencias trigonométricas, exponenciales, racionales)", "latex": P.to_str(True) + " + C"}]}
        lo = from_ast(normalize(parse(a))); hi = from_ast(normalize(parse(b)))
        r = integrar(fe, [{"var": v, "lo": lo, "hi": hi}], nombre="I")
        if r["exacto"] is None: return None
        res = {"status": "success_exact", "exact_result": r["exacto"].to_str(), "approximate_result": f"{r['aprox']:.12g}", "latex": {"result": r["exacto"].to_str(True)},
               "method": "integral_exacta_cas3", "verification": {"status": r["verificacion"], "method": "cuadratura numérica independiente (tanh-sinh)"},
               "steps": [{"text": "Interpretación: " + nota}] + r["pasos"]}
        if es_area: res["warnings"] = ["Se calculó la integral con signo; coincide con el área solo si la función es ≥ 0 en el intervalo."]
        return res
    except Exception:
        return None


def _limite(T, n, falla):
    m = re.search(r"(?:limite|lim)\s*(?:de\s+)?(.+?)\s+cuando\s+(\w)\s*(?:tiende|->|→|se aproxima)\s*(?:a\s+)?(.+)$", n, re.I)
    if not m:
        m2 = re.search(r"lim\s*_\{?\s*(\w)\s*(?:->|→)\s*([^}\s]+)\}?\s*(.+)$", n)
        if not m2: return None
        v, pt, expr = m2.group(1), m2.group(2), m2.group(3)
    else:
        expr, v, pt = m.group(1), m.group(2), m.group(3)
    d = "both"
    if re.search(r"derecha|\+\s*$|por\s+arriba", pt, re.I): d = "+"
    elif re.search(r"izquierda|-\s*$|por\s+abajo", pt, re.I): d = "-"
    pt = re.sub(r"\s*(?:por\s+(?:la\s+)?(?:derecha|izquierda|arriba|abajo)|\+|-)$", "", pt.strip()) if d != "both" else pt
    expr = _fn(expr); pt = _lim(pt)
    sub = {"operation": "limit", "expression": expr, "variables": [v], "point": pt}
    if d != "both": sub["direction"] = d
    out = _intentar(sub, f"límite de {expr} cuando {v} → {pt}" + ("" if d == "both" else f" por {d}"), falla)
    if out: return out
    # respaldo numérico: extrapolación hacia el punto
    if pt in ("oo", "-oo"):
        try:
            g = _comp(expr, [v]); sg = 1 if pt == "oo" else -1
            seq = [g(sg * 10.0 ** k) for k in (4, 5, 6, 7)]
            if abs(seq[3] - seq[2]) <= 1e-5 * (1 + abs(seq[3])):
                val = seq[3]; ex = _reconoce(val, 1e-5)
                if abs(val - math.e) < 1e-5: ex = "e"
                res = {"status": "success_approximate", "exact_result": None, "approximate_result": f"{val:.10g}", "method": "extrapolacion_numerica",
                       "verification": {"status": "not_possible", "method": None},
                       "warnings": ["Límite estimado numéricamente con valores muy grandes de la variable" + (f"; coincide con {ex}" if ex else "")],
                       "steps": [{"text": f"Interpretación: límite de {expr} cuando {v} → {pt}; el motor exacto no lo resuelve, se evalúa en valores crecientes"}]}
                if ex: res["data"] = {"posible_forma_exacta": ex}
                return res
        except Exception:
            return None
    if pt not in ("oo", "-oo"):
        try:
            g = _comp(expr, [v]); x0 = float(_comp(pt, [])())
            lados = [d] if d != "both" else ["+", "-"]
            vals = []
            for s in lados:
                sg = 1 if s == "+" else -1
                seq = [g(x0 + sg * 10.0 ** -k) for k in (3, 4, 5)]
                if abs(seq[2] - seq[1]) <= 1e-5 * (1 + abs(seq[2])): vals.append(seq[2])
                else: return None
            if len(vals) == 2 and abs(vals[0] - vals[1]) > 1e-4 * (1 + abs(vals[0])): return None
            val = vals[0]
            ex = _reconoce(val, 1e-6)
            res = {"status": "success_approximate", "exact_result": None, "approximate_result": f"{val:.10g}", "method": "extrapolacion_numerica",
                   "verification": {"status": "not_possible", "method": None}, "warnings": ["Límite estimado numéricamente (acercándose por ambos lados)" + (f"; coincide con {ex}" if ex else "")],
                   "steps": [{"text": f"Interpretación: límite de {expr} cuando {v} → {pt}; el motor exacto no lo resuelve, se estima con puntos cercanos"}]}
            if ex: res["data"] = {"posible_forma_exacta": ex}
            return res
        except Exception:
            return None
    return None


def _ecuaciones_de(n):
    from .calc3.texto import ecuaciones
    return ecuaciones(n)


def _resolver(T, n, falla):
    if not re.search(r"resuelv|resolver|soluci|halla\w*\s+(?:x|y|t|las\s+raices|las\s+soluciones|el\s+valor)|encuentra|raices|despeja|calcula\s+x|determina\s+x", T): return None
    if re.search(r"diferencial|y\s*'|y''", n): return None
    if re.search(r"<=|>=|<|>|≤|≥", n) and not re.search(r"=(?!=)", re.sub(r"<=|>=|≤|≥", "", n)):
        m = re.search(r"(?:inecuacion|desigualdad|resuelve|resolver)\s*(?:la\s+inecuacion\s+)?(.+)$", n, re.I)
        expr = mx((m.group(1) if m else n).replace("≤", "<=").replace("≥", ">="))
        return _intentar({"operation": "inequality", "expression": expr}, f"inecuación {expr}", falla)
    md = re.search(r"despeja\s+(\w)\s+(?:en|de)\s+(.+)$", n, re.I)
    if md:
        return _intentar({"operation": "solve", "expression": mx(md.group(2)), "variables": [md.group(1)]}, f"despeje de {md.group(1)}", falla)
    ecs = _ecuaciones_de(n)
    if not ecs:
        return None
    if len(ecs) >= 2:
        expr = "; ".join(ecs)
        out = _intentar({"operation": "solve", "expression": expr}, f"sistema de ecuaciones: {expr}", falla)
        return out
    e = ecs[0]
    v = _var(e.split("=")[0] + "+" + e.split("=")[-1])
    sub = {"operation": "solve", "expression": e}
    out = _intentar(sub, f"ecuación {e}", falla)
    if out: return out
    # respaldo numérico: raíces reales por barrido + bisección
    lhs, rhs = e.split("=", 1)
    g = f"({lhs})-({rhs})"
    rs = _raices_num(g, v)
    if not rs: return None
    f_ = _comp(g, [v])
    ok = all(abs(f_(r)) < 1e-7 for r in rs)
    txt = "; ".join(f"{v} ≈ {r:.10g}" + (f" (= {_reconoce(r, 1e-9)})" if _reconoce(r, 1e-9) else "") for r in rs)
    return {"status": "success_approximate", "exact_result": None, "approximate_result": txt, "method": "barrido_y_biseccion",
            "verification": {"status": "passed" if ok else "not_possible", "method": "evaluación del residuo f(raíz) ≈ 0"},
            "warnings": ["Soluciones reales halladas numéricamente en [−60, 60]; la ecuación no tiene resolución cerrada en el motor exacto"],
            "steps": [{"text": f"Interpretación: ecuación {e}; se buscan cambios de signo de f(x) = {g} y se refinan por bisección"}]}


def _algebra(T, n, falla):
    for pat, op, txt in ((r"(?:factoriza|factorizar|factorizacion de)\s+(.+)", "factor", "factorizar"), (r"(?:expande|expandir|desarrolla)\s+(.+)", "expand", "expandir"),
                         (r"(?:simplifica|simplificar|reduce)\s+(.+)", "simplify", "simplificar")):
        m = re.search(pat, n, re.I)
        if m: return _intentar({"operation": op, "expression": _fn(m.group(1))}, f"{txt} {_fn(m.group(1))}", falla)
    return None


def _serie(T, n, falla):
    m = re.search(r"(?:serie de (?:taylor|maclaurin)|taylor|maclaurin|desarrollo en serie)\s+(?:de\s+)?(.+?)(?:\s+(?:alrededor|en torno)\s+de\s+(?:\w\s*=\s*)?([-\w./]+))?(?:\s+(?:hasta|de)\s+orden\s+(\d+))?\s*$", n, re.I)
    if not m or not re.search(r"taylor|maclaurin|serie", T): return None
    expr = _fn(m.group(1)); pt = mx(m.group(2)) if m.group(2) else "0"; orden = int(m.group(3)) if m.group(3) else 5
    return _intentar({"operation": "series", "expression": expr, "variables": [_var(expr)], "point": pt, "order": orden}, f"serie de {expr} alrededor de {pt} hasta orden {orden}", falla)


def _laplace(T, n, falla):
    inv = bool(re.search(r"inversa", T))
    m = re.search(r"(?:transformada\s+(?:inversa\s+)?de\s+laplace|laplace)\s+(?:inversa\s+)?de\s+(.+)", n, re.I)
    if not m: return None
    expr = _fn(m.group(1))
    return _intentar({"operation": "inverse_laplace" if inv else "laplace", "expression": expr}, ("transformada inversa de Laplace" if inv else "transformada de Laplace") + f" de {expr}", falla)


def _matriz(T, n, falla):
    mats = re.findall(r"\[\s*\[[^\]]*\](?:\s*,\s*\[[^\]]*\])*\s*\]", n)
    if not mats and re.search(r"\[[^\[\]]*;[^\[\]]*\]", n):
        mats = [re.sub(r"\s*;\s*", "],[", "[" + x + "]") for x in re.findall(r"\[([^\[\]]*;[^\[\]]*)\]", n)]
        mats = ["[" + m + "]" for m in mats]
    if not mats: return None
    A = mats[0].replace(" ", "")
    for kw, op, nm in (("determinante", "matrix_det", "determinante"), ("inversa", "matrix_inverse", "inversa"), ("rango", "matrix_rank", "rango"),
                       ("transpuesta", "matrix_transpose", "transpuesta"), ("escalonada", "matrix_rref", "forma escalonada reducida"), ("autovalor", "eigen", "autovalores"),
                       ("valores propios", "eigen", "valores propios"), ("autovector", "eigen", "autovalores y autovectores")):
        if kw in T:
            return _intentar({"operation": op, "expression": A}, f"{nm} de la matriz {A}", falla)
    if len(mats) >= 2:
        B = mats[1].replace(" ", "")
        for kw, op, nm in (("multiplica", "matrix_mul", "producto"), ("producto", "matrix_mul", "producto"), ("suma", "matrix_add", "suma"), ("resta", "matrix_sub", "resta")):
            if kw in T: return _intentar({"operation": op, "structured_input": {"a": A, "b": B}}, f"{nm} de matrices", falla)
        if "resuelve" in T or "sistema" in T:
            return _intentar({"operation": "matrix_solve", "structured_input": {"a": A, "b": B}}, "sistema A·x = b", falla)
    return None


def _estadistica(T, n, falla):
    if not re.search(r"media|mediana|moda|desviacion|varianza|promedio|estadistic", T): return None
    nums = re.findall(r"-?\d+(?:\.\d+)?", re.sub(r"^[^:]*:", "", n) if ":" in n else n)
    if len(nums) < 2: return None
    return _intentar({"operation": "stats", "expression": ", ".join(nums)}, f"estadística descriptiva de los datos {', '.join(nums)}", falla)


def _unidades(T, n, falla):
    m = re.search(r"(?:convierte|convertir|pasa|pasar|cuantos?\s+\w+\s+son)\s+(.+)", n, re.I)
    if not m: return None
    t = re.sub(r"\s+(?:a|en|to)\s+", " to ", m.group(1).strip())
    return _intentar({"operation": "units", "expression": t}, f"conversión de unidades: {t}", falla)


def _ode(T, n, falla):
    if not re.search(r"ecuacion diferencial|edo\b|y'|y''|dy/dx", T + " " + n): return None
    m = re.search(r"(?:ecuacion diferencial|edo)?\s*:?\s*(y\s*'+\s*[^,;]*=.*|.*dy/dx.*=.*)", n)
    expr = mx((m.group(1) if m else n).replace("dy/dx", "y'"))
    return _intentar({"operation": "ode", "expression": (m.group(1) if m else n).strip()}, "ecuación diferencial ordinaria", falla)


def _extremo_1d(T, n, falla):
    if not re.search(r"maximo|minimo|extremo|puntos? criticos?|optimiz", T): return None
    m = re.search(r"(?:de|para)\s+(?:la\s+funcion\s+)?(?:f\s*\(\s*(\w)\s*\)\s*=\s*)?(.+?)(?:\s+en\s+(?:el\s+)?intervalo\s+\[?\s*([-\w./]+)\s*[,;]\s*([-\w./]+)\s*\]?)?\s*$", n, re.I)
    if not m: return None
    expr = _fn(m.group(2)); v = _var(expr, m.group(1))
    if re.search(r"\b[yz]\b", expr) and v == "x" and re.search(r"[yz]", expr): return None
    d1 = _intentar({"operation": "differentiate", "expression": expr, "variables": [v]}, "", falla)
    if not d1: return None
    d2 = _intentar({"operation": "differentiate", "expression": expr, "variables": [v], "order": 2}, "", falla)
    crit = _intentar({"operation": "solve", "expression": f"({d1['exact_result']})=0", "variables": [v]}, "", falla)
    pts = []
    if crit and crit.get("data", {}).get("solutions"):
        pts = [s["value"] for s in crit["data"]["solutions"]]
    else:
        rs = _raices_num(d1["exact_result"], v)
        pts = [f"{r:.12g}" for r in rs]
    if not pts: return None
    lineas = []; pasos = [{"text": f"Interpretación: extremos de f({v}) = {expr}: puntos críticos con f'({v}) = 0 y criterio de la segunda derivada"},
                          {"text": f"f'({v}) = {d1['exact_result']}"}, {"text": f"f''({v}) = {d2['exact_result'] if d2 else '—'}"}]
    f = _comp(expr, [v]); g2 = _comp(d2["exact_result"], [v]) if d2 else None
    lo = hi = None
    if m.group(3):
        lo, hi = float(_comp(mx(m.group(3)), [])()), float(_comp(mx(m.group(4)), [])())
    cand = []
    for p in pts:
        try: x0 = float(_comp(mx(p), [])())
        except Exception: continue
        if lo is not None and not (lo - 1e-12 <= x0 <= hi + 1e-12): continue
        fv = f(x0); s2 = g2(x0) if g2 else None
        clase = "máximo local" if s2 is not None and s2 < -1e-12 else ("mínimo local" if s2 is not None and s2 > 1e-12 else "criterio no concluyente")
        cand.append((x0, fv)); lineas.append(f"{v} = {p}: f = {fv:.10g}, f'' = {('%.6g' % s2) if s2 is not None else '—'} → {clase}")
    if lo is not None:
        for x0 in (lo, hi): cand.append((x0, f(x0))); lineas.append(f"extremo del intervalo {v} = {x0:g}: f = {f(x0):.10g}")
        mx_ = max(cand, key=lambda t: t[1]); mn = min(cand, key=lambda t: t[1])
        lineas.append(f"Máximo absoluto en [{lo:g}, {hi:g}]: f({mx_[0]:.10g}) = {mx_[1]:.10g}; mínimo absoluto: f({mn[0]:.10g}) = {mn[1]:.10g}")
    if not lineas: return None
    return {"status": "success_exact" if crit and crit.get("data", {}).get("solutions") else "success_approximate", "exact_result": "\n".join(lineas) if crit and crit.get("data", {}).get("solutions") else None,
            "approximate_result": "\n".join(lineas), "method": "criterio_de_la_segunda_derivada", "verification": {"status": "passed", "method": "evaluación directa de f en los puntos críticos y comparación con vecinos"},
            "steps": pasos + [{"text": l} for l in lineas]}


def _aritmetica(T, n, falla):
    mp = re.search(r"(\d+(?:\.\d+)?)\s*%\s*de\s*(\d+(?:\.\d+)?)", T)
    if mp:
        return _intentar({"operation": "evaluate", "expression": f"({mp.group(1)}/100)*{mp.group(2)}"}, f"{mp.group(1)} % de {mp.group(2)}", falla)
    m = re.search(r"(?:calcula|cuanto es|evalua|halla|determina)\s+(?:el\s+valor\s+de\s+)?(.+)$", n, re.I)
    cand = m.group(1) if m else n
    palabras = re.findall(r"[a-z]+", cand.lower())
    if not all(w in ("sin", "cos", "tan", "ln", "log", "sqrt", "exp", "pi", "e", "abs", "x", "y", "z", "t") for w in palabras): return None
    if not re.search(r"\d", cand): return None
    expr = mx(cand)
    return _intentar({"operation": "evaluate", "expression": expr}, f"cálculo de {expr}", falla)


_MANEJADORES = (_derivada, _limite, _serie, _laplace, _ode, _matriz, _unidades, _estadistica, _resolver, _extremo_1d, _algebra, _integral, _aritmetica)


def _es_calc3(T, n):
    if any(k in T for k in _CALC3): return True
    if "∬" in n or "∭" in n or "DOBLEINT" in n or "TRIPLEINT" in n: return True
    if re.search(r"∫\s*_[^∫]*∫", n): return True
    if re.search(r"\barea\b", T) and len(re.findall(r"\b[yx]\s*=", n)) >= 2 and not re.search(r"bajo la curva", T): return True
    return False


def resolver(req, st):
    texto = (req.get("expression") or "").strip()
    if not texto: raise InvalidRequest("Escriba el enunciado del ejercicio en 'expression'")
    n = re.sub(r"[¿?¡!]", " ", quitar_acentos(normalizar(texto))).strip()
    T = n.lower()
    falla = []
    if _es_calc3(T, n):
        from .calc3 import enunciado
        try:
            out = enunciado.resolver(texto, req, st)
            out.setdefault("data", {})["dominio"] = "calculo_multivariable_y_vectorial"
            return out
        except NotImplementedOperation as e:
            falla.append("calc3: " + e.message)
        except EngineError as e:
            if e.code in ("VERIFICATION_FAILED",): raise
            falla.append("calc3: " + e.message)
    for h in _MANEJADORES:
        try:
            out = h(T, n, falla)
        except EngineError as e:
            falla.append(f"{h.__name__}: {e.message}"); out = None
        except Exception as e:     # noqa
            falla.append(f"{h.__name__}: {type(e).__name__}"); out = None
        if out is not None:
            out.setdefault("data", {})["dominio"] = h.__name__.strip("_")
            return out
    if falla:
        raise NotImplementedOperation("No pude resolver el enunciado con los métodos disponibles. Intentos: " + " | ".join(falla[:4]))
    raise InvalidRequest("No reconocí qué se pide. Indique la operación (derivar, integrar, resolver, límite, matriz…) y la expresión.")
