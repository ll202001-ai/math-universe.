import 'package:flutter/material.dart';

/// Tecla del teclado cientifico: texto mostrado, texto insertado y desplazamiento del cursor tras insertar
/// (p. ej. "sin()" deja el cursor dentro de los parentesis).
class MathKey {
  const MathKey(this.label, this.insert, {this.cursorBack = 0, this.semantics, this.kind = KeyKind.normal});
  final String label;
  final String insert;
  final int cursorBack;
  final String? semantics;
  final KeyKind kind;
}

enum KeyKind { normal, digit, operator, action }

const _basic = <MathKey>[
  MathKey('7', '7', kind: KeyKind.digit), MathKey('8', '8', kind: KeyKind.digit), MathKey('9', '9', kind: KeyKind.digit),
  MathKey('÷', '/', kind: KeyKind.operator, semantics: 'dividir'), MathKey('(', '('), MathKey(')', ')'),
  MathKey('4', '4', kind: KeyKind.digit), MathKey('5', '5', kind: KeyKind.digit), MathKey('6', '6', kind: KeyKind.digit),
  MathKey('×', '*', kind: KeyKind.operator, semantics: 'multiplicar'), MathKey('xʸ', '^', kind: KeyKind.operator, semantics: 'potencia'),
  MathKey('√', 'sqrt()', cursorBack: 1, semantics: 'raiz cuadrada'),
  MathKey('1', '1', kind: KeyKind.digit), MathKey('2', '2', kind: KeyKind.digit), MathKey('3', '3', kind: KeyKind.digit),
  MathKey('−', '-', kind: KeyKind.operator, semantics: 'menos'), MathKey('x', 'x'), MathKey('π', 'pi', semantics: 'pi'),
  MathKey('0', '0', kind: KeyKind.digit), MathKey('.', '.', kind: KeyKind.digit, semantics: 'punto decimal'),
  MathKey('=', '='), MathKey('+', '+', kind: KeyKind.operator, semantics: 'mas'), MathKey('y', 'y'), MathKey('e', 'e', semantics: 'numero e'),
];

const _functions = <MathKey>[
  MathKey('sin', 'sin()', cursorBack: 1), MathKey('cos', 'cos()', cursorBack: 1), MathKey('tan', 'tan()', cursorBack: 1),
  MathKey('ln', 'ln()', cursorBack: 1, semantics: 'logaritmo natural'), MathKey('eˣ', 'exp()', cursorBack: 1, semantics: 'exponencial'),
  MathKey('|x|', 'abs()', cursorBack: 1, semantics: 'valor absoluto'),
  MathKey('sin⁻¹', 'asin()', cursorBack: 1, semantics: 'arcoseno'), MathKey('cos⁻¹', 'acos()', cursorBack: 1, semantics: 'arcocoseno'),
  MathKey('tan⁻¹', 'atan()', cursorBack: 1, semantics: 'arcotangente'), MathKey('x²', '^2', semantics: 'al cuadrado'),
  MathKey('x³', '^3', semantics: 'al cubo'), MathKey('n!', '!', semantics: 'factorial'),
  MathKey('sinh', 'sinh()', cursorBack: 1), MathKey('cosh', 'cosh()', cursorBack: 1), MathKey('tanh', 'tanh()', cursorBack: 1),
  MathKey('a/b', '()/()', cursorBack: 4, semantics: 'fraccion'), MathKey('ⁿ√', '^(1/)', cursorBack: 1, semantics: 'raiz n-esima'),
  MathKey('10ˣ', '10^', semantics: 'diez elevado a'),
];

const _algebra = <MathKey>[
  MathKey('x', 'x'), MathKey('y', 'y'), MathKey('z', 'z'), MathKey('a', 'a'), MathKey('b', 'b'), MathKey('c', 'c'),
  MathKey('=', '='), MathKey(';', '; ', semantics: 'separar ecuaciones'), MathKey(',', ','), MathKey('(', '('), MathKey(')', ')'),
  MathKey('^', '^'),
  MathKey('V', 'V'), MathKey('I', 'I'), MathKey('R', 'R'), MathKey('n', 'n'), MathKey('t', 't'), MathKey('k', 'k'),
];

const keypadTabs = <String, List<MathKey>>{'Básico': _basic, 'Funciones': _functions, 'Álgebra': _algebra};

/// Teclado cientifico contextual. Inserta en la posicion del cursor de [controller]; no calcula nada.
class MathKeypad extends StatefulWidget {
  const MathKeypad({super.key, required this.controller, required this.onSubmit, this.focusNode});
  final TextEditingController controller;
  final VoidCallback onSubmit;
  final FocusNode? focusNode;

