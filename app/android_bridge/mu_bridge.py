"""Puente Android (Chaquopy) <-> motor: recibe una linea JSON, devuelve una linea JSON. No contiene logica matematica.
Sin jsonschema en Android (primera version): se aplica una validacion estructural minima de la respuesta."""
import json

_STATUS = {"success_exact", "success_approximate", "unsupported", "invalid_input", "domain_error", "no_solution",
           "multiple_solutions", "timeout", "cancelled", "internal_error"}


def _fuera_de_contrato(msg, rid=None):
    return {"request_id": rid, "api_version": "1.1", "status": "internal_error", "elapsed_ms": 0,
            "error": {"code": "INTERNAL_ERROR", "message": msg, "details": {}}}


def handle(line):
    try:
        req = json.loads(line)
    except ValueError:
        return json.dumps(_fuera_de_contrato("JSON invalido"), ensure_ascii=False)
    rid = req.get("request_id") if isinstance(req, dict) else None
    try:
        from math_universe_engine.dispatcher import handle as motor
        resp = motor(req)
    except Exception as e:  # nunca se filtra una traza a la interfaz
        resp = _fuera_de_contrato("Fallo del puente: " + type(e).__name__, rid)
    if not (isinstance(resp, dict) and resp.get("status") in _STATUS and "api_version" in resp and "elapsed_ms" in resp):
        resp = _fuera_de_contrato("Respuesta fuera de contrato", rid)
    return json.dumps(resp, ensure_ascii=False)
