#!/usr/bin/env python3
"""Fetch a pinned vasm source checkout and build it; never committed or bundled."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build import VASM_REVISION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wsl',action='store_true',help='Build in Ubuntu-24.04 WSL on Windows')
    args = parser.parse_args()
    path = ROOT/'.tools'/'vasm'
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        subprocess.run(['git','init',str(path)],check=True)
        subprocess.run(['git','-C',str(path),'remote','add','origin','https://github.com/StarWolf3000/vasm-mirror.git'],check=True)
        subprocess.run(['git','-C',str(path),'fetch','--depth','1','origin',VASM_REVISION],check=True)
        subprocess.run(['git','-C',str(path),'checkout','--detach',VASM_REVISION],check=True)
    actual = subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
    if actual != VASM_REVISION:
        parser.error(f'Existing {path} is at {actual}, expected {VASM_REVISION}; leave it intact and install vasm separately')
    if args.wsl:
        linux_path = subprocess.check_output(['wsl','-d','Ubuntu-24.04','--exec','wslpath','-a',path.as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu-24.04','--exec','make','-C',linux_path,'CPU=m68k','SYNTAX=mot','-j4'],check=True)
        print(f'python build.py --wsl --vasm {linux_path}/vasmm68k_mot')
    elif os.name != 'nt':
        subprocess.run(['make','-C',str(path),'CPU=m68k','SYNTAX=mot','-j4'],check=True)
        print(f'python3 build.py --vasm {path}/vasmm68k_mot')
    else:
        parser.error('Use --wsl on Windows, or provide a native vasmm68k_mot to build.py')


if __name__ == '__main__':
    main()
