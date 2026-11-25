"""Genera/verifica los archivos golden de las operaciones de matrices (tests/golden/matrices/*.json).
Son pruebas de REGRESIÓN del contrato 1.1 (el valor esperado de los casos con respuesta conocida está además comprobado a mano en test_21).
   python tools/generar_golden.py --generar
"""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
DEST = os.path.join(ROOT, "tests", "golden", "matrices")
CASOS = {
    "suma": {"operation": "matrix_add", "structured_input": {"a": [[1, 2], [3, 4]], "b": [[5, 6], [7, 8]]}},
    "resta_fracciones": {"operation": "matrix_sub", "structured_input": {"a": "[[1/2,1/3],[1/4,1/5]]", "b": "[[1/2,0],[0,1/5]]"}},
    "producto_no_cuadrado": {"operation": "matrix_mul", "structured_input": {"a": [[1, 2, 3], [4, 5, 6]], "b": [[1], [0], [2]]}},
    "transpuesta": {"operation": "matrix_transpose", "structured_input": {"a": [[1, 2, 3], [4, 5, 6]]}},
    "determinante": {"operation": "matrix_det", "structured_input": {"a": [[2, 1, 0], [1, 3, 1], [0, 1, 4]]}},
    "determinante_alias": {"operation": "determinant", "expression": "[[1,2],[3,4]]"},
    "inversa": {"operation": "matrix_inverse", "structured_input": {"a": [[2, 1], [1, 1]]}},
    "inversa_singular": {"operation": "matrix_inverse", "structured_input": {"a": [[1, 2], [2, 4]]}},
    "rango": {"operation": "matrix_rank", "structured_input": {"a": [[1, 2, 3], [2, 4, 6], [1, 0, 1]]}},
    "rref": {"operation": "matrix_rref", "structured_input": {"a": [[1, 2, 1], [2, 4, 0]]}},
    "sistema_unico": {"operation": "matrix_solve", "structured_input": {"a": [[2, 1], [1, 3]], "b": [[3], [5]]}},
    "sistema_infinito": {"operation": "matrix_solve", "structured_input": {"a": [[1, 1], [1, 1]], "b": [[2], [2]]}},
    "sistema_sin_solucion": {"operation": "matrix_solve", "structured_input": {"a": [[1, 1], [1, 1]], "b": [[1], [2]]}},
    "dimension_incompatible": {"operation": "matrix_add", "structured_input": {"a": [[1, 2]], "b": [[1], [2]]}},
    "entrada_simbolica_rechazada": {"operation": "matrix_det", "structured_input": {"a": [["x", 1], [2, 3]]}},
}
CLAVES = ("status", "exact_result", "data", "verification", "error", "warnings", "conditions")


def respuesta_normalizada(req):
    from math_universe_engine.dispatcher import handle
    r = handle(dict(req, request_id="golden"))
    out = {k: r.get(k) for k in CLAVES if k in r}
    if "error" in out: out["error"] = {"code": out["error"]["code"]}
    return out


def main():
    os.makedirs(DEST, exist_ok=True)
    for nombre, req in CASOS.items():
        with open(os.path.join(DEST, nombre + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"request": req, "expected": respuesta_normalizada(req)}, f, indent=1, ensure_ascii=False); f.write("\n")
    print(len(CASOS), "golden escritos")


if __name__ == "__main__":
    if "--generar" in sys.argv: main()
