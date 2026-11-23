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
    required=['ring_radius_um','ring_width_um','bus_width_um','wavelength_nm','gaps_um'] if command=='ring-bus' else ['width_um','wavelengths_nm','segments']
    missing=set(required)-set(cfg)
    if missing:raise ValueError(f'Missing configuration keys: {sorted(missing)}')
    widths=[cfg[k] for k in ('width_um','ring_width_um','bus_width_um') if k in cfg]
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
    wl=cfg['wavelength_nm'];rad=cfg['ring_radius_um'];rw=cs.bottom_width(cfg['ring_width_um']);bw=cs.bottom_width(cfg['bus_width_um'])
    label=cfg.get('ring_channel','TE0');labels=cfg.get('bus_channels',[label]);mesh=cfg.get('mesh_scale',.7)
    if any(x[:2]!=label[:2] for x in labels):
        raise ValueError('Ring-bus cross-polarization coupling is not qualified by this implementation')
    if library:
        rc=modes.catalog(library/'ring');bc=modes.catalog(library/'bus')
    else:
        rc=modes.catalog(solver.solve(out/'ring',cs,[rw],[wl-2,wl,wl+2],[rad],[label],bin_dir,mesh,cores))
        bc=modes.catalog(solver.solve(out/'bus',cs,[bw],[wl-2,wl,wl+2],[0],labels,bin_dir,mesh,cores))
    rr=modes.select(rc,rw,wl,rad,label,True);br=[modes.select(bc,bw,wl,0,x,True) for x in labels]
    for r in [rr,*br]:check_material(r,cs)
    ring=modes.load(rr,cs);buses=[modes.load(r,cs) for r in br]
    disp=modes.dispersion(rc,rw,wl,rad,label)
    bd={}
    for x in labels:
        try:bd[x]=modes.dispersion(bc,bw,wl,0,x)
        except ValueError as error:
            if 'No retained' not in str(error):raise
            r=br[labels.index(x)]
            bd[x]=dict(neff=r['neff_real'],imag_neff=r['neff_imag'],ng=None,
                       warning='No derivative anchors in this historical bus scan; solve to obtain ng')
    rows=[];arrays={}
    for i,gap in enumerate(cfg['gaps_um']):
        row,a=coupling.calculate(ring,buses,cs.bottom_gap(gap),disp['ng'],**cfg.get('integration',{}))
        rows.append(row)
        arrays.update({f'gap{i}_{k}':v for k,v in a.items()})
    # Gram is a diagnostic of the retained bus basis, not silently orthogonalized CMT.
    fields=np.array([b.field for b in buses]);gram=modes.overlap(fields,fields,buses[0].weights)
    gram_error=float(np.max(abs(gram-np.eye(len(buses)))))
    if gram_error>.02:
        for r in rows:
            r['qualified']=False;r['status']='diagnostic_only';r['reasons'].append('bus_basis_nonorthogonality_above_2_percent')
    arrays['bus_gram']=gram
    np.savez_compressed(out/'complex_coupling.npz',**arrays)
    write_csv(out/'coupling.csv',[{**r,'reasons':';'.join(r['reasons'])} for r in rows])
    result=dict(version=__version__,command='ring-bus',configuration=cfg,ring_dispersion=disp,bus_dispersion=bd,
                bus_gram_identity_error=gram_error,results=rows,
                limitations=['isolated modes + forward Hermitian star CMT; not joint full-wave coupling',
                  'Qc_total only includes retained channels; not loaded Q',
                  'two integration domains are a model diagnostic, not an exact nonorthogonal identity',
                  'diagonal_phase is fixed-field self phase, not mode reshaping',
                  'zero coupling gives infinite Q, represented as null in JSON',
                  'material absorption zero; geometry leakage Q is not measured intrinsic Q'])
    return result


def bends(cfg,cs,out,library,bin_dir,cores):
    width=cs.bottom_width(cfg['width_um']);labels=cfg.get('channels',['TE0','TM0'])
    targets=np.array(sorted(cfg['wavelengths_nm']));anchors=sorted(cfg.get('anchor_wavelengths_nm',cfg['wavelengths_nm']))
    if targets.min()<min(anchors) or targets.max()>max(anchors):raise ValueError('Route wavelengths outside anchors')
    radii=sorted({float(s['radius_um']) for s in cfg['segments'] if s['kind']=='arc'})
    if library:
        st=modes.catalog(library/'straight');bd=modes.catalog(library/'bend')
    else:
        st=modes.catalog(solver.solve(out/'straight',cs,[width],anchors,[0],labels,bin_dir,cfg.get('mesh_scale',.7),cores))
        bd=modes.catalog(solver.solve(out/'bend',cs,[width],anchors,radii,labels,bin_dir,cfg.get('mesh_scale',.7),cores)) if radii else []
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
        p=sub.add_parser(name);p.add_argument('--config',required=True);p.add_argument('--output',required=True)
        p.add_argument('--library',help='Verified portable mode library; omit to solve in COMSOL')
        p.add_argument('--comsol-bin');p.add_argument('--cores',type=int,default=3)
    args=parser.parse_args(argv)
    try:
        cfg,cs=read_config(args.config,args.command)
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
