"""Comparación diferencial MOTOR PROPIO vs SymPy.   Ejecutar donde SymPy está instalado:  python audit/comparar_sympy.py

Principios anti-sesgo (el comparador NO debe favorecer al motor propio):
  1. El texto del motor se interpreta con el parser de SymPy (no con el del motor) y se evalúa en PUNTOS RACIONALES EXACTOS
     (sin ruido de coma flotante) a 40 cifras; tolerancia relativa 1e-25.
  2. Hace falta un MÍNIMO de puntos comparados (MIN_PUNTOS). Si no se alcanza, el caso es NO_CONCLUYENTE (nunca EQUIVALENTE).
  3. Si un lado está definido y el otro no en un punto, es DIFERENCIA (no se omite en silencio).
  4. Además de la comparación numérica se intenta confirmación simbólica (`Expr.equals`): si responde False, es DIFERENCIA.
  5. Los dominios (singularidades reales) se comparan y una discrepancia es DIFERENCIA_DOMINIO.
  6. Una "convención" solo se acepta si coincide EXACTAMENTE con la documentada en CONVENCIONES; cualquier otra diferencia es DIFERENCIA.
  7. Primitivas: la derivada de cada primitiva se compara con el INTEGRANDO (no solo entre sí).
  8. Si SymPy no produce referencia (error, no resuelto, plazo), el caso es SIN_REFERENCIA_SYMPY: NO está validado cruzadamente y se informa.
  9. Cada llamada a SymPy corre en un proceso hijo con plazo: un `simplify` colgado no bloquea la validación.
Veredictos: IDENTICO · EQUIVALENTE · CONVENCION_DOCUMENTADA · DIFERENCIA · DIFERENCIA_DOMINIO · NO_CONCLUYENTE · LIMITACION_MOTOR ·
            SIN_REFERENCIA_SYMPY · AMBOS_NO_SOPORTAN · ERROR_COMPARADOR.   Todo lo que no sea IDENTICO/EQUIVALENTE/CONVENCION_DOCUMENTADA
            /LIMITACION_MOTOR/AMBOS_NO_SOPORTAN requiere análisis y aparece en el informe como hallazgo.
Nota: sympify/parse_expr usan eval; aquí solo se alimentan con el corpus y con la salida del propio motor (herramienta de prueba, no producto)."""
import json, math, os, re, sys, cmath, traceback
from fractions import Fraction
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from math_universe_engine.dispatcher import handle



# ---------------------------------------------------------------- adaptador SymPy (delgado a propósito)
MIN_PUNTOS = 6
PUNTOS = [Fraction(n, d) for n, d in [(37, 100), (91, 100), (143, 100), (217, 100), (29, 10), (18, 5), (7, 3), (11, 7), (13, 4), (5, 9),
                                      (-58, 100), (-129, 100), (-12, 5), (-7, 3), (-11, 6), (-3, 7)]]
PLAZO_SYMPY_S = 90


class ComparadorError(Exception):
    pass


def no_derivable_por_cocientes(f, k, hs):
    """True si los cocientes incrementales laterales de f en k tienen límites DISTINTOS (p. ej. |x| en 0), False si coinciden,
    None si no es decidible. f: Fraction -> número. Independiente del motor."""
    try:
        difs = []
        for h in hs:
            qp = (f(k + h) - f(k)) / float(h)
            qm = (f(k) - f(k - h)) / float(h)
            difs.append(abs(qp - qm) > 1e-3 * (1 + abs(qp) + abs(qm)))
        return all(difs) if any(difs) else False
    except Exception:
        return None


