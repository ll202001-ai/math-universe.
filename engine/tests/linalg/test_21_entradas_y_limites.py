import time, pytest
from fractions import Fraction
from _soporte import run, Matrix
import math_universe_linalg as L
from math_universe_linalg.matrix import parse_matrix_text, entry


def test_texto_con_fracciones_decimales_y_expresiones():
    m = parse_matrix_text("[[1, 1/2],[0.25, (1+2)/6]]")
    assert m.to_strings() == [["1", "1/2"], ["1/4", "1/2"]]
    assert entry("1e3") == 1000 and entry("2.5e-2") == Fraction(1, 40)
    assert entry("-3") == -3 and entry("2.5") == Fraction(5, 2) and entry(0.1) == Fraction(1, 10) and entry("2*3") == 6


@pytest.mark.parametrize("malo", ["[[1,2],[3]]", "[[1,x]]", "[1,2]", "[[1,2],[3,4]", "[[]]", "", "[[1/0]]", "[[sqrt(2)]]", "[[pi]]",
                                  "[[1,2]],[[3,4]]", "[[1e999999999]]", "[[2*1e999999999]]", "[[1E+100000]]", "[[" + "9" * 61 + "]]", "[[__import__('os')]]"])
def test_entradas_invalidas_se_rechazan_sin_ejecutar_nada(malo):
    r = run("matrix_det", malo)
    assert r["status"] in ("invalid_input", "domain_error"), (malo, r["status"])
    assert r["exact_result"] is None


def test_no_se_aceptan_simbolos_ni_irracionales_y_el_mensaje_lo_dice():
    r = run("matrix_det", "[[sqrt(2), 1],[1, 1]]")
    assert r["status"] == "invalid_input" and "constante racional" in r["error"]["message"]


def test_tipos_prohibidos():
    for bad in ([[True, 1]], [[float("nan"), 1]], [[float("inf")]], [[None]], [[object()]]):
        assert run("matrix_rank", bad)["status"] == "invalid_input"


def test_vector_plano_es_columna():
    r = run("matrix_solve", [[1, 1], [1, -1]], [3, 1])
    assert r["data"]["particular"] == ["2", "1"]


def test_dimension_maxima():
    assert run("matrix_rank", [[1] * 41])["status"] == "invalid_input"
    assert run("matrix_rank", [[1]] * 41)["status"] == "invalid_input"
    assert run("matrix_rank", [[1] * 40])["status"] == "success_exact"


def test_operacion_desconocida_y_falta_de_argumentos():
    assert run("matrix_eigen", [[1]])["status"] == "unsupported"
    assert run("matrix_mul", [[1]])["status"] == "invalid_input"
    assert run("matrix_det")["status"] == "invalid_input"


def test_plazo_cooperativo_corta_calculos_largos():
    import random
    rng = random.Random(1)
    big = [[rng.randint(-9, 9) for _ in range(40)] for _ in range(40)]
    t0 = time.perf_counter()
    r = run("matrix_inverse", big, timeout_ms=1)
    assert r["status"] == "timeout" and time.perf_counter() - t0 < 5


def test_matriz_grande_exacta_en_tiempo_razonable():
    import random
    rng = random.Random(2)
    n = 20
    A = Matrix([[rng.randint(-9, 9) for _ in range(n)] for _ in range(n)])
    t0 = time.perf_counter()
    r = run("matrix_inverse", A, timeout_ms=60000)
    assert r["status"] in ("success_exact", "domain_error") and time.perf_counter() - t0 < 30
    if r["status"] == "success_exact": assert r["verification"]["status"] == "passed"


def test_resultados_son_json_serializables():
    import json
    for op, a, b in [("matrix_det", [[1, 2], [3, 4]], None), ("matrix_inverse", [[1, 2], [3, 4]], None), ("matrix_solve", [[1, 1], [2, 2]], [[3], [6]]),
                     ("matrix_mul", [[1, 2]], [[1], [1]]), ("matrix_inverse", [[1, 2], [2, 4]], None)]:
        json.dumps(L.run(op, a, b))


def test_entradas_hostiles_no_cuelgan_ni_superan_el_plazo():
    t0 = time.perf_counter()
    for malo in ["[[1e999999999]]", "[[1e100000]]", "[[10^999999]]", "[[2^99999999]]", "[[99999^99999]]", "[[" + "(" * 500 + "1" + ")" * 500 + "]]"]:
        r = run("matrix_det", malo)
        assert r["status"] in ("invalid_input", "domain_error", "internal_error") and r["exact_result"] is None, (malo[:30], r["status"])
    assert time.perf_counter() - t0 < 5
