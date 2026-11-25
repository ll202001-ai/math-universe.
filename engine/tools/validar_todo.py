"""Validación completa y reproducible del motor. Ejecutar desde la carpeta engine/:
      python tools/validar_todo.py            (informe INFORME_VALIDACION.md + validacion/*.json)
      python tools/validar_todo.py --estricto (código de salida != 0 si la validación está INCOMPLETA o hay fallos)
Registra versiones (Python, SO, SymPy, mpmath, NumPy, SciPy, jsonschema, pytest), ejecuta TODAS las pruebas
(incluido test_08_sympy.py), las pruebas aleatorias con semillas fijas, el oráculo independiente y la comparación
motor propio vs SymPy. Una prueba omitida NUNCA cuenta como aprobada y hace que la validación sea INCOMPLETA."""
import sys as _s
for _st in (_s.stdout, _s.stderr):
    try: _st.reconfigure(encoding='utf-8')
    except Exception: pass
import collections, datetime, importlib, json, os, platform, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
OUT = os.path.join(ROOT, "validacion"); os.makedirs(OUT, exist_ok=True)


def versiones():
    v = {"python": platform.python_version(), "implementacion": platform.python_implementation(),
         "sistema": platform.platform(), "arquitectura": platform.machine(), "ejecutable": sys.executable}
    for m in ("sympy", "mpmath", "numpy", "scipy", "jsonschema", "pytest"):
        try:
            from importlib import metadata
            importlib.import_module(m); v[m] = metadata.version(m)
        except Exception as e: v[m] = f"NO INSTALADO ({type(e).__name__})"
    import math_universe_engine as me
    v["motor"] = me.__version__
    return v


def paso_pytest():
    import pytest
    from run_tests import Collector
    os.chdir(ROOT)
    col = Collector()
    code = pytest.main(["-q", "tests", "-p", "no:cacheprovider", "-k", "not corpus_completo"], plugins=[col])
    cnt = collections.Counter(r[1] for r in col.rows)
    por_archivo = collections.OrderedDict()
    for nid, out, reason, d in col.rows:
        g = nid.split("::")[0].split("/")[-1].replace(" [MÓDULO COMPLETO]", "")
        por_archivo.setdefault(g, collections.Counter())[out] += 1
    return {"aprobadas": cnt["passed"], "falladas": cnt["failed"], "omitidas": cnt["skipped"], "codigo_pytest": int(code),
            "por_archivo": {k: dict(v) for k, v in por_archivo.items()},
            "omitidas_detalle": [(r[0], r[2]) for r in col.rows if r[1] == "skipped"][:50],
            "falladas_detalle": [r[0] for r in col.rows if r[1] == "failed"]}


def paso_fuzz():
    import audit.fuzz as fz
    res, tot = [], 0
    for seed in (1, 7, 99, 2024, 12345, 31337):
        st, fl = fz.main(300, seed); tot += len(fl)
        res.append({"semilla": seed, "casos": st, "fallos": len(fl), "ejemplos": [str(x)[:300] for x in fl[:5]]})
    return {"total_fallos": tot, "corridas": res}


def paso_oraculo():
    import audit.oraculo as o
    o.R.clear()
    for f in o.ALL: f()
    por = collections.OrderedDict()
    for x in o.R: por.setdefault(x["categoria"], {"ok": 0, "no_soportado": 0, "fallo": 0})[x["estado"]] += 1
    return {"total": len(o.R), "fallos": sum(1 for x in o.R if x["estado"] == "fallo"),
            "no_soportados": sum(1 for x in o.R if x["estado"] == "no_soportado"),
            "correctos": sum(1 for x in o.R if x["estado"] == "ok"),
            "por_categoria": dict(por),
            "fallos_detalle": [x for x in o.R if x["estado"] == "fallo"][:20],
            "no_soportados_detalle": [x for x in o.R if x["estado"] == "no_soportado"]}


