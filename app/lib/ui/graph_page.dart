import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import '../engine/engine_client.dart';
import '../engine/models.dart';

/// Graficas interactivas. Los puntos los calcula el MOTOR (operaciones plot/plot3d/parametric/polar); aqui solo se
/// dibujan. Al acercar o desplazar se vuelve a muestrear la vista para no perder detalle.
class GraphPage extends StatefulWidget {
  const GraphPage({super.key, required this.engine});
  final EngineClient engine;

  @override
  State<GraphPage> createState() => _GraphPageState();
}

enum GraphMode { function, parametric, polar, surface }

const _modeOps = {
  GraphMode.function: 'plot',
  GraphMode.parametric: 'parametric',
  GraphMode.polar: 'polar',
  GraphMode.surface: 'plot3d',
};

const _modeHints = {
  GraphMode.function: 'sin(x); x^2/4; 1/x',
  GraphMode.parametric: 'cos(3*t); sin(2*t)',
  GraphMode.polar: '1+cos(t)',
  GraphMode.surface: 'sin(x)*cos(y)',
};

const seriesColors = [Color(0xFF1B5E8C), Color(0xFFD1495B), Color(0xFF2A9D8F), Color(0xFFE9A03B), Color(0xFF6A4C93), Color(0xFF3D405B)];

class _GraphPageState extends State<GraphPage> {
  final TextEditingController _expr = TextEditingController(text: 'sin(x); x^2/4');
  GraphMode _mode = GraphMode.function;
  Rect _view = const Rect.fromLTRB(-10, -6, 10, 6); // x: left..right, y: top=ymin .. bottom=ymax
  Map<String, dynamic>? _data;
  String? _error;
  bool _busy = false;
  Timer? _resample;
  double _yaw = -0.6, _pitch = 0.5;
  Rect? _scaleStartView;
  Offset? _scaleStartFocal;

  @override
  void initState() {
    super.initState();
    _plot(resetView: true);
  }

  @override
  void dispose() {
    _resample?.cancel();
    _expr.dispose();
    super.dispose();
  }

