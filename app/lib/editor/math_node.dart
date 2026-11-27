/// Modelo del editor matematico estructurado (MATH UNIVERSE 0.7.0).
///
/// Una expresion es una fila ([MRow]) de nodos ([MNode]). Los nodos estructurados (fraccion, raiz, potencia,
/// integral, matriz...) tienen ranuras, que son a su vez filas editables. De este arbol salen dos textos:
///  * [MRow.toLatex]: lo que se DIBUJA (con cursor y casillas vacias), con la misma notacion que los resultados.
///  * [MRow.toEngine]: lo que se ENVIA al motor (sintaxis del contrato). Nada se calcula aqui.
library;

enum NK { atom, frac, pow, sub, sqrt, root, abs, floor, ceil, func, func2, logb, integral, sum, prod, lim, deriv, matrix, system }

/// Error de construccion: la expresion no se puede enviar tal como esta (se explica al usuario; no se simula nada).
class EditorError implements Exception {
  EditorError(this.message);
  final String message;
  @override
  String toString() => message;
}

class MRow {
  MRow([List<MNode>? items]) : items = items ?? [];
  final List<MNode> items;

  bool get isEmpty => items.isEmpty;
  bool get isNotEmpty => items.isNotEmpty;
  MRow clone() => MRow([for (final n in items) n.clone()]);

  /// LaTeX de la fila. [cursorAt] = posicion del cursor si esta fila es la activa.
  String toLatex({int? cursorAt, LatexCursor? ctx}) {
    final b = StringBuffer();
    for (var i = 0; i <= items.length; i++) {
      if (cursorAt == i) b.write(cursorLatex);
      if (i == items.length) break;
      b.write(items[i].toLatex(ctx));
      b.write(' ');
    }
    if (items.isEmpty && cursorAt == null) return emptySlotLatex;
    return b.toString().trim();
  }

  /// Texto para el motor. Inserta '*' donde la yuxtaposicion seria ambigua (xy, x2, x(…)).
  String toEngine() {
    final b = StringBuffer();
    String? prevEnd;
    for (final n in items) {
      final s = n.toEngine();
      if (s.isEmpty) continue;
      final start = _startType(n, s);
      if (prevEnd != null && _needsStar(prevEnd, start)) b.write('*');
      b.write(s);
      prevEnd = _endType(n, s);
    }
    return b.toString();
  }

  /// Fila "simple": un solo numero o identificador (no necesita parentesis como exponente, numerador...).
  bool get isSimple {
    if (items.length == 1 &&
        const {NK.func, NK.func2, NK.sqrt, NK.root, NK.abs, NK.floor, NK.ceil, NK.logb}.contains(items.first.kind)) {
      return true; // ya va entre parentesis: sin(x), sqrt(2)...
    }
    final s = toEngine();
    return RegExp(r'^([0-9]+(\.[0-9]+)?|[A-Za-z_][A-Za-z_0-9]*)$').hasMatch(s);
  }

  Map<String, dynamic> toJson() => {'i': [for (final n in items) n.toJson()]};
  static MRow fromJson(Map<String, dynamic> j) =>
      MRow([for (final n in (j['i'] as List)) MNode.fromJson(Map<String, dynamic>.from(n as Map))]);
}

const cursorLatex = r'\textcolor{#2979FF}{\vert}';
const emptySlotLatex = r'\textcolor{#9E9E9E}{\square}';

class LatexCursor {
  LatexCursor(this.row, this.pos);
  final MRow row;
  final int pos;
}

String _slotLatex(MRow r, LatexCursor? c) {
  if (c != null && identical(c.row, r)) return r.toLatex(cursorAt: c.pos, ctx: c);
  return r.toLatex(ctx: c);
}

String _startType(MNode n, String s) {
  if (n.kind == NK.pow || n.kind == NK.sub) return 'attach';
  final ch = s[0];
  if (RegExp(r'[0-9.]').hasMatch(ch)) return 'd';
  if (RegExp(r'[A-Za-z_]').hasMatch(ch)) return 'l';
  if (ch == '(' || ch == '[') return 'p';
  return 'o';
}

