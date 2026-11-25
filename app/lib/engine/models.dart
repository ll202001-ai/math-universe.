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

  /// LaTeX de la entrada y del resultado (contrato 1.2, si se pidio con latex: true).
  String? get latexInput => (raw['latex'] is Map) ? (raw['latex'] as Map)['input']?.toString() : null;
  String? get latexResult => (raw['latex'] is Map) ? (raw['latex'] as Map)['result']?.toString() : null;

  /// Pasos del procedimiento generados por el motor (contrato 1.2, si se pidieron con steps: true).
  List<({String text, String? latex})> get steps {
    final s = raw['steps'];
    if (s is! List) return const [];
    return [
      for (final e in s)
        if (e is Map) (text: e['text']?.toString() ?? '', latex: e['latex']?.toString())
    ];
  }

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
  'eigen': 'Autovalores y autovectores',
};

const matrixOpsNeedingB = {'matrix_add', 'matrix_sub', 'matrix_mul', 'matrix_solve'};

/// Campos contextuales que una operacion necesita (la interfaz solo muestra los que aplican).
enum OpField { variable, variables, point, direction, order, bounds, conditions }

/// Una herramienta de la calculadora: operacion del contrato, categoria, etiqueta, palabras de busqueda y ejemplo.
class OpSpec {
  const OpSpec(this.id, this.label, this.category, {this.fields = const {}, this.keywords = '', this.example, this.hint});
  final String id;
  final String label;
  final String category;
  final Set<OpField> fields;
  final String keywords;
  final String? example;
  final String? hint;
}

const opCategories = <String>[
  'Básico',
  'Álgebra',
  'Cálculo',
  'Varias variables',
  'Ecuaciones diferenciales',
  'Transformadas',
  'Estadística',
  'Complejos',
  'Unidades',
];

const opCatalog = <OpSpec>[
  OpSpec('evaluate', 'Calcular', 'Básico', keywords: 'evaluar aritmetica fracciones decimal valor', example: '1/3+1/6'),
  OpSpec('simplify', 'Simplificar', 'Álgebra', keywords: 'reducir cancelar dominio', example: '(x^3-8)/(x-2)'),
  OpSpec('expand', 'Expandir', 'Álgebra', keywords: 'desarrollar multiplicar', example: '(x-2)*(x-3)'),
  OpSpec('factor', 'Factorizar', 'Álgebra', keywords: 'factores polinomio raices', example: 'x^2-5*x+6'),
  OpSpec('solve', 'Resolver / despejar', 'Álgebra',
      fields: {OpField.variable}, keywords: 'ecuacion sistema despejar incognita', example: 'x^2-5*x+6=0'),
  OpSpec('inequality', 'Inecuación', 'Álgebra', keywords: 'desigualdad intervalo mayor menor', example: 'x^2-5*x+6>0'),
  OpSpec('differentiate', 'Derivar', 'Cálculo',
      fields: {OpField.variable, OpField.order}, keywords: 'derivada pendiente', example: 'x^3*sin(x)'),
  OpSpec('integrate', 'Integrar', 'Cálculo',
      fields: {OpField.variable, OpField.bounds}, keywords: 'integral primitiva area', example: 'x^2'),
  OpSpec('limit', 'Límite', 'Cálculo',
      fields: {OpField.variable, OpField.point, OpField.direction}, keywords: 'tiende limite', example: 'sin(x)/x'),
  OpSpec('series', 'Serie de Taylor', 'Cálculo',
      fields: {OpField.variable, OpField.point, OpField.order}, keywords: 'taylor maclaurin aproximacion polinomio', example: 'sin(x)'),
  OpSpec('partial', 'Derivada parcial', 'Varias variables',
      fields: {OpField.variables}, keywords: 'parcial mixta', example: 'x^3*y^2', hint: 'Variables en orden de derivación, p. ej. x, y'),
  OpSpec('gradient', 'Gradiente', 'Varias variables', fields: {OpField.variables}, keywords: 'nabla vector', example: 'x^2*y'),
  OpSpec('hessian', 'Hessiano', 'Varias variables', fields: {OpField.variables}, keywords: 'segunda derivada matriz', example: 'x^2+x*y+y^2'),
  OpSpec('jacobian', 'Jacobiano', 'Varias variables',
      fields: {OpField.variables}, keywords: 'jacobiana transformacion', example: 'x*y; x+y^2', hint: 'Componentes separadas por ;'),
  OpSpec('ode', 'Ecuación diferencial', 'Ecuaciones diferenciales',
      fields: {OpField.conditions}, keywords: 'edo dsolve diferencial y prima', example: "y''+y=0", hint: "Use y', y''. Condiciones: y(0)=0; y'(0)=1"),
  OpSpec('laplace', 'Transformada de Laplace', 'Transformadas', keywords: 'laplace s', example: 'exp(3*t)'),
  OpSpec('inverse_laplace', 'Laplace inversa', 'Transformadas', keywords: 'inversa laplace', example: '1/(s^2+1)'),
  OpSpec('stats', 'Estadística descriptiva', 'Estadística',
      keywords: 'media mediana moda varianza desviacion cuartiles datos', example: '2, 4, 4, 4, 5, 5, 7, 9', hint: 'Datos separados por comas'),
  OpSpec('complex', 'Número complejo', 'Complejos', keywords: 'complejo modulo argumento polar fasor i', example: '(2+3*i)*(1-i)'),
  OpSpec('units', 'Convertir unidades', 'Unidades',
      keywords: 'unidades conversion dimensional SI', example: '36 km/h to m/s', hint: 'Cantidad «to» unidad destino'),
];