class SympyAdapter:
    name = "sympy"

    def __init__(self):
        import sympy, mpmath
        self.sp = sympy
        self.mp = mpmath
        self.x = sympy.Symbol("x", real=True)

    def versions(self):
        return {"sympy": self.sp.__version__, "mpmath": self.mp.__version__}

    def parse(self, text, evaluate=True):
        sp = self.sp
        t = text.replace("^", "**").replace("−", "-")
        t = re.sub(r"(?<![A-Za-z_\d.])(\d+(?:\.\d+)?)\s*(?=[A-Za-z(])", r"\1*", t)        # 2x -> 2*x ; 2( -> 2*(
        t = re.sub(r"\)\s*(?=[A-Za-z0-9(])", ")*", t)                                      # )( -> )*(
        t = t.replace("+oo", "oo")
        names = set(re.findall(r"[A-Za-z_]\w*", t))
        loc = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "ln": sp.log, "log": sp.log, "sqrt": sp.sqrt,
               "abs": sp.Abs, "asin": sp.asin, "acos": sp.acos, "atan": sp.atan, "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
               "pi": sp.pi, "oo": sp.oo, "e": sp.E, "i": sp.I}
        for n in names:
            if n not in loc: loc[n] = sp.Symbol(n, real=True)
        loc["x"] = self.x
        return sp.sympify(t, locals=loc, evaluate=evaluate)

    def puntos(self):
        return list(PUNTOS)

    def num(self, expr, env):
        """Evalúa en puntos racionales EXACTOS a 40 cifras; complex/float; ±inf; ZeroDivisionError si no está definida."""
        sp = self.sp
        sub = {sp.Symbol(k, real=True): sp.Rational(v.numerator, v.denominator) for k, v in env.items()}
        v = expr.subs(sub) if sub else expr
        v = sp.N(v, 40)
        if v.has(sp.zoo) or v.has(sp.nan): raise ZeroDivisionError("indefinido")
        if v.free_symbols or not (v.is_number or v in (sp.oo, -sp.oo)):
            # Diagnóstico explícito (hallazgo de Windows nº7): nunca dejar que una comparación relacional sin resolver
            # (TypeError opaco) esconda la causa. Se informa la expresión exacta.
            raise ComparadorError(f"no se pudo reducir a un número: símbolos libres={sorted(map(str, v.free_symbols))} srepr={self.sp.srepr(v)[:300]}")
        if v == sp.oo: return float("inf")
        if v == -sp.oo: return float("-inf")
        re_, im_ = sp.re(v), sp.im(v)
        if abs(im_) < sp.Float("1e-30"): return float(re_)
        return complex(re_, im_)

    def indefinida_en(self, text, k):
        """¿La expresión ORIGINAL (sin evaluación automática al construirla: x/x NO se reduce a 1) es indefinida en x=k?"""
        sp = self.sp
        try:
            ex = self.parse(text, evaluate=False)
            v = ex.subs(self.x, sp.Rational(k.numerator, k.denominator))
            # Evaluar EXACTAMENTE el árbol sustituido antes de N(): sp.N sobre un 0/0 sin evaluar, p. ej. (8 - 1*8)/(2 - 1*2),
            # devuelve basura numérica (0.e+6, 1e138) en lugar de nan/zoo y ocultaba la singularidad (fallo de CI 2026-11-25).
            v = v.doit()
            v = sp.N(v, 30) if not v.has(sp.zoo, sp.nan) else v
            return bool(v.has(sp.zoo) or v.has(sp.nan))
        except Exception:
            return None

    def no_derivable_en(self, text, k):
        sp = self.sp
        try:
            ex = self.parse(text)
            return no_derivable_por_cocientes(lambda t: complex(sp.N(ex.subs(self.x, sp.Rational(t.numerator, t.denominator)), 30)), k,
                                              (Fraction(1, 10**6), Fraction(1, 10**9)))
        except Exception:
            return None

    def igual_simbolico_por_ramas(self, a, b):
        """DEMOSTRACIÓN exacta (no muestreo) de a-b == 0 sobre R menos las raíces de los argumentos de Abs()/sign().
        Se parte la recta real en los intervalos que delimitan las raíces reales de cada argumento u (polinomio); en cada intervalo
        u tiene signo constante (se evalúa EXACTAMENTE en un punto racional interior), así Abs(u)=±u y sign(u)=±1, y la diferencia
        queda como función algebraica cuya nulidad decide `cancel/simplify`. True = demostrado en todos los intervalos; None = no se pudo.
        Existe porque `Expr.equals` es un procedimiento heurístico (simplificación + muestreo numérico) y con Abs/sign puede dar False o None
        aunque la identidad sea exacta (sign(u)/|u| = 1/u no lo aplica SymPy automáticamente)."""
        sp = self.sp
        try:
            d = sp.together(a - b)
            ats = list(d.atoms(sp.Abs, sp.sign))
            raices = set()
            for at in ats:
                u = at.args[0]
                if not u.is_polynomial(self.x): return None
                P = sp.Poly(u, self.x)
                if P.degree() >= 1:
                    for r in sp.real_roots(P): raices.add(r)
            pts = sorted((sp.N(r, 40) for r in raices), key=lambda v: float(v))
            if not pts: muestras = [sp.Integer(0)]
            else:
                muestras = [sp.Rational(sp.floor(pts[0]) - 1)] + [sp.Rational(sp.N((pts[i] + pts[i + 1]) / 2, 25))
                                                                    for i in range(len(pts) - 1)] + [sp.Rational(sp.ceiling(pts[-1]) + 1)]
            for m in muestras:
                rep = {}
                for at in ats:
                    u = at.args[0]
                    sg = 1 if u.subs(self.x, m) > 0 else -1               # exacto: m es racional y u no se anula en el intervalo
                    rep[at] = sg * u if isinstance(at, sp.Abs) else sp.Integer(sg)
                e = d.xreplace(rep)
                if sp.cancel(sp.together(e)) != 0 and sp.simplify(e) != 0: return None
            return True
        except Exception:
            return None

    def limite_en(self, text, k):
        sp = self.sp
        try: return str(sp.limit(self.parse(text), self.x, sp.Rational(k.numerator, k.denominator)))
        except Exception: return None

    def derivada(self, expr, orden=1):
        return self.sp.diff(expr, self.x, orden)

    def misma_repr(self, a, b):
        try: return self.sp.srepr(a) == self.sp.srepr(b)
        except Exception: return False

    def igual_simbolico(self, a, b):
        """True/False/None (None = SymPy no pudo decidir)."""
        try:
            r = (a - b).equals(0)
            return None if r is None else bool(r)
        except Exception:
            return None

    def reference(self, case):
        sp, x = self.sp, self.x
        op, e = case["op"], case["expr"]
        try:
            if op in ("simplify", "expand", "factor"):
                ex = self.parse(e)
                fn = {"simplify": sp.simplify, "expand": sp.expand, "factor": sp.factor}[op]
                r = fn(ex)
                return {"tipo": "expr", "obj": r, "texto": str(r), "original": ex, "singularidades": self._singularidades(ex)}
            if op == "differentiate":
                r = sp.diff(self.parse(e), x, case.get("order", 1)); return {"tipo": "expr", "obj": r, "texto": str(r)}
            if op == "integrate":
                ex = self.parse(e)
                if "lower" in case:
                    r = sp.integrate(ex, (x, self.parse(case["lower"]), self.parse(case["upper"])))
                    if r.has(sp.Integral): return {"tipo": "no_resuelto"}
                    return {"tipo": "valor", "valor": float(sp.N(r, 30)), "texto": str(r)}
                r = sp.integrate(ex, x)
                if r.has(sp.Integral): return {"tipo": "no_resuelto"}
                return {"tipo": "primitiva", "obj": r, "texto": str(r), "integrando": ex}
            if op == "limit":
                ex = self.parse(e); pt = self.parse(case["point"]); d = case.get("direction", "both")
                r = sp.limit(ex, x, pt, "+-" if d == "both" else d)
                if r.has(sp.Limit): return {"tipo": "no_resuelto"}
                return {"tipo": "limite", "obj": r, "texto": str(r)}
            if op == "solve":
                if ";" in e or case.get("sistema"):
                    eqs = [self._eq(q) for q in e.split(";")]
                    syms = sorted(set().union(*[q.free_symbols for q in eqs]), key=str)
                    sol = sp.linsolve(eqs, *syms)
                    if sol == sp.EmptySet: return {"tipo": "vacio"}
                    s0 = list(sol)[0]
                    if any(c.free_symbols for c in s0): return {"tipo": "familia", "texto": str(sol)}
                    return {"tipo": "sistema", "valores": {str(q): complex(c) for q, c in zip(syms, s0)}, "texto": str(sol)}
                eq = self._eq(e)
                dom = sp.S.Complexes if case.get("complejo") else sp.S.Reals
                sol = sp.solveset(eq, x, domain=dom)
                if sol == sp.S.EmptySet: return {"tipo": "vacio"}
                if sol == dom: return {"tipo": "todo", "texto": f"todo el dominio ({dom})"}
                if not hasattr(sol, "__iter__") or isinstance(sol, sp.ConditionSet): return {"tipo": "no_resuelto"}
                return {"tipo": "conjunto", "valores": sorted([complex(sp.N(v, 30)) for v in sol], key=lambda z: (z.real, z.imag)), "texto": str(sol)}
        except Exception as ex_:
            return {"tipo": "error_sympy", "texto": f"{type(ex_).__name__}: {ex_}"}
        return {"tipo": "no_resuelto"}

    def _eq(self, s):
        l, r = s.split("=", 1) if "=" in s else (s, "0")
        return self.sp.Eq(self.parse(l), self.parse(r))

    def _singularidades(self, ex):
        try:
            from sympy.calculus.util import singularities
            return sorted(float(v) for v in singularities(ex, self.x) if v.is_real)
        except Exception:
            return None


