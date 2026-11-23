import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sinphotonics.io import new_output,write_json,sha256
from sinphotonics.solver import locate_bin,run_java


if __name__=='__main__':
    p=argparse.ArgumentParser(description='Read-only native source → new compact clear-solution templates')
    p.add_argument('--bend-model',required=True);p.add_argument('--straight-model',required=True)
    p.add_argument('--output',required=True);p.add_argument('--comsol-bin');a=p.parse_args()
    out=new_output(a.output);models=out/'models';models.mkdir()
    sources={k:Path(v).resolve() for k,v in [('bend',a.bend_model),('straight',a.straight_model)]}
    before={k:sha256(v) for k,v in sources.items()}
    run_java(Path(__file__).resolve().parents[1]/'sinphotonics/native/ExportTemplates.java',out,
             dict(**sources,output=models),locate_bin(a.comsol_bin))
    assert before=={k:sha256(v) for k,v in sources.items()},'Source model changed'
    write_json(out/'manifest.json',dict(status='clear-solution and clear-generated-mesh; geometry/material/mesh settings/studies retained',
        sources={k:dict(name=v.name,sha256=before[k]) for k,v in sources.items()},
        files=[dict(path=str(f.relative_to(out)),sha256=sha256(f),bytes=f.stat().st_size) for f in models.glob('*.mph')]))
