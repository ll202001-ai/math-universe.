"""Deducción numérica-exacta de límites en coordenadas polares / cilíndricas / esféricas.

Dada una región descrita por desigualdades g(x,y[,z]) ≥ 0, busca si es una «caja» en un sistema de coordenadas
(a ≤ r ≤ b, α ≤ θ ≤ β, …): halla los extremos por muestreo + bisección, los ajusta a valores exactos (múltiplos de π/12,
racionales, raíces de racionales) y VALIDA la caja contra la región con otros puntos. Si no es una caja exacta, devuelve None.
"""
import math
from fractions import Fraction as F
from . import contraste as CT

PI = math.pi


def _a_cartesianas(sis, q):
    if sis == "polares":
        r, t = q; return (r * math.cos(t), r * math.sin(t))
    if sis == "cilindricas":
        r, t, z = q; return (r * math.cos(t), r * math.sin(t), z)
    rho, ph, t = q
    return (rho * math.sin(ph) * math.cos(t), rho * math.sin(ph) * math.sin(t), rho * math.cos(ph))


def _a_param(sis, p, rango_theta):
    if sis == "polares":
        x, y = p; r = math.hypot(x, y)
        return (r, _ang(math.atan2(y, x), rango_theta)) if r > 1e-12 else (0.0, 0.0)
    if sis == "cilindricas":
        x, y, z = p; r = math.hypot(x, y)
        return (r, _ang(math.atan2(y, x), rango_theta) if r > 1e-12 else 0.0, z)
    x, y, z = p; rho = math.sqrt(x * x + y * y + z * z)
    if rho < 1e-12: return (0.0, 0.0, 0.0)
    ph = math.acos(max(-1.0, min(1.0, z / rho)))
    r = math.hypot(x, y)
    return (rho, ph, _ang(math.atan2(y, x), rango_theta) if r > 1e-12 else 0.0)


def _ang(t, rango):
    lo = rango[0]
    while t < lo: t += 2 * PI
    while t >= lo + 2 * PI: t -= 2 * PI
    return t


NOMBRES = {"polares": ["r", "theta"], "cilindricas": ["r", "theta", "z"], "esfericas": ["rho", "phi", "theta"]}


def _exacto_ang(v, tol=1e-7):
    k = v / PI * 12
    if abs(k - round(k)) < tol * 12:
        fr = F(int(round(k)), 12)
        if fr == 0: return "0"
        num, den = fr.numerator, fr.denominator
        sg = "-" if num < 0 else ""
        num = abs(num)
        cuerpo = "pi" if num == 1 else f"{num}*pi"
        return f"{sg}{cuerpo}" + (f"/{den}" if den != 1 else "")
    return None


def _exacto_long(v, tol=1e-9):
    if abs(v - round(v * 24) / 24) < tol:
        fr = F(round(v * 24), 24)
        return str(fr)
    for den in range(1, 49):
        q = round(v * v * den)
        if den > 0 and abs(v * v - q / den) < tol * max(1, v * v):
            fr = F(q, den)
            return f"sqrt({fr})"
    return None


def _extremos(gs, sis, dim, caja):
    rangos_theta = [(-PI, PI), (0.0, 2 * PI)]
    R = max(math.sqrt(sum(max(abs(a), abs(b)) ** 2 for a, b in caja)), 1e-9)
    mejor = None
    for rt in rangos_theta:
        if sis == "polares": rng = [(0.0, R), rt]
        elif sis == "cilindricas": rng = [(0.0, R), rt, caja[2]]
        else: rng = [(0.0, R), (0.0, PI), rt]
        ins = []
        for q in CT._pts(30000, rng):
            if CT._dentro(gs, _a_cartesianas(sis, q)): ins.append(q)
        if len(ins) < 20: continue
        k = len(rng)
        lo = [min(q[i] for q in ins) for i in range(k)]
        hi = [max(q[i] for q in ins) for i in range(k)]
        # refinar cada extremo por bisección sobre la línea coordenada
        for i in range(k):
            for sentido, cand in ((0, min(ins, key=lambda q: q[i])), (1, max(ins, key=lambda q: q[i]))):
                a = cand[i]; b = rng[i][0] if sentido == 0 else rng[i][1]
                def dentro(v, c=cand, i=i):
                    q = list(c); q[i] = v
                    return CT._dentro(gs, _a_cartesianas(sis, tuple(q)), eps=0.0)
                if dentro(b): a = b
                else:
                    for _ in range(60):
                        m = (a + b) / 2
                        if dentro(m): a = m
                        else: b = m
                if sentido == 0: lo[i] = a
                else: hi[i] = a
        largo = sum(h - l for l, h in zip(lo, hi))
        if mejor is None or largo < mejor[0]: mejor = (largo, lo, hi, rt)
    return mejor


