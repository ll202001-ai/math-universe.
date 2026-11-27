"""Intérprete de enunciados de Matemática III.

Entrada: el ejercicio escrito como en la guía («Evalúe ∭ 6xy dV, donde E está bajo el plano z = 1 + x + y y sobre la región plana
acotada por y = √x, y = 0 y x = 1»). Salida: la solicitud estructurada de `api3` (tipo + datos), que se resuelve con los mismos
métodos y la misma verificación independiente que los formularios. El intérprete NO calcula: solo lee, clasifica y plantea.
"""
import math
import re
from fractions import Fraction as F
from ..errors import InvalidRequest
from ..parser import parse
from ..ast_tools import normalize, free_symbols, to_str as ast_str, subs as ast_subs
from .texto import normalizar, quitar_acentos, mx, ecuaciones, tokens_texto, _separar_conjunciones, _REL
from .numerico import compile_ast
from . import contraste as CT
from . import politopo as PO

COORD = {"x", "y", "z"}
CONST_SYM = {"pi", "e"}
HEADERS = {"f", "g", "h", "delta", "I", "V", "P", "C", "U", "F", "G"}


class NoReconocido(InvalidRequest):
    pass


# ------------------------------------------------------------------------------------------------ utilidades
def _ast(s):
    return normalize(parse(mx(s) if not _es_mx(s) else s))


def _es_mx(s):
    return False


def _syms(s):
    try:
        return {v for v in free_symbols(_ast(s)) if v not in CONST_SYM}
    except Exception:
        return set()


def _ordenados(s):
    """símbolos en orden de aparición"""
    out = []
    for m in re.finditer(r"[A-Za-z_]\w*", mx(s)):
        w = m.group(0)
        if w in out or w in CONST_SYM or w in ("sin", "cos", "tan", "ln", "exp", "sqrt", "abs", "log", "sec", "csc", "cot", "asin", "acos", "atan", "sinh", "cosh", "tanh"):
            continue
        out.append(w)
    return out


def _txt(a):
    return ast_str(a)


class Ec:
    """ecuación o desigualdad: partes en notación del motor y operadores"""
    def __init__(self, crudo):
        self.crudo = crudo
        partes = re.split(r"(<=|>=|=|<|>)", crudo)
        self.partes = [p.strip() for p in partes[0::2]]
        self.ops = partes[1::2]
        self.cabecera = None
        m = re.match(r"^\s*([A-Za-z]\w*)\s*\(([^)]*)\)\s*$", self.partes[0]) if self.ops == ["="] else None
        if m and m.group(1) not in COORD | {"sin", "cos", "ln", "exp", "sqrt"}:
            self.cabecera = (m.group(1), [a.strip() for a in m.group(2).split(",")])
            self.mxp = [None, mx(self.partes[1])]
            return
        self.mxp = [mx(p) for p in self.partes]

    @property
    def es_igualdad(self):
        return self.ops == ["="]

    @property
    def lhs(self): return self.mxp[0]

    @property
    def rhs(self): return self.mxp[-1]

    def simbolos(self):
        s = set()
        for p in self.mxp:
            if p is not None: s |= _syms(p)
        return s

    def como_curva(self):
        return f"{self.mxp[0]}={self.mxp[1]}"

    def __repr__(self):
        return f"Ec({self.crudo})"


def leer_ecuaciones(texto):
    """[(Ec, sección)] — la sección aumenta tras cada «sujeta a / s.a.»"""
    t = quitar_acentos(normalizar(texto))
    toks = tokens_texto(t)
    seccion = 0
    marcas = []
    for k, s in toks:
        if k == "text" and s == "SUJETOA": marcas.append(1)
    toks = _separar_conjunciones(toks)
    tramos = []; cur = []; prof = 0; sec = 0
    for k, s in toks:
        if k == "text" and s == "SUJETOA":
            if cur: tramos.append((cur, sec)); cur = []
            sec += 1; continue
        if s == "(": prof += 1
        if s == ")": prof = max(0, prof - 1)
        sepr = (k == "text") or (k == "sep" and not s.isspace() and s != "'") or (k == "op" and s == "," and prof == 0)
        if sepr:
            if cur: tramos.append((cur, sec)); cur = []
        elif not (k == "sep" and s.isspace()):
            cur.append((k, s))
    if cur: tramos.append((cur, sec))
    out = []
    for tr, sc in tramos:
        if any(s in _REL for _, s in tr) and tr[0][1] not in _REL and tr[-1][1] not in _REL:
            try: out.append((Ec(" ".join(s for _, s in tr)), sc))
            except Exception: continue
    return out


def _num(s):
    return F(str(s).replace(" ", ""))


def _pares_puntos(t):
    """todos los puntos (a, b[, c]) del texto"""
    pts = []
    for m in re.finditer(r"\(\s*(-?\s*\d+(?:\.\d+)?(?:/\d+)?)\s*,\s*(-?\s*\d+(?:\.\d+)?(?:/\d+)?)(?:\s*,\s*(-?\s*\d+(?:\.\d+)?(?:/\d+)?))?\s*\)", t):
        pts.append(tuple(str(_num(g)) for g in m.groups() if g is not None))
    return pts


def _flags(T):
    return {
        "octante": "primer octante" in T,
        "cuadrante": "primer cuadrante" in T or "primer octante" in T,
        "cil": "cilindric" in T, "esf": "esferic" in T, "pol": "polar" in T,
    }


# ------------------------------------------------------------------------------------------------ manejadores
def _jacobiano(T, ecs):
    asig = [e for e, _ in ecs if e.es_igualdad and e.cabecera is None]
    if len(asig) < 2: raise NoReconocido("Para el jacobiano escriba la transformación, p. ej. x = u cos v, y = u sen v")
    lhs = [e.lhs for e in asig]
    if all(re.fullmatch(r"[A-Za-z]\w*", l) for l in lhs):
        directo = all(l in COORD for l in lhs) or not any(s in COORD for e in asig for s in _syms(e.rhs))
        if directo:
            old = lhs
            new = []
            for e in asig:
                for s in _ordenados(e.rhs):
                    if s not in old and s not in new: new.append(s)
            return {"tipo": "jacobiano", "viejas": old, "nuevas": new, "mapa": {e.lhs: e.rhs for e in asig}, "modo": "directo"}, \
                [f"Transformación directa: {', '.join(e.lhs + ' = ' + e.rhs for e in asig)}"]
        new = lhs
        old = []
        for e in asig:
            for s in _ordenados(e.rhs):
                if s not in new and s not in old: old.append(s)
        return {"tipo": "jacobiano", "viejas": old, "nuevas": new, "mapa": {e.lhs: e.rhs for e in asig}, "modo": "inverso"}, \
            [f"Transformación inversa: {', '.join(e.lhs + ' = ' + e.rhs for e in asig)} (se despejan las variables originales)"]
    raise NoReconocido("No pude identificar las variables de la transformación")


def _ajuste(T, texto):
    pts = [p for p in _pares_puntos(normalizar(texto)) if len(p) == 2]
    if len(pts) < 2: raise NoReconocido("Escriba los puntos del ajuste, p. ej. (1,1), (2,1) y (3,3)")
    return {"tipo": "ajuste_lineal", "puntos": [list(p) for p in pts]}, [f"Recta de mínimos cuadrados y = mx + b con los puntos {', '.join('(' + a + ', ' + b + ')' for a, b in pts)}"]


def _vars_de(expr_txts, defecto=None):
    s = set()
    for e in expr_txts: s |= _syms(e)
    orden = [v for v in ("x", "y", "z", "w") if v in s]
    if not orden:
        orden = sorted(s)
    return orden


def _optimizacion(T, texto, ecs):
    plan_notas = []
    cab = [(e, sc) for e, sc in ecs if e.cabecera is not None]
    # objetivo
    obj = None; vars_ = None
    if cab:
        e = cab[0][0]
        nombre, args = e.cabecera
        obj = e.rhs; vars_ = args
        otras = [(x, sc) for x, sc in ecs if x is not e]
    else:
        otras = list(ecs)
    # «f = expr» sin argumentos
    if obj is None:
        for e, sc in otras:
            if e.es_igualdad and re.fullmatch(r"[fgIPVCU]|delta", e.lhs):
                obj = e.rhs; otras = [(x, s) for x, s in otras if x is not e]; break
    pts = _pares_puntos(normalizar(texto))
    # --- caja rectangular más grande
    if obj is None and ("caja" in T or "paralelepipedo" in T) and ("mas grande" in T or "maximo" in T or "maxim" in T):
        planos = [e for e, sc in otras if e.es_igualdad]
        if not planos: raise NoReconocido("Indique el plano donde está el vértice de la caja, p. ej. x + 2y + 3z = 6")
        return {"tipo": "lagrange", "f": "x*y*z", "restricciones": [e.como_curva() for e in planos], "variables": ["x", "y", "z"], "positivo": True}, \
            ["Caja con tres caras en los planos coordenados y un vértice (x, y, z) sobre el plano: se maximiza V = xyz sujeta a la ecuación del plano (Lagrange, x, y, z > 0)"]
    # --- punto más cercano / lejano a un punto dado
    if obj is None and any(k in T for k in ("mas cercano", "mas lejano", "mas proximo", "distancia minima", "distancia maxima", "mas cerca", "mas lejos")):
        sup = [e for e, sc in otras if e.es_igualdad]
        dim3 = any("z" in e.simbolos() for e in sup)
        vs = ["x", "y", "z"] if dim3 else ["x", "y"]
        if "origen" in T or not pts:
            centro = ["0"] * len(vs)
        else:
            centro = list(pts[-1][:len(vs)])
            if len(centro) < len(vs): raise NoReconocido("El punto de referencia no tiene el mismo número de coordenadas que la superficie")
        f = "+".join(f"({v}-({c}))^2" for v, c in zip(vs, centro))
        return {"tipo": "lagrange", "f": f, "restricciones": [e.como_curva() for e in sup], "variables": vs, "distancia": True}, \
            [f"Se optimiza el cuadrado de la distancia {f} sujeto a {', '.join(e.crudo for e in sup)}; la distancia es la raíz cuadrada del valor de f"]
    if obj is None:
        # «maximizar/minimizar E» o «extremos de E»
        m = re.search(r"(?:maximiz\w*|minimiz\w*|optimiz\w*|extremos?\s+(?:locales\s+)?de(?:\s+la\s+funcion)?)\s+(.+?)(?:\s+SUJETOA|\.|$)", quitar_acentos(normalizar(texto)), flags=re.I)
        if m and not any(e.es_igualdad and e.lhs in ("f",) for e, _ in otras):
            cand = m.group(1)
            ee = ecuaciones(cand)
            if ee: cand = re.split(r"(?:<=|>=|=)", ee[0])[-1]
            obj = mx(cand)
    if obj is None:
        raise NoReconocido("No encontré la función a optimizar. Escríbala como f(x,y) = … (y las restricciones después de «s.a.»)")
    restr = [e for e, sc in otras if sc >= 1 or (cab and sc >= 1)]
    if not restr:
        restr = [e for e, sc in otras if e.es_igualdad and e.lhs not in ("f",) and not (e.lhs in COORD and e.rhs.replace(".", "").isdigit() and False)] if (("lagrange" in T) or ("restric" in T)) else []
    if vars_ is None: vars_ = _vars_de([obj] + [e.lhs + "+" + e.rhs for e in restr])
    simb = _syms(obj)
    params = [s for s in sorted(simb) if s not in vars_ and s not in CONST_SYM]
    nv = len(vars_)
    # --- parámetros
    if params:
        mv = re.search(r"valor\s+(?:maximo|minimo)\s+local\s+de\s+(-?\d+(?:\.\d+)?)", quitar_acentos(normalizar(texto)))
        if len(pts) and not restr and (mv or len(params) > 1):
            punto = list(pts[-1][:nv]) if len(pts[-1]) >= nv else None
            if punto is None: raise NoReconocido("Indique el punto, p. ej. en el punto (3, −5)")
            plan = {"tipo": "parametros_extremo", "f": obj, "variables": vars_, "punto": list(punto), "parametros": params}
            if mv: plan["valor"] = mv.group(1)
            return plan, [f"Parámetros {', '.join(params)}: se exige punto crítico y condición de extremo en ({', '.join(punto)})" + (f" con valor {mv.group(1)}" if mv else "")]
        if len(params) == 1 and pts:
            punto = list(pts[-1][:nv])
            ext = "maximo" if "maximo" in T and "minimo" not in T else "minimo"
            return {"tipo": "parametros_condicion", "f": obj, "variables": vars_, "punto": punto, "parametro": params[0], "extremo": ext}, \
                [f"Se busca el valor de {params[0]} para el que ({', '.join(punto)}) es un {ext} local"]
        if len(params) == 1:
            ext = "maximo" if "maximo" in T and "minimo" not in T else "minimo"
            return {"tipo": "parametros_condicion", "f": obj, "variables": vars_, "punto": ["0"] * nv, "parametro": params[0], "extremo": ext}, \
                [f"Se busca el valor de {params[0]} para el que el origen es un {ext} local"]
    restr = [x for x in restr if x.es_igualdad]
    if restr:
        positivo = bool(re.search(r"\^\(\s*\d+\s*/\s*\d+\s*\)", obj)) or "primer octante" in T or "no negativ" in T or "positiv" in T \
            or bool(re.search(r"[xyz](?:\s*,\s*[xyz])*\s*(?:>|>=)\s*0", T))
        return {"tipo": "lagrange", "f": obj, "restricciones": [e.como_curva() for e in restr], "variables": vars_, "positivo": positivo}, \
            [f"Optimizar f = {obj} sujeta a {'; '.join(e.crudo for e in restr)} (multiplicadores de Lagrange)"]
    return {"tipo": "extremos", "f": obj, "variables": vars_}, [f"Extremos locales de f = {obj} (puntos críticos y criterio de la Hessiana)"]



