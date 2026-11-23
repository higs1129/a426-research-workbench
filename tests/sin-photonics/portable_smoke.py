"""Execute distributed code with audit guards against historical/installed-Skill reads."""
import argparse
from pathlib import Path
import sys

p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--output',required=True);a=p.parse_args()
package=Path(a.package).resolve()


def guard(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=str(args[0]).replace('\\','/').lower()
        if '每日实验总结' in path or '/.codex/skills/' in path or '/scripts/run-0' in path:
            raise RuntimeError('Forbidden historical/installed-Skill dependency: '+path)


sys.addaudithook(guard)
sys.path.insert(0,str(package/'toolkit'))
from sinphotonics.cli import main
import sinphotonics
assert Path(sinphotonics.__file__).resolve().is_relative_to(package)
main(['ring-bus','--config',str(package/'toolkit/examples/ring-two-channels.json'),
      '--library',str(package/'modes'),'--output',a.output])