String _endType(MNode n, String s) {
  if (n.kind == NK.pow) return 'c';
  if (n.kind == NK.sub) return 'l';
  final ch = s[s.length - 1];
  if (RegExp(r'[0-9.]').hasMatch(ch)) return 'd';
  if (RegExp(r'[A-Za-z_]').hasMatch(ch)) return 'l';
  if (ch == ')' || ch == ']' || ch == '!' || ch == '%') return 'c';
  return 'o';
}

bool _needsStar(String prevEnd, String nextStart) {
  if (nextStart == 'attach') return false;
  if (prevEnd == 'l') return nextStart == 'l' || nextStart == 'd' || nextStart == 'p';
  if (prevEnd == 'c') return nextStart == 'd';
  return false;
}

String _wrap(MRow r) => r.isSimple ? r.toEngine() : '(${r.toEngine()})';

String _req(MRow r, String what) {
  final s = r.toEngine();
  if (s.isEmpty) throw EditorError('Complete $what (hay una casilla vacía)');
  return s;
}

/// Atomo = un simbolo indivisible: digito, letra, operador, constante, griega...
/// [text] es lo que va al motor; [tex] lo que se dibuja.
class MNode {
  MNode(this.kind, {this.text = '', this.tex = '', List<MRow>? slots, this.rows = 0, this.cols = 0}) : slots = slots ?? [];
  final NK kind;
  final String text;
  final String tex;
  final List<MRow> slots;
  final int rows;
  final int cols;

  factory MNode.atom(String engine, [String? latex]) => MNode(NK.atom, text: engine, tex: latex ?? atomLatex(engine));
  factory MNode.of(NK k, {String name = '', String tex = '', int rows = 0, int cols = 0}) {
    final n = switch (k) {
      NK.frac || NK.root || NK.func2 || NK.logb || NK.deriv => 2,
      NK.lim => 3,
      NK.integral || NK.sum || NK.prod => 4,
      NK.matrix => rows * cols,
      NK.system => rows,
      _ => 1,
    };
    return MNode(k, text: name, tex: tex, slots: [for (var i = 0; i < n; i++) MRow()], rows: rows, cols: cols);
  }

  MNode clone() => MNode(kind, text: text, tex: tex, slots: [for (final s in slots) s.clone()], rows: rows, cols: cols);

  bool get isStructure => kind != NK.atom;
  bool get allEmpty => slots.every((s) => s.isEmpty);

  /// Orden de navegacion vertical: ranura de arriba/abajo de una ranura dada (o null).
  int? slotAbove(int i) => switch (kind) {
        NK.frac => i == 1 ? 0 : null,
        NK.integral => i == 0 ? 1 : null,
        NK.sum || NK.prod => (i == 0 || i == 1) ? 2 : null,
        NK.matrix => i - cols >= 0 ? i - cols : null,
        NK.system => i - 1 >= 0 ? i - 1 : null,
        _ => null,
      };
  int? slotBelow(int i) => switch (kind) {
        NK.frac => i == 0 ? 1 : null,
        NK.integral => i == 1 ? 0 : null,
        NK.sum || NK.prod => i == 2 ? 1 : null,
        NK.matrix => i + cols < slots.length ? i + cols : null,
        NK.system => i + 1 < slots.length ? i + 1 : null,
        _ => null,
      };