def _ref_worker(case):
    """Se ejecuta en un proceso hijo (con plazo): importa SymPy y calcula la referencia."""
    return SympyAdapter().reference(case)


# ---------------------------------------------------------------- corpus
def corpus():
    import audit.oraculo as o
    C = []
    for t, f, cond in o.SIMP: C.append({"op": "simplify", "expr": t})
    for t in o.FACT: C.append({"op": "factor", "expr": t})
    for t, f, cond in o.SIMP[:6]: C.append({"op": "expand", "expr": t.split("/")[0]})
    for t, exp in o.EQ: C.append({"op": "solve", "expr": t})
    for t, f in o.DER: C.append({"op": "differentiate", "expr": t})
    for t, a, b, f in o.INT: C.append({"op": "integrate", "expr": t, "lower": repr(a) if not isinstance(a, int) else str(a), "upper": repr(b) if not isinstance(b, int) else str(b)})
    for t in ["x^3", "1/x", "x*exp(x)", "sin(x)^2", "cos(x)*sin(x)", "1/(x^2-1)", "1/(x^2+1)", "x*ln(x)", "exp(2x)", "(2x+1)/(x^2+x+1)",
              "1/(x^3+1)", "x^2*sin(x)", "ln(x)", "1/(x*(x+1))", "tan(x)", "sqrt(x)", "exp(-x)*x"]:
        C.append({"op": "integrate", "expr": t})
    for t, p, exp in o.LIM: C.append({"op": "limit", "expr": t, "point": p})
    for t, p, d, w in [("1/x", "0", "+", "oo"), ("1/x", "0", "-", "-oo"), ("1/x", "0", "both", "no"), ("abs(x)/x", "0", "both", "no")]:
        C.append({"op": "limit", "expr": t, "point": p, "direction": d})
    for s in ["2x+y=5; x-y=1", "x+y=2; 2x+2y=4", "x+y=2; 2x+2y=5", "x+y+z=3; x-y=1; z=1", "3x-2y=4; x+y=3"]:
        C.append({"op": "solve", "expr": s, "sistema": True})
    # convenciones que pueden diferir a propósito (se espera EQUIVALENTE o DIFERENCIA documentada)
    for t in ["sqrt(x^2)", "ln(exp(x))", "exp(ln(x))", "(-8)^(1/3)", "x^(1/2)*x^(1/2)", "abs(x)", "sin(pi/3)", "cos(7*pi/6)", "tan(pi/4)"]:
        C.append({"op": "simplify", "expr": t})
    for i, c in enumerate(C): c["id"] = i
    return C


