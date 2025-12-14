; Inno Setup Script for TranslateBookWithLLM
; Creates a professional Windows installer

#define MyAppName "TranslateBookWithLLM"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TranslateBookWithLLM"
#define MyAppURL "https://github.com/brunobracaioli/TranslateBookWithLLM"
#define MyAppExeName "TranslateBookWithLLM.exe"

[Setup]
; App identity
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Installation paths
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output settings
OutputDir=installer_output
OutputBaseFilename=TranslateBookWithLLM-Setup-{#MyAppVersion}
SetupIconFile=src\web\static\favicon.ico
Compression=lzma2/ultra64
SolidCompression=yes

; Windows version requirements
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; UI settings
WizardStyle=modern
WizardSizePercent=100

; Privileges (per-user installation doesn't require admin)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; License and info
LicenseFile=LICENSE
InfoBeforeFile=README.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main executable from PyInstaller
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Configuration example
Source: ".env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: ".env.example"; DestName: ".env"; DestDir: "{app}"; Flags: onlyifdoesntexist

; Documentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

; Optional documentation files
Source: "SIMPLE_MODE_README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "TRANSLATION_SIGNATURE.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "DOCKER.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Start menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "Translate books using LLM"
Name: "{group}\Configuration (.env)"; Filename: "{app}\.env"
Name: "{group}\Documentation"; Filename: "{app}\README.md"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop icon (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "Translate books using LLM"

; Quick launch (legacy)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Option to run after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up generated files
Type: filesandordirs; Name: "{app}\translated_files"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\.env"

[Messages]
; Custom messages
WelcomeLabel2=This will install [name/ver] on your computer.%n%nTranslateBookWithLLM is a powerful translation tool that uses local or cloud LLMs to translate books, subtitles, and text files.%n%nIMPORTANT: You need Ollama installed for local translation, or API keys for cloud providers (Gemini, OpenAI, OpenRouter).
FinishedLabel=Setup has finished installing [name] on your computer.%n%nThe web interface will be available at http://localhost:5000 when you run the application.%n%nConfigure your LLM provider by editing the .env file in the installation folder.

[Code]
// Custom code for checking prerequisites
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Could add checks for Ollama installation here in the future
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvFile: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Create output directory
    ForceDirectories(ExpandConstant('{app}\translated_files'));
  end;
end;
