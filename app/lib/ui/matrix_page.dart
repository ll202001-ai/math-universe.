import 'package:flutter/material.dart';

import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import 'result_view.dart';

class MatrixPage extends StatefulWidget {
  const MatrixPage({super.key, required this.engine, required this.store});
  final EngineClient engine;
  final HistoryStore store;

  @override
  State<MatrixPage> createState() => _MatrixPageState();
}

class _MatrixPageState extends State<MatrixPage> {
  final TextEditingController _a = TextEditingController(text: '1 2\n3 4');
  final TextEditingController _b = TextEditingController(text: '5 6\n7 8');
  String _op = 'matrix_det';
  EngineResponse? _resp;
  String? _localError;
  bool _busy = false;

  @override
  void dispose() {
    _a.dispose();
    _b.dispose();
    super.dispose();
  }

  Future<void> _calculate() async {
    List<List<String>> a;
    List<List<String>>? b;
    try {
      a = parseMatrixText(_a.text);
      b = matrixOpsNeedingB.contains(_op) ? parseMatrixText(_b.text) : null;
    } on FormatException catch (e) {
      setState(() {
        _localError = e.message;
        _resp = null;
      });
      return;
    }
    setState(() {
      _busy = true;
      _localError = null;
    });
    final r = await widget.engine.send({
      'operation': _op,
      'structured_input': {'a': a, 'b': ?b},
      'timeout_ms': 30000,
      'latex': true,
      'steps': true, // Gauss-Jordan paso a paso (inversa y sistemas), contrastado con el resultado del motor
    });
    await widget.store.add(HistoryEntry(
        createdAt: DateTime.now(),
        kind: 'matriz',
        operation: _op,
        input: 'A=${_a.text.trim().replaceAll('\n', '; ')}${b != null ? '  B=${_b.text.trim().replaceAll('\n', '; ')}' : ''}',
        result: r.exactResult ?? r.errorMessage ?? r.status,
        status: r.status));
    if (!mounted) return;
    setState(() {
      _resp = r;
      _busy = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final needsB = matrixOpsNeedingB.contains(_op);
    return ListView(padding: const EdgeInsets.all(16), children: [
      DropdownButtonFormField<String>(
        key: const Key('selector_operacion_matriz'),
        initialValue: _op,
        decoration: const InputDecoration(labelText: 'Operación', border: OutlineInputBorder()),
        items: [for (final e in matrixOperations.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
        onChanged: (v) => setState(() => _op = v ?? _op),
      ),
      const SizedBox(height: 12),
      TextField(
        key: const Key('campo_matriz_a'),
        controller: _a,
        minLines: 3,
        maxLines: 10,
        decoration: const InputDecoration(
            labelText: 'Matriz A (una fila por línea; columnas separadas por espacios)', helperText: 'Enteros, fracciones (1/2) o decimales (0.25). Máximo 40×40. Puede pegar celdas de una hoja de cálculo.', border: OutlineInputBorder()),
      ),
      if (needsB) ...[
        const SizedBox(height: 12),
        TextField(
          key: const Key('campo_matriz_b'),
          controller: _b,
          minLines: 3,
          maxLines: 10,
          decoration: InputDecoration(
              labelText: _op == 'matrix_solve' ? 'Vector b (una columna, un valor por línea)' : 'Matriz B', border: const OutlineInputBorder()),
        ),
      ],
      const SizedBox(height: 12),
      FilledButton.icon(
        key: const Key('boton_calcular_matriz'),
        onPressed: _busy ? null : _calculate,
        icon: const Icon(Icons.grid_on),
        label: const Text('Calcular'),
      ),
      const SizedBox(height: 16),
      if (_localError != null) Text(_localError!, key: const Key('error_local'), style: TextStyle(color: Theme.of(context).colorScheme.error)),
      if (_resp != null) ResultView(response: _resp!),
    ]);
  }
}
