"""Build one offline Chinese model guide, with in-memory semantic SVG only."""
import argparse
import html
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sinphotonics import __version__
from sinphotonics.report import check_html
from sinphotonics.materials import DATA
ET.register_namespace('', 'http://www.w3.org/2000/svg')


def label(x,y,text):
    return f'<text x="{x}" y="{y}">{html.escape(text)}</text>'


def diagram(name,title,structures,dimensions,annotations,source):
    name='diagram-'+name
    model=dict(figureId=name,kind='schematic',not_to_scale=True,
        coordinateSystem='diagram millimetres, not device micrometres',widthMm=185,heightMm=125,
        purpose='daily model explanation',fontPt=12,source=source,
        parameters=dict(thickness_nm=300,wall_deg=86,ring_width_bottom_um=1.2,
            bus_width_bottom_um=1.2,ring_radius_um=57.932443,gap_bottom_um=1.2,
            lower_oxide_um=4,upper_oxide_um=3,material='reference300-v1'))
    header=f'<svg xmlns="http://www.w3.org/2000/svg" width="185mm" height="125mm" viewBox="0 0 185 125" id="{name}" data-role="scientific-figure" role="img" aria-labelledby="{name}-title"><title id="{name}-title">{html.escape(title)}</title><metadata id="{name}-model" data-role="figure-model">{html.escape(json.dumps(model,ensure_ascii=False))}</metadata><style>#{name} text{{font-family:Calibri,"Microsoft YaHei",sans-serif;font-size:4.23px;fill:#111}}#{name} .dim{{fill:none;stroke:#333;stroke-width:.4}}#{name} .guide{{fill:none;stroke:#777;stroke-width:.3;stroke-dasharray:1.5 1.5}}</style>'
    body=''
    for role,content in [('structures',structures),('dimensions',dimensions),('annotations',label(5,8,title)+annotations+label(5,119,'示意比例；尺寸数值以标注及配置为准'))]:
        body+=f'<g id="{name}-{role}" data-role="{role}">{content}</g>'
    root=ET.fromstring(header+body+'</svg>')
    # Targeted label-anchor bounds, XML and semantic checks; no visual claims.
    for el in root.iter():
        if el.tag.endswith('text'):
            assert 0<float(el.get('x'))<185 and 0<float(el.get('y'))<125
    return ET.tostring(root,encoding='unicode')