# ------------------------------------------------------------------------------------------------ geometría numérica de curvas/superficies
def _g(e, vars_):
    """función numérica L-R de una ecuación"""
    a = ("bin", "-", _ast(e.mxp[0]), _ast(e.mxp[-1]))
    return compile_ast(a, list(vars_))


def _resolver_lineal(A, b):
    n = len(A)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12: return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def _ajustar(g, base, nvars, semilla=3):
    """coeficientes de g en la base de monomios; None si g no es combinación de la base"""
    import random
    rnd = random.Random(semilla)
    m = len(base)
    pts = [[rnd.uniform(-2.3, 2.7) for _ in range(nvars)] for _ in range(m + 8)]
    try:
        vals = [g(*p) for p in pts]
    except Exception:
        return None
    A = [[b(*p) for b in base] for p in pts[:m]]
    c = _resolver_lineal(A, vals[:m])
    if c is None: return None
    for p, v in zip(pts[m:], vals[m:]):
        if abs(sum(ci * b(*p) for ci, b in zip(c, base)) - v) > 1e-8 * (1 + abs(v)): return None
    return c


def _q(x):
    f = F(x).limit_denominator(1000)
    return f if abs(float(f) - x) < 1e-9 else None


_B2 = [lambda x, y: x * x, lambda x, y: y * y, lambda x, y: x * y, lambda x, y: x, lambda x, y: y, lambda x, y: 1.0]
_B3 = [lambda x, y, z: x * x, lambda x, y, z: y * y, lambda x, y, z: z * z, lambda x, y, z: x * y, lambda x, y, z: x * z,
       lambda x, y, z: y * z, lambda x, y, z: x, lambda x, y, z: y, lambda x, y, z: z, lambda x, y, z: 1.0]


def clase_curva(e):
    """clasifica una curva del plano: circulo(centro, r²) / recta(a,b,c) / otra"""
    g = _g(e, ("x", "y"))
    c = _ajustar(g, _B2, 2)
    if c is None: return ("otra",)
    a, b, cxy, d, ee, f0 = c
    if abs(cxy) < 1e-9 and abs(a - b) < 1e-9 and abs(a) > 1e-9:
        D, E, Fc = d / a, ee / a, f0 / a
        cx, cy = -D / 2, -E / 2
        r2 = cx * cx + cy * cy - Fc
        if r2 > 1e-12: return ("circulo", cx, cy, r2)
        return ("otra",)
    if abs(a) < 1e-9 and abs(b) < 1e-9 and abs(cxy) < 1e-9:
        return ("recta", d, ee, f0)
    return ("otra",)


def clase_superficie(e):
    g = _g(e, ("x", "y", "z"))
    c = _ajustar(g, _B3, 3)
    if c is None: return ("otra",)
    a, b, cc, xy, xz, yz, dx, dy, dz, k = c
    if max(abs(xy), abs(xz), abs(yz), abs(dx), abs(dy), abs(dz)) < 1e-9:
        if abs(a - b) < 1e-9 and abs(a - cc) < 1e-9 and abs(a) > 1e-9 and -k / a > 1e-12:
            return ("esfera", -k / a)
        if abs(a - b) < 1e-9 and abs(a) > 1e-9 and abs(cc) > 1e-9 and abs(k) < 1e-9 and a * cc < 0:
            return ("cono", -cc / a)          # a(x²+y²) + cc z² = 0 →  z² = (-a/cc)(x²+y²)... se guarda cc/(-a)
    if max(abs(a), abs(b), abs(cc), abs(xy), abs(xz), abs(yz), abs(dx), abs(dy)) < 1e-9 and abs(dz) > 1e-9:
        return ("plano_z", -k / dz)
    return ("otra",)


def _angulo_exacto(t):
    """ángulo en rad → texto exacto si es múltiplo de π/12 (si no, decimal)"""
    k = t / (math.pi / 12)
    if abs(k - round(k)) < 1e-9:
        f = F(int(round(k)), 12)
        if f == 0: return "0"
        n, d = f.numerator, f.denominator
        return ("pi" if (n, d) == (1, 1) else f"{n}*pi" if d == 1 else f"pi/{d}" if n == 1 else f"{n}*pi/{d}")
    return repr(t)


def _txt_raiz(r2):
    """r (positivo) con r² = r2 → texto exacto si r2 racional con raíz exacta o √q"""
    q = _q(r2)
    if q is None: return repr(math.sqrt(r2))
    n, d = q.numerator, q.denominator
    rn, rd = math.isqrt(n), math.isqrt(d)
    if rn * rn == n and rd * rd == d: return str(F(rn, rd))
    return f"sqrt({q})"

# ------------------------------------------------------------------------------------------------ integrales
_DIFERENCIALES = r"(?:d[xyz]|dr|dt|du|dv|dw|dtheta|dphi|drho)"


def _acotar(txt, pos):
    """lee un límite de integración desde txt[pos:]; admite {..}, (..) o un átomo; devuelve (texto, nueva posición)"""
    while pos < len(txt) and txt[pos] == " ": pos += 1
    if pos >= len(txt): raise NoReconocido("Límite de integración incompleto")
    if txt[pos] in "{(":
        cierra = "}" if txt[pos] == "{" else ")"
        d = 0; j = pos
        while j < len(txt):
            if txt[j] in "{(": d += 1
            elif txt[j] in "})":
                d -= 1
                if d == 0: break
            j += 1
        inner = txt[pos + 1:j] if txt[pos] == "{" else txt[pos:j + 1]
        return inner, j + 1
    m = re.match(r"[-+]?(?:\d+(?:\.\d+)?|[A-Za-z]+\d*)(?:\([^()]*\))?", txt[pos:])
    if not m: raise NoReconocido(f"No pude leer el límite «{txt[pos:pos + 12]}»")
    return m.group(0), pos + m.end()


def _iterada_explicita(n):
    """∫_a^b ∫_c^d f dy dx  → niveles interior→exterior e integrando"""
    n2 = n.replace("\\int", "∫")
    k = n2.find("∫")
    if k < 0: raise NoReconocido("")
    pos = k; limites = []
    while pos < len(n2) and n2[pos] == "∫":
        pos += 1
        while pos < len(n2) and n2[pos] == " ": pos += 1
        if n2[pos:pos + 1] != "_": raise NoReconocido("Escriba los límites como ∫_{a}^{b}")
        lo, pos = _acotar(n2, pos + 1)
        while pos < len(n2) and n2[pos] == " ": pos += 1
        if n2[pos:pos + 1] != "^": raise NoReconocido("Escriba los límites como ∫_{a}^{b}")
        hi, pos = _acotar(n2, pos + 1)
        limites.append((lo, hi))
        while pos < len(n2) and n2[pos] == " ": pos += 1
    resto = n2[pos:]
    # diferenciales al final del integrando: «... dy dx»
    m = re.search(r"((?:\s*" + _DIFERENCIALES + r")+)\s*(?:[,.;]|$|\s(?=[A-Za-zÁ-ú]{3,}))", resto)
    if not m: raise NoReconocido("Faltan los diferenciales (dx, dy, dz) al final de la integral")
    difs = re.findall(r"d(theta|phi|rho|[xyzrtuvw])", m.group(1))
    integrando = resto[:m.start()].strip()
    if len(difs) != len(limites): raise NoReconocido(f"Hay {len(limites)} signos de integral y {len(difs)} diferenciales")
    niveles = []
    for var, (lo, hi) in zip(difs, reversed(limites)):
        niveles.append([var, mx(lo), mx(hi)])
    return mx(integrando) if integrando else "1", niveles, difs


def _region_geom(ecs, n, T):
    """separa: cabeceras (f, δ), cadenas de desigualdades, curvas/superficies de igualdad y vértices"""
    cab = {}
    cadenas = []; curvas = []; simples = []
    for e, sc in ecs:
        if e.cabecera is not None:
            nom = e.cabecera[0]
            if nom in ("rho", "mu", "sigma", "lam", "dens", "densidad") and set(e.cabecera[1]) <= COORD: nom = "delta"
            cab[nom] = e
        elif e.es_igualdad and e.lhs in HEADERS and e.lhs != "V" and not re.search(r"[xyz]", e.lhs):
            cab[e.lhs] = e
        elif len(e.ops) == 2 and all(o in ("<=", "<", ">=", ">") for o in e.ops):
            cadenas.append(e)
        elif not e.es_igualdad:
            simples.append(e)
        else:
            curvas.append(e)
    vert = []
    mv = re.search(r"v[eé]rtices?[^(]*((?:\(\s*-?[\d./]+\s*,\s*-?[\d./]+\s*\)[\s,y]*(?:e\s+)?)+)", quitar_acentos(n))
    if mv: vert = [p for p in _pares_puntos(mv.group(1)) if len(p) == 2]
    return cab, cadenas, curvas, simples, vert


def _poligono(vert):
    cur = []
    k = len(vert)
    for i in range(k):
        (x1, y1), (x2, y2) = [tuple(F(c) for c in p) for p in (vert[i], vert[(i + 1) % k])]
        if x1 == x2: cur.append(f"x={x1}")
        else:
            m = (y2 - y1) / (x2 - x1); b = y1 - m * x1
            cur.append(f"y=({m})*x+({b})")
    cx = sum(float(F(p[0])) for p in vert) / k; cy = sum(float(F(p[1])) for p in vert) / k
    return cur, [cx, cy]


def _dens_frase(T, dim, eje=None):
    suma = {2: "x^2+y^2", 3: "x^2+y^2+z^2"}[dim]
    m = re.search(r"distancia (?:de p )?al eje ([xyz])", T)
    if m:
        e = m.group(1)
        base = {"x": "y^2+z^2", "y": "x^2+z^2", "z": "x^2+y^2"}[e]
        return f"({base})" if "cuadrado" in T else f"sqrt({base})"
    if "distancia al origen" in T or "distancia del origen" in T:
        return f"({suma})" if "cuadrado" in T else f"sqrt({suma})"
    if "distancia" in T and "plano xy" in T and dim == 3: return "z"
    return None


def _quantity(T, n):
    if "momento de inercia" in T or "momentos de inercia" in T: return "inercia"
    if "centro de masa" in T or re.search(r"\bmasa\b", T): return "masa"
    if "centroide" in T: return "centroide"
    if "volumen" in T: return "volumen"
    if re.search(r"\barea\b", T): return "area"
    return "integral"


