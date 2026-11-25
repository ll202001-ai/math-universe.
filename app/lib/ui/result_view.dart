import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../engine/models.dart';

/// Muestra una respuesta del motor sin reinterpretarla: resultado exacto, aproximacion opcional, condiciones, avisos
/// y, en un panel desplegable, la interpretacion, el metodo aplicado y la verificacion independiente.
class ResultView extends StatelessWidget {
  const ResultView({super.key, required this.response, this.input});
  final EngineResponse response;
  final String? input;

  static String statusText(EngineResponse r) {
    switch (r.status) {
      case 'success_exact':
        return 'Resultado exacto';
      case 'success_approximate':
        return 'Resultado aproximado';
      case 'multiple_solutions':
        return 'Infinitas soluciones';
      case 'no_solution':
        return 'Sin solución';
      case 'unsupported':
        return 'No soportado por el motor';
      case 'invalid_input':
        return 'Entrada no válida';
      case 'domain_error':
        return 'Error de dominio';
      case 'timeout':
        return 'Tiempo agotado';
      case 'cancelled':
        return 'Cancelado';
      default:
        return 'Error interno';
    }
  }

  static (IconData, String) verificationText(EngineResponse r) {
    switch (r.verificationStatus) {
      case 'passed':
        return (Icons.verified, 'Verificado de forma independiente');
      case 'failed':
        return (Icons.error_outline, 'Verificación fallida');
      case 'not_possible':
        return (Icons.help_outline, 'No fue posible verificar');
      default:
        return (Icons.help_outline, 'Sin verificación independiente');
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = response;
    final t = Theme.of(context);
    final cs = t.colorScheme;
    final (vIcon, vText) = verificationText(r);
    final m = r.matrix;
    return Card(
      key: const Key('tarjeta_resultado'),
      elevation: 0,
      color: cs.surfaceContainerLow,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: cs.outlineVariant)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
            Chip(
                key: const Key('chip_estado'),
                label: Text(statusText(r)),
                backgroundColor: r.hasResult ? cs.primaryContainer : cs.errorContainer),
            Chip(key: const Key('chip_verificacion'), avatar: Icon(vIcon, size: 18), label: Text(vText)),
          ]),
          const SizedBox(height: 8),
          if (r.exactResult != null && m == null)
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                  child: SelectableText(r.exactResult!,
                      key: const Key('texto_resultado'), style: t.textTheme.headlineSmall?.copyWith(fontFamily: 'monospace'))),
              IconButton(
                  tooltip: 'Copiar el resultado',
                  icon: const Icon(Icons.copy, size: 20),
                  onPressed: () => Clipboard.setData(ClipboardData(text: r.exactResult!))),
            ]),
          if (m != null) _MatrixTable(m),
          if (r.approximateResult != null)
            Padding(
                padding: const EdgeInsets.only(top: 6),
                child: SelectableText('≈ ${r.approximateResult}', key: const Key('texto_aproximado'), style: t.textTheme.titleMedium)),
          if (r.data['kind'] == 'infinite' || r.data['kind'] == 'unique') _SolveDetails(r.data),
          if (r.conditions.isNotEmpty)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('Condiciones: ${r.conditions.join(', ')}', key: const Key('texto_condiciones'))),
          for (final w in r.warnings) Padding(padding: const EdgeInsets.only(top: 6), child: Text('Aviso: $w', style: TextStyle(color: cs.tertiary))),
          if (r.errorMessage != null)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: SelectableText(r.errorMessage!, key: const Key('texto_error'), style: TextStyle(color: cs.error))),
          if (r.raw['local'] != true)
            Theme(
              data: t.copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                key: const Key('panel_procedimiento'),
                tilePadding: EdgeInsets.zero,
                childrenPadding: const EdgeInsets.only(bottom: 8),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                title: const Text('Procedimiento y verificación'),
                children: _details(context),
              ),
            ),
        ]),
      ),
    );
  }

  List<Widget> _details(BuildContext context) {
    final r = response;
    final t = Theme.of(context).textTheme;
    Widget row(String k, String v) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: RichText(
            text: TextSpan(style: t.bodyMedium, children: [
          TextSpan(text: '$k: ', style: const TextStyle(fontWeight: FontWeight.w600)),
          TextSpan(text: v),
        ])));
    return [
      if (input != null) row('Problema original', input!),
      if (r.interpretation != null) row('Interpretación del motor', r.interpretation!),
      if (r.method != null) row('Método aplicado', describeMethod(r.method)),
      row(
          'Verificación',
          r.verificationStatus == 'passed'
              ? 'satisfactoria — ${describeMethod(r.verificationMethod)}'
              : verificationText(r).$2),
      if (r.conditions.isNotEmpty) row('Restricciones conservadas', r.conditions.join(', ')),
      Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text(
            'Resultado calculado por el motor; no se dispone de un procedimiento simbólico detallado paso a paso. '
            'Se muestran el método aplicado y la comprobación independiente.',
            style: t.bodySmall),
      ),
      if (r.elapsedMs != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text('${r.elapsedMs!.toStringAsFixed(1)} ms', style: t.bodySmall)),
    ];
  }
}

class _MatrixTable extends StatelessWidget {
  const _MatrixTable(this.m);
  final List<List<String>> m;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Table(
        key: const Key('tabla_matriz'),
        defaultColumnWidth: const IntrinsicColumnWidth(),
        border: TableBorder.symmetric(inside: BorderSide(color: Theme.of(context).dividerColor)),
        children: [
          for (final row in m)
            TableRow(children: [
              for (final c in row)
                Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    child: SelectableText(c, style: const TextStyle(fontFamily: 'monospace')))
            ])
        ],
      ),
    );
  }
}

class _SolveDetails extends StatelessWidget {
  const _SolveDetails(this.data);
  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final basis = data['nullspace_basis'];
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Rango: ${data['rank']}'),
        if (data['particular'] is List) Text('Solución particular: ${(data['particular'] as List).join(', ')}'),
        if (basis is List && basis.isNotEmpty)
          for (var i = 0; i < basis.length; i++) Text('Dirección libre t${i + 1}: ${(basis[i] as List).join(', ')}'),
      ]),
    );
  }
}
