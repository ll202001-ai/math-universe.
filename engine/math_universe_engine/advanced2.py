"""Matemáticas avanzadas II (motor 0.7.0, contrato 1.3). Mismas reglas que advanced.py: SymPy calcula y una vía
INDEPENDIENTE comprueba; si la comprobación falla el resultado no se entrega; si no es posible, se declara.

sum / product      Σ y Π (finitas, infinitas y con límite simbólico)
substitute         sustitución de variables
matrix_symbolic    matrices con símbolos: det, inversa, transpuesta, producto, polinomio característico, autovalores
logic              lógica proposicional: simplificar, FNC, FND, tabla de verdad
sets               conjuntos e intervalos: ∪, ∩, diferencia
implicit_diff      derivación implícita dy/dx de F(x, y) = 0
"""
import itertools
import random
import re
from fractions import Fraction

from . import symbolic
from .advanced import _S, _ast, _check, _close, _latex, _num, _res, _sp, _txt, _set_text
from .ast_tools import eval_float, free_symbols
from .errors import InvalidRequest, MathDomainError, NotSolved, ParseError

ADVANCED2_OPS = ("sum", "product", "substitute", "matrix_symbolic", "logic", "sets", "implicit_diff")

MAX_DIRECT_TERMS = 20000


# ------------------------------------------------------------------ Σ y Π
def _bounds(req):
    p = req.get("params") or {}
    var = (p.get("var") or (req.get("variables") or ["k"])[0]).strip()
    lo, hi = str(p.get("from", "1")), str(p.get("to", "n"))
    if not re.fullmatch(r"[A-Za-z_]\w*", var): raise InvalidRequest("Variable de la suma no válida")
    return var, lo, hi


def op_sum_product(req, st):
    sp = _sp()
    is_sum = req["operation"] == "sum"
    var, lo_t, hi_t = _bounds(req)
    k = sp.Symbol(var, integer=True)
    term = _S(req["expression"]).subs(sp.Symbol(var), k)
    lo = _S(lo_t)
    hi = sp.oo if hi_t.replace(" ", "") in ("oo", "+oo", "inf", "∞") else _S(hi_t)
    F = (sp.summation if is_sum else sp.product)(term, (k, lo, hi))
    if F.has(sp.Sum, sp.Product): raise NotSolved("SymPy no encontró una forma cerrada (no implica que no exista)")
    F = sp.simplify(F)
    ok, how = _verify_sum(term, k, lo, hi, F, is_sum)
    _check(ok, how)
    sym = r"\sum" if is_sum else r"\prod"
    lat = sym + "_{" + var + "=" + _latex(lo) + "}^{" + _latex(hi) + "} " + _latex(term) + " = " + _latex(F)
    approx = None
    if not F.free_symbols and F.is_finite:
        try: approx = format(float(sp.N(F, 20)), ".15g")
        except TypeError: approx = None
    if F in (sp.oo, -sp.oo, sp.zoo): status_txt = "diverge"
    else: status_txt = _txt(F)
    return _res(status_txt, "sympy_summation" if is_sum else "sympy_product",
                ("passed" if ok else "not_possible", how if ok else None), approx=approx, latex=lat,
                data={"variable": var, "from": _txt(lo), "to": "oo" if hi == sp.oo else _txt(hi)})


