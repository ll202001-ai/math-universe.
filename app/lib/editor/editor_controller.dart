import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'math_node.dart';

/// Posicion del cursor: camino desde la fila raiz (indice del nodo, indice de la ranura) y posicion en la fila activa.
class EditorCursor {
  EditorCursor(this.path, this.pos);
  final List<(int, int)> path;
  final int pos;
  EditorCursor copy() => EditorCursor([...path], pos);
}

/// Solicitud derivada del editor: operacion propuesta por la estructura (integral, Σ, lim, d/dx, matriz…) o null
/// si la expresion es "normal" (la elige la interfaz), mas la expresion y los parametros del contrato.
class EditorRequest {
  EditorRequest({this.operation, required this.expression, this.params = const {}, this.extra = const {}});
  final String? operation;
  final String expression;
  final Map<String, dynamic> params;
  final Map<String, dynamic> extra;
}

/// Estado y edicion de una expresion. Todas las operaciones son locales (no calculan nada) y deshacibles.
class EditorController extends ChangeNotifier {
  EditorController([MRow? initial]) : _root = initial ?? MRow() {
    _cursor = EditorCursor(const [], _root.items.length);
  }

  MRow _root;
  late EditorCursor _cursor;
  final List<(MRow, EditorCursor)> _undo = [];
  final List<(MRow, EditorCursor)> _redo = [];
  static const _maxUndo = 200;

  MRow get root => _root;
  EditorCursor get cursor => _cursor;
  bool get isEmpty => _root.isEmpty;
  bool get canUndo => _undo.isNotEmpty;
  bool get canRedo => _redo.isNotEmpty;

  // ---------------------------------------------------------------- navegacion del arbol
  MRow _rowAt(List<(int, int)> path) {
    var row = _root;
    for (final (n, s) in path) {
      row = row.items[n].slots[s];
    }
    return row;
  }

  MRow get activeRow => _rowAt(_cursor.path);

  void _snapshot() {
    _undo.add((_root.clone(), _cursor.copy()));
    if (_undo.length > _maxUndo) _undo.removeAt(0);
    _redo.clear();
  }

  void _set(EditorCursor c) {
    _cursor = c;
    notifyListeners();
  }

  // ---------------------------------------------------------------- texto de salida
  String toLatex() => _root.toLatex(
      cursorAt: _cursor.path.isEmpty ? _cursor.pos : null, ctx: LatexCursor(activeRow, _cursor.pos));

  String toLatexPlain() => _root.items.isEmpty ? '' : _root.toLatex();

  /// Texto para el motor (lanza [EditorError] si falta algo o hay una estructura no admitida en esa posicion).
  String toEngine() => _root.toEngine();

  /// Solicitud segun la estructura: si la expresion es UNA integral, sumatoria, productoria, limite, derivada o
  /// matriz, la operacion y sus parametros salen de la propia plantilla.
  EditorRequest toRequest() {
    final items = _root.items;
    if (items.length == 1) {
      final n = items.first;
      String req(int i, String what) {
        final s = n.slots[i].toEngine();
        if (s.isEmpty) throw EditorError('Complete $what (hay una casilla vacía)');
        return s;
      }

      switch (n.kind) {
        case NK.integral:
          final lo = n.slots[0].toEngine(), hi = n.slots[1].toEngine();
          if (lo.isEmpty != hi.isEmpty) throw EditorError('Escriba los dos límites de integración o ninguno');
          return EditorRequest(operation: 'integrate', expression: req(2, 'el integrando'), extra: {
            'variables': [req(3, 'la variable de integración (dx)')],
            if (lo.isNotEmpty) 'lower': lo,
            if (hi.isNotEmpty) 'upper': hi,
          });
        case NK.sum:
        case NK.prod:
          return EditorRequest(
              operation: n.kind == NK.sum ? 'sum' : 'product',
              expression: req(3, 'el término general'),
              params: {'var': req(0, 'la variable'), 'from': req(1, 'el valor inicial'), 'to': req(2, 'el valor final')});
        case NK.lim:
          return EditorRequest(operation: 'limit', expression: req(2, 'la función del límite'), extra: {
            'variables': [req(0, 'la variable del límite')],
            'point': req(1, 'el punto al que tiende'),
          });
        case NK.deriv:
          return EditorRequest(operation: 'differentiate', expression: req(1, 'la función a derivar'), extra: {
            'variables': [req(0, 'la variable de derivación')]
          });
        case NK.matrix:
          return EditorRequest(operation: 'matrix', expression: n.toEngine(), extra: {
            'matrix': [
              for (var r = 0; r < n.rows; r++) [for (var c = 0; c < n.cols; c++) req(r * n.cols + c, 'la matriz')]
            ]
          });
        case NK.system:
          return EditorRequest(operation: 'solve', expression: n.toEngine());
        default:
          break;
      }
    }
    return EditorRequest(expression: toEngine());
  }