def _integrando_texto(n):
    m0 = re.search(r"integral(?:es)?\s+(?:doble|triple|iterada)?\s*de\s+(.+?)\s+(?:d[AV]\b|sobre\b|en\s+(?:la|el|r|e)\b|donde\b|extendida\b|para\b)", n, re.I)
    if m0 and not re.search(r"DOBLEINT|TRIPLEINT|∫", n): return mx(m0.group(1))
    m = re.search(r"(?:DOBLEINT|TRIPLEINT|∫)\s*(?:_\{?[A-Za-z]\}?\s+|[A-Z]\s+)?(.+?)\s*d[VAS]\b", n)
    if m: return mx(m.group(1))
    return None


def _integral(T, n, ecs, notas):
    fl = _flags(T)
    cab, cadenas, curvas, simples, vert = _region_geom(ecs, n, T)
    qty = _quantity(T, n)
    # ---- 1) integral iterada con límites escritos
    if "∫" in n and "_" in n and re.search(r"∫\s*_", n):
        if True:
            f, niv, difs = _iterada_explicita(n)
            if any(k in T for k in ("invierta", "cambie el orden", "cambio de orden", "orden de integracion")) and len(niv) == 2:
                (v1, lo1, hi1), (v2, lo2, hi2) = niv
                curvas2 = [f"{v1}={lo1}", f"{v1}={hi1}", f"{v2}={lo2}", f"{v2}={hi2}"]
                curvas2 = [c for c in curvas2 if not re.fullmatch(r"\w+=(.+)", c) or True]
                notas.append(f"Integral ∫∫ {f} d{v1} d{v2} con la región limitada por {', '.join(curvas2)}: se invierte el orden")
                return {"tipo": "cambio_orden", "f": f, "curvas": curvas2}
            notas.append(f"Integral iterada de {f}; niveles (de adentro hacia afuera): " + "; ".join(f"{v} de {a} a {b}" for v, a, b in niv))
            return {"tipo": "iterada", "f": f, "niveles": niv}
    # ---- 2a) paralelogramo/paralelepípedo: cadenas a <= (forma lineal) <= b
    if cadenas and not curvas and any(not re.fullmatch(r"[A-Za-z]\w*", e.mxp[1]) for e in cadenas):
        return _caja_lineal(T, n, cadenas, cab, qty, notas)
    # ---- 2) región dada por desigualdades encadenadas (conjunto E = {...})
    if cadenas and not curvas:
        f = _integrando_texto(n) or (cab["f"].rhs if "f" in cab else "1")
        niv = _niveles_de_cadenas(cadenas, simples)
        if qty in ("volumen", "area") and f == "1": pass
        notas.append("Región escrita con desigualdades: " + "; ".join(e.crudo for e in cadenas) + f". Integrando {f}")
        return {"tipo": "iterada", "f": f, "niveles": niv}
    # ---- 3) región por curvas / superficies
    f = _integrando_texto(n)
    if f is None and "f" in cab: f = cab["f"].rhs
    delta = None
    if "delta" in cab: delta = cab["delta"].rhs
    if f is None: f = "1"
    dim3 = (any("z" in e.simbolos() for e in curvas) or "TRIPLEINT" in n or " dv" in " " + T or "solido" in T or "paralelepipedo" in T) and not (
        qty == "area" or "lamina" in T or "region plana" in T and qty in ("masa", "centroide") and not any("z" in e.simbolos() for e in curvas))
    if "DOBLEINT" in n and not any("z" in e.simbolos() for e in curvas): dim3 = False
    pol = list(curvas)
    puntos = None
    if vert:
        c, puntos = _poligono(vert)
        pol = [Ec(x) for x in c] + pol
        notas.append("Región poligonal de vértices " + ", ".join(f"({a}, {b})" for a, b in vert))
    ejes = []
    if fl["cuadrante"] and not dim3:
        ejes = [Ec("x=0"), Ec("y=0")]
        pol += ejes
    if dim3:
        plan3 = _solido(T, n, pol, simples, f, delta, qty, fl, notas)
        if plan3.get("tipo") == "triple_region" and plan3.get("f") == "1" and plan3.get("z_inf") == "0" and len(plan3["curvas"]) >= 3 \
                and not any(k in T for k in ("dv", "triple")):
            # volumen bajo z = G(x,y): integral doble de G sobre la región plana (admite sustituciones automáticas)
            try:
                notas2 = []
                alt = _plana(T, n, [Ec(c) for c in plan3["curvas"]], [], plan3["z_sup"], None, "integral", fl, notas2, puntos, ())
                alts = [alt] + list(alt.pop("alternativas", []))
                if any(k in T for k in ("transformacion", "sustitucion", "cambio de variable")):
                    plan3 = dict(alts[0], alternativas=alts[1:] + [dict(plan3)])
                    notas.extend(notas2)
                else:
                    plan3["alternativas"] = alts
            except Exception:
                pass
        return plan3
    return _plana(T, n, pol, simples, f, delta, qty, fl, notas, puntos, ejes)


def _caja_lineal(T, n, cadenas, cab, qty, notas):
    """1 ≤ y+z ≤ 3, −1 ≤ z−y ≤ 1, 0 ≤ x−y ≤ 3  → u=y+z, v=z−y, w=x−y con límites constantes"""
    f = _integrando_texto(n) or (cab["f"].rhs if "f" in cab else "1")
    if qty in ("volumen", "area"): f = "1"
    dim = 3 if len(cadenas) >= 3 else 2
    nombres = ["u", "v", "w"][:len(cadenas)]
    mapa = {}; niv = []
    for nm, e in zip(nombres, cadenas):
        a, b = e.mxp[0], e.mxp[2]
        if e.ops[0] in (">=", ">"): a, b = b, a
        mapa[nm] = e.mxp[1]
        niv.append([nm, a, b])
    viejas = ["x", "y", "z"][:dim]
    notas.append("Región limitada por formas lineales: se toman " + ", ".join(f"{k} = {v}" for k, v in mapa.items()) + " y se integra en la caja del espacio nuevo")
    if dim == 3:
        return {"tipo": "cambio_variables_3d", "f": f, "viejas": viejas, "nuevas": nombres, "mapa": mapa, "modo": "inverso", "niveles": list(reversed(niv))}
    curvas = []
    for nm, a, b in niv:
        curvas += [f"{mapa[nm]}={a}", f"{mapa[nm]}={b}"]
    return {"tipo": "cambio_variables", "f": f, "curvas": curvas, "nuevas": nombres, "mapa": mapa, "modo": "inverso", "orden": "dydx"}


def _niveles_de_cadenas(cadenas, simples):
    """a <= v <= b ... → niveles interior→exterior ordenando por dependencia"""
    lims = {}
    for e in cadenas:
        v = e.mxp[1]
        if not re.fullmatch(r"[A-Za-z]\w*", v): raise NoReconocido(f"La desigualdad «{e.crudo}» debe tener una sola variable en el centro")
        a, b = e.mxp[0], e.mxp[2]
        if e.ops[0] in (">=", ">"): a, b = b, a
        lims[v] = (a, b)
    vars_ = list(lims)
    deps = {v: {s for s in _syms(lims[v][0]) | _syms(lims[v][1]) if s in lims} for v in vars_}
    orden = []     # exterior→interior
    rest = set(vars_)
    while rest:
        libres = [v for v in vars_ if v in rest and not (deps[v] & rest)]
        if not libres: raise NoReconocido("Los límites dependen unos de otros circularmente")
        v = libres[0]; orden.append(v); rest.discard(v)
    return [[v, lims[v][0], lims[v][1]] for v in reversed(orden)]

def _simples_a_curvas(simples):
    out = []
    for e in simples:
        if len(e.ops) == 1: out.append(Ec(f"{e.partes[0]} = {e.partes[1]}"))
    return out


def _mapa_de_ecuaciones(curvas):
    """ecuaciones con variables nuevas (u, v, …) → mapa nueva = f(x,y) ; devuelve (mapa, resto)"""
    from .cas3 import from_ast, Expr, GP
    mapa = {}; resto = []
    for e in curvas:
        extra = [s for s in e.simbolos() if s not in COORD]
        if not extra:
            resto.append(e); continue
        if len(extra) != 1: raise NoReconocido(f"La ecuación «{e.crudo}» mezcla varias variables nuevas")
        v = extra[0]
        g = from_ast(("bin", "-", _ast(e.mxp[0]), _ast(e.mxp[-1]))).gp()
        cs = g.coef_in(v)
        if set(cs) != {F(0), F(1)} or not cs[F(1)].is_mono():
            raise NoReconocido(f"No pude despejar {v} en «{e.crudo}»")
        val = -(cs[F(0)] * cs[F(1)].inv())
        mapa[v] = Expr.of(val).to_str()
    return mapa, resto


_BIBLIOTECA_UV = ["x*y", "x^2+y^2", "y^2-x^2", "x^2-y^2", "y/x", "x/y", "x+y", "x-y", "y/x^2", "x^2/y", "y^2/x", "x/y^2", "x*y^3", "x^3*y",
                  "x^2*y", "x*y^2", "y/x^3", "x^2/y^2", "x^2+4*y^2", "x*y^2"]


def _puntos_sobre(e):
    """puntos (x,y) sobre la curva de la ecuación"""
    g = _g(e, ("x", "y"))
    pts = []
    for x0 in (0.35, 0.8, 1.3, 1.9, 2.6, 3.4, -0.6, -1.4):
        ys = [k * 0.05 for k in range(-160, 161)]
        vals = []
        for y0 in ys:
            try: vals.append(g(x0, y0))
            except Exception: vals.append(None)
        for a, b, ya, yb in zip(vals, vals[1:], ys, ys[1:]):
            if a is None or b is None or isinstance(a, complex) or isinstance(b, complex): continue
            if a == 0: pts.append((x0, ya))
            elif a * b < 0:
                lo, hi = ya, yb
                for _ in range(60):
                    mid = (lo + hi) / 2
                    if g(x0, lo) * g(x0, mid) <= 0: hi = mid
                    else: lo = mid
                pts.append((x0, (lo + hi) / 2))
        if len(pts) >= 4: break
    # curvas verticales x = c
    if len(pts) < 2:
        for y0 in (0.4, 1.1, 2.0, 3.0):
            xs = [k * 0.05 for k in range(-160, 161)]
            for xa, xb in zip(xs, xs[1:]):
                try: a, b = g(xa, y0), g(xb, y0)
                except Exception: continue
                if a * b < 0:
                    lo, hi = xa, xb
                    for _ in range(60):
                        mid = (lo + hi) / 2
                        if g(lo, y0) * g(mid, y0) <= 0: hi = mid
                        else: lo = mid
                    pts.append(((lo + hi) / 2, y0))
    return pts


def _familias(curvas, extra=()):
    """busca u=F1(x,y), v=F2(x,y) tales que cada curva es un nivel de F1 o de F2 → [(F1, F2, cubiertas)] ordenados"""
    lib = list(extra) + _BIBLIOTECA_UV
    cubre = {}
    pts = {id(e): _puntos_sobre(e) for e in curvas}
    for Ftxt in lib:
        try: Fn = compile_ast(_ast(Ftxt), ["x", "y"])
        except Exception: continue
        cs = []
        for e in curvas:
            p = pts[id(e)]
            if len(p) < 2: continue
            try: vals = [Fn(a, b) for a, b in p]
            except Exception: continue
            if any(isinstance(v, complex) for v in vals): continue
            if max(vals) - min(vals) <= 1e-7 * (1 + abs(vals[0])): cs.append((e, vals[0]))
        if cs: cubre[Ftxt] = cs
    res = []
    keys = list(cubre)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            ca = {id(e) for e, _ in cubre[a]}; cb = {id(e) for e, _ in cubre[b]}
            if len(ca | cb) == len(curvas) and len(ca) >= 1 and len(cb) >= 1:
                res.append((a, b, len(ca | cb)))
    return res


