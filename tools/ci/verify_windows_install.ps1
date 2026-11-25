# Verificacion REAL de la instalacion en Windows (GitHub Actions, windows-latest):
#  1. instala MATH_UNIVERSE_SETUP.exe en modo silencioso, por usuario, como lo haria una persona;
#  2. comprueba los accesos directos y que el Python del sistema NO se usa;
#  3. bloquea con el Firewall de Windows todo el trafico de salida de la app y de su Python embebido, y comprueba
#     que el bloqueo funciona (una descarga desde el Python instalado debe fallar);
#  4. abre la app instalada en modo autoprueba (--autotest=informe.json): calculos reales en el motor local, SymPy,
#     mpmath e historial SQLite (escribir, cerrar, reabrir, leer);
#  5. abre la app normalmente y comprueba que sigue en marcha (no se cierra al arrancar);
#  6. desinstala.
# Limite honesto: es un Windows Server de GitHub, no un PC de escritorio fisico.
param([string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path)
$ErrorActionPreference = "Stop"
$dist = Join-Path $Root "dist"
$setup = Join-Path $dist "MATH_UNIVERSE_SETUP.exe"
if (-not (Test-Path $setup)) { throw "Falta $setup" }
$inst = Join-Path $env:RUNNER_TEMP "MATH_UNIVERSE_instalado"
$report = Join-Path $dist "AUTOPRUEBA_WINDOWS.json"

# 1) instalacion silenciosa
$p = Start-Process -FilePath $setup -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/DIR=`"$inst`"", "/TASKS=desktopicon") -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "El instalador termino con codigo $($p.ExitCode)" }
$exe = Join-Path $inst "math_universe_app.exe"
foreach ($f in @($exe, (Join-Path $inst "engine_runtime\python\pythonw.exe"), (Join-Path $inst "engine_runtime\engine\run_server.py"), (Join-Path $inst "vcruntime140.dll"))) {
  if (-not (Test-Path $f)) { throw "Instalacion incompleta: falta $f" }
}
$lnk = @(Get-ChildItem -Path ([Environment]::GetFolderPath("Programs")), ([Environment]::GetFolderPath("Desktop")) -Filter "MATH UNIVERSE.lnk" -Recurse -ErrorAction SilentlyContinue)
Write-Host "Accesos directos: $($lnk.FullName -join '; ')"
if ($lnk.Count -lt 2) { throw "No se crearon los accesos directos (menu Inicio y escritorio)" }

# 2) el Python del sistema no debe intervenir: se ocultan las variables que podrian redirigirlo
$env:PYTHONPATH = "C:\no_existe"; $env:PYTHONHOME = "C:\no_existe"

# 3) sin red para la app y su Python
$py = Join-Path $inst "engine_runtime\python\python.exe"
$pyw = Join-Path $inst "engine_runtime\python\pythonw.exe"
foreach ($prog in @($exe, $py, $pyw)) {
  New-NetFirewallRule -DisplayName ("MU_sin_red_" + (Split-Path $prog -Leaf)) -Direction Outbound -Program $prog -Action Block -Profile Any | Out-Null
}
& $py -I -c "import urllib.request,sys`ntry:`n urllib.request.urlopen('https://pypi.org', timeout=8); print('HAY RED'); sys.exit(1)`nexcept Exception as e:`n print('sin red (esperado):', type(e).__name__); sys.exit(0)"
if ($LASTEXITCODE -ne 0) { throw "El bloqueo de red no funciona: la prueba sin conexion no seria valida" }

# 4) autoprueba de la app instalada
if (Test-Path $report) { Remove-Item $report }
$app = Start-Process -FilePath $exe -ArgumentList "--autotest=`"$report`"" -PassThru
$null = $app.Handle   # necesario para que PowerShell conserve el codigo de salida
if (-not $app.WaitForExit(600000)) { $app.Kill(); throw "La autoprueba no termino en 10 minutos" }
if (-not (Test-Path $report)) { throw "La app no genero el informe de autoprueba (codigo $($app.ExitCode))" }
$rep = Get-Content $report -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($c in $rep.comprobaciones) { Write-Host ("{0} {1} :: {2}" -f ($(if ($c.ok) { "OK   " } else { "FALLA" })), $c.nombre, $c.detalle) }
Write-Host ("Autoprueba Windows: {0}/{1} correctas en {2} ms; dependencias: {3}" -f $rep.aprobadas, $rep.total, $rep.duracion_ms, ($rep.dependencias_motor | ConvertTo-Json -Compress))
if (-not $rep.todo_correcto -or $app.ExitCode -ne 0) { throw "La autoprueba de la app instalada fallo ($($rep.fallidas) fallos)" }

# 5) arranque normal (con interfaz): debe seguir abierta y con el motor iniciado
$gui = Start-Process -FilePath $exe -PassThru
$null = $gui.Handle
Start-Sleep -Seconds 20
if ($gui.HasExited) { throw "La app se cerro sola al arrancar (codigo $($gui.ExitCode))" }
$children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($gui.Id)" | Where-Object { $_.Name -like "python*" }
Write-Host "Procesos del motor bajo la app: $($children.Name -join ', ')"
if (-not $children) { throw "La app abrio pero no inicio su motor Python local" }
Stop-Process -Id $gui.Id -Force
Start-Sleep -Seconds 2
Get-Process -Name python, pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$inst*" } | Stop-Process -Force

# 6) desinstalacion
Get-NetFirewallRule -DisplayName "MU_sin_red_*" | Remove-NetFirewallRule
$unins = Get-ChildItem $inst -Filter "unins*.exe" | Select-Object -First 1
$u = Start-Process -FilePath $unins.FullName -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
Write-Host "Desinstalacion: codigo $($u.ExitCode)"
Write-Host "Instalacion de Windows verificada sin red."