  // ---------------------------------------------------------------- edicion
  /// Inserta un nodo en el cursor. Si tiene ranuras, el cursor entra en la primera vacia.
  void insert(MNode node, {bool takePrevious = false}) {
    _snapshot();
    final row = activeRow;
    var pos = _cursor.pos;
    if (takePrevious && pos > 0 && node.kind == NK.frac) {
      final start = _termStart(row, pos);
      var taken = row.items.sublist(start, pos);
      row.items.removeRange(start, pos);
      pos = start;
      // (x+1)/3: la fraccion ya agrupa, los parentesis exteriores sobran
      if (taken.length >= 2 && taken.first.kind == NK.atom && taken.first.text == '(' && taken.last.kind == NK.atom &&
          taken.last.text == ')' && _matchingClose(taken) == taken.length - 1) {
        taken = taken.sublist(1, taken.length - 1);
      }
      node.slots[0].items.addAll(taken);
    }
    row.items.insert(pos, node);
    if (node.isStructure && node.slots.isNotEmpty) {
      final first = node.slots.indexWhere((s) => s.isEmpty);
      final slot = first < 0 ? node.slots.length - 1 : first;
      _set(EditorCursor([..._cursor.path, (pos, slot)], node.slots[slot].items.length));
    } else {
      _set(EditorCursor(_cursor.path, pos + 1));
    }
  }

  void insertAtom(String engine, [String? latex]) => insert(MNode.atom(engine, latex));

  int _matchingClose(List<MNode> items) {
    var depth = 0;
    for (var i = 0; i < items.length; i++) {
      final n = items[i];
      if (n.kind != NK.atom) continue;
      if (n.text == '(') depth++;
      if (n.text == ')') {
        depth--;
        if (depth == 0) return i;
      }
    }
    return -1;
  }

  /// Parentesis abiertos sin cerrar en la fila activa, antes del cursor.
  int _openParens() {
    var d = 0;
    final row = activeRow;
    for (var i = 0; i < _cursor.pos; i++) {
      final n = row.items[i];
      if (n.kind == NK.atom && n.text == '(') d++;
      if (n.kind == NK.atom && n.text == ')') d--;
    }
    return d;
  }

  /// Inicio del "termino" anterior al cursor (para que '/' convierta lo anterior en numerador).
  int _termStart(MRow row, int pos) {
    var i = pos - 1;
    final last = row.items[i];
    if (last.kind == NK.atom && last.text == ')') {
      var depth = 0;
      for (; i >= 0; i--) {
        final t = row.items[i].text;
        if (row.items[i].kind == NK.atom && t == ')') depth++;
        if (row.items[i].kind == NK.atom && t == '(') depth--;
        if (depth == 0) break;
      }
      return i < 0 ? 0 : (i > 0 && row.items[i - 1].kind == NK.func ? i - 1 : i);
    }
    bool termish(MNode n) =>
        n.isStructure || (n.kind == NK.atom && RegExp(r'^([0-9.]|[A-Za-z_]\w*)$').hasMatch(n.text) && n.text != 'oo');
    while (i >= 0 && termish(row.items[i])) {
      i--;
    }
    return i + 1;
  }

