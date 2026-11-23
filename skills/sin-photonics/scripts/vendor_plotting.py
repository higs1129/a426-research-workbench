"""Freeze the renderer from one committed source revision; never hand-edit its copy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent/'plotting-runtime'
FILES=['scripts/render_semantic_svg.py','scripts/bundle_editable_figure.py','assets/style-profiles.json']


def check():
    manifest=json.loads((ROOT/'provenance.json').read_text(encoding='utf-8'))
    if {r['path'] for r in manifest['files']}!=set(FILES):raise ValueError('Incomplete bundled plotting manifest')
    for item in manifest['files']:
        path=ROOT/item['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Bundled plotting file changed: '+item['path'])
    return manifest


def update(repository,revision):
    repository=Path(repository).resolve()
    commit=subprocess.check_output(['git','-C',str(repository),'rev-parse',revision+'^{commit}'],text=True).strip()
    data={name:subprocess.check_output(['git','-C',str(repository),'show',f'{commit}:skills/scientific-plotting/{name}']) for name in FILES}
    manifest=dict(source='a426-research-workbench/skills/scientific-plotting',source_commit=commit,
        maintenance='Generated dependency snapshot; update from committed source with scripts/vendor_plotting.py. Do not edit these files.',
        files=[dict(path=name,sha256=hashlib.sha256(content).hexdigest()) for name,content in data.items()])
    for name,content in data.items():
        target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    (ROOT/'provenance.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return check()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repository');parser.add_argument('--revision',default='HEAD');args=parser.parse_args()
    result=update(args.repository,args.revision) if args.repository else check()
    print(json.dumps(dict(status='verified',source_commit=result['source_commit'],files=len(result['files']))))
