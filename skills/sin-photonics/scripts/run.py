"""Thin installed Skill launcher; reusable algorithm lives in the toolkit."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--toolkit',default=os.environ.get('SIN_PHOTONICS_HOME'))
    args,remaining=p.parse_known_args()
    if not args.toolkit:p.error('Supply --toolkit or SIN_PHOTONICS_HOME')
    toolkit=Path(args.toolkit).resolve()
    if not (toolkit/'sinphotonics/cli.py').is_file():p.error('Toolkit package not found')
    env=os.environ.copy();env['PYTHONPATH']=str(toolkit)+os.pathsep+env.get('PYTHONPATH','')
    raise SystemExit(subprocess.call([sys.executable,'-m','sinphotonics',*remaining],env=env))


if __name__=='__main__':main()