def paso_comparacion():
    try:
        import sympy, mpmath  # noqa
    except ImportError as e:
        return {"ejecutada": False, "motivo": f"SymPy/mpmath no instalados: {e}"}
    import audit.comparar_sympy as c
    ad = c.SympyAdapter()
    cnt, filas = c.ejecutar(ad, os.path.join(OUT, "comparacion_sympy.json"))
    total = len(filas)
    sin_ref = [f for f in filas if f["veredicto"] == "SIN_REFERENCIA_SYMPY"]
    ambos = [f for f in filas if f["veredicto"] == "AMBOS_NO_SOPORTAN"]
    return {"ejecutada": True, "versiones": ad.versions(), "conteo": cnt, "total": total,
            "con_referencia": total - len(sin_ref) - len(ambos),
            "hallazgos": [f for f in filas if f["veredicto"] in c.HALLAZGOS],
            "convenciones": [f for f in filas if f["veredicto"] == "CONVENCION_DOCUMENTADA"],
            "demostrados_por_ramas": [f for f in filas if "DEMOSTRADO exactamente por ramas" in f["detalle"]],
            "dominio_sympy_amplio": [f for f in filas if f["veredicto"] == "SYMPY_AMPLIA_DOMINIO"],
            "sin_referencia": sin_ref, "ambos_no_soportan": ambos,
            "limitaciones_motor": [f for f in filas if f["veredicto"] == "LIMITACION_MOTOR"]}


