import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import '../editor/editor_controller.dart';
import '../editor/keyboard_layout.dart';
import '../editor/math_editor.dart';
import '../editor/math_keyboard.dart';
import '../editor/math_node.dart';
import 'math_view.dart';
import 'result_view.dart';

/// Hoja de trabajo matematica (0.7.0): varias expresiones en bloques; cada una se construye con el editor visual
/// estructurado (fracciones, raices, potencias, integrales, matrices…) y el teclado de 10 pestañas, o como texto.
/// La herramienta es interpretada y modificable (categorias o busqueda) y tiene opciones contextuales.
/// Todo calculo lo hace el motor local; las instrucciones en espanol se interpretan y se confirman antes de calcular.
class CalculatorPage extends StatefulWidget {
  const CalculatorPage({super.key, required this.engine, required this.store, this.initialExpression, this.initialOperation});
  final EngineClient engine;
  final HistoryStore store;
  final String? initialExpression;
  final String? initialOperation;

  @override
  State<CalculatorPage> createState() => _CalculatorPageState();
}

const _digitsOptions = <int>[15, 30, 50, 100];

/// Un bloque de la hoja de trabajo: su expresion (editor + texto), la operacion elegida y su resultado.
class _Block {
  _Block(this.ed);
  final EditorController ed;
  String text = '';
  bool textSource = false; // true: lo ultimo editado fue la linea de texto (se envia tal cual)
  String? manualOp;
  EngineResponse? resp;
  String? lastInput;
  String? localError;
}

class _CalculatorPageState extends State<CalculatorPage> implements KeyboardHost {
  late final TextEditingController _expr = TextEditingController(text: widget.initialExpression ?? '');
  final List<_Block> _blocks = [];
  int _active = 0;
  bool _syncing = false;
  bool? _showKeyboard;
  final TextEditingController _var = TextEditingController();
  final TextEditingController _point = TextEditingController(text: '0');
  final TextEditingController _order = TextEditingController();
  final TextEditingController _lower = TextEditingController();
  final TextEditingController _upper = TextEditingController();
  final TextEditingController _conds = TextEditingController();
  final FocusNode _editorFocus = FocusNode(debugLabel: 'editor');
  String _category = opCategories.first;
  String _direction = 'both';
  int _digits = 15;
  bool _busy = false;
  Map<String, dynamic>? _interpretation;

  _Block get _b => _blocks[_active];
  EditorController get _ed => _b.ed;
  String? get _manualOp => _b.manualOp;
  set _manualOp(String? v) => _b.manualOp = v;
  EngineResponse? get _resp => _b.resp;
  String? get _lastInput => _b.lastInput;

  @override
  void initState() {
    super.initState();
    _addBlock(text: widget.initialExpression ?? '', op: widget.initialOperation);
    if (_manualOp != null) _category = opSpec(_manualOp!)?.category ?? _category;
    _expr.addListener(_onText);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // teclado visible por defecto si hay altura suficiente (en pantallas bajas se abre con el boton)
    _showKeyboard ??= MediaQuery.of(context).size.height >= 700;
  }

  void _addBlock({String text = '', String? op}) {
    final b = _Block(EditorController());
    b.ed.addListener(() => _onEditor(b));
    if (text.isNotEmpty) {
      b.text = text;
      b.textSource = true;
      b.ed.replaceQuiet(parseLinear(text));
    }
    b.manualOp = op;
    _blocks.add(b);
    _active = _blocks.length - 1;
  }

  void _activate(int i) {
    if (i == _active) return;
    setState(() {
      _active = i;
      _interpretation = null;
      _syncing = true;
      _expr.text = _b.text;
      _syncing = false;
    });
  }

  void _newBlock() {
    setState(() {
      _addBlock();
      _interpretation = null;
      _syncing = true;
      _expr.text = '';
      _syncing = false;
    });
    _editorFocus.requestFocus();
  }

  void _deleteBlock(int i) {
    if (_blocks.length == 1) {
      setState(() {
        _b.ed.clear();
        _b.resp = null;
      });
      return;
    }
    setState(() {
      _blocks.removeAt(i);
      if (_active >= _blocks.length) _active = _blocks.length - 1;
      _syncing = true;
      _expr.text = _b.text;
      _syncing = false;
    });
  }

