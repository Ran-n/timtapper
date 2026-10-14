; Inno Setup script for the Windows installer. scripts/build_windows.py compiles it with ISCC, passing every
; #define below as /D<name>=<value>; don't compile it by hand.

#ifndef AppName
  #error AppName is not defined: build with scripts/build_windows.py
#endif

[Setup]
; never change AppId: Windows matches upgrades and the uninstall entry on it
AppId={{C05E84E0-BC94-4C61-91D8-AFDD3726A92E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; per-user by default, so no admin prompt; the dialog still offers an install for every user
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#LicenseFile}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBase}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; an upgrade replaces the bundled Python and app code whole, so no module of the older version is left to import
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\DLLs"
Type: filesandordirs; Name: "{app}\Lib"
Type: filesandordirs; Name: "{app}\site-packages"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
