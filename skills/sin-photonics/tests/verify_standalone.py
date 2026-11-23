"""Exercise the actual Skill entry point from an isolated Git clone/interpreter.

No default data/output paths: callers choose permitted local test locations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


BOOTSTRAP='''import atexit,json,os,runpy,sys
from pathlib import Path
cfg=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
entry=Path(cfg["entry"]).resolve();skill=entry.parents[1]
forbidden=[Path(p).resolve() for p in cfg["forbid"]]
def audit(event,args):
    if event=="open" and isinstance(args[0],(str,bytes,os.PathLike)):
        path=Path(os.fsdecode(args[0])).resolve()
        if any(path.is_relative_to(root) for root in forbidden):
            raise RuntimeError("Forbidden dependency outside installed Skill: "+str(path))
sys.addaudithook(audit)
sys.dont_write_bytecode=True
sys.path.insert(0,str(entry.parent))
def record():
    modules={name:str(Path(module.__file__).resolve()) for name,module in list(sys.modules.items())
        if getattr(module,"__file__",None) and (name.startswith("sinphotonics") or name in ["render_semantic_svg","bundle_editable_figure","vendor_plotting"])}
    Path(cfg["audit"]).write_text(json.dumps(dict(modules=modules,all_inside_skill=all(Path(p).is_relative_to(skill) for p in modules.values())),indent=2),encoding="utf-8")
atexit.register(record)
sys.argv=[str(entry),*cfg["args"]]
runpy.run_path(str(entry),run_name="__main__")
'''


def verify(skill,out,reference,comsol,forbid):
    skill=skill.resolve();out=out.resolve()
    if out.exists():raise FileExistsError('Choose a new output directory: '+str(out))
    out.mkdir(parents=True);bootstrap=out/'audit_entry.py';bootstrap.write_text(BOOTSTRAP,encoding='utf-8')
    commands=[]
    def run(label,args,expect=0):
        config=out/(label+'-invocation.json');audit=out/(label+'-imports.json')
        config.write_text(json.dumps(dict(entry=str(skill/'scripts/run.py'),forbid=[str(p.resolve()) for p in forbid],
            args=list(map(str,args)),audit=str(audit)),ensure_ascii=False),encoding='utf-8')
        env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
            SIN_PHOTONICS_HOME='deliberately-unavailable-toolkit',SIN_PLOTTING_ROOT='deliberately-unavailable-renderer',
            PYTHONPATH='deliberately-unavailable-pythonpath')
        print('VERIFY '+label,flush=True)
        completed=subprocess.run([sys.executable,'-I',str(bootstrap),str(config)],cwd=out,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/(label+'.log')).write_text(completed.stdout+'\n'+completed.stderr,encoding='utf-8')
        if completed.returncode!=expect:raise AssertionError(f'{label}: {completed.returncode}\n{completed.stderr}\n{completed.stdout}')
        inspected=json.loads(audit.read_text(encoding='utf-8'))
        assert inspected['all_inside_skill'],inspected
        commands.append(dict(label=label,args=list(map(str,args)),returncode=completed.returncode,loaded_modules=len(inspected['modules'])))
        return completed.stdout
    assert run('version',['--version']).strip()=='2.0.0'
    doctor=json.loads(run('doctor',['doctor',*(['--comsol-bin',comsol,'--require-comsol'] if comsol else [])]))
    assert doctor['status']=='ready'
    plan=json.loads(run('plan',['ring-bus','--config',skill/'examples/ring-scan-small.json','--plan']))['scan_plan']
    assert plan['native_mode_cases']==18 and plan['coupling_cases']==16
    guide=out/'model-and-equations.html'
    run('guide',['guide','--output',guide])
    content=guide.read_text(encoding='utf-8')
    assert len(re.findall(r'<svg\b',content))==4 and not re.search(r'</?\w+:svg',content)
    assert 'reference300-v1' in content and '2.701536873' in content
    summary=dict(version='2.0.0',python=sys.version.split()[0],dependencies=doctor['dependencies'],
        isolated_interpreter=True,hostile_external_environment_ignored=True,guide_native_svg_count=4,
        git_clone_root=str(skill),forbidden_dependencies=[str(p.resolve()) for p in forbid])
    if reference:
        run('reference-coupling',['ring-bus','--config',skill/'examples/ring-two-channels.json',
            '--library',reference/'modes','--output',out/'coupling'])
        result=json.loads((out/'coupling/result.json').read_text(encoding='utf-8'))['results'][0]
        assert result['qualified'] and result['window_status']=='converged',result['reasons']
        run('reference-route',['bends','--config',skill/'examples/route-r40-reference.json',
            '--library',reference/'modes','--output',out/'route'])
        rows=json.loads((out/'route/result.json').read_text(encoding='utf-8'))['results']
        center=[r['total_retained_power'] for r in rows if r['wavelength_nm']==1550]
        assert len(center)==2 and max(abs(a-b) for a,b in zip(center,[.8755899911763,.0275325830381]))<2e-10
        summary.update(reference_coupling_qualified=True,route_1550_retained_power=center)
    if comsol:
        cfg=json.loads((skill/'examples/ring-reference.json').read_text(encoding='utf-8'))
        cfg.update(gaps_um=[1.2],mode_search=dict(eigenmodes=2))
        config=out/'native-config.json';config.write_text(json.dumps(cfg,indent=2),encoding='utf-8')
        run('native-solve',['ring-bus','--config',config,'--output',out/'native','--comsol-bin',comsol])
        result=json.loads((out/'native/result.json').read_text(encoding='utf-8'))
        row=result['results'][0]
        assert row['qualified'] and row['window_status']=='converged',row['reasons']
        assert abs(row['Qc_total']/3456625-1)<.002
        native_models=list((out/'native').glob('*/models/*.mph'))
        assert len(native_models)==2 and len(result['mode_map'])==6
        summary['native']=dict(Qc_total=row['Qc_total'],qualified=True,native_models=2,selected_modes=6,
            model_hashes=[dict(path=str(p.relative_to(out)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in native_models])
    summary['commands']=commands
    (out/'standalone-validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reference',type=Path)
    parser.add_argument('--comsol-bin');parser.add_argument('--forbid',type=Path,action='append',default=[])
    args=parser.parse_args()
    verify(args.skill,args.output,args.reference.resolve() if args.reference else None,args.comsol_bin,args.forbid)
