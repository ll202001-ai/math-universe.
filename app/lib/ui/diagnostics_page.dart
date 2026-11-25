import 'package:flutter/material.dart';

import '../data/history_store.dart';
import '../diagnostics/autotest.dart';
import '../engine/engine_client.dart';

/// «Comprobar instalacion»: ejecuta la autoprueba real (motor local + SymPy + historial SQLite) y muestra cada resultado.
class DiagnosticsPage extends StatefulWidget {
  const DiagnosticsPage({super.key, required this.engine, required this.openStore});
  final EngineClient engine;
  final Future<HistoryStore> Function() openStore;

  @override
  State<DiagnosticsPage> createState() => _DiagnosticsPageState();
}

class _DiagnosticsPageState extends State<DiagnosticsPage> {
  final List<AutotestCheck> _checks = [];
  AutotestReport? _report;
  bool _running = false;

  Future<void> _run() async {
    setState(() {
      _running = true;
      _checks.clear();
      _report = null;
    });
    final rep = await runAutotest(widget.engine, widget.openStore, onCheck: (c) {
      if (mounted) setState(() => _checks.add(c));
    });
    if (!mounted) return;
    setState(() {
      _report = rep;
      _running = false;
    });
  }

  @override
  void initState() {
    super.initState();
    _run();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final rep = _report;
    return Scaffold(
      appBar: AppBar(title: const Text('Comprobar instalación')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Se ejecutan cálculos reales en el motor local (Python + SymPy) y se guarda y recupera una entrada del '
            'historial SQLite. No se usa internet.'),
        const SizedBox(height: 12),
        if (rep != null)
          Card(
            key: const Key('resumen_diagnostico'),
            color: rep.allOk ? cs.primaryContainer : cs.errorContainer,
            child: ListTile(
              leading: Icon(rep.allOk ? Icons.check_circle : Icons.error),
              title: Text(rep.allOk ? 'Todo correcto: ${rep.passed}/${rep.checks.length}' : 'Fallos: ${rep.failed} de ${rep.checks.length}'),
              subtitle: Text('Python ${rep.dependencies['python'] ?? '?'} · SymPy ${rep.dependencies['sympy'] ?? 'no disponible'} · '
                  'mpmath ${rep.dependencies['mpmath'] ?? 'no disponible'} · ${rep.elapsed.inMilliseconds} ms'),
            ),
          ),
        if (_running) const LinearProgressIndicator(),
        for (final c in _checks)
          ListTile(
            dense: true,
            leading: Icon(c.ok ? Icons.check : Icons.close, color: c.ok ? Colors.green : cs.error),
            title: Text(c.name),
            subtitle: Text(c.detail, maxLines: 3, overflow: TextOverflow.ellipsis),
          ),
        const SizedBox(height: 12),
        if (!_running) OutlinedButton.icon(onPressed: _run, icon: const Icon(Icons.refresh), label: const Text('Repetir')),
      ]),
    );
  }
}
