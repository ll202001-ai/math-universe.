import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import 'math_keypad.dart';
import 'math_view.dart';
import 'result_view.dart';

/// Area de trabajo unica de la calculadora: expresion (con vista previa dibujada), herramienta interpretada y
/// modificable (por categorias o busqueda), opciones contextuales, resultado y teclado cientifico.
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

class _CalculatorPageState extends State<CalculatorPage> {
  late final TextEditingController _expr = TextEditingController(text: widget.initialExpression ?? '');
  final TextEditingController _var = TextEditingController();
  final TextEditingController _point = TextEditingController(text: '0');
  final TextEditingController _order = TextEditingController();
  final TextEditingController _lower = TextEditingController();
  final TextEditingController _upper = TextEditingController();
  final TextEditingController _conds = TextEditingController();
  final FocusNode _focus = FocusNode();
  String? _manualOp;
  String _category = opCategories.first;
  String _direction = 'both';
  int _digits = 15;
  bool _showKeypad = true;
  EngineResponse? _resp;
  String? _lastInput;
  bool _busy = false;
  String? _preview;
  Timer? _debounce;
  Map<String, dynamic>? _interpretation;

  @override
  void initState() {
    super.initState();
    _manualOp = widget.initialOperation;
    if (_manualOp != null) _category = opSpec(_manualOp!)?.category ?? _category;
    _expr.addListener(_onText);
  }

  void _onText() {
    if (!mounted) return;
    setState(() => _interpretation = null);
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 450), _updatePreview);
  }

  /// Vista previa dibujada de lo que se esta escribiendo (el motor la genera; no calcula nada).
  Future<void> _updatePreview() async {
    final t = _expr.text.trim();
    if (t.isEmpty || looksLikeNaturalLanguage(t) || const {'units', 'stats', 'ode', 'inequality'}.contains(_op)) {
      if (mounted) setState(() => _preview = null);
      return;
    }
    final r = await widget.engine.send({'operation': 'parse', 'expression': t, 'latex': true, 'timeout_ms': 5000});
    if (!mounted || _expr.text.trim() != t) return;
    setState(() => _preview = r.status == 'success_exact' ? r.latexInput : null);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _expr.removeListener(_onText);
    for (final c in [_expr, _var, _point, _order, _lower, _upper, _conds]) {
      c.dispose();
    }
    _focus.dispose();
    super.dispose();
  }

  String get _op => _manualOp ?? suggestOperation(_expr.text);
  OpSpec get _spec => opSpec(_op) ?? opCatalog.first;

  /// Categoria visible: la elegida por el usuario o, en modo automatico, la de la operacion sugerida.
  String get _cat => _manualOp == null ? _spec.category : _category;

  List<String> _list(String s) => s.split(RegExp(r'[,;\s]+')).map((e) => e.trim()).where((e) => e.isNotEmpty).toList();

  Future<void> _calculate() async {
    final text = _expr.text.trim();
    if (text.isEmpty || _busy) return;
    if (looksLikeNaturalLanguage(text) && _interpretation == null) {
      await _interpret(text);
      return;
    }
    final op = _op;
    final f = _spec.fields;
    setState(() => _busy = true);
    final req = <String, dynamic>{'operation': op, 'expression': text, 'timeout_ms': 30000, 'latex': true, 'steps': true};
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
      _resp = r;
      _lastInput = text;
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
    _expr.removeListener(_onText);
    setState(() {
      _expr.text = d['expression']?.toString() ?? _expr.text;
      _manualOp = d['operation']?.toString();
      _category = opSpec(_manualOp ?? '')?.category ?? _category;
      final vars = d['variables'];
      if (vars is List && vars.isNotEmpty) _var.text = vars.join(', ');
      if (d['point'] != null) _point.text = d['point'].toString();
      if (d['direction'] != null) _direction = d['direction'].toString();
      _interpretation = null;
    });
    _expr.addListener(_onText);
    _updatePreview();
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

  Widget _workspace(BuildContext context, {required bool keypadInline}) {
    final theme = Theme.of(context);
    final interpreted = _spec.label;
    final natural = looksLikeNaturalLanguage(_expr.text);
    return ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
      CallbackShortcuts(
        bindings: {const SingleActivator(LogicalKeyboardKey.enter, control: true): _calculate},
        child: TextField(
          key: const Key('campo_expresion'),
          controller: _expr,
          focusNode: _focus,
          style: theme.textTheme.headlineSmall?.copyWith(fontFamily: 'monospace'),
          textInputAction: TextInputAction.done,
          keyboardType: TextInputType.visiblePassword, // sin autocorreccion del teclado del sistema
          autocorrect: false,
          enableSuggestions: false,
          decoration: InputDecoration(
            hintText: 'x^2-5*x+6=0   o   «deriva x al cubo por seno de x»',
            labelText: 'Expresión o instrucción',
            border: const OutlineInputBorder(),
            suffixIcon: _expr.text.isEmpty
                ? null
                : IconButton(tooltip: 'Borrar la expresión', icon: const Icon(Icons.close), onPressed: () => _expr.clear()),
          ),
          onSubmitted: (_) => _calculate(),
        ),
      ),
      if (_preview != null)
        Container(
          key: const Key('vista_previa'),
          margin: const EdgeInsets.only(top: 8),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(10)),
          child: MathView(_preview, fontSize: 22),
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
            tooltip: _showKeypad ? 'Ocultar teclado científico' : 'Mostrar teclado científico',
            onPressed: () => setState(() => _showKeypad = !_showKeypad),
            icon: Icon(_showKeypad ? Icons.keyboard_hide : Icons.keyboard),
          ),
      ]),
      const SizedBox(height: 12),
      if (_resp != null) ResultView(response: _resp!, input: _lastInput),
      if (_resp == null)
        _Examples(
            onPick: (e, op) => setState(() {
                  _expr.text = e;
                  _manualOp = op;
                  if (op != null) _category = opSpec(op)?.category ?? _category;
                })),
      if (!keypadInline && _showKeypad) ...[
        const SizedBox(height: 16),
        MathKeypad(controller: _expr, onSubmit: _calculate, focusNode: _focus),
      ],
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, box) {
      final wide = box.maxWidth >= 900;
      if (!wide) return _workspace(context, keypadInline: false);
      return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: _workspace(context, keypadInline: true)),
        const VerticalDivider(width: 1),
        SizedBox(
          width: 420,
          child: SingleChildScrollView(
              padding: const EdgeInsets.all(16), child: MathKeypad(controller: _expr, onSubmit: _calculate, focusNode: _focus)),
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
