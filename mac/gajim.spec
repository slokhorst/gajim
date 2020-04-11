# -*- mode: python -*-

block_cipher = None

cwd = os.getcwd()
icon = os.path.join(cwd, "mac", "Gajim.icns")

info_plist = {
    "CFBundleDisplayName": "Gajim",
    "NSHighResolutionCapable": True,
}

hiddenimports = ['nbxmpp', 'pyobjc', 'AppKit']

# https://github.com/pyinstaller/pyinstaller/commit/91481570517707fc70aa70dca9eb986c61eac35d
hiddenimports.append('pkg_resources.py2_warn')

# https://github.com/pyinstaller/pyinstaller/issues/4569
#import subprocess
#subprocess.check_output("sed -i sed 's/metadata.entry_points()\[\'keyring.backends\'\]/(metadata.EntryPoint(name=\'macOS\',value=\'keyring.backends.OS_X\',group=\'keyring.backends\'),)/g' /usr/local/lib/python3.7/site-packages/keyring/backend.py", shell=True)


import sys
print(sys.path)
#sys.path.insert(0, os.path.join(cwd))
#from gajim.common.modules import MODULES
#hiddenimports += ['gajim.common.modules.' + m for m in MODULES]
#sys.path.pop(0)

# import site
# typelib_path = os.path.join(site.getsitepackages()[1], 'gnome', 'lib', 'girepository-1.0')
# binaries = [(os.path.join(typelib_path, tl), 'gi_typelibs') for tl in os.listdir(typelib_path)]

a = Analysis(['launch.py'],
             pathex=[cwd],
             binaries=[],
             datas=[('gajim', 'gajim')],
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
