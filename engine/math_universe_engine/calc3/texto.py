"""Lectura de enunciados escritos como en una guía: texto mixto (español/inglés + notación matemática) → ecuaciones y expresiones.

- `normalizar(texto)`: Unicode matemático → ASCII (superíndices, √, π, θ, ≤, letras en cursiva matemática…).
- `mx(fragmento)`: fragmento matemático → texto que entiende el analizador del motor (multiplicación implícita, sen→sin, cos v → cos(v)…).
- `ecuaciones(texto)`: encuentra las ecuaciones/desigualdades que aparecen dentro de la prosa y las devuelve ya separadas
  («y = x^2 y y = 2x» → dos ecuaciones; la «y» conjunción se distingue de la variable y).
"""
import re
import unicodedata

FUNCS = {"sin", "cos", "tan", "sec", "csc", "cot", "ln", "log", "exp", "sqrt", "abs", "asin", "acos", "atan", "sinh", "cosh", "tanh"}
ALIAS = {"sen": "sin", "tg": "tan", "tang": "tan", "arcsen": "asin", "arcsin": "asin", "arccos": "acos", "arctan": "atan", "arctg": "atan",
         "senh": "sinh", "lg": "log"}
CONSTS = {"pi", "theta", "phi", "rho", "lam", "mu", "nu", "alpha", "beta", "gamma", "sigma", "omega", "varphi", "inf", "delta"}
VARALF = set("xyzuvwt")
VARALF2 = set("xyzuvwtabcdkmnpqrs")
_STOP = {"el", "la", "lo", "los", "las", "de", "del", "en", "es", "se", "si", "un", "una", "al", "no", "ni", "su", "sus", "por", "con", "que",
         "sea", "son", "ser", "hay", "dos", "tres", "mas", "uno", "era", "dar", "den", "dan", "sub", "sup", "and", "the", "for", "dx", "dy", "dz", "dv", "da",
         "pasa", "ver", "eje", "ejes", "arc", "cas", "sin", "tan", "cos", "sec", "csc"}

_SUP = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-", "⁺": "+"}
_REEMPLAZO = {"−": "-", "–": "-", "—": "-", "×": "*", "·": "*", "⋅": "*", "÷": "/", "≤": "<=", "≥": ">=", "⩽": "<=", "⩾": ">=",
              "π": "pi", "θ": "theta", "ϑ": "theta", "φ": "phi", "ϕ": "phi", "ρ": "rho", "λ": "lam", "μ": "mu", "ν": "nu", "δ": "delta",
              "∞": "inf", "′": "'", "’": "'", "“": '"', "”": '"', "√": "√"}


def normalizar(t):
    t = t.replace("∬", " DOBLEINT ").replace("∭", " TRIPLEINT ").replace("∮", " ∫ ")
    out = []
    i = 0
    while i < len(t):
        c = t[i]
        if c in _SUP:
            j = i
            s = ""
            while j < len(t) and t[j] in _SUP:
                s += _SUP[t[j]]; j += 1
            out.append("^" + s if not s.startswith("-") else "^(" + s + ")")
            i = j; continue
        out.append(c); i += 1
    t = "".join(out)
    t = unicodedata.normalize("NFKC", t)
    for a, b in _REEMPLAZO.items():
        t = t.replace(a, b)
    t = t.replace("​", "").replace(" ", " ")
    t = re.sub(r"\bs\s*\.\s*a\s*\.", " SUJETOA ", t, flags=re.I)
    t = re.sub(r"\bsuje(?:t[ao]s?|cion|ción)\s+a\b", " SUJETOA ", t, flags=re.I)
    t = re.sub(r"\bcon\s+la[s]?\s+restricci[oó]n(?:es)?\b", " SUJETOA ", t, flags=re.I)
    # √ sin paréntesis: √x, √2, √(...)
    t = re.sub(r"√\s*\(", "sqrt(", t)
    t = re.sub(r"√\s*([A-Za-z0-9_.]+)", r"sqrt(\1)", t)
    t = t.replace("√", "sqrt")
    prev = None
    while prev != t:                         # |expr| → abs(expr)
        prev = t
        t = re.sub(r"\|([^|]+)\|", r"abs(\1)", t)
    return t


