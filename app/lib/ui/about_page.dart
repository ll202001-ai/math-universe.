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
  'Todavía no hay ecuaciones en derivadas parciales, elementos finitos, simulador de circuitos por nodos ni transformada de Fourier.',
  'No hay entrada manuscrita ni por imagen, y no hay asistente de IA en línea: las instrucciones en español se interpretan con reglas y siempre se piden confirmar.',
  'El paso a paso cubre ecuaciones de primer y segundo grado, derivadas y Gauss-Jordan. En el resto se muestran el método y la verificación, sin inventar pasos.',
  'Ecuaciones con radicales, valor absoluto, exponenciales o trigonométricas y algunas integrales pueden devolver «No soportado».',
  'Los resultados calculados con SymPy se marcan como tales y pasan por una comprobación independiente. Si no se puede comprobar, se indica.',
  'Ceros y extremos marcados en las gráficas son aproximaciones numéricas del muestreo.',
  'Matrices: solo entradas numéricas exactas, hasta 40×40 (autovalores exactos hasta 6×6).',
  'Ingeniería: cálculos de apoyo; no sustituyen un diseño certificado ni una inspección profesional.',
  'El instalador de Windows y el APK no están firmados con un certificado comercial: Windows o Android pueden mostrar un aviso.',
];
