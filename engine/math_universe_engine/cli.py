"""Línea de comandos de apoyo (no es la interfaz del producto):
   python -m math_universe_engine.cli simplify "(x^2-1)/(x-1)"
   python -m math_universe_engine.cli solve "2x+y=5; x-y=1"
   python -m math_universe_engine.cli limit "sin(x)/x" --point 0
   python -m math_universe_engine.cli integrate "x^2" --lower 0 --upper 3
"""
import argparse
import json
import sys
from .dispatcher import handle


def main(argv=None):
    ap = argparse.ArgumentParser(prog="math_universe_engine.cli")
    ap.add_argument("operation"); ap.add_argument("expression", nargs="?")
    ap.add_argument("--var", action="append", dest="variables"); ap.add_argument("--point"); ap.add_argument("--direction")
    ap.add_argument("--lower"); ap.add_argument("--upper"); ap.add_argument("--order", type=int)
    ap.add_argument("--precision", type=int); ap.add_argument("--timeout-ms", type=int, dest="timeout_ms")
    ap.add_argument("--assume", action="append", default=[], help="variable=positive|negative|nonzero|integer|real|complex")
    for st in (sys.stdout, sys.stderr):
        try: st.reconfigure(encoding="utf-8")
        except Exception: pass
    a = ap.parse_args(argv)
    req = {"operation": a.operation}
    if a.expression is not None: req["expression"] = a.expression
    for k in ("variables", "point", "direction", "lower", "upper", "order", "precision", "timeout_ms"):
        if getattr(a, k) is not None: req[k] = getattr(a, k)
    if a.assume:
        req["assumptions"] = dict(x.split("=", 1) for x in a.assume)
    json.dump(handle(req), sys.stdout, ensure_ascii=False, indent=2); sys.stdout.write("\n")


if __name__ == "__main__":
    main()
