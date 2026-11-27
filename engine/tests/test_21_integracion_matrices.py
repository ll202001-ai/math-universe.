"""Integración de las operaciones de matrices en el dispatcher (contrato 1.1): contrato, golden, errores, servidor, H-1, NumPy."""
import glob, json, os, subprocess, sys, time
from fractions import Fraction
import pytest
from math_universe_engine.dispatcher import handle, MATRIX_OPS, API_VERSION, REQUEST_SCHEMA, RESPONSE_SCHEMA, capabilities

ENGINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN = sorted(glob.glob(os.path.join(ENGINE, "tests", "golden", "matrices", "*.json")))


def M(op, a, b=None, **k):
    si = {"a": a}
    if b is not None: si["b"] = b
    return handle({"operation": op, "structured_input": si, **k})


# ---- valores conocidos comprobados a mano (independientes de los golden) ----
def test_valores_conocidos():
    assert M("matrix_det", [[1, 2], [3, 4]])["exact_result"] == "-2"
    assert M("matrix_det", [[2, 1, 0], [1, 3, 1], [0, 1, 4]])["exact_result"] == "18"
    assert M("matrix_mul", [[1, 2], [3, 4]], [[0, 1], [1, 0]])["exact_result"] == "[[2, 1], [4, 3]]"
    assert M("matrix_inverse", [[2, 1], [1, 1]])["exact_result"] == "[[1, -1], [-1, 2]]"
    assert M("matrix_rank", [[1, 2, 3], [2, 4, 6], [1, 0, 1]])["exact_result"] == "2"
    assert M("matrix_transpose", [[1, 2, 3], [4, 5, 6]])["exact_result"] == "[[1, 4], [2, 5], [3, 6]]"
    r = M("matrix_solve", [[2, 1], [1, 3]], [[3], [5]])
    assert r["status"] == "success_exact" and r["data"]["particular"] == ["4/5", "7/5"]     # 2x+y=3, x+3y=5
    assert M("matrix_add", "[[1/2,1/3]]", "[[1/2,2/3]]")["exact_result"] == "[[1, 1]]"


def test_alias_determinant_y_expression():
    a = handle({"operation": "determinant", "expression": "[[1,2],[3,4]]"})
    b = M("matrix_det", [[1, 2], [3, 4]])
    assert a["status"] == "success_exact" and a["exact_result"] == b["exact_result"] == "-2"


@pytest.mark.parametrize("op", MATRIX_OPS)
def test_toda_respuesta_cumple_el_esquema_y_viene_verificada(op):
    import jsonschema
    b = {"matrix_solve": [[1], [0]]}.get(op, [[1, 0], [0, 1]])
    r = M(op, [[2, 1], [1, 3]], b if op in ("matrix_add", "matrix_sub", "matrix_mul", "matrix_solve") else None, request_id=7)
    jsonschema.validate(r, RESPONSE_SCHEMA)
    assert r["api_version"] == "1.3" == API_VERSION and r["request_id"] == 7
    assert r["status"] in ("success_exact", "multiple_solutions"), r
    assert r["verification"]["status"] == "passed" and r["verification"]["method"]


@pytest.mark.parametrize("path", GOLDEN, ids=lambda p: os.path.basename(p))
def test_golden(path):
    from tools.generar_golden import respuesta_normalizada
    g = json.load(open(path, encoding="utf-8"))
    assert respuesta_normalizada(g["request"]) == g["expected"]


def test_hay_golden_para_las_nueve_operaciones():
    ops = {json.load(open(p, encoding="utf-8"))["request"]["operation"] for p in GOLDEN}
    assert set(MATRIX_OPS) | {"determinant"} <= ops


# ---- errores: nunca éxito falso ----
@pytest.mark.parametrize("req,status,code", [
    ({"operation": "matrix_add", "structured_input": {"a": [[1, 2]], "b": [[1], [2]]}}, "invalid_input", None),
    ({"operation": "matrix_inverse", "structured_input": {"a": [[1, 2], [2, 4]]}}, "domain_error", "DOMAIN_ERROR"),
    ({"operation": "matrix_inverse", "structured_input": {"a": [[1, 2, 3], [4, 5, 6]]}}, "invalid_input", None),     # no cuadrada: error de forma de la entrada
    ({"operation": "matrix_det", "structured_input": {"a": [["x", 1], [2, 3]]}}, "invalid_input", "PARSE_ERROR"),
    ({"operation": "matrix_det", "structured_input": {"a": [[1e999999999]]}}, "invalid_input", None),
    ({"operation": "matrix_det"}, "invalid_input", "INVALID_REQUEST"),
    ({"operation": "matrix_add", "structured_input": {"a": [[1]]}}, "invalid_input", "INVALID_REQUEST"),
    ({"operation": "matrix_det", "structured_input": {"a": [[1]], "c": 1}}, "invalid_input", None),
    ({"operation": "matrix_det", "structured_input": {"a": []}}, "invalid_input", None),
    ({"operation": "matrix_det", "structured_input": {"a": [[1, 2], [3]]}}, "invalid_input", None),
    ({"operation": "matrix_det", "structured_input": "[[1]]"}, "invalid_input", None),
])
def test_errores_controlados(req, status, code):
    r = handle(req)
    assert r["status"] == status, r
    assert r.get("exact_result") is None and r["verification"]["status"] != "passed"
    if code: assert r["error"]["code"] == code


