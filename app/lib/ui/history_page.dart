import 'package:flutter/material.dart';

import '../data/history_store.dart';

class HistoryPage extends StatefulWidget {
  const HistoryPage({super.key, required this.store, required this.onReuse});
  final HistoryStore store;
  final void Function(HistoryEntry entry) onReuse;

  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  final TextEditingController _q = TextEditingController();
  List<HistoryEntry> _items = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _q.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final items = await widget.store.list(query: _q.text);
    if (!mounted) return;
    setState(() => _items = items);
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Expanded(
              child: TextField(
                  key: const Key('campo_buscar_historial'),
                  controller: _q,
                  decoration: const InputDecoration(prefixIcon: Icon(Icons.search), labelText: 'Buscar en el historial', border: OutlineInputBorder()),
                  onChanged: (_) => _load())),
          IconButton(
              key: const Key('boton_actualizar_historial'), tooltip: 'Actualizar', onPressed: _load, icon: const Icon(Icons.refresh)),
          IconButton(
              tooltip: 'Borrar todo',
              onPressed: () async {
                await widget.store.clear();
                await _load();
              },
              icon: const Icon(Icons.delete_sweep)),
        ]),
      ),
      Expanded(
        child: _items.isEmpty
            ? const Center(child: Text('Sin cálculos guardados'))
            : ListView.separated(
                itemCount: _items.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, i) {
                  final e = _items[i];
                  return ListTile(
                    title: Text(e.input, maxLines: 2, overflow: TextOverflow.ellipsis),
                    subtitle: Text('${_opLabel(e.operation)} → ${e.result}', maxLines: 2, overflow: TextOverflow.ellipsis),
                    leading: Icon(e.kind == 'matriz' ? Icons.grid_on : Icons.functions),
                    trailing: IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () async {
                          await widget.store.delete(e.id!);
                          await _load();
                        }),
                    onTap: () => widget.onReuse(e),
                  );
                },
              ),
      ),
    ]);
  }
}

String _opLabel(String op) => const {
      'evaluate': 'Calcular',
      'simplify': 'Simplificar',
      'expand': 'Expandir',
      'factor': 'Factorizar',
      'solve': 'Resolver',
      'differentiate': 'Derivar',
      'integrate': 'Integrar',
      'limit': 'Límite',
      'matrix_add': 'A + B',
      'matrix_sub': 'A − B',
      'matrix_mul': 'A × B',
      'matrix_transpose': 'Transpuesta',
      'matrix_det': 'Determinante',
      'matrix_inverse': 'Inversa',
      'matrix_rank': 'Rango',
      'matrix_rref': 'Forma escalonada',
      'matrix_solve': 'A x = b',
    }[op] ??
    op;
