import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import numpy as np
import jsonschema
from . import __version__
from .geometry import CrossSection
from .materials import indices
from . import modes,coupling,routes,solver
from .io import new_output,write_json,write_csv,sha256


def read_config(path,command):
    cfg=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    schema=json.loads(Path(__file__).with_name('config.schema.json').read_text())
    jsonschema.validate(cfg,schema)
    cs=CrossSection(**cfg.get('cross_section',{}))
    required=['gaps_um'] if command=='ring-bus' else ['width_um','wavelengths_nm','segments']
    missing=set(required)-set(cfg)
    if missing:raise ValueError(f'Missing configuration keys: {sorted(missing)}')
    widths=[cfg[k] for k in ('width_um','ring_width_um','bus_width_um') if k in cfg]
    if command=='ring-bus':
        from .scan import plan
        axes=plan(cfg,cs)['axes']
        widths+=axes['ring_widths_um']+axes['bus_widths_um']
        integration=cfg.get('integration',{})
        for radius in axes['ring_radii_um']:
            coupling.window_plan(radius,integration,integration.get('window',{}))
    if any(cs.bottom_width(w)-2*cs.h*1e6*cs.cot<=0 for w in widths):
        raise ValueError('Nonpositive top width')
    if any(cs.bottom_gap(g)<=0 for g in cfg.get('gaps_um',[])):
        raise ValueError('Converted bottom gap must be positive')
    return cfg,cs


def check_library(path,cs):
    path=Path(path).resolve()
    manifest=json.loads((path/'library.json').read_text(encoding='utf-8'))
    expected=asdict(cs);actual=manifest['cross_section']
    for key in expected:
        if key=='size_reference':continue  # exported widths always bottom-defined
        if expected[key]!=actual[key]:raise ValueError(f'Mode library cross section differs: {key}')
    for f in manifest['files']:
        p=(path/f['path']).resolve()
        if not p.is_relative_to(path) or sha256(p)!=f['sha256']:
            raise ValueError(f'Mode library integrity mismatch: {f["path"]}')
    return path


def check_material(row,cs):
    nc,no=indices(row['wavelength_nm'],cs.material)
    if abs(row['n_core']-nc)>1e-8 or abs(row['n_oxide']-no)>1e-8:
        raise ValueError('Mode material does not match configured preset')


def ring_bus(cfg,cs,out,library,bin_dir,cores):
    from .scan import run
    return run(cfg,cs,out,library,bin_dir,cores)