# ---------------------------------------------------------------- comparación (lógica pura, probada sin SymPy)
OK_VEREDICTOS = ("IDENTICO", "EQUIVALENTE", "CONVENCION_DOCUMENTADA", "SYMPY_AMPLIA_DOMINIO", "LIMITACION_MOTOR", "AMBOS_NO_SOPORTAN")
# SYMPY_AMPLIA_DOMINIO: SymPy da un valor donde la función ORIGINAL no existe (singularidad evitable perdida al construir la expresión,
# o derivada en un punto anguloso). Solo se acepta con evidencia independiente del motor (ver _confirmar_no_existe); si no, DIFERENCIA_DOMINIO.
HALLAZGOS = ("DIFERENCIA", "DIFERENCIA_DOMINIO", "NO_CONCLUYENTE", "ERROR_COMPARADOR")

# Convenciones ACEPTADAS: solo si el motor y SymPy dan EXACTAMENTE esto. Cualquier otra diferencia sigue siendo DIFERENCIA.
CONVENCIONES = {
    "(-8)^(1/3)": {"motor": "-2", "sympy": complex(1.0, 3 ** 0.5),
                   "explicacion": "Dominio real: raíz real de índice impar (-2). SymPy: rama principal compleja 1+√3·i."},
}


def _close(a, b, tol=1e-25, ad=None):
    """Tolerancia relativa. `ad.tol` (solo adaptadores de prueba con coma flotante) puede ensancharla; SymPy usa 0 (precisión 40 cifras)."""
    tol = max(tol, getattr(ad, "tol", 0.0))
    if isinstance(a, float) and math.isinf(a) or isinstance(b, float) and math.isinf(b):
        return a == b
    return abs(a - b) <= tol * (1 + abs(a) + abs(b))


