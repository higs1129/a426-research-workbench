"""HTML with in-memory semantic SVG from the scientific-plotting renderer.

The share package carries a hashed, frozen renderer dependency under
plotting-runtime; its maintained source stays in scientific-plotting.
"""
import html
import importlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
from .io import clean


def renderer():
    toolkit=Path(__file__).resolve().parents[1]
    root=toolkit.parent/'plotting-runtime'
    if not (root/'scripts/render_semantic_svg.py').is_file():
        raise FileNotFoundError('Bundled renderer missing; install the complete sin-photonics Skill directory')
    sys.path.insert(0,str(root/'scripts'))
    module=importlib.import_module('render_semantic_svg')
    if not Path(module.__file__).resolve().is_relative_to(root.resolve()):
        raise RuntimeError('A different renderer is already imported; run through this Skill entry point')
    return module


def chart(figure_id,title,xlabel,ylabel,series,provenance,xunit='',yunit='',yscale='linear'):
    pts=np.array([p for s in series for p in s['points']],float)
    if not np.isfinite(pts).all():raise ValueError('Nonfinite chart data')
    def limits(a,log=False):
        if log:
            a=np.log10(a)
        lo,hi=a.min(),a.max();pad=max((hi-lo)*.12,.02 if log else max(abs(lo)*.05,.02))
        return [10**(lo-pad),10**(hi+pad)] if log else [lo-pad,hi+pad]
    model=dict(figureId=figure_id,profile='185mm-double',heightMm=130,purpose='daily',
        sourceOrigin='authoritative-data',coordinateConfidence='exact',title=title,
        x=dict(domain=limits(pts[:,0]),scale='linear',title=xlabel,unit=xunit),
        y=dict(domain=limits(pts[:,1],yscale=='log'),scale=yscale,title=ylabel,unit=yunit),
        series=series,annotations=[],legend=False,provenance=provenance,
        presentation=dict(tickPt=16,axisLabelPt=16,legendPt=16,markerDiameterMm=1.4))
    root=renderer().render(clean(model),{'margins':{'left':30,'right':12,'top':15,'bottom':27},'markerDiameter':1.4})
    # Put the legend in HTML to reserve the complete plot for physical data.
    for child in list(root):
        if child.get('data-role')=='legend':root.remove(child)
    legend='<p>'+ ' · '.join(html.escape(s['label']) for s in series)+'</p>'
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    return ET.tostring(root,encoding='unicode')+legend


def structure(cfg,kind):
    cs=cfg.get('cross_section',{});h=cs.get('thickness_nm',300);wall=cs.get('wall_deg',86)
    # Diagram is explicitly schematic, not calibrated physical coordinates.
    if kind=='ring-bus':
        plan=f'<circle cx="125" cy="100" r="65" fill="none" stroke="#0866a6" stroke-width="7"/><path d="M215 20V180" stroke="#bc3f37" stroke-width="7"/><text x="25" y="200">R = {cfg["ring_radius_um"]:g} µm; ring / straight bus</text>'
    else:
        arcs=sum(s['kind']=='arc' for s in cfg['segments'])
        plan=f'<path d="M20 160H65Q105 160 105 120V70Q105 30 145 30H220" fill="none" stroke="#0866a6" stroke-width="7"/><text x="20" y="200">{arcs} circular arcs; coherent forward modes</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 225" role="img" aria-label="structure schematic"><g font-family="Calibri, Microsoft YaHei, sans-serif" font-size="15" fill="black">{plan}<rect x="300" y="30" width="350" height="135" fill="#e3edf4"/><path d="M395 105L405 80H545L555 105Z" fill="#719a49"/><text x="310" y="55">Upper SiO₂ {cs.get("upper_oxide_um",3):g} µm</text><text x="310" y="145">Lower SiO₂ {cs.get("lower_oxide_um",4):g} µm</text><text x="310" y="188">SiN {h:g} nm; wall {wall:g}°</text><text x="310" y="211">{cs.get("size_reference","bottom")} width / gap; schematic, not to scale</text></g></svg>'


def table(rows):
    keys=list(dict.fromkeys(k for r in rows for k in r if k!='window'))
    return '<details><summary>数值与诊断表</summary><table><tr>'+''.join(f'<th>{html.escape(k)}</th>' for k in keys)+'</tr>'+''.join('<tr>'+''.join(f'<td>{html.escape(str(clean(r.get(k))))}</td>' for k in keys)+'</tr>' for r in rows)+'</table></details>'


