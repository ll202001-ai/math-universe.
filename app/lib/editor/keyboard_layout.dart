import 'editor_controller.dart';
import 'math_node.dart';

/// Acciones que el teclado pide a la pantalla (no al editor): elegir una operacion y/o calcular.
abstract class KeyboardHost {
  void setOperation(String op, {bool calculate = false});
  void calculate();
}

enum KeyStyle { digit, op, struct, func, action, normal }

/// Una tecla: etiqueta (LaTeX si [tex]), nombre para lectores de pantalla y accion sobre el editor.
class MathKey {
  const MathKey(this.label, this.semantics, this.action, {this.tex = true, this.style = KeyStyle.normal, this.id});
  final String label;
  final String semantics;
  final void Function(EditorController c, KeyboardHost h) action;
  final bool tex;
  final KeyStyle style;

  /// Identificador estable para pruebas (por defecto, la etiqueta).
  final String? id;
  String get keyId => id ?? semantics;
}

MathKey _a(String engine, String label, String sem, {KeyStyle style = KeyStyle.normal, bool tex = true}) =>
    MathKey(label, sem, (c, h) => c.insertAtom(engine), style: style, tex: tex);
MathKey _digit(String d) => MathKey(d, d, (c, h) => c.insertAtom(d), style: KeyStyle.digit, tex: false);
MathKey _node(NK k, String label, String sem, {int rows = 0, int cols = 0, String? id}) =>
    MathKey(label, sem, (c, h) => c.insert(MNode.of(k, rows: rows, cols: cols)), style: KeyStyle.struct, id: id);
MathKey _f(String name, String label, [String? sem]) =>
    MathKey(label, sem ?? name, (c, h) => c.insert(funcNode(name)), style: KeyStyle.func);
MathKey _f2(String name, String label, String sem) => MathKey(label, sem, (c, h) => c.insert(func2Node(name)), style: KeyStyle.func);
MathKey _op(String op, String label, String sem, {bool calc = true}) =>
    MathKey(label, sem, (c, h) => h.setOperation(op, calculate: calc), tex: false, style: KeyStyle.action);

/// Plantilla con algunas ranuras ya rellenas (variable de integracion, de la suma…).
MNode _pre(NK k, Map<int, String> fill) {
  final n = MNode.of(k);
  fill.forEach((i, v) => n.slots[i].items.add(MNode.atom(v)));
  return n;
}

void _powWith(EditorController c, String e) {
  c.insert(MNode.of(NK.pow));
  c.insertAtom(e);
  c.right();
}

void _rootIndex(EditorController c, String n) {
  c.insert(MNode.of(NK.root));
  c.insertAtom(n);
  c.right();
}

