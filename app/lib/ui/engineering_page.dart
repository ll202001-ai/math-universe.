import 'package:flutter/material.dart';

import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import 'result_view.dart';

/// Ingenieria electrica y unidades. La biblioteca de formulas viene del motor (operacion «formulas»); el usuario elige
/// la formula, marca la incognita y escribe los datos. El motor despeja, calcula exacto + aproximado y verifica por
/// sustitucion. Ninguna formula se evalua en Dart.
class EngineeringPage extends StatefulWidget {
  const EngineeringPage({super.key, required this.engine, required this.store});
  final EngineClient engine;
  final HistoryStore store;

  @override
  State<EngineeringPage> createState() => _EngineeringPageState();
}

class _EngineeringPageState extends State<EngineeringPage> {
  List<Map<String, dynamic>> _formulas = [];
  String? _error;
  Map<String, dynamic>? _selected;
  String? _unknown;
  final Map<String, TextEditingController> _values = {};
  final TextEditingController _units = TextEditingController(text: '36 km/h to m/s');
  EngineResponse? _resp;
  EngineResponse? _unitsResp;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final c in _values.values) {
      c.dispose();
    }
    _units.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final r = await widget.engine.send({'operation': 'formulas'}, timeout: const Duration(seconds: 60));
    if (!mounted) return;
    setState(() {
      if (r.status == 'success_exact' && r.data['formulas'] is List) {
        _formulas = (r.data['formulas'] as List).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
        if (_formulas.isNotEmpty) _select(_formulas.first);
      } else {
        _error = r.errorMessage ?? 'No se pudo cargar la biblioteca de fórmulas';
      }
    });
  }

  void _select(Map<String, dynamic> f) {
    _selected = f;
    final vars = Map<String, dynamic>.from(f['variables'] as Map);
    _unknown = vars.keys.first;
    for (final c in _values.values) {
      c.dispose();
    }
    _values
      ..clear()
      ..addAll({for (final v in vars.keys) v: TextEditingController()});
    _resp = null;
  }

  Future<void> _solve() async {
    final f = _selected;
    if (f == null || _busy) return;
    setState(() => _busy = true);
    final known = {
      for (final e in _values.entries)
        if (e.key != _unknown && e.value.text.trim().isNotEmpty) e.key: e.value.text.trim()
    };
    final r = await widget.engine.send({
      'operation': 'formula',
      'params': {'id': f['id'], 'known': known, 'unknown': _unknown},
      'latex': true,
      'timeout_ms': 20000,
    });
    try {
      await widget.store.add(HistoryEntry(
          createdAt: DateTime.now(),
          kind: 'calculo',
          operation: 'formula',
          input: '${f['name']}: ${known.entries.map((e) => '${e.key}=${e.value}').join(', ')}',
          result: r.exactResult ?? r.errorMessage ?? r.status,
          status: r.status));
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _resp = r;
      _busy = false;
    });
  }

  Future<void> _convert() async {
    final t = _units.text.trim();
    if (t.isEmpty) return;
    final r = await widget.engine.send({'operation': 'units', 'expression': t, 'latex': true, 'timeout_ms': 20000});
    if (!mounted) return;
    setState(() => _unitsResp = r);
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final f = _selected;
    final vars = f == null ? <String, dynamic>{} : Map<String, dynamic>.from(f['variables'] as Map);
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Ingeniería eléctrica', style: t.textTheme.titleLarge),
      const SizedBox(height: 4),
      Text('Elija una fórmula, marque la incógnita y escriba los datos (valores exactos o decimales).', style: t.textTheme.bodySmall),
      const SizedBox(height: 12),
      if (_error != null) Text(_error!, style: TextStyle(color: t.colorScheme.error)),
      if (_formulas.isNotEmpty)
        DropdownButtonFormField<String>(
          key: const Key('selector_formula'),
          initialValue: f?['id']?.toString(),
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Fórmula', border: OutlineInputBorder()),
          items: [
            for (final x in _formulas)
              DropdownMenuItem(value: x['id'].toString(), child: Text('${x['name']}   ${x['equation']}', overflow: TextOverflow.ellipsis))
          ],
          onChanged: (id) => setState(() => _select(_formulas.firstWhere((x) => x['id'] == id))),
        ),
      if (f != null) ...[
        const SizedBox(height: 8),
        Text(f['equation'].toString(), style: t.textTheme.titleMedium?.copyWith(fontFamily: 'monospace')),
        const SizedBox(height: 8),
        for (final v in vars.keys)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(children: [
              ChoiceChip(
                key: Key('incognita_$v'),
                label: Text(v == _unknown ? '$v = ?' : v),
                selected: v == _unknown,
                onSelected: (_) => setState(() => _unknown = v),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  key: Key('dato_$v'),
                  controller: _values[v],
                  enabled: v != _unknown,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                  decoration: InputDecoration(
                      isDense: true, border: const OutlineInputBorder(), labelText: '$v — ${vars[v]}', hintText: v == _unknown ? 'incógnita' : null),
                ),
              ),
            ]),
          ),
        FilledButton.icon(
            key: const Key('boton_formula'),
            onPressed: _busy ? null : _solve,
            icon: const Icon(Icons.bolt),
            label: Text(_busy ? 'Calculando…' : 'Calcular $_unknown')),
        const SizedBox(height: 12),
        if (_resp != null) ResultView(response: _resp!),
      ],
      const SizedBox(height: 8),
      Text('Los resultados son cálculos educativos y de apoyo: no sustituyen un diseño certificado ni una inspección profesional.',
          style: t.textTheme.bodySmall?.copyWith(fontStyle: FontStyle.italic)),
      const Divider(height: 32),
      Text('Conversión de unidades', style: t.textTheme.titleLarge),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(
          child: TextField(
            key: const Key('campo_unidades'),
            controller: _units,
            decoration: const InputDecoration(
                isDense: true, border: OutlineInputBorder(), labelText: 'Cantidad «to» unidad', helperText: 'Ej.: 1 kWh to J · 60 mi/h to km/h · 220 V*10 A to kW'),
            onSubmitted: (_) => _convert(),
          ),
        ),
        const SizedBox(width: 8),
        FilledButton(key: const Key('boton_unidades'), onPressed: _convert, child: const Text('Convertir')),
      ]),
      const SizedBox(height: 12),
      if (_unitsResp != null) ResultView(response: _unitsResp!),
    ]);
  }
}