def _motor(case):
    q = {"operation": case["op"], "expression": case["expr"]}
    if case["op"] in ("differentiate", "integrate", "limit"): q["variables"] = ["x"]
    for k in ("point", "direction", "lower", "upper", "order"):
        if k in case: q[k] = case[k]
    if case.get("complejo"): q["assumptions"] = {"x": "complex"}
    # SESGO CORREGIDO (hallazgo de Windows nº7): si el motor usa el respaldo SymPy, "motor vs SymPy" compara SymPy consigo mismo.
    # Aquí el motor corre SIEMPRE solo con su código propio; el respaldo se prueba aparte (test_11 / test_08).
    prev = os.environ.get("MATH_UNIVERSE_DISABLE_SYMPY")
    os.environ["MATH_UNIVERSE_DISABLE_SYMPY"] = "1"
    try:
        return handle(q)
    finally:
        if prev is None: os.environ.pop("MATH_UNIVERSE_DISABLE_SYMPY", None)
        else: os.environ["MATH_UNIVERSE_DISABLE_SYMPY"] = prev


def comparar_expr(ad, a, b):
    """Compara dos expresiones del adaptador en puntos racionales exactos.
    Devuelve (n_comparados, primera_diferencia|None, puntos_definidos_en_un_solo_lado)."""
    n, dif, uno = 0, None, []
    for x in ad.puntos():
        env = {"x": x}
        try: va, da = ad.num(a, env), True
        except ZeroDivisionError: va, da = None, False
        try: vb, db = ad.num(b, env), True
        except ZeroDivisionError: vb, db = None, False
        if da != db: uno.append((str(x), "sympy" if da else "motor")); continue
        if not da: continue
        n += 1
        if not _close(va, vb, ad=ad): dif = (str(x), va, vb); break
    return n, dif, uno


def _veredicto_equivalencia(ad, a, b, etiqueta=""):
    n, dif, uno = comparar_expr(ad, a, b)
    if dif: return "DIFERENCIA", f"{etiqueta}x={dif[0]}: SymPy {dif[1]} vs motor {dif[2]}"
    if uno: return "DIFERENCIA_DOMINIO", f"{etiqueta}definido en un solo lado en x={uno[:3]} (lado que SÍ está definido)"
    if n < MIN_PUNTOS: return "NO_CONCLUYENTE", f"{etiqueta}solo {n} puntos comparados (mínimo {MIN_PUNTOS})"
    sim = ad.igual_simbolico(a, b)
    nota = ""
    if sim is not True:
        # `equals` es heurístico: un False/None NO se toma por prueba. Se intenta una DEMOSTRACIÓN exacta por ramas de Abs/sign.
        por_ramas = getattr(ad, "igual_simbolico_por_ramas", None)
        if por_ramas is not None and por_ramas(a, b) is True:
            nota = f" | SymPy.equals={sim}; DEMOSTRADO exactamente por ramas de Abs/sign (cancel=0 en cada intervalo); puede diferir en los puntos excluidos"
            sim = True
        elif sim is False:
            return "DIFERENCIA", f"{etiqueta}coinciden en {n} puntos pero SymPy.equals(a-b, 0) = False y no hay demostración exacta"
    return ("IDENTICO" if ad.misma_repr(a, b) else "EQUIVALENTE"), f"{n} puntos exactos; simbólico={'confirmado' if sim else 'no decidido'}{nota}"


def _condiciones_puntuales(conds):
    """(todas_puntuales, {valores}) para condiciones 'x ≠ k'. Si hay otras (x>0, polinomios...) no se compara el dominio."""
    vals, todas = set(), True
    for c in conds:
        m = re.match(r"^x ≠ (-?\d+(?:/\d+)?)$", c.strip())
        if m: vals.add(round(eval_frac(m.group(1)), 12))
        else: todas = False
    return todas, sorted(vals)


def _puntos_especiales(resp, ref):
    ks = {Fraction(0)}
    for c in resp.get("conditions", []):
        m = re.match(r"^x ≠ (-?\d+(?:/\d+)?)$", c.strip())
        if m: ks.add(Fraction(m.group(1)))
    for s_ in ref.get("singularidades") or []: ks.add(Fraction(s_).limit_denominator(10**6))
    return sorted(ks)


