import 'package:flutter/material.dart';

import '../data/history_store.dart';
import '../engine/engine_client.dart';
import '../engine/models.dart';
import 'result_view.dart';

/// Matemática III: integrales dobles y triples, coordenadas, Jacobianos, extremos y Lagrange.
/// La página solo arma la solicitud (operación «calc3»); el motor resuelve, muestra el procedimiento paso a paso
/// y verifica con una integración numérica independiente. Ningún cálculo matemático se hace en Dart.
class _Campo {
  const _Campo(this.key, this.label, {this.hint, this.lines = 1, this.def = '', this.opciones});
  final String key;
  final String label;
  final String? hint;
  final int lines;
  final String def;
  final List<String>? opciones; // lista de opciones (desplegable)
}

class _Tipo {
  const _Tipo(this.id, this.nombre, this.ayuda, this.campos, this.build);
  final String id;
  final String nombre;
  final String ayuda;
  final List<_Campo> campos;
  final Map<String, dynamic> Function(Map<String, String> v) build;
}

List<String> _lineas(String s) => s.split(RegExp(r'[\n;]')).map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
List<String> _csv(String s) => s.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
List<List<String>> _triples(String s) => _lineas(s).map((l) {
      final p = _csv(l);
      if (p.length != 3) throw FormatException('Cada nivel debe ser «variable, límite inferior, límite superior»: «$l»');
      return p;
    }).toList();
List<List<String>> _pares(String s) => _lineas(s).map((l) {
      final p = _csv(l);
      if (p.length != 2) throw FormatException('Cada punto debe ser «x, y»: «$l»');
      return p;
    }).toList();
Map<String, String> _mapa(String s) {
  final m = <String, String>{};
  for (final l in _lineas(s)) {
    final i = l.indexOf('=');
    if (i < 1) throw FormatException('Use «variable = expresión»: «$l»');
    m[l.substring(0, i).trim()] = l.substring(i + 1).trim();
  }
  return m;
}

Map<String, dynamic> _conPunto(Map<String, dynamic> p, Map<String, String> v) {
  final pt = (v['punto'] ?? '').trim();
  if (pt.isNotEmpty) {
    final c = _csv(pt);
    if (c.length != 2) throw const FormatException('El punto debe ser «x, y»');
    p['punto'] = c;
  }
  return p;
}

const _ordenes = ['dydx', 'dxdy'];
const _cCurvas = _Campo('curvas', 'Curvas que limitan la región (una por línea)', lines: 3, hint: 'y = x^2\ny = 2*x');
const _cOrden = _Campo('orden', 'Orden de integración', opciones: _ordenes);
const _cPunto = _Campo('punto', 'Punto dentro de la región (opcional, si hay varias regiones)', hint: '1, 1');

