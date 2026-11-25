"""Valida solicitudes (esquema + límites) y despacha operaciones. Contrato: Adenda rectora §7."""
import json
import math
import os
import re
import time
from fractions import Fraction
from . import __version__, symbolic, limits, calculus, numeric_mp, solve as S
from .arith import evaluate as arith_eval, format_fraction, to_decimal
from .ast_tools import normalize, to_str, free_symbols, eval_float, eval_q, const_value
from .errors import *
from .parser import parse
from .poly import Poly, u_factor, u_to_poly
from .qsqrt import Q, q_to_decimal
from .rational import Ctx, to_rf, rf_str, condition_list
from .verify import equivalent

API_VERSION = "1.1"
_SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "schema")
try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def _load(name):
    with open(os.path.join(_SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


REQUEST_SCHEMA = _load("request.schema.json")
RESPONSE_SCHEMA = _load("response.schema.json")

STATUS_BY_CODE = {
    "INVALID_REQUEST": "invalid_input", "PARSE_ERROR": "invalid_input", "LIMIT_EXCEEDED": "invalid_input",
    "VERSION_MISMATCH": "invalid_input", "DOMAIN_ERROR": "domain_error", "NOT_IMPLEMENTED": "unsupported",
    "DEPENDENCY_MISSING": "unsupported", "NOT_SOLVED": "unsupported", "TIMEOUT": "timeout",
    "VERIFICATION_FAILED": "internal_error", "INTERNAL_ERROR": "internal_error",
}


def _dependencias():
    """Versiones REALES importadas en este proceso (no las declaradas): permite comprobar en la app instalada que
    SymPy y mpmath están empaquetados (Python embebido en Windows, Chaquopy en Android)."""
    import importlib
    import platform
    out = {"python": platform.python_version()}
    for mod in ("sympy", "mpmath", "jsonschema"):            # lista fija: nunca un nombre que venga de la entrada
        try:
            out[mod] = getattr(importlib.import_module(mod), "__version__", "desconocida")
        except Exception:
            out[mod] = None
    return out


def capabilities():
    sym = symbolic.available()
    return {"engine_version": __version__, "api_version": API_VERSION, "dependencies": _dependencias(),
            "modules": {
                "parser_seguro": "estable", "aritmetica_exacta": "estable",
                "simplificacion_racional_con_dominio": "estable", "expansion": "estable",
                "factorizacion_univariante_Q": "estable (grado>=6 puede quedar sin verificar irreducibilidad)",
                "ecuaciones_una_variable": "estable (hasta grado 2 exacto + raices racionales; cubicas irreducibles: no soportadas)",
                "sistemas_lineales": "estable", "despeje_literal_grado_1": "estable",
                "derivadas": "estable", "integrales": "experimental (polinomios, racionales con factores lineales/cuadraticos, poly*{exp,sin,cos}, x^k*ln x)",
                "limites": "experimental (series de Laurent; sin infinitos de funciones trascendentes)",
                "verificacion_independiente": "estable (por operacion)",
                "respaldo_sympy": "experimental (resultado verificado de forma independiente)" if sym else "no_disponible_en_este_entorno",
                "matrices_algebra_lineal": "estable (entradas racionales exactas, hasta 40x40: suma, resta, producto, transpuesta, determinante, inversa, rango, rref, sistemas; cada resultado con verificacion independiente)", "determinant": "alias de matrix_det", "autovalores": "planificada", "estadistica": "planificada",
                "ingenieria_electrica": "planificada"}}


def _validate(req):
    if not isinstance(req, dict):
        raise InvalidRequest("La solicitud debe ser un objeto JSON")
    if jsonschema is not None:
        err = next(iter(jsonschema.Draft202012Validator(REQUEST_SCHEMA).iter_errors(req)), None)
        if err is not None:
            raise InvalidRequest("Solicitud inválida: " + err.message, {"path": [str(p) for p in err.absolute_path]})
    elif "operation" not in req:
        raise InvalidRequest("Falta 'operation'")


def _approx_float(val, precision, warnings, given=True):
    digits = min(precision, 15)
    if precision > 15 and given:
        warnings.append("precision > 15 cifras: no se pudo usar mpmath para este resultado; solo se garantizan ~15 cifras")
    return format(val, f".{digits}g")


class State:
    def __init__(self, req):
        self.req = req
        self.assumptions = req.get("assumptions") or {}
        self.precision_given = "precision" in req
        self.precision = req.get("precision", 30)
        self.warnings = []
        self.conditions = []

    def used(self, names):
        for k in self.assumptions:
            if k not in names:
                self.warnings.append(f"El supuesto sobre '{k}' no se aplicó: la variable no aparece en la expresión")


def _text_ast(text):
    return normalize(parse(text))


def _result(status="success_exact", exact=None, approx=None, method=None, ver=("not_performed", None), data=None, parsed=None, extra_conditions=None):
    out = {"status": status, "exact_result": exact, "approximate_result": approx, "method": method,
           "verification": {"status": ver[0], "method": ver[1]}}
    if data is not None: out["data"] = data
    if parsed is not None: out["parsed_input"] = parsed
    return out


def _finish_verification(res, verdict, method, unverified=None):
    res["verification"] = {"status": verdict, "method": method}
    if verdict == "failed":
        raise VerificationFailed("La verificación independiente falló: el resultado no se entrega como válido",
                                 {"unverified_result": unverified if unverified is not None else res.get("exact_result"), "method": method})
    return res


def _numeric_approx(exact_text, st):
    try:
        ast = _text_ast(exact_text)
        if free_symbols(ast): return None
        try:
            q = eval_q(ast, {})                       # radicales cuadráticos: cifras exactas con aritmética entera
            if q.b != 0 and q.d > 0:
                return q_to_decimal(q, st.precision)
        except (NotImplementedOperation, MathDomainError, ValueError):
            pass
        if st.precision_given and st.precision > 15 and numeric_mp.available():
            txt = numeric_mp.approx(ast, st.precision)   # mpmath, contrastado con la evaluación en coma flotante
            if txt is not None: return txt
        return _approx_float(eval_float(ast, {}), st.precision, st.warnings, st.precision_given)
    except Exception:
        return None


# ===================== operaciones =====================
def op_parse(req, st):
    text = req["expression"]
    parts = [p.strip() for p in re.split(r"[;\n]", text) if p.strip()]
    asts = []
    for p in parts:
        sides = p.split("=")
        if len(sides) > 2: raise ParseError("Más de un signo '='")
        asts.append(" = ".join(to_str(normalize(parse(s))) for s in sides))
    syms = sorted(set().union(*[free_symbols(normalize(parse(s))) for p in parts for s in p.split("=")]))
    return _result(exact=None, method="parser_seguro", parsed={"canonical": asts, "symbols": syms})


def _canon_expr(ast, st, cancel=True):
    ctx = Ctx(st.assumptions)
    rf = to_rf(ast, ctx)
    if cancel: rf = rf.cancel(ctx.warnings)
    else:
        from .rational import RF
        rf = RF(rf.n, rf.d)
    conds = condition_list(ctx.conds, st.assumptions) + [i for i in dict.fromkeys(ctx.ineqs)]
    st.warnings += ctx.warnings
    return rf, conds


def op_evaluate(req, st):
    ast = _text_ast(req["expression"]); parsed = {"canonical": to_str(ast)}
    if not free_symbols(ast):
        try:
            val = arith_eval(ast)
            r = _result(exact=format_fraction(val), method="aritmetica_racional_exacta", parsed=parsed)
            if val.denominator != 1:
                r["approximate_result"] = to_decimal(val, st.precision)
                st.warnings.append("approximate_result es una aproximación decimal truncada; exact_result es exacto")
            # verificación por una segunda vía: el anillo de polinomios racionales (algoritmo distinto de arith)
            try:
                c2 = Ctx(); back = to_rf(ast, c2).cancel()
                v = "passed" if (back.n.is_const() and back.d.is_const() and back.n.const_value() / back.d.const_value() == val) else "failed"
            except Exception:
                v = "not_possible"
            return _finish_verification(r, v, "segunda_via_anillo_de_polinomios_racionales", r["exact_result"])
        except NotImplementedOperation:
            pass
    rf, conds = _canon_expr(ast, st)
    txt = rf_str(rf)
    r = _result(exact=txt, method="simplificacion_exacta", parsed=parsed)
    st.conditions += conds
    if not free_symbols(ast):
        r["approximate_result"] = _numeric_approx(txt, st)
    v = equivalent(ast, txt, st.assumptions)
    return _finish_verification(r, v, "evaluacion_en_puntos_exactos_del_original_vs_resultado")


def op_simplify(req, st, cancel=True, label="simplify"):
    ast = _text_ast(req["expression"])
    rf, conds = _canon_expr(ast, st, cancel)
    txt = rf_str(rf)
    st.conditions += conds; st.used(free_symbols(ast))
    r = _result(exact=txt, method="cancelacion_racional_exacta" if cancel else "expansion_polinomica_exacta", parsed={"canonical": to_str(ast)})
    v = equivalent(ast, txt, st.assumptions)
    return _finish_verification(r, v, "evaluacion_en_puntos_exactos_del_original_vs_resultado")


_MSG_INCOMPLETA = "Búsqueda de factores agotada: la irreducibilidad de algún factor NO está probada (el producto sí es correcto)"


def _factor_homogeneous(rest, vs):
    """Polinomio homogéneo en exactamente dos variables: se deshomogeneiza (b=1), se factoriza en Q[t] y se rehomogeneiza.
    Devuelve (escala, [(Poly, mult)], completo) o None si no aplica."""
    if len(vs) != 2: return None
    degs = {sum(e for _, e in m) for m in rest.t}
    if len(degs) != 1: return None
    a, b = vs
    q = rest.subs(b, 1)
    sc, facs, complete = u_factor(q.to_upoly(a))
    out = []
    for f, m in facs:
        k = len(f) - 1
        F = Poly()
        for j, cj in enumerate(f):
            if cj != 0: F = F + Poly.const(cj) * (Poly.var(a) ** j) * (Poly.var(b) ** (k - j))
        out.append((F, m))
    return sc, out, complete


def _factor_poly_str(p, warnings):
    if p.is_const(): return str(p.const_value()) if p.const_value().denominator == 1 else f"({p})"
    c, mono, rest = p.content_and_monomial()
    pieces = []
    for v, e in mono: pieces.append(v if e == 1 else f"{v}^{e}")
    if not rest.is_const():
        vs = rest.vars()
        if len(vs) == 1:
            sc, facs, complete = u_factor(rest.to_upoly(vs[0]))
            if not complete: warnings.append(_MSG_INCOMPLETA)
            c = c * sc
            for f, m in facs:
                fs = f"({u_to_poly(f, vs[0])})"
                pieces.append(fs if m == 1 else f"{fs}^{m}")
        else:
            hom = _factor_homogeneous(rest, vs)
            if hom is None:
                warnings.append("Polinomio multivariante no homogéneo: solo se extrae contenido y monomio común (factorización multivariante general no implementada)")
                pieces.append(f"({rest})")
            else:
                sc, facs, complete = hom
                if not complete: warnings.append(_MSG_INCOMPLETA)
                c = c * sc
                for f, m in facs:
                    fs = f"({f})"
                    pieces.append(fs if m == 1 else f"{fs}^{m}")
    else:
        c = c * rest.const_value()
    if c == 1 and len(pieces) == 1 and pieces[0].startswith("(") and pieces[0].endswith(")") and pieces[0].count("(") == 1:
        return pieces[0][1:-1]
    if c == 1 and pieces: pre = ""
    elif c == -1 and pieces: pre = "-"
    else: pre = (str(c) if c.denominator == 1 else f"({c})") + ("*" if pieces else "")
    return pre + "*".join(pieces)


def op_factor(req, st):
    ast = _text_ast(req["expression"])
    rf, conds = _canon_expr(ast, st, True)
    st.conditions += conds; st.used(free_symbols(ast))
    ns = _factor_poly_str(rf.n, st.warnings)
    if rf.d == Poly.const(1): txt = ns
    else: txt = f"({ns})/({_factor_poly_str(rf.d, st.warnings)})"
    r = _result(exact=txt, method="factorizacion_racional_Q", parsed={"canonical": to_str(ast)},
                data={"factorization_complete": _MSG_INCOMPLETA not in st.warnings})
    # verificación: re-expandir la forma factorizada (ruta independiente) y comparar con el original
    v = equivalent(ast, txt, st.assumptions)
    try:
        c2 = Ctx(); back = to_rf(_text_ast(txt), c2).cancel()
        same = (back.n * rf.d == rf.n * back.d)
        v = "passed" if same and v != "failed" else ("failed" if not same else v)
    except Exception:
        pass
    return _finish_verification(r, v, "reexpansion_de_la_forma_factorizada_y_evaluacion_en_puntos")


def _sol_entry(var, q, mult, precision=15):
    d = {"variable": var, "value": str(q), "multiplicity": mult}
    try:
        if q.b != 0 and q.d > 0: d["approximate"] = q_to_decimal(q, precision)
        else: d["approximate"] = format(q.to_float(), ".15g")
    except Exception:
        c = q.to_complex(); d["approximate"] = f"{c.real:.15g}{c.imag:+.15g}i"
    return d


def _msg_var_ausente(var, syms):
    pista = [x for x in syms if len(x) > 1 and var in x]
    m = f"La variable '{var}' no aparece en la ecuación"
    if pista:
        m += (f". Los identificadores de varias letras son símbolos únicos ({', '.join(pista)}): "
              "use * para multiplicar (por ejemplo a*t)")
    return m


def op_solve(req, st):
    text = req["expression"]
    eq_texts = [t.strip() for t in re.split(r"[;\n]", text) if t.strip()]
    variables = req.get("variables") or []
    if len(eq_texts) > 1 or len(variables) > 1:
        return _solve_system(eq_texts, variables, st)
    t = eq_texts[0]
    if "=" not in t: t += " = 0"
    lhs, rhs = S.split_equation(t)
    syms = sorted(free_symbols(lhs) | free_symbols(rhs))
    if not syms:
        # Enunciado sin incógnitas: se decide con aritmética exacta (no se inventa una incógnita)
        try:
            truth = eval_q(lhs, {}) == eval_q(rhs, {})
        except NotImplementedOperation as e:
            raise InvalidRequest("La ecuación no contiene incógnitas y no se pudo decidir con aritmética exacta: " + str(e))
        parsed = {"canonical": f"{to_str(lhs)} = {to_str(rhs)}"}
        if truth:
            return _finish_verification(_result("success_exact", exact="Verdadero", method="comparacion_aritmetica_exacta", parsed=parsed,
                                                data={"truth_value": True}), "passed", "evaluacion_exacta_de_ambos_miembros")
        return _finish_verification(_result("no_solution", exact="Falso", method="comparacion_aritmetica_exacta", parsed=parsed,
                                            data={"truth_value": False}), "passed", "evaluacion_exacta_de_ambos_miembros")
    var = variables[0] if variables else None
    if var is None:
        if len(syms) != 1: raise InvalidRequest("Indique la variable a resolver (hay varios símbolos)", {"symbols": syms})
        var = syms[0]
    if var not in syms: raise InvalidRequest(_msg_var_ausente(var, syms))
    st.used(set(syms))
    parsed = {"canonical": f"{to_str(lhs)} = {to_str(rhs)}", "variable": var}
    if len(syms) > 1:
        return _isolate(lhs, rhs, var, st, parsed)
    info = S.solve_one_variable(lhs, rhs, var, st.assumptions)
    st.conditions += info["conditions"] + list(dict.fromkeys(info["ctx"].ineqs)); st.warnings += info["ctx"].warnings
    if info["kind"] == "none":
        return _result("no_solution", method="analisis_polinomico_exacto", parsed=parsed, ver=("not_possible", None))
    if info["kind"] == "all":
        st.warnings.append("Identidad: se cumple para todo valor del dominio")
        r = _result("multiple_solutions", exact=f"{var} ∈ dominio", method="analisis_polinomico_exacto", parsed=parsed,
                    data={"solution_set": "todo el dominio"})
        return _finish_verification(r, "not_possible", None)
    kept, dropped, complete = S.finish_roots(info, var, st.assumptions, [])
    data = {"solutions": [_sol_entry(var, q, m, st.precision if st.precision_given else 15) for q, m in kept],
            "discarded": [{"value": str(q), "reason": why} for q, why in dropped],
            "domain": st.assumptions.get(var, "real")}
    for q, why in dropped:
        st.warnings.append(f"{var} = {q} descartada: {why}")
    if not complete:
        data["partial"] = True
        raise NotSolved("Ecuación de grado >= 3 sin factorización racional/cuadrática: no soportada por el motor propio",
                        {"partial_solutions": data["solutions"]})
    if not kept:
        return _result("no_solution", method="analisis_polinomico_exacto", parsed=parsed, data=data, ver=("not_possible", None))
    txt = ", ".join(f"{var} = {q}" for q, _ in kept)
    approx = None
    if any(q.b != 0 for q, _ in kept):
        approx = ", ".join(f"{var} ≈ {s['approximate']}" for s in data["solutions"])
    r = _result("success_exact", exact=txt, approx=approx, method="factorizacion_racional_y_formula_cuadratica", parsed=parsed, data=data)
    # verificación: sustitución exacta en la ecuación ORIGINAL (AST), no en el polinomio resuelto
    ok = True
    try:
        for q, _ in kept:
            if eval_q(lhs, {var: q}) != eval_q(rhs, {var: q}): ok = False
        verdict = "passed" if ok else "failed"
    except (NotImplementedOperation, MathDomainError):
        verdict = "not_possible"
    return _finish_verification(r, verdict, "sustitucion_exacta_en_la_ecuacion_original", txt)


def _isolate(lhs, rhs, var, st, parsed):
    res, ctx, c1 = S.isolate(lhs, rhs, var, st.assumptions)
    conds = condition_list(ctx.conds, st.assumptions) + list(dict.fromkeys(ctx.ineqs))
    st.conditions += conds; st.warnings += ctx.warnings
    txt = f"{var} = {rf_str(res)}"
    r = _result(exact=txt, method="despeje_literal_grado_1", parsed=parsed, data={"variable": var, "expression": rf_str(res)})
    v = S.verify_isolate(lhs, rhs, var, _text_ast(rf_str(res)), st.assumptions)
    return _finish_verification(r, v, "sustitucion_exacta_en_valores_racionales_aleatorios")


def _solve_system(eq_texts, variables, st):
    kind, data, eqs, vs, sol = S.solve_linear(eq_texts, variables or None, st.assumptions)
    st.used(set(vs))
    parsed = {"canonical": [f"{to_str(a)} = {to_str(b)}" for a, b in eqs], "variables": vs}
    if kind == "none":
        return _result("no_solution", method="eliminacion_gauss_jordan", parsed=parsed, data=data,
                       ver=("passed", "rango(A) < rango([A|b]): fila 0 = c con c != 0 en la forma escalonada reducida"))
    txt = ", ".join(f"{v} = {sol[v]}" for v in vs)
    data["solution"] = {v: str(sol[v]) for v in vs}
    # supuestos sobre la solución única
    if kind == "unique":
        for v, a in st.assumptions.items():
            if v in sol:
                x = sol[v].const_value()
                if (a == "positive" and x <= 0) or (a == "negative" and x >= 0) or (a == "nonzero" and x == 0) or (a == "integer" and x.denominator != 1):
                    return _result("no_solution", method="eliminacion_gauss_jordan", parsed=parsed, data=data,
                                   ver=("not_possible", None))
    else:
        for v, a in st.assumptions.items():
            if v in vs: st.conditions.append(f"{v} {'>' if a == 'positive' else '<' if a == 'negative' else '≠' if a == 'nonzero' else 'es'} {'0' if a in ('positive','negative','nonzero') else a}")
    status = "success_exact" if kind == "unique" else "multiple_solutions"
    if kind == "infinite": st.warnings.append("Infinitas soluciones: " + ", ".join(data["free_variables"]) + " libre(s)")
    r = _result(status, exact=txt, method="eliminacion_gauss_jordan", parsed=parsed, data=data)
    v = S.verify_linear(kind, eqs, vs, sol)
    return _finish_verification(r, v, "sustitucion_exacta_en_las_ecuaciones_originales")


def _var_for_calculus(ast, req):
    vs = req.get("variables") or []
    syms = sorted(free_symbols(ast))
    if vs: return vs[0]
    if len(syms) == 1: return syms[0]
    if not syms: raise InvalidRequest("La expresión no contiene variable")
    raise InvalidRequest("Indique la variable (hay varios símbolos)", {"symbols": syms})


def op_differentiate(req, st):
    ast = _text_ast(req["expression"]); var = _var_for_calculus(ast, req); order = req.get("order", 1)
    if var not in free_symbols(ast):
        st.warnings.append(f"La variable '{var}' no aparece en la expresión: la derivada es 0")
    d = calculus.differentiate(ast, var, order)
    txt, ctx = calculus.canon(d, st.assumptions)
    st.conditions += condition_list(ctx.conds, st.assumptions) + list(dict.fromkeys(ctx.ineqs)); st.warnings += ctx.warnings
    r = _result(exact=txt, method="reglas_de_derivacion_sobre_el_AST", parsed={"canonical": to_str(ast), "variable": var, "order": order})
    if order == 1:
        v = calculus.verify_derivative(ast, var, _text_ast(txt))
        m = "diferencias_finitas_centrales_de_orden_4_del_original"
    else:
        v, m = "not_possible", "verificacion de orden superior no implementada"
    return _finish_verification(r, v, m)


def op_integrate(req, st):
    ast = _text_ast(req["expression"]); var = _var_for_calculus(ast, req)
    F = calculus.integrate_indefinite(ast, var)
    parsed = {"canonical": to_str(ast), "variable": var}
    lo, hi = req.get("lower"), req.get("upper")
    if (lo is None) != (hi is None): raise InvalidRequest("Indique ambos límites 'lower' y 'upper'")
    if lo is None:
        txt, ctx = calculus.canon(F)
        # Condiciones de dominio del INTEGRANDO (hallazgo de Windows nº4: ∫1/(x^3+1) no informaba x ≠ -1). La primitiva vale en cada
        # intervalo donde el integrando es continuo; la constante C puede ser distinta en cada intervalo.
        try:
            _, ctx0 = calculus.canon(ast, st.assumptions)
            st.conditions += condition_list(ctx0.conds, st.assumptions) + list(dict.fromkeys(ctx0.ineqs))
            st.warnings += ctx0.warnings
        except MathDomainError:
            pass
        r = _result(exact=txt + " + C", method="integracion_simbolica_propia", parsed=parsed)
        v = calculus.verify_antiderivative(ast, var, _text_ast(txt))
        return _finish_verification(r, v, "diferencias_finitas_de_la_primitiva_vs_integrando")
    la, ha = _text_ast(lo), _text_ast(hi)
    a, b = const_value(la), const_value(ha)
    if a is None or b is None: raise InvalidRequest("Los límites deben ser constantes racionales")
    # el integrando debe ser finito en [a,b]: se comprueba con denominadores y evaluación
    ctxd = Ctx(); frf = to_rf(ast, ctxd).cancel()
    for p in ctxd.conds + ([frf.d] if not frf.d.is_const() else []):
        if p.vars() == [var]:
            from .solve import poly_roots
            roots, _ = poly_roots(p.to_upoly(var))
            for q, _m in roots:
                if q.is_real() and min(a, b) <= q.to_float() <= max(a, b):
                    raise NotImplementedOperation("El integrando tiene una singularidad en el intervalo: integral impropia no implementada")
    Fv = ("bin", "-", calculus.subs(F, var, ha), calculus.subs(F, var, la))
    try:
        txt, ctx = calculus.canon(Fv)
    except MathDomainError:
        # La primitiva no está definida en un extremo. Si el integrando sí es finito en el interior, es una integral
        # impropia (no implementada); si no lo es, el integrando no está definido en parte del intervalo.
        inside = 0
        for k in range(1, 10):
            try:
                v = eval_float(ast, {var: float(a) + (float(b) - float(a)) * k / 10})
                if not isinstance(v, complex) and math.isfinite(v): inside += 1
            except Exception:
                pass
        if inside == 9:
            raise NotImplementedOperation("Integral impropia (la primitiva no está definida en un extremo): no implementada")
        raise MathDomainError("El integrando no está definido en parte del intervalo de integración")
    r = _result(exact=txt, method="teorema_fundamental_del_calculo_con_primitiva_propia", parsed={**parsed, "lower": str(a), "upper": str(b)})
    ap = _numeric_approx(txt, st)
    r["approximate_result"] = ap
    try:
        simp = calculus.simpson(ast, var, float(a), float(b))
        exv = eval_float(_text_ast(txt), {})
        v = "passed" if abs(simp - exv) <= 1e-7 * (1 + abs(exv)) else "failed"
    except Exception:
        v = "not_possible"
    return _finish_verification(r, v, "cuadratura_de_Simpson_adaptativa_del_integrando_original")


def op_limit(req, st):
    ast = _text_ast(req["expression"]); var = _var_for_calculus(ast, req)
    if "point" not in req: raise InvalidRequest("Falta 'point' (racional, +oo o -oo)")
    point = calculus.parse_point(req["point"]); direction = req.get("direction", "both")
    if st.assumptions: st.warnings.append("assumptions no se aplican a límites en esta versión")
    res = calculus.limit(ast, var, point, direction)
    parsed = {"canonical": to_str(ast), "variable": var, "point": str(point), "direction": direction}
    if res["kind"] == "dne":
        return _result("no_solution", method="series_de_Laurent_exactas", parsed=parsed,
                       data={"reason": res["reason"], "lateral_limits": [("+inf" if s > 0 else "-inf") if k == "inf" else str(s) for k, s in res["sides"]]},
                       ver=("not_possible", None))
    exact = str(res["value"]) if res["kind"] == "finite" else ("oo" if res["sign"] > 0 else "-oo")
    r = _result(exact=exact, method="series_de_Laurent_exactas", parsed=parsed)
    v = calculus.verify_limit(ast, var, point, res, direction)
    return _finish_verification(r, v, "evaluacion_numerica_cerca_del_punto_del_original")


MATRIX_OPS = ("matrix_add", "matrix_sub", "matrix_mul", "matrix_transpose", "matrix_det", "matrix_inverse", "matrix_rank", "matrix_rref", "matrix_solve")


def _matrix_inputs(req):
    si = req.get("structured_input") or {}
    if not isinstance(si, dict): raise InvalidRequest("'structured_input' debe ser un objeto")
    extra = set(si) - {"a", "b"}
    if extra: raise InvalidRequest("Campos no reconocidos en structured_input: " + ", ".join(sorted(extra)))
    a = si.get("a", req.get("expression"))
    return a, si.get("b")


def op_matrix(req, st):
    """Álgebra lineal exacta (contrato 1.1). Reutiliza el módulo math_universe_linalg tal como se validó en la fase 9B."""
    from math_universe_linalg import api as LA
    op = req["operation"]
    op = "matrix_det" if op == "determinant" else op
    a, b = _matrix_inputs(req)
    txt, data, ok, how, warnings, status = LA.compute(op, a, b)
    st.warnings.extend(warnings)
    if not ok:
        raise VerificationFailed("La verificación independiente falló: el resultado no se entrega como válido",
                                 {"unverified_result": txt, "method": how})
    return _result(status, exact=txt, method="algebra_lineal_exacta_Q", ver=("passed", how), data=data, parsed={"operation": op})


OPS = {"parse": op_parse, "evaluate": op_evaluate, "simplify": op_simplify,
       "expand": lambda r, s: op_simplify(r, s, cancel=False), "factor": op_factor, "solve": op_solve,
       "differentiate": op_differentiate, "integrate": op_integrate, "limit": op_limit,
       "determinant": op_matrix, **{m: op_matrix for m in MATRIX_OPS}}


def _dispatch(req, st):
    op = req["operation"]
    if op == "ping": return {"data": {"pong": True}}
    if op == "capabilities": return {"data": capabilities()}
    if op == "determinant" or op in MATRIX_OPS:
        return op_matrix(req, st)
    if not req.get("expression"): raise InvalidRequest("Falta 'expression'")
    fn = OPS.get(op)
    if fn is None: raise NotImplementedOperation(f"Operación '{op}' no implementada")
    try:
        return fn(req, st)
    except (NotImplementedOperation, NotSolved) as e:
        if op in symbolic.SYMBOLIC_OPS and symbolic.available():
            return _sympy_fallback(req, st, op, e)
        if op in symbolic.SYMBOLIC_OPS and not symbolic.available():
            e.details = {**e.details, "sympy": "no disponible en este entorno"}
        raise


def _sympy_fallback(req, st, op, cause):
    ast = _text_ast(req["expression"])
    remaining = max(0.05, limits._deadline - time.perf_counter()) if limits._deadline else 10
    txt = limits.run_hard_timeout(symbolic.run, (op, ast, req.get("variables")), remaining)
    st.warnings.append("Resultado calculado por SymPy (respaldo experimental); sin procedimiento detallado")
    r = _result(exact=txt, method="sympy_respaldo_experimental", parsed={"canonical": to_str(ast)})
    # El resultado de SymPy pasa por la MISMA verificación independiente que los del motor propio.
    verdict, how = "not_possible", None
    try:
        if op in ("simplify", "expand", "factor"):
            verdict, how = equivalent(ast, txt, st.assumptions), "evaluacion_en_puntos"
        else:
            var = (req.get("variables") or sorted(free_symbols(ast)) or ["x"])[0]
            if op == "differentiate":
                verdict, how = calculus.verify_derivative(normalize(ast), var, _text_ast(txt)), "diferencias_finitas_del_original"
            elif op == "integrate":
                F = _text_ast(txt.replace("+ C", "").strip())
                verdict, how = calculus.verify_antiderivative(normalize(ast), var, F), "derivada_numerica_de_la_primitiva"
    except Exception:
        verdict, how = "not_possible", None
    if verdict == "not_possible": how = None
    return _finish_verification(r, verdict, how, txt)


def _apply_validity(resp):
    if jsonschema is not None:
        try:
            jsonschema.validate(resp, RESPONSE_SCHEMA)
        except jsonschema.ValidationError as e:  # nunca se emite una respuesta fuera de contrato
            return {"request_id": resp.get("request_id"), "api_version": API_VERSION, "status": "internal_error",
                    "elapsed_ms": resp.get("elapsed_ms", 0),
                    "error": {"code": "INTERNAL_ERROR", "message": "Respuesta fuera de contrato: " + e.message[:200], "details": {}}}
    return resp


def _norm_cond(c):
    """'abs(u) ≠ 0' ⇔ 'u ≠ 0' (mismo conjunto de puntos): se imprime la forma simple. Solo si el paréntesis de abs( abarca todo u."""
    if c.startswith("abs(") and c.endswith(") ≠ 0"):
        inner, depth = c[4:-5], 0
        for ch in inner:
            depth += (ch == "(") - (ch == ")")
            if depth < 0: return c
        if depth == 0: return inner + " ≠ 0"
    return c


def handle(req):
    t0 = time.perf_counter()
    rid = req.get("request_id") if isinstance(req, dict) else None
    resp = {"request_id": rid, "api_version": API_VERSION, "status": "success_exact", "conditions": [], "warnings": [],
            "verification": {"status": "not_performed", "method": None}}
    try:
        _validate(req)
        ev = req.get("engine_version")
        if ev is not None and ev.split(".")[0] != __version__.split(".")[0]:
            raise VersionMismatch("Versión de motor incompatible", {"expected": ev, "actual": __version__})
        limits.start(req.get("timeout_ms"))
        st = State(req)
        out = _dispatch(req, st)
        if st.assumptions and req["operation"] in ("differentiate", "integrate"):
            st.warnings.append("assumptions no se aplican a esta operación en esta versión (se ignoran)")
        resp["conditions"] = list(dict.fromkeys(_norm_cond(c) for c in st.conditions))
        resp["warnings"] = list(dict.fromkeys(st.warnings + out.pop("warnings", [])))
        resp.update(out)
    except EngineError as e:
        resp["status"] = STATUS_BY_CODE.get(e.code, "internal_error")
        resp["error"] = {"code": e.code, "message": e.message, "details": _jsonable(e.details)}
    except RecursionError:
        resp["status"] = "invalid_input"
        resp["error"] = {"code": "LIMIT_EXCEEDED", "message": "Anidamiento excesivo", "details": {}}
    except MemoryError:
        resp["status"] = "internal_error"
        resp["error"] = {"code": "LIMIT_EXCEEDED", "message": "Memoria insuficiente", "details": {}}
    except Exception as e:  # no filtrar trazas internas a la interfaz
        resp["status"] = "internal_error"
        resp["error"] = {"code": "INTERNAL_ERROR", "message": type(e).__name__, "details": {}}
    finally:
        limits.stop()
    resp["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    return _apply_validity(resp)


def _jsonable(x):
    try:
        json.dumps(x); return x
    except TypeError:
        return json.loads(json.dumps(x, default=str))
