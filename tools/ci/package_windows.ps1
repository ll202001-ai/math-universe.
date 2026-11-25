# Empaqueta MATH UNIVERSE para Windows: app Flutter + Python embebido (SymPy, mpmath, jsonschema) + motor + runtime de
# Visual C++, prueba el motor EMPAQUETADO y crea el instalador MATH_UNIVERSE_SETUP.exe y una version portable.
# Se ejecuta en GitHub Actions (windows-latest). No requiere intervencion del usuario.
param([string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path)
$ErrorActionPreference = "Stop"
$PyVer = "3.12.10"                      # misma version menor que Chaquopy en Android (3.12)
$Pip = @("sympy==1.14.0", "mpmath==1.3.0", "jsonschema")   # ver engine/requirements-lock.txt
$rel = Join-Path $Root "app\build\windows\x64\runner\Release"
if (-not (Test-Path (Join-Path $rel "math_universe_app.exe"))) { throw "No se encontro la app compilada en $rel" }

$rt = Join-Path $rel "engine_runtime"
if (Test-Path $rt) { Remove-Item $rt -Recurse -Force }
New-Item -ItemType Directory -Force (Join-Path $rt "python") | Out-Null

# 1) Python embebido oficial (python.org)
$zip = Join-Path $env:RUNNER_TEMP "python-embed.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $zip
Expand-Archive $zip -DestinationPath (Join-Path $rt "python") -Force
$pth = Get-ChildItem (Join-Path $rt "python") -Filter "python*._pth" | Select-Object -First 1
$zipName = ($pth.BaseName -replace "_pth$","") + ".zip"
[IO.File]::WriteAllText($pth.FullName, "$zipName`r`n.`r`n..\site-packages`r`n")

# 2) Dependencias del motor para ESE Python (solo wheels oficiales; SymPy y mpmath son Python puro)
python -m pip install --quiet --target (Join-Path $rt "site-packages") --platform win_amd64 --python-version 3.12 --only-binary=:all: --implementation cp @Pip
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias del motor para el Python embebido" }
Get-ChildItem (Join-Path $rt "site-packages") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# 3) motor (sin pruebas, auditoria ni herramientas)
$eng = Join-Path $rt "engine"
New-Item -ItemType Directory -Force $eng | Out-Null
foreach ($d in "math_universe_engine","math_universe_linalg","schema") { Copy-Item (Join-Path $Root "engine\$d") (Join-Path $eng $d) -Recurse }
Copy-Item (Join-Path $Root "engine\run_server.py") $eng
Get-ChildItem $eng -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# 4) runtime de Visual C++ junto a la app (despliegue local permitido por Microsoft): la app abre en un Windows limpio
foreach ($dll in "msvcp140.dll","vcruntime140.dll","vcruntime140_1.dll") {
  $src = Join-Path $env:WINDIR "System32\$dll"
  if (-not (Test-Path $src)) { throw "No se encontro $dll en el equipo de compilacion" }
  Copy-Item $src $rel -Force
}

# 5) prueba del motor EMPAQUETADO (Python embebido, aislado, sin nada instalado en el sistema)
$py = Join-Path $rt "python\python.exe"
$deps = & $py -I -c "import sympy, mpmath, jsonschema; print(sympy.__version__, mpmath.__version__, jsonschema.__version__)"
if ($LASTEXITCODE -ne 0) { throw "SymPy/mpmath/jsonschema no se importan en el Python embebido" }
Write-Host "Python embebido: sympy, mpmath, jsonschema = $deps"
$reqs = @(
 '{"operation":"ping","request_id":1}',
 '{"operation":"matrix_det","request_id":2,"structured_input":{"a":[[1,2],[3,4]]}}',
 '{"operation":"matrix_inverse","request_id":3,"structured_input":{"a":[[2,1],[1,1]]}}',
 '{"operation":"simplify","request_id":4,"expression":"(x^3-8)/(x-2)"}',
 '{"operation":"evaluate","request_id":5,"expression":"1e999999999","timeout_ms":2000}',
 '{"operation":"integrate","request_id":6,"expression":"sin(x)^2","timeout_ms":60000}',
 '{"operation":"evaluate","request_id":7,"expression":"pi","precision":40}',
 '{"operation":"eigen","request_id":8,"structured_input":{"a":[[2,1],[1,2]]},"latex":true}',
 '{"operation":"plot","request_id":9,"expression":"1/x","params":{"xmin":-2,"xmax":2,"samples":101}}'
)
$OutputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$out = ($reqs -join "`n") | & $py -I -X utf8 (Join-Path $eng "run_server.py")
if ($LASTEXITCODE -ne 0) { throw "El motor empaquetado termino con error" }
$lines = @($out)
if ($lines.Count -ne $reqs.Count) { throw "Se esperaban $($reqs.Count) respuestas y llegaron $($lines.Count)" }
$r = $lines | ForEach-Object { $_ | ConvertFrom-Json }
if ($r[0].status -ne "success_exact") { throw "ping fallo" }
if ($r[1].exact_result -ne "-2" -or $r[1].verification.status -ne "passed") { throw "determinante fallo" }
if ($r[2].exact_result -ne "[[1, -1], [-1, 2]]") { throw "inversa fallo: $($r[2].exact_result)" }
if ($r[3].api_version -ne "1.2" -or ($r[3].conditions -notcontains "x $([char]0x2260) 2")) { throw "dominio x != 2 perdido: $($lines[3])" }
if ($r[4].status -ne "invalid_input") { throw "H-1: el literal gigante no fue rechazado" }
if ($r[5].method -ne "sympy_respaldo_experimental" -or $r[5].verification.status -ne "passed") { throw "SymPy no funciona en el motor empaquetado: $($lines[5])" }
if ($r[6].approximate_result -ne "3.141592653589793238462643383279502884197") { throw "mpmath no funciona en el motor empaquetado: $($lines[6])" }
if ($r[7].verification.status -ne "passed" -or -not $r[7].latex.result) { throw "autovalores/LaTeX fallan en el motor empaquetado: $($lines[7])" }
if (@($r[8].data.series[0].segments).Count -ne 2) { throw "la grafica de 1/x no corta la asintota: $($lines[8])" }
Write-Host "Motor empaquetado: $($reqs.Count)/$($reqs.Count) respuestas correctas (incluye SymPy, mpmath, autovalores, LaTeX y graficas)"

# 6) instalador (Inno Setup) y version portable
$dist = Join-Path $Root "dist"
New-Item -ItemType Directory -Force $dist | Out-Null
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { choco install innosetup -y --no-progress | Out-Null }
if (-not (Test-Path $iscc)) { throw "No se encontro Inno Setup" }
& $iscc "/O$dist" (Join-Path $Root "installer\MathUniverse.iss")
if ($LASTEXITCODE -ne 0) { throw "Fallo la creacion del instalador" }
if (-not (Test-Path (Join-Path $dist "MATH_UNIVERSE_SETUP.exe"))) { throw "No se genero MATH_UNIVERSE_SETUP.exe" }
Compress-Archive -Path (Join-Path $rel "*") -DestinationPath (Join-Path $dist "MATH_UNIVERSE_portable_windows.zip") -Force
Get-ChildItem $dist | ForEach-Object { "{0}  {1}  ({2:N1} MB)" -f $_.Name, (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), ($_.Length / 1MB) }