def _plana(T, n, curvas, simples, f, delta, qty, fl, notas, puntos, ejes=()):
    curvas = list(curvas) + _simples_a_curvas(simples)
    ejes_ids = {id(e) for e in ejes}
    mapa, curvas = _mapa_de_ecuaciones(curvas)
    orden = "dxdy" if re.search(r"\bdx\s*dy\b", T) or "dxdy" in T else "dydx"
    punto = [str(round(p, 6)) for p in puntos] if puntos else None
    if qty in ("masa", "centroide"):
        if delta is None: delta = _dens_frase(T, 2) or "1"
    base = {"curvas": [e.como_curva() for e in curvas], "orden": orden}
    if punto: base["punto"] = punto
    if mapa:
        nuevas = list(mapa)
        notas.append("Cambio de variables dado: " + "; ".join(f"{k} = {v}" for k, v in mapa.items()))
        base_m = dict(base, curvas=[e.como_curva() for e in curvas if id(e) not in ejes_ids])
        return {"tipo": "cambio_variables", "f": f if qty in ("integral",) else "1", "nuevas": nuevas, "mapa": mapa, "modo": "inverso", **base_m}
    # ---- polares
    cls = [clase_curva(e) for e in curvas]
    hay_circ = any(c[0] == "circulo" for c in cls)
    polar_ok = hay_circ and all(c[0] in ("circulo", "recta") for c in cls) and all(
        (c[0] == "recta" and abs(c[3]) < 1e-9) or (c[0] == "circulo") for c in cls) and \
        all(c[0] != "circulo" or abs(c[1]) < 1e-9 and abs(c[2]) < 1e-9 or abs(c[1] ** 2 + c[2] ** 2 - c[3]) < 1e-9 for c in cls)
    if (fl["pol"] or polar_ok) and qty in ("area", "integral") and polar_ok:
        niv = _niveles_polares(cls, T, fl)
        if niv is not None:
            notas.append("Región circular: se usan coordenadas polares")
            return {"tipo": "coordenadas", "sistema": "polares", "f": "1" if qty == "area" else f, "niveles": niv}
    # ---- rectangulares (+ sustituciones automáticas como alternativas)
    quiere_cv = any(k in T for k in ("transformacion", "sustitucion", "cambio de variable", "cambio de coordenadas", "jacobiano"))
    sin_ejes = [e for e in curvas if id(e) not in ejes_ids]
    base_cv = dict(base, curvas=[e.como_curva() for e in sin_ejes])
    cands = _candidatos_cv(sin_ejes, f, base_cv, qty, delta, T) if (quiere_cv or qty in ("integral", "masa", "centroide", "area")) and len(sin_ejes) >= 3 else []
    if fl["cuadrante"] and not puntos:
        for c in cands: c.setdefault("punto", ["1", "1"]) if False else None
    if qty == "area": plan = {"tipo": "region", "que": "area", **base}
    elif qty == "integral": plan = {"tipo": "region", "que": "integral", "f": f, **base}
    elif qty in ("masa", "centroide"): plan = {"tipo": "region", "que": "masa", "delta": delta if qty == "masa" else "1", **base}
    else: plan = None
    if plan is not None:
        if (quiere_cv or ejes) and cands:
            p0 = cands[0]; p0["alternativas"] = cands[1:] + [plan]
            notas.append("Sustitución elegida a partir de las curvas/integrando: " + ", ".join(f"{k} = {v}" for k, v in p0["mapa"].items()))
            return p0
        plan["alternativas"] = cands
        return plan
    raise NoReconocido("Para un volumen bajo una superficie escriba la ecuación z = f(x, y) y la región plana")


_ESPECIALES = {   # familias cuyo despeje no es lineal ni monomial: x, y en función de (u, v) (primer cuadrante)
    ("x^2+y^2", "y^2-x^2"): {"x": "sqrt((u-v)/2)", "y": "sqrt((u+v)/2)"},
    ("x^2+y^2", "x^2-y^2"): {"x": "sqrt((u+v)/2)", "y": "sqrt((u-v)/2)"},
}


def _lineales_del_integrando(f):
    """subexpresiones lineales no triviales en x,y de las funciones del integrando (p. ej. x-y y x+y en cos((x-y)/(x+y)))"""
    try: a = _ast(f)
    except Exception: return []
    out = []
    def lineal(nd):
        try:
            g = compile_ast(nd, ["x", "y"])
            c = _ajustar(g, [lambda x, y: x, lambda x, y: y, lambda x, y: 1.0], 2)
        except Exception: return False
        return c is not None and (abs(c[0]) > 1e-9 or abs(c[1]) > 1e-9) and not (abs(c[0]) > 1e-9 and abs(c[1]) < 1e-9 and abs(c[2]) < 1e-9) and not (abs(c[1]) > 1e-9 and abs(c[0]) < 1e-9 and abs(c[2]) < 1e-9)
    def rec(nd):
        if nd[0] == "bin":
            if nd[1] in "+-*/^":
                if lineal(nd): out.append(ast_str(nd)); return
            rec(nd[2]); rec(nd[3])
        elif nd[0] == "call":
            for x in nd[2]: rec(x)
        elif nd[0] == "neg": rec(nd[1])
    rec(a)
    uniq = []
    for t in out:
        if t not in uniq: uniq.append(t)
    return uniq


def _candidatos_cv(curvas, f, base, qty, delta, T):
    """posibles sustituciones u=F1(x,y), v=F2(x,y) a partir de las familias de curvas y del integrando"""
    cands = []
    extra = _lineales_del_integrando(f) if f not in ("1", None) else []
    pares = []
    try:
        for a, b, cubre in _familias(curvas, extra):
            pares.append((a, b))
    except Exception:
        pass
    if len(extra) >= 2:
        pares.append((extra[1], extra[0]) if False else (extra[0], extra[1]))
    vistos = set()
    for a, b in pares:
        if (a, b) in vistos: continue
        vistos.add((a, b))
        esp = _ESPECIALES.get((a, b)) or _ESPECIALES.get((b, a))
        if esp:
            mapa = dict(esp); modo = "directo"
            if (b, a) in _ESPECIALES: a, b = b, a
        else:
            mapa = {"u": a, "v": b}; modo = "inverso"
        if esp:
            mapa = {"x": esp["x"], "y": esp["y"]}
        d = {"curvas": base["curvas"], "nuevas": ["u", "v"], "mapa": mapa, "modo": modo, "orden": base.get("orden", "dydx")}
        if "punto" in base: d["punto"] = base["punto"]
        if qty in ("masa", "centroide"):
            d.update({"tipo": "cambio_variables_masa", "delta": delta if qty == "masa" else "1"})
        else:
            d.update({"tipo": "cambio_variables", "f": f if qty == "integral" else "1"})
        if modo == "directo": d["mapa"] = {"x": mapa["x"], "y": mapa["y"]}
        cands.append(d)
    return cands


def _niveles_polares(cls, T, fl):
    """límites r(θ), θ para una región descrita por círculos/rectas (todos por el origen o centrados en él)"""
    cen0 = sorted(c[3] for c in cls if c[0] == "circulo" and abs(c[1]) < 1e-9 and abs(c[2]) < 1e-9)
    thr = [c for c in cls if c[0] == "circulo" and (abs(c[1]) > 1e-9 or abs(c[2]) > 1e-9)]
    rectas = [c for c in cls if c[0] == "recta"]
    th0, th1 = "0", "2*pi"
    if fl["cuadrante"]: th0, th1 = "0", "pi/2"
    if len(rectas) >= 2 and not fl["cuadrante"]:
        angs = sorted({round((math.atan2(-c[1], c[2]) % math.pi), 9) for c in rectas})
        if len(angs) >= 2: th0, th1 = _angulo_exacto(angs[0]), _angulo_exacto(angs[1])
    elif len(rectas) == 1 and not fl["cuadrante"]:
        c = rectas[0]; a = math.atan2(-c[1], c[2]) % math.pi
        th0, th1 = (_angulo_exacto(a), "pi") if a < math.pi / 2 else ("0", _angulo_exacto(a))
    if thr and not cen0:
        c = thr[0]; cx, cy = c[1], c[2]
        rr = f"{_fmt(2 * cx)}*cos(theta)+{_fmt(2 * cy)}*sin(theta)"
        if abs(cx) < 1e-9: th0, th1 = ("0", "pi") if cy > 0 else ("pi", "2*pi")
        elif abs(cy) < 1e-9: th0, th1 = ("-pi/2", "pi/2") if cx > 0 else ("pi/2", "3*pi/2")
        else: return None
        return [["r", "0", rr], ["theta", th0, th1]]
    if len(cen0) == 1: return [["r", "0", _txt_raiz(cen0[0])], ["theta", th0, th1]]
    if len(cen0) >= 2:
        return [["r", _txt_raiz(cen0[0]), _txt_raiz(cen0[-1])], ["theta", th0, th1]]
    return None


def _fmt(x):
    q = _q(x)
    return str(q) if q is not None else repr(x)

def _despejar(e, w):
    """superficie → lista de (expresión en las otras variables, grado) tales que w = expresión. Grado 1 (única) o 2 (±)."""
    from .cas3 import from_ast, Expr
    if e.lhs == w and w not in _syms(e.rhs): return [(e.rhs, 1)]
    if e.rhs == w and w not in _syms(e.lhs): return [(e.lhs, 1)]
    g = from_ast(("bin", "-", _ast(e.mxp[0]), _ast(e.mxp[-1]))).gp()
    cs = g.coef_in(w)
    ex = sorted(cs)
    if ex == [F(0), F(1)] or ex == [F(1)]:
        c1 = cs[F(1)]
        if not c1.is_mono(): raise NoReconocido(f"No pude despejar {w} en «{e.crudo}»")
        c0 = cs.get(F(0))
        val = -(c0 * c1.inv()) if c0 is not None else None
        return [(Expr.of(val).to_str() if val is not None else "0", 1)]
    if ex == [F(0), F(2)]:
        c2, c0 = cs[F(2)], cs[F(0)]
        if not c2.is_mono(): raise NoReconocido(f"No pude despejar {w} en «{e.crudo}»")
        rad = -(c0 * c2.inv())
        return [(f"sqrt({Expr.of(rad).to_str()})", 2)]
    raise NoReconocido(f"No pude despejar {w} en «{e.crudo}»")


def _qparams(T, qty, f, delta, dim=3):
    eje = None
    if qty == "inercia":
        m = re.search(r"eje\s+([xyz])", T)
        eje = m.group(1) if m else "z"
    if delta is None: delta = _dens_frase(T, dim) or "1"
    if qty == "volumen": return {"que": "integral", "f": "1"}
    if qty == "integral": return {"que": "integral", "f": f}
    if qty == "centroide": return {"que": "masa3d", "delta": "1"}
    if qty == "masa": return {"que": "masa3d", "delta": delta}
    if qty == "inercia": return {"que": "inercia", "delta": delta, "eje": eje}
    return {"que": "integral", "f": f}


def _solido(T, n, curvas, simples, f, delta, qty, fl, notas):
    curvas = list(curvas) + _simples_a_curvas(simples)
    surf = [e for e in curvas if "z" in e.simbolos() or e.simbolos() & {"rho", "phi"}]
    xy = [e for e in curvas if e not in surf]
    q = _qparams(T, qty, f, delta)
    clases = []
    for e in surf:
        if e.simbolos() & {"rho", "phi"}: clases.append(("directa", e))
        else:
            e2 = _quitar_raiz(e)
            clases.append(clase_superficie(e2) + (e2,) if True else ())
    esf_ok = bool(surf) and all(c[0] in ("esfera", "cono", "directa") or (c[0] == "plano_z" and abs(c[1]) < 1e-9) for c in clases) and \
        any(c[0] in ("esfera", "cono", "directa") for c in clases) and not xy
    forzar = "cil" if fl["cil"] else "esf" if fl["esf"] else None
    # ¿simetría circular? (cilindro, paraboloide de revolución…)
    circ = any(clase_curva(e)[0] == "circulo" for e in xy)
    if not circ:
        for e in surf:
            if e.simbolos() & {"rho", "phi"}: continue
            try:
                g = _g(_quitar_raiz(e), ("x", "y", "z"))
                c = _ajustar(g, _B3, 3)
                if c is not None and abs(c[0] - c[1]) < 1e-9 and abs(c[0]) > 1e-9 and max(abs(c[3]), abs(c[4]), abs(c[5]), abs(c[6]), abs(c[7])) < 1e-9: circ = True
            except Exception: pass
    if forzar == "esf" or (forzar is None and esf_ok):
        niv = _niveles_esfericos(clases, T, fl, xy)
        notas.append("Sólido con esferas/conos: coordenadas esféricas " + "; ".join(f"{v}: {a}→{b}" for v, a, b in niv))
        return {"tipo": "coordenadas", "sistema": "esfericas", "niveles": niv, "f": q.get("f", "1"), **{k: v for k, v in q.items() if k != "f"}}
    if forzar == "cil" or (forzar is None and circ):
        try:
            niv = _niveles_cilindricos(surf, xy, T, fl, notas)
            notas.append("Sólido de revolución: coordenadas cilíndricas " + "; ".join(f"{v}: {a}→{b}" for v, a, b in niv))
            return {"tipo": "coordenadas", "sistema": "cilindricas", "niveles": niv, "f": q.get("f", "1"), **{k: v for k, v in q.items() if k != "f"}}
        except NoReconocido:
            if forzar == "cil": raise
    try:
        return _solido_elipse(T, surf, xy, q, fl, notas)
    except NoReconocido:
        pass
    return _solido_rect(T, n, surf, xy, q, fl, notas)