def build(output):
    plan=diagram('plan','环—直总线：底部边缘 gap',
        '<circle cx="55" cy="63" r="34" fill="none" stroke="#17669a" stroke-width="5"/><path d="M102 23V101" stroke="#b8473d" stroke-width="5"/><circle cx="55" cy="63" r=".8"/>',
        '<path class="dim" d="M55 63H89M89 60V66M91.5 63H99.5M91.5 60V66M99.5 60V66"/><path class="guide" d="M55 63H160"/>',
        label(31,43,'环中心线 R')+label(110,35,'直总线 w_b')+label(110,57,'g_b = 1.2 µm')+label(8,105,'R = 57.932443 µm')+label(110,81,'w_r = w_b')+label(110,88,'= 1.2 µm')+label(110,100,'R_b：圆心→总线中心'),
        'geometry.CrossSection; coupling.kernels rb / rho / phi')
    section=diagram('section','独立截面：层结构、侧壁与开放边界',
        '<rect x="8" y="20" width="169" height="84" fill="#f7e8d2" stroke="#b77c32"/><rect x="14" y="26" width="157" height="72" fill="#e3edf4"/><path d="M14 38H171V26H14Z" fill="#f6f9fc"/><path d="M14 82H171V98H14Z" fill="#bbbbbb"/><path d="M42 67L48 54H88L94 67Z" fill="#719a49" stroke="#36501f"/>',
        '<path class="dim" d="M42 72H94M42 69V75M94 69V75M100 54V67M97 54H103M97 67H103"/><path class="guide" d="M94 67H111"/>',
        label(18,34,'空气')+label(18,47,'上 SiO₂ 3 µm')+label(112,60,'h = 300 nm')+label(112,68,'θ = 86°')+label(43,79,'底宽 w_bottom')+label(112,48,'θ 相对水平面')+label(18,91,'局部硅衬底')+label(112,77,'下 SiO₂ 4 µm')+label(112,23,'外圈 PML')+label(18,110,'直：Cartesian；弯：axisymmetric，ρ=R+u'),
        'NativeModes.java geometry/material/PML; coupling.quad')
    kernel=diagram('kernel','两种积分域与局部矢量旋转',
        '<path d="M23 99Q91 67 61 22" fill="none" stroke="#17669a" stroke-width="4"/><path d="M104 22V100" stroke="#b8473d" stroke-width="4"/><circle cx="67" cy="63" r="2.2" fill="#17669a"/><circle cx="104" cy="63" r="2.2" fill="#b8473d"/>',
        '<path class="guide" d="M23 63H155M23 96L67 63M67 63H104"/><path class="dim" d="M112 95V31L110 35M112 31L114 35M23 96H49M23 96V78"/>',
        label(7,20,'D_r：环芯')+label(118,27,'D_b：总线芯')+label(117,52,'s（直线坐标）')+label(10,56,'T_φ E_r')+label(10,106,'环域 t=Rφ，面积权重含 ρ/R')+label(117,76,'总线域：')+label(117,83,'ρ=hypot(R_b+u,s)')+label(117,91,'相位 βs−qφ'),
        'coupling.kernels gb/gr coordinate mapping and vector rotation')
    route=diagram('route','相干路线：传播与基底投影',
        '<path d="M10 45H48Q66 45 66 63V78Q66 96 84 96H121Q139 96 139 78V45H174" fill="none" stroke="#17669a" stroke-width="3"/><rect x="39" y="39" width="5" height="12" fill="#b8473d"/><rect x="146" y="39" width="5" height="12" fill="#b8473d"/>',
        '<path class="guide" d="M41.5 29V58M148.5 29V58"/>',
        label(8,23,'a_in → M=G⁻¹B → D → … → M → a_out')+label(9,36,'直基底')+label(68,55,'弯基底')+label(118,36,'输出基底')+label(8,68,'D_j = exp(−ik₀n_jL)')+label(8,76,'L_arc = R|θ_arc|')+label(8,108,'功率 a†Ga；正交模单独功率相加不产生条纹'),
        'routes.matrices / propagate / spectrum; modes.overlap')
    text=(Path(__file__).parents[1]/'docs/model-and-equations.html.in').read_text(encoding='utf-8')
    material='<table><tr><th>i</th><th>SiN Bᵢ</th><th>SiN Cᵢ / µm²</th><th>SiO₂ Bᵢ</th><th>SiO₂ Cᵢ / µm²</th></tr>'
    for i,values in enumerate(zip(DATA['sin_B'],DATA['sin_C'],DATA['oxide_B'],DATA['oxide_C']),1):
        material+='<tr><td>'+str(i)+'</td>'+''.join(f'<td>{v}</td>' for v in values)+'</tr>'
    material+='</table>'
    for key,value in dict(version=__version__,plan_svg=plan,section_svg=section,kernel_svg=kernel,route_svg=route,material_table=material).items():text=text.replace('{{'+key+'}}',value)
    assert not re.search(r'\{\{\w+\}\}',text)
    ids=re.findall(r'\bid="([^"]+)"',text)
    assert len(ids)==len(set(ids))
    for anchor in re.findall(r'href="#([^"]+)"',text):assert anchor in ids
    assert not re.search(r'<(?:script|img|link)\b',text,re.I)
    assert len(re.findall(r'<svg\b',text))==4
    assert not re.search(r'</?\w+:',text)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(text,encoding='utf-8')
    assert check_html(output)==4
    return dict(path=str(output),semantic_diagrams=4,equations=len(re.findall(r'class="eq"',text)),offline=True,validation='XML, roles, unique IDs, links, label anchors; no browser aesthetic review')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(build(parser.parse_args().output),ensure_ascii=False))
