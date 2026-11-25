"""Servidor JSON Lines por stdin/stdout (Windows). Una solicitud por línea, una respuesta por línea.
Uso: python -I -m math_universe_engine.server
"""
import json
import sys
from .dispatcher import handle, API_VERSION

MAX_LINE = 100_000


def _utf8(stream):
    """Windows usa por defecto la página de códigos local (cp1252/cp850): se fuerza UTF-8 en el canal con Flutter."""
    try: stream.reconfigure(encoding="utf-8", errors="strict")
    except Exception: pass


def main(stdin=None, stdout=None):
    if stdin is None: stdin = sys.stdin; _utf8(stdin)
    if stdout is None: stdout = sys.stdout; _utf8(stdout)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        if len(line) > MAX_LINE:
            resp = {"request_id": None, "api_version": API_VERSION, "status": "invalid_input", "elapsed_ms": 0,
                    "error": {"code": "LIMIT_EXCEEDED", "message": "Línea demasiado larga", "details": {}}}
        else:
            try:
                resp = handle(json.loads(line))
            except json.JSONDecodeError:
                resp = {"request_id": None, "api_version": API_VERSION, "status": "invalid_input", "elapsed_ms": 0,
                        "error": {"code": "INVALID_REQUEST", "message": "JSON inválido", "details": {}}}
        stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        stdout.flush()


if __name__ == "__main__":
    main()
