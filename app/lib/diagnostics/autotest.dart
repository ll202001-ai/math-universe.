import 'dart:async';

import '../data/history_store.dart';
import '../editor/editor_controller.dart';
import '../editor/math_node.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';

/// Resultado de una comprobacion de la autoprueba.
class AutotestCheck {
  AutotestCheck(this.name, this.ok, this.detail);
  final String name;
  final bool ok;
  final String detail;

  Map<String, dynamic> toJson() => {'nombre': name, 'ok': ok, 'detalle': detail};
}

/// Informe completo de la autoprueba.
class AutotestReport {
  AutotestReport(this.checks, this.elapsed, this.dependencies);
  final List<AutotestCheck> checks;
  final Duration elapsed;
  final Map<String, dynamic> dependencies;

  int get passed => checks.where((c) => c.ok).length;
  int get failed => checks.length - passed;
  bool get allOk => checks.isNotEmpty && failed == 0;

  Map<String, dynamic> toJson() => {
        'aprobadas': passed,
        'fallidas': failed,
        'total': checks.length,
        'todo_correcto': allOk,
        'duracion_ms': elapsed.inMilliseconds,
        'dependencias_motor': dependencies,
        'comprobaciones': [for (final c in checks) c.toJson()],
      };
}

/// Autoprueba de la aplicacion INSTALADA: ejecuta operaciones reales en el motor local (Python + SymPy) y una
/// escritura/lectura real en el historial SQLite (cerrando y reabriendo la base de datos).
/// No contiene ninguna logica matematica: solo compara lo que devuelve el motor con valores conocidos.
///
/// [openStore] abre el historial persistente (el mismo que usa la app). La entrada de prueba se borra al final.
Future<AutotestReport> runAutotest(EngineClient engine, Future<HistoryStore> Function() openStore,
    {void Function(AutotestCheck)? onCheck}) async {
  final sw = Stopwatch()..start();
  final checks = <AutotestCheck>[];
  var deps = <String, dynamic>{};

  void add(String name, bool ok, String detail) {
    final c = AutotestCheck(name, ok, detail);
    checks.add(c);
    onCheck?.call(c);
  }

  Future<EngineResponse> call(Map<String, dynamic> req, {int ms = 30000}) =>
      engine.send({...req, 'timeout_ms': ms}, timeout: Duration(milliseconds: ms + 30000));

  String show(EngineResponse r) =>
      '${r.status} | ${r.exactResult ?? r.errorMessage ?? ''} | verificacion=${r.verificationStatus}'
      '${r.conditions.isEmpty ? '' : ' | condiciones=${r.conditions.join(', ')}'} | metodo=${r.method}';

  Future<void> expectEngine(String name, Map<String, dynamic> req, bool Function(EngineResponse r) ok, {int ms = 30000}) async {
    try {
      final r = await call(req, ms: ms);
      add(name, ok(r), show(r));
    } catch (e) {
      add(name, false, 'excepcion: $e');
    }
  }

  bool verified(EngineResponse r) => r.verificationStatus == 'passed';

  // 1. El motor local arranca y responde.
  await expectEngine('Motor local responde (ping)', {'operation': 'ping'}, (r) => r.status == 'success_exact', ms: 60000);

  // 2. Dependencias realmente importadas por el motor empaquetado.
  try {
    final r = await call({'operation': 'capabilities'}, ms: 60000);
    final d = r.data['dependencies'];
    deps = d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};
    add('SymPy y mpmath presentes en el motor empaquetado', deps['sympy'] != null && deps['mpmath'] != null,
        'python=${deps['python']} sympy=${deps['sympy']} mpmath=${deps['mpmath']}');
  } catch (e) {
    add('SymPy y mpmath presentes en el motor empaquetado', false, 'excepcion: $e');
  }

  // 3. Pruebas de aceptacion matematicas.
  await expectEngine('Aritmetica: 1+1 = 2', {'operation': 'evaluate', 'expression': '1+1'},
      (r) => r.status == 'success_exact' && r.exactResult == '2');
  await expectEngine('Aritmetica exacta: 1/3 + 1/6 = 1/2', {'operation': 'evaluate', 'expression': '1/3+1/6'},
      (r) => r.status == 'success_exact' && r.exactResult == '1/2' && verified(r));
  await expectEngine('Factorizar x^2-5*x+6 (verificado por re-expansion)', {'operation': 'factor', 'expression': 'x^2-5*x+6'},
      (r) => verified(r) && (r.exactResult ?? '').contains('(x - 2)') && (r.exactResult ?? '').contains('(x - 3)'));
  await expectEngine('Expandir (x-2)*(x-3) recupera x^2-5*x+6', {'operation': 'expand', 'expression': '(x-2)*(x-3)'},
      (r) => r.exactResult == 'x^2 - 5*x + 6' && verified(r));
  await expectEngine('Resolver x^2-5*x+6=0 (raices sustituidas en la ecuacion)', {'operation': 'solve', 'expression': 'x^2-5*x+6=0'},
      (r) => r.exactResult == 'x = 2, x = 3' && verified(r));
  await expectEngine('Sistema 2x+y=5; x-y=1', {'operation': 'solve', 'expression': '2x+y=5; x-y=1'},
      (r) => r.exactResult == 'x = 2, y = 1' && verified(r));
  await expectEngine('Despejar R en V=I*R (condicion I != 0)', {
    'operation': 'solve',
    'expression': 'V=I*R',
    'variables': ['R']
  }, (r) => r.exactResult == 'R = V/I' && r.conditions.contains('I ≠ 0'));
  await expectEngine('Derivar x^3*sin(x) (contraste numerico)', {'operation': 'differentiate', 'expression': 'x^3*sin(x)'},
      (r) => r.status == 'success_exact' && verified(r));
  await expectEngine('Integrar x^2 con constante C (verificado derivando)', {'operation': 'integrate', 'expression': 'x^2'},
      (r) => (r.exactResult ?? '').contains('+ C') && verified(r));
  await expectEngine('Limite de sin(x)/x en 0 = 1', {'operation': 'limit', 'expression': 'sin(x)/x', 'point': '0'},
      (r) => r.exactResult == '1');
  await expectEngine('Dominio: (x^3-8)/(x-2) conserva x != 2', {'operation': 'simplify', 'expression': '(x^3-8)/(x-2)'},
      (r) => r.exactResult == 'x^2 + 2*x + 4' && r.conditions.contains('x ≠ 2') && verified(r));
  await expectEngine('SymPy real dentro de la app: integrar sin(x)^2', {'operation': 'integrate', 'expression': 'sin(x)^2'},
      (r) => r.status == 'success_exact' && r.method == 'sympy_respaldo_experimental' && verified(r), ms: 120000);
  await expectEngine('Determinante de [[1,2],[3,4]] = -2', {
    'operation': 'matrix_det',
    'structured_input': {
      'a': [
        ['1', '2'],
        ['3', '4']
      ]
    }
  }, (r) => r.exactResult == '-2' && verified(r));
  await expectEngine('Inversa de [[2,1],[1,1]] con A*A^-1 = I', {
    'operation': 'matrix_inverse',
    'structured_input': {
      'a': [
        ['2', '1'],
        ['1', '1']
      ]
    }
  }, (r) => r.exactResult == '[[1, -1], [-1, 2]]' && verified(r) && (r.verificationMethod ?? '').contains('= I'));

  // 4. Modulos 0.6.0 (SymPy + verificacion independiente), presentacion, pasos y graficas.
  await expectEngine('Autovalores de [[2,1],[1,2]] = {1, 3} (A·v = λ·v)', {
    'operation': 'eigen',
    'structured_input': {
      'a': [
        ['2', '1'],
        ['1', '2']
      ]
    }
  }, (r) {
    final ev = (r.data['eigenvalues'] as List?)?.whereType<Map>().map((e) => e['value'].toString()).toSet() ?? {};
    return verified(r) && ev.length == 2 && ev.containsAll({'1', '3'});
  }, ms: 60000);
  await expectEngine("EDO y''+y=0 con y(0)=0, y'(0)=1 → sin(x)", {
    'operation': 'ode',
    'expression': "y''+y=0",
    'conditions': ['y(0)=0', "y'(0)=1"]
  }, (r) => r.exactResult == 'y(x) = sin(x)' && verified(r), ms: 120000);
  await expectEngine('Transformada de Laplace de e^(3t) = 1/(s-3)', {'operation': 'laplace', 'expression': 'exp(3*t)'},
      (r) => r.exactResult == '1/(s - 3)' && verified(r), ms: 120000);
  await expectEngine('Unidades: 36 km/h = 10 m/s', {'operation': 'units', 'expression': '36 km/h to m/s'},
      (r) => r.exactResult == '10 m/s' && verified(r), ms: 60000);
  await expectEngine('Ley de Ohm: V=12, R=4 → I=3', {
    'operation': 'formula',
    'params': {
      'id': 'ohm',
      'known': {'V': '12', 'R': '4'},
      'unknown': 'I'
    }
  }, (r) => r.exactResult == 'I = 3' && verified(r), ms: 60000);
  await expectEngine('Notación matemática: LaTeX de (x^3-8)/(x-2)', {
    'operation': 'simplify',
    'expression': '(x^3-8)/(x-2)',
    'latex': true
  }, (r) => (r.latexInput ?? '').contains(r'\frac') && r.latexResult == 'x^{2} + 2 x + 4');
  await expectEngine('Paso a paso de x^2-5*x+6=0 termina en las raíces', {
    'operation': 'solve',
    'expression': 'x^2-5*x+6=0',
    'steps': true
  }, (r) => r.steps.length >= 4 && r.steps.last.latex == r'x = 2,\quad x = 3');
  await expectEngine('Gráfica de 1/x: la asíntota corta la curva', {
    'operation': 'plot',
    'expression': '1/x',
    'params': {'xmin': -2, 'xmax': 2, 'samples': 101}
  }, (r) => (((r.data['series'] as List?)?.first as Map?)?['segments'] as List?)?.length == 2);

  // 5. Version 0.7.0: editor estructurado conectado al motor real y nuevas operaciones verificadas.
  try {
    // Mismas acciones que los botones: fraccion, x, potencia, 2, salir, +3x+2, bajar al denominador, x+1.
    final ed = EditorController();
    ed.insert(MNode.of(NK.frac));
    ed.insertAtom('x');
    ed.insert(MNode.of(NK.pow));
    ed.insertAtom('2');
    ed.right();
    for (final a in ['+', '3', 'x', '+', '2']) {
      ed.insertAtom(a);
    }
    ed.down();
    for (final a in ['x', '+', '1']) {
      ed.insertAtom(a);
    }
    final req = ed.toRequest();
    final r = await call({'operation': 'simplify', 'expression': req.expression});
    add('Editor visual: fracción (x²+3x+2)/(x+1) construida con botones → x + 2',
        r.exactResult == 'x + 2' && r.conditions.contains('x ≠ -1') && verified(r), 'entrada=${req.expression} | ${show(r)}');
  } catch (e) {
    add('Editor visual: fracción (x²+3x+2)/(x+1) construida con botones → x + 2', false, 'excepcion: $e');
  }
  await expectEngine('Sumatoria Σ k (k=1..10) = 55', {
    'operation': 'sum',
    'expression': 'k',
    'params': {'var': 'k', 'from': '1', 'to': '10'}
  }, (r) => r.exactResult == '55' && verified(r), ms: 60000);
  await expectEngine('Serie Σ 1/k² (k=1..∞) = π²/6', {
    'operation': 'sum',
    'expression': '1/k^2',
    'params': {'var': 'k', 'from': '1', 'to': 'oo'}
  }, (r) => r.exactResult == 'pi^2/6' && verified(r), ms: 60000);
  await expectEngine('Sustitución x=2, y=a+1 en x²+y = a + 5', {
    'operation': 'substitute',
    'expression': 'x^2+y',
    'params': {
      'values': {'x': '2', 'y': 'a+1'}
    }
  }, (r) => r.exactResult == 'a + 5' && verified(r), ms: 60000);
  await expectEngine('Determinante simbólico [[a,b],[c,d]] = ad − bc', {
    'operation': 'matrix_symbolic',
    'structured_input': {
      'a': [
        ['a', 'b'],
        ['c', 'd']
      ]
    },
    'params': {'op': 'det'}
  }, (r) => r.exactResult == 'a*d - b*c' && verified(r), ms: 60000);
  await expectEngine('Lógica: ¬(p ∧ q) = ¬p ∨ ¬q (tabla de verdad)', {'operation': 'logic', 'expression': '~(p & q)'},
      (r) => r.exactResult == '¬p ∨ ¬q' && verified(r), ms: 60000);
  await expectEngine('Conjuntos: [0,2] ∪ [1,3] = [0, 3]', {'operation': 'sets', 'expression': '[0,2] ∪ [1,3]'},
      (r) => r.exactResult == '[0, 3]' && verified(r), ms: 60000);
  await expectEngine('Funciones especiales: gamma(5) + log(8,2) + 50% = 55/2', {
    'operation': 'evaluate',
    'expression': 'gamma(5)+log(8,2)+50%'
  }, (r) => r.exactResult == '55/2' && verified(r), ms: 60000);

  // 6. Persistencia SQLite real: escribir, cerrar, reabrir, leer, borrar.
  final marker = 'autoprueba-${DateTime.now().microsecondsSinceEpoch}';
  try {
    final s1 = await openStore();
    await s1.add(HistoryEntry(
        createdAt: DateTime.now(), kind: 'calculo', operation: 'evaluate', input: marker, result: '2', status: 'success_exact'));
    await s1.close();
    final s2 = await openStore();
    final found = await s2.list(query: marker);
    final ok = found.length == 1 && found.single.result == '2';
    for (final e in found) {
      if (e.id != null) await s2.delete(e.id!);
    }
    final left = await s2.list(query: marker);
    await s2.close();
    add('Historial SQLite: guardar, cerrar, reabrir y recuperar', ok && left.isEmpty,
        'recuperadas=${found.length}, restantes tras borrar=${left.length}');
  } catch (e) {
    add('Historial SQLite: guardar, cerrar, reabrir y recuperar', false, 'excepcion: $e');
  }

  sw.stop();
  return AutotestReport(checks, sw.elapsed, deps);
}
