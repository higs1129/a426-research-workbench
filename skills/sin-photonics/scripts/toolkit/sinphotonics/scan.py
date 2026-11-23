"""Cartesian ring-bus plans with deduplicated native mode families."""
from itertools import product
from pathlib import Path
import json
import numpy as np
from . import __version__,modes,coupling,solver
from .materials import indices
from .io import write_json,write_csv

AXES={'ring_widths_um':'ring_width_um','bus_widths_um':'bus_width_um',
      'ring_radii_um':'ring_radius_um','wavelengths_nm':'wavelength_nm'}


def plan(cfg,cs):
    axes={plural:sorted(set(cfg.get('scan',{}).get(plural,[cfg.get(single)]))) for plural,single in AXES.items()}
    if any(None in values for values in axes.values()):raise ValueError('Every ring-bus axis needs a scalar or scan array')
    anchors=sorted({round(w+d,9) for w in axes['wavelengths_nm'] for d in [-2,0,2]})
    ring=dict(widths=[cs.bottom_width(w) for w in axes['ring_widths_um']],radii=axes['ring_radii_um'],
              wavelengths=anchors,channels=[cfg.get('ring_channel','TE0')])
    bus=dict(widths=[cs.bottom_width(w) for w in axes['bus_widths_um']],radii=[0],
             wavelengths=anchors,channels=cfg.get('bus_channels',[cfg.get('ring_channel','TE0')]))
    def count(f):return len(f['widths'])*len(f['radii'])*len(f['wavelengths'])*len(f['channels'])
    return dict(kind='cartesian',axes=axes,ring=ring,bus=bus,native_models=2,
        native_mode_cases=count(ring)+count(bus),ring_mode_cases=count(ring),bus_mode_cases=count(bus),
        coupling_cases=int(np.prod([len(v) for v in axes.values()]))*len(cfg['gaps_um']),
        ng_stencil_nm=[-2,0,2],reuse='one native ring family and one bus family; gap never triggers FEM')


def material_check(row,cs):
    nc,no=indices(row['wavelength_nm'],cs.material)
    if abs(row['n_core']-nc)>1e-8 or abs(row['n_oxide']-no)>1e-8:raise ValueError('Mode material mismatch')