final keyboardTabs = <String, List<MathKey>>{
  'Básico': [
    _digit('7'), _digit('8'), _digit('9'), _a('/', r'\div', 'dividir', style: KeyStyle.op), _a('(', '(', 'abre paréntesis'),
    _a(')', ')', 'cierra paréntesis'),
    _digit('4'), _digit('5'), _digit('6'), _a('*', r'\times', 'multiplicar', style: KeyStyle.op),
    _node(NK.frac, r'\frac{\square}{\square}', 'fracción'), MathKey(r'\square^{2}', 'al cuadrado', (c, h) => _powWith(c, '2'), style: KeyStyle.struct),
    _digit('1'), _digit('2'), _digit('3'), _a('-', '-', 'menos', style: KeyStyle.op), _node(NK.sqrt, r'\sqrt{\square}', 'raíz cuadrada'),
    _node(NK.pow, r'\square^{\square}', 'potencia'),
    _digit('0'), _a('.', '.', 'punto decimal', style: KeyStyle.digit), _a('=', '=', 'igual'), _a('+', '+', 'más', style: KeyStyle.op),
    _a('pi', r'\pi', 'pi'), _a('e', r'\mathrm{e}', 'número e'),
    _a('x', 'x', 'x'), _a('y', 'y', 'y'), _a('%', r'\%', 'porcentaje'), _a('!', 'n!', 'factorial'),
    _node(NK.abs, r'|\square|', 'valor absoluto'), _node(NK.root, r'\sqrt[n]{\square}', 'raíz n-ésima'),
  ],
  'Álgebra': [
    _a('x', 'x', 'x'), _a('y', 'y', 'y'), _a('z', 'z', 'z'), _a('a', 'a', 'a'), _a('b', 'b', 'b'), _a('c', 'c', 'c'),
    _node(NK.frac, r'\frac{\square}{\square}', 'fracción'), _node(NK.pow, r'\square^{\square}', 'potencia'),
    _node(NK.sub, r'\square_{\square}', 'subíndice'), _node(NK.sqrt, r'\sqrt{\square}', 'raíz cuadrada'),
    _node(NK.root, r'\sqrt[n]{\square}', 'raíz n-ésima'), _node(NK.abs, r'|\square|', 'valor absoluto'),
    _a('(', '(', 'abre paréntesis'), _a(')', ')', 'cierra paréntesis'), _a('[', '[', 'abre corchete'), _a(']', ']', 'cierra corchete'),
    _a('{', r'\{', 'abre llave'), _a('}', r'\}', 'cierra llave'),
    _a('=', '=', 'igual'), _a('<', '<', 'menor'), _a('>', '>', 'mayor'), _a('<=', r'\le', 'menor o igual'),
    _a('>=', r'\ge', 'mayor o igual'), _a('i', r'\mathrm{i}', 'unidad imaginaria'),
    _a(',', ',', 'coma'), _a(';', ';', 'punto y coma'), _f('exp', r'e^{\square}', 'exponencial'),
    MathKey(r'10^{\square}', 'diez elevado a', (c, h) {
      c.insertAtom('1');
      c.insertAtom('0');
      c.insert(MNode.of(NK.pow));
    }, style: KeyStyle.struct),
    _a('n', 'n', 'n'), _a('t', 't', 't'),
  ],
  'Cálculo': [
    MathKey(r'\frac{d}{dx}', 'derivada', (c, h) => c.insert(_pre(NK.deriv, {0: 'x'})), style: KeyStyle.struct),
    MathKey(r'\int\square\,dx', 'integral indefinida', (c, h) {
      c.insert(_pre(NK.integral, {3: 'x'}));
      c.right(); // de la ranura inferior a la superior
      c.right(); // al integrando
    }, style: KeyStyle.struct, id: 'integral'),
    MathKey(r'\int_{a}^{b}', 'integral definida', (c, h) => c.insert(_pre(NK.integral, {3: 'x'})), style: KeyStyle.struct, id: 'integral_definida'),
    MathKey(r'\sum', 'sumatoria', (c, h) => c.insert(_pre(NK.sum, {0: 'k'})), style: KeyStyle.struct),
    MathKey(r'\prod', 'productoria', (c, h) => c.insert(_pre(NK.prod, {0: 'k'})), style: KeyStyle.struct),
    MathKey(r'\lim', 'límite', (c, h) => c.insert(_pre(NK.lim, {0: 'x'})), style: KeyStyle.struct),
    _a('oo', r'\infty', 'infinito'), _a("'", "y'", 'prima (derivada)'), _f('ln', r'\ln', 'logaritmo natural'),
    _node(NK.logb, r'\log_{b}', 'logaritmo en base b'), _f('exp', r'e^{\square}', 'exponencial'), _a('!', 'n!', 'factorial'),
    _a('x', 'x', 'x'), _a('t', 't', 't'), _a('n', 'n', 'n'), _a('k', 'k', 'k'),
    _node(NK.frac, r'\frac{\square}{\square}', 'fracción'), _node(NK.pow, r'\square^{\square}', 'potencia'),
    _op('series', 'Taylor', 'serie de Taylor'), _op('partial', '∂', 'derivada parcial'), _op('gradient', '∇', 'gradiente'),
    _op('implicit_diff', 'dy/dx impl.', 'derivación implícita'), _op('laplace', 'ℒ', 'transformada de Laplace'),
    _op('inverse_laplace', 'ℒ⁻¹', 'Laplace inversa'),
  ],
  'Trigonometría': [
    _f('sin', r'\sin'), _f('cos', r'\cos'), _f('tan', r'\tan'), _f('sec', r'\sec'), _f('csc', r'\csc'), _f('cot', r'\cot'),
    _f('asin', r'\sin^{-1}', 'arcoseno'), _f('acos', r'\cos^{-1}', 'arcocoseno'), _f('atan', r'\tan^{-1}', 'arcotangente'),
    _f('sinh', r'\sinh'), _f('cosh', r'\cosh'), _f('tanh', r'\tanh'),
    _f('asinh', r'\sinh^{-1}', 'arcoseno hiperbólico'), _f('acosh', r'\cosh^{-1}', 'arcocoseno hiperbólico'),
    _f('atanh', r'\tanh^{-1}', 'arcotangente hiperbólica'), _a('pi', r'\pi', 'pi'), _a('theta', r'\theta', 'theta'),
    MathKey(r'\square^{2}', 'al cuadrado', (c, h) => _powWith(c, '2'), style: KeyStyle.struct),
  ],
  'Matrices y vectores': [
    _node(NK.matrix, r'\begin{pmatrix}\square&\square\\\square&\square\end{pmatrix}', 'matriz 2×2', rows: 2, cols: 2, id: 'matriz_2x2'),
    _node(NK.matrix, r'\begin{pmatrix}\square&\square&\square\\\square&\square&\square\\\square&\square&\square\end{pmatrix}', 'matriz 3×3',
        rows: 3, cols: 3, id: 'matriz_3x3'),
    _node(NK.matrix, r'\begin{pmatrix}\square\\\square\end{pmatrix}', 'vector columna 2', rows: 2, cols: 1, id: 'vector_2'),
    _node(NK.matrix, r'\begin{pmatrix}\square\\\square\\\square\end{pmatrix}', 'vector columna 3', rows: 3, cols: 1, id: 'vector_3'),
    MathKey('+ fila', 'añadir fila', (c, h) => c.resizeMatrix(dRows: 1), tex: false),
    MathKey('+ col', 'añadir columna', (c, h) => c.resizeMatrix(dCols: 1), tex: false),
    MathKey('− fila', 'quitar fila', (c, h) => c.resizeMatrix(dRows: -1), tex: false),
    MathKey('− col', 'quitar columna', (c, h) => c.resizeMatrix(dCols: -1), tex: false),
    _op('matrix_det', 'det', 'determinante'), _op('matrix_inverse', 'A⁻¹', 'inversa'),
    _op('matrix_transpose', 'Aᵀ', 'transpuesta'), _op('matrix_rank', 'rango', 'rango'),
    _op('eigen', 'λ, v', 'autovalores y autovectores'), _op('matrix_rref', 'RREF', 'forma escalonada'),
  ],
  'Estadística': [
    _digit('7'), _digit('8'), _digit('9'), _a(',', ',', 'coma'), _a('-', '-', 'menos', style: KeyStyle.op),
    _digit('4'), _digit('5'), _digit('6'), _a('.', '.', 'punto decimal', style: KeyStyle.digit), _node(NK.frac, r'\frac{\square}{\square}', 'fracción'),
    _digit('1'), _digit('2'), _digit('3'), _digit('0'), _op('stats', 'Estadística', 'calcular estadística'),
  ],
  'Ecuaciones': [
    _a('=', '=', 'igual'), _a('<', '<', 'menor'), _a('>', '>', 'mayor'), _a('<=', r'\le', 'menor o igual'),
    _a('>=', r'\ge', 'mayor o igual'), _a('x', 'x', 'x'), _a('y', 'y', 'y'), _a('z', 'z', 'z'),
    _node(NK.system, r'\begin{cases}\square\\\square\end{cases}', 'sistema de 2 ecuaciones', rows: 2, id: 'sistema_2'),
    _node(NK.system, r'\begin{cases}\square\\\square\\\square\end{cases}', 'sistema de 3 ecuaciones', rows: 3, id: 'sistema_3'),
    _a("'", "y'", 'prima'), MathKey("y''", 'segunda derivada', (c, h) {
      c.insertAtom('y');
      c.insertAtom("'");
      c.insertAtom("'");
    }, tex: false),
    _op('solve', 'Resolver', 'resolver'), _op('inequality', 'Inecuación', 'resolver inecuación'),
    _op('ode', 'EDO', 'ecuación diferencial'), _op('substitute', 'Sustituir', 'sustituir valores', calc: false),
  ],
  'Griegas': [
    for (final g in const [
      ('alpha', 'alfa'), ('beta', 'beta'), ('gamma', 'gamma'), ('delta', 'delta'), ('epsilon', 'épsilon'), ('theta', 'theta'),
      ('lambda', 'lambda'), ('mu', 'mu'), ('rho', 'rho'), ('sigma', 'sigma'), ('tau', 'tau'), ('phi', 'fi'), ('omega', 'omega'),
      ('Delta', 'delta mayúscula'), ('Sigma', 'sigma mayúscula'), ('Omega', 'omega mayúscula'), ('Phi', 'fi mayúscula'),
      ('pi', 'pi'),
    ])
      _a(g.$1, greekLatex[g.$1] ?? r'\pi', g.$2),
  ],
  'Lógica y conjuntos': [
    _a('∧', r'\land', 'y lógico'), _a('∨', r'\lor', 'o lógico'), _a('¬', r'\lnot', 'negación'), _a('→', r'\rightarrow', 'implica'),
    _a('↔', r'\leftrightarrow', 'si y solo si'), _a('⊕', r'\oplus', 'o exclusivo'),
    _a('p', 'p', 'p'), _a('q', 'q', 'q'), _a('r', 'r', 'r'), _a('(', '(', 'abre paréntesis'), _a(')', ')', 'cierra paréntesis'),
    _op('logic', 'Lógica', 'simplificar lógica'),
    _a('∪', r'\cup', 'unión'), _a('∩', r'\cap', 'intersección'), _a(r'\', r'\setminus', 'diferencia de conjuntos'),
    _a('∅', r'\varnothing', 'conjunto vacío'), _a('[', '[', 'abre corchete'), _a(']', ']', 'cierra corchete'),
    _a('{', r'\{', 'abre llave'), _a('}', r'\}', 'cierra llave'), _a(',', ',', 'coma'), _a('oo', r'\infty', 'infinito'),
    _op('sets', 'Conjuntos', 'operar conjuntos'),
  ],
  'Funciones especiales': [
    _f('gamma', r'\Gamma', 'función gamma'), _f2('beta', r'\mathrm{B}', 'función beta'), _f('erf', r'\operatorname{erf}', 'función error'),
    _f('erfc', r'\operatorname{erfc}', 'función error complementaria'), _f('zeta', r'\zeta', 'zeta de Riemann'),
    _f2('besselj', r'J_{n}', 'Bessel J'), _node(NK.floor, r'\lfloor\square\rfloor', 'parte entera'),
    _node(NK.ceil, r'\lceil\square\rceil', 'techo'), _node(NK.logb, r'\log_{b}', 'logaritmo en base b'),
    _node(NK.root, r'\sqrt[n]{\square}', 'raíz n-ésima'),
    MathKey(r'\sqrt[3]{\square}', 'raíz cúbica', (c, h) => _rootIndex(c, '3'), style: KeyStyle.struct),
    _f2('mod', r'\operatorname{mod}', 'módulo'), _f2('gcd', r'\gcd', 'máximo común divisor'),
    _f2('lcm', r'\operatorname{lcm}', 'mínimo común múltiplo'), _node(NK.abs, r'|\square|', 'valor absoluto'),
    _a('!', 'n!', 'factorial'), _a('%', r'\%', 'porcentaje'),
  ],
};