OpSpec? opSpec(String id) {
  for (final o in opCatalog) {
    if (o.id == id) return o;
  }
  return null;
}

/// Busca herramientas por nombre o palabra clave (sin tildes ni mayusculas).
List<OpSpec> searchOps(String q) {
  String n(String s) => s
      .toLowerCase()
      .replaceAll(RegExp('[áà]'), 'a')
      .replaceAll(RegExp('[éè]'), 'e')
      .replaceAll(RegExp('[íì]'), 'i')
      .replaceAll(RegExp('[óò]'), 'o')
      .replaceAll(RegExp('[úù]'), 'u');
  final t = n(q.trim());
  if (t.isEmpty) return opCatalog;
  return opCatalog.where((o) => n('${o.label} ${o.keywords} ${o.category}').contains(t)).toList();
}

final Map<String, String> calculusOperations = {for (final o in opCatalog) o.id: o.label};

/// ¿El texto parece una instruccion en espanol (y no una expresion)? Entonces se interpreta antes de calcular.
bool looksLikeNaturalLanguage(String text) => RegExp(
        r'^\s*(deriva|derivar|derivada|integra|integrar|integral|resuelve|resolver|calcula|cu[aá]nto|factoriza|simplifica|expande|desarrolla|despeja|l[ií]mite|el l[ií]mite|autovalores|valores propios|convierte|transformada|laplace|serie|taylor|gradiente|ra[ií]z)\b',
        caseSensitive: false)
    .hasMatch(text);

/// Operacion sugerida para una entrada (la interfaz la muestra y el usuario puede cambiarla antes de calcular).
/// No interpreta matematicas: solo mira si hay '=' o letras.
String suggestOperation(String text) {
  final t = text.trim();
  if (t.contains("'")) return 'ode';
  if (RegExp(r'<|>|≤|≥').hasMatch(t)) return 'inequality';
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
  'sympy_eigenvects_verificado': 'Autovectores con SymPy',
  'sympy_diff_parcial': 'Derivación parcial (SymPy)',
  'sympy_gradiente': 'Gradiente (SymPy)',
  'sympy_hessiano': 'Matriz hessiana (SymPy)',
  'sympy_jacobiano': 'Matriz jacobiana (SymPy)',
  'sympy_series_taylor': 'Desarrollo de Taylor (SymPy)',
  'sympy_inecuacion_real': 'Resolución de inecuaciones reales (SymPy)',
  'aritmetica_compleja_sympy': 'Aritmética compleja exacta',
  'sympy_dsolve': 'Resolución simbólica de EDO (SymPy dsolve)',
  'sympy_laplace_transform': 'Transformada de Laplace (SymPy)',
  'sympy_inverse_laplace': 'Transformada inversa de Laplace (SymPy)',
  'estadistica_descriptiva_exacta': 'Estadística con aritmética exacta',
  'conversion_unidades_SI': 'Conversión mediante el Sistema Internacional',
  'analisis_dimensional_SI': 'Análisis dimensional (SI)',
  'biblioteca_de_formulas': 'Fórmula de la biblioteca resuelta para la incógnita',
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