def _confirmar_no_existe(ad, case, k):
    """Evidencia INDEPENDIENTE DEL MOTOR de que lo que se compara no existe en x=k: la función original (sin autosimplificar) es
    indefinida, o (derivadas) los cocientes incrementales laterales tienen límites distintos. True/False/None."""
    if case["op"] == "differentiate":
        nd = getattr(ad, "no_derivable_en", None)
        r = nd(case["expr"], k) if nd else None
        if r: return True
    ind = getattr(ad, "indefinida_en", None)
    return ind(case["expr"], k) if ind else None


def _discrepancias_puntuales(ad, case, a, b, ks, excluidos_motor=()):
    """Compara SymPy (a) y motor (b) en los puntos especiales ks. Devuelve veredicto/detalle si hay algo distinto, o None.
    excluidos_motor: puntos que el motor EXCLUYE explícitamente en `conditions` ('x ≠ k'). Si en uno de ellos la expresión del
    motor tiene valor pero la de SymPy no, NO hay diferencia de dominio: el resultado del motor está restringido a x ≠ k.
    Caso real: simplify((x^3-8)/(x-2)) → motor 'x^2 + 2*x + 4' con 'x ≠ 2'; SymPy 1.14 deja el cociente sin simplificar
    (misma cuenta de operaciones) y es indefinido en 2. Se exige además evidencia independiente del motor de que la función
    original no existe en k; sin ella sigue siendo DIFERENCIA_DOMINIO."""
    excl = set(excluidos_motor)
    solo_sympy, otros = [], []
    for k in ks:
        env = {"x": k}
        try: va = ad.num(a, env)
        except ZeroDivisionError: va = None
        try: vb = ad.num(b, env)
        except ZeroDivisionError: vb = None
        if va is None and vb is None: continue
        if va is not None and vb is None: solo_sympy.append(k)
        elif va is None:
            if k in excl and _confirmar_no_existe(ad, case, k) is True:
                continue                                   # ambos excluyen k (el motor lo declara en sus condiciones)
            otros.append(("DIFERENCIA_DOMINIO", f"x={k}: el motor da valor y SymPy no"))
        elif not _close(va, vb, ad=ad): otros.append(("DIFERENCIA", f"x={k}: SymPy {va} vs motor {vb}"))
    if otros: return otros[0]
    if solo_sympy:
        pruebas = [(k, _confirmar_no_existe(ad, case, k)) for k in solo_sympy]
        if all(p is True for _, p in pruebas):
            return "SYMPY_AMPLIA_DOMINIO", ("SymPy da valor en x=" + ", ".join(map(str, solo_sympy)) +
                                            " donde la función original no existe (confirmado de forma independiente del motor); el motor lo excluye con razón")
        return "DIFERENCIA_DOMINIO", f"el motor excluye x={[str(k) for k, p in pruebas if p is not True]} sin evidencia independiente de que la función no exista allí"
    return None


