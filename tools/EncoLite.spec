# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite\\ui', 'ui'), ('C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite\\encolite\\oppo_models.json', 'encolite'), ('C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite\\LICENSE', '.')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('slint')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite\\main.py'],
    pathex=['C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite\\.build-deps', 'C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'PIL', 'matplotlib', 'pytest', 'unittest', 'psutil'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EncoLite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite\\tools\\windows-version.txt',
    icon=['C:\\Users\\aclan\\Documents\\ChatGPT\\电脑\\EncoLite\\ui\\assets\\app-icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='EncoLite',
)