  /// Borrar (⌫): nunca destruye nada fuera del cursor. Una estructura con contenido se abre en vez de borrarse.
  void backspace() {
    final row = activeRow;
    final pos = _cursor.pos;
    if (pos > 0) {
      final prev = row.items[pos - 1];
      if (prev.isStructure && !prev.allEmpty) {
        final slot = prev.slots.lastIndexWhere((s) => s.isNotEmpty);
        _set(EditorCursor([..._cursor.path, (pos - 1, slot)], prev.slots[slot].items.length));
        return;
      }
      _snapshot();
      row.items.removeAt(pos - 1);
      _set(EditorCursor(_cursor.path, pos - 1));
      return;
    }
    if (_cursor.path.isEmpty) return;
    final (ni, si) = _cursor.path.last;
    final parentPath = _cursor.path.sublist(0, _cursor.path.length - 1);
    final parent = _rowAt(parentPath);
    final node = parent.items[ni];
    if (node.allEmpty) {
      _snapshot();
      parent.items.removeAt(ni);
      _set(EditorCursor(parentPath, ni));
    } else if (si > 0) {
      _set(EditorCursor([...parentPath, (ni, si - 1)], node.slots[si - 1].items.length));
    } else {
      _set(EditorCursor(parentPath, ni));
    }
  }

  void clear() {
    if (_root.isEmpty) return;
    _snapshot();
    _root = MRow();
    _set(EditorCursor(const [], 0));
  }

  void setRow(MRow row) {
    _snapshot();
    _root = row;
    _set(EditorCursor(const [], row.items.length));
  }

  void setText(String text) => setRow(parseLinear(text));

  /// Sustituye la expresion sin registrar un paso de deshacer (sincronizacion con la linea de texto).
  void replaceQuiet(MRow row) {
    _root = row;
    _set(EditorCursor(const [], row.items.length));
  }

  void undo() {
    if (_undo.isEmpty) return;
    _redo.add((_root.clone(), _cursor.copy()));
    final (r, c) = _undo.removeLast();
    _root = r;
    _set(c);
  }

  void redo() {
    if (_redo.isEmpty) return;
    _undo.add((_root.clone(), _cursor.copy()));
    final (r, c) = _redo.removeLast();
    _root = r;
    _set(c);
  }

  // ---------------------------------------------------------------- flechas
  void left() {
    final row = activeRow;
    final pos = _cursor.pos;
    if (pos > 0) {
      final prev = row.items[pos - 1];
      if (prev.isStructure && prev.slots.isNotEmpty) {
        final s = prev.slots.length - 1;
        _set(EditorCursor([..._cursor.path, (pos - 1, s)], prev.slots[s].items.length));
      } else {
        _set(EditorCursor(_cursor.path, pos - 1));
      }
      return;
    }
    if (_cursor.path.isEmpty) return;
    final (ni, si) = _cursor.path.last;
    final parentPath = _cursor.path.sublist(0, _cursor.path.length - 1);
    if (si > 0) {
      final node = _rowAt(parentPath).items[ni];
      _set(EditorCursor([...parentPath, (ni, si - 1)], node.slots[si - 1].items.length));
    } else {
      _set(EditorCursor(parentPath, ni));
    }
  }

  void right() {
    final row = activeRow;
    final pos = _cursor.pos;
    if (pos < row.items.length) {
      final next = row.items[pos];
      if (next.isStructure && next.slots.isNotEmpty) {
        _set(EditorCursor([..._cursor.path, (pos, 0)], 0));
      } else {
        _set(EditorCursor(_cursor.path, pos + 1));
      }
      return;
    }
    if (_cursor.path.isEmpty) return;
    final (ni, si) = _cursor.path.last;
    final parentPath = _cursor.path.sublist(0, _cursor.path.length - 1);
    final node = _rowAt(parentPath).items[ni];
    if (si + 1 < node.slots.length) {
      _set(EditorCursor([...parentPath, (ni, si + 1)], 0));
    } else {
      _set(EditorCursor(parentPath, ni + 1));
    }
  }

  void _vertical(bool up) {
    for (var d = _cursor.path.length - 1; d >= 0; d--) {
      final (ni, si) = _cursor.path[d];
      final parentPath = _cursor.path.sublist(0, d);
      final node = _rowAt(parentPath).items[ni];
      final target = up ? node.slotAbove(si) : node.slotBelow(si);
      if (target != null) {
        _set(EditorCursor([...parentPath, (ni, target)], node.slots[target].items.length));
        return;
      }
    }
  }

  void up() => _vertical(true);
  void down() => _vertical(false);

