# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置
"""
import os

base = os.path.abspath('.')

a = Analysis(
    [os.path.join(base, 'run.py')],
    pathex=[base],
    binaries=[],
    datas=[
        (os.path.join(base, 'static'), 'static'),
    ],
    hiddenimports=[
        'psutil',
        'win32gui',
        'win32process',
        'win32api',
        'win32con',
        'flask',
        'flask.json',
        'jinja2',
        'markupsafe',
        'activity_parser',
        'config',
        'database',
        'monitor',
        'reporter',
        'daily_editor',
        'oa_filler',
    ],
    hookspath=[],
    hooksconfighooks={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WorkTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # 不显示控制台窗口
    icon=None,            # 可以后续添加icon路径
)
