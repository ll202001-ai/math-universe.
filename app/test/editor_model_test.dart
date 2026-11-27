import 'package:flutter_test/flutter_test.dart';
import 'package:math_universe_app/editor/editor_controller.dart';
import 'package:math_universe_app/editor/math_node.dart';

void type(EditorController c, String s) {
  for (final ch in s.split('')) {
    c.typeChar(ch);
  }
}

void main() {
  test('fraccion construida con botones: (x^2+3x+2)/(x+1)', () {
    final c = EditorController();
    c.insert(MNode.of(NK.frac)); // boton fraccion: cursor en el numerador
    c.insertAtom('x');
    c.insert(MNode.of(NK.pow)); // boton potencia: cursor en el exponente
    c.insertAtom('2');
    c.right(); // sale del exponente
    for (final a in ['+', '3', 'x', '+', '2']) {
      c.insertAtom(a);
    }
    c.down(); // al denominador
    for (final a in ['x', '+', '1']) {
      c.insertAtom(a);
    }
    expect(c.toEngine(), '((x^2+3x+2)/(x+1))');
    expect(c.root.toLatex(), contains(r'\frac{x ^{2} + 3 x + 2}{x + 1}'));
  });

  test('con el teclado fisico: "/" toma lo anterior como numerador y "^" abre exponente', () {
    final c = EditorController();
    type(c, '1/2');
    expect(c.toEngine(), '(1/2)');
    final d = EditorController();
    type(d, 'x^2');
    d.right();
    type(d, '+1');
    expect(d.toEngine(), 'x^2+1');
    final e = EditorController();
    type(e, '(x+1)/3');
    expect(e.toEngine(), '((x+1)/3)');
  });

  test('las palabras se convierten en funciones y griegas; sin no se convierte antes de sinh', () {
    final c = EditorController();
    type(c, 'sin(x)');
    expect(c.toEngine(), 'sin(x)');
    final h = EditorController();
    type(h, 'sinh(x)');
    expect(h.toEngine(), 'sinh(x)');
    final g = EditorController();
    type(g, 'theta+alpha');
    expect(g.toEngine(), 'theta+alpha');
    expect(g.root.toLatex(), contains(r'\theta'));
    final s = EditorController();
    type(s, 'sqrt(9)');
    expect(s.toEngine(), 'sqrt(9)');
    final l = EditorController();
    type(l, 'x<=2');
    expect(l.toEngine(), 'x<=2');
  });

  test('multiplicacion implicita sin ambiguedad', () {
    final c = EditorController();
    type(c, 'xy');
    expect(c.toEngine(), 'x*y');
    final d = EditorController();
    type(d, '2x');
    expect(d.toEngine(), '2x');
    final e = EditorController();
    type(e, 'x(x+1)');
    expect(e.toEngine(), 'x*(x+1)');
    final f = EditorController();
    type(f, 'x^2');
    f.right();
    type(f, '3');
    expect(f.toEngine(), 'x^2*3', reason: 'el exponente no se mezcla con lo que sigue');
  });

  test('borrar no destruye una estructura con contenido: primero entra en ella', () {
    final c = EditorController();
    c.insert(MNode.of(NK.sqrt));
    type(c, '16');
    c.right(); // fuera de la raiz
    c.backspace(); // entra en la raiz
    expect(c.toEngine(), 'sqrt(16)');
    c.backspace();
    expect(c.toEngine(), 'sqrt(1)');
    c.backspace(); // raiz vacia: ahora si se borra al retroceder desde dentro
    c.backspace();
    expect(c.root.isEmpty, isTrue);
  });

  test('deshacer y rehacer', () {
    final c = EditorController();
    type(c, '12');
    c.clear();
    expect(c.root.isEmpty, isTrue);
    c.undo();
    expect(c.toEngine(), '12');
    c.redo();
    expect(c.root.isEmpty, isTrue);
  });

  test('casillas vacias: se informa claramente y no se envia nada', () {
    final c = EditorController();
    c.insert(MNode.of(NK.frac));
    type(c, '1');
    expect(() => c.toEngine(), throwsA(isA<EditorError>().having((e) => e.message, 'mensaje', contains('denominador'))));
  });

  test('plantillas de calculo: integral definida, sumatoria, limite, derivada, matriz y sistema', () {
    final i = EditorController();
    i.insert(MNode.of(NK.integral)); // ranuras: inferior, superior, integrando, variable
    type(i, '0');
    i.right();
    type(i, '1');
    i.right();
    type(i, 'x^2');
    i.right();
    i.right();
    type(i, 'x');
    final ri = i.toRequest();
    expect(ri.operation, 'integrate');
    expect(ri.expression, 'x^2');
    expect(ri.extra, {'variables': ['x'], 'lower': '0', 'upper': '1'});

    final s = EditorController();
    s.insert(MNode.of(NK.sum));
    type(s, 'k');
    s.right();
    type(s, '1');
    s.right();
    type(s, '10');
    s.right();
    type(s, 'k');
    final rs = s.toRequest();
    expect(rs.operation, 'sum');
    expect(rs.params, {'var': 'k', 'from': '1', 'to': '10'});

    final l = EditorController();
    l.insert(MNode.of(NK.lim));
    type(l, 'x');
    l.right();
    type(l, '0');
    l.right();
    type(l, 'sin(x)/x'); // ')' cierra sin(x); '/' convierte sin(x) en numerador
    expect(l.root.items.single.slots[2].toEngine(), '(sin(x)/x)');
    final rl = l.toRequest();
    expect(rl.operation, 'limit');
    expect(rl.extra['point'], '0');

    final m = EditorController();
    m.insert(MNode.of(NK.matrix, rows: 2, cols: 2));
    for (final v in ['1', '2', '3', '4']) {
      type(m, v);
      m.right();
    }
    final rm = m.toRequest();
    expect(rm.operation, 'matrix');
    expect(rm.extra['matrix'], [['1', '2'], ['3', '4']]);
    expect(m.resizeMatrix(dRows: 1), isFalse, reason: 'el cursor ya no esta dentro de la matriz');

    final sy = EditorController();
    sy.insert(MNode.of(NK.system, rows: 2));
    type(sy, '2x+y=5');
    sy.down();
    type(sy, 'x-y=1');
    expect(sy.toRequest().expression, '2x+y=5; x-y=1');
  });

  test('una integral dentro de otra expresion se rechaza con un mensaje claro (no se simula)', () {
    final c = EditorController();
    type(c, '2+');
    c.insert(MNode.of(NK.integral));
    expect(() => c.toRequest(), throwsA(isA<EditorError>()));
  });

  test('matriz: añadir filas y columnas conserva el contenido', () {
    final m = EditorController();
    m.insert(MNode.of(NK.matrix, rows: 2, cols: 2));
    type(m, '7');
    expect(m.resizeMatrix(dCols: 1), isTrue);
    expect(m.root.items.first.cols, 3);
    expect(m.root.items.first.slots[0].toEngine(), '7');
  });

  test('pegar texto y recuperar del historial: el texto lineal se convierte en estructura', () {
    final c = EditorController();
    c.setText('sqrt(x)+abs(-2)+x^(1/2)+log(8,2)+sin(x)^2');
    expect(c.toEngine(), 'sqrt(x)+abs(-2)+x^(1/2)+log(8,2)+sin(x)^2');
    expect(c.root.items.where((n) => n.isStructure).length, greaterThanOrEqualTo(5));
    final d = EditorController();
    d.setText('2x+y=5; x-y=1');
    expect(d.toEngine(), '2x+y=5;x-y=1');
  });

  test('navegacion: flechas entre numerador y denominador y siguiente casilla vacia', () {
    final c = EditorController();
    c.insert(MNode.of(NK.frac));
    c.down();
    type(c, '5');
    c.up();
    type(c, '3');
    expect(c.toEngine(), '(3/5)');
    final r = EditorController();
    r.insert(MNode.of(NK.root));
    r.nextEmpty();
    type(r, '8');
    r.left();
    r.left();
    type(r, '3');
    expect(r.toEngine(), 'root(8,3)');
  });
}