  /// La linea de texto cambio (el usuario escribio o pego): el editor se reconstruye sin tocar el texto.
  void _onText() {
    if (!mounted || _syncing) return;
    final b = _b;
    b.text = _expr.text;
    b.textSource = true;
    b.localError = null;
    _syncing = true;
    if (looksLikeNaturalLanguage(_expr.text)) {
      b.ed.replaceQuiet(MRow());
    } else {
      b.ed.replaceQuiet(parseLinear(_expr.text));
    }
    _syncing = false;
    setState(() => _interpretation = null);
  }

  /// El editor visual cambio: la linea de texto muestra lo que se enviara al motor.
  void _onEditor(_Block b) {
    if (!mounted || _syncing) return;
    b.textSource = false;
    b.localError = null;
    String t;
    try {
      t = b.ed.toEngine();
    } on EditorError {
      t = b.text; // expresion incompleta: se conserva el ultimo texto valido
    } catch (_) {
      t = b.text;
    }
    b.text = t;
    if (identical(b, _b)) {
      _syncing = true;
      _expr.text = t;
      _syncing = false;
    }
    setState(() => _interpretation = null);
  }

  @override
  void dispose() {
    _expr.removeListener(_onText);
    for (final c in [_expr, _var, _point, _order, _lower, _upper, _conds]) {
      c.dispose();
    }
    for (final b in _blocks) {
      b.ed.dispose();
    }
    _editorFocus.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------- KeyboardHost
  @override
  void setOperation(String op, {bool calculate = false}) {
    setState(() {
      _manualOp = op;
      _category = opSpec(op)?.category ?? _category;
    });
    if (calculate) _calculate();
  }

  @override
  void calculate() => _calculate();

  String get _op => _manualOp ?? suggestOperation(_expr.text);
  OpSpec get _spec => opSpec(_op) ?? opCatalog.first;

  /// Categoria visible: la elegida por el usuario o, en modo automatico, la de la operacion sugerida.
  String get _cat => _manualOp == null ? _spec.category : _category;

  List<String> _list(String s) => s.split(RegExp(r'[,;\s]+')).map((e) => e.trim()).where((e) => e.isNotEmpty).toList();

  static const _matrixOps = {'matrix_det', 'matrix_inverse', 'matrix_transpose', 'matrix_rank', 'matrix_rref', 'eigen'};
  static const _symbolicMatrixOp = {'matrix_det': 'det', 'matrix_inverse': 'inverse', 'matrix_transpose': 'transpose', 'eigen': 'eigen'};

  Future<void> _calculate() async {
    if (_busy) return;
    final b = _b;
    b.ed.flushPending();
    String text = _expr.text.trim();
    Map<String, dynamic>? fromEditor;
    if (!b.textSource && !b.ed.isEmpty) {
      try {
        final er = b.ed.toRequest();
        text = er.expression;
        if (er.operation != null) {
          fromEditor = {'operation': er.operation, ...er.extra, if (er.params.isNotEmpty) 'params': er.params};
        }
      } on EditorError catch (e) {
        setState(() => b.localError = e.message);
        return;
      }
    }
    if (text.isEmpty) return;
    if (fromEditor == null && looksLikeNaturalLanguage(text) && _interpretation == null) {
      await _interpret(text);
      return;
    }
    var op = _op;
    Map<String, dynamic> req;
    if (fromEditor != null && fromEditor['operation'] == 'matrix') {
      final m = (fromEditor['matrix'] as List).map((r) => (r as List).map((e) => e.toString()).toList()).toList();
      final mop = _matrixOps.contains(_manualOp) ? _manualOp! : 'matrix_det';
      final symbolic = m.expand((r) => r).any((e) => RegExp(r'[A-Za-z]').hasMatch(e.replaceAll(RegExp(r'\b(pi|e|sqrt)\b'), '')));
      if (symbolic) {
        final sop = _symbolicMatrixOp[mop];
        if (sop == null) {
          setState(() => b.localError = 'Con símbolos se puede calcular: determinante, inversa, transpuesta y autovalores.');
          return;
        }
        op = 'matrix_symbolic';
        req = {'operation': op, 'structured_input': {'a': m}, 'params': {'op': sop}};
      } else {
        op = mop;
        req = {'operation': op, 'structured_input': {'a': m}};
      }
      req.addAll({'timeout_ms': 30000, 'latex': true, 'steps': true});
      await _send(b, req, text, op);
      return;
    }
    if (fromEditor != null) {
      op = fromEditor['operation'] as String;
      req = {...fromEditor, 'expression': text, 'timeout_ms': 30000, 'latex': true, 'steps': true};
      if (_digits != 15) req['precision'] = _digits;
      await _send(b, req, text, op);
      return;
    }
    final f = _spec.fields;
    req = <String, dynamic>{'operation': op, 'expression': text, 'timeout_ms': 30000, 'latex': true, 'steps': true};
    if ((f.contains(OpField.variable) || f.contains(OpField.variables)) && _var.text.trim().isNotEmpty) {
      req['variables'] = f.contains(OpField.variables) ? _list(_var.text) : [_var.text.trim()];
    }
    if (f.contains(OpField.point)) {
      req['point'] = _point.text.trim().isEmpty ? '0' : _point.text.trim();
      if (op == 'limit' && _direction != 'both') req['direction'] = _direction;
    }
    if (f.contains(OpField.order) && int.tryParse(_order.text.trim()) != null) req['order'] = int.parse(_order.text.trim());
    if (op == 'integrate' && _lower.text.trim().isNotEmpty && _upper.text.trim().isNotEmpty) {
      req['lower'] = _lower.text.trim();
      req['upper'] = _upper.text.trim();
    }
    if (f.contains(OpField.conditions) && _conds.text.trim().isNotEmpty) {
      req['conditions'] = _conds.text.split(RegExp(r'[;\n]')).map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    }
    if (_digits != 15) req['precision'] = _digits;
    if (op == 'sum' || op == 'product') {
      req['params'] = {'var': _var.text.trim().isEmpty ? 'k' : _var.text.trim(), 'from': _lower.text.trim().isEmpty ? '1' : _lower.text.trim(),
        'to': _upper.text.trim().isEmpty ? 'n' : _upper.text.trim()};
    }
    if (op == 'substitute') {
      final values = <String, String>{};
      for (final part in _conds.text.split(RegExp(r'[;,\n]'))) {
        final kv = part.split('=');
        if (kv.length == 2 && kv[0].trim().isNotEmpty) values[kv[0].trim()] = kv[1].trim();
      }
      req['params'] = {'values': values};
    }
    if (op == 'logic' || op == 'sets') req['expression'] = text;
    await _send(_b, req, text, op);
  }

  Future<void> _send(_Block b, Map<String, dynamic> req, String text, String op) async {
    setState(() {
      _busy = true;
      b.localError = null;
    });
    final r = await widget.engine.send(req);
    try {
      await widget.store.add(HistoryEntry(
          createdAt: DateTime.now(),
          kind: 'calculo',
          operation: op,
          input: text,
          result: r.exactResult ?? r.errorMessage ?? r.status,
          status: r.status));
    } catch (_) {
      // el historial nunca bloquea un calculo
    }
    if (!mounted) return;
    setState(() {
      b.resp = r;
      b.lastInput = text;
      _busy = false;
    });
  }

  /// Instruccion en espanol: el motor la interpreta (sin calcular) y la interfaz pide confirmacion.
  Future<void> _interpret(String text) async {
    setState(() => _busy = true);
    final r = await widget.engine.send({'operation': 'interpret', 'expression': text, 'timeout_ms': 5000});
    if (!mounted) return;
    setState(() {
      _busy = false;
      _interpretation = r.data.isEmpty ? {'understood': false, 'summary': r.errorMessage ?? 'No se pudo interpretar'} : r.data;
    });
  }

  void _acceptInterpretation() {
    final d = _interpretation!;
    setState(() {
      _expr.text = d['expression']?.toString() ?? _expr.text; // _onText reconstruye el editor
      _manualOp = d['operation']?.toString();
      _category = opSpec(_manualOp ?? '')?.category ?? _category;
      final vars = d['variables'];
      if (vars is List && vars.isNotEmpty) _var.text = vars.join(', ');
      if (d['point'] != null) _point.text = d['point'].toString();
      if (d['direction'] != null) _direction = d['direction'].toString();
      _interpretation = null;
    });
    _calculate();
  }

  Future<void> _searchTools() async {
    final picked = await showModalBottomSheet<OpSpec>(
      context: context,
      isScrollControlled: true,
      builder: (c) => _ToolSearch(),
    );
    if (picked != null) {
      setState(() {
        _manualOp = picked.id;
        _category = picked.category;
        if (_expr.text.trim().isEmpty && picked.example != null) _expr.text = picked.example!;
      });
    }
  }

  Widget _categorySelector() {
    return SingleChildScrollView(
      key: const Key('selector_categoria'),
      scrollDirection: Axis.horizontal,
      child: Row(children: [
        for (final c in opCategories)
          Padding(
            padding: const EdgeInsets.only(right: 6),
            child: FilterChip(
              key: Key('cat_$c'),
              label: Text(c),
              selected: _cat == c,
              showCheckmark: false,
              onSelected: (_) => setState(() {
                _category = c;
                final first = opCatalog.firstWhere((o) => o.category == c);
                if (opSpec(_op)?.category != c) _manualOp = first.id;
                if (_expr.text.trim().isEmpty && first.example != null) _expr.text = first.example!;
              }),
            ),
          ),
      ]),
    );
  }

  Widget _operationSelector() {
    final suggested = suggestOperation(_expr.text);
    final ops = opCatalog.where((o) => o.category == _cat || o.id == _op).toList();
    return Wrap(key: const Key('selector_operacion'), spacing: 6, runSpacing: 6, children: [
      for (final o in ops)
        ChoiceChip(
          key: Key('op_${o.id}'),
          label: Text(o.label),
          selected: _op == o.id,
          avatar: (_manualOp == null && suggested == o.id) ? const Icon(Icons.auto_awesome, size: 16) : null,
          onSelected: (_) => setState(() {
            _manualOp = o.id;
            if (_expr.text.trim().isEmpty && o.example != null) _expr.text = o.example!;
          }),
        ),
    ]);
  }

  Widget _field(TextEditingController c, String label, {String? hint, Key? key}) => Expanded(
      child: TextField(
          key: key,
          controller: c,
          decoration: InputDecoration(isDense: true, labelText: label, hintText: hint, border: const OutlineInputBorder())));

  List<Widget> _contextOptions() {
    final s = _spec;
    final f = s.fields;
    final row = <Widget>[];
    void gap() {
      if (row.isNotEmpty) row.add(const SizedBox(width: 8));
    }

    if (f.contains(OpField.variable)) {
      row.add(_field(_var, s.id == 'solve' ? 'Despejar (opcional)' : 'Variable (opcional)', hint: 'x', key: const Key('campo_variable')));
    }
    if (f.contains(OpField.variables)) {
      row.add(_field(_var, 'Variables (opcional)', hint: 'x, y', key: const Key('campo_variable')));
    }
    if (f.contains(OpField.point)) {
      gap();
      row.add(_field(_point, s.id == 'limit' ? 'Tiende a' : 'Alrededor de', hint: '0, 2, +oo', key: const Key('campo_punto')));
    }
    if (f.contains(OpField.order)) {
      gap();
      row.add(_field(_order, s.id == 'series' ? 'Orden (6)' : 'Orden (1)', key: const Key('campo_orden')));
    }
    if (f.contains(OpField.bounds)) {
      gap();
      row.add(_field(_lower, 'Desde (definida)'));
      row.add(const SizedBox(width: 8));
      row.add(_field(_upper, 'Hasta'));
    }
    final out = <Widget>[];
    if (row.isNotEmpty) out.add(Padding(padding: const EdgeInsets.only(top: 10), child: Row(children: row)));
    if (f.contains(OpField.direction)) {
      out.add(Padding(
        padding: const EdgeInsets.only(top: 6),
        child: SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'both', label: Text('Ambos lados')),
            ButtonSegment(value: '-', label: Text('Izquierda')),
            ButtonSegment(value: '+', label: Text('Derecha')),
          ],
          selected: {_direction},
          onSelectionChanged: (v) => setState(() => _direction = v.first),
        ),
      ));
    }
    if (f.contains(OpField.conditions)) {
      out.add(Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Row(children: [_field(_conds, 'Condiciones iniciales (opcional)', hint: "y(0)=0; y'(0)=1", key: const Key('campo_condiciones'))])));
    }
    if (s.hint != null) {
      out.add(Padding(padding: const EdgeInsets.only(top: 6), child: Text(s.hint!, style: Theme.of(context).textTheme.bodySmall)));
    }
    return out;
  }

  Widget _interpretationCard(BuildContext context) {
    final d = _interpretation!;
    final ok = d['understood'] == true;
    final cs = Theme.of(context).colorScheme;
    return Card(
      key: const Key('tarjeta_interpretacion'),
      color: ok ? cs.secondaryContainer : cs.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(ok ? Icons.translate : Icons.help_outline, size: 18),
            const SizedBox(width: 6),
            Expanded(child: Text(ok ? 'Entendí: ${d['summary']}' : '${d['summary']}', style: Theme.of(context).textTheme.titleSmall)),
          ]),
          if (ok) ...[
            const SizedBox(height: 8),
            Row(children: [
              FilledButton.icon(
                  key: const Key('boton_confirmar_interpretacion'),
                  onPressed: _acceptInterpretation,
                  icon: const Icon(Icons.check),
                  label: const Text('Confirmar y calcular')),
              const SizedBox(width: 8),
              TextButton(
                  onPressed: () => setState(() {
                        _expr.text = d['expression']?.toString() ?? _expr.text;
                        _manualOp = d['operation']?.toString();
                        _category = opSpec(_manualOp ?? '')?.category ?? _category;
                        _interpretation = null;
                      }),
                  child: const Text('Editar')),
            ]),
          ],
        ]),
      ),
    );
  }

  /// Bloques anteriores (o posteriores) de la hoja: entrada dibujada y resultado; al tocarlos se editan.
  Widget _blockCard(BuildContext context, int i) {
    final b = _blocks[i];
    final t = Theme.of(context);
    String? latex;
    try {
      latex = b.ed.isEmpty ? null : b.ed.root.toLatex();
    } catch (_) {
      latex = null;
    }
    return Card(
      key: Key('bloque_$i'),
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 8),
      color: t.colorScheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: BorderSide(color: t.colorScheme.outlineVariant)),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _activate(i),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CircleAvatar(radius: 12, child: Text('${i + 1}', style: const TextStyle(fontSize: 12))),
            const SizedBox(width: 10),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (latex != null) MathView(latex, fontSize: 18) else Text(b.text, style: const TextStyle(fontFamily: 'monospace')),
                if (b.resp != null)
                  Row(children: [
                    Icon(b.resp!.hasResult ? Icons.arrow_right_alt : Icons.error_outline, size: 18, color: t.colorScheme.primary),
                    const SizedBox(width: 4),
                    Expanded(
                        child: b.resp!.latexResult != null
                            ? MathView(b.resp!.latexResult, fallback: b.resp!.exactResult, fontSize: 18)
                            : Text(b.resp!.exactResult ?? b.resp!.errorMessage ?? ResultView.statusText(b.resp!),
                                maxLines: 2, overflow: TextOverflow.ellipsis)),
                  ]),
              ]),
            ),
            IconButton(
                tooltip: 'Eliminar bloque',
                visualDensity: VisualDensity.compact,
                onPressed: () => _deleteBlock(i),
                icon: const Icon(Icons.close, size: 18)),
          ]),
        ),
      ),
    );
  }

  Widget _workspace(BuildContext context, {required bool keypadInline}) {
    final theme = Theme.of(context);
    final interpreted = _spec.label;
    final natural = _b.textSource && looksLikeNaturalLanguage(_expr.text);
    return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
      for (var i = 0; i < _active; i++) _blockCard(context, i),
      Row(children: [
        CircleAvatar(radius: 12, backgroundColor: theme.colorScheme.primary, child: Text('${_active + 1}',
            style: TextStyle(fontSize: 12, color: theme.colorScheme.onPrimary))),
        const SizedBox(width: 8),
        Text('Expresión ${_active + 1}', style: theme.textTheme.titleSmall),
        const Spacer(),
        TextButton.icon(
            key: const Key('boton_nuevo_bloque'),
            onPressed: _newBlock,
            icon: const Icon(Icons.add, size: 18),
            label: const Text('Nueva expresión')),
      ]),
      const SizedBox(height: 6),
      MathEditor(key: Key('editor_$_active'), controller: _ed, focusNode: _editorFocus, onSubmit: _calculate),
      const SizedBox(height: 8),
      CallbackShortcuts(
        bindings: {const SingleActivator(LogicalKeyboardKey.enter, control: true): _calculate},
        child: TextField(
          key: const Key('campo_expresion'),
          controller: _expr,
          style: theme.textTheme.titleMedium?.copyWith(fontFamily: 'monospace'),
          textInputAction: TextInputAction.done,
          keyboardType: TextInputType.visiblePassword, // sin autocorreccion del teclado del sistema
          autocorrect: false,
          enableSuggestions: false,
          decoration: InputDecoration(
            isDense: true,
            prefixIcon: const Icon(Icons.short_text, size: 20),
            hintText: 'o escriba aquí: x^2-5*x+6=0, «deriva x al cubo por seno de x»…',
            labelText: 'Texto o instrucción en español',
            border: const OutlineInputBorder(),
            suffixIcon: _expr.text.isEmpty
                ? null
                : IconButton(tooltip: 'Borrar la expresión', icon: const Icon(Icons.close), onPressed: () => _expr.clear()),
          ),
          onSubmitted: (_) => _calculate(),
        ),
      ),
      if (_b.localError != null)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(_b.localError!, key: const Key('error_editor'), style: TextStyle(color: theme.colorScheme.error)),
        ),
      if (_interpretation != null) Padding(padding: const EdgeInsets.only(top: 8), child: _interpretationCard(context)),
      const SizedBox(height: 10),
      Row(children: [
        Expanded(child: _categorySelector()),
        IconButton(
            key: const Key('boton_buscar_herramienta'),
            tooltip: 'Buscar herramienta',
            onPressed: _searchTools,
            icon: const Icon(Icons.search)),
      ]),
      const SizedBox(height: 6),
      _operationSelector(),
      const SizedBox(height: 6),
      Row(children: [
        Icon(natural ? Icons.translate : (_manualOp == null ? Icons.auto_awesome : Icons.touch_app), size: 16, color: theme.colorScheme.primary),
        const SizedBox(width: 6),
        Expanded(
            child: Text(
                natural
                    ? 'Instrucción en español: se interpretará y se le pedirá confirmación'
                    : (_manualOp == null ? 'Operación sugerida: $interpreted (puede cambiarla)' : 'Operación elegida: $interpreted'),
                key: const Key('operacion_interpretada'),
                style: theme.textTheme.bodyMedium)),
        if (_manualOp != null) TextButton(onPressed: () => setState(() => _manualOp = null), child: const Text('Automática')),
      ]),
      ..._contextOptions(),
      const SizedBox(height: 12),
      Row(children: [
        Expanded(
          child: FilledButton.icon(
            key: const Key('boton_calcular'),
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            onPressed: _busy ? null : _calculate,
            icon: _busy
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : Icon(natural ? Icons.translate : Icons.calculate),
            label: Text(_busy ? 'Calculando…' : (natural ? 'Interpretar' : interpreted)),
          ),
        ),
        const SizedBox(width: 8),
        Tooltip(
          message: 'Cifras de la aproximación decimal',
          child: DropdownButton<int>(
            key: const Key('selector_cifras'),
            value: _digits,
            onChanged: (v) => setState(() => _digits = v ?? 15),
            items: [for (final d in _digitsOptions) DropdownMenuItem(value: d, child: Text('$d cifras'))],
          ),
        ),
        if (!keypadInline)
          IconButton(
            key: const Key('boton_teclado'),
            tooltip: (_showKeyboard ?? true) ? 'Ocultar teclado matemático' : 'Mostrar teclado matemático',
            onPressed: () => setState(() => _showKeyboard = !(_showKeyboard ?? true)),
            icon: Icon((_showKeyboard ?? true) ? Icons.keyboard_hide : Icons.keyboard),
          ),
      ]),
      const SizedBox(height: 12),
      AnimatedSwitcher(
        duration: const Duration(milliseconds: 200),
        child: _resp != null
            ? ResultView(key: ValueKey(_resp), response: _resp!, input: _lastInput)
            : _Examples(
                onPick: (e, op) => setState(() {
                      _expr.text = e;
                      _manualOp = op;
                      if (op != null) _category = opSpec(op)?.category ?? _category;
                    })),
      ),
      for (var i = _active + 1; i < _blocks.length; i++) Padding(padding: const EdgeInsets.only(top: 8), child: _blockCard(context, i)),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, box) {
      final wide = box.maxWidth >= 900;
      if (!wide) {
        return Column(children: [
          Expanded(child: _workspace(context, keypadInline: false)),
          if (_showKeyboard ?? true) MathKeyboard(key: const Key('teclado_matematico'), controller: _ed, host: this),
        ]);
      }
      return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: _workspace(context, keypadInline: true)),
        const VerticalDivider(width: 1),
        SizedBox(
          width: 480,
          child: SingleChildScrollView(child: MathKeyboard(key: const Key('teclado_matematico'), controller: _ed, host: this)),
        ),
      ]);
    });
  }
}