def quitar_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------------------- fragmento matemático → texto del motor
_TOK = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([A-Za-z]+(?:_\w+|\d+)?)|(<=|>=|\*\*|[-+*/^=<>(),|]))")


def _tokens(s):
    pos = 0; out = []
    s = s.strip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m:
            raise ValueError(f"Carácter no reconocido «{s[pos:pos + 1]}» en «{s}»")
        sp = s[pos:m.start(0) + len(m.group(0)) - len(m.group(0).lstrip())] if False else ""
        espacio_antes = m.group(0)[0].isspace() or (pos > 0 and s[pos - 1].isspace())
        if m.group(1) is not None: out.append(("num", m.group(1), espacio_antes))
        elif m.group(2) is not None: out.append(("word", m.group(2), espacio_antes))
        else: out.append(("op", m.group(3), espacio_antes))
        pos = m.end()
    return out


def _palabra(w):
    """lista de tokens (kind, texto) para una palabra: función, constante, variable o producto de variables"""
    lw = w.lower()
    lw = ALIAS.get(lw, lw)
    if lw in FUNCS: return [("func", lw)]
    if lw == "e": return [("var", "e")]
    if lw in CONSTS: return [("var", lw)]
    if re.fullmatch(r"[A-Za-z]\d+", w) or re.fullmatch(r"[A-Za-z]_\w+", w): return [("var", w)]
    if len(w) == 1: return [("var", w)]
    # función pegada a variable: sinx, cosv, lnx
    for f in sorted(FUNCS | set(ALIAS), key=len, reverse=True):
        if lw.startswith(f) and len(lw) > len(f):
            return [("func", ALIAS.get(f, f))] + _palabra(w[len(f):])
    for c in sorted(CONSTS, key=len, reverse=True):
        if lw.startswith(c) and len(lw) > len(c):
            return [("var", c)] + _palabra(w[len(c):])
    # producto de letras sueltas: xy → x y
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", w)
    if m and len(m.group(1)) > 1:
        letras = list(m.group(1)); letras[-1] += m.group(2)
        return [("var", c) for c in letras]
    return [("var", c) for c in w]


def mx(frag):
    """fragmento matemático → expresión ASCII con multiplicación explícita y funciones con paréntesis"""
    frag = normalizar(frag).strip()
    frag = frag.replace("**", "^")
    raw = _tokens(frag)
    # 1) expandir palabras
    toks = []   # (kind, text) kind: num var func op
    for k, t, sp in raw:
        if k == "num": toks.append(["num", t, sp])
        elif k == "word": toks.extend([[kk, tt, sp if i == 0 else False] for i, (kk, tt) in enumerate(_palabra(t))])
        else: toks.append(["op", t, sp])
    # 2) funciones sin paréntesis: cos v, sin 2x, sin^2 x
    out = []
    i = 0
    n = len(toks)
    while i < n:
        k, t, sp = toks[i]
        if k == "func":
            pot = None
            j = i + 1
            if j < n and toks[j][1] == "^" and j + 1 < n:
                # sin^2 x → (sin(x))^2 ; sin^(2) x
                if toks[j + 1][1] == "(":
                    d = 0; p = j + 1; trozo = []
                    while p < n:
                        trozo.append(toks[p][1])
                        if toks[p][1] == "(": d += 1
                        elif toks[p][1] == ")":
                            d -= 1
                            if d == 0: break
                        p += 1
                    pot = "".join(trozo); j = p + 1
                else:
                    pot = toks[j + 1][1]; j += 2
            if j < n and toks[j][1] == "(":
                d = 0; p = j; trozo = []
                while p < n:
                    trozo.append(toks[p])
                    if toks[p][1] == "(": d += 1
                    elif toks[p][1] == ")":
                        d -= 1
                        if d == 0: break
                    p += 1
                inner = mx(" ".join(x[1] if x[0] != "func" else x[1] for x in trozo[1:-1])) if trozo else ""
                inner = _reconstruir(trozo[1:-1])
                call = f"{t}({inner})"
                i = p + 1
            else:
                # argumento = primer trozo de números/variables sin espacios (2x, x, xy)
                trozo = []
                p = j
                while p < n and toks[p][0] in ("num", "var") and (not trozo or not toks[p][2]):
                    trozo.append(toks[p]); p += 1
                    if toks[p - 1][0] == "var" and p < n and toks[p][1] == "^" and p + 1 < n:
                        trozo.append(toks[p]); trozo.append(toks[p + 1]); p += 2
                if not trozo: raise ValueError(f"La función {t} no tiene argumento")
                call = f"{t}({_reconstruir(trozo)})"
                i = p
            if pot is not None: call = f"({call})^{pot}"
            out.append(("atom", call, sp))
            continue
        out.append((k, t, sp)); i += 1
    return _reconstruir_con_mult(out)