  String toLatex(LatexCursor? c) {
    String s(int i) => _slotLatex(slots[i], c);
    switch (kind) {
      case NK.atom:
        return tex;
      case NK.frac:
        return '\\frac{${s(0)}}{${s(1)}}';
      case NK.pow:
        return '^{${s(0)}}';
      case NK.sub:
        return '_{${s(0)}}';
      case NK.sqrt:
        return '\\sqrt{${s(0)}}';
      case NK.root:
        return '\\sqrt[${s(0)}]{${s(1)}}';
      case NK.abs:
        return '\\left|${s(0)}\\right|';
      case NK.floor:
        return '\\left\\lfloor ${s(0)}\\right\\rfloor';
      case NK.ceil:
        return '\\left\\lceil ${s(0)}\\right\\rceil';
      case NK.func:
        return '$tex\\left(${s(0)}\\right)';
      case NK.func2:
        return '$tex\\left(${s(0)},\\,${s(1)}\\right)';
      case NK.logb:
        return '\\log_{${s(0)}}\\left(${s(1)}\\right)';
      case NK.integral:
        final lo = slots[0].isEmpty && slots[1].isEmpty && !_cursorIn(c, 0) && !_cursorIn(c, 1);
        return lo ? '\\int ${s(2)}\\,d${s(3)}' : '\\int_{${s(0)}}^{${s(1)}} ${s(2)}\\,d${s(3)}';
      case NK.sum:
        return '\\sum_{${s(0)}=${s(1)}}^{${s(2)}} ${s(3)}';
      case NK.prod:
        return '\\prod_{${s(0)}=${s(1)}}^{${s(2)}} ${s(3)}';
      case NK.lim:
        return '\\lim_{${s(0)}\\to ${s(1)}} ${s(2)}';
      case NK.deriv:
        return '\\frac{d}{d${s(0)}}\\left(${s(1)}\\right)';
      case NK.matrix:
        final b = StringBuffer('\\begin{pmatrix}');
        for (var r = 0; r < rows; r++) {
          b.write([for (var k = 0; k < cols; k++) s(r * cols + k)].join(' & '));
          if (r < rows - 1) b.write(' \\\\ ');
        }
        return '$b\\end{pmatrix}';
      case NK.system:
        return '\\begin{cases}${[for (var i = 0; i < slots.length; i++) s(i)].join(' \\\\ ')}\\end{cases}';
    }
  }

  bool _cursorIn(LatexCursor? c, int i) => c != null && identical(c.row, slots[i]);

  String toEngine() {
    switch (kind) {
      case NK.atom:
        return text;
      case NK.frac:
        return '(${_wrap(MRow([..._nonEmpty(0, 'el numerador')]))}/${_wrap(MRow([..._nonEmpty(1, 'el denominador')]))})';
      case NK.pow:
        return '^${_wrap(MRow([..._nonEmpty(0, 'el exponente')]))}';
      case NK.sub:
        final s = _req(slots[0], 'el subíndice');
        if (!RegExp(r'^[A-Za-z0-9]+$').hasMatch(s)) throw EditorError('El subíndice debe ser un número o letras (p. ej. x₁)');
        return '_$s';
      case NK.sqrt:
        return 'sqrt(${_req(slots[0], 'la raíz')})';
      case NK.root:
        return 'root(${_req(slots[1], 'el radicando')},${_req(slots[0], 'el índice de la raíz')})';
      case NK.abs:
        return 'abs(${_req(slots[0], 'el valor absoluto')})';
      case NK.floor:
        return 'floor(${_req(slots[0], 'la parte entera')})';
      case NK.ceil:
        return 'ceil(${_req(slots[0], 'el techo')})';
      case NK.func:
        return '$text(${_req(slots[0], 'el argumento de $text')})';
      case NK.func2:
        return '$text(${_req(slots[0], 'el primer argumento de $text')},${_req(slots[1], 'el segundo argumento de $text')})';
      case NK.logb:
        return 'log(${_req(slots[1], 'el argumento del logaritmo')},${_req(slots[0], 'la base del logaritmo')})';
      case NK.matrix:
        return '[${[
          for (var r = 0; r < rows; r++) '[${[for (var k = 0; k < cols; k++) _req(slots[r * cols + k], 'la matriz')].join(',')}]'
        ].join(',')}]';
      case NK.system:
        return [for (final s in slots) _req(s, 'la ecuación del sistema')].join('; ');
      case NK.integral:
      case NK.sum:
      case NK.prod:
      case NK.lim:
      case NK.deriv:
        throw EditorError('${_calcName()} debe ocupar toda la expresión: el motor todavía no admite '
            '${_calcName().toLowerCase()} dentro de otra expresión.');
    }
  }

  List<MNode> _nonEmpty(int i, String what) {
    if (slots[i].isEmpty) throw EditorError('Complete $what (hay una casilla vacía)');
    return slots[i].items;
  }

  String _calcName() => switch (kind) {
        NK.integral => 'La integral',
        NK.sum => 'La sumatoria',
        NK.prod => 'La productoria',
        NK.lim => 'El límite',
        _ => 'La derivada',
      };

  Map<String, dynamic> toJson() => {
        'k': kind.name,
        if (text.isNotEmpty) 't': text,
        if (tex.isNotEmpty) 'x': tex,
        if (slots.isNotEmpty) 's': [for (final s in slots) s.toJson()],
        if (rows != 0) 'r': rows,
        if (cols != 0) 'c': cols,
      };

  static MNode fromJson(Map<String, dynamic> j) => MNode(NK.values.byName(j['k'] as String),
      text: (j['t'] ?? '') as String,
      tex: (j['x'] ?? '') as String,
      slots: [for (final s in (j['s'] as List? ?? const [])) MRow.fromJson(Map<String, dynamic>.from(s as Map))],
      rows: (j['r'] ?? 0) as int,
      cols: (j['c'] ?? 0) as int);
}