def deducir(gs, dim, sistemas=None):
    """→ (sistema, [[nombre, lo, hi], …] de INTERNA a EXTERNA) o None"""
    caja = CT._caja(gs, dim)
    if caja is None: return None
    for sis in (sistemas or (["polares"] if dim == 2 else ["cilindricas", "esfericas"])):
        e = _extremos(gs, sis, dim, caja)
        if e is None: continue
        _, lo, hi, rt = e
        nom = NOMBRES[sis]
        txt = []
        ok = True
        for i, nm in enumerate(nom):
            es_ang = nm in ("theta", "phi")
            a = _exacto_ang(lo[i]) if es_ang else (_exacto_long(lo[i]) if nm != "z" else _exacto_long(abs(lo[i])))
            b = _exacto_ang(hi[i]) if es_ang else (_exacto_long(hi[i]) if nm != "z" else _exacto_long(abs(hi[i])))
            if nm == "z":
                a = _signo(lo[i], a); b = _signo(hi[i], b)
            if a is None or b is None: ok = False; break
            txt.append([nm, a, b])
        if not ok: continue
        # validación: puntos de la caja cartesiana
        mal = 0; n = 0
        for p in CT._pts(40000, caja, ini=777):
            dentro_reg = CT._dentro(gs, p)
            q = _a_param(sis, p, rt)
            eps = 1e-9
            en_caja = all(lo[i] - eps <= q[i] <= hi[i] + eps for i in range(len(nom)))
            n += 1
            if dentro_reg != en_caja: mal += 1
        if mal / n > 0.0008: continue
        # el orden de integración: interna primero (r, θ…) con θ/φ como externas
        return sis, txt
    return None


def _signo(v, s):
    if s is None: return None
    return ("-" + s if v < 0 and s != "0" else s) if not s.startswith("-") else s


def _extremo_eje(gs, dim, i, caja):
    """mínimo y máximo de la coordenada i en la región (convexa): muestreo + bisección + ascenso por coordenadas (precisión ~1e-12)"""
    ins = [p for p in CT._pts(30000, caja) if CT._dentro(gs, p)]
    if len(ins) < 20: return None
    centro = [sum(p[k] for p in ins) / len(ins) for k in range(dim)]
    if not CT._dentro(gs, tuple(centro)): centro = list(ins[0])
    otros = [k for k in range(dim) if k != i]
    res = []
    for sentido in (0, 1):
        def borde(oth):
            q = list(centro)
            for k, v in oth.items(): q[k] = v
            q[i] = centro[i]
            if not CT._dentro(gs, tuple(q), eps=0.0): return None
            a = centro[i]; b = caja[i][1] if sentido else caja[i][0]
            q[i] = b
            if CT._dentro(gs, tuple(q), eps=0.0): return b
            for _ in range(60):
                m = (a + b) / 2; q[i] = m
                if CT._dentro(gs, tuple(q), eps=0.0): a = m
                else: b = m
            return a
        oth = {k: centro[k] for k in otros}
        best = borde(oth)
        if best is None: return None
        step = 0.25 * max(caja[k][1] - caja[k][0] for k in otros) if otros else 0.0
        while otros and step > 1e-13:
            mov = False
            for k in otros:
                for sg in (1, -1):
                    o2 = dict(oth); o2[k] = oth[k] + sg * step
                    v = borde(o2)
                    if v is not None and ((v > best) if sentido else (v < best)):
                        best = v; oth = o2; mov = True
            if not mov: step /= 2
        res.append(best)
    return res[0], res[1]


def deducir_escalado(gs, dim):
    """regiones que son caja en polares/cilíndricas/esféricas tras trasladar y escalar los ejes (elipses, elipsoides, círculos
    desplazados…). → (sistema, niveles, centros, semiejes) con textos exactos, o None"""
    caja = CT._caja(gs, dim)
    if caja is None: return None
    cen = []; sem = []
    for i in range(dim):
        e = _extremo_eje(gs, dim, i, caja)
        if e is None: return None
        lo, hi = e
        c = (lo + hi) / 2; a = (hi - lo) / 2
        if a <= 1e-9: return None
        cc = _exacto_long(abs(c)) if abs(c) > 1e-9 else "0"
        aa = _exacto_long(a)
        if cc is None or aa is None: return None
        cen.append(("-" + cc) if c < -1e-9 else cc); sem.append(aa)
    def gs2(*u):
        return None
    cf = [float(F(_a_float_txt(c))) if False else _val(c) for c in cen]
    af = [_val(a) for a in sem]
    esc = [(lambda *u, g=g: g(*[cf[k] + af[k] * u[k] for k in range(dim)])) for g in gs]
    r = deducir(esc, dim)
    if r is None: return None
    sis, niv = r
    return sis, niv, cen, sem


def _val(txt):
    from ..parser import parse
    from ..ast_tools import normalize
    return float(compile_ast_val(txt))


def compile_ast_val(txt):
    from .numerico import compile_ast
    from ..parser import parse
    from ..ast_tools import normalize
    return compile_ast(normalize(parse(txt)), [])()
