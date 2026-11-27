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
    if restr:
        positivo = bool(re.search(r"\^\(\s*\d+\s*/\s*\d+\s*\)", obj)) or "primer octante" in T or "no negativ" in T
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
            cab[e.cabecera[0]] = e
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
    opt = any(k in T for k in ("extremo", "maximo", "minimo", "maximiz", "minimiz", "optimiz", "punto critico", "puntos criticos", "lagrange",
                               "mas cercano", "mas lejano", "mas proximo", "distancia minima", "distancia maxima", "mas grande", "punto de silla", "sujetoa"))
    if opt and not hay_integral and not any(k in T for k in ("area de", "centro de masa", "momento de inercia")):
        return _optimizacion(T, texto, ecs)
    if hay_integral or _quantity(T, n) != "integral":
        notas = []
        plan = _integral(T, n, ecs, notas)
        return plan, notas
    raise NoReconocido("No reconocí el tipo de ejercicio. Escríbalo como en la guía: la función, la región (curvas o desigualdades) y qué se pide")



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
    mejor = None; ultimo_error = None
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
        if r.get("status") == "success_exact": mejor = (p, r); break
        if mejor is None: mejor = (p, r)
    if mejor is None:
        raise ultimo_error if ultimo_error else NoReconocido("No pude resolver el enunciado")
    p, r = mejor
    pasos = [{"text": "Interpretación del enunciado", "latex": None}]
    pasos[0]["text"] = "Interpretación del enunciado: " + " ".join(notas) if notas else "Interpretación del enunciado"
    pasos.append({"text": f"Tipo de ejercicio reconocido: {p['tipo']}"})
    r["steps"] = pasos + list(r.get("steps", []))
    r["method"] = "enunciado→" + str(r.get("method", p["tipo"]))
    return r
