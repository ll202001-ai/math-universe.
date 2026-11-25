"""La fase 8 se CONSERVA: todo archivo del motor es idéntico al de la fase 8 salvo los cambios DECLARADOS de la integración (0.4.0).
Un cambio no declarado en el motor, o una modificación de las versiones anteriores archivadas, hace fallar esta prueba."""
import hashlib, os
import pytest

ENGINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAIZ = os.path.dirname(ENGINE)
MAN8 = os.path.join(RAIZ, "versiones_anteriores", "fase8", "MANIFIESTO_SHA256.txt")
MODIFICADOS_DECLARADOS = {
    "engine/math_universe_engine/__init__.py",       # versión 0.3.0 -> 0.4.0
    "engine/math_universe_engine/dispatcher.py",     # operaciones de matrices, API 1.1
    "engine/math_universe_engine/parser.py",         # H-1: cota del exponente decimal
    "engine/schema/request.schema.json",             # contrato 1.1: operaciones y structured_input de matrices
    "engine/audit/no_soportado.py",                  # 'determinant' ya no es una limitación
    "engine/tests/test_12_no_soportado.py",          # (si cambió) catálogo
    "engine/audit/comparar_sympy.py",                # 0.5.0: 0/0 sin evaluar y condiciones x ≠ k del motor (CI 2026-11-25)
    "engine/tests/test_05_entradas_y_aproximacion.py",  # 0.5.0: con mpmath, pi a 40 cifras ya no es una limitación
    "engine/tests/test_09_auditoria.py",             # 0.5.0: idem (la limitación solo persiste sin mpmath)
}


def _h(p):
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()


def _manifiesto8():
    if not os.path.isfile(MAN8): pytest.fail(f"Falta el manifiesto de la fase 8 archivada: {MAN8}")
    with open(MAN8, encoding="utf-8") as f:
        return dict(l.rstrip("\n").split("  ", 1)[::-1] for l in f if l.strip())


def test_los_archivos_del_motor_fase8_estan_intactos_salvo_los_declarados():
    man = _manifiesto8()
    motor = {r: h for r, h in man.items() if r.startswith("engine/") and "__pycache__" not in r}
    assert len(motor) > 40
    distintos, faltan = [], []
    for rel, h in motor.items():
        p = os.path.join(RAIZ, rel)
        if not os.path.isfile(p): faltan.append(rel); continue
        if _h(p) != h and rel not in MODIFICADOS_DECLARADOS: distintos.append(rel)
    assert not faltan, f"Archivos de la fase 8 desaparecidos: {faltan}"
    assert not distintos, f"Modificaciones NO declaradas respecto de la fase 8: {distintos}"


def test_las_modificaciones_declaradas_siguen_siendo_las_unicas_que_cambian():
    man = _manifiesto8()
    cambiados = {r for r, h in man.items() if r.startswith("engine/") and os.path.isfile(os.path.join(RAIZ, r)) and _h(os.path.join(RAIZ, r)) != h}
    assert cambiados <= MODIFICADOS_DECLARADOS, cambiados - MODIFICADOS_DECLARADOS
    assert {"engine/math_universe_engine/dispatcher.py", "engine/math_universe_engine/parser.py"} <= cambiados   # los cambios sí están


def test_los_zip_de_las_versiones_anteriores_no_cambiaron():
    hashes = {}
    with open(os.path.join(RAIZ, "versiones_anteriores", "HASHES_ZIP.txt"), encoding="utf-8") as f:
        for l in f:
            if l.strip(): h, rel = l.rstrip("\n").split("  ", 1); hashes[rel] = h
    assert set(hashes) == {"fase8/math_universe_fase8.zip", "fase9b/math_universe_linalg_fase9b.zip"}
    for rel, h in hashes.items():
        assert _h(os.path.join(RAIZ, "versiones_anteriores", rel)) == h, rel
    # y coinciden con los hashes entregados al usuario en su momento
    assert hashes["fase8/math_universe_fase8.zip"] == "6e1713f69398ba716d18416e01f78d70cd62268286caef52b1f8e76c61ad893b"
    assert hashes["fase9b/math_universe_linalg_fase9b.zip"] == "c287ce1c787235d888b14623cb91e91fcc14fcb56ee7d46371b534f33feb493b"
