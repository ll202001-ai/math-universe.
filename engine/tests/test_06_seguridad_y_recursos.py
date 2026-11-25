"""Seguridad (sin ejecución arbitraria) y límites de recursos."""
import ast as pyast, glob, json, os, subprocess, sys, time
import pytest
from conftest import call

PKG = os.path.join(os.path.dirname(__file__), "..", "math_universe_engine")


# ---------------- seguridad ----------------
@pytest.mark.parametrize("payload", [
    "__import__('os').system('echo hi')", "exec('1')", "eval('1+1')", "open('/etc/passwd').read()",
    "().__class__.__bases__", "x.__class__", "lambda: 1", "[i for i in range(3)]", "os.system('ls')",
    "1; import os", "`ls`", "$(ls)", "x; DROP TABLE a", "a.b", "{'a':1}", "\"x\"", "x = __import__",
])
def test_inyeccion_es_texto_no_codigo(payload):
    r = call(operation="evaluate", expression=payload)
    assert r["status"] in ("invalid_input", "unsupported", "domain_error"), r
    assert not os.path.exists("/tmp/mu_pwned")


def test_el_codigo_fuente_no_usa_eval_exec_compile_import_dinamico():
    prohibidos = {"eval", "exec", "compile", "__import__"}
    for f in glob.glob(os.path.join(PKG, "*.py")):
        tree = pyast.parse(open(f, encoding="utf-8").read())
        for node in pyast.walk(tree):
            if isinstance(node, pyast.Call) and isinstance(node.func, pyast.Name):
                assert node.func.id not in prohibidos, (f, node.func.id, node.lineno)
            if isinstance(node, pyast.Attribute) and node.attr in ("system", "popen"):
                pytest.fail(f"uso de {node.attr} en {f}")
    # sympify / parse_expr (que evalúan texto) tampoco
    for f in glob.glob(os.path.join(PKG, "*.py")):
        src = open(f, encoding="utf-8").read()
        assert "sympify(" not in src and "parse_expr(" not in src and "S(\"" not in src, f


def test_entradas_extranas_no_producen_error_interno():
    for s in ["\x00", "💥+1", "１+１", "2" + "​" + "+3", "x" * 4000, "-" * 100 + "1", "((((" * 30 + "1" + "))))" * 30]:
        r = call(operation="evaluate", expression=s)
        assert r["status"] != "internal_error", (s[:20], r)


def test_el_motor_no_leakea_trazas():
    r = call(operation="evaluate", expression="1/0")
    assert "Traceback" not in str(r) and "File \"" not in str(r)


# ---------------- límites de recursos ----------------
def test_timeout_ms_se_aplica_de_verdad():
    t = time.perf_counter()
    r = call(operation="expand", expression="(x+y+1)^100", timeout_ms=5)
    assert r["status"] == "timeout" and r["error"]["code"] == "TIMEOUT"
    assert time.perf_counter() - t < 5
    assert "exact_result" not in r or r["exact_result"] is None   # nunca resultado parcial como final


def test_el_plazo_no_contamina_la_solicitud_siguiente():
    call(operation="expand", expression="(x+y+1)^100", timeout_ms=5)
    r = call(operation="evaluate", expression="2+2")
    assert r["status"] == "success_exact" and r["exact_result"] == "4"


def test_timeout_por_defecto_existe():
    from math_universe_engine import limits
    assert limits.DEFAULT_TIMEOUT_MS > 0


def test_limite_de_terminos():
    r = call(operation="expand", expression="(a+b+c+d+e+f+g+h+1)^60", timeout_ms=60000)
    assert r["status"] in ("invalid_input", "timeout")
    if r["status"] == "invalid_input": assert r["error"]["code"] == "LIMIT_EXCEEDED"


def test_limite_de_exponente():
    assert call(operation="evaluate", expression="9^99999")["error"]["code"] == "LIMIT_EXCEEDED"
    assert call(operation="expand", expression="(x+1)^100000")["error"]["code"] == "LIMIT_EXCEEDED"
    assert call(operation="evaluate", expression="2^(2^20)")["status"] == "invalid_input"


def test_limite_de_factorial_y_anidamiento_y_longitud():
    assert call(operation="evaluate", expression="99999!")["error"]["code"] == "LIMIT_EXCEEDED"
    assert call(operation="evaluate", expression="(" * 500 + "1" + ")" * 500)["status"] == "invalid_input"
    assert call(operation="evaluate", expression="9" * 6000)["status"] == "invalid_input"


def test_hard_timeout_mata_el_proceso_hijo():
    from math_universe_engine import limits
    from math_universe_engine.errors import TimeoutExceeded
    t = time.perf_counter()
    with pytest.raises(TimeoutExceeded):
        limits.run_hard_timeout(time.sleep, (30,), 1.0)
    assert time.perf_counter() - t < 10


def test_hard_timeout_devuelve_resultado_si_termina():
    from math_universe_engine import limits
    assert limits.run_hard_timeout(sorted, ([3, 1, 2],), 10) == [1, 2, 3]


def test_factorizacion_larga_respeta_timeout():
    r = call(operation="factor", expression="x^7+x+1", timeout_ms=60000)       # irreducible sobre Q (7 ≢ 2 mod 3)
    assert r["status"] == "success_exact" and r["exact_result"] == "x^7 + x + 1" and r["data"]["factorization_complete"] is True


# ---------------- servidor JSON Lines ----------------
def _run_server(lines):
    code = "import sys;sys.path.insert(0,sys.argv[1]);from math_universe_engine.server import main;main()"
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    p = subprocess.run([sys.executable, "-I", "-c", code, root], input="\n".join(lines) + "\n", text=True, capture_output=True, timeout=60)
    return [json.loads(l) for l in p.stdout.splitlines()]


def test_servidor_jsonlines_una_respuesta_por_linea():
    out = _run_server([
        json.dumps({"request_id": 1, "operation": "simplify", "expression": "(x^2-1)/(x-1)"}),
        "esto no es json",
        json.dumps({"request_id": 3, "operation": "solve", "expression": "2x+y=5; x-y=1"}),
        json.dumps({"request_id": 4, "operation": "evaluate", "expression": "1/0"}),
    ])
    assert [o["status"] for o in out] == ["success_exact", "invalid_input", "success_exact", "domain_error"]
    assert out[0]["conditions"] == ["x ≠ 1"] and out[2]["exact_result"] == "x = 2, y = 1"


def test_servidor_linea_demasiado_larga():
    out = _run_server([json.dumps({"operation": "evaluate", "expression": "1+" * 80000 + "1"})])
    assert out[0]["status"] == "invalid_input" and out[0]["error"]["code"] == "LIMIT_EXCEEDED"


def test_servidor_utf8_aunque_la_consola_sea_cp1252():
    """En Windows la codificación por defecto de stdin/stdout suele ser cp1252: el canal debe seguir siendo UTF-8."""
    import subprocess, sys, os, json
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    req = json.dumps({"request_id": 1, "operation": "simplify", "expression": "(x^2−1)/(x−1)"}, ensure_ascii=False) + "\n"   # incluye el signo menos Unicode
    p = subprocess.run([sys.executable, os.path.join(root, "run_server.py")], input=req.encode("utf-8"), capture_output=True, env=env, timeout=30)
    out = json.loads(p.stdout.decode("utf-8"))
    assert out["status"] == "success_exact" and out["conditions"] == ["x ≠ 1"], (out, p.stderr[:300])