def clasificar(case, resp, ref, ad):
    """Devuelve (veredicto, detalle)."""
    st, op, expr = resp["status"], case["op"], case["expr"]
    t = ref["tipo"]
    if t in ("error_sympy", "no_resuelto"):
        if st == "unsupported": return "AMBOS_NO_SOPORTAN", ref.get("texto", "SymPy no resuelve")
        return "SIN_REFERENCIA_SYMPY", f"SymPy no dio referencia ({ref.get('texto', 'no resuelto')}); resultado del motor ({st}) NO validado cruzadamente"
    if st == "unsupported":
        return "LIMITACION_MOTOR", (resp.get("error") or {}).get("message", "")
    if st in ("internal_error", "invalid_input", "domain_error") and t != "vacio":
        return "DIFERENCIA", f"motor: {st} {(resp.get('error') or {}).get('message', '')} | SymPy: {ref.get('texto')}"
    try:
        # convención documentada (estricta)
        cv = CONVENCIONES.get(expr)
        if cv and op == "simplify":
            if resp.get("exact_result") == cv["motor"] and ref.get("obj") is not None and _close(ad.num(ref["obj"], {}), cv["sympy"], 1e-9, ad):
                return "CONVENCION_DOCUMENTADA", cv["explicacion"]
        if op in ("simplify", "expand", "factor", "differentiate"):
            if not st.startswith("success"): return "DIFERENCIA", f"motor {st}; SymPy {ref['texto']}"
            mot = ad.parse(resp["exact_result"])
            v, det = _veredicto_equivalencia(ad, ref["obj"], mot)
            det = f"motor: {resp['exact_result']} | SymPy: {ref['texto']} | {det}"
            if v in ("IDENTICO", "EQUIVALENTE"):
                excl = [Fraction(m.group(1)) for c in resp.get("conditions", [])
                        if (m := re.match(r"^x ≠ (-?\d+(?:/\d+)?)$", c.strip()))]
                d = _discrepancias_puntuales(ad, case, ref["obj"], mot, _puntos_especiales(resp, ref), excl)
                if d: return d[0], det + " | " + d[1]
            if v in ("IDENTICO", "EQUIVALENTE") and op in ("simplify", "expand", "factor") and ref.get("singularidades") is not None:
                puntual, conds = _condiciones_puntuales(resp["conditions"])
                sing = [round(x, 12) for x in ref["singularidades"]]
                if not puntual: det += " | dominio: condiciones no puntuales, no comparado"
                elif conds != sing:
                    faltan = [c for c in sing if c not in conds]
                    extra = [c for c in conds if c not in sing]
                    if faltan: return "DIFERENCIA_DOMINIO", det + f" | el motor NO excluye singularidades de SymPy {faltan} (motor {conds} vs SymPy {sing})"
                    # el motor excluye puntos que SymPy no: se acepta SOLO si la expresión original es realmente indefinida allí
                    pruebas = [_confirmar_no_existe(ad, case, Fraction(c).limit_denominator(10**6)) for c in extra]
                    if all(p is True for p in pruebas):
                        lim = getattr(ad, "limite_en", None)
                        lims = {str(c): lim(case["expr"], Fraction(c).limit_denominator(10**6)) for c in extra} if lim else {}
                        return "SYMPY_AMPLIA_DOMINIO", det + (f" | SymPy pierde la singularidad evitable en x={extra} (autosimplifica al construir la expresión); "
                                                              f"original indefinida allí: confirmado; límites en esos puntos: {lims}")
                    return "DIFERENCIA_DOMINIO", det + f" | motor {conds} vs SymPy {sing}; sin evidencia independiente para {extra}"
                else: det += " | dominio coincide"
            return v, det
        if op == "integrate" and t == "primitiva":
            if not st.startswith("success"): return "DIFERENCIA", f"motor {st}"
            mot = ad.parse(resp["exact_result"].replace("+ C", "").strip())
            v, det = _veredicto_equivalencia(ad, ad.derivada(mot), ref["integrando"], "d(primitiva del motor) vs integrando: ")
            if v not in ("IDENTICO", "EQUIVALENTE"): return v, det
            v2, det2 = _veredicto_equivalencia(ad, ad.derivada(ref["obj"]), ref["integrando"], "d(primitiva de SymPy) vs integrando: ")
            extra = "" if v2 in ("IDENTICO", "EQUIVALENTE") else f" | AVISO: la primitiva de SymPy no deriva al integrando ({det2})"
            return "EQUIVALENTE", f"motor: {resp['exact_result']} | SymPy: {ref['texto']} | {det}{extra}"
        if op == "integrate" and t == "valor":
            if not st.startswith("success"): return "DIFERENCIA", f"motor {st}"
            b = float(resp["approximate_result"]) if resp.get("approximate_result") else float(ad.num(ad.parse(resp["exact_result"]), {}))
            a = ref["valor"]
            return ("EQUIVALENTE" if _close(a, b, 1e-9, ad) else "DIFERENCIA"), f"motor {b} | SymPy {a}"
        if op == "limit":
            if st == "no_solution":
                ok = str(ref["texto"]) in ("nan", "zoo") or "Accum" in str(ref["texto"])
                return ("EQUIVALENTE" if ok else "DIFERENCIA"), f"motor: el límite no existe | SymPy: {ref['texto']}"
            if not st.startswith("success"): return "DIFERENCIA", f"motor {st}"
            a, b = ad.num(ref["obj"], {}), ad.num(ad.parse(resp["exact_result"]), {})
            return ("EQUIVALENTE" if _close(a, b, 1e-20, ad) else "DIFERENCIA"), f"motor {resp['exact_result']} | SymPy {ref['texto']}"
        if op == "solve":
            if t == "vacio": return ("EQUIVALENTE" if st == "no_solution" else "DIFERENCIA"), f"motor {st} {resp.get('exact_result')}"
            if t in ("todo", "familia"):
                if (t == "todo" and st == "success_exact" and resp.get("exact_result") == "Verdadero"
                        and not re.search(r"[A-Za-z]", re.sub(r"\b(pi|e)\b", "", expr))):
                    return "CONVENCION_DOCUMENTADA", ("Ecuación sin incógnita y verdadera: el motor responde la PROPOSICIÓN ('Verdadero', success_exact); SymPy "
                                                      "devuelve el conjunto solución (todo el dominio). Mismo hecho matemático. Con incógnita (x=x) el motor sí devuelve multiple_solutions.")
                return ("EQUIVALENTE" if st == "multiple_solutions" else "DIFERENCIA"), f"motor {st} {resp.get('exact_result')} | SymPy {ref.get('texto')}"
            if t == "sistema":
                if st != "success_exact": return "DIFERENCIA", f"motor {st}"
                sol = resp["data"]["solution"]
                if set(sol) != set(ref["valores"]): return "DIFERENCIA", f"variables distintas: motor {sorted(sol)} SymPy {sorted(ref['valores'])}"
                for k, v in sol.items():
                    if not _close(complex(ad.num(ad.parse(v), {})), ref["valores"][k], 1e-20, ad): return "DIFERENCIA", f"{k}: motor {v} SymPy {ref['valores'][k]}"
                return "EQUIVALENTE", resp["exact_result"]
            if t == "conjunto":
                if st != "success_exact": return "DIFERENCIA", f"motor {st} {resp.get('exact_result')} | SymPy {ref['texto']}"
                mv = sorted([complex(ad.num(ad.parse(q["value"]), {})) for q in resp["data"]["solutions"]], key=lambda z: (z.real, z.imag))
                rv = ref["valores"]
                if len(mv) != len(rv): return "DIFERENCIA", f"nº de soluciones: motor {resp['exact_result']} | SymPy {ref['texto']}"
                ok = all(_close(a, b, 1e-20, ad) for a, b in zip(mv, rv))
                return ("EQUIVALENTE" if ok else "DIFERENCIA"), f"motor {resp['exact_result']} | SymPy {ref['texto']}"
    except Exception as e:
        tb = traceback.format_exc().strip().splitlines()
        return "ERROR_COMPARADOR", f"{type(e).__name__}: {e} | traza: " + " ⏎ ".join(l.strip() for l in tb[-6:])[:900]
    return "ERROR_COMPARADOR", "caso sin rama de comparación"


