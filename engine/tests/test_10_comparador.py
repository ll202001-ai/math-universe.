"""Prueba la MECÁNICA y la AUSENCIA DE SESGO del comparador con un adaptador falso que NO usa SymPy.
(El adaptador falso evalúa con el evaluador del motor: es circular a propósito, solo se prueba la lógica de clasificación.)
Esto NO sustituye la comparación real con SymPy (tools/validar_todo.py la ejecuta donde SymPy está instalado)."""
import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import audit.comparar_sympy as cmp
from math_universe_engine.parser import parse
from math_universe_engine.ast_tools import normalize, eval_float
from math_universe_engine import calculus


class FakeAdapter:
    tol = 1e-9                                       # coma flotante: se ensancha la tolerancia
    simbolico = True

    def versions(self): return {"fake": "0"}
    def puntos(self): return cmp.PUNTOS
    def parse(self, t): return normalize(parse(t))
    def num(self, ast, env):
        try:
            v = eval_float(ast, {k: float(x) for k, x in env.items()})
        except Exception as e:
            raise ZeroDivisionError(str(e))
        if isinstance(v, float) and v != v: raise ZeroDivisionError("nan")
        if isinstance(v, complex) and abs(v.imag) < 1e-12: v = v.real
        return v
    def derivada(self, ast, orden=1): return normalize(calculus.differentiate(ast, "x", orden))
    def misma_repr(self, a, b): return a == b
    def igual_simbolico(self, a, b): return self.simbolico
    def indefinida_en(self, text, k):
        try: self.num(self.parse(text), {"x": k}); return False
        except ZeroDivisionError: return True
    def no_derivable_en(self, text, k):
        ast = self.parse(text)
        return cmp.no_derivable_por_cocientes(lambda t: self.num(ast, {"x": t}), k, (cmp.Fraction(1, 10**4), cmp.Fraction(1, 10**6)))


def resp(**k):
    base = {"status": "success_exact", "exact_result": None, "approximate_result": None, "conditions": [], "warnings": [],
            "verification": {"status": "passed", "method": "x"}, "data": {}}
    base.update(k); return base


AD = FakeAdapter()
def A(t): return AD.parse(t)


def ref_expr(t, sing=None, texto=None):
    return {"tipo": "expr", "obj": A(t), "texto": texto or t, "singularidades": sing}


# ---------- lo básico ----------
def test_equivalente_y_diferencia():
    case = {"op": "simplify", "expr": "(x^2-1)/(x-1)", "id": 0}
    v, det = cmp.clasificar(case, resp(exact_result="1+x", conditions=["x ≠ 1"]), ref_expr("x+1", [1.0]), AD)
    assert v == "EQUIVALENTE" and "dominio coincide" in det
    v, det = cmp.clasificar(case, resp(exact_result="x+2", conditions=["x ≠ 1"]), ref_expr("x+1", [1.0]), AD)
    assert v == "DIFERENCIA" and "x=" in det


# ---------- anti-sesgo ----------
def test_no_se_declara_equivalente_sin_puntos_comparados():
    """Si ninguna expresión está definida en los puntos (todo indefinido), NO es 'equivalente': es no concluyente."""
    case = {"op": "simplify", "expr": "ln(-1-x^2)", "id": 1}
    v, det = cmp.clasificar(case, resp(exact_result="ln(-1-x^2)"), ref_expr("ln(-1-x^2)"), AD)
    assert v == "NO_CONCLUYENTE", (v, det)


def test_definido_en_un_solo_lado_es_diferencia_de_dominio():
    case = {"op": "simplify", "expr": "x", "id": 2}
    v, det = cmp.clasificar(case, resp(exact_result="sqrt(x)"), ref_expr("x"), AD)         # sqrt(x) indefinido en puntos negativos (en este adaptador)
    assert v in ("DIFERENCIA", "DIFERENCIA_DOMINIO")


def test_dominio_incompleto_del_motor_se_detecta():
    case = {"op": "simplify", "expr": "(x^2-1)/(x-1)", "id": 3}
    v, det = cmp.clasificar(case, resp(exact_result="x+1", conditions=[]), ref_expr("x+1", [1.0]), AD)
    assert v == "DIFERENCIA_DOMINIO" and "[1.0]" in det