def _solido_elipse(T, surf, xy, q, fl, notas):
    """sólido entre z = G1 y z = G2 sobre una elipse a x²+b y² = c con semiejes racionales: x = A r cosθ, y = B r sinθ"""
    if q.get("que") == "masa3d" and q.get("delta") is None: raise NoReconocido("")
    zs = []
    for e in surf:
        for g, gr in _despejar(e, "z"):
            if gr != 1: raise NoReconocido("")
            zs.append(g)
    if not zs or len(zs) > 2: raise NoReconocido("")
    zn = [g for g in zs if g.strip() != "0"]
    if len(zs) == 1: zs = [zs[0], "0"]
    # curva base: la elipse
    if xy:
        base = xy[0]
    else:
        base = Ec(f"{zs[0]} = {zs[1]}")
    g = _g(base, ("x", "y"))
    c = _ajustar(g, _B2, 2)
    if c is None: raise NoReconocido("")
    a, b, cxy, d, e_, f0 = c
    if abs(cxy) > 1e-9 or abs(d) > 1e-9 or abs(e_) > 1e-9 or abs(a - b) < 1e-9 or a * b <= 0 or -f0 / a <= 0: raise NoReconocido("")
    A2, B2_ = _q(-f0 / a), _q(-f0 / b)
    if A2 is None or B2_ is None: raise NoReconocido("")
    def raiz(q_):
        n_, d_ = q_.numerator, q_.denominator
        rn, rd = math.isqrt(n_), math.isqrt(d_)
        return F(rn, rd) if rn * rn == n_ and rd * rd == d_ else None
    A, B = raiz(A2), raiz(B2_)
    if A is None or B is None: raise NoReconocido("")
    mx_ = f"({A})*r*cos(theta)"; my_ = f"({B})*r*sin(theta)"
    def en_r(txt):
        fn = compile_ast(_ast(txt), ["x", "y"])
        base_r = [lambda r, t: 1.0, lambda r, t: r * r, lambda r, t: r ** 4]
        h = lambda r, t: fn(float(A) * r * math.cos(t), float(B) * r * math.sin(t))
        cc = _ajustar(h, base_r, 2)
        if cc is None: raise NoReconocido("")
        qq = [_q(v) for v in cc]
        if any(v is None for v in qq): raise NoReconocido("")
        return "+".join(f"({v})*r^{2 * k}" for k, v in enumerate(qq) if v != 0) or "0"
    g1, g2 = en_r(zs[0]), en_r(zs[1])
    t0 = 0.5; ev = lambda t: compile_ast(_ast(t), ["r", "theta"])(0.5, 0.7)
    lo, hi = (g1, g2) if ev(g1) <= ev(g2) else (g2, g1)
    que = q.get("que")
    if que == "inercia":
        eje = q.get("eje", "z"); suma = {"x": "y^2+z^2", "y": "x^2+z^2", "z": "x^2+y^2"}[eje]
        f = f"({q.get('delta') or '1'})*({suma})"
    elif que == "masa3d": f = q.get("delta") or "1"
    else: f = q.get("f", "1")
    notas.append(f"Región elíptica: se usa la transformación x = {mx_}, y = {my_} (jacobiano {A * B}·r)")
    return {"tipo": "cambio_variables_3d", "f": f, "viejas": ["x", "y", "z"], "nuevas": ["r", "theta", "z"],
            "mapa": {"x": mx_, "y": my_, "z": "z"}, "modo": "directo",
            "niveles": [["z", lo, hi], ["r", "0", "1"], ["theta", "0", "2*pi"]]}


def _quitar_raiz(e):
    """z = sqrt(G) → z² = G (la rama se decide por el contexto)"""
    a, b = e.mxp[0], e.mxp[-1]
    for lado, otro, izq in ((b, a, True), (a, b, False)):
        m = re.fullmatch(r"sqrt\((.*)\)", lado.strip())
        if m:
            # comprobar que los paréntesis balancean (sqrt(a)+sqrt(b) no es una sola raíz)
            d = 0; ok = True
            for ch in lado.strip()[5:-1]:
                if ch == "(": d += 1
                elif ch == ")":
                    d -= 1
                    if d < 0: ok = False; break
            if ok and d == 0:
                return Ec(f"({otro})^2 = {m.group(1)}")
    return e


def _niveles_esfericos(clases, T, fl, xy):
    rhos = sorted(c[1] for c in clases if c[0] == "esfera")
    conos = [c for c in clases if c[0] == "cono"]
    dirs = [c[1] for c in clases if c[0] == "directa"]
    plano = any(c[0] == "plano_z" for c in clases) or fl["octante"]
    # ρ
    if dirs:
        e = dirs[0]
        l, r = e.mxp[0], e.mxp[-1]
        rho_hi = r if l.strip() == "rho" else l
        rho = ["rho", "0", rho_hi]
    elif len(rhos) == 1: rho = ["rho", "0", _txt_raiz(rhos[0])]
    elif len(rhos) >= 2: rho = ["rho", _txt_raiz(rhos[0]), _txt_raiz(rhos[-1])]
    else: raise NoReconocido("No encontré la esfera que limita el sólido")
    # φ
    phi_max = "pi/2" if plano else "pi"
    phi = ["phi", "0", phi_max]
    if conos:
        tg2 = conos[0][1]
        fc = _angulo_exacto(math.atan(math.sqrt(tg2)))
        abajo = any(k in T for k in ("debajo del cono", "bajo el cono", "fuera del cono", "por debajo del cono", "exterior al cono"))
        phi = ["phi", fc, phi_max] if abajo else ["phi", "0", fc]
    th = ["theta", "0", "pi/2" if fl["cuadrante"] else "2*pi"]
    return [rho, phi, th]


def _niveles_cilindricos(surf, xy, T, fl, notas):
    from .cas3 import from_ast, pitag
    from . import coords as CO
    # --- región en el plano xy (r, θ)
    xy2 = list(xy)
    zs = []          # (texto en x,y, grado)
    for e in surf:
        for g, gr in _despejar(_quitar_raiz(e) if False else e, "z"):
            zs.append((g, gr, e))
    # curva de proyección implícita (intersección de superficies o del cilindro implícito)
    if not xy2 and len(zs) >= 2:
        a, b = zs[0][0], zs[1][0]
        xy2.append(Ec(f"{a} = {b}"))
    if fl["cuadrante"]: xy2 += [Ec("x=0"), Ec("y=0")]
    cls = [clase_curva(e) for e in xy2]
    niv_r = _niveles_polares(cls, T, fl)
    if niv_r is None: raise NoReconocido("No pude describir la región del plano xy en polares (se esperan círculos y rectas por el origen)")
    (_, r0, r1), (_, t0, t1) = niv_r
    # --- z entre dos superficies
    def polar(txt):
        c = _radial(txt)
        if c is not None:
            t = "+".join(f"({v})*r^{2 * k}" for k, v in enumerate(c) if v != 0)
            return t or "0"
        an = CO.a_nuevas(txt, "cilindricas")
        return pitag(from_ast(an)).to_str()
    def polar_raiz(g):
        rad = g[5:-1]
        c = _radial(rad)
        if c is not None and len(c) >= 2 and all(v == 0 for v in c[2:]):
            a, b = c[0], c[1]
            if a == 0 and b > 0: return f"({_txt_raiz(float(b))})*r"
            return f"sqrt(({a})+({b})*r^2)"
        return polar(g)
    cand = []
    for g, gr, e in zs:
        if gr == 2:
            pr = polar_raiz(g)
            cand.append((pr, "+", e)); cand.append(("-(" + pr + ")", "-", e))
        else:
            cand.append((polar(g), "", e))
    # muestra
    try:
        rm = _eval_limite(r0, 0.5, 0.8) , _eval_limite(r1, 0.5, 0.8)
    except Exception:
        rm = (0.0, 1.0)
    rs = (rm[0] + rm[1]) / 2 if rm[1] > rm[0] else 0.5
    tm = (_const(t0) + _const(t1)) / 2
    plano0 = any(abs(_val_en(c[0], rs, tm)) < 1e-9 and c[1] == "" for c in cand)
    if len(cand) == 2 and cand[0][1] and cand[1][1]:
        cand = cand[:1] if plano0 else cand
    util = []
    for c in cand:
        if c[1] == "-" and (plano0 or "hoja superior" in T or "por encima" in T): continue
        util.append(c)
    if len(util) == 1:
        util.append(("0", "", None))
    if len(util) != 2:
        if len(util) > 2:
            # varias superficies: quitar la que coincide con z=0 y quedarse con las dos de mayor interés
            raise NoReconocido("Hay más de dos superficies en z; el sólido necesita dividirse en piezas")
        raise NoReconocido("Necesito dos superficies en z (inferior y superior)")
    a, b = util
    va, vb = _val_en(a[0], rs, tm), _val_en(b[0], rs, tm)
    lo, hi = (a[0], b[0]) if va <= vb else (b[0], a[0])
    return [["z", lo, hi], ["r", r0, r1], ["theta", t0, t1]]


def _radial(txt):
    """txt(x, y) = Σ c_k (x²+y²)^k  → [c_0, c_1, ...] racionales; None si no es radial"""
    try:
        g = compile_ast(_ast(txt), ["x", "y"])
    except Exception:
        return None
    base = [lambda x, y: 1.0, lambda x, y: x * x + y * y, lambda x, y: (x * x + y * y) ** 2, lambda x, y: (x * x + y * y) ** 3]
    c = _ajustar(g, base, 2)
    if c is None: return None
    q = [_q(v) for v in c]
    if any(v is None for v in q): return None
    return q


def _const(txt):
    return compile_ast(_ast(txt), [])()


def _eval_limite(txt, r, t):
    return compile_ast(_ast(txt), ["r", "theta"])(r, t)


def _val_en(txt, r, t):
    return compile_ast(_ast(txt), ["r", "theta"])(r, t)


