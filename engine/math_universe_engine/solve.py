"""Ecuaciones de una variable, sistemas lineales y despeje literal (motor exacto propio)."""
import random
from fractions import Fraction
from . import limits
from .ast_tools import eval_q, normalize, free_symbols, to_str, CONSTANTS
from .errors import (NotImplementedOperation, InvalidRequest, MathDomainError, NotSolved, EngineError)
from .parser import parse
from .poly import Poly, u_factor, u_to_poly, u_divmod, u_trim
from .qsqrt import Q
from .rational import RF, Ctx, to_rf, rf_str, condition_list


def split_equation(text):
    parts = text.split("=")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise InvalidRequest("Se esperaba una ecuación con un único signo '='")
    return normalize(parse(parts[0])), normalize(parse(parts[1]))


def _fmt(q): return str(q)


# ---------- raíces de un polinomio univariante con coeficientes racionales ----------
def poly_roots(coeffs):
    """[(raíz Q, multiplicidad)] y bandera 'completo'. Raíces racionales y cuadráticas exactas;
    cúbicas+ irreducibles sin raíz racional quedan sin resolver (completo=False)."""
    sc, facs, _ = u_factor(coeffs)
    roots, complete = [], True
    for f, mult in facs:
        d = len(f) - 1
        if d == 1:
            roots.append((Q(-f[0] / f[1]), mult))
        elif d == 2:
            a, b, c = f[2], f[1], f[0]
            disc = b * b - 4 * a * c
            s = Q.sqrt_rational(disc)
            for sg in (1, -1):
                roots.append(((Q(-b) + s * sg) / (2 * a), mult))
        else:
            complete = False
    return roots, complete


def _order_key(q):
    try: return (0, q.to_float())
    except Exception: return (1, float(q.a))


def _satisfies(q, assumption):
    if assumption is None: return True
    if assumption == "complex": return True
    if assumption in ("real",): return q.is_real()
    if not q.is_real(): return False
    x = q.to_float()
    if assumption == "positive": return x > 0
    if assumption == "negative": return x < 0
    if assumption == "nonzero": return x != 0
    if assumption == "integer": return q.b == 0 and q.a.denominator == 1
    return True


def solve_one_variable(lhs, rhs, var, assumptions):
    ctx = Ctx(assumptions)
    f = (to_rf(lhs, ctx) - to_rf(rhs, ctx)).cancel(ctx.warnings)
    others = [v for v in (f.n.vars() + f.d.vars()) if v != var]
    import re as _re2
    dep = [v for v in set(others) if _re2.search(r"\b" + _re2.escape(var) + r"\b", v)]
    if dep:
        raise NotImplementedOperation(f"Ecuación con funciones no polinómicas de {var} ({', '.join(sorted(dep))}): "
                                      "radicales, valor absoluto, exponenciales, logaritmos y trigonométricas aún no se resuelven")
    if others: raise NotImplementedOperation(f"Parámetros libres {sorted(set(others))}: use despeje literal (una sola variable)")
    conds = condition_list(ctx.conds, assumptions)
    # raíces del numerador SIN cancelar que anulan un denominador: se informan como excluidas
    try:
        raw = to_rf(lhs, Ctx(assumptions)) - to_rf(rhs, Ctx(assumptions))
        excluded = []
        if raw.n.vars() == [var] and not raw.n.is_zero():
            rr, _ = poly_roots(raw.n.to_upoly(var))
            for q, _m in rr:
                if any((not p.is_const()) and p.evaluate({var: q}) == 0 for p in ctx.conds if set(p.vars()) <= {var}):
                    excluded.append(f"{var} = {q} excluida: anula un denominador de la ecuación original")
        ctx.warnings.extend(excluded)
    except Exception:
        pass
    if var not in f.n.vars() and not f.n.is_zero():
        return {"kind": "none", "conditions": conds, "ctx": ctx, "f": f}
    if f.n.is_zero():
        return {"kind": "all", "conditions": conds, "ctx": ctx, "f": f}
    return {"kind": "roots", "conditions": conds, "ctx": ctx, "f": f, "var": var}


def finish_roots(info, var, assumptions, original_conds):
    """Calcula raíces, filtra dominio/supuestos/denominadores. Devuelve dict de resultados."""
    f = info["f"]
    roots, complete = poly_roots(f.n.to_upoly(var))
    dom = assumptions.get(var, "real")
    kept, dropped = [], []
    # polinomios que deben ser ≠ 0
    forb = [p for p in info["ctx"].conds if not p.is_const()]
    for r, m in roots:
        bad = False
        for p in forb:
            try:
                if p.evaluate({var: r}) == 0: bad = True; break
            except Exception: pass
        if bad: dropped.append((r, "anula un denominador")); continue
        if dom != "complex" and not r.is_real():
            dropped.append((r, "solución no real")); continue
        if not _satisfies(r, dom if dom != "real" else None):
            dropped.append((r, f"incumple el supuesto {dom}")); continue
        kept.append((r, m))
    kept.sort(key=lambda t: _order_key(t[0]))
    return kept, dropped, complete


# ---------- sistemas lineales ----------
def rref(M, ncols_coef, log):
    M = [row[:] for row in M]; rows = len(M); r = 0; pivots = []
    for c in range(ncols_coef):
        limits.check()
        p = next((i for i in range(r, rows) if M[i][c] != 0), None)
        if p is None: continue
        if p != r:
            M[r], M[p] = M[p], M[r]; log.append(f"F{r+1} <-> F{p+1}")
        pv = M[r][c]
        if pv != 1:
            M[r] = [x / pv for x in M[r]]; log.append(f"F{r+1} <- F{r+1}/({_fr(pv)})")
        for i in range(rows):
            if i != r and M[i][c] != 0:
                fct = M[i][c]; M[i] = [a - fct * b for a, b in zip(M[i], M[r])]
                log.append(f"F{i+1} <- F{i+1} - ({_fr(fct)})*F{r+1}")
        pivots.append(c); r += 1
        if r == rows: break
    return M, pivots


