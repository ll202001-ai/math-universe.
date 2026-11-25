"""Regenera docs/NO_SOPORTADO.md ejecutando el catálogo audit/no_soportado.py."""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from audit.no_soportado import generar_markdown

if __name__ == "__main__":
    dest = os.path.join(ROOT, "..", "docs", "NO_SOPORTADO.md")
    open(dest, "w", encoding="utf-8", newline="\n").write(generar_markdown())
    print("escrito", os.path.abspath(dest))
