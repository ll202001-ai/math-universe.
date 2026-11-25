; Instalador de MATH UNIVERSE (Inno Setup 6). Instala por usuario: no necesita permisos de administrador.
; Incluye la app, el motor matematico (Python embebido con SymPy y mpmath) y el runtime de Visual C++: no requiere
; instalar nada mas ni conexion a internet.
[Setup]
AppId={{6D5B6A52-3C0A-4C3B-9E87-4D41A1F0C1A7}
AppName=MATH UNIVERSE
AppVersion=0.6.0
AppVerName=MATH UNIVERSE 0.6.0
VersionInfoVersion=0.6.0
AppPublisher=MATH UNIVERSE
DefaultDirName={autopf}\MATH UNIVERSE
DefaultGroupName=MATH UNIVERSE
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=MATH_UNIVERSE_SETUP
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\math_universe_app.exe
UninstallDisplayName=MATH UNIVERSE

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\app\build\windows\x64\runner\Release\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\MATH UNIVERSE"; Filename: "{app}\math_universe_app.exe"
Name: "{autodesktop}\MATH UNIVERSE"; Filename: "{app}\math_universe_app.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"

[UninstallDelete]
; caches de Python generadas al usar la app
Type: filesandordirs; Name: "{app}\engine_runtime"

[Run]
Filename: "{app}\math_universe_app.exe"; Description: "Abrir MATH UNIVERSE"; Flags: nowait postinstall skipifsilent
