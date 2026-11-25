import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import 'math_keypad.dart';
import 'result_view.dart';

/// Area de trabajo de la calculadora: una sola pantalla con la expresion, la operacion interpretada (modificable),
/// opciones contextuales, el resultado y el teclado cientifico. Todo calculo lo hace el motor local.
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
  final TextEditingController _lower = TextEditingController();
  final TextEditingController _upper = TextEditingController();
  final FocusNode _focus = FocusNode();
  String? _manualOp;
  String _direction = 'both';
  int _digits = 15;
  bool _showKeypad = true;
  EngineResponse? _resp;
  String? _lastInput;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _manualOp = widget.initialOperation;
    _expr.addListener(_onText);
  }

  void _onText() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _expr.removeListener(_onText);
    for (final c in [_expr, _var, _point, _lower, _upper]) {
      c.dispose();
    }
    _focus.dispose();
    super.dispose();
  }

  String get _op => _manualOp ?? suggestOperation(_expr.text);

  Future<void> _calculate() async {
    final text = _expr.text.trim();
    if (text.isEmpty || _busy) return;
    final op = _op;
    setState(() => _busy = true);
    final req = <String, dynamic>{'operation': op, 'expression': text, 'timeout_ms': 20000};
    if (_var.text.trim().isNotEmpty) req['variables'] = [_var.text.trim()];
    if (op == 'limit') {
      req['point'] = _point.text.trim().isEmpty ? '0' : _point.text.trim();
      if (_direction != 'both') req['direction'] = _direction;
    }
    if (op == 'integrate' && _lower.text.trim().isNotEmpty && _upper.text.trim().isNotEmpty) {
      req['lower'] = _lower.text.trim();
      req['upper'] = _upper.text.trim();
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

  Widget _operationSelector() {
    final suggested = suggestOperation(_expr.text);
    return SingleChildScrollView(
      key: const Key('selector_operacion'),
      scrollDirection: Axis.horizontal,
      child: Row(children: [
        for (final e in calculusOperations.entries)
          Padding(
            padding: const EdgeInsets.only(right: 6),
            child: ChoiceChip(
              key: Key('op_${e.key}'),
              label: Text(e.value),
              selected: _op == e.key,
              avatar: (_manualOp == null && suggested == e.key) ? const Icon(Icons.auto_awesome, size: 16) : null,
              onSelected: (_) => setState(() => _manualOp = e.key),
            ),
          ),
      ]),
    );
  }

  List<Widget> _contextOptions() {
    final op = _op;
    final needsVar = const {'solve', 'differentiate', 'integrate', 'limit'}.contains(op);
    final row = <Widget>[];
    if (needsVar) {
      row.add(Expanded(
          child: TextField(
              key: const Key('campo_variable'),
              controller: _var,
              decoration: InputDecoration(
                  isDense: true,
                  labelText: op == 'solve' ? 'Despejar (opcional)' : 'Variable (opcional)',
                  hintText: 'x',
                  border: const OutlineInputBorder()))));
    }
    if (op == 'limit') {
      row.addAll([
        const SizedBox(width: 8),
        Expanded(
            child: TextField(
                key: const Key('campo_punto'),
                controller: _point,
                decoration: const InputDecoration(isDense: true, labelText: 'Tiende a', hintText: '0, 2, +oo, -oo', border: OutlineInputBorder()))),
        const SizedBox(width: 8),
        DropdownButton<String>(
          value: _direction,
          onChanged: (v) => setState(() => _direction = v ?? 'both'),
          items: const [
            DropdownMenuItem(value: 'both', child: Text('ambos lados')),
            DropdownMenuItem(value: '+', child: Text('por la derecha')),
            DropdownMenuItem(value: '-', child: Text('por la izquierda')),
          ],
        ),
      ]);
    }
    if (op == 'integrate') {
      row.addAll([
        const SizedBox(width: 8),
        Expanded(
            child: TextField(
                controller: _lower,
                decoration: const InputDecoration(isDense: true, labelText: 'Desde (definida)', border: OutlineInputBorder()))),
        const SizedBox(width: 8),
        Expanded(
            child: TextField(
                controller: _upper, decoration: const InputDecoration(isDense: true, labelText: 'Hasta', border: OutlineInputBorder()))),
      ]);
    }
    if (row.isEmpty) return const [];
    return [Padding(padding: const EdgeInsets.only(top: 10), child: Row(children: row))];
  }

  Widget _workspace(BuildContext context, {required bool keypadInline}) {
    final theme = Theme.of(context);
    final interpreted = calculusOperations[_op] ?? _op;
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
            hintText: 'Ej.: x^2-5*x+6=0',
            labelText: 'Expresión',
            border: const OutlineInputBorder(),
            suffixIcon: _expr.text.isEmpty
                ? null
                : IconButton(tooltip: 'Borrar la expresión', icon: const Icon(Icons.close), onPressed: () => _expr.clear()),
          ),
          onSubmitted: (_) => _calculate(),
        ),
      ),
      const SizedBox(height: 10),
      Row(children: [
        Icon(_manualOp == null ? Icons.auto_awesome : Icons.touch_app, size: 16, color: theme.colorScheme.primary),
        const SizedBox(width: 6),
        Expanded(
            child: Text(_manualOp == null ? 'Operación sugerida: $interpreted (puede cambiarla)' : 'Operación elegida: $interpreted',
                key: const Key('operacion_interpretada'), style: theme.textTheme.bodyMedium)),
        if (_manualOp != null) TextButton(onPressed: () => setState(() => _manualOp = null), child: const Text('Automática')),
      ]),
      const SizedBox(height: 6),
      _operationSelector(),
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
                : const Icon(Icons.calculate),
            label: Text(_busy ? 'Calculando…' : interpreted),
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

class _Examples extends StatelessWidget {
  const _Examples({required this.onPick});
  final void Function(String expression, String? operation) onPick;

  static const _items = <(String, String?, String)>[
    ('1/3+1/6', null, 'Fracciones exactas'),
    ('x^2-5*x+6=0', null, 'Ecuación cuadrática'),
    ('2x+y=5; x-y=1', null, 'Sistema de ecuaciones'),
    ('V=I*R', 'solve', 'Despejar: escriba R en «Despejar»'),
    ('x^2-5*x+6', 'factor', 'Factorizar'),
    ('x^3*sin(x)', 'differentiate', 'Derivar'),
    ('x^2', 'integrate', 'Integrar'),
    ('sin(x)/x', 'limit', 'Límite en 0'),
    ('(x^3-8)/(x-2)', 'simplify', 'Simplificar conservando el dominio'),
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
