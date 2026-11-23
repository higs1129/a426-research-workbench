"""Build an explicit v1.1 distribution without modifying a previous release."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sinphotonics import __version__
from sinphotonics.io import new_output,write_json,sha256
from build_guide import build as build_guide
from package_manifest import verify


def build(previous,native,validation,readback,skill,out,commit):
    verify(previous)
    check=json.loads((validation/'validation.json').read_text(encoding='utf-8'))
    assert check['native_scan']['coupling_cases']==16
    mapping={}
    for family in ['ring','bus']:
        for row in csv.DictReader((native/family/'native-map.csv').open(encoding='utf-8')):
            mapping[family,row['outer'],row['eigenmode']]=row
    seen=set();max_error=0.
    for row in csv.DictReader(readback.open(encoding='utf-8')):
        key=(row['family'],row['outer'],row['eigenmode']);source=mapping[key]
        assert (row['model'],row['study'],row['dataset'])==(source['model'],source['study'],source['dataset'])
        with np.load(native/row['family']/'raw'/source['npz']) as z:
            v=z['info'][:,int(row['eigenmode'])-1]
        for k,field in [(0,'neff_real'),(1,'neff_imag'),(6,'width_bottom_um'),(7,'wavelength_nm'),(8,'radius_um')]:
            error=abs(v[k]-float(row[field]));max_error=max(max_error,error);assert error<1e-8
        seen.add(key)
    assert seen==set(mapping)
    out=new_output(out);copied=[]
    def copy(source,destination):
        target=out/destination;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        copied.append(dict(path=destination,source=source.name,sha256=sha256(target)))
    def tree(source,destination):
        for f in sorted(source.rglob('*')):
            if f.is_file() and not any(s in ('__pycache__','.pytest_cache') or s.endswith('.egg-info') for s in f.relative_to(source).parts):
                if destination=='skill' and 'tests' in f.relative_to(source).parts:continue
                copy(f,destination+'/'+f.relative_to(source).as_posix())
    for name in ['modes','evidence','plotting-runtime']:tree(previous/name,name)
    copy(previous/'sources.json','evidence/legacy-v1-sources.json')
    copy(previous/'verification/validation.json','evidence/legacy-v1-validation.json')
    # Preserve only useful cleared route templates; replace old solved ring/bus
    # representatives with the two new native multi-geometry family models.
    for name in ['bend','straight']:
        copy(previous/f'models/{name}-cleared-template.mph',f'models/{name}-cleared-template.mph')
    for family in ['ring','bus']:
        for name in ['raw','models']:tree(native/family/name,f'native-scan/{family}/{name}')
        for name in ['manifest.json','native-map.csv','solver-status.json']:
            copy(native/family/name,f'native-scan/{family}/{name}')
    for name in ['library.json','configuration.json']:copy(native/name,'native-scan/'+name)
    copy(readback,'verification/native-readback.csv')
    write_json(out/'verification/native-readback-check.json',dict(candidate_solutions=len(seen),max_absolute_error=max_error,
        method='COMSOL loadCopy: saved parameter/solution identity and neff compared against NPZ'))
    for name in ['native-replay','mixed-channels']:tree(validation/name,'verification/'+name)
    copy(validation/'validation.json','verification/validation-v1.1.json')
    tree(Path(__file__).resolve().parents[1],'toolkit');tree(skill,'skill')
    guide=build_guide(out/'model-and-equations.html');write_json(out/'verification/guide-check.json',guide)
    write_json(out/'version.json',dict(version=__version__,source_commit=commit,material='reference300-v1',
        base_release=json.loads((previous/'version.json').read_text(encoding='utf-8')),
        native_models='native-scan/{ring,bus}/models/*.mph; 18 parameter/channel cases, 36 candidates read back'))
    write_json(out/'sources.json',dict(previous_release_checksums_sha256=sha256(previous/'checksums.json'),files=copied,
        model_status={'native-scan/ring/models/bend_modes.mph':'solved; widths1.2/1.3, radii57.932443/60, λ1548/1550/1552; all saved identities read back',
        'native-scan/bus/models/straight_modes.mph':'solved; widths1.1/1.2, λ1548/1550/1552; all saved identities read back',
        'models/bend-cleared-template.mph':'legacy settings only; solution/mesh cleared',
        'models/straight-cleared-template.mph':'legacy settings only; solution/mesh cleared'}))
    (out/'README.md').write_text('''# SiN photonics 1.1.0

只使用300 nm工艺的 `reference300-v1` 材料参数。先读[模型与公式说明](model-and-equations.html)：独立离线HTML，4幅语义结构图、22组公式、材料系数、计算函数映射与限制。

## 本版验收

- [验证汇总](verification/validation-v1.1.json)：纵向窗口独立收敛，参考gap1.2的Qc≈3.456625 M；显式15、30 µm与自动初值一致。支持域不足不能用零填充假装通过。
- [真实原生多参数扫描](verification/native-replay/report.html)：2环宽×2总线宽×2半径×2间隙，共16项；底层18个模式算例合并在2个带解MPH内。[参数/解映射](verification/native-replay/native-mode-map.json)包含ng的全部±2 nm锚点。
- [缺失通道用例](verification/mixed-channels/report.html)：窄总线TE1缺失记为null和诊断，其他几何继续处理。
- [原生读回](verification/native-readback-check.json)：36个候选解的参数及复neff与NPZ逐项比较。
- R40自动规划保留足够比较次数，但旧场的边缘比≈2.27e−4，仍为采样域截断诊断；这不是通过放宽阈值得到的修复。

## 使用

Python≥3.11，NumPy≥2、SciPy≥1.14、jsonschema≥4.20。新几何需要COMSOL6.1；重放不需要历史目录或COMSOL。

```powershell
$env:PYTHONPATH = (Resolve-Path toolkit).Path
python -m sinphotonics ring-bus --config toolkit/examples/ring-scan-small.json --plan
python -m sinphotonics ring-bus --config toolkit/examples/ring-scan-small.json --library native-scan --output replay-scan
python -m sinphotonics ring-bus --config toolkit/examples/ring-reference.json --library modes --output replay-reference
python -m sinphotonics bends --config toolkit/examples/route-r40-reference.json --library modes --output replay-route
python toolkit/scripts/package_manifest.py verify .
```

新求解省略`--library`并给出`--comsol-bin`。扫描预算、窗口容差与原始数组说明见[工具README](toolkit/README.md)。[Skill说明](skill/SKILL.md)与[操作参考](skill/references/operation.md)随包提供。

`native-scan`保存本次两个带解MPH及其必要原始字段；`models`仅保留两个清空解的转弯模板。没有复制整套历史MPH。`evidence/legacy-v1-*`和旧CSV是明确标记的历史基准，不代表1.1重新验收。原始资料与1.0包未修改。

纵向收敛、双域一致和数值守恒均不等于网格/PML收敛或全器件物理验证。TM、非正交与遗漏通道限制详见模型说明。结构图仅示意，不是全三维联合解。
''',encoding='utf-8')
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['previous','native','validation','readback','skill-source','output','source-commit']:p.add_argument('--'+key,required=True)
    a=p.parse_args()
    print(build(Path(a.previous).resolve(),Path(a.native).resolve(),Path(a.validation).resolve(),Path(a.readback).resolve(),Path(a.skill_source).resolve(),a.output,a.source_commit))