class _ToolSearch extends StatefulWidget {
  @override
  State<_ToolSearch> createState() => _ToolSearchState();
}

class _ToolSearchState extends State<_ToolSearch> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final res = searchOps(_q);
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.7,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              key: const Key('campo_buscar_herramienta'),
              autofocus: true,
              decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search), labelText: 'Buscar herramienta (p. ej. «autovalores», «despejar», «laplace»)'),
              onChanged: (v) => setState(() => _q = v),
            ),
          ),
          Expanded(
            child: ListView(children: [
              for (final o in res)
                ListTile(
                  title: Text(o.label),
                  subtitle: Text('${o.category}${o.example != null ? ' · ej.: ${o.example}' : ''}'),
                  onTap: () => Navigator.pop(context, o),
                ),
              if (res.isEmpty) const ListTile(title: Text('Ninguna herramienta coincide')),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Examples extends StatelessWidget {
  const _Examples({required this.onPick});
  final void Function(String expression, String? operation) onPick;

  static const _items = <(String, String?, String)>[
    ('1/3+1/6', null, 'Fracciones exactas'),
    ('x^2-5*x+6=0', null, 'Ecuación cuadrática (con pasos)'),
    ('2x+y=5; x-y=1', null, 'Sistema de ecuaciones'),
    ('x^3*sin(x)', 'differentiate', 'Derivar (con pasos)'),
    ('x^2', 'integrate', 'Integrar'),
    ('sin(x)/x', 'limit', 'Límite en 0'),
    ('sin(x)', 'series', 'Serie de Taylor'),
    ('x^2-5*x+6>0', 'inequality', 'Inecuación'),
    ("y''+y=0", 'ode', 'Ecuación diferencial'),
    ('x^2*y', 'gradient', 'Gradiente'),
    ('(2+3*i)*(1-i)', 'complex', 'Números complejos'),
    ('36 km/h to m/s', 'units', 'Unidades'),
    ('deriva x al cubo por seno de x', null, 'Instrucción en español'),
  ];

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Ejemplos (toque para insertar)', style: t.textTheme.titleSmall),
      const SizedBox(height: 6),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final (e, op, label) in _items)
          ActionChip(tooltip: label, label: Text(e, style: const TextStyle(fontFamily: 'monospace')), onPressed: () => onPick(e, op)),
      ]),
    ]);
  }
}