  Future<void> _plot({bool resetView = false}) async {
    final text = _expr.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final params = <String, dynamic>{};
    switch (_mode) {
      case GraphMode.function:
        params.addAll({'xmin': _view.left, 'xmax': _view.right, 'samples': 800});
      case GraphMode.surface:
        params.addAll({'xmin': -3, 'xmax': 3, 'ymin': -3, 'ymax': 3, 'grid': 40});
      case GraphMode.parametric:
      case GraphMode.polar:
        params.addAll({'tmin': 0, 'tmax': 2 * math.pi, 'samples': 1200});
    }
    final r = await widget.engine.send({'operation': _modeOps[_mode], 'expression': text, 'params': params, 'timeout_ms': 20000});
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (r.status != 'success_exact') {
        _error = r.errorMessage ?? r.status;
        return;
      }
      if (r.data['x_range'] is! List || r.data['y_range'] is! List) {
        if (r.data['grid'] is! List) {
          _error = 'El motor no devolvió datos de gráfica';
          return;
        }
      }
      _data = r.data;
      if (resetView && _mode != GraphMode.surface && r.data['x_range'] is List && r.data['y_range'] is List) {
        final xr = (r.data['x_range'] as List).cast<num>();
        final yr = (r.data['y_range'] as List).cast<num>();
        if (_mode == GraphMode.function) {
          _view = Rect.fromLTRB(xr[0].toDouble(), yr[0].toDouble(), xr[1].toDouble(), yr[1].toDouble());
        } else {
          final pad = 0.15 * math.max(xr[1] - xr[0], yr[1] - yr[0]).toDouble() + 0.1;
          _view = Rect.fromLTRB(xr[0] - pad, yr[0] - pad, xr[1] + pad, yr[1] + pad);
        }
      }
    });
  }

  void _scheduleResample() {
    if (_mode != GraphMode.function) return;
    _resample?.cancel();
    _resample = Timer(const Duration(milliseconds: 250), () => _plot());
  }

  void _zoom(double factor, Offset focalFrac) {
    final fx = _view.left + _view.width * focalFrac.dx;
    final fy = _view.bottom - _view.height * focalFrac.dy;
    setState(() {
      _view = Rect.fromLTRB(fx - (fx - _view.left) * factor, fy - (fy - _view.top) * factor, fx + (_view.right - fx) * factor,
          fy + (_view.bottom - fy) * factor);
    });
    _scheduleResample();
  }

  Widget _canvas(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return LayoutBuilder(builder: (context, box) {
      final size = Size(box.maxWidth, box.maxHeight);
      final surface = _mode == GraphMode.surface;
      return Listener(
        onPointerSignal: (e) {
          if (e is PointerScrollEvent && !surface) {
            _zoom(e.scrollDelta.dy > 0 ? 1.15 : 1 / 1.15, Offset(e.localPosition.dx / size.width, e.localPosition.dy / size.height));
          }
        },
        child: GestureDetector(
          onScaleStart: (d) {
            _scaleStartView = _view;
            _scaleStartFocal = d.localFocalPoint;
          },
          onScaleUpdate: (d) {
            if (surface) {
              setState(() {
                _yaw += d.focalPointDelta.dx * 0.01;
                _pitch = (_pitch + d.focalPointDelta.dy * 0.01).clamp(-1.5, 1.5);
              });
              return;
            }
            final v0 = _scaleStartView!, f0 = _scaleStartFocal!;
            final s = 1 / d.scale;
            final dx = -(d.localFocalPoint.dx - f0.dx) / size.width * v0.width * s;
            final dy = (d.localFocalPoint.dy - f0.dy) / size.height * v0.height * s;
            final fx = v0.left + v0.width * f0.dx / size.width;
            final fy = v0.bottom - v0.height * f0.dy / size.height;
            setState(() {
              _view = Rect.fromLTRB(fx - (fx - v0.left) * s + dx, fy - (fy - v0.top) * s + dy, fx + (v0.right - fx) * s + dx,
                  fy + (v0.bottom - fy) * s + dy);
            });
          },
          onScaleEnd: (_) => _scheduleResample(),
          child: ClipRect(
            child: CustomPaint(
              key: const Key('lienzo_grafica'),
              size: size,
              painter: surface
                  ? SurfacePainter(_data, yaw: _yaw, pitch: _pitch, colorScheme: cs)
                  : PlotPainter(_data, _view, colorScheme: cs),
            ),
          ),
        ),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final series = (_data?['series'] as List?)?.whereType<Map>().toList() ?? const [];
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
        child: Column(children: [
          SegmentedButton<GraphMode>(
            key: const Key('modo_grafica'),
            showSelectedIcon: false,
            segments: const [
              ButtonSegment(value: GraphMode.function, label: Text('y = f(x)')),
              ButtonSegment(value: GraphMode.parametric, label: Text('Paramétrica')),
              ButtonSegment(value: GraphMode.polar, label: Text('Polar')),
              ButtonSegment(value: GraphMode.surface, label: Text('3D')),
            ],
            selected: {_mode},
            onSelectionChanged: (v) {
              setState(() {
                _mode = v.first;
                _expr.text = _modeHints[_mode]!;
                _data = null;
                if (_mode == GraphMode.function) _view = const Rect.fromLTRB(-10, -6, 10, 6);
              });
              _plot(resetView: true);
            },
          ),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: TextField(
                key: const Key('campo_grafica'),
                controller: _expr,
                style: const TextStyle(fontFamily: 'monospace'),
                decoration: InputDecoration(
                    isDense: true,
                    border: const OutlineInputBorder(),
                    labelText: switch (_mode) {
                      GraphMode.function => 'Funciones de x (separadas por ;)',
                      GraphMode.parametric => 'x(t); y(t)',
                      GraphMode.polar => 'r(t)',
                      GraphMode.surface => 'z = f(x, y)',
                    }),
                onSubmitted: (_) => _plot(resetView: true),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.icon(
                key: const Key('boton_graficar'),
                onPressed: _busy ? null : () => _plot(resetView: true),
                icon: _busy ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.show_chart),
                label: const Text('Graficar')),
          ]),
        ]),
      ),
      if (_error != null)
        Padding(padding: const EdgeInsets.all(8), child: Text(_error!, key: const Key('error_grafica'), style: TextStyle(color: Theme.of(context).colorScheme.error))),
      Expanded(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: DecoratedBox(
            decoration: BoxDecoration(
                border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular(12)),
            child: ClipRRect(borderRadius: BorderRadius.circular(12), child: _canvas(context)),
          ),
        ),
      ),
      if (_mode != GraphMode.surface && series.isNotEmpty)
        SizedBox(
          height: 64,
          child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12), children: [
            for (var i = 0; i < series.length; i++)
              Padding(
                padding: const EdgeInsets.only(right: 16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Container(width: 14, height: 4, color: seriesColors[i % seriesColors.length]),
                    const SizedBox(width: 6),
                    Text('${series[i]['expression']}', style: const TextStyle(fontFamily: 'monospace')),
                  ]),
                  if ((series[i]['roots'] as List?)?.isNotEmpty ?? false)
                    Text('ceros ≈ ${(series[i]['roots'] as List).take(6).map((r) => _fmt(r as num)).join(', ')}',
                        style: Theme.of(context).textTheme.bodySmall),
                ]),
              ),
            IconButton(
                tooltip: 'Restablecer la vista',
                onPressed: () {
                  setState(() => _view = const Rect.fromLTRB(-10, -6, 10, 6));
                  _plot(resetView: true);
                },
                icon: const Icon(Icons.center_focus_strong)),
          ]),
        ),
      if (_mode == GraphMode.surface)
        const Padding(padding: EdgeInsets.only(bottom: 8), child: Text('Arrastre para girar la superficie')),
    ]);
  }
}

