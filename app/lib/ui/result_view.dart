import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../engine/models.dart';
import 'math_view.dart';

/// Muestra una respuesta del motor sin reinterpretarla: resultado (dibujado en notacion matematica cuando el motor
/// envia LaTeX), aproximacion, condiciones, avisos, datos estructurados y, en un panel, el procedimiento real del motor
/// y su verificacion independiente.
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
    final latex = r.latexResult;
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
          if (r.latexInput != null) ...[
            const SizedBox(height: 6),
            Text('Entrada interpretada', style: t.textTheme.labelMedium),
            MathView(r.latexInput, key: const Key('latex_entrada'), fontSize: 18, color: cs.onSurfaceVariant),
          ],
          const SizedBox(height: 8),
          if (r.exactResult != null && m == null)
            Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
              Expanded(
                child: latex != null
                    ? MathView(latex, key: const Key('latex_resultado'), fallback: r.exactResult, fontSize: 26)
                    : SelectableText(r.exactResult!,
                        key: const Key('texto_resultado'), style: t.textTheme.headlineSmall?.copyWith(fontFamily: 'monospace')),
              ),
              IconButton(
                  tooltip: 'Copiar el resultado (texto)',
                  icon: const Icon(Icons.copy, size: 20),
                  onPressed: () => Clipboard.setData(ClipboardData(text: r.exactResult!))),
            ]),
          if (latex != null && r.exactResult != null && m == null)
            Text(r.exactResult!, key: const Key('texto_resultado'), style: t.textTheme.bodySmall?.copyWith(fontFamily: 'monospace')),
          if (m != null) latex != null ? MathView(latex, fallback: r.exactResult, fontSize: 22) : _MatrixTable(m),
          if (r.approximateResult != null)
            Padding(
                padding: const EdgeInsets.only(top: 6),
                child: SelectableText('≈ ${r.approximateResult}', key: const Key('texto_aproximado'), style: t.textTheme.titleMedium)),
          if (r.data['kind'] == 'infinite' || r.data['kind'] == 'unique') _SolveDetails(r.data),
          ..._structured(context, r),
          if (r.conditions.isNotEmpty)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('Condiciones: ${r.conditions.join(', ')}', key: const Key('texto_condiciones'))),
          for (final w in r.warnings) Padding(padding: const EdgeInsets.only(top: 6), child: Text('Aviso: $w', style: TextStyle(color: cs.tertiary))),
          if (r.errorMessage != null)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: SelectableText(r.errorMessage!, key: const Key('texto_error'), style: TextStyle(color: cs.error))),
          if (r.raw['local'] != true && r.status != 'invalid_input')
            Theme(
              data: t.copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                key: const Key('panel_procedimiento'),
                tilePadding: EdgeInsets.zero,
                initiallyExpanded: r.steps.isNotEmpty,
                childrenPadding: const EdgeInsets.only(bottom: 8),
                expandedCrossAxisAlignment: CrossAxisAlignment.start,
                title: Text(r.steps.isNotEmpty ? 'Procedimiento paso a paso' : 'Procedimiento y verificación'),
                children: _details(context),
              ),
            ),
        ]),
      ),
    );
  }

  List<Widget> _structured(BuildContext context, EngineResponse r) {
    final d = r.data;
    final t = Theme.of(context).textTheme;
    final out = <Widget>[];
    Widget kv(String k, Object? v) => Padding(
        padding: const EdgeInsets.only(top: 2),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 190, child: Text(k, style: t.bodyMedium?.copyWith(fontWeight: FontWeight.w600))),
          Expanded(child: SelectableText('${v ?? '—'}')),
        ]));
    if (d['eigenvalues'] is List) {
      out.add(const SizedBox(height: 8));
      if (d['characteristic_polynomial_latex'] != null) {
        out.add(Text('Polinomio característico', style: t.labelMedium));
        out.add(MathView('p(\\lambda) = ${d['characteristic_polynomial_latex']}', fontSize: 18));
      }
      for (final e in (d['eigenvalues'] as List).whereType<Map>()) {
        final vecs = (e['vectors'] as List? ?? []).map((v) => '(${(v as List).join(', ')})').join('; ');
        out.add(kv('λ = ${e['value']}  (mult. ${e['multiplicity']})', 'autovector(es): $vecs'));
      }
      out.add(kv('Diagonalizable', d['diagonalizable'] == true ? 'sí' : 'no'));
    }
    if (d.containsKey('mean') && d.containsKey('median')) {
      out.add(const SizedBox(height: 8));
      for (final (k, key) in [
        ('n', 'n'),
        ('Media', 'mean'),
        ('Mediana', 'median'),
        ('Moda', 'mode'),
        ('Mínimo', 'min'),
        ('Máximo', 'max'),
        ('Rango', 'range'),
        ('Varianza (población)', 'variance_population'),
        ('Varianza (muestra)', 'variance_sample'),
        ('Desv. típica (población)', 'std_population'),
        ('Desv. típica (muestra)', 'std_sample'),
        ('Q1', 'q1'),
        ('Q3', 'q3'),
        ('Rango intercuartílico', 'iqr'),
      ]) {
        final v = d[key];
        out.add(kv(k, v is List ? (v.isEmpty ? 'sin moda' : v.join(', ')) : v));
      }
    }
    if (d.containsKey('modulus') && d.containsKey('argument')) {
      out.add(const SizedBox(height: 8));
      out.add(kv('Parte real', d['real']));
      out.add(kv('Parte imaginaria', d['imaginary']));
      out.add(kv('Módulo', d['modulus']));
      out.add(kv('Argumento', '${d['argument']} rad  (${d['argument_degrees']}°)'));
      out.add(kv('Forma polar', d['polar']));
      out.add(kv('Conjugado', d['conjugate']));
    }
    if (d['formula'] != null && d['name'] != null) {
      out.add(kv('Fórmula', '${d['name']}: ${d['formula']}'));
    }
    return out;
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
    final steps = r.steps;
    return [
      if (steps.isNotEmpty)
        for (var i = 0; i < steps.length; i++)
          Padding(
            key: Key('paso_$i'),
            padding: const EdgeInsets.only(top: 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${i + 1}. ${steps[i].text}', style: t.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
              if (steps[i].latex != null) MathView(steps[i].latex, fontSize: 18),
            ]),
          ),
      if (input != null) row('Problema original', input!),
      if (r.interpretation != null) row('Interpretación del motor', r.interpretation!),
      if (r.method != null) row('Método aplicado', describeMethod(r.method)),
      row('Verificación',
          r.verificationStatus == 'passed' ? 'satisfactoria — ${describeMethod(r.verificationMethod)}' : verificationText(r).$2),
      if (r.conditions.isNotEmpty) row('Restricciones conservadas', r.conditions.join(', ')),
      if (steps.isEmpty)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
              'Resultado calculado por el motor; para esta operación no se dispone de un procedimiento simbólico detallado. '
              'Se muestran el método aplicado y la comprobación independiente.',
              style: t.bodySmall),
        ),
      if (r.elapsedMs != null)
        Padding(padding: const EdgeInsets.only(top: 4), child: Text('${r.elapsedMs!.toStringAsFixed(1)} ms', style: t.bodySmall)),
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