  @override
  State<MathKeypad> createState() => _MathKeypadState();
}

class _MathKeypadState extends State<MathKeypad> {
  String _tab = keypadTabs.keys.first;

  TextEditingController get _c => widget.controller;

  TextSelection get _sel {
    final s = _c.selection;
    if (!s.isValid) return TextSelection.collapsed(offset: _c.text.length);
    return s;
  }

  void _insert(MathKey k) {
    final s = _sel;
    final text = _c.text.replaceRange(s.start, s.end, k.insert);
    final pos = s.start + k.insert.length - k.cursorBack;
    _c.value = TextEditingValue(text: text, selection: TextSelection.collapsed(offset: pos));
  }

  void _backspace() {
    final s = _sel;
    if (s.start != s.end) {
      _c.value = TextEditingValue(text: _c.text.replaceRange(s.start, s.end, ''), selection: TextSelection.collapsed(offset: s.start));
    } else if (s.start > 0) {
      _c.value = TextEditingValue(text: _c.text.replaceRange(s.start - 1, s.start, ''), selection: TextSelection.collapsed(offset: s.start - 1));
    }
  }

  void _move(int d) {
    final p = (_sel.baseOffset + d).clamp(0, _c.text.length);
    _c.selection = TextSelection.collapsed(offset: p);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final keys = keypadTabs[_tab]!;
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SegmentedButton<String>(
        key: const Key('pestanas_teclado'),
        showSelectedIcon: false,
        segments: [for (final t in keypadTabs.keys) ButtonSegment(value: t, label: Text(t))],
        selected: {_tab},
        onSelectionChanged: (v) => setState(() => _tab = v.first),
      ),
      const SizedBox(height: 8),
      LayoutBuilder(builder: (context, box) {
        const cols = 6;
        final w = (box.maxWidth - (cols - 1) * 6) / cols;
        final h = w.clamp(40.0, 54.0);
        return Wrap(spacing: 6, runSpacing: 6, children: [
          for (final k in keys)
            SizedBox(
                width: w,
                height: h,
                child: _KeyButton(
                  label: k.label,
                  semantics: k.semantics ?? k.label,
                  background: switch (k.kind) {
                    KeyKind.digit => cs.surfaceContainerHighest,
                    KeyKind.operator => cs.secondaryContainer,
                    _ => cs.surfaceContainer,
                  },
                  foreground: k.kind == KeyKind.operator ? cs.onSecondaryContainer : cs.onSurface,
                  onTap: () => _insert(k),
                )),
        ]);
      }),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(child: _ActionButton(icon: Icons.chevron_left, label: 'Mover a la izquierda', onTap: () => _move(-1))),
        const SizedBox(width: 6),
        Expanded(child: _ActionButton(icon: Icons.chevron_right, label: 'Mover a la derecha', onTap: () => _move(1))),
        const SizedBox(width: 6),
        Expanded(child: _ActionButton(icon: Icons.backspace_outlined, label: 'Borrar', onTap: _backspace, key: const Key('tecla_borrar'))),
        const SizedBox(width: 6),
        Expanded(
            child: _ActionButton(
                icon: Icons.clear_all, label: 'Borrar todo', onTap: () => _c.clear(), color: cs.errorContainer, key: const Key('tecla_ac'))),
        const SizedBox(width: 6),
        Expanded(
            flex: 2,
            child: _ActionButton(
                icon: Icons.keyboard_return, label: 'Calcular', onTap: widget.onSubmit, color: cs.primary, iconColor: cs.onPrimary)),
      ]),
    ]);
  }
}

class _KeyButton extends StatelessWidget {
  const _KeyButton({required this.label, required this.semantics, required this.background, required this.foreground, required this.onTap});
  final String label;
  final String semantics;
  final Color background;
  final Color foreground;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: semantics,
      excludeSemantics: true,
      child: Material(
        color: background,
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: onTap,
          child: Center(
              child: Text(label, style: Theme.of(context).textTheme.titleMedium?.copyWith(color: foreground, fontWeight: FontWeight.w500))),
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({super.key, required this.icon, required this.label, required this.onTap, this.color, this.iconColor});
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color? color;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: Material(
          color: color ?? Theme.of(context).colorScheme.surfaceContainer,
          borderRadius: BorderRadius.circular(10),
          child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: onTap,
              child: SizedBox(height: 46, child: Icon(icon, color: iconColor))),
        ),
      ),
    );
  }
}
