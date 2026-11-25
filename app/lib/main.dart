import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_settings.dart';
import 'data/history_store.dart';
import 'diagnostics/autotest.dart';
import 'engine/engine_client.dart';
import 'engine/engine_factory.dart';
import 'ui/home_page.dart';
import 'version.dart';

/// Argumento de linea de comandos (Windows): `--autotest=<ruta del informe JSON>` ejecuta la autoprueba de la app
/// instalada, escribe el informe y termina (codigo 0 si todo es correcto). En Android se activa con el extra del
/// intent `autotest` (ver MainActivity.kt) y el informe se escribe en el registro del sistema (logcat).
String? autotestPathFromArgs(List<String> args) {
  for (final a in args) {
    if (a.startsWith('--autotest=')) return a.substring('--autotest='.length);
    if (a == '--autotest') return '';
  }
  return null;
}

Future<HistoryStore> openPersistentStore() => SqliteHistoryStore.open();

Future<void> main(List<String> args) async {
  WidgetsFlutterBinding.ensureInitialized();
  final EngineClient engine = createEngineClient();

  var autotestPath = autotestPathFromArgs(args);
  if (autotestPath == null && Platform.isAndroid) {
    try {
      final req = await const MethodChannel('math_universe/app').invokeMethod<bool>('autotestRequested');
      if (req == true) autotestPath = '';
    } catch (_) {}
  }
  if (autotestPath != null) {
    runApp(AutotestApp(engine: engine, reportPath: autotestPath));
    return;
  }

  HistoryStore store;
  String? storeWarning;
  try {
    store = await openPersistentStore();
  } catch (e) {
    store = MemoryHistoryStore();
    storeWarning = 'No se pudo abrir el historial en disco ($e). El historial de esta sesión no se guardará.';
  }
  runApp(MathUniverseApp(engine: engine, store: store, storeWarning: storeWarning, openStore: openPersistentStore));
}

ThemeData _theme(Brightness b) {
  final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFF1B5E8C), brightness: b);
  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    visualDensity: VisualDensity.standard,
    inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
  );
}

class MathUniverseApp extends StatefulWidget {
  const MathUniverseApp({super.key, required this.engine, required this.store, this.storeWarning, this.openStore});

  final EngineClient engine;
  final HistoryStore store;
  final String? storeWarning;
  final Future<HistoryStore> Function()? openStore;

  @override
  State<MathUniverseApp> createState() => _MathUniverseAppState();
}

class _MathUniverseAppState extends State<MathUniverseApp> {
  final AppSettings _settings = AppSettings();

  @override
  void dispose() {
    _settings.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _settings,
      builder: (context, _) => MaterialApp(
        title: 'MATH UNIVERSE',
        debugShowCheckedModeBanner: false,
        theme: _theme(Brightness.light),
        darkTheme: _theme(Brightness.dark),
        themeMode: _settings.themeMode,
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(_settings.textScale)),
          child: child!,
        ),
        home: HomePage(
            engine: widget.engine, store: widget.store, storeWarning: widget.storeWarning, openStore: widget.openStore, settings: _settings),
      ),
    );
  }
}

/// Pantalla de autoprueba (instalacion verificada por la integracion continua o por el usuario).
class AutotestApp extends StatefulWidget {
  const AutotestApp({super.key, required this.engine, required this.reportPath});
  final EngineClient engine;
  final String reportPath;

  @override
  State<AutotestApp> createState() => _AutotestAppState();
}

class _AutotestAppState extends State<AutotestApp> {
  final List<AutotestCheck> _checks = [];
  AutotestReport? _report;

  @override
  void initState() {
    super.initState();
    _run();
  }

  Future<void> _run() async {
    // Marcadores en el registro: la integracion continua de Android los lee con logcat.
    print('MU_AUTOTEST_INICIO {"version":"$appVersion","plataforma":"${Platform.operatingSystem}"}');
    final rep = await runAutotest(widget.engine, openPersistentStore, onCheck: (c) {
      print('MU_AUTOTEST ${jsonEncode(c.toJson())}');
      if (mounted) setState(() => _checks.add(c));
    });
    final json = {
      'version': appVersion,
      'plataforma': Platform.operatingSystem,
      'version_so': Platform.operatingSystemVersion,
      'fecha': DateTime.now().toIso8601String(),
      ...rep.toJson(),
    };
    final summary = Map<String, dynamic>.from(json)..remove('comprobaciones');
    print('MU_AUTOTEST_FIN ${jsonEncode(summary)}');
    if (widget.reportPath.isNotEmpty) {
      try {
        await File(widget.reportPath).writeAsString(const JsonEncoder.withIndent('  ').convert(json));
      } catch (e) {
        print('MU_AUTOTEST_ERROR no se pudo escribir el informe: $e');
      }
    }
    if (mounted) setState(() => _report = rep);
    if (!Platform.isAndroid && widget.reportPath.isNotEmpty) {
      await widget.engine.dispose();
      exit(rep.allOk ? 0 : 1);
    }
  }

  @override
  Widget build(BuildContext context) {
    final rep = _report;
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: _theme(Brightness.light),
      home: Scaffold(
        appBar: AppBar(title: const Text('MATH UNIVERSE · autoprueba')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          Text(rep == null ? 'Ejecutando…' : (rep.allOk ? 'Todo correcto: ${rep.passed}/${rep.checks.length}' : 'Fallos: ${rep.failed}')),
          for (final c in _checks) ListTile(dense: true, leading: Icon(c.ok ? Icons.check : Icons.close), title: Text(c.name), subtitle: Text(c.detail)),
        ]),
      ),
    );
  }
}