def test_dimension_maxima_y_plazo():
    n = 41
    r = M("matrix_det", [[1 if i == j else 0 for j in range(n)] for i in range(n)])
    assert r["status"] == "invalid_input" and r["error"]["code"] in ("LIMIT_EXCEEDED", "INVALID_REQUEST")
    import random
    rng = random.Random(1)
    big = [[rng.randint(-99, 99) for _ in range(40)] for _ in range(40)]
    r = M("matrix_inverse", big, timeout_ms=1)
    assert r["status"] in ("timeout", "success_exact")         # 1 ms: normalmente agota el plazo; si no, el resultado debe estar verificado
    if r["status"] == "success_exact": assert r["verification"]["status"] == "passed"


def test_verificacion_fallida_no_entrega_resultado(monkeypatch):
    import math_universe_linalg.api as A
    monkeypatch.setattr(A.checks, "check_det", lambda a, d: False)
    r = M("matrix_det", [[1, 2], [3, 4]])
    assert r["status"] == "internal_error" and r["error"]["code"] == "VERIFICATION_FAILED" and r.get("exact_result") is None
    assert "unverified_result" in r["error"]["details"]


# ---- H-1 ----
@pytest.mark.parametrize("e", ["1e999999999", "1e100000", "1e20000", "1e1001"])
def test_h1_literales_gigantes_no_cuelgan(e):
    t = time.perf_counter()
    r = handle({"operation": "evaluate", "expression": e, "timeout_ms": 2000})
    assert time.perf_counter() - t < 1.5
    assert r["status"] == "invalid_input" and r["error"]["code"] == "LIMIT_EXCEEDED"


def test_h1_no_rompe_notacion_cientifica_normal():
    assert handle({"operation": "evaluate", "expression": "2.5e3+1"})["exact_result"] == "2501"
    assert handle({"operation": "evaluate", "expression": "1e-3"})["exact_result"] == "1/1000"


# ---- contrato y compatibilidad ----
def test_capabilities_y_esquema():
    c = capabilities()
    assert c["engine_version"] == "0.7.0" and c["api_version"] == "1.3" and c["modules"]["matrices_algebra_lineal"].startswith("estable")
    assert set(MATRIX_OPS) <= set(REQUEST_SCHEMA["properties"]["operation"]["enum"])


def test_cliente_de_la_api_1_0_sigue_funcionando():
    r = handle({"operation": "evaluate", "expression": "1/3+1/6", "engine_version": "0.3.0"})   # mayor igual => compatible
    assert r["status"] == "success_exact" and r["exact_result"] == "1/2"
    assert handle({"operation": "differentiate", "expression": "x^3", "variables": ["x"]})["exact_result"] == "3*x^2"


def test_servidor_json_lines_con_matrices():
    reqs = [{"operation": "ping", "request_id": 1}, {"operation": "matrix_det", "request_id": 2, "structured_input": {"a": [[1, 2], [3, 4]]}},
            {"operation": "matrix_solve", "request_id": 3, "structured_input": {"a": [[1, 1], [1, -1]], "b": [[3], [1]]}}]
    entrada = "\n".join(json.dumps(r) for r in reqs) + "\n"
    out = subprocess.run([sys.executable, "-I", os.path.join(ENGINE, "run_server.py")], input=entrada, capture_output=True, text=True,
                         encoding="utf-8", timeout=60, env={**os.environ, "PYTHONUTF8": "1"})
    assert out.returncode == 0, out.stderr
    rs = [json.loads(l) for l in out.stdout.splitlines()]
    assert [r["request_id"] for r in rs] == [1, 2, 3]
    assert rs[1]["exact_result"] == "-2" and rs[2]["data"]["particular"] == ["2", "1"]


# ---- oráculo NumPy (solo pruebas) a través del dispatcher ----
def test_contra_numpy_via_dispatcher():
    np = pytest.importorskip("numpy")
    import random
    rng = random.Random(2024)
    n_ok = 0
    for _ in range(60):
        n = rng.randint(1, 5)
        A = [[rng.randint(-9, 9) for _ in range(n)] for _ in range(n)]
        Af = np.array(A, dtype=float)
        d = M("matrix_det", A)
        assert d["status"] == "success_exact"
        assert abs(float(Fraction(d["exact_result"])) - np.linalg.det(Af)) <= 1e-6 * max(1, abs(np.linalg.det(Af)))
        assert int(M("matrix_rank", A)["exact_result"]) == np.linalg.matrix_rank(Af)
        if abs(np.linalg.det(Af)) > 0.5 and np.linalg.cond(Af) < 1e6:
            inv = M("matrix_inverse", A)
            assert inv["status"] == "success_exact"
            got = np.array([[float(Fraction(x)) for x in row] for row in inv["data"]["matrix"]])
            assert np.allclose(got, np.linalg.inv(Af), atol=1e-8); n_ok += 1
    assert n_ok >= 20