def page(path,title,content,payload):
    encoded=json.dumps(clean(payload),ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
    text=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font:18px Calibri,"Microsoft YaHei",sans-serif;max-width:1060px;margin:32px auto;padding:0 24px;color:#111}}svg{{display:block;max-width:100%;height:auto;margin:18px 0}}section{{margin:36px 0}}table{{border-collapse:collapse;font-size:13px}}td,th{{border:1px solid #bbb;padding:5px}}details{{overflow:auto}}.notice{{border-left:4px solid #bd5c2c;padding:12px;background:#fff7ec}}a{{color:#0866a6}}</style>
<h1>{html.escape(title)}</h1>{content}<script type="application/json" id="authoritative-data">{encoded}</script></html>'''
    Path(path).write_text(text,encoding='utf-8')
    check_html(path)


def check_html(path):
    import re
    from html.parser import HTMLParser
    text=Path(path).read_text(encoding='utf-8');ids=[];count=0
    class SvgMarkupAudit(HTMLParser):
        depth=0
        def handle_starttag(self,tag,attrs):
            if ':' in tag and (self.depth or tag.split(':')[-1]=='svg'):
                raise ValueError('Prefixed SVG tags are not native SVG elements in text/html')
            if tag=='svg':self.depth+=1
        def handle_endtag(self,tag):
            if tag=='svg':self.depth-=1
    SvgMarkupAudit().feed(text)
    for svg in re.findall(r'<(?:\w+:)?svg\b.*?</(?:\w+:)?svg>',text,re.S):
        root=ET.fromstring(svg)
        if root.get('data-role')!='scientific-figure':continue
        count+=1
        roles={el.get('data-role') for el in root.iter()}
        metadata=next(el for el in root.iter() if el.get('data-role')=='figure-model')
        model=json.loads(metadata.text)
        required=('figure-model','structures','dimensions','annotations') if model.get('kind')=='schematic' else ('figure-model','data-series','axes','ticks-x','ticks-y','axis-title-x','axis-title-y')
        for role in required:
            if role not in roles:raise ValueError(f'Missing SVG role: {role}')
        for el in root.iter():
            if el.get('id'):ids.append(el.get('id'))
            if any(k.lower().startswith('on') for k in el.attrib):raise ValueError('SVG event handler')
        if model.get('kind')=='schematic':
            if not model.get('not_to_scale') or not model.get('parameters') or not model.get('source'):raise ValueError('Unspecified schematic provenance')
        else:renderer().validate_finite(model)
        if 'Calibri' not in svg or 'Microsoft YaHei' not in svg:raise ValueError('Fallback fonts missing')
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate SVG ids')
    if not count:raise ValueError('No semantic figure')
    return count


def simulation_report(out,result):
    cfg=result['configuration'];rows=result['results'];kind=result['command'];series=[]
    if kind=='ring-bus':
        figure='';facets=sorted({(r.get('ring_radius_um',cfg.get('ring_radius_um')),r.get('wavelength_nm',cfg.get('wavelength_nm'))) for r in rows})
        for fi,(radius,wl) in enumerate(facets):
            selected=[r for r in rows if r.get('ring_radius_um',radius)==radius and r.get('wavelength_nm',wl)==wl]
            groups=sorted({(r.get('ring_width_bottom_um',cfg.get('ring_width_um')),r.get('bus_width_bottom_um',cfg.get('bus_width_um'))) for r in selected})
            series=[]
            for wi,(rw,bw) in enumerate(groups):
                group=[r for r in selected if r.get('ring_width_bottom_um',rw)==rw and r.get('bus_width_bottom_um',bw)==bw]
                qkeys=sorted({k for r in group for k in r if k.startswith('Qc_')})
                for key in qkeys:
                    for good in [True,False]:
                        points=[[r['gap_bottom_um'],r[key]/1e6] for r in group if r.get(key) is not None and np.isfinite(r[key]) and r['qualified']==good]
                        if points:series.append(dict(id=f'w{wi}-{key}-{good}',kind='point-line' if good else 'scatter',
                            label=f'wr{rw:g}/wb{bw:g} {key}'+('' if good else ' diagnostic'),points=points))
            figure+=f'<h2>R={radius:g} µm · λ={wl:g} nm</h2>'
            if series:
                figure+=chart(f'coupling-{fi}','Retained coupling estimate','Bottom gap','Qc',series,'complex_coupling.npz; native-mode-map.json','µm','million','log')
            else:
                series=[dict(id='status',kind='scatter',label='No finite Qc: inspect diagnostics',points=[[i+1,0] for i in range(len(selected))])]
                figure+=chart(f'coupling-{fi}','Unavailable or zero-coupling cases','Case ordinal','Finite Qc available',series,'result.json')
        first=result.get('cases',[{}])[0];cfg={**cfg,**{k:first[k] for k in ['ring_radius_um','ring_width_um','bus_width_um'] if k in first}}
        figure+='<p>每点保留 window_status、实际积分半范围及逐次比较；完整诊断见 <a href="result.json">result.json</a>，原生参数/解对应见 <a href="native-mode-map.json">native-mode-map.json</a>。缺失通道不会填成零或替换为 TE0。</p>'
        csvname='coupling.csv'
    else:
        for label in result['channels']:
            series.append(dict(id=label,kind='point-line',label=label+' input',points=[[r['wavelength_nm'],r['total_retained_power']*100] for r in rows if r['input']==label]))
        figure=chart('route','Coherent retained-mode background','Wavelength','Retained power',series,'route_complex.npz; configuration.json','nm','%')
        csvname='route.csv'
    note='<div class="notice">这是独立模场与有限前向模式模型。数值筛选不等于全波或实验验证；诊断失败结果不可作为可信设计值。</div>'
    limits='<ul>'+''.join('<li>'+html.escape(t)+'</li>' for t in result['limitations'])+'</ul>'
    page(out/'report.html','SiN '+kind,structure(cfg,kind)+note+figure+limits+f'<p><a href="{csvname}">CSV</a></p>'+table(rows),result)