String _fmt(num v) => v.abs() >= 1e4 || (v != 0 && v.abs() < 1e-3) ? v.toStringAsExponential(3) : double.parse(v.toStringAsFixed(4)).toString();

/// Dibuja ejes, cuadricula y las series (segmentos) devueltas por el motor en la vista [view].
class PlotPainter extends CustomPainter {
  PlotPainter(this.data, this.view, {required this.colorScheme});
  final Map<String, dynamic>? data;
  final Rect view;
  final ColorScheme colorScheme;

  Offset toScreen(double x, double y, Size s) =>
      Offset((x - view.left) / view.width * s.width, s.height - (y - view.top) / view.height * s.height);

  static double niceStep(double range) {
    final raw = range / 8;
    final p = math.pow(10, (math.log(raw) / math.ln10).floor()).toDouble();
    for (final m in [1, 2, 5, 10]) {
      if (raw <= m * p) return m * p;
    }
    return 10 * p;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = colorScheme.outlineVariant.withValues(alpha: 0.5)
      ..strokeWidth = 1;
    final axis = Paint()
      ..color = colorScheme.onSurfaceVariant
      ..strokeWidth = 1.4;
    final label = TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 10);
    final sx = niceStep(view.width), sy = niceStep(view.height);
    for (var x = (view.left / sx).ceil() * sx; x <= view.right; x += sx) {
      final p = toScreen(x, 0, size);
      canvas.drawLine(Offset(p.dx, 0), Offset(p.dx, size.height), grid);
      _text(canvas, _fmt(x), Offset(p.dx + 2, (toScreen(0, 0, size).dy + 2).clamp(0, size.height - 12)), label);
    }
    for (var y = (view.top / sy).ceil() * sy; y <= view.bottom; y += sy) {
      final p = toScreen(0, y, size);
      canvas.drawLine(Offset(0, p.dy), Offset(size.width, p.dy), grid);
      if (y.abs() > sy / 2) _text(canvas, _fmt(y), Offset((toScreen(0, 0, size).dx + 3).clamp(0, size.width - 30), p.dy - 12), label);
    }
    final o = toScreen(0, 0, size);
    canvas.drawLine(Offset(0, o.dy), Offset(size.width, o.dy), axis);
    canvas.drawLine(Offset(o.dx, 0), Offset(o.dx, size.height), axis);
    final series = (data?['series'] as List?)?.whereType<Map>().toList() ?? const [];
    for (var i = 0; i < series.length; i++) {
      final color = seriesColors[i % seriesColors.length];
      final pen = Paint()
        ..color = color
        ..strokeWidth = 2.2
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round;
      for (final seg in (series[i]['segments'] as List? ?? const [])) {
        final path = Path();
        var first = true;
        for (final pt in (seg as List)) {
          final q = toScreen((pt[0] as num).toDouble(), (pt[1] as num).toDouble(), size);
          if (first) {
            path.moveTo(q.dx, q.dy);
            first = false;
          } else {
            path.lineTo(q.dx, q.dy);
          }
        }
        canvas.drawPath(path, pen);
      }
      final dot = Paint()..color = color;
      for (final r in (series[i]['roots'] as List? ?? const [])) {
        canvas.drawCircle(toScreen((r as num).toDouble(), 0, size), 4, dot);
      }
      for (final e in (series[i]['extrema'] as List? ?? const []).whereType<Map>()) {
        final q = toScreen((e['x'] as num).toDouble(), (e['y'] as num).toDouble(), size);
        canvas.drawCircle(q, 3.5, Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
      }
    }
  }

