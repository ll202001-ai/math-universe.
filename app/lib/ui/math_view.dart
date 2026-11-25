import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

/// Formula dibujada a partir del LaTeX que genera el motor (fracciones, raices, exponentes, matrices).
/// Si el LaTeX no se puede dibujar, se muestra el texto [fallback] (nunca se pierde el resultado).
/// Las formulas largas se desplazan en horizontal en lugar de cortarse.
class MathView extends StatelessWidget {
  const MathView(this.latex, {super.key, this.fallback, this.fontSize, this.color, this.selectable = false});

  final String? latex;
  final String? fallback;
  final double? fontSize;
  final Color? color;
  final bool selectable;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.titleLarge!.copyWith(fontSize: fontSize, color: color);
    final tex = latex;
    Widget fb() => SelectableText(fallback ?? tex ?? '', style: style.copyWith(fontFamily: 'monospace'));
    if (tex == null || tex.isEmpty) return fb();
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Math.tex(
        tex,
        mathStyle: MathStyle.display,
        textStyle: style,
        onErrorFallback: (_) => fb(),
      ),
    );
  }
}