  /// Salta a la siguiente casilla vacia (Tab), o al final.
  void nextEmpty() {
    final slots = <List<(int, int)>>[];
    void walk(MRow r, List<(int, int)> p) {
      for (var i = 0; i < r.items.length; i++) {
        final n = r.items[i];
        for (var s = 0; s < n.slots.length; s++) {
          final pp = [...p, (i, s)];
          if (n.slots[s].isEmpty) slots.add(pp);
          walk(n.slots[s], pp);
        }
      }
    }

    walk(_root, const []);
    String key(List<(int, int)> p) => p.map((e) => '${e.$1}.${e.$2}').join('/');
    final cur = key(_cursor.path);
    final idx = slots.indexWhere((p) => key(p).compareTo(cur) > 0);
    if (idx >= 0) {
      _set(EditorCursor(slots[idx], 0));
    } else if (slots.isNotEmpty) {
      _set(EditorCursor(slots.first, 0));
    } else {
      _set(EditorCursor(const [], _root.items.length));
    }
  }

  /// Cursor al final de la expresion (toque en el area de trabajo).
  void moveToEnd() => _set(EditorCursor(const [], _root.items.length));

  // ---------------------------------------------------------------- matrices
  /// Añade una fila o columna a la matriz que contiene el cursor.
  bool resizeMatrix({int dRows = 0, int dCols = 0}) {
    for (var d = _cursor.path.length - 1; d >= 0; d--) {
      final (ni, _) = _cursor.path[d];
      final parentPath = _cursor.path.sublist(0, d);
      final parent = _rowAt(parentPath);
      final node = parent.items[ni];
      if (node.kind != NK.matrix) continue;
      final r = node.rows + dRows, c = node.cols + dCols;
      if (r < 1 || c < 1 || r > 10 || c > 10) return false;
      _snapshot();
      final fresh = MNode.of(NK.matrix, rows: r, cols: c);
      for (var i = 0; i < node.rows && i < r; i++) {
        for (var j = 0; j < node.cols && j < c; j++) {
          fresh.slots[i * c + j].items.addAll(node.slots[i * node.cols + j].items);
        }
      }
      parent.items[ni] = fresh;
      _set(EditorCursor([...parentPath, (ni, 0)], fresh.slots[0].items.length));
      return true;
    }
    return false;
  }

  // ---------------------------------------------------------------- teclado fisico
  static const _autoNames = [
    'asinh', 'acosh', 'atanh', 'sqrt', 'asin', 'acos', 'atan', 'sinh', 'cosh', 'tanh', 'gamma', 'zeta', 'sin', 'cos',
    'tan', 'sec', 'csc', 'cot', 'exp', 'erf', 'abs', 'log', 'ln',
  ];

  /// Escritura con el teclado fisico, al estilo de un editor matematico: '/' fraccion con lo anterior, '^' exponente,
  /// '_' subindice, letras que forman una funcion (sin, sqrt…) o una griega (alpha…) se convierten solas.
  /// Devuelve true si la tecla se ha consumido.
  bool handleKey(KeyEvent e) {
    if (e is! KeyDownEvent && e is! KeyRepeatEvent) return false;
    final k = e.logicalKey;
    final ctrl = HardwareKeyboard.instance.isControlPressed || HardwareKeyboard.instance.isMetaPressed;
    if (ctrl && k == LogicalKeyboardKey.keyZ) {
      HardwareKeyboard.instance.isShiftPressed ? redo() : undo();
      return true;
    }
    if (ctrl && k == LogicalKeyboardKey.keyY) {
      redo();
      return true;
    }
    if (ctrl) return false;
    if (k == LogicalKeyboardKey.arrowLeft) return _do(left);
    if (k == LogicalKeyboardKey.arrowRight) return _do(right);
    if (k == LogicalKeyboardKey.arrowUp) return _do(up);
    if (k == LogicalKeyboardKey.arrowDown) return _do(down);
    if (k == LogicalKeyboardKey.backspace) return _do(backspace);
    if (k == LogicalKeyboardKey.tab) return _do(nextEmpty);
    if (k == LogicalKeyboardKey.escape) return _do(moveToEnd);
    final ch = e.character;
    if (ch == null || ch.isEmpty || ch.codeUnitAt(0) < 32) return false;
    typeChar(ch);
    return true;
  }

  bool _do(VoidCallback f) {
    f();
    return true;
  }

