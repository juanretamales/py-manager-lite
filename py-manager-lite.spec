# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None
project_root = SPECPATH

a = Analysis(
    ['run.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('app', 'app'),
    ],
    hiddenimports=[
        'flet',
        'flet_desktop',
        'sqlalchemy',
        'sqlalchemy.sql.default_comparator',
        'sqlalchemy.dialects.sqlite',
        'app',
        'app.core',
        'app.core.config',
        'app.db',
        'app.db.session',
        'app.models',
        'app.repositories',
        'app.services',
        'app.views',
        'app.components',
    ],
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
    name='py-manager-lite',
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
    name='py-manager-lite',
)
