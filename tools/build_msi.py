"""Build a per-user MSI using Windows Installer, with no custom uninstaller EXE."""
from pathlib import Path
import hashlib
import json
import sys
import uuid
import ctypes as C
import warnings
warnings.filterwarnings('ignore',category=DeprecationWarning)
import msilib as m
from msilib import schema, sequence

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.5.0-preview.19'
MSI_VERSION='0.5.19'
APP_NAME='Enco Lite'
UPGRADE='{A0A57009-2B4F-490E-AB44-80C02964E3DD}'
PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
BUNDLE=ROOT/'dist/EncoLite-qt'
OUTPUT=ROOT/'release'/f'EncoLite-{VERSION}-win-x64.msi'

def stable_id(prefix,path):
    return prefix+hashlib.sha256(str(path).encode()).hexdigest()[:24]

def component_guid(path):
    return '{'+str(uuid.uuid5(uuid.UUID(UPGRADE),str(path))).upper()+'}'

def build():
    from prepare_installer_assets import prepare
    prepare(ROOT)
    OUTPUT.parent.mkdir(exist_ok=True)
    db=m.init_database(str(OUTPUT),schema,APP_NAME,PRODUCT,MSI_VERSION,'Enco Lite contributors')
    # MSI uses a Windows codepage; 936 preserves Simplified Chinese shortcut names.
    codepage=ROOT/'build/_ForceCodepage.idt';codepage.parent.mkdir(exist_ok=True)
    codepage.write_bytes(b'\r\n\r\n936\t_ForceCodepage\r\n')
    db.Commit()
    del db
    api=C.WinDLL('msi')
    api.MsiOpenDatabaseW.argtypes=[C.c_wchar_p,C.c_void_p,C.POINTER(C.c_uint32)]
    api.MsiDatabaseImportW.argtypes=[C.c_uint32,C.c_wchar_p,C.c_wchar_p]
    api.MsiDatabaseCommit.argtypes=[C.c_uint32]
    api.MsiCloseHandle.argtypes=[C.c_uint32]
    handle=C.c_uint32()
    assert api.MsiOpenDatabaseW(str(OUTPUT),C.c_void_p(1),C.byref(handle))==0
    try:
        status=api.MsiDatabaseImportW(handle,str(codepage.parent),codepage.name)
        assert status==0,('MSI codepage import',status)
        assert api.MsiDatabaseCommit(handle)==0
    finally:api.MsiCloseHandle(handle)
    db=m.OpenDatabase(str(OUTPUT),m.MSIDBOPEN_TRANSACT)
    view=db.OpenView("UPDATE `Property` SET `Value`='2052' WHERE `Property`='ProductLanguage'")
    view.Execute(None);view.Close()
    summary=db.GetSummaryInformation(20)
    summary.SetProperty(m.PID_CODEPAGE,936)
    summary.SetProperty(m.PID_TEMPLATE,'x64;2052')
    summary.SetProperty(m.PID_PAGECOUNT,500)
    summary.Persist()
    # Use Windows Installer's native wizard; no bootstrap executable.
    execute_sequence=list(sequence.InstallExecuteSequence)
    m.change_sequence(execute_sequence,'LaunchConditions',450)
    m.add_data(db,'InstallExecuteSequence',execute_sequence)
    view=db.OpenView("UPDATE `InstallExecuteSequence` SET `Sequence`=1510 WHERE `Action`='RemoveExistingProducts'")
    view.Execute(None);view.Close()
    m.add_data(db,'Property',[
        ('UpgradeCode',UPGRADE),('ARPNOMODIFY','1'),('ARPSYSTEMCOMPONENT','1'),
        ('ARPPRODUCTICON','AppIcon'),('INSTALLLEVEL','1'),('SecureCustomProperties','OLDPRODUCTS;NEWPRODUCTS;INSTALLDIR;CREATE_DESKTOP_SHORTCUT;LAUNCH_AFTER_INSTALL'),
        ('ProductRelease',VERSION)])
    m.add_data(db,'Upgrade',[
        (UPGRADE,None,MSI_VERSION,None,513,None,'OLDPRODUCTS'),
        (UPGRADE,MSI_VERSION,None,None,258,None,'NEWPRODUCTS')])
    m.add_data(db,'RegLocator',[('OSBuild',2,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion','CurrentBuildNumber',18)])
    m.add_data(db,'AppSearch',[('WINDOWSBUILD','OSBuild')])
    # The stable entry-script component also locates older installations that did not
    # publish ARPINSTALLLOCATION. Keep upgrades and startup links in that folder.
    m.add_data(db,'CompLocator',[('ExistingInstall',component_guid(Path('desktop_entry.py')),1)])
    m.add_data(db,'AppSearch',[('EXISTINGINSTALLDIR','ExistingInstall')])
    m.add_data(db,'CustomAction',[
        ('UseExistingDirectory',51,'INSTALLDIR','[EXISTINGINSTALLDIR]'),
        ('SetInstallLocation',51,'ARPINSTALLLOCATION','[INSTALLDIR]')])
    m.add_data(db,'InstallExecuteSequence',[
        ('UseExistingDirectory','EXISTINGINSTALLDIR',425),
        ('SetInstallLocation',None,1010)])
    m.add_data(db,'CustomAction',[('ReinstallAll',51,'REINSTALL','ALL')])
    m.add_data(db,'InstallExecuteSequence',[('ReinstallAll','Installed AND NOT REMOVE',750)])
    m.add_data(db,'LaunchCondition',[
        ('NOT NEWPRODUCTS','已安装更新版本的 Enco Lite。'),
        ('VersionNT64 AND WINDOWSBUILD >= 17763','Enco Lite 需要 64 位 Windows 10 1809 或更新版本。')])
    cab=m.CAB('EncoLite.cab')
    target=m.Directory(db,cab,None,str(BUNDLE),'TARGETDIR','SourceDir',componentflags=0)
    local=m.Directory(db,cab,target,'','LocalAppDataFolder','.',componentflags=0)
    programs=m.Directory(db,cab,local,'','UserPrograms','Programs',componentflags=0)
    install=m.Directory(db,cab,programs,str(BUNDLE),'INSTALLDIR','ENCOLI~1|'+APP_NAME,componentflags=0)
    m.Feature(db,'Main','Enco Lite','OPPO earphone control',1,directory='INSTALLDIR').set_current()
    dirs={Path('.'):install}
    files={}
    for path in sorted(BUNDLE.rglob('*')):
        relative=path.relative_to(BUNDLE)
        if path.is_dir():
            parent=dirs[relative.parent]
            dirs[relative]=m.Directory(db,cab,parent,path.name,stable_id('D',relative),parent.make_short(path.name)+'|'+path.name,componentflags=0)
        elif path.is_file():
            directory=dirs[relative.parent]
            component=stable_id('C',relative)
            directory.start_component(component,flags=0,keyfile=path.name,uuid=component_guid(relative))
            file_id=directory.add_file(path.name)
            files[relative.as_posix()]=(file_id,component)
    manifest_path=BUNDLE/'runtime-manifest.json'
    runtime_manifest=json.loads(manifest_path.read_text('utf-8')) if manifest_path.exists() else {}
    exe,exe_component=files[runtime_manifest.get('entry_point','EncoLite.exe')]
    launch_arguments=runtime_manifest.get('entry_arguments')
    quick_arguments=((launch_arguments+' ') if launch_arguments else '')+'--quick'
    # The explicit Startup folder also works when MSI runs in service context.
    # Only remove the shortcut when it belongs to this installation.
    if launch_arguments and 'desktop_entry.py' in launch_arguments:
        cleanup=launch_arguments+' --remove-autostart --startup-folder "[StartupFolder]."'
        m.add_data(db,'CustomAction',[('RemoveAutostart',1106,exe,cleanup)])
        m.add_data(db,'InstallExecuteSequence',[
            ('RemoveAutostart','Installed AND REMOVE~="ALL" AND NOT UPGRADINGPRODUCTCODE',3450)])
    m.add_data(db,'Directory',[
        ('ProgramMenuFolder','TARGETDIR','.'),('AppMenu','ProgramMenuFolder','ENCOLI~1|'+APP_NAME),
        ('DesktopFolder','TARGETDIR','.')])
    m.add_data(db,'Icon',[('AppIcon',m.Binary(str(ROOT/'ui/assets/app-icon.ico')))])
    # A registry key is the key path for per-user shortcuts.
    m.add_data(db,'Component',[
        ('MenuComponent',component_guid('shortcuts/menu'),'AppMenu',260,None,'MenuRegistry'),
        ('DesktopComponent',component_guid('shortcuts/desktop'),'DesktopFolder',260,'CREATE_DESKTOP_SHORTCUT="1"','DesktopRegistry')])
    m.add_data(db,'FeatureComponents',[('Main','MenuComponent'),('Main','DesktopComponent')])
    registry_key=r'Software\EncoLite\Installer' if APP_NAME=='Enco Lite' else r'Software\EncoLite\Installer\Validation'+'\\'+UPGRADE
    m.add_data(db,'Registry',[
        ('MenuRegistry',1,registry_key,'Menu', '1','MenuComponent'),
        ('DesktopRegistry',1,registry_key,'Desktop','1','DesktopComponent')])
    # Apps/Control Panel otherwise request basic MSI UI and bypass our pages.
    # Keep one per-user uninstall entry which explicitly selects full UI.
    arp_key=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\EncoLite.'+UPGRADE.strip('{}')
    m.add_data(db,'Component',[
        ('UninstallComponent',component_guid('registry/uninstall'),'INSTALLDIR',260,None,'UninstallName')])
    m.add_data(db,'FeatureComponents',[('Main','UninstallComponent')])
    uninstall_command='"[SystemFolder]msiexec.exe" /x '+PRODUCT+' /qf /norestart'
    arp_values=[('Name','DisplayName',APP_NAME),('Version','DisplayVersion',VERSION),
                ('Publisher','Publisher','Enco Lite contributors'),('Location','InstallLocation','[INSTALLDIR]'),
                ('Icon','DisplayIcon','"[INSTALLDIR]ui\\assets\\app-icon.ico"'),
                ('Command','UninstallString',uninstall_command),
                ('Quiet','QuietUninstallString','"[SystemFolder]msiexec.exe" /x '+PRODUCT+' /qn /norestart'),
                ('NoModify','NoModify','#1'),('NoRepair','NoRepair','#1')]
    m.add_data(db,'Registry',[(('UninstallName' if suffix=='Name' else 'Uninstall'+suffix),1,arp_key,name,value,'UninstallComponent')
                             for suffix,name,value in arp_values])
    m.add_data(db,'Registry',[('UninstallKey',1,arp_key,'*',None,'UninstallComponent')])
    m.add_data(db,'Shortcut',[
        ('MainShortcut','AppMenu','ENCOLI~1|'+APP_NAME,'MenuComponent','[#'+exe+']',launch_arguments,None,None,'AppIcon',0,1,'INSTALLDIR'),
        ('QuickShortcut','AppMenu','QUICKC~1|快捷控制','MenuComponent','[#'+exe+']',quick_arguments,None,None,'AppIcon',0,1,'INSTALLDIR'),
        ('DesktopShortcut','DesktopFolder','ENCOLI~1|Enco Lite','DesktopComponent','[#'+exe+']',launch_arguments,None,None,'AppIcon',0,1,'INSTALLDIR')])
    m.add_data(db,'RemoveFile',[('RemoveAppMenu','MenuComponent',None,'AppMenu',2)])
    from msi_ui import add_wizard
    add_wizard(db,ROOT,runtime_manifest.get('entry_point','EncoLite.exe'),launch_arguments or '')
    cab.commit(db)
    db.Commit()
    manifest={'version':VERSION,'msi_version':MSI_VERSION,'product_code':PRODUCT,'upgrade_code':UPGRADE,'file_count':len(files),
              'arp_key':arp_key,'uninstall_command':uninstall_command}
    (ROOT/'build/msi-manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
    print(json.dumps(manifest),flush=True)
    return OUTPUT

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,default=BUNDLE)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--version',default=VERSION)
    parser.add_argument('--msi-version',default=MSI_VERSION)
    parser.add_argument('--upgrade-code',default=UPGRADE)
    parser.add_argument('--name',default=APP_NAME)
    args=parser.parse_args()
    BUNDLE=args.bundle;VERSION=args.version;MSI_VERSION=args.msi_version;UPGRADE=args.upgrade_code;APP_NAME=args.name
    PRODUCT='{'+str(uuid.uuid5(uuid.UUID(UPGRADE),VERSION)).upper()+'}'
    OUTPUT=args.output or ROOT/'release'/f'EncoLite-{VERSION}-win-x64.msi'
    build()
