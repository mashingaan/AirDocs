# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

# Read version dynamically
version_file = Path('core/version.py')
version_ns = {}
exec(version_file.read_text(encoding='utf-8'), version_ns)
APP_VERSION = version_ns['VERSION']

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('templates', 'templates'),
        ('data/migrations', 'data/migrations'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f'AirDocs_{APP_VERSION}',
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AirDocs',
)