/// Simbolos griegos y constantes: nombre para el motor → LaTeX.
const greekLatex = <String, String>{
  'alpha': r'\alpha', 'beta': r'\beta', 'gamma': r'\gamma', 'delta': r'\delta', 'epsilon': r'\varepsilon',
  'zeta': r'\zeta', 'eta': r'\eta', 'theta': r'\theta', 'kappa': r'\kappa', 'lambda': r'\lambda', 'mu': r'\mu',
  'nu': r'\nu', 'xi': r'\xi', 'rho': r'\rho', 'sigma': r'\sigma', 'tau': r'\tau', 'phi': r'\varphi', 'chi': r'\chi',
  'psi': r'\psi', 'omega': r'\omega', 'Gamma': r'\Gamma', 'Delta': r'\Delta', 'Theta': r'\Theta', 'Lambda': r'\Lambda',
  'Sigma': r'\Sigma', 'Phi': r'\Phi', 'Psi': r'\Psi', 'Omega': r'\Omega',
};

/// LaTeX de un atomo a partir de su texto para el motor.
String atomLatex(String e) {
  const ops = <String, String>{
    '*': r'\cdot', '/': r'\div', '-': '-', '+': '+', '=': '=', '<': '<', '>': '>', '<=': r'\le', '>=': r'\ge',
    'pi': r'\pi', 'oo': r'\infty', '(': r'\left(', ')': r'\right)', '[': r'\lbrack', ']': r'\rbrack', '{': r'\lbrace',
    '}': r'\rbrace', ',': r',\,', ';': r';\;', '%': r'\%', '!': '!', "'": "'", 'i': r'\mathrm{i}', 'e': r'\mathrm{e}',
    '∧': r'\land', '∨': r'\lor', '¬': r'\lnot', '→': r'\rightarrow', '↔': r'\leftrightarrow', '⊕': r'\oplus',
    '∪': r'\cup', '∩': r'\cap', '\\': r'\setminus', '∅': r'\varnothing', '.': '.',
  };
  if (ops.containsKey(e)) {
    // ( ) sueltos: sin \left/\right (no siempre estan emparejados mientras se escribe)
    if (e == '(') return '(';
    if (e == ')') return ')';
    return ops[e]!;
  }
  if (greekLatex.containsKey(e)) return greekLatex[e]!;
  return e;
}

/// Funciones de un argumento: nombre para el motor → LaTeX.
const funcLatex = <String, String>{
  'sin': r'\sin', 'cos': r'\cos', 'tan': r'\tan', 'sec': r'\sec', 'csc': r'\csc', 'cot': r'\cot',
  'asin': r'\sin^{-1}', 'acos': r'\cos^{-1}', 'atan': r'\tan^{-1}', 'sinh': r'\sinh', 'cosh': r'\cosh', 'tanh': r'\tanh',
  'asinh': r'\sinh^{-1}', 'acosh': r'\cosh^{-1}', 'atanh': r'\tanh^{-1}', 'ln': r'\ln', 'log': r'\log', 'exp': r'\exp',
  'gamma': r'\Gamma', 'erf': r'\operatorname{erf}', 'erfc': r'\operatorname{erfc}', 'zeta': r'\zeta',
  'cbrt': r'\operatorname{cbrt}', 'sgn': r'\operatorname{sgn}',
};

const func2Latex = <String, String>{'beta': r'\mathrm{B}', 'besselj': r'J', 'gcd': r'\gcd', 'lcm': r'\operatorname{lcm}', 'mod': r'\operatorname{mod}'};

