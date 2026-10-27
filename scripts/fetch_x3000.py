#!/usr/bin/env python3
"""
Fetches Apple's TeraScale 2 drivers from macOS High Sierra 10.13.6, the last release that shipped them, without a Mac
or Apple's software update servers.

OpenCore Legacy Patcher root-patches these drivers onto newer macOS, and keeps the original binaries in its
PatcherSupportPkg repository on GitHub. This does a sparse, blob-filtered clone of only the files listed below.

Usage:
    python scripts/fetch_x3000.py [-o ../TerascaleRed-RE/10.13.6]

Needs git. Apple's binaries are Apple's copyright: the default output is outside this repository, keep it there.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = 'https://github.com/dortania/PatcherSupportPkg.git'
BASE = 'Universal-Binaries/10.13.6/System/Library/Extensions'
PATHS = [
    'AMDRadeonX3000.kext',                # accelerator: CAIL, PM4, Evergreen/NI hardware classes
    'AMDRadeonX3000GLDriver.bundle',      # OpenGL driver and ATIRadeonX3000SCLib.dylib, the shader compiler
    'AMD5000Controller.kext',             # DCE 4 display (Evergreen)
    'AMD6000Controller.kext',             # DCE 5 display (Northern Islands)
    'AMDSupport.kext',                    # shared AMD display support
    'AMDFramebuffer.kext',
    'AMDRadeonVADriver.bundle',
]


def run(*cmd, cwd=None):
    print('+', ' '.join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main():
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('-o', '--out', default=str(root.parent / 'TerascaleRed-RE' / '10.13.6'))
    args = ap.parse_args()
    out = Path(args.out).resolve()
    if root in out.parents or out == root:
        sys.exit('refusing to put Apple binaries inside the repository')
    work = out.parent / '.psp-clone'
    if not work.exists():
        run('git', 'clone', '--depth', '1', '--filter=blob:none', '--no-checkout', '--sparse', REPO, str(work))
    run('git', 'sparse-checkout', 'set', '--no-cone', *[f'{BASE}/{p}/' for p in PATHS], cwd=work)
    run('git', 'checkout', cwd=work)
    out.mkdir(parents=True, exist_ok=True)
    found = 0
    for p in PATHS:
        src = work / BASE / p
        if not src.exists():
            print(f'  not in PatcherSupportPkg: {p}')
            continue
        dst = out / p
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        found += 1
    print(f'{found}/{len(PATHS)} bundles in {out}')
    sclib = out / 'AMDRadeonX3000GLDriver.bundle/Contents/MacOS/ATIRadeonX3000SCLib.dylib'
    if sclib.exists():
        print(f'next: python scripts/sclib_hooks.py "{sclib}"')


if __name__ == '__main__':
    main()