  void _text(Canvas c, String s, Offset at, TextStyle st) {
    final tp = TextPainter(text: TextSpan(text: s, style: st), textDirection: TextDirection.ltr)..layout();
    tp.paint(c, at);
  }

  @override
  bool shouldRepaint(PlotPainter old) => old.data != data || old.view != view || old.colorScheme != colorScheme;
}

/// Superficie z = f(x, y) en malla, proyeccion ortografica con giro (yaw/pitch) y color segun la altura.
class SurfacePainter extends CustomPainter {
  SurfacePainter(this.data, {required this.yaw, required this.pitch, required this.colorScheme});
  final Map<String, dynamic>? data;
  final double yaw, pitch;
  final ColorScheme colorScheme;

  @override
  void paint(Canvas canvas, Size size) {
    final grid = (data?['grid'] as List?)?.map((r) => (r as List).map((v) => (v as num?)?.toDouble()).toList()).toList();
    if (grid == null || grid.isEmpty) return;
    final zr = (data!['z_range'] as List).map((v) => (v as num).toDouble()).toList();
    final n = grid.length, m = grid[0].length;
    final zspan = (zr[1] - zr[0]).abs() < 1e-12 ? 1.0 : zr[1] - zr[0];
    Offset project(int i, int j, double z) {
      final x = j / (m - 1) * 2 - 1, y = i / (n - 1) * 2 - 1, zz = ((z.clamp(zr[0], zr[1]) - zr[0]) / zspan) * 1.2 - 0.6;
      final x1 = x * math.cos(yaw) - y * math.sin(yaw);
      final y1 = x * math.sin(yaw) + y * math.cos(yaw);
      final y2 = y1 * math.sin(pitch) - zz * math.cos(pitch);
      final scale = math.min(size.width, size.height) * 0.36;
      return Offset(size.width / 2 + x1 * scale, size.height / 2 + y2 * scale);
    }

    Color shade(double z) {
      final t = ((z - zr[0]) / zspan).clamp(0.0, 1.0);
      return Color.lerp(const Color(0xFF1B5E8C), const Color(0xFFE9A03B), t)!;
    }

    final pen = Paint()
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    for (var i = 0; i < n; i++) {
      for (var j = 0; j < m; j++) {
        final z = grid[i][j];
        if (z == null) continue;
        final p = project(i, j, z);
        if (j + 1 < m && grid[i][j + 1] != null) {
          canvas.drawLine(p, project(i, j + 1, grid[i][j + 1]!), pen..color = shade(z));
        }
        if (i + 1 < n && grid[i + 1][j] != null) {
          canvas.drawLine(p, project(i + 1, j, grid[i + 1][j]!), pen..color = shade(z));
        }
      }
    }
  }

  @override
  bool shouldRepaint(SurfacePainter old) => old.data != data || old.yaw != yaw || old.pitch != pitch;
}

/// Utilidad para pruebas: numero total de segmentos de una respuesta de grafica.
int segmentCount(EngineResponse r) =>
    ((r.data['series'] as List?) ?? const []).fold<int>(0, (a, s) => a + (((s as Map)['segments'] as List?)?.length ?? 0));