def _solido_rect(T, n, surf, xy, q, fl, notas):
    """sólido entre dos superficies z = G(x,y) sobre una región D del plano xy (en rectangulares)"""
    if fl["octante"]: xy = list(xy) + [Ec("x=0"), Ec("y=0")]
    elif fl["cuadrante"]: xy = list(xy) + [Ec("x=0"), Ec("y=0")]
    # variable de altura: z si todas las ecuaciones en z se despejan; si no y, x
    alt = "z"
    for w in ("z", "y", "x"):
        con = [e for e in surf if w in e.simbolos()]
        if w != "z":
            con = [e for e in (surf + xy) if w in e.simbolos()]
        try:
            for e in con: _despejar(e, w)
            if con:
                alt = w; break
        except NoReconocido:
            continue
    todas = surf + xy if alt != "z" else surf
    if alt != "z":
        # renombrar: alt ↔ z para reutilizar el motor
        def ren(s): 
            return re.sub(r"\b(z|%s)\b" % alt, lambda m: alt if m.group(1) == "z" else "z", s)
        surf2 = [Ec(ren(e.como_curva())) for e in surf + xy if alt in e.simbolos()]
        xy2 = [Ec(ren(e.como_curva())) for e in surf + xy if alt not in e.simbolos()]
        notas.append(f"La variable de altura es {alt}; se intercambia con z para planteo (los resultados por coordenadas aparecen intercambiados)")
        surf, xy = surf2, xy2
        for k in ("f", "delta"):
            if k in q: q[k] = ren(q[k])
    zs = []
    for e in surf:
        for g, gr in _despejar(e, "z"): zs.append(g if gr == 1 else None)
    zs = [g for g in zs if g is not None]
    fl_oct = fl["octante"] or "primer octante" in T
    zn = [g for g in zs if g.strip() not in ("0",)]
    if fl_oct or any(g.strip() == "0" for g in zs) or "sobre el plano xy" in T:
        zi, zsup = "0", None
        if len(zn) == 1: zsup = zn[0]
        elif len(zn) > 1: raise NoReconocido("Hay varias superficies superiores; el sólido necesita dividirse en piezas (use 'Sólido en dos piezas')")
        if zsup is None: raise NoReconocido("Falta la superficie superior del sólido")
    else:
        if len(zn) == 1: zi, zsup = "0", zn[0]       # una sola superficie: la base es el plano xy
        elif len(zn) == 2: zi, zsup = zn
        else: raise NoReconocido("Necesito dos superficies z = f(x, y) (inferior y superior)")
    plan = {"tipo": "triple_region", "z_inf": zi, "z_sup": zsup, "curvas": [e.como_curva() for e in xy], "orden": "dydx"}
    plan.update(q)
    plan["f"] = q.get("f", "1")
    notas.append(f"Sólido entre z = {zi} y z = {zsup} sobre la región del plano xy limitada por {', '.join(e.crudo for e in xy) or 'la proyección de la intersección'}")
    return plan
# ------------------------------------------------------------------------------------------------ entrada
def clasificar(texto):
    """→ (plan(dict de api3), notas de interpretación)"""
    n = normalizar(texto)
    T = quitar_acentos(n).lower()
    ecs = leer_ecuaciones(texto)
    hay_integral = any(c in n for c in "∫") or "DOBLEINT" in n or "TRIPLEINT" in n or "integral" in T or "evalue" in T and ("dv" in T or "da" in T)
    if "jacobian" in T and len([1 for e, _ in ecs if e.es_igualdad]) >= 2 and not hay_integral:
        return _jacobiano(T, ecs)
    if any(k in T for k in ("diferencial de area", "diferencial de volumen")) and not hay_integral:
        return _jacobiano(T, ecs)
    if any(k in T for k in ("minimos cuadrados", "regresion lineal", "recta de ajuste", "ajuste de una recta")) or ("recta" in T and "ajuste" in T):
        return _ajuste(T, texto)
    if any(k in T for k in ("gradiente", "divergencia", "rotacional", "laplaciano", "conservativo", "funcion potencial", "trabajo",
                            "integral de linea", "circulacion", "flujo", "area de la superficie", "area superficial", "area de superficie")) \
            and not ("∫" in n and re.search(r"∫\s*_", n)):
        notas = []
        pl, nt = _vectorial(T, n, texto, ecs, notas)
        return pl, notas + nt
    opt = any(k in T for k in ("extremo", "maximo", "minimo", "maximiz", "minimiz", "optimiz", "punto critico", "puntos criticos", "lagrange",
                               "mas cercano", "mas lejano", "mas proximo", "distancia minima", "distancia maxima", "mas grande", "punto de silla", "sujetoa"))
    if opt and not hay_integral and not any(k in T for k in ("area de", "centro de masa", "momento de inercia")):
        return _optimizacion(T, texto, ecs)
    if hay_integral or _quantity(T, n) != "integral":
        notas = []
        try:
            pd = _plan_desigualdades(texto, ecs, T, n, notas) if not re.search(r"∫\s*_", n) else None
        except Exception:
            pd = None
        if pd is not None:
            try:
                n2 = []; viejo = _integral(T, n, ecs, n2)
                pd.setdefault("alternativas", []).append(viejo)
            except Exception:
                pass
            try:
                n3 = []; pp = _politopo_plan(texto, n3)
                if pp is not None: pd["alternativas"].append(pp) if "alternativas" in pd else pd.__setitem__("alternativas", [pp])
            except Exception:
                pass
            return pd, notas
        notas = []
        try:
            plan = _integral(T, n, ecs, notas)
        except NoReconocido:
            notas = []
            pl = _politopo_plan(texto, notas)
            if pl is None: raise
            return pl, notas
        try:
            n2 = []
            pl = _politopo_plan(texto, n2)
        except Exception:
            pl = None
        if pl is not None:
            plan.setdefault("alternativas", []).append(pl)
        return plan, notas
    raise NoReconocido("No reconocí el tipo de ejercicio. Escríbalo como en la guía: la función, la región (curvas o desigualdades) y qué se pide")



def _contexto_contraste(texto):
    """argumentos para contraste.esperado (o None si no aplica)"""
    try:
        n = normalizar(texto); T = quitar_acentos(n).lower()
        if re.search(r"∫\s*_", n): return None
        ecs = leer_ecuaciones(texto); fl = _flags(T)
        qty = _quantity(T, n)
        cab, *_ = _region_geom(ecs, n, T)
        dim = 3 if any("z" in e.simbolos() for e, _ in ecs if e.cabecera is None) else 2
        f = _integrando_texto(n) or (cab["f"].rhs if "f" in cab else None)
        delta = cab["delta"].rhs if "delta" in cab else _dens_frase(T, dim)
        m = re.search(r"\beje\s+([xyz])\b", T)
        gs = None
        try:
            pl = _politopo_plan(texto, [])
        except Exception:
            pl = None
        if pl is not None:
            vs = pl["variables"]
            cons = PO.restricciones_desde_textos(pl["restricciones"], vs)
            gs = [(lambda *p, c=c: float(sum(c[0][v] * p[i] for i, v in enumerate(vs)) + c[1])) for c in cons]
            dim = len(vs); f = f or pl.get("f")
            delta = pl.get("delta") if qty in ("masa", "centroide", "inercia") else delta
        return (ecs, fl, dim, qty, f, delta, m.group(1) if m else None, gs)
    except Exception:
        return None


def _acotado(cons, vs):
    """la región {cons ≥ 0} es acotada: cada variable tiene cota inferior y superior tras eliminar las demás"""
    try:
        for v in vs:
            c = [x for x in PO._normaliza(cons)]
            for w in vs:
                if w != v: c = PO._normaliza(PO._fm(c, w))
            if not any(k[0][v] > 0 for k in c) or not any(k[0][v] < 0 for k in c): return False
        return True
    except Exception:
        return False


def _politopo_plan(texto, notas):
    """región lineal (desigualdades, planos, vértices, valor absoluto) → plan «politopo»; None si no es lineal"""
    n = normalizar(texto); T = quitar_acentos(n).lower()
    if re.search(r"∫\s*_", n): return None
    ecs = leer_ecuaciones(texto); fl = _flags(T)
    qty = _quantity(T, n)
    if qty == "integral" and not ("DOBLEINT" in n or "TRIPLEINT" in n or "integral" in T): return None
    cab, cadenas, curvas, simples, vert = _region_geom(ecs, n, T)
    dim = 3 if any("z" in e.simbolos() for e, _ in ecs if e.cabecera is None) or "solido" in T or "tetraedro" in T or "piramide" in T or TRIPLE(T, n) else 2
    vs = ["x", "y", "z"][:dim]
    desig = []
    for e in cadenas + simples:
        if e.simbolos() - set(vs): return None
        desig.append("".join(p + o for p, o in zip(e.mxp, e.ops + [""])))
    cons = PO.restricciones_desde_textos(desig, vs) if desig else []
    if cons is None: return None
    planos = []
    for e in curvas:
        if e.simbolos() - set(vs): return None
        a = PO.afin(f"({e.mxp[0]})-({e.mxp[1]})", vs)
        if a is None: return None
        planos.append(a)
    if "coordenad" in T:
        for v in vs:
            planos.append(({w: (F(1) if w == v else F(0)) for w in vs}, F(0)))
    if fl["cuadrante"] or fl["octante"]:
        for v in vs: cons.append(({w: (F(1) if w == v else F(0)) for w in vs}, F(0)))
    if vert and dim == 2:
        c, _ = _poligono(vert)
        for cs in c:
            a = PO.afin(cs.replace("=", "-(") + ")", vs) if cs.startswith("x=") or True else None
            if a is not None: planos.append(a)
    if not cons and not planos: return None
    # celdas del arreglo de planos dentro de las desigualdades
    celdas = {}
    import itertools as _it
    rng = [k * 0.5 for k in range(-16, 17)] + [0.25, 0.75, 1.25, 1.75]
    pts = list(_it.product(rng, repeat=dim)) if dim == 2 else [p for p in _it.product([k * 0.5 for k in range(-12, 13)] + [0.25, 0.75, 1.25], repeat=3)]
    def val(a, p): return float(sum(a[0][v] * p[i] for i, v in enumerate(vs)) + a[1])
    for p in pts:
        if any(val(c, p) < -1e-12 for c in cons): continue
        sg = tuple((val(a, p) > 0) - (val(a, p) < 0) for a in planos)
        if 0 in sg: continue
        celdas.setdefault(sg, []).append(p)
    cands = []
    for sg in celdas:
        cc = list(cons) + [a if s > 0 else PO._neg(a) for a, s in zip(planos, sg)]
        if _acotado(cc, vs): cands.append((sg, cc))
    if not planos and cons and _acotado(cons, vs): cands = [((), list(cons))]
    if not cands: return None
    if len(cands) > 1:
        notas.append(f"Los planos/rectas encierran {len(cands)} regiones acotadas; se usa la que está limitada por todas las curvas dadas (o la de mayor medida)")
        def _facetas(cc):
            # planos del enunciado que son frontera real (cara con interior) de la celda
            k = 0
            for a, s in zip(planos, sg_of[id(cc)]):
                otros = [c for c in cc if not (c[0] == (a[0] if s > 0 else PO._neg(a)[0]) and c[1] == (a[1] if s > 0 else PO._neg(a)[1]))]
                if PO.vertices(cc, vs) and _acotado(otros, vs) is False or len(PO.vertices(otros, vs)) != len(PO.vertices(cc, vs)): k += 1
            return k
        sg_of = {id(cc): sg for sg, cc in cands}
        cands.sort(key=lambda sc: (-_facetas(sc[1]), -_medida_aprox(sc[1], vs)))
    sg, cc = cands[0]
    f = _integrando_texto(n) or (cab["f"].rhs if "f" in cab else "1")
    if qty in ("volumen", "area"): f = "1"
    delta = cab["delta"].rhs if "delta" in cab else _dens_frase(T, dim)
    if qty in ("masa", "centroide") and delta is None: delta = "1"
    if qty == "centroide": delta = "1"
    m = re.search(r"\beje\s+([xyz])\b", T)
    cons_txt = [PO._afin_str(a, vs) + ">=0" for a in PO._normaliza(cc)]
    notas.append("Región lineal (politopo): " + "; ".join(cons_txt) + ". Se parte en piezas con límites afines y se integra exactamente.")
    return {"tipo": "politopo", "variables": vs, "restricciones": cons_txt, "f": f, "que": qty, "delta": delta or "1", "eje": m.group(1) if m else None}


def TRIPLE(T, n): return "TRIPLEINT" in n or "integral triple" in T


def _medida_aprox(cons, vs):
    ev = [(lambda p, c=c: float(sum(c[0][v] * p[i] for i, v in enumerate(vs)) + c[1])) for c in cons]
    caja = CT._caja(ev, len(vs))
    if caja is None: return 0
    N = 6000; vol = 1.0
    for a, b in caja: vol *= (b - a)
    k = sum(1 for p in CT._pts(N, caja) if all(g(p) >= -1e-12 for g in ev))
    return vol * k / N


