"""Execute distributed code with audit guards against historical/installed-Skill reads."""
import argparse
from pathlib import Path
import sys
import json
import numpy as np

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
      '--library',str(package/'modes'),'--output',str(Path(a.output)/'coupling')])
main(['bends','--config',str(package/'toolkit/examples/route-r40-reference.json'),
      '--library',str(package/'modes'),'--output',str(Path(a.output)/'route')])
route=json.loads((Path(a.output)/'route/result.json').read_text(encoding='utf-8'))
center=[r['total_retained_power'] for r in route['results'] if r['wavelength_nm']==1550]
np.testing.assert_allclose(center,[.8755899911763,.0275325830381],atol=2e-10)
print(json.dumps(dict(portable=True,version=sinphotonics.__version__,route_1550=center)))