def test_dominio_con_restricciones_no_puntuales_se_declara_no_comparado():
    case = {"op": "simplify", "expr": "ln(x)", "id": 4}
    v, det = cmp.clasificar(case, resp(exact_result="ln(x)", conditions=["x > 0"]), ref_expr("ln(x)", []), AD)
    assert v in ("IDENTICO", "EQUIVALENTE") and "no comparado" in det


def test_confirmacion_simbolica_negativa_es_diferencia():
    class Ad2(FakeAdapter): simbolico = False
    case = {"op": "simplify", "expr": "x", "id": 5}
    v, det = cmp.clasificar(case, resp(exact_result="x"), ref_expr("x+0*x"), Ad2())
    assert v == "DIFERENCIA" and "equals" in det


def test_convencion_solo_si_coincide_exactamente():
    case = {"op": "simplify", "expr": "(-8)^(1/3)", "id": 6}
    ref = {"tipo": "expr", "obj": A("1+sqrt(3)*0"), "texto": "1 + sqrt(3)*I", "singularidades": None}

    class Ad3(FakeAdapter):
        def num(self, ast, env): return complex(1.0, 3 ** 0.5) if ast == ref["obj"] and not env else super().num(ast, env)
    v, _ = cmp.clasificar(case, resp(exact_result="-2"), ref, Ad3())
    assert v == "CONVENCION_DOCUMENTADA"
    v, _ = cmp.clasificar(case, resp(exact_result="-3"), ref, Ad3())          # el motor dio otra cosa: NO es la convención documentada
    assert v != "CONVENCION_DOCUMENTADA"


def test_sin_referencia_no_se_confunde_con_acuerdo():
    case = {"op": "integrate", "expr": "x", "id": 7}
    v, det = cmp.clasificar(case, resp(exact_result="x^2/2 + C"), {"tipo": "no_resuelto"}, AD)
    assert v == "SIN_REFERENCIA_SYMPY" and "NO validado" in det
    v, _ = cmp.clasificar(case, resp(status="unsupported"), {"tipo": "no_resuelto"}, AD)
    assert v == "AMBOS_NO_SOPORTAN"


def test_limitacion_del_motor_y_errores_del_motor():
    case = {"op": "integrate", "expr": "x", "id": 8}
    ref = {"tipo": "primitiva", "obj": A("x^2/2"), "texto": "x**2/2", "integrando": A("x")}
    v, _ = cmp.clasificar(case, resp(status="unsupported", error={"message": "no"}), ref, AD)
    assert v == "LIMITACION_MOTOR"
    v, _ = cmp.clasificar(case, resp(status="internal_error", error={"message": "boom"}), ref, AD)
    assert v == "DIFERENCIA"                                                   # un error interno NO se esconde como limitación


def test_primitiva_se_compara_con_el_integrando_no_solo_con_sympy():
    case = {"op": "integrate", "expr": "x", "id": 9}
    ref = {"tipo": "primitiva", "obj": A("x^2/2"), "texto": "x**2/2", "integrando": A("x")}
    v, _ = cmp.clasificar(case, resp(exact_result="x^2/2 + 7 + C"), ref, AD)       # difiere en una constante: válido
    assert v in ("IDENTICO", "EQUIVALENTE")
    v, det = cmp.clasificar(case, resp(exact_result="x^2/3 + C"), ref, AD)         # derivada ≠ integrando: error del motor
    assert v == "DIFERENCIA" and "integrando" in det


def test_solve_conjunto_y_sistemas():
    case = {"op": "solve", "expr": "x^2-4=0", "id": 10}
    r = resp(exact_result="x = -2, x = 2", data={"solutions": [{"value": "-2"}, {"value": "2"}]})
    v, _ = cmp.clasificar(case, r, {"tipo": "conjunto", "valores": [-2 + 0j, 2 + 0j], "texto": "{-2, 2}"}, AD)
    assert v == "EQUIVALENTE"
    v, _ = cmp.clasificar(case, r, {"tipo": "conjunto", "valores": [2 + 0j], "texto": "{2}"}, AD)
    assert v == "DIFERENCIA"
    cs = {"op": "solve", "expr": "x+y=2; x-y=0", "id": 11, "sistema": True}
    rs = resp(exact_result="x = 1, y = 1", data={"solution": {"x": "1", "y": "1"}})
    v, _ = cmp.clasificar(cs, rs, {"tipo": "sistema", "valores": {"x": 1 + 0j, "y": 1 + 0j}, "texto": "{(1, 1)}"}, AD)
    assert v == "EQUIVALENTE"
    v, _ = cmp.clasificar(cs, rs, {"tipo": "sistema", "valores": {"x": 1 + 0j, "z": 1 + 0j}, "texto": "..."}, AD)
    assert v == "DIFERENCIA"


