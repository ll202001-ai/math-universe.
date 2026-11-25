"""Diagnóstico de la comparación motor ↔ SymPy para casos concretos (ejecutar donde SymPy está instalado):
    python tools/diagnosticar_comparador.py            (escribe validacion/diagnostico_comparador.txt)
Para cada caso imprime, SIN interpretar: la respuesta del motor (con el respaldo SymPy DESACTIVADO), la referencia de SymPy, la expresión
diferencia con su srepr, el resultado de Expr.equals, simplify, is_zero, la demostración exacta por ramas, valores a 60 cifras en puntos
racionales de ambos lados de las singularidades, y la evaluación de la expresión original sin autosimplificar. Sirve para fijar la CAUSA
RAÍZ con datos reproducibles, no con suposiciones."""
import os, sys, traceback
from fractions import Fraction
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "validacion")

CASOS = [
    {"op": "simplify", "expr": "(x^3-8)/(x-2)"},
    {"op": "simplify", "expr": "x/x"},
    {"op": "integrate", "expr": "1/(x^3+1)"},
    {"op": "integrate", "expr": "1/x"},
    {"op": "differentiate", "expr": "abs(x)"},
]


def seguro(f, *a):
    try: return f(*a)
    except Exception as e: return f"<<{type(e).__name__}: {e}>>"


def main():
    import audit.comparar_sympy as c
    ad = c.SympyAdapter()
    sp = ad.sp
    L = [f"versiones: {ad.versions()}"]
    for case in CASOS:
        case = {**case, "id": 0}
        L += ["", "=" * 100, f"CASO {case['op']}({case['expr']})"]
        m = c._motor(case)
        L += [f"motor: status={m['status']} resultado={m.get('exact_result')} condiciones={m['conditions']} metodo={m.get('method')} verificacion={m['verification']}"]
        ref = ad.reference(case)
        L += [f"SymPy: tipo={ref.get('tipo')} texto={ref.get('texto')} singularidades={ref.get('singularidades')}"]
        L += [f"veredicto del comparador: {seguro(c.clasificar, case, m, ref, ad)}"]
        if case["op"] == "integrate" and ref.get("tipo") == "primitiva" and m["status"] == "success_exact":
            mot = ad.parse(m["exact_result"].replace("+ C", "").strip()); a, b = ad.derivada(mot), ref["integrando"]
        elif case["op"] in ("simplify", "differentiate") and ref.get("obj") is not None and m["status"] == "success_exact":
            a, b = ref["obj"], ad.parse(m["exact_result"])
        else:
            continue
        d = a - b
        L += [f"a (SymPy / d(primitiva)) = {a}", f"b (motor / integrando)      = {b}", f"srepr(a-b) = {sp.srepr(d)[:600]}",
              f"equals(0)        = {seguro(lambda: d.equals(0))}", f"simplify(a-b)    = {seguro(lambda: sp.simplify(d))}",
              f"is_zero          = {seguro(lambda: d.is_zero)}", f"por ramas (demostración exacta) = {seguro(ad.igual_simbolico_por_ramas, a, b)}"]
        for k in (Fraction(-3), Fraction(-11, 10), Fraction(-9, 10), Fraction(1, 3), Fraction(7, 2)):
            va = seguro(lambda: sp.N(a.subs(ad.x, sp.Rational(k.numerator, k.denominator)), 60))
            vb = seguro(lambda: sp.N(b.subs(ad.x, sp.Rational(k.numerator, k.denominator)), 60))
            L += [f"  x={k}: a={va}  b={vb}  a-b={seguro(lambda: sp.N((a - b).subs(ad.x, sp.Rational(k.numerator, k.denominator)), 60))}"]
        for k in (Fraction(0), Fraction(2), Fraction(-1)):
            L += [f"  original sin autosimplificar indefinida en x={k}: {seguro(ad.indefinida_en, case['expr'], k)} · límite: {seguro(ad.limite_en, case['expr'], k)}"]
    os.makedirs(OUT, exist_ok=True)
    texto = "\n".join(str(l) for l in L)
    open(os.path.join(OUT, "diagnostico_comparador.txt"), "w", encoding="utf-8").write(texto + "\n")
    print(texto)
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except ImportError as e:
        print("SymPy/mpmath no instalados:", e); sys.exit(2)
    except Exception:
        traceback.print_exc(); sys.exit(1)
