; Inno Setup script for WinFloat. Build with build.ps1 (needs dist\WinFloat from PyInstaller first).

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "WinFloat"
#define MyAppExe "WinFloat.exe"

[Setup]
AppId={{A3F1C2D4-7B6E-4F18-9C3A-5D2E8B1F6A47}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=WinFloat-Setup-{#MyAppVersion}
SetupIconFile=WinFloat.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Installs just for the current user without an admin prompt; the wizard lets the user choose "all users" instead.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Setup/uninstall ask the user to close WinFloat first (same mutex name main.py uses for its single-instance guard).
AppMutex=Local\WinFloat.SingleInstance

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked
Name: "autostart"; Description: "Start WinFloat when I sign in to Windows (runs in the system tray)"; Flags: unchecked

[Files]
Source: "..\dist\WinFloat\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; Same value the app's own "Start with Windows" switch writes (see ontop/autostart.py), so the two stay in sync.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "WinFloat"; \
  ValueData: """{app}\{#MyAppExe}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart
; Startup entry written by the app before it was renamed from OnTop.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "OnTop"; Flags: deletevalue

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurrentUninstallStepChanged(CurrentUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurrentUninstallStep <> usUninstall then
    Exit;
  { The user may have switched autostart on inside the app rather than via this installer. }
  RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'WinFloat');
  DataDir := ExpandConstant('{userappdata}\WinFloat');
  if (not UninstallSilent) and DirExists(DataDir) then
    if MsgBox('Also delete your WinFloat settings and logs?' + #13#10 + DataDir, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(DataDir, True, True, True);
end;