  /// Nombres que son prefijo de otro (sin → sinh): se convierten cuando llega el siguiente caracter.
  static const _ambiguous = {'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'erf'};
  bool _justOpened = false;

  /// Un caracter escrito (teclado fisico o pegado caracter a caracter).
  void typeChar(String ch) {
    final pending = _pendingWord();
    if (pending != null && ch != 'h' && !(pending == 'erf' && ch == 'c')) {
      _convertWord(pending);
      if (ch == '(' || ch == ' ') return; // el '(' ya lo pone la funcion
    } else if (_justOpened && ch == '(') {
      _justOpened = false;
      return;
    }
    _justOpened = false;
    if (ch == ')' && _openParens() <= 0 && _cursor.path.isNotEmpty) {
      // cierra la funcion/raiz/valor absoluto en la que se esta escribiendo
      final (ni, _) = _cursor.path.last;
      final parentPath = _cursor.path.sublist(0, _cursor.path.length - 1);
      final kind = _rowAt(parentPath).items[ni].kind;
      if (const {NK.func, NK.func2, NK.sqrt, NK.abs, NK.floor, NK.ceil, NK.logb, NK.root}.contains(kind)) {
        _set(EditorCursor(parentPath, ni + 1));
        return;
      }
    }
    switch (ch) {
      case ' ':
        return;
      case '/':
        insert(MNode.of(NK.frac), takePrevious: true);
        return;
      case '^':
        insert(MNode.of(NK.pow));
        return;
      case '_':
        insert(MNode.of(NK.sub));
        return;
      case '|':
        insert(MNode.of(NK.abs));
        return;
    }
    if (ch == '=' && _lastAtom() == '<') return _replaceLast('<=');
    if (ch == '=' && _lastAtom() == '>') return _replaceLast('>=');
    insertAtom(ch);
    if (RegExp(r'[A-Za-z]').hasMatch(ch)) {
      final w = _wordBeforeCursor();
      final name = _matchName(w);
      if (name != null && !_ambiguous.contains(name)) _convertWord(name);
    }
  }

  String _wordBeforeCursor() {
    final row = activeRow;
    var word = '';
    var i = _cursor.pos;
    while (i > 0 && row.items[i - 1].kind == NK.atom && RegExp(r'^[A-Za-z]$').hasMatch(row.items[i - 1].text)) {
      i--;
      word = row.items[i].text + word;
    }
    return word;
  }

  static final List<String> _names = ([..._autoNames, ...greekLatex.keys, 'pi']..sort((a, b) => b.length.compareTo(a.length)));

  String? _matchName(String word) {
    for (final n in _names) {
      if (n.length > 1 && word.endsWith(n)) return n;
    }
    return null;
  }

  /// Si justo antes del cursor hay un nombre ambiguo completo (sin, cos…), lo devuelve.
  String? _pendingWord() {
    final n = _matchName(_wordBeforeCursor());
    return (n != null && _ambiguous.contains(n)) ? n : null;
  }

  void _convertWord(String name) {
    final row = activeRow;
    final pos = _cursor.pos;
    final s = pos - name.length;
    _snapshot();
    row.items.removeRange(s, pos);
    final MNode node = switch (name) {
      'sqrt' => MNode.of(NK.sqrt),
      'abs' => MNode.of(NK.abs),
      _ when _autoNames.contains(name) => funcNode(name),
      _ => MNode.atom(name),
    };
    row.items.insert(s, node);
    if (node.isStructure) {
      _justOpened = true;
      _set(EditorCursor([..._cursor.path, (s, 0)], 0));
    } else {
      _set(EditorCursor(_cursor.path, s + 1));
    }
  }

  /// Termina una palabra pendiente (p. ej. al calcular con «sin» recien escrito).
  void flushPending() {
    final p = _pendingWord();
    if (p != null) _convertWord(p);
  }

  String? _lastAtom() {
    final row = activeRow;
    if (_cursor.pos == 0) return null;
    final n = row.items[_cursor.pos - 1];
    return n.kind == NK.atom ? n.text : null;
  }

  void _replaceLast(String engine) {
    final row = activeRow;
    _snapshot();
    row.items[_cursor.pos - 1] = MNode.atom(engine);
    notifyListeners();
  }
}
