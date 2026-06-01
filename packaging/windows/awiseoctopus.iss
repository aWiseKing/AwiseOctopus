#define AppName "AwiseOctopus"
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
#ifndef SourceDir
#define SourceDir "..\..\dist\pyinstaller\AwiseOctopus"
#endif
#ifndef OutputDir
#define OutputDir "..\..\dist\artifacts"
#endif

[Setup]
AppId={{AwiseOctopus}}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=AwiseOctopus-{#AppVersion}-windows-x64-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AwiseOctopus"; Filename: "{app}\awiseoctopus.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\AwiseOctopus"; Filename: "{app}\awiseoctopus.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\awiseoctopus.exe"; Description: "Launch AwiseOctopus"; Flags: nowait postinstall skipifsilent