def _reconstruir(toks):
    return _reconstruir_con_mult([(k, t, sp) for k, t, sp in toks])


def _reconstruir_con_mult(toks):
    """inserta * entre operandos contiguos"""
    res = []
    prev = None
    for k, t, sp in toks:
        if k == "func":   # (no debería llegar: func ya se resolvió)
            k = "atom"
        if prev is not None:
            pk, pt = prev
            fin_op = pk in ("num", "var", "atom") or pt == ")"
            ini_op = k in ("num", "var", "atom") or t == "("
            if fin_op and ini_op:
                if not (pk == "num" and k == "num"):
                    res.append("*")
                else:
                    res.append("*")
        res.append(t)
        prev = (k, t)
    return "".join(res)


# ------------------------------------------------------------------------- ecuaciones dentro de la prosa
_REL = {"=", "<=", ">=", "<", ">"}
_PTK = re.compile(r"(\d+(?:\.\d+)?)|([A-Za-z]+(?:_\w+|\d+)?)|(<=|>=|[-+*/^=<>(),|{};:.\[\]'\"!?¿¡])|(\s+)|(.)")


def _es_palabra_mat(w):
    lw = w.lower()
    if lw in FUNCS or lw in ALIAS or lw in CONSTS or lw == "e": return True
    if len(w) == 1: return True
    if re.fullmatch(r"[A-Za-z]\d+", w) or re.fullmatch(r"[A-Za-z]_\w+", w): return True
    if all(c in VARALF for c in lw): return True
    if len(lw) <= 3 and lw not in _STOP and all(c in VARALF2 for c in lw): return True
    m = re.fullmatch(r"([a-z]+)(\d+)", lw)
    if m and all(c in VARALF for c in m.group(1)): return True
    for f in sorted(FUNCS | set(ALIAS), key=len, reverse=True):   # sinx, cosv
        if lw.startswith(f) and len(lw) - len(f) <= 3 and all(c in VARALF for c in lw[len(f):]): return True
    return False


def tokens_texto(t):
    """[(tipo, texto)] tipo: num / word(mat) / text(palabra no matemática) / op / sep"""
    out = []
    for m in _PTK.finditer(t):
        if m.group(1): out.append(["num", m.group(1)])
        elif m.group(2):
            w = m.group(2)
            out.append(["word" if _es_palabra_mat(w) else "text", w])
        elif m.group(3):
            c = m.group(3)
            out.append(["op" if c in "-+*/^=<>()<=>=|," or c in ("<=", ">=") else "sep", c])
        elif m.group(5):
            out.append(["sep", m.group(5)])
    return out


def _fin_operando(tok):
    return tok is not None and (tok[0] in ("num", "word") or tok[1] == ")")


def _ini_operando(tok):
    return tok is not None and (tok[0] in ("num", "word") or tok[1] == "(")


