; ============================================================
;  Podcast AI Studio - Inno Setup installer script
;
;  Build with:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" pyinstaller\installer.iss
;
;  Prerequisite: run pyinstaller\build.bat first so that
;  dist\run_gui_app\ exists and contains run_gui_app.exe.
; ============================================================

#define MyAppName        "Podcast AI Studio"
#define MyAppShortName   "PodcastAIStudio"
#define MyAppVersion     "0.4.2"
#define MyAppPublisher   "Tomomi Research Inc."
#define MyAppExeName     "run_gui_app.exe"
; A stable, unique GUID identifying this application to the
; Windows installer database. Do NOT change this between releases —
; it is what allows new versions to upgrade in place over old ones.
#define MyAppId          "{{8E5D1C30-7B4A-4FB2-9C8E-A1F0B2C3D4E5}"

; Resolve paths relative to this .iss file (pyinstaller/) so the
; script works regardless of the caller's current directory.
#define SourceRoot       SourcePath + "..\dist\run_gui_app"
#define IconFile         SourcePath + "app_icon.ico"
#define OutputBaseDir    SourcePath + "..\installer_output"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://www.tomomi-research.com/
AppSupportURL=https://www.tomomi-research.com/
DefaultDirName={autopf}\{#MyAppShortName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes
OutputDir={#OutputBaseDir}
OutputBaseFilename={#MyAppShortName}-Setup-{#MyAppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ShowLanguageDialog=auto

; Branding
WizardImageStretch=no
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main exe — gets the icon resource so Windows shows it correctly
; even before extraction completes.
Source: "{#SourceRoot}\{#MyAppExeName}"; DestDir: "{app}"; \
    Flags: ignoreversion

; Everything else under the dist folder (the entire _internal/
; tree, plus any sibling files PyInstaller emits next to the exe).
; recursesubdirs picks up subdirectories; createallsubdirs ensures
; empty dirs (if any) are created.
Source: "{#SourceRoot}\*"; DestDir: "{app}"; \
    Excludes: "{#MyAppExeName}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up runtime files written by the GUI (recent projects index,
; user-edited config) on uninstall so the install dir does not get
; left behind.
Type: files; Name: "{app}\config.yaml"
Type: files; Name: "{app}\.recent_projects.json"
Type: filesandordirs; Name: "{app}\output"