def _verify_sum(term, k, lo, hi, F, is_sum):
    """Finitas: suma/producto directo término a término (aritmética exacta). Límite simbólico n: se comprueba para
    n = lo..lo+5 sumando directamente. Infinitas: mpmath nsum/nprod (aceleración de series) frente al valor cerrado."""
    sp = _sp()
    try:
        if hi == sp.oo:
            import mpmath
            mpmath.mp.dps = 30
            f = sp.lambdify(k, term, "mpmath")
            val = (mpmath.nsum if is_sum else mpmath.nprod)(f, [int(lo), mpmath.inf])
            if F in (sp.oo, -sp.oo): return (None, None)
            ref = complex(sp.N(F, 30))
            return (abs(complex(val) - ref) <= 1e-12 * max(1, abs(ref)),
                    "serie evaluada numéricamente con mpmath (nsum/nprod) y comparada con la forma cerrada")
        if hi.free_symbols:
            n = list(hi.free_symbols)[0]
            for m in range(0, 6):
                hv = hi.subs(n, int(lo) + m)
                acc = sp.Integer(0) if is_sum else sp.Integer(1)
                for j in range(int(lo), int(hv) + 1):
                    acc = acc + term.subs(k, j) if is_sum else acc * term.subs(k, j)
                if sp.simplify(acc - F.subs(n, hv)) != 0: return (False, "suma directa")
            return (True, f"suma directa término a término para {n} = {int(lo)}…{int(lo) + 5}")
        a, b = int(lo), int(hi)
        if b - a > MAX_DIRECT_TERMS: return (None, None)
        acc = sp.Integer(0) if is_sum else sp.Integer(1)
        for j in range(a, b + 1):
            acc = acc + term.subs(k, j) if is_sum else acc * term.subs(k, j)
        return (sp.simplify(acc - F) == 0, f"{'suma' if is_sum else 'producto'} directo de los {b - a + 1} términos")
    except (TypeError, ValueError):
        return (None, None)


# ------------------------------------------------------------------ sustitución
def op_substitute(req, st):
    sp = _sp()
    values = (req.get("params") or {}).get("values") or {}
    if not values: raise InvalidRequest("Indique los valores, p. ej. x = 2, y = a + 1")
    ast = _ast(req["expression"])
    expr = symbolic.to_sympy(ast)
    subs = {sp.Symbol(k): _S(str(v)) for k, v in values.items()}
    r = sp.simplify(expr.subs(subs))
    # verificación independiente: evaluador propio en coma flotante (original con los valores) frente al resultado
    rest = sorted(set().union(*[s.free_symbols for s in subs.values()]) | (r.free_symbols), key=lambda s: s.name)
    rnd = random.Random(3)
    checked, ok = 0, True
    for _ in range(12):
        env = {s.name: rnd.randint(-9, 9) / rnd.randint(2, 7) for s in rest}
        try:
            full = dict(env)
            for k, v in values.items(): full[k] = eval_float(_ast(str(v)), env)
            a = eval_float(ast, full)
            b = eval_float(_ast(_txt(r)), env)
        except Exception:
            continue
        if not _close(complex(a), complex(b), 1e-9): ok = False
        checked += 1
        if checked >= 4: break
    _check(ok, "evaluación en puntos")
    return _res(_txt(r), "sustitucion_sympy",
                ("passed" if checked else "not_possible", "evaluador propio en puntos de prueba" if checked else None),
                latex=_latex(r), data={"values": {k: str(v) for k, v in values.items()}})


# ------------------------------------------------------------------ matrices simbólicas
def _matrix(a):
    sp = _sp()
    if isinstance(a, str):
        rows = re.findall(r"\[([^\[\]]+)\]", a)
        a = [[c.strip() for c in r.split(",")] for r in rows]
    if not a or not isinstance(a, list): raise InvalidRequest("Matriz vacía")
    rows = [r if isinstance(r, list) else [r] for r in a]
    if len({len(r) for r in rows}) != 1: raise InvalidRequest("Todas las filas deben tener el mismo número de columnas")
    if len(rows) > 8 or len(rows[0]) > 8: raise InvalidRequest("Matrices simbólicas: máximo 8×8")
    return sp.Matrix([[_S(str(c)) for c in r] for r in rows])


def _mlatex(M):
    return _latex(M).replace(r"\left[", r"\begin{pmatrix}").replace(r"\right]", r"\end{pmatrix}") \
        .replace(r"\begin{matrix}", "").replace(r"\end{matrix}", "") if False else _latex(M)


def _numeric_points(M_syms, k=3, seed=11):
    rnd = random.Random(seed)
    return [{s: _sp().Rational(rnd.randint(-9, 9), rnd.randint(2, 7)) for s in M_syms} for _ in range(k)]


