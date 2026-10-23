[Setup]
AppId={{2E49F8D4-9A85-4E36-A23D-38F20EB5E184}
AppName=OpenLP Custom
AppVersion=3.1.99
AppPublisher=OpenLP Custom
DefaultDirName={localappdata}\Programs\OpenLP Custom
DefaultGroupName=OpenLP Custom
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\outputs
OutputBaseFilename=OpenLP-Custom-Windows-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\OpenLP Custom.exe
DisableProgramGroupPage=yes
LicenseFile=windows-verify\OpenLP Custom Windows\source\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "windows-verify\OpenLP Custom Windows\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OpenLP Custom"; Filename: "{app}\OpenLP Custom.exe"
Name: "{autodesktop}\OpenLP Custom"; Filename: "{app}\OpenLP Custom.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OpenLP Custom.exe"; Description: "Open OpenLP Custom"; Flags: nowait postinstall skipifsilent
