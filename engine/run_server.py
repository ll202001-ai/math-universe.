"""Servidor JSON Lines del motor (una solicitud JSON por línea en stdin, una respuesta por línea en stdout).
   python -I run_server.py
"""
import os
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from math_universe_engine.server import main
    main()
