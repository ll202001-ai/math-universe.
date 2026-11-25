"""Interfaz de operaciones (formato de respuesta ALINEADO con la API 1.0 del motor, pero NO registrado en su dispatcher ni validado
contra su esquema: eso se decidirá en la etapa de integración)."""
import time
from fractions import Fraction
from . import _motor
_motor.ensure()
from math_universe_engine import limits
from math_universe_engine.errors import EngineError, InvalidRequest, MathDomainError, NotImplementedOperation, TimeoutExceeded, LimitExceeded
from . import ops, checks
from .matrix import Matrix, as_matrix, fr
from . import __version__

OPERATIONS = ("matrix_add", "matrix_sub", "matrix_mul", "matrix_transpose", "matrix_det", "matrix_inverse", "matrix_rank", "matrix_rref", "matrix_solve")

_STATUS = {"INVALID_REQUEST": "invalid_input", "PARSE_ERROR": "invalid_input", "DOMAIN_ERROR": "domain_error", "NOT_IMPLEMENTED": "unsupported",
           "LIMIT_EXCEEDED": "internal_error", "TIMEOUT": "timeout"}


def _mtxt(m): return "[" + ", ".join("[" + ", ".join(fr(x) for x in r) + "]" for r in m.rows) + "]"


def _vtxt(v): return "[" + ", ".join(fr(x) for x in v) + "]"


def _independent_rows(a):
    """Filas independientes (pivotes de Aᵀ) para el certificado del rango."""
    R, piv = ops.rref_raw([list(c) for c in zip(*a.rows)], a.nr)
    return piv


def _dispatch(op, a, b):
    if op == "matrix_add":
        c = ops.add(a, b); return _mtxt(c), {"matrix": c.to_strings()}, checks.check_add(a, b, c), "(A+B)−B = A elemento a elemento"
    if op == "matrix_sub":
        c = ops.sub(a, b); return _mtxt(c), {"matrix": c.to_strings()}, checks.check_sub(a, b, c), "(A−B)+B = A elemento a elemento"
    if op == "matrix_mul":
        c = ops.mul(a, b); return _mtxt(c), {"matrix": c.to_strings()}, checks.check_mul(a, b, c), "Freivalds exacto: (AB)v = A(Bv) con 6 vectores racionales"
    if op == "matrix_transpose":
        t = ops.transpose(a); return _mtxt(t), {"matrix": t.to_strings()}, checks.check_transpose(a, t), "índice a índice: Tᵢⱼ = Aⱼᵢ"
    if op == "matrix_det":
        d = ops.det(a)
        return fr(d), {"determinant": fr(d), "invertible": d != 0}, checks.check_det(a, d), "Bareiss" + (" + Laplace" if a.nr <= 6 else "") + " + det(Aᵀ) = det(A)"
    if op == "matrix_inverse":
        inv = ops.inverse(a)
        return _mtxt(inv), {"matrix": inv.to_strings()}, checks.check_inverse(a, inv), "A·A⁻¹ = I y A⁻¹·A = I (exacto)"
    if op == "matrix_rank":
        R, piv = ops.rref(a)
        r = len(piv); rows = _independent_rows(a)
        null = ops._null_vectors(R.tolist(), piv, a.nc)
        ok = checks.check_rank(a, r, piv, rows, null)
        return str(r), {"rank": r, "pivot_columns": piv, "nullity": a.nc - r}, ok, "menor r×r no nulo (Bareiss) y nulidad ≥ n−r con A·v = 0"
    if op == "matrix_rref":
        R, piv = ops.rref(a)
        ok = ops.rank(a) == len(piv) and checks.check_mul(a, Matrix.identity(a.nc), a) and _rref_ok(R, piv)
        return _mtxt(R), {"matrix": R.to_strings(), "pivot_columns": piv, "rank": len(piv)}, ok, "forma reducida: pivotes 1, ceros en su columna, filas nulas al final"
    if op == "matrix_solve":
        res = ops.solve(a, b)
        ok = checks.check_solve(a, b, res)
        if res["kind"] == "none":
            return "Sin solución", {"kind": "none", "rank": res["rank"], "certificate_y": [fr(x) for x in res["certificate"]]}, ok, "certificado de Farkas: yᵀA = 0 con yᵀb ≠ 0"
        data = {"kind": res["kind"], "rank": res["rank"], "particular": [fr(x) for x in res["particular"]],
                "nullspace_basis": [[fr(x) for x in v] for v in res["nullspace"]], "free_columns": res["free"]}
        txt = "x = " + _vtxt(res["particular"]) + ("" if not res["nullspace"] else " + " + " + ".join(f"t{i+1}·{_vtxt(v)}" for i, v in enumerate(res["nullspace"])))
        return txt, data, ok, "A·x_p = b y A·v = 0 para cada vector de la base del núcleo (exacto)"
    raise NotImplementedOperation(f"Operación '{op}' no implementada")