final List<_Tipo> _tipos = [
  _Tipo('iterada', 'Integral iterada (límites dados)', 'Escriba los niveles de adentro hacia afuera: variable, límite inferior, límite superior.', const [
    _Campo('f', 'Integrando', hint: 'x*y'),
    _Campo('niveles', 'Niveles (uno por línea, el primero es la integral interna)', lines: 3, hint: 'y, 0, x\nx, 0, 1'),
  ], (v) => {'tipo': 'iterada', 'f': v['f'], 'niveles': _triples(v['niveles']!)}),
  _Tipo('area', 'Área de una región (doble integral)', 'Escriba las curvas; el motor halla las intersecciones y arma la integral.', const [_cCurvas, _cOrden, _cPunto],
      (v) => _conPunto({'tipo': 'region', 'que': 'area', 'curvas': _lineas(v['curvas']!), 'orden': v['orden']}, v)),
  _Tipo('volumen', 'Volumen bajo una superficie z = f(x,y)', 'Integral doble de z sobre la región D.', const [
    _Campo('z', 'Superficie z = ', hint: '4-x^2-y^2'),
    _cCurvas,
    _cOrden,
    _cPunto
  ], (v) => _conPunto({'tipo': 'region', 'que': 'volumen', 'z': v['z'], 'curvas': _lineas(v['curvas']!), 'orden': v['orden']}, v)),
  _Tipo('integral', 'Integral doble sobre una región', 'Integral de f(x,y) sobre la región limitada por las curvas.', const [
    _Campo('f', 'Integrando', hint: 'x+y'),
    _cCurvas,
    _cOrden,
    _cPunto
  ], (v) => _conPunto({'tipo': 'region', 'que': 'integral', 'f': v['f'], 'curvas': _lineas(v['curvas']!), 'orden': v['orden']}, v)),
  _Tipo('masa', 'Masa y centro de masa de una lámina', 'Densidad δ(x,y) sobre la región: m, M_x, M_y y centro de masa.', const [
    _Campo('delta', 'Densidad δ(x,y)', hint: 'x+y', def: '1'),
    _cCurvas,
    _cOrden,
    _cPunto
  ], (v) => _conPunto({'tipo': 'region', 'que': 'masa', 'delta': v['delta'], 'curvas': _lineas(v['curvas']!), 'orden': v['orden']}, v)),
  _Tipo('cambio_orden', 'Cambiar el orden de integración', 'Da la integral en ambos órdenes y calcula con el que tiene primitiva.', const [
    _Campo('f', 'Integrando', hint: 'exp(y^2)', def: '1'),
    _cCurvas,
    _cPunto
  ], (v) => _conPunto({'tipo': 'cambio_orden', 'f': v['f'], 'curvas': _lineas(v['curvas']!)}, v)),
  _Tipo('triple', 'Integral triple: sólido entre dos superficies', 'Sólido entre z inferior y z superior sobre la región D del plano xy. Volumen, masa, centro de masa o inercia.', const [
    _Campo('z_inf', 'z inferior', hint: '0'),
    _Campo('z_sup', 'z superior', hint: 'x'),
    _cCurvas,
    _cOrden,
    _Campo('que', 'Qué calcular', opciones: ['integral', 'masa3d', 'inercia']),
    _Campo('f', 'Integrando (solo si «integral»; 1 = volumen)', def: '1'),
    _Campo('delta', 'Densidad δ (masa3d / inercia)', def: '1'),
    _Campo('eje', 'Eje de inercia', opciones: ['z', 'x', 'y']),
    _cPunto
  ], (v) {
    final p = <String, dynamic>{
      'tipo': 'triple_region',
      'z_inf': v['z_inf'],
      'z_sup': v['z_sup'],
      'curvas': _lineas(v['curvas']!),
      'orden': v['orden'],
      'que': v['que'],
      'f': v['f'],
      'delta': v['delta'],
      'eje': v['eje'],
    };
    return _conPunto(p, v);
  }),
  _Tipo('coordenadas', 'Integral triple en cilíndricas / esféricas / polares', 'Niveles de adentro hacia afuera en las variables nuevas (r, theta, z) o (rho, phi, theta). El motor agrega el Jacobiano.', const [
    _Campo('sistema', 'Sistema', opciones: ['polares', 'cilindricas', 'esfericas']),
    _Campo('f', 'Integrando (en x, y, z)', def: '1'),
    _Campo('niveles', 'Niveles (uno por línea)', lines: 3, hint: 'z, 0, 4-r^2\nr, 0, 2\ntheta, 0, 2*pi'),
    _Campo('que', 'Qué calcular', opciones: ['integral', 'masa3d', 'inercia']),
    _Campo('delta', 'Densidad δ (masa3d / inercia)', def: '1'),
    _Campo('eje', 'Eje de inercia', opciones: ['z', 'x', 'y']),
  ], (v) => {
        'tipo': 'coordenadas',
        'sistema': v['sistema'],
        'f': v['f'],
        'niveles': _triples(v['niveles']!),
        'que': v['que'],
        'delta': v['delta'],
        'eje': v['eje'],
      }),
  _Tipo('jacobiano', 'Jacobiano de una transformación', 'Modo «directo»: x = x(u,v). Modo «inverso»: u = u(x,y) y el motor despeja.', const [
    _Campo('viejas', 'Variables originales', def: 'x, y'),
    _Campo('nuevas', 'Variables nuevas', def: 'u, v'),
    _Campo('mapa', 'Transformación (una por línea)', lines: 2, hint: 'x = u*v\ny = u/v'),
    _Campo('modo', 'Modo', opciones: ['directo', 'inverso']),
  ], (v) => {'tipo': 'jacobiano', 'viejas': _csv(v['viejas']!), 'nuevas': _csv(v['nuevas']!), 'mapa': _mapa(v['mapa']!), 'modo': v['modo']}),
  _Tipo('cambio_variables', 'Cambio de variables en integral doble', 'Transforma la región al plano uv, agrega |J| e integra.', const [
    _Campo('f', 'Integrando f(x,y)'),
    _cCurvas,
    _Campo('nuevas', 'Variables nuevas', def: 'u, v'),
    _Campo('mapa', 'Transformación (una por línea)', lines: 2, hint: 'u = x+y\nv = x-y'),
    _Campo('modo', 'Modo', opciones: ['inverso', 'directo']),
    _cOrden,
    _cPunto
  ], (v) => _conPunto({
        'tipo': 'cambio_variables',
        'f': v['f'],
        'curvas': _lineas(v['curvas']!),
        'nuevas': _csv(v['nuevas']!),
        'mapa': _mapa(v['mapa']!),
        'modo': v['modo'],
        'orden': v['orden'],
      }, v)),
  _Tipo('cambio3d', 'Cambio de variables en integral triple', 'Transformación directa x=x(r,t,z)… o inversa; límites en las variables nuevas (de la interna a la externa). Ej.: elipsoide con x=3r·cos(t), y=2r·sin(t).', const [
    _Campo('f', 'Integrando f(x,y,z)', hint: 'z*(x^2+y^2)'),
    _Campo('viejas', 'Variables originales', def: 'x, y, z'),
    _Campo('nuevas', 'Variables nuevas', def: 'r, t, z'),
    _Campo('mapa', 'Transformación (una por línea)', lines: 3, hint: 'x = 3*r*cos(t)\ny = 2*r*sin(t)\nz = z'),
    _Campo('modo', 'Modo', opciones: ['directo', 'inverso']),
    _Campo('niveles', 'Niveles (uno por línea, el primero es el interno)', lines: 3, hint: 'z, 0, 36*(1-r^2)\nr, 0, 1\nt, 0, 2*pi'),
  ], (v) => {
        'tipo': 'cambio_variables_3d',
        'f': v['f'],
        'viejas': _csv(v['viejas']!),
        'nuevas': _csv(v['nuevas']!),
        'mapa': _mapa(v['mapa']!),
        'modo': v['modo'],
        'niveles': _triples(v['niveles']!),
      }),
  _Tipo('dos_piezas', 'Sólido en dos piezas (suma de dos triples)', 'Cuando la superficie superior cambia (p. ej. z = 3 y z = 4 − y²). Cada pieza lleva su región y un punto interior.', const [
    _Campo('f', 'Integrando (1 = volumen)', def: '1'),
    _Campo('z_inf_a', 'Pieza 1: z inferior', def: '0'),
    _Campo('z_sup_a', 'Pieza 1: z superior', hint: '3'),
    _Campo('curvas_a', 'Pieza 1: curvas (una por línea)', lines: 3, hint: 'y=x\ny=2*x\ny=1'),
    _Campo('punto_a', 'Pieza 1: punto interior', hint: '0.5, 0.8'),
    _Campo('z_inf_b', 'Pieza 2: z inferior', def: '0'),
    _Campo('z_sup_b', 'Pieza 2: z superior', hint: '4-y^2'),
    _Campo('curvas_b', 'Pieza 2: curvas (una por línea)', lines: 4, hint: 'y=x\ny=2*x\ny=1\ny=2'),
    _Campo('punto_b', 'Pieza 2: punto interior', hint: '1, 1.5'),
    _cOrden,
  ], (v) {
    Map<String, dynamic> pieza(String s) {
      final p = <String, dynamic>{
        'tipo': 'triple_region',
        'f': v['f'],
        'z_inf': v['z_inf_$s'],
        'z_sup': v['z_sup_$s'],
        'curvas': _lineas(v['curvas_$s']!),
        'orden': v['orden'],
      };
      final pt = _csv(v['punto_$s'] ?? '');
      if (pt.length == 2) p['punto'] = pt;
      return p;
    }

    return {'tipo': 'suma', 'partes': [pieza('a'), pieza('b')]};
  }),
  _Tipo('extremos', 'Extremos locales (Hessiano)', 'Puntos críticos y clasificación con el criterio de Sylvester.', const [
    _Campo('f', 'f', hint: 'x^3+y^3-3*x*y'),
    _Campo('variables', 'Variables', def: 'x, y'),
  ], (v) => {'tipo': 'extremos', 'f': v['f'], 'variables': _csv(v['variables']!)}),
  _Tipo('lagrange', 'Extremos con restricciones (Lagrange)', 'Una o dos restricciones; el motor da los puntos y clasifica.', const [
    _Campo('f', 'f', hint: 'x^2+y^2'),
    _Campo('restricciones', 'Restricciones (una por línea)', lines: 2, hint: 'x*y=1'),
    _Campo('variables', 'Variables', def: 'x, y'),
  ], (v) => {'tipo': 'lagrange', 'f': v['f'], 'restricciones': _lineas(v['restricciones']!), 'variables': _csv(v['variables']!)}),
  _Tipo('ajuste', 'Mínimos cuadrados (recta y = mx + b)', 'Escriba un punto «x, y» por línea.', const [
    _Campo('puntos', 'Puntos', lines: 4, hint: '1, 2\n2, 3\n3, 5'),
  ], (v) => {'tipo': 'ajuste_lineal', 'puntos': _pares(v['puntos']!)}),
];

