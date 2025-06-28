# -*- mode: python -*-
from PyInstaller.utils.hooks import collect_all

import sys
import sys
a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates/*', 'templates'),
        ('static/*', 'static'),
        ('settings/*', 'settings'),
        ('functions/*', 'functions'),
        ('chromedriver.exe', '.')
    ] + (['chromedriver', '.'] if sys.platform.startswith('linux') else []),
    hiddenimports=[
        'engineio.async_drivers.threading',
        'nltk',
        'nltk.corpus',
        'nltk.tokenize',
        'nltk.stem',
        'newspaper'
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False
)

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, 
          name='ReportBuilder',
          debug=False,
          console=False,
          icon='icon.ico')