def op_matrix_symbolic(req, st):
    sp = _sp()
    si = req.get("structured_input") or {}
    A = _matrix(si.get("a", req.get("expression")))
    what = (req.get("params") or {}).get("op", "det")
    syms = sorted(A.free_symbols, key=lambda s: s.name)
    if what == "det":
        if A.rows != A.cols: raise InvalidRequest("El determinante requiere una matriz cuadrada")
        d1 = sp.factor(A.det(method="bareiss"))
        d2 = A.det(method="berkowitz")
        ok = sp.simplify(d1 - d2) == 0
        _check(ok, "dos métodos")
        return _res(_txt(d1), "determinante_simbolico", ("passed", "Bareiss y Berkowitz coinciden (dos algoritmos distintos)"),
                    latex=r"\det" + _latex(A) + " = " + _latex(d1), data={"determinant": _txt(d1)})
    if what == "inverse":
        if A.rows != A.cols: raise InvalidRequest("La inversa requiere una matriz cuadrada")
        d = sp.simplify(A.det())
        if d == 0: raise MathDomainError("La matriz es singular (determinante 0)")
        Ai = A.inv().applyfunc(sp.simplify)
        ok = (A * Ai - sp.eye(A.rows)).applyfunc(sp.simplify) == sp.zeros(A.rows)
        _check(ok, "A·A⁻¹ = I")
        conds = [f"{_txt(d)} ≠ 0"] if d.free_symbols else []
        return _res(_mtxt(Ai), "inversa_simbolica", ("passed", "A·A⁻¹ = I simplificado"), latex=_latex(Ai),
                    data={"matrix": [[_txt(Ai[i, j]) for j in range(Ai.cols)] for i in range(Ai.rows)]}, conditions=conds)
    if what == "transpose":
        T = A.T
        ok = all(T[j, i] == A[i, j] for i in range(A.rows) for j in range(A.cols))
        _check(ok, "índice a índice")
        return _res(_mtxt(T), "transpuesta_simbolica", ("passed", "comparación índice a índice"), latex=_latex(T),
                    data={"matrix": [[_txt(T[i, j]) for j in range(T.cols)] for i in range(T.rows)]})
    if what == "mul":
        B = _matrix(si.get("b"))
        if A.cols != B.rows: raise InvalidRequest(f"Dimensiones incompatibles: {A.rows}×{A.cols} por {B.rows}×{B.cols}")
        C = (A * B).applyfunc(sp.expand)
        ok = True
        for pt in _numeric_points(sorted(A.free_symbols | B.free_symbols, key=lambda s: s.name)):
            if (A.subs(pt) * B.subs(pt) - C.subs(pt)) != sp.zeros(C.rows, C.cols): ok = False
        _check(ok, "puntos")
        return _res(_mtxt(C), "producto_simbolico", ("passed", "producto numérico exacto en puntos racionales"), latex=_latex(C),
                    data={"matrix": [[_txt(C[i, j]) for j in range(C.cols)] for i in range(C.rows)]})
    if what in ("charpoly", "eigen"):
        if A.rows != A.cols: raise InvalidRequest("Se requiere una matriz cuadrada")
        lam = sp.Symbol("lambda")
        p = sp.factor(A.charpoly(lam).as_expr())
        ok = sp.simplify(p - (lam * sp.eye(A.rows) - A).det()) == 0
        _check(ok, "det(λI − A)")
        data = {"characteristic_polynomial": _txt(p)}
        txt = "p(λ) = " + _txt(p)
        if what == "eigen":
            vals = sp.roots(sp.Poly(A.charpoly(lam).as_expr(), lam))
            if sum(vals.values()) != A.rows: raise NotSolved("No se pudieron obtener todas las raíces en forma cerrada")
            for v in vals: _check(sp.simplify(p.subs(lam, v)) == 0, "raíz")
            data["eigenvalues"] = [{"value": _txt(v), "multiplicity": int(m)} for v, m in vals.items()]
            txt = "; ".join(f"λ = {_txt(v)} (multiplicidad {m})" for v, m in vals.items())
        return _res(txt, "polinomio_caracteristico_simbolico", ("passed", "comparado con det(λI − A) calculado aparte"),
                    latex="p(\\lambda) = " + _latex(p), data=data)
    raise InvalidRequest("Operación de matriz no reconocida (det, inverse, transpose, mul, charpoly, eigen)")