MNode funcNode(String name) => MNode(NK.func, text: name, tex: funcLatex[name] ?? '\\operatorname{$name}', slots: [MRow()]);
MNode func2Node(String name) => MNode(NK.func2, text: name, tex: func2Latex[name] ?? '\\operatorname{$name}', slots: [MRow(), MRow()]);

/// Texto lineal → arbol (para pegar, para el historial y para la linea de texto). Reconoce funciones
/// `nombre(...)`, `sqrt(...)`, `abs(...)`, `^` con un termino o un grupo, y simbolos griegos. Todo lo demas son atomos.
MRow parseLinear(String text) {
  final p = _LinearParser(text.replaceAll(' ', ''));
  return p.row(null);
}

class _LinearParser {
  _LinearParser(this.s);
  final String s;
  int i = 0;

  static final _ident = RegExp(r'[A-Za-z_][A-Za-z_0-9]*');

  MRow row(String? until) {
    final out = <MNode>[];
    while (i < s.length) {
      final ch = s[i];
      if (until != null && (ch == until || (until == ',' && ch == ')'))) break;
      if (ch == '^') {
        i++;
        out.add(MNode(NK.pow, slots: [_operand()]));
        continue;
      }
      final m = _ident.matchAsPrefix(s, i);
      if (m != null) {
        final name = m.group(0)!;
        final after = m.end < s.length ? s[m.end] : '';
        if (after == '(' && _knownCall(name)) {
          i = m.end + 1;
          final a = row(',');
          MNode node;
          if (i < s.length && s[i] == ',') {
            i++;
            final b = row(')');
            node = name == 'log' || name == 'ln'
                ? MNode(NK.logb, slots: [b, a])
                : name == 'root'
                    ? MNode(NK.root, slots: [b, a])
                    : MNode(NK.func2, text: name, tex: func2Latex[name] ?? '\\operatorname{$name}', slots: [a, b]);
          } else {
            node = switch (name) {
              'sqrt' => MNode(NK.sqrt, slots: [a]),
              'abs' => MNode(NK.abs, slots: [a]),
              'floor' => MNode(NK.floor, slots: [a]),
              'ceil' => MNode(NK.ceil, slots: [a]),
              _ => MNode(NK.func, text: name, tex: funcLatex[name] ?? '\\operatorname{$name}', slots: [a]),
            };
          }
          if (i < s.length && s[i] == ')') i++;
          out.add(node);
          continue;
        }
        i = m.end;
        if (greekLatex.containsKey(name) || name == 'pi' || name == 'oo' || name.length == 1) {
          out.add(MNode.atom(name));
        } else {
          // nombres de varias letras (x_1, abc): un atomo por letra si son letras sueltas sin subindice
          if (RegExp(r'^[A-Za-z]+$').hasMatch(name)) {
            for (final c in name.split('')) {
              out.add(MNode.atom(c));
            }
          } else {
            out.add(MNode.atom(name, name.replaceAllMapped(RegExp(r'_(\w+)'), (mm) => '_{${mm[1]}}')));
          }
        }
        continue;
      }
      // operadores de dos caracteres
      if (s.startsWith('<=', i) || s.startsWith('>=', i)) {
        out.add(MNode.atom(s.substring(i, i + 2)));
        i += 2;
        continue;
      }
      if (s.startsWith('**', i)) {
        i += 2;
        out.add(MNode(NK.pow, slots: [_operand()]));
        continue;
      }
      out.add(MNode.atom(ch));
      i++;
    }
    return MRow(out);
  }

  /// Operando de '^': un grupo (…) entero o un termino (numero/identificador, con signo opcional).
  MRow _operand() {
    if (i < s.length && s[i] == '(') {
      i++;
      final r = row(')');
      if (i < s.length && s[i] == ')') i++;
      return r;
    }
    final m = RegExp(r'-?([0-9]+(\.[0-9]+)?|[A-Za-z_][A-Za-z_0-9]*)').matchAsPrefix(s, i);
    if (m == null) return MRow();
    i = m.end;
    return parseLinear(m.group(0)!);
  }

  bool _knownCall(String n) =>
      funcLatex.containsKey(n) || func2Latex.containsKey(n) || const {'sqrt', 'abs', 'floor', 'ceil', 'root', 'log', 'ln'}.contains(n);
}
