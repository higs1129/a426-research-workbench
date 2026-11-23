"""Self-contained entry point: paths always resolve inside this Skill."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import runpy
import sys

ROOT=Path(__file__).resolve().parents[1]
TOOLKIT=ROOT/'scripts/toolkit'
MINIMUM={'numpy':(2,0),'scipy':(1,14),'jsonschema':(4,20)}


def dependencies():
    found={};errors=[]
    if sys.version_info<(3,11):errors.append('Python >=3.11 required')
    for name,minimum in MINIMUM.items():
        try:
            version=importlib.metadata.version(name);found[name]=version
            if tuple(map(int,re.findall(r'\d+',version)[:2]))<minimum:
                errors.append(f'{name} >='+'.'.join(map(str,minimum))+' required')
        except importlib.metadata.PackageNotFoundError:errors.append(f'{name} missing')
    return found,errors


def doctor(argv):
    parser=argparse.ArgumentParser(description='Check bundled code, Python dependencies and optional COMSOL')
    parser.add_argument('--comsol-bin');parser.add_argument('--require-comsol',action='store_true')
    args=parser.parse_args(argv);versions,errors=dependencies()
    from vendor_plotting import check
    try:check()
    except (ValueError,FileNotFoundError) as error:errors.append(str(error))
    required=['sinphotonics/native/NativeModes.java','sinphotonics/materials.json','sinphotonics/config.schema.json','docs/model-and-equations.html.in']
    for relative in required:
        if not (TOOLKIT/relative).is_file():errors.append('Bundled resource missing: '+relative)
    comsol=None;comsol_note='not checked while Python dependencies are missing'
    if not errors:
        from sinphotonics.solver import locate_bin
        try:comsol=str(locate_bin(args.comsol_bin));comsol_note='executables found; license is verified by an actual solve'
        except FileNotFoundError as error:
            comsol_note=str(error)
            if args.require_comsol or args.comsol_bin:errors.append(comsol_note)
    print(json.dumps(dict(skill_root=str(ROOT),python=sys.version.split()[0],dependencies=versions,
        bundled_resources_ok=not errors,comsol_bin=comsol,comsol_note=comsol_note,
        errors=errors,status='ready' if not errors else 'action_required'),ensure_ascii=False,indent=2))
    return 2 if errors else 0


def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    argv=list(sys.argv[1:] if argv is None else argv)
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(TOOLKIT))
    if argv and argv[0]=='doctor':return doctor(argv[1:])
    if argv==['--version']:
        from sinphotonics import __version__
        print(__version__);return 0
    _,errors=dependencies()
    if errors:
        print('; '.join(errors)+f'\nInstall with: "{sys.executable}" -m pip install -r "{ROOT / "requirements.txt"}"',file=sys.stderr)
        return 2
    if argv and argv[0]=='guide':
        sys.argv=[str(TOOLKIT/'scripts/build_guide.py'),*argv[1:]]
        runpy.run_path(sys.argv[0],run_name='__main__');return 0
    from sinphotonics.cli import main as cli_main
    cli_main(argv)
    return 0


if __name__=='__main__':raise SystemExit(main())
