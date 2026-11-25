import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/history_store.dart';

/// Historial local: buscar, filtrar favoritos, marcar favoritos, reutilizar (editar en la calculadora), borrar y exportar.
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
  bool _onlyFavorites = false;

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
    final items = await widget.store.list(query: _q.text, onlyFavorites: _onlyFavorites);
    if (!mounted) return;
    setState(() => _items = items);
  }

  Future<void> _export() async {
    final all = await widget.store.list(limit: 100000);
    await Clipboard.setData(ClipboardData(text: historyToCsv(all)));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Historial copiado al portapapeles en formato CSV (${all.length} entradas). Péguelo en una hoja de cálculo.')));
  }

  Future<void> _confirmClear() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('¿Borrar todo el historial?'),
        content: const Text('Se eliminarán todos los cálculos guardados en este equipo. No se puede deshacer.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancelar')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Borrar')),
        ],
      ),
    );
    if (ok == true) {
      await widget.store.clear();
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
        child: Row(children: [
          Expanded(
              child: TextField(
                  key: const Key('campo_buscar_historial'),
                  controller: _q,
                  decoration: const InputDecoration(
                      isDense: true, prefixIcon: Icon(Icons.search), labelText: 'Buscar en el historial', border: OutlineInputBorder()),
                  onChanged: (_) => _load())),
          IconButton(key: const Key('boton_actualizar_historial'), tooltip: 'Actualizar', onPressed: _load, icon: const Icon(Icons.refresh)),
          IconButton(key: const Key('boton_exportar_historial'), tooltip: 'Exportar (CSV al portapapeles)', onPressed: _export, icon: const Icon(Icons.ios_share)),
          IconButton(tooltip: 'Borrar todo', onPressed: _confirmClear, icon: const Icon(Icons.delete_sweep)),
        ]),
      ),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(children: [
          FilterChip(
            key: const Key('filtro_favoritos'),
            label: const Text('Solo favoritos'),
            avatar: const Icon(Icons.star, size: 18),
            selected: _onlyFavorites,
            onSelected: (v) {
              setState(() => _onlyFavorites = v);
              _load();
            },
          ),
          const SizedBox(width: 8),
          Expanded(child: Text('Toque una entrada para editarla en la calculadora', style: Theme.of(context).textTheme.bodySmall)),
        ]),
      ),
      Expanded(
        child: _items.isEmpty
            ? Center(child: Text(_onlyFavorites ? 'Sin favoritos' : 'Sin cálculos guardados'))
            : ListView.separated(
                itemCount: _items.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, i) {
                  final e = _items[i];
                  return ListTile(
                    title: Text(e.input, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontFamily: 'monospace')),
                    subtitle: Text('${_opLabel(e.operation)} → ${e.result}', maxLines: 2, overflow: TextOverflow.ellipsis),
                    leading: Icon(e.kind == 'matriz' ? Icons.grid_on : Icons.functions),
                    trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                      IconButton(
                          key: Key('favorito_${e.id}'),
                          tooltip: e.favorite ? 'Quitar de favoritos' : 'Marcar como favorito',
                          icon: Icon(e.favorite ? Icons.star : Icons.star_border, color: e.favorite ? Colors.amber : null),
                          onPressed: () async {
                            await widget.store.setFavorite(e.id!, !e.favorite);
                            await _load();
                          }),
                      IconButton(
                          tooltip: 'Borrar',
                          icon: const Icon(Icons.close),
                          onPressed: () async {
                            await widget.store.delete(e.id!);
                            await _load();
                          }),
                    ]),
                    onTap: () => widget.onReuse(e),
                  );
                },
              ),
      ),
    ]);
  }
}

String _opLabel(String op) =>
    const {
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