def _mtxt(M):
    return "[[" + "], [".join(", ".join(_txt(M[i, j]) for j in range(M.cols)) for i in range(M.rows)) + "]]"


# ------------------------------------------------------------------ lógica proposicional
_LTOK = re.compile(r"\s*(?:(<->|↔|<=>|->|→|=>|∧|&&?|∨|\|\|?|¬|~|!|⊕|\^|\(|\)|\btrue\b|\bfalse\b|\bverdadero\b|\bfalso\b|\bV\b|\bF\b)|([A-Za-z_]\w*))", re.IGNORECASE)


def _ltokens(text):
    t = (" " + text + " ").replace(" y ", " & ").replace(" o ", " | ").replace(" no ", " ~ ").replace(" and ", " & ") \
        .replace(" or ", " | ").replace(" not ", " ~ ").replace(" xor ", " ^ ")
    pos, out = 0, []
    while pos < len(t):
        if not t[pos:].strip(): break
        m = _LTOK.match(t, pos)
        if not m: raise ParseError("Símbolo no válido en una expresión lógica", {"position": pos})
        op, name = m.groups()
        out.append(("op", op) if op else ("id", name))
        pos = m.end()
    return out


class _LP:
    """Parser propio de lógica (precedencia: ¬ > ∧ > ⊕ > ∨ > → > ↔). Devuelve un árbol de tuplas."""
    def __init__(self, toks): self.t, self.i = toks, 0
    def peek(self): return self.t[self.i] if self.i < len(self.t) else (None, None)
    def nxt(self): v = self.peek(); self.i += 1; return v
    def parse(self):
        e = self.iff()
        if self.i != len(self.t): raise ParseError("Expresión lógica incompleta o mal formada")
        return e
    def iff(self):
        a = self.imp()
        while self.peek()[1] in ("<->", "↔", "<=>"): self.nxt(); a = ("iff", a, self.imp())
        return a
    def imp(self):
        a = self.orr()
        if self.peek()[1] in ("->", "→", "=>"): self.nxt(); return ("imp", a, self.imp())
        return a
    def orr(self):
        a = self.xor()
        while self.peek()[1] in ("|", "||", "∨"): self.nxt(); a = ("or", a, self.xor())
        return a
    def xor(self):
        a = self.andd()
        while self.peek()[1] in ("^", "⊕"): self.nxt(); a = ("xor", a, self.andd())
        return a
    def andd(self):
        a = self.nott()
        while self.peek()[1] in ("&", "&&", "∧"): self.nxt(); a = ("and", a, self.nott())
        return a
    def nott(self):
        if self.peek()[1] in ("~", "!", "¬"): self.nxt(); return ("not", self.nott())
        k, v = self.nxt()
        if v == "(":
            e = self.iff()
            if self.nxt()[1] != ")": raise ParseError("Falta ')'")
            return e
        if k == "op" and v.lower() in ("true", "verdadero", "v"): return ("const", True)
        if k == "op" and v.lower() in ("false", "falso", "f"): return ("const", False)
        if k == "id": return ("var", v)
        raise ParseError("Expresión lógica incompleta")


def _leval(n, env):
    k = n[0]
    if k == "var": return env[n[1]]
    if k == "const": return n[1]
    if k == "not": return not _leval(n[1], env)
    a, b = _leval(n[1], env), _leval(n[2], env)
    return {"and": a and b, "or": a or b, "xor": a != b, "imp": (not a) or b, "iff": a == b}[k]


def _lvars(n, acc):
    if n[0] == "var": acc.add(n[1])
    for c in n[1:]:
        if isinstance(c, tuple): _lvars(c, acc)
    return acc


def _l2sp(n):
    sp = _sp()
    k = n[0]
    if k == "var": return sp.Symbol(n[1])
    if k == "const": return sp.true if n[1] else sp.false
    if k == "not": return sp.Not(_l2sp(n[1]))
    a, b = _l2sp(n[1]), _l2sp(n[2])
    return {"and": sp.And, "or": sp.Or, "xor": sp.Xor, "imp": sp.Implies, "iff": sp.Equivalent}[k](a, b)


