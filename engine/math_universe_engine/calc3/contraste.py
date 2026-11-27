"""Contraste independiente del resultado con el ENUNCIADO original.

Cuando la región del enunciado está dada solo por desigualdades (x²+y² ≤ 4, x ≥ 0, 0 ≤ z ≤ 2 …), se calcula la cantidad
pedida (área, volumen, integral, masa, centroide, inercia) por cuasi-Monte Carlo (Halton) directamente sobre esas
desigualdades, sin usar ningún planteamiento de integral. Si el resultado del motor no coincide, el planteamiento
interpretó mal el enunciado (restricción ignorada, región equivocada, densidad perdida…) y se rechaza.
No sustituye la verificación por cuadratura: la complementa atacando el error más peligroso (interpretación).
"""
import math
import re
from .numerico import compile_ast
from ..parser import parse
from ..ast_tools import normalize


def _ast(s): return normalize(parse(s))


def _halton(i, base):
    f, r = 1.0, 0.0
    while i > 0:
        f /= base; r += f * (i % base); i //= base
    return r


_PRIMOS = (2, 3, 5)


def _pts(n, caja, ini=1):
    d = len(caja)
    for i in range(ini, ini + n):
        yield tuple(caja[k][0] + (caja[k][1] - caja[k][0]) * _halton(i, _PRIMOS[k]) for k in range(d))


def _compila(s, vs):
    g = compile_ast(_ast(s), vs)
    return g


def desigualdades(ecs, fl, dim):
    """lista de (g, estricta) con g(*coords) ≥ 0 ⇔ se cumple; solo si TODA relación no-cabecera es desigualdad"""
    vs = ["x", "y", "z"][:dim]
    out = []
    hay = False
    for e, _ in ecs:
        if e.cabecera is not None: continue
        if any(op == "=" for op in e.ops): return None
        hay = True
        for k, op in enumerate(e.ops):
            a, b = e.mxp[k], e.mxp[k + 1]
            if op in ("<", "<="): a, b = b, a        # a ≥ b
            try: out.append(_compila(f"({a})-({b})", vs))
            except Exception: return None
    if not hay: return None
    if fl.get("cuadrante"):
        out += [_compila("x", vs), _compila("y", vs)]
    if fl.get("octante") and dim == 3: out.append(_compila("z", vs))
    return out


def _dentro(gs, p, eps=1e-12):
    try:
        for g in gs:
            v = g(*p)
            if isinstance(v, complex) or v < -eps: return False
        return True
    except Exception:
        return False


def _caja(gs, dim):
    for R in (1.5, 3, 6, 12, 24, 48):
        caja = [(-R, R)] * dim
        ins = [p for p in _pts(8000 if dim == 2 else 20000, caja) if _dentro(gs, p)]
        if len(ins) < 6: continue
        lo = [min(p[k] for p in ins) for k in range(dim)]
        hi = [max(p[k] for p in ins) for k in range(dim)]
        if max(max(abs(a), abs(b)) for a, b in zip(lo, hi)) >= 0.97 * R: continue
        pad = [0.12 * (h - l) + 0.1 for l, h in zip(lo, hi)]
        return [(l - q, h + q) for l, h, q in zip(lo, hi, pad)]
    return None


def esperado(ecs, fl, dim, qty, f=None, delta=None, eje=None, gs=None):
    """→ lista de valores esperados (p. ej. [m, x̄, ȳ]) o None si el contraste no aplica"""
    if qty not in ("area", "volumen", "integral", "masa", "centroide", "inercia"): return None
    if qty == "area" and dim != 2: return None
    if qty == "volumen" and dim != 3: return None
    if gs is None: gs = desigualdades(ecs, fl, dim)
    if gs is None: return None
    vs = ["x", "y", "z"][:dim]
    try:
        w = _compila(f if (qty == "integral" and f) else (delta if qty in ("masa", "centroide", "inercia") and delta else "1"), vs)
        if qty == "inercia":
            if eje is None: return None
            otros = [v for v in vs if v != eje]
            if len(otros) != dim - 1: return None
            wi = _compila("+".join(f"{v}^2" for v in otros), vs)
    except Exception:
        return None
    caja = _caja(gs, dim)
    if caja is None: return None
    vol = 1.0
    for a, b in caja: vol *= (b - a)
    N = 90000 if dim == 2 else 160000
    s = 0.0; mom = [0.0] * dim; ine = 0.0
    try:
        for p in _pts(N, caja):
            if not _dentro(gs, p): continue
            ww = w(*p)
            if isinstance(ww, complex): return None
            s += ww
            for k in range(dim): mom[k] += ww * p[k]
            if qty == "inercia": ine += ww * wi(*p)
    except Exception:
        return None
    s *= vol / N; mom = [m * vol / N for m in mom]; ine *= vol / N
    if qty in ("area", "volumen", "integral"): return [s]
    if qty == "inercia": return [ine]
    if abs(s) < 1e-12: return None
    if qty == "masa": return [s] + [m / s for m in mom]
    return [m / s for m in mom]


def coincide(esp, resultado_txt, rel=0.04):
    """cada valor esperado debe aparecer (en tolerancia) entre los números del resultado"""
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+(?:e[+-]?\d+)?|-?\d+(?:e[+-]?\d+)?", resultado_txt or "")]
    if not nums: return None
    escala = max([abs(v) for v in esp] + [1e-9])
    for v in esp:
        tol = rel * max(abs(v), 0.15 * escala) + 1e-6
        if not any(abs(n - v) <= tol for n in nums): return False
    return True