def _cerrar_cuadrica(ecs, T):
    """una única ecuación que es una cuádrica cerrada (elipse/elipsoide/esfera) → la región que encierra (≤)"""
    ig = [(e, s) for e, s in ecs if e.cabecera is None and e.es_igualdad]
    if len(ig) != 1: return ecs
    e0 = ig[0][0]
    try:
        dim = 3 if "z" in e0.simbolos() else 2
        if e0.simbolos() - {"x", "y", "z"}: return ecs
        g = _g(e0, ("x", "y", "z") if dim == 3 else ("x", "y"))
        if dim == 3:
            c = _ajustar(g, _B3, 3)
            ok = c is not None and max(abs(v) for v in c[3:9]) < 1e-9 and c[0] * c[1] > 0 and c[1] * c[2] > 0 and c[0] * c[9] < 0 if c is not None else False
        else:
            c = _ajustar(g, _B2, 2)
            if c is None: return ecs
            a, b, cxy, d, ee, f0 = c
            r = f0 - (d * d / (4 * a) + ee * ee / (4 * b)) if abs(a) > 1e-12 and abs(b) > 1e-12 else 1
            ok = abs(cxy) < 1e-9 and a * b > 0 and a * r < 0
    except Exception:
        return ecs
    if not ok: return ecs
    nuevo = []
    for e, s in ecs:
        if e is e0: nuevo.append((Ec(f"({e0.mxp[0]})<=({e0.mxp[1]})"), s))
        else: nuevo.append((e, s))
    return nuevo


def _plan_desigualdades(texto, ecs, T, n, notas, f_forzada=None, qty_forzada=None):
    """región dada SOLO por desigualdades y que es una caja en polares/cilíndricas/esféricas → plan «coordenadas» con límites exactos"""
    from . import coordscan as CS
    fl = _flags(T)
    qty = qty_forzada or _quantity(T, n)
    ecs = _cerrar_cuadrica(ecs, T)
    cab, *_ = _region_geom(ecs, n, T)
    dim = 3 if any("z" in e.simbolos() for e, _ in ecs if e.cabecera is None) else 2
    gs = CT.desigualdades(ecs, fl, dim)
    if gs is None: return None
    r = CS.deducir(gs, dim)
    esc = None
    if r is None:
        esc = CS.deducir_escalado(gs, dim)
        if esc is None: return None
        r = (esc[0], esc[1])
    sis, niv = r
    f = f_forzada or _integrando_texto(n) or (cab["f"].rhs if "f" in cab else None)
    delta = cab["delta"].rhs if "delta" in cab else _dens_frase(T, dim)
    m = re.search(r"\beje\s+([xyz])\b", T)
    if esc is not None:
        _, niv_s, cen, sem = esc
        vs = ["x", "y", "z"][:dim]
        ren = {"z": "w"}
        niv2 = [[ren.get(a, a), b, c] for a, b, c in niv_s]
        if sis == "polares":
            mapa = {"x": f"({cen[0]})+({sem[0]})*r*cos(theta)", "y": f"({cen[1]})+({sem[1]})*r*sin(theta)"}; nuevas = ["r", "theta"]
        elif sis == "cilindricas":
            mapa = {"x": f"({cen[0]})+({sem[0]})*r*cos(theta)", "y": f"({cen[1]})+({sem[1]})*r*sin(theta)", "z": f"({cen[2]})+({sem[2]})*w"}; nuevas = ["r", "theta", "w"]
        else:
            mapa = {"x": f"({cen[0]})+({sem[0]})*rho*sin(phi)*cos(theta)", "y": f"({cen[1]})+({sem[1]})*rho*sin(phi)*sin(theta)", "z": f"({cen[2]})+({sem[2]})*rho*cos(phi)"}
            nuevas = ["rho", "phi", "theta"]
        if qty in ("area", "volumen"): fx = "1"
        elif qty == "integral": fx = f or "1"
        elif qty == "inercia":
            d = delta or "1"; eje = m.group(1) if m else "z"
            fx = f"({d})*(" + {"x": "y^2+z^2", "y": "x^2+z^2", "z": "x^2+y^2"}[eje] + ")"
            if dim == 2: fx = f"({d})*(" + {"x": "y^2", "y": "x^2", "z": "x^2+y^2"}[eje] + ")"
        else: return None
        notas.append("Región elíptica/desplazada: se traslada y escala (" + ", ".join(f"{v} = {mapa[v]}" for v in vs) + f") y es una caja en coordenadas {sis}: " + ", ".join(f"{a} de {b} a {c}" for a, b, c in niv2))
        return {"tipo": "cambio_variables_3d", "f": fx, "viejas": vs, "nuevas": nuevas, "mapa": mapa, "modo": "directo", "niveles": niv2}
    plan = {"tipo": "coordenadas", "sistema": sis, "niveles": niv if sis != "esfericas" else niv}
    if qty in ("area", "volumen"): plan["f"] = "1"
    elif qty == "integral": plan["f"] = f or "1"
    elif qty in ("masa", "centroide"):
        plan["delta"] = "1" if qty == "centroide" else (delta or "1")
        plan["que"] = "masa2d" if dim == 2 else "masa3d"
    elif qty == "inercia":
        eje = m.group(1) if m else "z"
        d = delta or "1"
        if dim == 2:
            suma = {"x": "y^2", "y": "x^2", "z": "x^2+y^2"}[eje]
            plan["f"] = f"({d})*({suma})"
        else:
            plan.update({"que": "inercia", "delta": d, "eje": eje})
    notas.append(f"Región escrita con desigualdades: es una caja en coordenadas {sis}: " + ", ".join(f"{a} de {b} a {c}" for a, b, c in niv))
    return plan


# ------------------------------------------------------------------------------------------------ cálculo vectorial
def _parte_balanceada(s, i):
    """s[i] es un paréntesis/ángulo de apertura → (contenido, índice siguiente)"""
    par = {"(": ")", "<": ">", "[": "]"}
    ab = s[i]; ce = par[ab]; prof = 0
    for j in range(i, len(s)):
        if s[j] in "([<" and (s[j] == ab or s[j] != "<"): prof += 1
        elif s[j] in ")]>" and (s[j] == ce or s[j] != ">"): prof -= 1
        if prof == 0: return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


def _comas_nivel0(s):
    out = []; prof = 0; cur = ""
    for ch in s:
        if ch in "([": prof += 1
        elif ch in ")]": prof -= 1
        if ch == "," and prof == 0: out.append(cur); cur = ""
        else: cur += ch
    out.append(cur)
    return [c.strip() for c in out if c.strip()]


def _campo(n, nombres="FGHVEB"):
    """campo vectorial F = (P, Q[, R]) o F = P i + Q j + R k → (nombre, [componentes en sintaxis del motor]) o None"""
    n = n.replace("⟨", "(").replace("⟩", ")").replace("〈", "(").replace("〉", ")")
    m = re.search(r"(?<![A-Za-z])([%s])\s*(?:\([^)=]*\))?\s*=\s*" % nombres, n)
    if not m: return None
    i = m.end()
    if i < len(n) and n[i] in "(<[":
        cont, _ = _parte_balanceada(n, i)
        cs = _comas_nivel0(cont)
        if len(cs) in (2, 3): return m.group(1), [mx(c) for c in cs]
    resto = re.split(r"(?:\.\s|\n|;|\s+(?:en|a lo largo|sobre|donde|sobre|para|calcul)\b)", n[i:], maxsplit=1)[0]
    partes = re.split(r"(?<![A-Za-z0-9_])\*?\s*([ijk])(?![A-Za-z0-9_(])|(?<=[0-9)\^a-z])\s*([ijk])(?![A-Za-z0-9_(])", resto)
    comp = {}
    buf = ""
    toks = re.findall(r"(.+?)\s*\*?\s*(?<![A-Za-z])([ijk])(?![A-Za-z0-9_(])", resto)
    for expr, c in toks:
        expr = expr.strip().lstrip("+").strip()
        if expr in ("", "+"): expr = "1"
        if expr == "-": expr = "-1"
        comp[c] = comp.get(c, "") + (("+" if comp.get(c) and not expr.startswith("-") else "") + mx(expr))
    if comp and set(comp) <= set("ijk"):
        ks = "ijk"[:3 if "k" in comp else 2]
        return m.group(1), [comp.get(k, "0") for k in ks]
    return None


def _curva_param(T, n, ecs, comps, notas):
    pts = _pares_puntos(n)
    # r(t) = (…) explícita
    m = re.search(r"\br\s*\(\s*t\s*\)\s*=\s*", n)
    if m and m.end() < len(n) and n[m.end()] in "(<[":
        cont, j = _parte_balanceada(n, m.end())
        cs = [mx(c) for c in _comas_nivel0(cont)]
        resto = n[j:]
        mi = re.search(r"(-?[\w./^*()\-]+?)\s*(?:<=|≤|\\leq)\s*t\s*(?:<=|≤)\s*([\w./^*()\-]+)", resto) or \
              re.search(r"t\s*(?:de|desde)\s*(-?[\w./^*()]+)\s*(?:a|hasta)\s*([\w./^*()]+)", resto)
        if not mi: raise NoReconocido("Indique el intervalo del parámetro, p. ej. 0 ≤ t ≤ 2π")
        a, b = mx(mi.group(1)), mx(mi.group(2))
        cv = {v: c for v, c in zip("xyz", cs)}; cv["t"] = [a, b]
        notas.append("Curva dada en forma paramétrica r(t)")
        return cv, None
    curvas = [e for e, _ in ecs if e.es_igualdad and e.cabecera is None and e.lhs not in ("F", "f") and not (e.simbolos() <= {"t"})]
    ex_circ = None
    for e in curvas:
        if "z" in e.simbolos(): continue
        cl = clase_curva(e)
        if cl[0] == "circulo":
            _, cx, cy, r2 = cl
            R = _txt_raiz(r2); horario = "horario" in T and "antihorario" not in T and "contrario" not in T
            cxs, cys = _fmt(cx), _fmt(cy)
            t0, t1 = ("2*pi", "0") if horario else ("0", "2*pi")
            cv = {"x": f"({cxs})+({R})*cos(t)", "y": f"({cys})+({R})*sin(t)", "t": [t0, t1]}
            notas.append(f"Circunferencia con centro ({cxs}, {cys}) y radio {R}, recorrida en sentido {'horario' if horario else 'antihorario'} (si no se indica, se toma el antihorario, orientación positiva)")
            green = {"cx": cxs, "cy": cys, "R": R, "signo": -1 if horario else 1}
            return cv, green
    # curva explícita y = g(x) o x = g(y)
    for e in curvas:
        if e.lhs in ("y", "x") and e.lhs not in _syms(e.rhs) and not ("z" in e.simbolos()):
            v = e.lhs; o = "x" if v == "y" else "y"
            if len(pts) >= 2:
                a, b = pts[0][0 if v == "y" else 1], pts[-1][0 if v == "y" else 1]
            else:
                mr = re.search(r"%s\s*(?:de|desde)\s*(?:%s\s*=\s*)?(-?[\w./]+)\s*(?:a|hasta)\s*(?:%s\s*=\s*)?(-?[\w./]+)" % (o, o, o), T)
                if not mr: continue
                a, b = mx(mr.group(1)), mx(mr.group(2))
            cv = {o: "t", v: e.rhs.replace(o, "(t)"), "t": [str(a), str(b)]}
            notas.append(f"Curva {e.crudo}: se parametriza con {o} = t, t de {a} a {b}")
            return cv, None
    # segmento entre dos puntos
    if len(pts) >= 2 and any(k in T for k in ("segmento", "recta", "linea recta", "de (", "desde")):
        A, B = pts[0], pts[-1]
        cv = {v: f"({a})+t*(({b})-({a}))" for v, a, b in zip("xyz", A, B)}; cv["t"] = ["0", "1"]
        notas.append(f"Segmento de {tuple(A)} a {tuple(B)}: r(t) = A + t(B − A), t de 0 a 1")
        return cv, None
    raise NoReconocido("No pude determinar la curva: dé r(t) = (…) con su intervalo, una circunferencia, y = g(x) con los extremos, o dos puntos (segmento)")


