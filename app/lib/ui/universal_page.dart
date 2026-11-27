import 'package:flutter/material.dart';

import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import 'result_view.dart';

/// Entrada universal: el usuario escribe el ejercicio con sus palabras o en notacion matematica y el motor local
/// (operacion `resolver`) lo interpreta, elige el metodo, lo resuelve y lo verifica. Los formularios especializados
/// existen en otras pestanas, pero nunca son obligatorios.
class UniversalPage extends StatefulWidget {
  const UniversalPage({super.key, required this.engine, required this.store});
  final EngineClient engine;
  final HistoryStore store;

  @override
  State<UniversalPage> createState() => _UniversalPageState();
}

class _UniversalPageState extends State<UniversalPage> {
  final TextEditingController _c = TextEditingController();
  EngineResponse? _resp;
  String? _input;
  bool _busy = false;

  static const _ejemplos = <String>[
    'deriva x^3*sin(x)',
    'integral de x*e^x dx de 0 a 1',
    'límite de sin(x)/x cuando x tiende a 0',
    'resuelve cos(x)=x',
    'área entre y=x^2 y y=x',
    'volumen del sólido bajo z=4-x^2-y^2 sobre el disco x^2+y^2<=4',
    'divergencia de F=(x*y, y*z, z*x)',
    'máximo de xyz con x+y+z=3 y x,y,z>0',
  ];

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  Future<void> _resolver() async {
    final text = _c.text.trim();
    if (text.isEmpty || _busy) return;
    setState(() {
      _busy = true;
      _input = text;
    });
    final r = await widget.engine.send({
      'operation': 'resolver',
      'expression': text,
      'latex': true,
      'steps': true,
      'timeout_ms': 60000,
    }, timeout: const Duration(seconds: 90));
    try {
      await widget.store.add(HistoryEntry(
          createdAt: DateTime.now(),
          kind: 'calculo',
          operation: 'resolver',
          input: text,
          result: r.exactResult ?? r.approximateResult ?? r.errorMessage ?? r.status,
          status: r.status));
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _resp = r;
      _busy = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final th = Theme.of(context);
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Resolver cualquier ejercicio', style: th.textTheme.titleLarge),
      const SizedBox(height: 4),
      Text(
          'Escriba o pegue el enunciado tal como lo tiene: en español, con símbolos (∫, ∬, √, π) o en notación de calculadora. '
          'El motor local detecta qué se pide, elige el método, resuelve con exactitud cuando es posible, contrasta el resultado '
          'con un método independiente y no entrega nada que no haya podido verificar.',
          style: th.textTheme.bodySmall),
      const SizedBox(height: 12),
      TextField(
        key: const Key('campo_universal'),
        controller: _c,
        minLines: 3,
        maxLines: 8,
        decoration: const InputDecoration(labelText: 'Ejercicio', hintText: 'Ej.: calcula el volumen del sólido limitado por z=x^2+y^2 y z=4', alignLabelWithHint: true),
      ),
      const SizedBox(height: 8),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final e in _ejemplos)
          ActionChip(
              label: Text(e, style: const TextStyle(fontSize: 12)),
              onPressed: () => setState(() => _c.text = e)),
      ]),
      const SizedBox(height: 12),
      FilledButton.icon(
          key: const Key('boton_universal'),
          onPressed: _busy ? null : _resolver,
          icon: const Icon(Icons.auto_awesome),
          label: Text(_busy ? 'Resolviendo…' : 'Resolver')),
      const SizedBox(height: 12),
      if (_resp != null) ResultView(key: ValueKey(_resp), response: _resp!, input: _input),
    ]);
  }
}