def _fr(x): return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def linear_system(texts, variables=None):
    eqs = [split_equation(t) for t in texts]
    polys = []
    for l, r in eqs:
        ctx = Ctx(); f = to_rf(l, ctx) - to_rf(r, ctx)
        if not f.d.is_const() or ctx.conds:
            raise NotImplementedOperation("Sistema con denominadores variables: no es lineal en las incógnitas")
        polys.append(f.n.scale(1 / f.d.const_value()))
    syms = sorted({v for p in polys for v in p.vars()})
    vs = variables or syms
    extra = [s for s in syms if s not in vs]
    if extra: raise NotImplementedOperation(f"Símbolos {extra} no declarados como incógnitas (parámetros no soportados en sistemas)")
    A, b = [], []
    for p in polys:
        row = [Fraction(0)] * len(vs); const = Fraction(0)
        for m, c in p.t.items():
            if m == (): const = c
            elif len(m) == 1 and m[0][1] == 1: row[vs.index(m[0][0])] += c
            else: raise NotImplementedOperation("El sistema no es lineal")
        A.append(row); b.append(-const)
    return eqs, vs, A, b


def solve_linear(texts, variables, assumptions):
    eqs, vs, A, b = linear_system(texts, variables)
    n = len(vs); aug = [A[i] + [b[i]] for i in range(len(A))]
    log = []
    R, piv = rref(aug, n, log)
    rank = len(piv)
    inconsistent = any(all(x == 0 for x in row[:n]) and row[n] != 0 for row in R)
    rank_aug = rank + (1 if inconsistent else 0)
    data = {"variables": vs, "coefficient_matrix": [[_fr(x) for x in r] for r in A],
            "augmented_matrix": [[_fr(x) for x in r] for r in aug],
            "rref": [[_fr(x) for x in r] for r in R], "rank_A": rank, "rank_augmented": rank_aug,
            "row_operations": log}
    if inconsistent: return "none", data, eqs, vs, None
    free = [vs[c] for c in range(n) if c not in piv]
    sol = {}
    for i, c in enumerate(piv):
        expr = Poly.const(R[i][n])
        for fcol in range(n):
            if fcol not in piv and R[i][fcol] != 0:
                expr = expr - Poly.var(vs[fcol]).scale(R[i][fcol])
        sol[vs[c]] = expr
    for v in free: sol[v] = Poly.var(v)
    data["free_variables"] = free
    return ("unique" if not free else "infinite"), data, eqs, vs, sol


def verify_linear(kind, eqs, vs, sol, trials=4):
    """Sustituye en las ecuaciones ORIGINALES (AST) con aritmética exacta."""
    free = [v for v in vs if sol[v].vars() == [v] and sol[v] == Poly.var(v)]
    rng = random.Random(7); n = 1 if kind == "unique" else trials
    for _ in range(n):
        env = {v: Fraction(rng.randint(-9, 9), rng.randint(1, 4)) for v in free}
        full = dict(env)
        for v in vs:
            full[v] = sol[v].evaluate(env) if sol[v].vars() else sol[v].const_value()
        for l, r in eqs:
            if eval_q(l, full) != eval_q(r, full): return "failed"
    return "passed"


# ---------- despeje literal ----------
def isolate(lhs, rhs, var, assumptions):
    ctx = Ctx(assumptions)
    f = (to_rf(lhs, ctx) - to_rf(rhs, ctx))
    # trabajar con el numerador; los denominadores pasan a condiciones
    if not f.d.is_const(): ctx.conds.append(f.d)
    num = f.n
    co = num.coeffs_in(var)
    if not co or max(co) == 0 and True and var not in num.vars():
        raise InvalidRequest(f"La variable '{var}' no aparece en la ecuación" + (". Los identificadores de varias letras son símbolos únicos; use * para multiplicar" if any(len(x) > 1 and var in x for x in free_symbols(lhs) | free_symbols(rhs)) else ""))
    deg = max(co)
    if deg != 1:
        raise NotImplementedOperation(f"Despeje literal solo implementado para grado 1 en '{var}' (grado {deg})")
    c1, c0 = co[1], co.get(0, Poly())
    ctx.conds.append(c1)
    res = RF(-c0, c1).cancel(ctx.warnings)
    return res, ctx, c1


def verify_isolate(lhs, rhs, var, result_ast, assumptions, trials=5):
    syms = sorted((free_symbols(lhs) | free_symbols(rhs) | free_symbols(result_ast)) - {var})
    rng = random.Random(11); ok = 0
    for _ in range(trials * 6):
        env = {s: Fraction(rng.randint(1, 12), rng.randint(1, 5)) * rng.choice([1, 1, -1]) for s in syms}
        for s, a in assumptions.items():
            if s in env:
                if a == "positive": env[s] = abs(env[s])
                elif a == "negative": env[s] = -abs(env[s])
        try:
            val = eval_q(result_ast, env)
            e2 = dict(env); e2[var] = val
            if eval_q(lhs, e2) != eval_q(rhs, e2): return "failed"
            ok += 1
        except MathDomainError:
            continue
        if ok >= trials: break
    return "passed" if ok else "not_possible"
