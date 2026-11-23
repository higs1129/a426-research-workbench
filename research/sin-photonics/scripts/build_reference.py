"""Build a small, portable, ignored reference package from explicit read-only sources."""
import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sinphotonics import modes
from sinphotonics.geometry import CrossSection,rounded_route
from sinphotonics.io import new_output,write_json,sha256


def build(library,out,plotting_root,native,templates,skill_source=None):
    out=new_output(out);sources=[]
    def copy(source,dest):
        dest=out/dest;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
        sources.append(dict(path=dest.relative_to(out).as_posix(),source=str(source.relative_to(library)) if source.is_relative_to(library) else str(source.name),
                            sha256=sha256(dest),bytes=dest.stat().st_size))
    coupling=library/'research/sin-ring-bus-coupling'
    bend=library/'research/chip2-simulation-backup/2026-10-07/bend-filter'
    selected=set()
    # Keep the original arrays untouched; restrict cases rather than thin fields.
    for run,widths,labels in [('run-03',[1.2,2.],['TE0','TE1']),('run-08',[1.2],['TM0'])]:
        rows=modes.catalog(coupling/'raw_data'/run)
        for group,radius in [('ring',57.932442975),('bus',0.)]:
            for width in widths:
                for label in labels:
                    if group=='ring' and label=='TE1':continue
                    if width==1.2 and label=='TE1':continue
                    for wl in [1548,1550,1552]:
                        try:r=modes.select(rows,width,wl,radius,label)
                        except ValueError:
                            # Historical bus width scans have no derivative anchors.
                            if group=='bus' and width==1.2 and label=='TE0' and wl!=1550:
                                r=modes.select(modes.catalog(coupling/'raw_data/run-08'),width,wl,radius,label)
                            elif group=='bus' and wl!=1550:continue
                            else:raise
                        key=(group,r['source'])
                        if key in selected:continue
                        selected.add(key);p=Path(r['source'])
                        copy(p,f'modes/{group}/{run}_{p.name}')
    for group,prefix in [('straight','straight_spectrum'),('bend','bend_spectrum_r40')]:
        for p in sorted((bend/'raw_data/run-01').glob(prefix+'_s*_p*.npz')):
            copy(p,f'modes/{group}/{p.name}')
    for group in ['ring','bus']:
        for p in (native/group/'models').glob('*.mph'):
            copy(p,f'models/{group}-solved.mph')
        copy(native/group/'manifest.json',f'evidence/native-{group}-manifest.json')
    # Compact templates exported from the newly verified one-wavelength run;
    # do not copy the 100 MiB historical mesh/sweep backups.
    for name in ['bend','straight']:
        copy(templates/f'models/{name}-cleared-template.mph',f'models/{name}-cleared-template.mph')
    copy(templates/'manifest.json','evidence/template-manifest.json')
    for name in ['coupling_scan.csv','ring_modes.csv','bus_channel_status.csv']:
        copy(coupling/'processed_data/run-03'/name,f'evidence/{name}')
    for name in ['tm_qc_gap.csv','integration_checks.csv','modes_1550_summary.csv']:
        copy(coupling/'processed_data/run-08'/name,f'evidence/{name}')
    copy(coupling/'processed_data/run-05/qc_phase_comparison.csv','evidence/qc_phase_comparison.csv')
    for name in ['spectrum_r40_summary.json','spectrum_r40_1nm_summary.csv','layout_geometry_reference.json']:
        copy(bend/'processed_data/run-01'/name,f'evidence/{name}')
    for src,dest in [
        ('outputs/流片/2026-10-nine-chip-array/chip_02/accepted/parameters.json','chip2-accepted-run04.json'),
        ('outputs/流片/2026-10-nine-chip-array/chip_02/accepted/provenance.json','chip2-provenance.json'),
        ('summaries/weekly/2026-11-09_to_2026-11-20/assets/nov20/array-mu0.csv','array-mu0.csv'),
        ('summaries/weekly/2026-11-09_to_2026-11-20/assets/q-branch-review/review-evidence.json','branch-review.json'),
        ('research/chip2-simulation-backup/2026-10-07/README.md','cleared-models-source.md')]:copy(library/src,f'evidence/{dest}')
    code=Path(__file__).resolve().parents[1]
    for p in code.rglob('*'):
        if p.is_file() and not any(part in ('__pycache__','.pytest_cache') or part.endswith('.egg-info') for part in p.relative_to(code).parts):
            copy(p,'toolkit/'+p.relative_to(code).as_posix())
    for f in ['scripts/render_semantic_svg.py','scripts/bundle_editable_figure.py','assets/style-profiles.json']:
        copy(plotting_root/f,'plotting-runtime/'+f)
    if skill_source:
        for f in skill_source.rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts and 'tests' not in f.relative_to(skill_source).parts:
                copy(f,'skill/'+f.relative_to(skill_source).as_posix())
    mf=[{k:r[k] for k in ['path','sha256']} for r in sources if r['path'].startswith('modes/')]
    for r in mf:r['path']=r['path'].removeprefix('modes/')
    write_json(out/'modes/library.json',dict(cross_section=asdict(CrossSection()),files=mf))
    write_json(out/'sources.json',dict(source_root_hint='original library (not required at runtime)',files=sources,
        model_status={'ring-solved.mph':'COMSOL 6.1; new 1548/1550/1552 TE0 solutions; readback verified',
        'bus-solved.mph':'COMSOL 6.1; new 1548/1550/1552 TE0 solutions; readback verified',
        'bend-cleared-template.mph':'R40 TE0/TM0 native settings; solutions and generated mesh cleared; readback verified',
        'straight-cleared-template.mph':'straight TE0/TM0 native settings; solutions and generated mesh cleared; readback verified'}))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-library',required=True);p.add_argument('--output',required=True)
    p.add_argument('--plotting-root',required=True);p.add_argument('--native-reference',required=True)
    p.add_argument('--templates',required=True);p.add_argument('--skill-source');a=p.parse_args()
    print(build(Path(a.source_library).resolve(),a.output,Path(a.plotting_root).resolve(),Path(a.native_reference).resolve(),
                Path(a.templates).resolve(),Path(a.skill_source).resolve() if a.skill_source else None))
