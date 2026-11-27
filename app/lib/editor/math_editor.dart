import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../ui/math_view.dart';
import 'editor_controller.dart';
import 'math_node.dart';

/// Area de trabajo del editor: dibuja la expresion con su cursor (fracciones, raices, exponentes, matrices…),
/// recibe el teclado fisico y ofrece deshacer, rehacer, copiar, pegar y limpiar.
class MathEditor extends StatefulWidget {
  const MathEditor({super.key, required this.controller, this.onSubmit, this.autofocus = false, this.focusNode});
  final EditorController controller;
  final VoidCallback? onSubmit;
  final bool autofocus;
  final FocusNode? focusNode;

  @override
  State<MathEditor> createState() => _MathEditorState();
}

class _MathEditorState extends State<MathEditor> {
  late final FocusNode _focus = widget.focusNode ?? FocusNode(debugLabel: 'editor_matematico');

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_changed);
    _focus.addListener(_changed);
  }

  @override
  void didUpdateWidget(MathEditor old) {
    super.didUpdateWidget(old);
    if (old.controller != widget.controller) {
      old.controller.removeListener(_changed);
      widget.controller.addListener(_changed);
    }
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.controller.removeListener(_changed);
    _focus.removeListener(_changed);
    if (widget.focusNode == null) _focus.dispose();
    super.dispose();
  }

  KeyEventResult _onKey(FocusNode n, KeyEvent e) {
    if ((e is KeyDownEvent) && (e.logicalKey == LogicalKeyboardKey.enter || e.logicalKey == LogicalKeyboardKey.numpadEnter)) {
      widget.controller.flushPending();
      widget.onSubmit?.call();
      return KeyEventResult.handled;
    }
    final ctrl = HardwareKeyboard.instance.isControlPressed || HardwareKeyboard.instance.isMetaPressed;
    if (ctrl && e is KeyDownEvent && e.logicalKey == LogicalKeyboardKey.keyV) {
      _paste();
      return KeyEventResult.handled;
    }
    if (ctrl && e is KeyDownEvent && e.logicalKey == LogicalKeyboardKey.keyC) {
      _copy();
      return KeyEventResult.handled;
    }
    return widget.controller.handleKey(e) ? KeyEventResult.handled : KeyEventResult.ignored;
  }

  Future<void> _paste() async {
    final d = await Clipboard.getData(Clipboard.kTextPlain);
    final t = d?.text?.trim();
    if (t != null && t.isNotEmpty) widget.controller.setText(t);
  }

  Future<void> _copy() async {
    try {
      await Clipboard.setData(ClipboardData(text: widget.controller.toEngine()));
    } on EditorError {
      // expresion incompleta: no se copia
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final c = widget.controller;
    final focused = _focus.hasFocus;
    return Focus(
      focusNode: _focus,
      autofocus: widget.autofocus,
      onKeyEvent: _onKey,
      child: GestureDetector(
        key: const Key('area_editor'),
        behavior: HitTestBehavior.opaque,
        onTap: () {
          _focus.requestFocus();
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          constraints: const BoxConstraints(minHeight: 96),
          padding: const EdgeInsets.fromLTRB(16, 10, 6, 6),
          decoration: BoxDecoration(
            color: cs.surfaceContainerLowest,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: focused ? cs.primary : cs.outlineVariant, width: focused ? 2 : 1),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Semantics(
              label: 'Expresión: ${_safe(c)}',
              child: c.isEmpty
                  ? Row(children: [
                      MathView(cursorLatex, fontSize: 30),
                      const SizedBox(width: 8),
                      Flexible(
                          child: Text('Escriba con el teclado matemático o el del equipo',
                              style: TextStyle(color: cs.onSurfaceVariant), overflow: TextOverflow.ellipsis)),
                    ])
                  : MathView(c.toLatex(), key: const Key('editor_latex'), fontSize: 30),
            ),
            Row(mainAxisAlignment: MainAxisAlignment.end, children: [
              _tool(Icons.undo, 'Deshacer', c.canUndo ? c.undo : null, 'editor_deshacer'),
              _tool(Icons.redo, 'Rehacer', c.canRedo ? c.redo : null, 'editor_rehacer'),
              _tool(Icons.content_copy, 'Copiar como texto', c.isEmpty ? null : _copy, 'editor_copiar'),
              _tool(Icons.content_paste, 'Pegar expresión', _paste, 'editor_pegar'),
              _tool(Icons.clear, 'Limpiar', c.isEmpty ? null : c.clear, 'editor_limpiar'),
            ]),
          ]),
        ),
      ),
    );
  }

  String _safe(EditorController c) {
    try {
      return c.toEngine();
    } on EditorError {
      return 'incompleta';
    }
  }

  Widget _tool(IconData i, String tip, VoidCallback? f, String key) =>
      IconButton(key: Key(key), visualDensity: VisualDensity.compact, iconSize: 20, tooltip: tip, onPressed: f, icon: Icon(i));
}
