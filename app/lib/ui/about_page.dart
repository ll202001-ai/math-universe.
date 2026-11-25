import 'package:flutter/material.dart';

import '../engine/engine_client.dart';
import '../version.dart';

/// Version, estado real de los modulos y limitaciones conocidas. Los modulos se leen del propio motor (capabilities).
class AboutPage extends StatefulWidget {
  const AboutPage({super.key, required this.engine});
  final EngineClient engine;

  @override
  State<AboutPage> createState() => _AboutPageState();
}

class _AboutPageState extends State<AboutPage> {
  Map<String, dynamic>? _caps;
  String? _error;

  @override
  void initState() {
    super.initState();
    widget.engine.send({'operation': 'capabilities'}, timeout: const Duration(seconds: 60)).then((r) {
      if (!mounted) return;
      setState(() {
        if (r.status == 'success_exact') {
          _caps = r.data;
        } else {
          _error = r.errorMessage ?? r.status;
        }
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final mods = (_caps?['modules'] is Map) ? Map<String, dynamic>.from(_caps!['modules'] as Map) : <String, dynamic>{};
    final deps = (_caps?['dependencies'] is Map) ? Map<String, dynamic>.from(_caps!['dependencies'] as Map) : <String, dynamic>{};
    return Scaffold(
      appBar: AppBar(title: const Text('Acerca de MATH UNIVERSE')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text('MATH UNIVERSE $appVersion', style: t.headlineSmall),
        const SizedBox(height: 4),
        const Text('Calculadora matemática exacta. Todos los cálculos se hacen en este equipo con un motor local '
            '(Python, SymPy, mpmath). No se envía nada a internet.'),
        const SizedBox(height: 12),
        if (_caps != null)
          Text('Motor ${_caps!['engine_version']} · contrato ${_caps!['api_version']} · Python ${deps['python']} · '
              'SymPy ${deps['sympy'] ?? 'no disponible'} · mpmath ${deps['mpmath'] ?? 'no disponible'}'),
        if (_error != null) Text('Motor no disponible: $_error'),
        const SizedBox(height: 16),
        Text('Estado de los módulos (informado por el motor)', style: t.titleMedium),
        for (final e in mods.entries) ListTile(dense: true, title: Text(e.key.replaceAll('_', ' ')), subtitle: Text('${e.value}')),
        const SizedBox(height: 16),
        Text('Limitaciones conocidas', style: t.titleMedium),
        const SizedBox(height: 6),
        for (final l in knownLimitations) Padding(padding: const EdgeInsets.only(bottom: 4), child: Text('• $l')),
      ]),
    );
  }
}

const knownLimitations = <String>[
  'No hay todavía gráficas, estadística, autovalores, ecuaciones diferenciales ni ingeniería eléctrica: están planificados, no implementados.',
  'No hay entrada manuscrita, por voz ni en lenguaje natural libre: se escribe la expresión o se usa el teclado científico.',
  'No se muestra un procedimiento paso a paso: se indican el método aplicado y la verificación independiente.',
  'Ecuaciones con radicales, valor absoluto, exponenciales o trigonométricas y algunas integrales devuelven «No soportado».',
  'Los resultados de SymPy (respaldo) se marcan como tales y pasan por la misma verificación independiente.',
  'Matrices: solo entradas numéricas exactas (enteros, fracciones, decimales), hasta 40×40.',
  'El instalador de Windows y el APK no están firmados con un certificado comercial: Windows o Android pueden mostrar un aviso.',
];