def _ltxt(e):
    sp = _sp()
    s = str(e)
    return s.replace("&", "∧").replace("|", "∨").replace("~", "¬").replace("True", "V").replace("False", "F")


def op_logic(req, st):
    sp = _sp()
    from sympy.logic.boolalg import simplify_logic, to_cnf, to_dnf
    tree = _LP(_ltokens(req["expression"])).parse()
    names = sorted(_lvars(tree, set()))
    if len(names) > 10: raise InvalidRequest("Lógica: máximo 10 variables")
    form = (req.get("params") or {}).get("form", "simplify")
    E = _l2sp(tree)
    R = {"simplify": lambda: simplify_logic(E), "cnf": lambda: to_cnf(E, simplify=True), "dnf": lambda: to_dnf(E, simplify=True),
         "table": lambda: simplify_logic(E)}.get(form, lambda: simplify_logic(E))()
    # verificación independiente: tabla de verdad COMPLETA con el evaluador propio frente al resultado de SymPy
    rows, ok = [], True
    for vals in itertools.product([False, True], repeat=len(names)):
        env = dict(zip(names, vals))
        a = _leval(tree, env)
        b = bool(R.subs({sp.Symbol(k): v for k, v in env.items()})) if names else bool(R)
        if a != b: ok = False
        rows.append({"values": [int(v) for v in vals], "result": int(a)})
    _check(ok, "tabla de verdad")
    kind = "tautología" if all(r["result"] for r in rows) else ("contradicción" if not any(r["result"] for r in rows) else "contingencia")
    return _res(_ltxt(R), "logica_proposicional_sympy", ("passed", f"tabla de verdad completa ({len(rows)} filas) con un evaluador propio"),
                latex=_latex(R), data={"variables": names, "truth_table": rows, "classification": kind, "form": form})


# ------------------------------------------------------------------ conjuntos e intervalos
_STOK = re.compile(r"\s*(?:(∪|∩|\\|−|-|U\b|∅|\(|\)|\[|\]|\{|\}|,|;)|(-?[0-9][0-9./]*|-?oo|-?∞|[A-Za-z_]\w*(?:\([^()]*\))?))")


def _sparse(text):
    """Parser propio: [a,b] (a,b) [a,b) {x,y} ∅ con ∪ ∩ \\ y paréntesis. Árbol: ("iv", a, b, lo, ro) ("fin", [..]) ("op", o, A, B)."""
    t = text.replace(" U ", " ∪ ").replace("unión", "∪").replace("intersección", "∩")
    toks, pos = [], 0
    while pos < len(t):
        if not t[pos:].strip(): break
        m = _STOK.match(t, pos)
        if not m: raise ParseError("Símbolo no válido en una expresión de conjuntos", {"position": pos})
        toks.append(m.group(1) or m.group(2)); pos = m.end()
    i = [0]

    def peek(): return toks[i[0]] if i[0] < len(toks) else None
    def nxt(): v = peek(); i[0] += 1; return v

    def val(s):
        s = s.replace("∞", "oo")
        return _S(s)

    def prim():
        v = nxt()
        if v == "∅": return ("fin", [])
        if v == "{":
            items = []
            while peek() != "}":
                items.append(val(nxt()))
                if peek() == ",": nxt()
                elif peek() != "}": raise ParseError("Conjunto mal formado")
            nxt(); return ("fin", items)
        if v in ("[", "("):
            a = val(nxt())
            if nxt() not in (",", ";"): raise ParseError("Intervalo mal formado: use [a, b]")
            b = val(nxt()); c = nxt()
            if c not in ("]", ")"): raise ParseError("Intervalo mal formado")
            if v == "(" and peek() in ("∪", "∩", "\\", None, ")") and False: pass
            return ("iv", a, b, v == "(", c == ")")
        raise ParseError("Se esperaba un conjunto o intervalo")

    def expr():
        a = prim()
        while peek() in ("∪", "∩", "\\", "−", "-"):
            o = nxt(); a = ("op", {"−": "\\", "-": "\\"}.get(o, o), a, prim())
        return a
    tree = expr()
    if i[0] != len(toks): raise ParseError("Expresión de conjuntos mal formada")
    return tree


