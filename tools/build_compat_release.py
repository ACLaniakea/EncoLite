"""Build an isolated old-runtime candidate; do not promote it to release/."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
from package_compat import package,ROOT,VERSION,SLINT_VERSION
OUTPUT=ROOT/'.tools/compat-release'

if __name__=='__main__':
    bundle=package();OUTPUT.mkdir(parents=True,exist_ok=True)
    source=OUTPUT/f'EncoLite-{VERSION}-source.zip'
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as archive:
        for folder in ('encolite','ui'):
            for path in sorted((bundle/folder).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.write(path,Path('EncoLite')/path.relative_to(bundle))
        for folder in ('tools','tests','docs'):
            for path in sorted((ROOT/folder).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
                    archive.write(path,Path('EncoLite')/path.relative_to(ROOT))
        for name in ('main.py','run.py','README.md','LICENSE','THIRD_PARTY_NOTICES.md'):
            archive.write(bundle/name,Path('EncoLite')/name)
        archive.writestr('EncoLite/requirements.txt',f'slint=={SLINT_VERSION}\n')
    sources=bundle/'Source';sources.mkdir()
    import shutil
    shutil.copy2(source,sources/source.name)
    notes=OUTPUT/'INSTALL-NOTES.txt'
    notes.write_text(f'''Enco Lite {VERSION}

Windows 10 1809+ x64。请先在 Windows 蓝牙设置中配对 OPPO 耳机。
安装包自带官方 Python 运行库，不需要另装 Python。
单击托盘图标打开快捷控制，双击打开主窗口。
关闭窗口后继续驻留托盘，不默认开机自启。
卸载保留 %APPDATA%\\EncoLite 下的个人设置。

此构建为安装验证候选。测试范围和待验证事项见随附文档。
开源许可证、第三方说明和应用源码随安装包提供。
''','utf-8')
    msi=OUTPUT/f'EncoLite-{VERSION}-win-x64.msi'
    subprocess.run([sys.executable,str(ROOT/'tools/build_msi.py'),'--bundle',str(bundle),
        '--output',str(msi),'--version',VERSION,'--msi-version','0.3.3'],check=True)
    subprocess.run([str(ROOT/'.tools/InnoSetup/ISCC.exe'),'/Qp',
        f'/DReleaseVersion={VERSION}',f'/DArtifactsFolder={OUTPUT}',
        '/DFileVersion=0.3.0.3','/DCompatRuntime',f'/DInstallNotes={notes}',str(ROOT/'tools/installer.iss')],check=True)
    entries=[]
    for path in (source,msi,OUTPUT/f'EncoLite-{VERSION}-win-x64-setup.exe'):
        entries.append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUTPUT/'build-manifest.json').write_text(json.dumps({'version':VERSION,'status':'candidate; validation pending','files':entries},indent=2),'utf-8')
    print(json.dumps(entries),flush=True)