def run(cfg,cs,out,library,bin_dir,cores):
    p=plan(cfg,cs);write_json(out/'scan-plan.json',p)
    label=cfg.get('ring_channel','TE0');labels=p['bus']['channels']
    if any(c[:2]!=label[:2] for c in labels):raise ValueError('Cross-polarization ring-bus CMT is not qualified')
    catalogs={};manifests={}
    for family in ['ring','bus']:
        if library:
            folder=library/family
            if (folder/'raw').is_dir():
                manifests[family]=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
                folder=folder/'raw'
        else:
            f=p[family]
            folder=solver.solve(out/family,cs,f['widths'],f['wavelengths'],f['radii'],f['channels'],bin_dir,
                cfg.get('mesh_scale',.7),cores,cfg.get('mode_search'),strict_modes=False)
            manifests[family]=json.loads((out/family/'manifest.json').read_text(encoding='utf-8'))
        catalogs[family]=modes.catalog(folder)
    cache={};disp_cache={};mapping=[];identities={}
    def identify(family,row):
        key=(family,Path(row['source']).name,row['solution'])
        if key not in identities:
            identity=dict(mode_id=f'm{len(mapping):04}',family=family,
                **{k:row[k] for k in ['width_bottom_um','wavelength_nm','radius_um']},
                channel=row['mode'],npz=key[1],npz_solution=row['solution'])
            if family in manifests:
                selected=next(s for s in manifests[family]['selections'] if s.get('source')==key[1] and s.get('solution')==key[2])
                identity['native']=selected['native']
            else:identity['native']=dict(status='legacy archive; native mapping not reconstructed')
            identities[key]=identity;mapping.append(identity)
        return identities[key]['mode_id']
    def get(family,width,wl,rad,channel):
        key=(family,width,wl,rad,channel)
        if key not in cache:
            row=modes.select(catalogs[family],width,wl,rad,channel,True);material_check(row,cs)
            mode=modes.load(row,cs);cache[key]=mode
            identify(family,row)
        return cache[key]
    def dispersion(family,width,wl,rad,channel):
        key=(family,width,wl,rad,channel)
        if key not in disp_cache:
            value=modes.dispersion(catalogs[family],width,wl,rad,channel)
            value['anchor_mode_ids']=[identify(family,modes.select(catalogs[family],width,round(wl+d,9),rad,channel)) for d in [-2,0,2]]
            disp_cache[key]=value
        return disp_cache[key]
    rows=[];arrays={};cases=[]
    axes=p['axes'];combinations=product(axes['ring_widths_um'],axes['bus_widths_um'],axes['ring_radii_um'],axes['wavelengths_nm'])
    for case_index,(rwidth,bwidth,rad,wl) in enumerate(combinations):
        case_id=f'case{case_index:04}';rw=cs.bottom_width(rwidth);bw=cs.bottom_width(bwidth)
        parameters=dict(case_id=case_id,ring_width_um=rwidth,bus_width_um=bwidth,ring_width_bottom_um=rw,
                        bus_width_bottom_um=bw,ring_radius_um=rad,wavelength_nm=wl)
        case=dict(**parameters,requested_channels=labels)
        available=[];missing=[];selection_errors={};ring=None;disp=None
        try:
            ring=get('ring',rw,wl,rad,label);disp=dispersion('ring',rw,wl,rad,label)
        except ValueError as error:selection_errors['ring_'+label]=str(error)
        for channel in labels:
            try:available.append(get('bus',bw,wl,0,channel))
            except ValueError as error:missing.append(channel);selection_errors['bus_'+channel]=str(error)
        case.update(missing_channels=missing,selection_errors=selection_errors,ring_dispersion=disp,
            ring_mode_id=identify('ring',ring.row) if ring else None,
            bus_mode_ids={b.row['mode']:identify('bus',b.row) for b in available})
        bd={}
        for b in available:
            channel=b.row['mode']
            try:bd[channel]=dispersion('bus',bw,wl,0,channel)
            except ValueError as error:
                bd[channel]=dict(neff=b.neff.real,imag_neff=b.neff.imag,ng=None,warning=str(error))
        case['bus_dispersion']=bd
        gram_error=None
        if ring is not None and disp is not None and available:
            fields=np.array([b.field for b in available]);gram=modes.overlap(fields,fields,available[0].weights)
            gram_error=float(np.max(abs(gram-np.eye(len(available)))))
            arrays[case_id+'_bus_gram']=gram
        for gi,gap in enumerate(cfg['gaps_um']):
            base=dict(**parameters,gap_input_um=gap,gap_bottom_um=cs.bottom_gap(gap),requested_channels=','.join(labels),
                      retained_channels=','.join(b.row['mode'] for b in available),missing_channels=','.join(missing),
                      bus_gram_identity_error=gram_error)
            if ring is None or disp is None or not available:
                row=dict(**base,qualified=False,status='mode_unavailable',reasons=list(selection_errors.values()))
            else:
                try:
                    calc,a=coupling.calculate(ring,available,cs.bottom_gap(gap),disp['ng'],**cfg.get('integration',{}))
                    row={**base,**calc}
                    arrays.update({f'{case_id}_gap{gi}_{k}':v for k,v in a.items()})
                    if missing:row['reasons'].append('requested_channels_not_retained:'+','.join(missing))
                    if gram_error>.02:row['reasons'].append('bus_basis_nonorthogonality_above_2_percent')
                    if row['reasons']:row['qualified']=False;row['status']='diagnostic_only'
                except ValueError as error:row=dict(**base,qualified=False,status='calculation_failed',reasons=[str(error)])
            # Stable table schema; absent channels are null, never fake zero coupling.
            for channel in labels:
                for prefix in ['Qc_','K_','overlap_discrepancy_','amplitude_real_','amplitude_imag_','absolute_floor_dominated_']:
                    row.setdefault(prefix+channel,None)
            for key in ['Qc_total','K_total','power_balance','window_status','window_extent_um']:row.setdefault(key,None)
            rows.append(row)
        case['bus_gram_identity_error']=gram_error;cases.append(case)
    np.savez_compressed(out/'complex_coupling.npz',**arrays)
    flat=[{k:(';'.join(v) if k=='reasons' else v) for k,v in r.items() if k!='window'} for r in rows]
    keys=list(dict.fromkeys(k for r in flat for k in r));write_csv(out/'coupling.csv',[{k:r.get(k) for k in keys} for r in flat])
    write_json(out/'native-mode-map.json',dict(modes=mapping,cases=cases))
    result=dict(version=__version__,command='ring-bus',configuration=cfg,scan_plan=p,cases=cases,mode_map=mapping,results=rows,
        limitations=['isolated modes + forward Hermitian star CMT; not joint full-wave coupling',
        'Qc_total includes only the named retained channels; missing requested channels make the case diagnostic',
        'two-domain consistency, longitudinal window convergence and finite sampling-support decay are distinct diagnostics',
        'window convergence does not establish FEM mesh/PML or full-wave model accuracy',
        'diagonal_phase is fixed-field self phase; not mode reshaping',
        'zero coupling gives infinite Q (null in JSON); near-zero channels use explicit absolute tolerances',
        'material absorption zero; geometry leakage Q is not measured intrinsic Q'])
    if len(cases)==1:
        result.update(ring_dispersion=cases[0]['ring_dispersion'],bus_dispersion=cases[0]['bus_dispersion'],
                      bus_gram_identity_error=cases[0]['bus_gram_identity_error'])
    return result
