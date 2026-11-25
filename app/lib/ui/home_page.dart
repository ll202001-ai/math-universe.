import 'package:flutter/material.dart';

import '../app_settings.dart';
import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import 'about_page.dart';
import 'calculator_page.dart';
import 'diagnostics_page.dart';
import 'history_page.dart';
import 'matrix_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.engine, required this.store, this.storeWarning, this.openStore, this.settings});
  final EngineClient engine;
  final HistoryStore store;
  final String? storeWarning;

  /// Abre una conexion nueva al historial persistente (para la autoprueba). Si es null se usa uno en memoria.
  final Future<HistoryStore> Function()? openStore;
  final AppSettings? settings;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _tab = 0;
  String? _engineLine;
  Key _calcKey = UniqueKey();
  Key _histKey = UniqueKey();
  String? _reuseExpr;
  String? _reuseOp;

  @override
  void initState() {
    super.initState();
    _checkEngine();
  }

  Future<void> _checkEngine() async {
    final r = await widget.engine.send({'operation': 'ping'}, timeout: const Duration(seconds: 60));
    if (!mounted) return;
    setState(() => _engineLine = r.status == 'success_exact' ? 'Motor local listo' : 'Motor no disponible: ${r.errorMessage ?? r.status}');
  }

  @override
  void dispose() {
    widget.engine.dispose();
    widget.store.close();
    super.dispose();
  }

  void _onMenu(String v) {
    final s = widget.settings;
    switch (v) {
      case 'diagnostico':
        Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => DiagnosticsPage(engine: widget.engine, openStore: widget.openStore ?? () async => MemoryHistoryStore())));
      case 'acerca':
        Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => AboutPage(engine: widget.engine)));
      case 'tema':
        s?.cycleTheme();
      case 'texto+':
        s?.changeTextScale(0.1);
      case 'texto-':
        s?.changeTextScale(-0.1);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      CalculatorPage(key: _calcKey, engine: widget.engine, store: widget.store, initialExpression: _reuseExpr, initialOperation: _reuseOp),
      MatrixPage(engine: widget.engine, store: widget.store),
      HistoryPage(
          key: _histKey,
          store: widget.store,
          onReuse: (e) {
            if (e.kind == 'calculo') {
              setState(() {
                _reuseExpr = e.input;
                _reuseOp = calculusKnown(e.operation) ? e.operation : null;
                _calcKey = UniqueKey();
                _tab = 0;
              });
            }
          }),
    ];
    final ok = _engineLine == null || _engineLine!.startsWith('Motor local listo');
    final cs = Theme.of(context).colorScheme;
    void select(int i) => setState(() {
          _tab = i;
          if (i == 2) _histKey = UniqueKey(); // recarga el historial al entrar
        });
    const destinations = [
      (Icons.functions, 'Calculadora'),
      (Icons.grid_on, 'Matrices'),
      (Icons.history, 'Historial'),
    ];
    return LayoutBuilder(builder: (context, box) {
      final wide = box.maxWidth >= 720;
      final body = Column(children: [
        if (widget.storeWarning != null) MaterialBanner(content: Text(widget.storeWarning!), actions: const [SizedBox()]),
        Expanded(child: IndexedStack(index: _tab, children: pages)),
      ]);
      return Scaffold(
        appBar: AppBar(
          title: const Text('MATH UNIVERSE', style: TextStyle(fontWeight: FontWeight.w600, letterSpacing: 1.2)),
          bottom: PreferredSize(
              preferredSize: const Size.fromHeight(22),
              child: Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(ok ? Icons.circle : Icons.error, size: 10, color: ok ? Colors.green : cs.error),
                    const SizedBox(width: 6),
                    Flexible(
                        child: Text(_engineLine ?? 'Iniciando motor…',
                            key: const Key('estado_motor'),
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(color: ok ? null : cs.error))),
                    const SizedBox(width: 6),
                    const Text('· sin conexión necesaria', style: TextStyle(fontSize: 12)),
                  ]))),
          actions: [
            PopupMenuButton<String>(
              key: const Key('menu_principal'),
              tooltip: 'Menú',
              onSelected: _onMenu,
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'diagnostico', child: ListTile(leading: Icon(Icons.health_and_safety), title: Text('Comprobar instalación'))),
                PopupMenuItem(value: 'tema', child: ListTile(leading: Icon(Icons.brightness_6), title: Text('Cambiar tema (claro/oscuro/sistema)'))),
                PopupMenuItem(value: 'texto+', child: ListTile(leading: Icon(Icons.text_increase), title: Text('Texto más grande'))),
                PopupMenuItem(value: 'texto-', child: ListTile(leading: Icon(Icons.text_decrease), title: Text('Texto más pequeño'))),
                PopupMenuItem(value: 'acerca', child: ListTile(leading: Icon(Icons.info_outline), title: Text('Acerca de y limitaciones'))),
              ],
            ),
          ],
        ),
        body: wide
            ? Row(children: [
                NavigationRail(
                  selectedIndex: _tab,
                  onDestinationSelected: select,
                  labelType: NavigationRailLabelType.all,
                  destinations: [for (final (i, l) in destinations) NavigationRailDestination(icon: Icon(i), label: Text(l))],
                ),
                const VerticalDivider(width: 1),
                Expanded(child: body),
              ])
            : body,
        bottomNavigationBar: wide
            ? null
            : NavigationBar(
                selectedIndex: _tab,
                onDestinationSelected: select,
                destinations: [for (final (i, l) in destinations) NavigationDestination(icon: Icon(i), label: l)],
              ),
      );
    });
  }
}

bool calculusKnown(String op) => calculusOperations.containsKey(op);