def bends(cfg,cs,out,library,bin_dir,cores):
    width=cs.bottom_width(cfg['width_um']);labels=cfg.get('channels',['TE0','TM0'])
    targets=np.array(sorted(cfg['wavelengths_nm']));anchors=sorted(cfg.get('anchor_wavelengths_nm',cfg['wavelengths_nm']))
    if targets.min()<min(anchors) or targets.max()>max(anchors):raise ValueError('Route wavelengths outside anchors')
    radii=sorted({float(s['radius_um']) for s in cfg['segments'] if s['kind']=='arc'})
    if library:
        st=modes.catalog(library/'straight');bd=modes.catalog(library/'bend')
    else:
        st=modes.catalog(solver.solve(out/'straight',cs,[width],anchors,[0],labels,bin_dir,cfg.get('mesh_scale',.7),cores,cfg.get('mode_search')))
        bd=modes.catalog(solver.solve(out/'bend',cs,[width],anchors,radii,labels,bin_dir,cfg.get('mesh_scale',.7),cores,cfg.get('mode_search'))) if radii else []
    keys=[(0.,0)]+[(r,sign) for r in radii for sign in [-1,1]]
    def get_sets(wl):
        sets={}
        for radius,sign in keys:
            rows=[modes.select(st if radius==0 else bd,width,wl,radius,label,True) for label in labels]
            for r in rows:check_material(r,cs)
            sets[radius,sign]=[modes.load(r,cs,'interface') for r in rows]
        return sets
    reference=get_sets(anchors[len(anchors)//2]);all_anchors=[]
    for wl in anchors:
        all_anchors.append(routes.matrices(get_sets(wl),reference))
    if len(anchors)==1:
        outputs=[routes.propagate(*all_anchors[0],cfg['segments'],wl) for wl in targets]
        power=np.array([x[0] for x in outputs]);amp=np.array([x[1] for x in outputs])
    else:
        power,amp=routes.spectrum(anchors,all_anchors,cfg['segments'],targets)
    reasons=[]
    if np.any(power>1.001) or np.any(power<0):reasons.append('nonpassive_retained_projection')
    np.savez_compressed(out/'route_complex.npz',wavelength_nm=targets,total_retained_power=power,
        amplitude=amp,anchor_wavelength_nm=anchors,
        anchor_neff=np.array([[a[0][k] for k in keys] for a in all_anchors]),
        anchor_gram=np.array([[a[2][k] for k in keys] for a in all_anchors]),
        anchor_transition=np.array([[[a[1][b,s] for s in keys] for b in keys] for a in all_anchors]))
    rows=[]
    for i,wl in enumerate(targets):
        for j,label in enumerate(labels):
            row=dict(wavelength_nm=wl,input=label,total_retained_power=power[i,j],
                     IL_dB=-10*np.log10(power[i,j]) if power[i,j]>0 else np.inf,
                     original_channel_power=abs(amp[i,j,j])**2)
            for k,outlabel in enumerate(labels):row[f'coefficient_power_{outlabel}']=abs(amp[i,k,j])**2
            rows.append(row)
    write_csv(out/'route.csv',rows)
    return dict(version=__version__,command='bends',configuration=cfg,channels=labels,results=rows,
        status='diagnostic_only' if reasons else 'retained_mode_approximation',reasons=reasons,
        limitations=['power=a†Ga; coefficient powers need not sum to total in a nonorthogonal basis',
        'forward retained modes only; missing power is not fully resolved radiation',
        'circular arcs and straight segments; no Euler / arbitrary-curvature claim',
        'phase-aligned cubic matrix interpolation, log-loss PCHIP with 1e-16 numerical floor; no extrapolation',
        'coherent broadband background includes dispersion trend; peak-to-peak is not detrended ripple',
        'does not include tapers, cavities, metal, fiber or roughness'])


def main(argv=None):
    parser=argparse.ArgumentParser(description='SiN isolated-mode ring coupling and coherent circular routes')
    parser.add_argument('--version',action='version',version=__version__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ['ring-bus','bends','routes']:
        p=sub.add_parser(name);p.add_argument('--config',required=True);p.add_argument('--output')
        p.add_argument('--library',help='Verified portable mode library; omit to solve in COMSOL')
        p.add_argument('--comsol-bin');p.add_argument('--cores',type=int,default=3)
        if name=='ring-bus':
            p.add_argument('--plan',action='store_true',help='Preview native and coupling case counts without solving')
            p.add_argument('--max-native-cases',type=int,default=32)
            p.add_argument('--max-coupling-cases',type=int,default=128)
    args=parser.parse_args(argv)
    try:
        cfg,cs=read_config(args.config,args.command)
        if args.cores<1:raise ValueError('cores must be positive')
        if args.command=='ring-bus':
            from .scan import plan
            planned=plan(cfg,cs)
            print(json.dumps({'scan_plan':planned},ensure_ascii=False),flush=True)
            if args.plan:return
            if planned['coupling_cases']>args.max_coupling_cases or (not args.library and planned['native_mode_cases']>args.max_native_cases):
                raise ValueError('Scan exceeds explicit case budget; inspect --plan and deliberately set --max-native-cases / --max-coupling-cases')
        if not args.output:raise ValueError('--output is required for execution')
        library=check_library(args.library,cs) if args.library else None
        bin_dir=solver.locate_bin(args.comsol_bin) if library is None else None
        out=new_output(args.output)
        write_json(out/'configuration.json',cfg)
        result=(ring_bus if args.command=='ring-bus' else bends)(cfg,cs,out,library,bin_dir,args.cores)
        write_json(out/'result.json',result)
        from .report import simulation_report
        simulation_report(out,result)
        print(json.dumps(dict(output=str(out),command=args.command,rows=len(result['results'])),ensure_ascii=False))
    except (ValueError,FileNotFoundError,FileExistsError,RuntimeError,jsonschema.ValidationError) as error:
        parser.exit(2,str(error)+'\n')


if __name__=='__main__':main()