class Mat3Page extends StatefulWidget {
  const Mat3Page({super.key, required this.engine, required this.store});
  final EngineClient engine;
  final HistoryStore store;

  @override
  State<Mat3Page> createState() => _Mat3PageState();
}

class _Mat3PageState extends State<Mat3Page> {
  _Tipo _tipo = _tipos.first;
  final Map<String, TextEditingController> _ctl = {};
  final Map<String, String> _opc = {};
  EngineResponse? _resp;
  String? _err;
  bool _busy = false;

  String _k(_Tipo t, _Campo c) => '${t.id}.${c.key}';

  TextEditingController _c(_Tipo t, _Campo c) => _ctl.putIfAbsent(_k(t, c), () => TextEditingController(text: c.def));

  @override
  void dispose() {
    for (final c in _ctl.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _resolver() async {
    if (_busy) return;
    final t = _tipo;
    final v = <String, String>{};
    for (final c in t.campos) {
      v[c.key] = c.opciones != null ? (_opc[_k(t, c)] ?? c.opciones!.first) : _c(t, c).text.trim();
    }
    Map<String, dynamic> params;
    try {
      params = t.build(v);
    } on FormatException catch (e) {
      setState(() {
        _err = e.message;
        _resp = null;
      });
      return;
    }
    setState(() {
      _busy = true;
      _err = null;
    });
    final r = await widget.engine.send({
      'operation': 'calc3',
      'params': params,
      'latex': true,
      'steps': true,
      'timeout_ms': 60000,
    }, timeout: const Duration(seconds: 90));
    try {
      await widget.store.add(HistoryEntry(
          createdAt: DateTime.now(),
          kind: 'mat3',
          operation: 'calc3',
          input: '${t.nombre}: ${v.entries.where((e) => e.value.isNotEmpty).map((e) => '${e.key}=${e.value.replaceAll('\n', ' ; ')}').join(', ')}',
          result: r.exactResult ?? r.approximateResult ?? r.errorMessage ?? r.status,
          status: r.status));
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _resp = r;
      _busy = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final th = Theme.of(context);
    final t = _tipo;
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Matemática III', style: th.textTheme.titleLarge),
      const SizedBox(height: 4),
      Text('Elija el tipo de ejercicio, escriba los datos y el motor muestra el procedimiento paso a paso y lo verifica de forma independiente.',
          style: th.textTheme.bodySmall),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(
        key: const Key('selector_tipo_mat3'),
        initialValue: t.id,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'Tipo de ejercicio', border: OutlineInputBorder()),
        items: [for (final x in _tipos) DropdownMenuItem(value: x.id, child: Text(x.nombre, overflow: TextOverflow.ellipsis))],
        onChanged: (id) => setState(() {
          _tipo = _tipos.firstWhere((x) => x.id == id);
          _resp = null;
          _err = null;
        }),
      ),
      const SizedBox(height: 8),
      Text(t.ayuda, style: th.textTheme.bodySmall),
      const SizedBox(height: 8),
      for (final c in t.campos)
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: c.opciones != null
              ? DropdownButtonFormField<String>(
                  key: Key('mat3_${t.id}_${c.key}'),
                  initialValue: _opc[_k(t, c)] ?? c.opciones!.first,
                  decoration: InputDecoration(labelText: c.label, border: const OutlineInputBorder(), isDense: true),
                  items: [for (final o in c.opciones!) DropdownMenuItem(value: o, child: Text(o))],
                  onChanged: (o) => setState(() => _opc[_k(t, c)] = o ?? c.opciones!.first),
                )
              : TextField(
                  key: Key('mat3_${t.id}_${c.key}'),
                  controller: _c(t, c),
                  minLines: c.lines,
                  maxLines: c.lines == 1 ? 1 : c.lines + 2,
                  decoration: InputDecoration(labelText: c.label, hintText: c.hint, border: const OutlineInputBorder(), isDense: true),
                ),
        ),
      FilledButton.icon(
          key: const Key('boton_mat3'),
          onPressed: _busy ? null : _resolver,
          icon: const Icon(Icons.calculate),
          label: Text(_busy ? 'Resolviendo…' : 'Resolver paso a paso')),
      if (_err != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_err!, style: TextStyle(color: th.colorScheme.error))),
      const SizedBox(height: 12),
      if (_resp != null) ResultView(response: _resp!),
    ]);
  }
}
