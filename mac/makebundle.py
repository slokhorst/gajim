#!/usr/bin/env python3
import os
import shutil
import sys
import argparse
from subprocess import run

if __name__ == '__main__':
    if not os.path.isdir('mac'):
        sys.exit("can't find the 'mac' directory. make sure you run "
                 "this script from the project root")

    parser = argparse.ArgumentParser(description='Create a macOS .app bundle.')
    parser.add_argument('--version', default='0.0.1',
                        help='version number of the .app bundle')
    args = parser.parse_args()

    dmg_name = 'gajim-{}.dmg'.format(args.version)

    run(['pyinstaller', 'mac/gajim.spec'], check=True)
    run(['rm' '-rf', 'dist/launch'])
    run(['hdiutil', 'create', '-volname', 'Gajim', '-srcfolder', 'dist', '-ov', '-format', 'UDZO', dmg_name])
