"""Real-field v1.1 regression, using explicit frozen/native local inputs."""
import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'research/sin-photonics'))
from sinphotonics import modes,coupling
from sinphotonics.geometry import CrossSection
from sinphotonics.io import write_json,sha256
from sinphotonics.cli import main


def verify(reference,native,out):
    out.mkdir(parents=True,exist_ok=True);cs=CrossSection()
    def load(folder,width,rad,label='TE0'):
        rows=modes.catalog(folder)
        return modes.load(modes.select(rows,width,1550,rad,label,True),cs),rows
    ring,rc=load(reference/'modes/ring',1.2,57.932443)
    bus,_=load(reference/'modes/bus',1.2,0)
    ng=modes.dispersion(rc,1.2,1550,57.932443,'TE0')['ng']
    fixed=[]
    for extent in [15,30,40]:
        w=coupling.evaluate_window(ring,[bus],1.2,extent_um=extent)
        fixed.append(dict(extent_um=extent,Qc=coupling.quality_factors(w['powers'],ng,57.932443,1550)[0]))
    converged=[]
    for integration in [dict(extent_um=15),dict(extent_um=30),{}]:
        value,_=coupling.calculate(ring,[bus],1.2,ng,**integration)
        assert value['qualified'] and value['window']['converged'],value['reasons']
        converged.append(value)
    assert max(r['Qc_total'] for r in converged)/min(r['Qc_total'] for r in converged)-1<1e-5
    assert abs(converged[0]['Qc_total']/fixed[2]['Qc']-1)<1e-5
    limited,_=coupling.calculate(ring,[bus],1.2,ng,extent_um=8,window=dict(max_extent_um=15))
    assert not limited['qualified'] and limited['window_status']=='unconverged_at_limit'
    small,sr=load(reference/'modes/bend',1.2,40)
    smallng=modes.dispersion(sr,1.2,1550,40,'TE0',step_nm=10)['ng']
    small_result,_=coupling.calculate(small,[bus],1.2,smallng)
    assert len(small_result['window']['comparisons'])>=2
    assert small_result['window_status']=='sampling_domain_truncated' and not small_result['qualified']
    assert small_result['window']['sampling_support'][0]['ring']['boundary_field_ratio']>1e-4
    small_again,_=coupling.calculate(small,[bus],1.2,smallng,extent_um=10)
    assert small_again['window_status']=='sampling_domain_truncated'
    assert abs(small_result['Qc_total']/small_again['Qc_total']-1)<1e-4
    # The legacy diagonal benchmark used a fixed 30 µm window. Preserve that
    # regression separately from the new convergence acceptance criterion.
    wide,wrc=load(reference/'modes/ring',2,57.932443)
    buses=[load(reference/'modes/bus',2,0,label)[0] for label in ['TE0','TE1']]
    wideng=modes.dispersion(wrc,2,1550,57.932443,'TE0')['ng']
    phase=coupling.evaluate_window(wide,buses,.8,extent_um=30,step_um=.03,diagonal_phase=True)
    qt,qj=coupling.quality_factors(phase['powers'],wideng,57.932443,1550)
    qvals=dict(total=qt,TE0=qj[0],TE1=qj[1]);phase_errors=[]
    for e in csv.DictReader((reference/'evidence/qc_phase_comparison.csv').open(encoding='utf-8-sig')):
        if float(e['ring_um'])==2 and float(e['bus_um'])==2 and float(e['gap_um'])==.8:
            delta=qvals[e['channel']]/float(e['Qc_both_phases'])-1
            assert abs(delta)<1e-8;phase_errors.append(delta)
    assert len(phase_errors)==3
    # Give the solved native family a checked library index for final-code replay.
    files=[p for family in ['ring','bus'] for p in (native/family/'raw').glob('*.npz')]
    files += [native/family/name for family in ['ring','bus'] for name in ['manifest.json','native-map.csv']]
    write_json(native/'library.json',dict(cross_section=asdict(cs),files=[dict(path=p.relative_to(native).as_posix(),sha256=sha256(p)) for p in files]))
    config=native/'configuration.json'
    main(['ring-bus','--config',str(config),'--library',str(native),'--output',str(out/'native-replay')])
    scan=json.loads((out/'native-replay/result.json').read_text(encoding='utf-8'))
    assert len(scan['results'])==16 and len(scan['mode_map'])==18
    assert len({(r['case_id'],r['gap_input_um']) for r in scan['results']})==16
    assert all(r['qualified'] for r in scan['results'])
    for case in scan['cases']:
        assert len(case['ring_dispersion']['anchor_mode_ids'])==3
        assert len(case['bus_dispersion']['TE0']['anchor_mode_ids'])==3
    # Missing TE1 at a narrow width is a per-case outcome, not TE0 substitution.
    mixed=dict(ring_width_um=1.2,ring_radius_um=57.932443,wavelength_nm=1550,
        scan=dict(bus_widths_um=[1.2,2]),gaps_um=[1.2],bus_channels=['TE0','TE1'])
    write_json(out/'mixed-config.json',mixed)
    main(['ring-bus','--config',str(out/'mixed-config.json'),'--library',str(reference/'modes'),'--output',str(out/'mixed-channels')])
    mixed_result=json.loads((out/'mixed-channels/result.json').read_text(encoding='utf-8'))
    narrow,broad=mixed_result['results']
    assert narrow['missing_channels']=='TE1' and narrow['K_TE1'] is None and not narrow['qualified']
    assert broad['missing_channels']=='' and broad['K_TE1'] is not None and broad['qualified']
    # Plan and budget refusal must finish before COMSOL/output creation.
    main(['ring-bus','--config',str(config),'--plan'])
    try:main(['ring-bus','--config',str(config),'--output',str(out/'budget-must-not-exist'),'--max-native-cases','1'])
    except SystemExit as error:assert error.code==2
    else:raise AssertionError('Missing budget refusal')
    assert not (out/'budget-must-not-exist').exists()
    summary=dict(fixed_window_reference=fixed,reference_converged=converged,limited_window=limited,
        small_radius_40=small_result,small_radius_repeat_Q=small_again['Qc_total'],
        fixed_window_diagonal_max_relative_error=max(abs(np.array(phase_errors))),
        native_scan=dict(models=2,native_mode_cases=18,coupling_cases=16,qualified=sum(r['qualified'] for r in scan['results'])),
        missing_channel_cases=mixed_result['results'])
    write_json(out/'validation.json',summary)
    print(json.dumps(dict(validation=str(out/'validation.json'),R40_status=small_result['window_status'],reference_Qc=converged[0]['Qc_total'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    verify(Path(a.reference),Path(a.native),Path(a.output))
