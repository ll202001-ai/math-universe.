"""Ejecuta toda la batería y genera INFORME_PRUEBAS.md (aprobadas / falladas / OMITIDAS por separado)."""
import sys as _s
for _st in (_s.stdout, _s.stderr):
    try: _st.reconfigure(encoding='utf-8')
    except Exception: pass
import collections, datetime, os, platform, sys, time
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Collector:
    def __init__(self): self.rows = []; self.t0 = time.time()

    def pytest_collectreport(self, report):
        if report.outcome == "skipped":
            reason = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else ""
            self.rows.append((report.nodeid + " [MÓDULO COMPLETO]", "skipped", reason, 0))

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.outcome in ("skipped", "failed")):
            out = report.outcome
            reason = ""
            if out == "skipped":
                reason = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else ""
            self.rows.append((report.nodeid, out, reason, report.duration))


def main():
    os.chdir(ROOT)
    col = Collector()
    code = pytest.main(["-q", "tests", "-p", "no:cacheprovider"], plugins=[col])
    cnt = collections.Counter(r[1] for r in col.rows)
    try:
        import sympy; sv = sympy.__version__
    except ImportError:
        sv = "NO instalado"
    groups = collections.OrderedDict()
    for nid, out, reason, d in col.rows:
        g = nid.split("::")[0].split("/")[-1].replace(" [MÓDULO COMPLETO]", "")
        groups.setdefault(g, collections.Counter())[out] += 1
    lines = ["# INFORME DE PRUEBAS · MATH UNIVERSE motor",
             f"Fecha: {datetime.datetime.now().isoformat(timespec='seconds')} · Python {platform.python_version()} · {platform.platform()}",
             f"SymPy: {sv}", "",
             f"**Aprobadas: {cnt['passed']} · Falladas: {cnt['failed']} · Omitidas: {cnt['skipped']}** (las omitidas NO se cuentan como aprobadas)", "",
             "| Archivo | Aprobadas | Falladas | Omitidas |", "|---|---|---|---|"]
    for g, c in groups.items():
        lines.append(f"| {g} | {c['passed']} | {c['failed']} | {c['skipped']} |")
    skipped = [r for r in col.rows if r[1] == "skipped"]
    if skipped:
        lines += ["", "## Pruebas omitidas (requieren un entorno que aquí no existe)"]
        for nid, _, reason, _ in skipped[:40]:
            lines.append(f"- `{nid}` — {reason}")
    failed = [r for r in col.rows if r[1] == "failed"]
    if failed:
        lines += ["", "## Pruebas FALLADAS"] + [f"- `{r[0]}`" for r in failed]
    open(os.path.join(ROOT, "INFORME_PRUEBAS.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
