#ifndef ReleaseVersion
  #define ReleaseVersion "0.3.0-preview.2"
#endif
#define SourceRoot ".."
#ifndef ArtifactsFolder
  #define ArtifactsFolder "..\release"
#endif
#ifndef FileVersion
  #define FileVersion "0.3.0.2"
#endif
#ifndef InstallNotes
  #define InstallNotes "..\docs\INSTALL-NOTES.txt"
#endif

[Setup]
#ifdef DirectSetupHost
UseSetupLdr=no
#endif
AppId={{A0A57009-2B4F-490E-AB44-80C02964E3DD}
AppName=Enco Lite
AppVersion={#ReleaseVersion}
AppVerName=Enco Lite {#ReleaseVersion}
AppPublisher=Enco Lite contributors
DefaultDirName={localappdata}\Programs\Enco Lite
DefaultGroupName=Enco Lite
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern dynamic
WizardSizePercent=110
LicenseFile={#SourceRoot}\LICENSE
InfoBeforeFile={#InstallNotes}
SetupIconFile={#SourceRoot}\ui\assets\app-icon.ico
AppMutex=Local\EncoLite.Desktop
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
Uninstallable=no
Compression=lzma2
SolidCompression=yes
OutputDir={#ArtifactsFolder}
OutputBaseFilename=EncoLite-{#ReleaseVersion}-win-x64-setup
VersionInfoVersion={#FileVersion}
VersionInfoDescription=Enco Lite Installer
VersionInfoProductName=Enco Lite
VersionInfoProductVersion={#FileVersion}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#ArtifactsFolder}\EncoLite-{#ReleaseVersion}-win-x64.msi"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Run]
#ifdef NativeDesktopRuntime
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\desktop_entry.py"""; Description: "{cm:LaunchProgram,Enco Lite}"; Flags: nowait postinstall skipifsilent
#else
#ifdef CompatRuntime
Filename: "{app}\runtime\pythonw.exe"; Parameters: """{app}\run.py"""; Description: "{cm:LaunchProgram,Enco Lite}"; Flags: nowait postinstall skipifsilent
#else
Filename: "{app}\EncoLite.exe"; Description: "{cm:LaunchProgram,Enco Lite}"; Flags: nowait postinstall skipifsilent
#endif
#endif

[Code]
var
  MsiExitCode: Integer;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Params, LogPath: String;
  DesktopValue: String;
begin
  if CurStep = ssPostInstall then
  begin
    DesktopValue := '0';
    if WizardIsTaskSelected('desktopicon') then DesktopValue := '1';
    LogPath := ExpandConstant('{tmp}\EncoLite-msi.log');
    Params := '/i "' + ExpandConstant('{tmp}\EncoLite-{#ReleaseVersion}-win-x64.msi') +
      '" /qn /norestart INSTALLDIR="' + ExpandConstant('{app}') +
      '" CREATE_DESKTOP_SHORTCUT=' + DesktopValue + ' REINSTALLMODE=amus /L*v "' + LogPath + '"';
    if not Exec(ExpandConstant('{sys}\msiexec.exe'), Params, '', SW_HIDE,
      ewWaitUntilTerminated, MsiExitCode) then
    begin
      MsiExitCode := 1603;
      RaiseException('Unable to start Windows Installer.');
    end;
    if (MsiExitCode <> 0) and (MsiExitCode <> 3010) then
      RaiseException('Windows Installer failed (' + IntToStr(MsiExitCode) + '). Log: ' + LogPath);
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := MsiExitCode;
  if Result = 3010 then Result := 0;
end;