def _s2sp(n):
    sp = _sp()
    if n[0] == "iv": return sp.Interval(n[1], n[2], n[3], n[4])
    if n[0] == "fin": return sp.FiniteSet(*n[1])
    a, b = _s2sp(n[2]), _s2sp(n[3])
    return {"∪": sp.Union, "∩": sp.Intersection, "\\": sp.Complement}[n[1]](a, b)


def _smember(n, x):
    """Pertenencia con un evaluador propio (comparaciones de números), independiente de SymPy sets."""
    if n[0] == "iv":
        a, b = float(_sp().N(n[1])), float(_sp().N(n[2]))
        return (a < x if n[3] else a <= x) and (x < b if n[4] else x <= b)
    if n[0] == "fin": return any(abs(float(_sp().N(v)) - x) < 1e-12 for v in n[1])
    A, B = _smember(n[2], x), _smember(n[3], x)
    return {"∪": A or B, "∩": A and B, "\\": A and not B}[n[1]]


def _sends(n, acc):
    if n[0] == "iv":
        for v in n[1:3]:
            if v.is_finite: acc.add(float(_sp().N(v)))
    elif n[0] == "fin":
        acc.update(float(_sp().N(v)) for v in n[1])
    else:
        _sends(n[2], acc); _sends(n[3], acc)
    return acc


def op_sets(req, st):
    sp = _sp()
    tree = _sparse(req["expression"])
    R = sp.simplify(_s2sp(tree)) if hasattr(sp, "simplify") else _s2sp(tree)
    R = _s2sp(tree)
    ends = sorted(_sends(tree, set()))
    pts = set(ends)
    for j, e in enumerate(ends):
        pts.update({e - 1.25, e + 0.375})
        if j + 1 < len(ends): pts.add((e + ends[j + 1]) / 2)
    ok = True
    for x in pts:
        if bool(R.contains(sp.nsimplify(x))) != _smember(tree, x): ok = False
    _check(ok, "pertenencia")
    return _res(_set_text(R), "conjuntos_sympy", ("passed", f"pertenencia comprobada en {len(pts)} puntos con un evaluador propio"),
                latex=_latex(R), data={"empty": R == sp.S.EmptySet})


# ------------------------------------------------------------------ derivación implícita
def op_implicit_diff(req, st):
    sp = _sp()
    text = req["expression"]
    l, r = text.split("=", 1) if "=" in text else (text, "0")
    F = _S(l) - _S(r)
    names = req.get("variables") or ["y", "x"]
    y, x = sp.Symbol(names[0]), sp.Symbol(names[1] if len(names) > 1 else "x")
    if y not in F.free_symbols: raise InvalidRequest(f"La ecuación no contiene {y}")
    d = sp.simplify(sp.idiff(F, y, x))
    alt = sp.simplify(-sp.diff(F, x) / sp.diff(F, y))      # teorema de la función implícita (vía distinta de idiff)
    ok = sp.simplify(d - alt) == 0
    _check(ok, "función implícita")
    return _res(_txt(d), "derivacion_implicita",
                ("passed", "coincide con −F_x/F_y (teorema de la función implícita)"),
                latex=r"\frac{d" + y.name + "}{d" + x.name + "} = " + _latex(d),
                conditions=[f"{_txt(sp.diff(F, y))} ≠ 0"])


def run(req, st):
    op = req["operation"]
    _sp()
    if op not in ("matrix_symbolic",) and not req.get("expression"): raise InvalidRequest("Falta 'expression'")
    return {"sum": op_sum_product, "product": op_sum_product, "substitute": op_substitute,
            "matrix_symbolic": op_matrix_symbolic, "logic": op_logic, "sets": op_sets,
            "implicit_diff": op_implicit_diff}[op](req, st)
