"""Nov20 accepted mu=0 experiment versus accepted-run04 1550 nm design.

No branch assignment or refitting occurs here. All included and excluded rows
are retained; the confirmed used_in_die_mean flag controls statistics.
"""
import argparse
import csv
import html
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sinphotonics.io import new_output,write_json,write_csv,sha256
from sinphotonics.report import chart,structure,table,page


def compare(reference,output):
    out=new_output(output);evidence=reference/'evidence'
    accepted=json.loads((evidence/'chip2-accepted-run04.json').read_text(encoding='utf-8'))
    dies={d['id']:d for d in accepted['dies']}
    allrows=list(csv.DictReader((evidence/'array-mu0.csv').open(encoding='utf-8-sig')))
    data=[];summary=[]
    for r in allrows:
        if r['chip']!='2':continue
        d=dies[r['die']];cavity=int(r['cavity'].lstrip('c')) if r['cavity'] else None
        ring=next((x for u in d['units'] for x in u['rings'] if x['index']==cavity),None)
        if ring is None and len(d['gap_values_nm'])!=1:raise ValueError('Unassigned cavity with ambiguous gap')
        row=dict(r);row.update(gap_nm=ring['gap_nm'] if ring else d['gap_values_nm'][0],radius_um=ring['radius_um'] if ring else None,
            assignment_status='assigned' if ring else 'missing_cavity_same_gap_die_only',
            Qc_design_1550=d['Qc_TE0_reference_estimate'],
            delta_wavelength_nm=float(r['mu0_wavelength_nm'])-1550 if r['mu0_wavelength_nm'] else None,
            Q1_over_design=float(r['Q1'])/d['Qc_TE0_reference_estimate'] if r['Q1'] else None)
        data.append(row)
    for die,d in sorted(dies.items()):
        rows=[r for r in data if r['die']==die];used=[r for r in rows if r['used_in_die_mean'].lower()=='true']
        if not used:continue
        q=np.array([float(r['Q1']) for r in used]);delta=[r['delta_wavelength_nm'] for r in used]
        theory=d['Qc_TE0_reference_estimate']
        summary.append(dict(die=die,gap_nm=d['gap_values_nm'][0],n=len(q),excluded=len(rows)-len(q),
            included_without_cavity=sum(r['assignment_status']!='assigned' for r in used),
            Q1_mean=float(np.mean(q)),Q1_sample_std=float(np.std(q,ddof=1)) if len(q)>1 else None,
            Qc_design_1550=theory,mean_over_design=float(np.mean(q)/theory),
            relative_bias_percent=float((np.mean(q)/theory-1)*100),
            wavelength_offset_min_nm=min(delta),wavelength_offset_max_nm=max(delta)))
    used=[r for r in data if r['used_in_die_mean'].lower()=='true']
    raw=dict(id='accepted-mu0',kind='scatter',label='Measured Q1, included μ=0',
        color='#18699a',points=[[r['gap_nm'],float(r['Q1'])/1e6] for r in used],semantics='measurement-fit')
    curve=sorted({(d['gap_values_nm'][0],d['Qc_TE0_reference_estimate']/1e6) for d in dies.values()})
    theory=dict(id='design',kind='polyline',label='Design Qc at 1550 nm',color='#bd3930',points=curve,semantics='theory-approximation')
    source=dict(input='Nov20 array-mu0.csv; accepted run04 parameters',sha256={p.name:sha256(p) for p in [evidence/'array-mu0.csv',evidence/'chip2-accepted-run04.json']},
                statistics='arithmetic mean; sample standard deviation ddof=1; used_in_die_mean only')
    f1=chart('experiment-distribution','Chip2: every accepted cavity','Design bottom gap','Q1 / Qc',[raw,theory],source,'nm','million','log')
    ratios=dict(id='die-means',kind='scatter',label='Die mean / design',points=[[i+1,r['mean_over_design']] for i,r in enumerate(summary)])
    one=dict(id='unity',kind='polyline',label='Ratio = 1',points=[[.5,1],[len(summary)+.5,1]])
    f2=chart('bias','Die-level bias','Die ordinal (see table)','Mean Q1 / design Qc',[ratios,one],source)
    # Error-bar segments remain independently editable quantitative objects.
    series=[dict(id='means',kind='scatter',label='Mean Q1',points=[[i+1,r['Q1_mean']/1e6] for i,r in enumerate(summary)])]
    for i,r in enumerate(summary):
        sd=r['Q1_sample_std']
        if sd is not None:series.append(dict(id=f'std-{i}',kind='polyline',label=r['die']+' ±1 sample SD',
            points=[[i+1,(r['Q1_mean']-sd)/1e6],[i+1,(r['Q1_mean']+sd)/1e6]],semantics='sample-standard-deviation'))
    f3=chart('die-spread','Die means and spread','Die ordinal (see table)','Q1',series,source,'','million')
    cfg=dict(ring_radius_um=57.932443,cross_section=dict(thickness_nm=300,wall_deg=86,size_reference='bottom'))
    notes='''<div class="notice">实验支持是分布比较，不是模型精确性证明。Q1 沿用已确认分支与腔归属；理论 Qc 没有用于选择欠/过耦合分支。</div>
<p>主参考：Chip2 ring index 7，R=57.932443 µm，环/总线底宽 1.2 µm，设计 FSR≈420.2105457 GHz，阵列半径步进≈9.193684 nm。accepted run04 为当前几何；光学基准为 run02。</p>
<p>实验取 μ=0 的真实波长，理论为 1550 nm 单点；逐点波长差保留在 CSV。若源表标记纳入均值但 cavity 为空，保留原纳入标记，仅按该 die 唯一 gap 做 die 级比较，不推断腔号或半径；归属缺口在表中逐项标明，仍待核对。无唯一 μ=0 的行按源表排除。86° 是设计假设，未视为 SEM 证实。由 FSR 换算的 ng 不构成第二项独立验证。</p>
<p>拟合 Q0 可能包含未观测通道损耗。端到端插损包含光纤、taper、传播、加工和腔，不能单独验证转弯。早期总 IL≈1.494434 dB 使用 1.1 µm taper 近似 1.2 µm，以及 500 µm 行距无腔旧走线；不代表当前 750 µm 行距带腔/金属结构。</p>'''
    links='<p><a href="experiment-all-rows.csv">全部取点（含排除项）</a> · <a href="die-summary.csv">逐 die 均值、样本标准差与偏差</a></p>'
    payload=dict(provenance=source,summary=summary,all_rows=data)
    write_json(out/'comparison.json',payload);write_csv(out/'experiment-all-rows.csv',data);write_csv(out/'die-summary.csv',summary)
    mapping='<p>Die ordinal: '+'; '.join(f'{i+1}={r["die"]}' for i,r in enumerate(summary))+'</p>'
    page(out/'report.html','300 nm SiN：参考结构与最新实验对照',structure(cfg,'ring-bus')+notes+f1+f2+f3+mapping+links+table(summary),payload)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    rows=compare(Path(a.reference),a.output)
    print(json.dumps(rows,ensure_ascii=False))