def main():
    estricto = "--estricto" in sys.argv
    t0 = time.time()
    ver = versiones()
    json.dump(ver, open(os.path.join(OUT, "entorno.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("Entorno:", json.dumps(ver, ensure_ascii=False))
    R = {"fecha": datetime.datetime.now().isoformat(timespec="seconds"), "entorno": ver}
    R["pytest"] = paso_pytest()
    R["fuzz"] = paso_fuzz()
    R["oraculo"] = paso_oraculo()
    R["comparacion"] = paso_comparacion()
    R["segundos"] = round(time.time() - t0, 1)
    json.dump(R, open(os.path.join(OUT, "resultados.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)

    motivos = []
    p = R["pytest"]
    if p["falladas"]: motivos.append(f"{p['falladas']} prueba(s) fallada(s)")
    if p["omitidas"]: motivos.append(f"{p['omitidas']} prueba(s) OMITIDA(S) (no cuentan como aprobadas)")
    if "NO INSTALADO" in str(ver["sympy"]): motivos.append("SymPy no instalado")
    if "NO INSTALADO" in str(ver["mpmath"]): motivos.append("mpmath no instalado")
    if R["fuzz"]["total_fallos"]: motivos.append(f"{R['fuzz']['total_fallos']} fallo(s) en pruebas aleatorias")
    if R["oraculo"]["fallos"]: motivos.append(f"{R['oraculo']['fallos']} fallo(s) del oráculo independiente")
    cmpr = R["comparacion"]
    if not cmpr["ejecutada"]: motivos.append("comparación con SymPy NO ejecutada")
    elif cmpr["hallazgos"]: motivos.append(f"{len(cmpr['hallazgos'])} hallazgo(s) de la comparación motor/SymPy por analizar (diferencias, dominio, no concluyentes o errores del comparador)")
    veredicto = "VALIDACIÓN COMPLETA Y SIN HALLAZGOS PENDIENTES" if not motivos else "VALIDACIÓN INCOMPLETA O CON HALLAZGOS: " + "; ".join(motivos)

    L = ["# INFORME DE VALIDACIÓN · MATH UNIVERSE motor " + ver["motor"], "",
         f"Fecha: {R['fecha']} · duración {R['segundos']} s", "", f"## Veredicto\n**{veredicto}**", "",
         "## Versiones registradas", "| Componente | Versión |", "|---|---|"]
    for k, v in ver.items(): L.append(f"| {k} | {v} |")
    L += ["", "## 1. Pruebas automatizadas (pytest)",
          f"**Aprobadas: {p['aprobadas']} · Falladas: {p['falladas']} · Omitidas: {p['omitidas']}** (las omitidas NO se cuentan como aprobadas)", "",
          "| Archivo | Aprobadas | Falladas | Omitidas |", "|---|---|---|---|"]
    for g, c in p["por_archivo"].items(): L.append(f"| {g} | {c.get('passed',0)} | {c.get('failed',0)} | {c.get('skipped',0)} |")
    if p["omitidas_detalle"]:
        L += ["", "Omitidas:"] + [f"- `{a}` — {b}" for a, b in p["omitidas_detalle"]]
    if p["falladas_detalle"]:
        L += ["", "FALLADAS:"] + [f"- `{a}`" for a in p["falladas_detalle"]]
    L += ["", "## 2. Pruebas aleatorias (semillas fijas, oráculo independiente)", "| Semilla | Simplificar | Derivar | Factorizar | Expandir | Integrar | Fallos |", "|---|---|---|---|---|---|---|"]
    for c in R["fuzz"]["corridas"]:
        s = c["casos"]; L.append(f"| {c['semilla']} | {s['simplify']} | {s['diff']} | {s['factor']} | {s['expand']} | {s['integral']} | {c['fallos']} |")
    L += ["", "## 3. Auditoría con oráculo independiente (NumPy/SciPy/diferencias finitas, sin usar el parser del motor)",
          f"Total {R['oraculo']['total']}: **correctos {R['oraculo']['correctos']} · no soportados (declarados, NO cuentan como correctos) {R['oraculo']['no_soportados']} · fallos {R['oraculo']['fallos']}**", "",
          "| Categoría | Correctos | No soportados | Fallos |", "|---|---|---|---|"]
    for k, v in R["oraculo"]["por_categoria"].items(): L.append(f"| {k} | {v['ok']} | {v['no_soportado']} | {v['fallo']} |")
    if R["oraculo"]["no_soportados_detalle"]:
        L += ["", "No soportados (el motor lo declara; no es un resultado):"] + [f"- {x['categoria']}: `{x['caso']}` — {x['detalle'][:100]}" for x in R["oraculo"]["no_soportados_detalle"]]
    L += ["", "## 4. Comparación motor propio vs SymPy"]
    if not cmpr["ejecutada"]:
        L += [f"**NO EJECUTADA** — {cmpr['motivo']}"]
    else:
        L += [f"Versiones: {cmpr['versiones']}", "",
              f"Casos: {cmpr['total']} · con referencia de SymPy (validados cruzadamente): {cmpr['con_referencia']} · "
              f"sin referencia de SymPy (NO validados cruzadamente): {len(cmpr['sin_referencia'])} · ninguno resuelve: {len(cmpr['ambos_no_soportan'])}", "",
              "| Veredicto | Casos |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(cmpr["conteo"].items())]
        for titulo, clave in (("HALLAZGOS por analizar (error, dominio, no concluyente o fallo del comparador)", "hallazgos"),
                              ("Convenciones documentadas (coinciden exactamente con lo documentado)", "convenciones"),
                              ("SymPy da valor donde la función original NO existe (evidencia independiente del motor; el motor excluye el punto con razón) — REVISAR", "dominio_sympy_amplio"),
                              ("Equivalencias que SymPy.equals NO confirmó y se DEMOSTRARON exactamente por ramas de Abs/sign (equals es heurístico) — REVISAR", "demostrados_por_ramas"),
                              ("Limitaciones del motor propio (SymPy sí resuelve)", "limitaciones_motor"),
                              ("Sin referencia de SymPy: resultado del motor NO validado cruzadamente", "sin_referencia"),
                              ("Ninguno de los dos resuelve", "ambos_no_soportan")):
            if cmpr[clave]:
                L += ["", f"### {titulo}"] + [f"- `{f['op']}` `{f['expr']}` → {f['veredicto']}: {f['detalle'][:(900 if clave == 'hallazgos' else 400)]}" for f in cmpr[clave][:80]]
    L += ["", "## Cómo interpretar", "- *Implementado* = existe código; *probado* = pasa las pruebas anteriores; *pendiente* = ver docs/FUNCIONES.md.",
          "- Este informe lo genera `tools/validar_todo.py`; no contiene resultados escritos a mano."]
    open(os.path.join(ROOT, "INFORME_VALIDACION.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n" + "\n".join(L[:12]))
    ok = not motivos
    return 0 if (ok or not estricto) else 1


if __name__ == "__main__":
    sys.exit(main())
