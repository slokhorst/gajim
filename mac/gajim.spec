# -*- mode: python -*-

block_cipher = None

cwd = os.getcwd()
icon = os.path.join(cwd, "mac", "Gajim.icns")

info_plist = {
    "CFBundleDisplayName": "Gajim",
    "NSHighResolutionCapable": True,
}

a = Analysis(['launch.py'],
             pathex=[cwd],
             binaries=[],
             datas=[('gajim', 'gajim')],
             hiddenimports=['gajim.common.modules.adhoc_commands', 'gajim.common.modules.chatstates', 'gajim.common.modules.discovery', 'gajim.common.modules.iq', 'gajim.common.modules.receipts'],
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
