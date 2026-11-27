import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

import 'editor_controller.dart';
import 'keyboard_layout.dart';

/// Teclado matematico de 10 pestañas. Cada tecla actua sobre el editor (inserta un simbolo o una plantilla) o pide
/// una operacion a la pantalla. Cambiar de pestaña nunca altera la expresion.
class MathKeyboard extends StatefulWidget {
  const MathKeyboard({super.key, required this.controller, required this.host, this.compact = false});
  final EditorController controller;
  final KeyboardHost host;
  final bool compact;

  @override
  State<MathKeyboard> createState() => _MathKeyboardState();
}

class _MathKeyboardState extends State<MathKeyboard> {
  String _tab = keyboardTabs.keys.first;

  EditorController get _c => widget.controller;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final keys = keyboardTabs[_tab]!;
    return Material(
      color: cs.surfaceContainer,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(
            height: 38,
            child: ListView(key: const Key('pestanas_teclado'), scrollDirection: Axis.horizontal, children: [
              for (final t in keyboardTabs.keys)
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: ChoiceChip(
                    key: Key('pestana_$t'),
                    label: Text(t),
                    selected: _tab == t,
                    showCheckmark: false,
                    visualDensity: VisualDensity.compact,
                    onSelected: (_) => setState(() => _tab = t),
                  ),
                ),
            ]),
          ),
          const SizedBox(height: 6),
          LayoutBuilder(builder: (context, box) {
            final cols = box.maxWidth >= 640 ? 8 : 6;
            final w = (box.maxWidth - (cols - 1) * 5) / cols;
            final h = widget.compact ? 40.0 : (w * 0.62).clamp(42.0, 52.0);
            return Wrap(spacing: 5, runSpacing: 5, children: [
              for (final k in keys) SizedBox(width: w, height: h, child: _key(context, k)),
            ]);
          }),
          const SizedBox(height: 6),
          _controlRow(context),
          const SizedBox(height: 5),
          _actionRow(context),
        ]),
      ),
    );
  }

  Widget _key(BuildContext context, MathKey k) {
    final cs = Theme.of(context).colorScheme;
    final (bg, fg) = switch (k.style) {
      KeyStyle.digit => (cs.surfaceContainerHighest, cs.onSurface),
      KeyStyle.op => (cs.secondaryContainer, cs.onSecondaryContainer),
      KeyStyle.struct => (cs.primaryContainer, cs.onPrimaryContainer),
      KeyStyle.func => (cs.tertiaryContainer, cs.onTertiaryContainer),
      KeyStyle.action => (cs.primary, cs.onPrimary),
      KeyStyle.normal => (cs.surfaceContainerLowest, cs.onSurface),
    };
    final style = TextStyle(color: fg, fontSize: 17, fontWeight: FontWeight.w500);
    return Semantics(
      button: true,
      label: k.semantics,
      excludeSemantics: true,
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          key: Key('tecla_${k.keyId}'),
          borderRadius: BorderRadius.circular(10),
          onTap: () => k.action(_c, widget.host),
          child: Center(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: k.tex
                    ? Math.tex(k.label, textStyle: style, onErrorFallback: (_) => Text(k.label, style: style))
                    : Text(k.label, style: style),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _controlRow(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    Widget b(IconData i, String tip, VoidCallback f, String key, {Color? color, Color? fg}) => Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2.5),
            child: Tooltip(
              message: tip,
              child: Semantics(
                button: true,
                label: tip,
                excludeSemantics: true,
                child: Material(
                  color: color ?? cs.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                  child: InkWell(
                      key: Key(key),
                      borderRadius: BorderRadius.circular(10),
                      onTap: f,
                      child: SizedBox(height: 42, child: Icon(i, color: fg, size: 20))),
                ),
              ),
            ),
          ),
        );
    return Row(children: [
      b(Icons.chevron_left, 'Izquierda', _c.left, 'tecla_izquierda'),
      b(Icons.chevron_right, 'Derecha', _c.right, 'tecla_derecha'),
      b(Icons.keyboard_arrow_up, 'Arriba (numerador, límite superior…)', _c.up, 'tecla_arriba'),
      b(Icons.keyboard_arrow_down, 'Abajo (denominador, límite inferior…)', _c.down, 'tecla_abajo'),
      b(Icons.keyboard_tab, 'Siguiente casilla vacía', _c.nextEmpty, 'tecla_siguiente'),
      b(Icons.undo, 'Deshacer', _c.undo, 'tecla_deshacer'),
      b(Icons.redo, 'Rehacer', _c.redo, 'tecla_rehacer'),
      b(Icons.backspace_outlined, 'Borrar', _c.backspace, 'tecla_borrar'),
      b(Icons.clear_all, 'Limpiar expresión', _c.clear, 'tecla_ac', color: cs.errorContainer, fg: cs.onErrorContainer),
    ]);
  }

  Widget _actionRow(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    Widget a(String label, String op, {bool primary = false}) => Expanded(
          flex: primary ? 2 : 3,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2.5),
            child: primary
                ? FilledButton(
                    key: const Key('tecla_calcular'),
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(44), padding: EdgeInsets.zero),
                    onPressed: widget.host.calculate,
                    child: const Text('=', style: TextStyle(fontSize: 22)))
                : OutlinedButton(
                    key: Key('accion_$op'),
                    style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(44), padding: const EdgeInsets.symmetric(horizontal: 2), foregroundColor: cs.primary),
                    onPressed: () => widget.host.setOperation(op, calculate: true),
                    child: FittedBox(child: Text(label))),
          ),
        );
    return Row(children: [
      a('Simplificar', 'simplify'),
      a('Expandir', 'expand'),
      a('Factorizar', 'factor'),
      a('Resolver', 'solve'),
      a('=', 'evaluate', primary: true),
    ]);
  }
}