def _rref_ok(R, piv):
    rows = R.rows; lead = []
    for i, r in enumerate(rows):
        nz = [j for j, x in enumerate(r) if x != 0]
        if not nz: lead.append(None); continue
        j = nz[0]
        if r[j] != 1: return False
        if any(rows[k][j] != 0 for k in range(len(rows)) if k != i): return False
        lead.append(j)
    ints = [x for x in lead if x is not None]
    return ints == sorted(ints) and ints == list(piv) and all(x is None for x in lead[len(ints):]) and None not in lead[:len(ints)]


def compute(operation, a, b=None):
    """Calcula y verifica SIN gestionar el plazo ni capturar errores (para el dispatcher del motor, que ya los gestiona).
    Devuelve (texto_exacto, data, verificado: bool, método, avisos, estado_final). Lanza EngineError ante entradas/dominio inválidos."""
    if operation not in OPERATIONS: raise NotImplementedOperation(f"Operación '{operation}' no implementada", {"available": list(OPERATIONS)})
    if a is None: raise InvalidRequest("Falta la matriz 'a'")
    A = as_matrix(a)
    B = as_matrix(b) if b is not None else None
    if operation in ("matrix_add", "matrix_sub", "matrix_mul", "matrix_solve") and B is None:
        raise InvalidRequest("Esta operación necesita también 'b'")
    txt, data, ok, how = _dispatch(operation, A, B)
    warnings, status = [], "success_exact"
    if ok:
        if operation == "matrix_solve": status = {"unique": "success_exact", "infinite": "multiple_solutions", "none": "no_solution"}[data["kind"]]
        if operation == "matrix_det" and not data["invertible"]: warnings.append("Determinante 0: la matriz es singular")
    return txt, data, ok, how, warnings, status


def run(operation, a=None, b=None, timeout_ms=10000):
    """Ejecuta una operación y devuelve un dict con status / exact_result / data / verification (nunca lanza para errores matemáticos)."""
    t0 = time.perf_counter()
    resp = {"api_version": "1.0-linalg-aislado", "linalg_version": __version__, "operation": operation, "status": "success_exact",
            "exact_result": None, "approximate_result": None, "conditions": [], "warnings": [],
            "verification": {"status": "not_performed", "method": None}, "data": {}}
    try:
        if operation not in OPERATIONS: raise NotImplementedOperation(f"Operación '{operation}' no implementada", {"available": list(OPERATIONS)})
        if a is None: raise InvalidRequest("Falta la matriz 'a'")
        A = as_matrix(a)
        B = as_matrix(b) if b is not None else None
        if operation in ("matrix_add", "matrix_sub", "matrix_mul", "matrix_solve") and B is None:
            raise InvalidRequest("Esta operación necesita también 'b'")
        limits.start(timeout_ms)
        try:
            txt, data, ok, how = _dispatch(operation, A, B)
        finally:
            limits.stop()
        if ok:
            resp.update(exact_result=txt, data=data, verification={"status": "passed", "method": how})
            if operation == "matrix_solve":
                resp["status"] = {"unique": "success_exact", "infinite": "multiple_solutions", "none": "no_solution"}[data["kind"]]
            if operation == "matrix_det" and not data["invertible"]: resp["warnings"].append("Determinante 0: la matriz es singular")
        else:
            resp.update(status="internal_error", error={"code": "VERIFICATION_FAILED", "message": "El resultado NO superó la verificación independiente",
                                                        "details": {"unverified_result": txt}}, verification={"status": "failed", "method": how})
    except EngineError as e:
        resp["status"] = _STATUS.get(e.code, "internal_error")
        resp["error"] = {"code": e.code, "message": e.message, "details": e.details}
    resp["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    return resp
