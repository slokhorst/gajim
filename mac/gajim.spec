# -*- mode: python -*-

block_cipher = None

cwd = os.getcwd()
icon = os.path.join(cwd, "mac", "Gajim.icns")

info_plist = {
    "CFBundleDisplayName": "Gajim",
    "NSHighResolutionCapable": True,
}

hiddenimports = ['nbxmpp', 'pyobjc', 'AppKit', 'importlib', 'importlib.resources']

import sys
print("sys.path:")
print(sys.path)
#sys.path.insert(0, os.path.join(cwd))
#from gajim.common.modules import MODULES
#hiddenimports += ['gajim.common.modules.' + m for m in MODULES]
#sys.path.pop(0)

# https://github.com/pyinstaller/pyinstaller/issues/1966
typelib_path = '/usr/local/lib/girepository-1.0'
typelibs = [(os.path.join(typelib_path, tl), 'gi_typelibs') for tl in os.listdir(typelib_path)]
datas = [('gajim', 'gajim')] + typelibs
print("datas:")
print(datas)

a = Analysis(['launch.py'],
             pathex=[cwd],
             binaries=[],
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='launch',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='launch')
app = BUNDLE(coll,
             name='Gajim.app',
             icon=icon,
             info_plist=info_plist,
             bundle_identifier='org.gajim.gajim')