def _separar_conjunciones(toks):
    """marca como sep las «y» que son conjunción española (no la variable y)"""
    n = len(toks)
    # «a», «o», «e», «u» sueltas seguidas de una palabra española son preposiciones/conjunciones, no variables
    for i, tk in enumerate(toks):
        if tk[0] == "word" and tk[1] in ("a", "o", "e", "u") and i + 1 < n and toks[i + 1][0] == "text":
            ant = toks[i - 1] if i > 0 else None
            if ant is None or ant[0] in ("text", "sep") or ant[1] in (",", ";"):
                tk[0] = "text"
            elif ant[0] in ("num", "word") or ant[1] == ")":
                tk[0] = "text"
    prev = None
    for i, tk in enumerate(toks):
        if tk[0] == "word" and tk[1] == "y":
            sig = toks[i + 1] if i + 1 < n else None
            # buscar el siguiente token significativo
            conj = False
            if prev is not None and prev[0] == "text" and sig is not None and _ini_operando(sig) and sig[1] not in _REL:
                # «… coordenados y x+y+z=1»: tras una palabra, «y» seguida de un operando y de una relación posterior es conjunción
                k = i + 1; tiene_rel = False
                while k < n and toks[k][0] not in ("sep", "text"):
                    if toks[k][1] in _REL: tiene_rel = True; break
                    k += 1
                conj = tiene_rel
            elif _fin_operando(prev):
                if sig is not None and sig[0] == "text": conj = True
                elif sig is not None and _ini_operando(sig):
                    # ¿hay una relación después, y ya hubo una antes en este tramo?
                    antes = False
                    k = i - 1
                    while k >= 0 and toks[k][0] not in ("sep", "text"):
                        if toks[k][1] in _REL: antes = True; break
                        k -= 1
                    despues = False
                    k = i + 1
                    while k < n and toks[k][0] not in ("sep", "text"):
                        if toks[k][1] in _REL: despues = True; break
                        k += 1
                    conj = antes and despues
                    if conj:
                        # varias «y» seguidas entre dos relaciones: la conjunción es la última («u y y y²» = u·y ; y²)
                        k = i + 1
                        while k < n and toks[k][0] not in ("sep", "text") and toks[k][1] not in _REL:
                            if toks[k][0] == "word" and toks[k][1] == "y" and k + 1 < n and _ini_operando(toks[k + 1]):
                                conj = False; break
                            k += 1
            if conj:
                tk[0] = "sep"; tk[1] = ";"
                prev = tk
                continue
        if tk[0] != "sep" or tk[1] in (")",):
            prev = tk if tk[0] != "sep" else prev
        if tk[0] == "sep": prev = None
    return toks


def ecuaciones(texto):
    """lista de cadenas matemáticas (ya con mx) que contienen = < > <= >= en el texto, separando conjunciones"""
    t = quitar_acentos(normalizar(texto))
    toks = tokens_texto(t)
    toks = _separar_conjunciones(toks)
    # tramos separados por palabras de texto o separadores; las comas dentro de paréntesis no separan
    tramos = []; cur = []; prof = 0
    for k, s in toks:
        if s == "(": prof += 1
        if s == ")": prof = max(0, prof - 1)
        sepr = (k in ("text",)) or (k == "sep" and s not in (" ", "\t", "\n") and s not in ("'",)) or (k == "op" and s == "," and prof == 0)
        if k == "sep" and s.isspace():
            sepr = False
        if sepr:
            if cur: tramos.append(cur); cur = []
        else:
            if k == "sep" and s.isspace(): continue
            cur.append((k, s))
            if k == "op" and s == "(": pass
    if cur: tramos.append(cur)
    res = []
    for tr in tramos:
        if any(s in _REL for _, s in tr) and tr[0][1] not in _REL and tr[-1][1] not in _REL:
            # recortar «y» sobrante al final/principio no se hace: ya se resolvió arriba
            txt = " ".join(s for _, s in tr)
            res.append(txt)
    return res


def a_motor(eq):
    """ecuación/desigualdad en texto → partes mx. «a = b» → ('=', mx(a), mx(b)); cadena a <= x <= b → ('chain', [mx..], [ops])"""
    partes = re.split(r"(<=|>=|=|<|>)", eq)
    exprs = [mx(p) for p in partes[0::2]]
    ops = partes[1::2]
    return exprs, ops