def test_error_del_propio_comparador_no_se_oculta():
    case = {"op": "simplify", "expr": "x", "id": 12}
    v, det = cmp.clasificar(case, resp(exact_result="x +* 2"), ref_expr("x"), AD)     # texto no analizable
    assert v == "ERROR_COMPARADOR"


def test_hallazgos_y_aceptables_son_disjuntos():
    assert not set(cmp.HALLAZGOS) & set(cmp.OK_VEREDICTOS)


def test_corpus_bien_formado():
    C = cmp.corpus()
    assert len(C) >= 150 and len({c["id"] for c in C}) == len(C)
    assert {c["op"] for c in C} >= {"simplify", "expand", "factor", "solve", "differentiate", "integrate", "limit"}
    for c in C[:40]:
        r = cmp._motor(c)                       # el lado del motor se puede ejecutar sin SymPy
        assert r["status"] in ("success_exact", "multiple_solutions", "no_solution", "unsupported", "domain_error", "invalid_input")


def test_pipeline_completo_con_adaptador_falso(tmp_path):
    """Ejecuta ejecutar() de extremo a extremo (sin procesos) con una referencia 'perfecta' derivada del propio motor:
    comprueba que el informe se produce y que ningún caso queda sin clasificar."""
    class AdRef(FakeAdapter):
        def reference(self, case):
            return {"tipo": "no_resuelto"}                       # sin referencia: todo debe quedar como SIN_REFERENCIA o AMBOS_NO_SOPORTAN
    cnt, filas = cmp.ejecutar(AdRef(), str(tmp_path / "o.json"), con_procesos=False)
    assert sum(cnt.values()) == len(cmp.corpus())
    assert set(cnt) <= {"SIN_REFERENCIA_SYMPY", "AMBOS_NO_SOPORTAN"}
    assert (tmp_path / "o.json").exists()


# ======================= hallazgos de la validación en Windows nº3 (docs/HALLAZGOS_WINDOWS_3.md) =======================
def test_el_motor_se_ejecuta_sin_respaldo_sympy_en_la_comparacion(monkeypatch):
    """Sesgo corregido: con el respaldo activo, 'motor vs SymPy' comparaba SymPy consigo mismo (sqrt(x), tan(x))."""
    visto = {}
    def falso_handle(q):
        visto["env"] = os.environ.get("MATH_UNIVERSE_DISABLE_SYMPY"); return resp()
    monkeypatch.setattr(cmp, "handle", falso_handle)
    monkeypatch.delenv("MATH_UNIVERSE_DISABLE_SYMPY", raising=False)
    cmp._motor({"op": "simplify", "expr": "x"})
    assert visto["env"] == "1"
    assert "MATH_UNIVERSE_DISABLE_SYMPY" not in os.environ          # se restaura el entorno
    monkeypatch.setenv("MATH_UNIVERSE_DISABLE_SYMPY", "0")
    cmp._motor({"op": "simplify", "expr": "x"})
    assert os.environ["MATH_UNIVERSE_DISABLE_SYMPY"] == "0"


def test_singularidad_evitable_perdida_por_sympy_se_acepta_solo_con_evidencia_independiente():
    # x/x: SymPy lo reduce a 1 al construirlo y pierde x≠0; el motor lo conserva. La función ORIGINAL es indefinida en 0 -> el motor tiene razón.
    case = {"op": "simplify", "expr": "x/x", "id": 20}
    v, det = cmp.clasificar(case, resp(exact_result="1", conditions=["x ≠ 0"]), ref_expr("1", []), AD)
    assert v == "SYMPY_AMPLIA_DOMINIO" and "confirmado" in det, (v, det)
    # el motor NO puede inventar restricciones: x ≠ 3 para 'x' no tiene respaldo -> hallazgo
    case = {"op": "simplify", "expr": "x", "id": 21}
    v, _ = cmp.clasificar(case, resp(exact_result="x", conditions=["x ≠ 3"]), ref_expr("x", []), AD)
    assert v == "DIFERENCIA_DOMINIO"
    # y no puede OMITIR una singularidad que SymPy sí ve (sigue siendo hallazgo)
    case = {"op": "simplify", "expr": "1/(x-2)", "id": 22}
    v, _ = cmp.clasificar(case, resp(exact_result="1/(x-2)", conditions=[]), ref_expr("1/(x-2)", [2.0]), AD)
    assert v == "DIFERENCIA_DOMINIO"


