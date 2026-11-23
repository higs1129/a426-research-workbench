"""Representative regression against portable frozen evidence, no historical imports."""
import argparse
import csv
import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/toolkit'))
from sinphotonics import modes,coupling,routes
from sinphotonics.geometry import CrossSection
from sinphotonics.io import write_json


def verify(ref,results):
    cs=CrossSection();rc=modes.catalog(ref/'modes/ring');bc=modes.catalog(ref/'modes/bus')
    r=modes.load(modes.select(rc,2,1550,57.932443,'TE0',True),cs)
    buses=[modes.load(modes.select(bc,2,1550,0,label,True),cs) for label in ['TE0','TE1']]
    ng=modes.dispersion(rc,2,1550,57.932443,'TE0')['ng']
    wide,_=coupling.calculate(r,buses,.8,ng)
    expected=next(r for r in csv.DictReader((ref/'evidence/coupling_scan.csv').open(encoding='utf-8-sig'))
        if float(r['ring_width_um'])==2 and float(r['bus_width_um'])==2 and float(r['gap_um'])==.8)
    for k in ['Qc_TE0','Qc_TE1']:
        assert abs(wide[k]/float(expected[k])-1)<.002,(k,wide[k],expected[k])
    # Historical self-phase numbers used L=30 µm. Keep this fixed-window
    # regression distinct from v1.1 longitudinal convergence acceptance.
    phase_window=coupling.evaluate_window(r,buses,.8,extent_um=30,step_um=.03,nu=48,nv=24,diagonal_phase=True)
    qt,qj=coupling.quality_factors(phase_window['powers'],ng,r.row['radius_um'],1550)
    phase=dict(Qc_total=qt,Qc_TE0=qj[0],Qc_TE1=qj[1])
    phase_errors=[]
    for e in csv.DictReader((ref/'evidence/qc_phase_comparison.csv').open(encoding='utf-8-sig')):
        if float(e['ring_um'])==2 and float(e['bus_um'])==2 and float(e['gap_um'])==.8:
            delta=phase['Qc_'+e['channel']]/float(e['Qc_both_phases'])-1
            phase_errors.append(delta);assert abs(delta)<1e-8
    assert len(phase_errors)==3
    te=json.loads((results/'te-regression-v2/result.json').read_text(encoding='utf-8'))
    expectedrows=list(csv.DictReader((ref/'evidence/coupling_scan.csv').open(encoding='utf-8-sig')))
    deviations=[]
    for r in te['results']:
        e=next(x for x in expectedrows if float(x['ring_width_um'])==1.2 and float(x['bus_width_um'])==1.2 and abs(float(x['gap_um'])-r['gap_bottom_um'])<1e-8)
        err=r['Qc_TE0']/float(e['Qc_TE0'])-1;deviations.append(err)
        assert abs(err)<.001 and r['qualified']
    tm=json.loads((results/'tm-regression/result.json').read_text(encoding='utf-8'))
    assert not tm['results'][0]['qualified'] and tm['results'][0]['overlap_discrepancy_TM0']>.2
    assert 28000<tm['ring_dispersion']['ideal_geometry_Q']<30000
    historical_tm=list(csv.DictReader((ref/'evidence/tm_qc_gap.csv').open(encoding='utf-8-sig')))
    assert len(historical_tm)==33 and all(x['qualified']=='False' for x in historical_tm)
    route=json.loads((results/'route-regression-v2/result.json').read_text(encoding='utf-8'))
    center=[r['total_retained_power'] for r in route['results'] if r['wavelength_nm']==1550]
    np.testing.assert_allclose(center,[.8755899911763,.0275325830381],atol=2e-10)
    # Phase conventions are basis gauges. Arbitrary mode phases must not change powers.
    st=modes.catalog(ref/'modes/straight');bd=modes.catalog(ref/'modes/bend')
    labels=['TE0','TM0'];sets={}
    for rad,sign in [(0.,0),(40.,-1),(40.,1)]:
        sets[rad,sign]=[modes.load(modes.select(st if rad==0 else bd,1.2,1550,rad,l,True),cs,'interface') for l in labels]
    first=routes.propagate(*routes.matrices(sets),route['configuration']['segments'],1550)[0]
    for i,ms in enumerate(sets.values()):
        for j,m in enumerate(ms):m.field*=np.exp(1j*(.3+i+.7*j))
    second=routes.propagate(*routes.matrices(sets),route['configuration']['segments'],1550)[0]
    np.testing.assert_allclose(first,second,atol=1e-12)
    # Truly independent 1555 nm FEM anchor checks the broadband interpolation.
    sets={}
    for rad,sign in [(0.,0),(40.,-1),(40.,1)]:
        sets[rad,sign]=[modes.load(modes.select(st if rad==0 else bd,1.2,1555,rad,l,True),cs,'interface') for l in labels]
    direct=routes.propagate(*routes.matrices(sets),route['configuration']['segments'],1555)[0]
    interp=np.array([r['total_retained_power'] for r in route['results'] if r['wavelength_nm']==1555])
    assert max(abs(direct-interp))<1e-6
    modified=json.loads((results/'modified-structure/result.json').read_text(encoding='utf-8'))
    assert modified['results'][0]['qualified']
    assert abs(modified['results'][0]['gap_bottom_um']-1.1837535884222572)<1e-12
    summary=dict(te_max_relative_regression_error=max(abs(np.array(deviations))),wide_bus_channels=wide,
        diagonal_phase_max_relative_regression_error=max(abs(np.array(phase_errors))),
        tm_diagnostic=tm['results'][0],historical_TM_failed_points=len(historical_tm),
        route_1550_retained_power=center,phase_gauge_invariance_max_error=float(max(abs(first-second))),
        route_1555_interpolation_absolute_error=(interp-direct).tolist(),modified_structure=modified['results'][0])
    write_json(results/'validation.json',summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--results',required=True);a=p.parse_args()
    verify(Path(a.reference),Path(a.results))
