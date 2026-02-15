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
        ('data/migrations/*.sql', 'data/migrations'),
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
    a.binaries,
    a.datas,
    [],
    name='AirDocs',
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