class _AdSigno(FakeAdapter):
    """SymPy simulado para d|x|/dx: sign(x) (con sign(0)=0) frente al x/|x| del motor."""
    por_ramas = True
    def num(self, ast, env):
        if ast == "SIGN":
            x = float(env["x"]); return float((x > 0) - (x < 0))
        return super().num(ast, env)
    def igual_simbolico(self, a, b): return False                       # equals global falla por x=0
    def igual_simbolico_por_ramas(self, a, b): return self.por_ramas


def test_derivada_de_abs_sign_vs_x_sobre_abs():
    case = {"op": "differentiate", "expr": "abs(x)", "id": 23}
    ref = {"tipo": "expr", "obj": "SIGN", "texto": "sign(x)"}
    r = resp(exact_result="x/abs(x)", conditions=["x ≠ 0"])
    v, det = cmp.clasificar(case, r, ref, _AdSigno())
    assert v == "SYMPY_AMPLIA_DOMINIO", (v, det)                         # |x| no es derivable en 0 (cocientes -1 y +1)
    # si NO se demuestra la igualdad en x>0 y x<0, la discrepancia simbólica sigue siendo DIFERENCIA (no se esconde)
    class SinPrueba(_AdSigno): por_ramas = None
    v, det = cmp.clasificar(case, r, ref, SinPrueba())
    assert v == "DIFERENCIA" and "equals" in det
    # función SÍ derivable en 0 y motor que la excluye: no hay evidencia -> DIFERENCIA_DOMINIO
    case2 = {"op": "differentiate", "expr": "x^2", "id": 24}
    v, _ = cmp.clasificar(case2, resp(exact_result="x/abs(x)", conditions=["x ≠ 0"]), ref, _AdSigno())
    assert v in ("DIFERENCIA", "DIFERENCIA_DOMINIO")


def test_cocientes_incrementales_distinguen_punto_anguloso_de_punto_liso():
    f_abs = lambda t: abs(float(t))
    f_cuad = lambda t: float(t) ** 2
    hs = (cmp.Fraction(1, 10**4), cmp.Fraction(1, 10**6))
    assert cmp.no_derivable_por_cocientes(f_abs, cmp.Fraction(0), hs) is True
    assert cmp.no_derivable_por_cocientes(f_cuad, cmp.Fraction(0), hs) is False
    assert cmp.no_derivable_por_cocientes(f_abs, cmp.Fraction(2), hs) is False


def test_ecuacion_constante_verdadera_es_convencion_documentada_solo_sin_incognita():
    ref = {"tipo": "todo", "texto": "todo el dominio"}
    r = resp(exact_result="Verdadero")
    v, _ = cmp.clasificar({"op": "solve", "expr": "5=5", "id": 25}, r, ref, AD)
    assert v == "CONVENCION_DOCUMENTADA"
    v, _ = cmp.clasificar({"op": "solve", "expr": "pi=pi", "id": 26}, r, ref, AD)
    assert v == "CONVENCION_DOCUMENTADA"
    # con incógnita el motor DEBE devolver multiple_solutions: 'Verdadero' ahí sería una diferencia real
    v, _ = cmp.clasificar({"op": "solve", "expr": "x=x", "id": 27}, r, ref, AD)
    assert v == "DIFERENCIA"
    v, _ = cmp.clasificar({"op": "solve", "expr": "x=x", "id": 28}, resp(status="multiple_solutions", exact_result="x ∈ dominio"), ref, AD)
    assert v == "EQUIVALENTE"


def test_error_del_comparador_conserva_la_causa():
    class Roto(FakeAdapter):
        def num(self, ast, env): raise TypeError("cannot determine truth value of Relational")
    case = {"op": "simplify", "expr": "x", "id": 29}
    v, det = cmp.clasificar(case, resp(exact_result="x"), ref_expr("x"), Roto())
    assert v == "ERROR_COMPARADOR" and "Relational" in det and "traza" in det


def test_errores_del_comparador_siguen_siendo_hallazgos():
    assert "ERROR_COMPARADOR" in cmp.HALLAZGOS and "SYMPY_AMPLIA_DOMINIO" not in cmp.HALLAZGOS