def eval_frac(s):
    return float(Fraction(s.strip()))


def _referencia(ad, case, con_procesos):
    if not con_procesos: return ad.reference(case)
    from math_universe_engine import limits
    from math_universe_engine.errors import TimeoutExceeded
    try:
        return limits.run_hard_timeout(_ref_worker, (case,), PLAZO_SYMPY_S)
    except TimeoutExceeded:
        return {"tipo": "error_sympy", "texto": f"plazo de {PLAZO_SYMPY_S} s agotado en SymPy"}
    except Exception as e:
        return {"tipo": "error_sympy", "texto": f"fallo del proceso de SymPy: {e}"}


def ejecutar(ad, salida, con_procesos=None):
    if con_procesos is None: con_procesos = isinstance(ad, SympyAdapter)
    C = corpus()
    filas, cnt = [], {}
    for c in C:
        resp = _motor(c)
        ref = _referencia(ad, c, con_procesos)
        v, det = clasificar(c, resp, ref, ad)
        filas.append({**{k: c[k] for k in c if k != "id"}, "id": c["id"], "veredicto": v, "detalle": det,
                      "estado_motor": resp["status"], "verificacion_motor": resp["verification"]["status"]})
        cnt[v] = cnt.get(v, 0) + 1
    json.dump({"versiones": ad.versions(), "conteo": cnt, "casos": filas}, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return cnt, filas


def main():
    try:
        ad = SympyAdapter()
    except ImportError as e:
        print("SymPy/mpmath no instalados: la comparación NO se ejecutó (", e, ")")
        return 2
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida"), exist_ok=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida", "comparacion_sympy.json")
    cnt, filas = ejecutar(ad, out)
    print("Versiones:", ad.versions())
    for k in sorted(cnt): print(f"  {k:24} {cnt[k]}")
    for f in filas:
        if f["veredicto"] in HALLAZGOS or f["veredicto"] == "SIN_REFERENCIA_SYMPY":
            print("  >>", f["veredicto"], f["op"], f["expr"], "|", f["detalle"][:220])
    return 0


if __name__ == "__main__":
    sys.exit(main())
