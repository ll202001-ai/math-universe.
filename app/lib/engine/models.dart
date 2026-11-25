/// Respuesta del motor (contrato JSON 1.1). Solo lectura: ningun calculo matematico se hace en Dart.
class EngineResponse {
  EngineResponse(this.raw);

  final Map<String, dynamic> raw;

  /// Respuesta generada por el cliente (no por el motor): motor no disponible, plazo agotado, etc.
  factory EngineResponse.local(String status, String code, String message) => EngineResponse({
        'status': status,
        'api_version': 'cliente',
        'verification': {'status': 'not_performed', 'method': null},
        'conditions': <String>[],
        'warnings': <String>[],
        'error': {'code': code, 'message': message, 'details': <String, dynamic>{}},
        'local': true,
      });

  String get status => (raw['status'] ?? 'internal_error').toString();
  String? get exactResult => raw['exact_result']?.toString();
  String? get approximateResult => raw['approximate_result']?.toString();
  String? get method => raw['method']?.toString();
  List<String> get conditions => _strings(raw['conditions']);
  List<String> get warnings => _strings(raw['warnings']);
  Map<String, dynamic> get data => (raw['data'] is Map) ? Map<String, dynamic>.from(raw['data'] as Map) : <String, dynamic>{};
  String get verificationStatus => ((raw['verification'] is Map) ? (raw['verification'] as Map)['status'] : null)?.toString() ?? 'not_performed';
  String? get verificationMethod => ((raw['verification'] is Map) ? (raw['verification'] as Map)['method'] : null)?.toString();
  String? get errorCode => ((raw['error'] is Map) ? (raw['error'] as Map)['code'] : null)?.toString();
  String? get errorMessage => ((raw['error'] is Map) ? (raw['error'] as Map)['message'] : null)?.toString();
  double? get elapsedMs => (raw['elapsed_ms'] is num) ? (raw['elapsed_ms'] as num).toDouble() : null;

  /// Interpretacion del motor (forma canonica de la entrada), si la envia.
  String? get interpretation {
    final p = raw['parsed_input'];
    if (p is! Map) return null;
    final c = p['canonical'];
    if (c is List) return c.join(' ; ');
    return c?.toString();
  }

  /// Hay un resultado matematico que mostrar (exacto, familia de soluciones o conjunto vacio).
  bool get hasResult => const {'success_exact', 'success_approximate', 'multiple_solutions', 'no_solution'}.contains(status);

  /// Matriz de resultado (lista de filas de textos) si la respuesta la trae en data.matrix.
  List<List<String>>? get matrix {
    final m = data['matrix'];
    if (m is! List) return null;
    return m.map<List<String>>((r) => (r as List).map((e) => e.toString()).toList()).toList();
  }

  static List<String> _strings(dynamic v) => (v is List) ? v.map((e) => e.toString()).toList() : <String>[];
}

const matrixOperations = <String, String>{
  'matrix_add': 'Suma A + B',
  'matrix_sub': 'Resta A - B',
  'matrix_mul': 'Producto A x B',
  'matrix_transpose': 'Transpuesta',
  'matrix_det': 'Determinante',
  'matrix_inverse': 'Inversa',
  'matrix_rank': 'Rango',
  'matrix_rref': 'Forma escalonada reducida',
  'matrix_solve': 'Resolver A x = b',
};

const matrixOpsNeedingB = {'matrix_add', 'matrix_sub', 'matrix_mul', 'matrix_solve'};

const calculusOperations = <String, String>{
  'evaluate': 'Calcular',
  'simplify': 'Simplificar',
  'expand': 'Expandir',
  'factor': 'Factorizar',
  'solve': 'Resolver / despejar',
  'differentiate': 'Derivar',
  'integrate': 'Integrar',
  'limit': 'Límite',
};

/// Operacion sugerida para una entrada (la interfaz la muestra y el usuario puede cambiarla antes de calcular).
/// No interpreta matematicas: solo mira si hay '=' o letras.
String suggestOperation(String text) {
  final t = text.trim();
  if (t.contains('=') || t.contains(';')) return 'solve';
  final noFunctions = t.replaceAll(RegExp(r'\b(sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|ln|log|exp|sqrt|abs|pi|e)\b'), '');
  if (RegExp(r'[A-Za-z]').hasMatch(noFunctions)) return 'simplify';
  return 'evaluate';
}

/// Descripcion legible de los metodos y verificaciones que informa el motor (contrato 1.1). Si un metodo no esta en
/// la tabla se muestra su nombre tecnico tal cual: nunca se inventa una descripcion.
const methodDescriptions = <String, String>{
  'aritmetica_racional_exacta': 'Aritmética racional exacta (fracciones sin decimales)',
  'simplificacion_exacta': 'Simplificación exacta (radicales y constantes conservados)',
  'cancelacion_racional_exacta': 'Cancelación exacta de factores comunes (conservando el dominio original)',
  'comparacion_aritmetica_exacta': 'Comparación aritmética exacta',
  'analisis_polinomico_exacto': 'Análisis polinómico exacto',
  'factorizacion_racional_Q': 'Factorización sobre los racionales',
  'factorizacion_racional_y_formula_cuadratica': 'Factorización racional y fórmula cuadrática',
  'eliminacion_gauss_jordan': 'Eliminación de Gauss-Jordan exacta',
  'despeje_literal_grado_1': 'Despeje literal (ecuación de primer grado en la variable)',
  'reglas_de_derivacion_sobre_el_AST': 'Reglas de derivación (producto, cociente, cadena)',
  'integracion_simbolica_propia': 'Integración simbólica del motor',
  'teorema_fundamental_del_calculo_con_primitiva_propia': 'Regla de Barrow con la primitiva obtenida',
  'series_de_Laurent_exactas': 'Desarrollo en serie exacto alrededor del punto',
  'algebra_lineal_exacta_Q': 'Álgebra lineal exacta sobre los racionales',
  'sympy_respaldo_experimental': 'SymPy (motor simbólico de respaldo)',
  'parser_seguro': 'Analizador sintáctico seguro',
  'sustitucion_exacta_en_la_ecuacion_original': 'Sustitución exacta de cada solución en la ecuación original',
  'evaluacion_en_puntos_exactos_del_original_vs_resultado': 'Comparación exacta del original y el resultado en puntos de prueba',
  'diferencias_finitas_centrales_de_orden_4_del_original': 'Contraste numérico con diferencias finitas del original',
  'diferencias_finitas_del_original': 'Contraste numérico con diferencias finitas del original',
  'derivada_numerica_de_la_primitiva': 'Derivación numérica de la primitiva comparada con el integrando',
  'evaluacion_en_puntos': 'Comparación del original y el resultado en puntos de prueba',
  'expansion_polinomica_exacta': 'Expansión polinómica exacta',
};

String describeMethod(String? m) => m == null ? '' : (methodDescriptions[m] ?? m.replaceAll('_', ' '));

/// "1 2 3\n4 5 6" (o con comas/punto y coma) -> [["1","2","3"],["4","5","6"]]. Lanza FormatException si no es rectangular.
List<List<String>> parseMatrixText(String text) {
  final rows = text
      .split(RegExp(r'[\n;]'))
      .map((l) => l.trim())
      .where((l) => l.isNotEmpty)
      .map((l) => l.split(RegExp(r'[\s,]+')).where((c) => c.isNotEmpty).toList())
      .toList();
  if (rows.isEmpty) throw const FormatException('La matriz esta vacia');
  final n = rows.first.length;
  if (rows.any((r) => r.length != n)) throw const FormatException('Todas las filas deben tener el mismo numero de columnas');
  return rows;
}