def _sup_area(T, n, ecs, notas):
    """área de la superficie z = f(x,y): ∬_D sqrt(1 + f_x² + f_y²) dA; D se deduce de las demás condiciones"""
    from . import vectorial as VE
    sup = None; otros = []
    for e, sc in ecs:
        if e.cabecera is not None: continue
        if e.es_igualdad and e.lhs == "z" and "z" not in _syms(e.rhs) and sup is None: sup = e.rhs
        elif e.es_igualdad and e.rhs == "z" and "z" not in _syms(e.lhs) and sup is None: sup = e.lhs
        else: otros.append(e)
    if sup is None: raise NoReconocido("Escriba la superficie como z = f(x, y)")
    fx, fy = VE.derivar(sup, "x").to_str(), VE.derivar(sup, "y").to_str()
    integrando = f"sqrt(1+({fx})^2+({fy})^2)"
    desig = []
    below = any(k in T for k in ("bajo", "debajo", "por debajo", "menor", "inferior"))
    for e in otros:
        if not e.es_igualdad: desig.append(e); continue
        s = e.simbolos()
        if s == {"z"} or (s <= {"z"}):
            c = e.rhs if e.lhs == "z" else e.lhs
            # z = c: region f(x,y) ≤ c (bajo el plano) o ≥ c (sobre)
            sentido = "<=" if (below or "sobre" not in T) else ">="
            desig.append(Ec(f"({sup}){sentido}({c})"))
        elif "z" not in s:
            cl = e.como_curva(); a, b = e.mxp[0], e.mxp[1]
            desig.append(Ec(f"({a})<=({b})"))                 # dentro del cilindro / curva cerrada
    if "plano xy" in T and not any("z" in str(d.crudo) for d in desig):
        desig.append(Ec(f"({sup})>=0"))
    if not desig: raise NoReconocido("Indique la región D del plano xy (o un plano z = c que corte la superficie)")
    ecs2 = [(d, 0) for d in desig]
    fl = _flags(T)
    plan = None
    try:
        plan = _plan_desigualdades("", ecs2, T, n, notas, f_forzada=integrando, qty_forzada="integral")
    except Exception:
        plan = None
    if plan is None:
        try:
            plan = _plan_desigualdades("", [(Ec(f"({a.partes[1]})>=0") if False else d, 0) for d in desig], T, n, notas, f_forzada=integrando, qty_forzada="integral")
        except Exception:
            plan = None
    if plan is None: raise NoReconocido("No pude describir la región D en polares ni como caja; escriba la integral con límites")
    notas.append(f"Área de superficie: A = ∬_D √(1 + (∂z/∂x)² + (∂z/∂y)²) dA con z = {sup}, ∂z/∂x = {fx}, ∂z/∂y = {fy}")
    return plan


def _vectorial(T, n, texto, ecs, notas):
    if "area de la superficie" in T or "area superficial" in T or "area de superficie" in T:
        return _sup_area(T, n, ecs, notas), []
    cf = _campo(n)
    cab = {e.cabecera[0]: e for e, _ in ecs if e.cabecera is not None}
    esc = None
    for nm in ("f", "g", "phi", "u"):
        if nm in cab and cf is None: esc = (nm, cab[nm].rhs, cab[nm].cabecera[1]); break
    if esc is None and cf is None:
        for e, _ in ecs:
            if e.es_igualdad and e.lhs in ("f", "g") : esc = (e.lhs, e.rhs, None); break
    if "gradiente" in T and esc:
        vs = esc[2] or sorted(_syms(esc[1]) & COORD) or ["x", "y"]
        return {"tipo": "vectorial", "op": "gradiente", "f": esc[1], "variables": vs}, ["Gradiente de f = " + esc[1]]
    if "laplaciano" in T and esc:
        vs = esc[2] or sorted(_syms(esc[1]) & COORD) or ["x", "y"]
        return {"tipo": "vectorial", "op": "laplaciano", "f": esc[1], "variables": vs}, ["Laplaciano de f = " + esc[1]]
    if cf is None: raise NoReconocido("No encontré el campo vectorial; escríbalo como F = (P, Q, R) o F = P i + Q j + R k")
    nm, comps = cf
    vs = ["x", "y", "z"][:len(comps)]
    base = {"tipo": "vectorial", "campo": comps, "variables": vs}
    nota = f"Campo {nm} = ({', '.join(comps)})"
    if "divergencia" in T and "flujo" not in T: return dict(base, op="divergencia"), [nota]
    if "rotacional" in T: return dict(base, op="rotacional"), [nota]
    if any(k in T for k in ("conservativo", "funcion potencial", "potencial")) and not any(k in T for k in ("trabajo", "integral de linea")):
        return dict(base, op="conservativo"), [nota]
    if any(k in T for k in ("trabajo", "integral de linea", "circulacion", "a lo largo")):
        nn = []
        cv, green = _curva_param(T, n, ecs, comps, nn)
        pl = dict(base, op="linea", curva=cv)
        if green and len(comps) == 2: pl["green"] = green
        return pl, [nota] + nn
    if "flujo" in T:
        # teorema de la divergencia para superficies cerradas: ∬ F·n dS = ∭ div F dV
        from . import vectorial as VE
        div = None
        for k, (c, v) in enumerate(zip(comps, vs)):
            d = VE.derivar(c, v); div = d if div is None else div + d
        ecs3 = []
        for e, sc in ecs:
            if e.cabecera is not None or "z" not in e.simbolos() and e.es_igualdad and False: continue
            if e.es_igualdad and e.lhs == nm: continue
            if e.es_igualdad and clase_superficie_segura(e) == "esfera":
                ecs3.append((Ec(f"({e.mxp[0]})<=({e.mxp[1]})"), 0))
            elif not e.es_igualdad: ecs3.append((e, sc))
        if not ecs3: raise NoReconocido("Para el flujo describa el sólido cerrado (esfera, caja con desigualdades…)")
        nn = [f"Flujo a través de una superficie cerrada: teorema de la divergencia, ∬ F·n dS = ∭ div F dV con div F = {div.to_str()}"]
        plan = _plan_desigualdades(texto, ecs3, T, n, nn, f_forzada=div.to_str(), qty_forzada="integral")
        if plan is None:
            pol = None
            try: pol = _politopo_plan_desde(ecs3, T, n, nn, div.to_str())
            except Exception: pol = None
            plan = pol
        if plan is None: raise NoReconocido("No pude describir el sólido del flujo")
        return plan, [nota] + nn
    raise NoReconocido("No reconocí qué se pide del campo vectorial (divergencia, rotacional, conservativo/potencial, trabajo, flujo)")


def clase_superficie_segura(e):
    try: return clase_superficie(e)[0]
    except Exception: return "otra"


def _politopo_plan_desde(ecs3, T, n, notas, f):
    desig = []
    vs = ["x", "y", "z"]
    for e, _ in ecs3:
        desig.append("".join(p + o for p, o in zip(e.mxp, e.ops + [""])))
    cons = PO.restricciones_desde_textos(desig, vs)
    if cons is None or not _acotado(cons, vs): return None
    cons_txt = [PO._afin_str(a, vs) + ">=0" for a in PO._normaliza(cons)]
    return {"tipo": "politopo", "variables": vs, "restricciones": cons_txt, "f": f, "que": "integral", "delta": "1", "eje": None}


def resolver(texto, req, st):
    """interpreta el enunciado y lo resuelve con api3; devuelve la respuesta del contrato con la interpretación al inicio de los pasos"""
    from . import api3
    plan, notas = clasificar(texto)
    alternativas = plan.pop("alternativas", [])
    if plan["tipo"] == "iterada" and len(plan["niveles"]) == 2:
        (v1, lo1, hi1), (v2, lo2, hi2) = plan["niveles"]
        alternativas.append({"tipo": "cambio_orden", "f": plan["f"], "curvas": [f"{v1}={lo1}", f"{v1}={hi1}", f"{v2}={lo2}", f"{v2}={hi2}"]})
    candidatos = []
    for p0 in [plan] + alternativas:
        candidatos.append(p0)
        if "orden" in p0 and p0["tipo"] in ("cambio_variables", "cambio_variables_masa", "region", "triple_region"):
            candidatos.append(dict(p0, orden="dxdy" if p0["orden"] == "dydx" else "dydx"))
    mejor = None; ultimo_error = None; rechazados = []
    ctx = _contexto_contraste(texto)
    esp_cache = []
    def _esperado():
        if not esp_cache:
            try: esp_cache.append(CT.esperado(*ctx) if ctx else None)
            except Exception: esp_cache.append(None)
        return esp_cache[0]
    for p in candidatos:
        try:
            r = api3._run(p["tipo"], dict(p), req, st)
        except (InvalidRequest, Exception) as e:   # noqa
            ultimo_error = e
            if mejor is None and isinstance(e, InvalidRequest): pass
            continue
        r.setdefault("data", {})["plan"] = p
        if any("regiones acotadas" in w for w in r.get("warnings", [])) and "punto" not in p:
            # varias regiones cerradas y el enunciado no indica cuál: se toma la del primer cuadrante
            r2 = None
            for px in (0.5, 1.0, 1.5, 2.0, 0.25, 2.5, 3.0, 4.0):
                for py in (0.5, 1.0, 1.5, 2.0, 0.25, 2.5, 3.0, 4.0):
                    try:
                        r2 = api3._run(p["tipo"], dict(p, punto=[str(px), str(py)]), req, st)
                    except Exception:
                        r2 = None; continue
                    if r2 is not None and not any("regiones acotadas" in w for w in r2.get("warnings", [])):
                        p = dict(p, punto=[str(px), str(py)]); r = r2
                        r.setdefault("warnings", []).append("Las curvas encierran varias regiones; se tomó la del primer cuadrante que contiene el punto (%s, %s)." % (px, py))
                        r2 = "ok"; break
                    r2 = None
                if r2 == "ok": break
        esp = _esperado()
        if esp is not None:
            ok = CT.coincide(esp, f"{r.get('exact_result')} {r.get('approximate_result')}")
            if ok is False:
                rechazados.append((p, esp)); continue
            if ok:
                r.setdefault("steps", []).append({"text": "Contraste independiente con el enunciado (cuasi-Monte Carlo directo sobre las desigualdades): esperado ≈ " + ", ".join("%.4g" % v for v in esp) + " — coincide."})
        if r.get("status") == "success_exact": mejor = (p, r); break
        if mejor is None: mejor = (p, r)
    if mejor is None and rechazados:
        from ..errors import VerificationFailed
        raise VerificationFailed("El planteamiento no coincide con un contraste independiente hecho directamente sobre el enunciado "
                                 "(posible restricción ignorada o región mal interpretada); no se entrega el resultado.",
                                 {"esperado_aprox": rechazados[0][1], "planteamiento": rechazados[0][0]})
    if mejor is None:
        raise ultimo_error if ultimo_error else NoReconocido("No pude resolver el enunciado")
    p, r = mejor
    if p.get("distancia") and r.get("data", {}).get("puntos"):
        from .cas3 import from_ast as _fa
        lin = []; dmin = None
        for pt in r["data"]["puntos"]:
            try:
                d = _fa(normalize(parse(f"sqrt({pt['valor']})")))
                dv = math.sqrt(float(pt["valor_aprox"]) if pt.get("valor_aprox") is not None else float(_fa(normalize(parse(pt['valor']))).eval({})))
            except Exception:
                continue
            cl = pt.get("clase") or ""
            etq = "mínima" if "mín" in cl else ("máxima" if "máx" in cl else "")
            lin.append(f"Distancia {etq} = {d.to_str()} ≈ {dv:.10g}  en P({', '.join(pt['coordenadas'])})".replace("  ", " "))
            if "mín" in cl and (dmin is None or dv < dmin): dmin = dv
        if lin:
            r["exact_result"] = (r.get("exact_result") or "") + "\n" + "\n".join(lin)
            r["approximate_result"] = f"{dmin:.10g}" if dmin is not None else r.get("approximate_result")
            r.setdefault("steps", []).append({"text": "El valor de f es el cuadrado de la distancia: se extrae la raíz cuadrada. " + "; ".join(lin)})
    pasos = [{"text": "Interpretación del enunciado", "latex": None}]
    pasos[0]["text"] = "Interpretación del enunciado: " + " ".join(notas) if notas else "Interpretación del enunciado"
    pasos.append({"text": f"Tipo de ejercicio reconocido: {p['tipo']}"})
    r["steps"] = pasos + list(r.get("steps", []))
    r["method"] = "enunciado→" + str(r.get("method", p["tipo"]))
    return r
