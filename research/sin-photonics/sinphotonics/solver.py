"""COMSOL 6.1 native sweeps. Immutable Java + UTF-8 properties, no code rewriting."""
from pathlib import Path
import os
import shutil
import subprocess
import time
import numpy as np
from .materials import expression
from .io import write_json,sha256


def locate_bin(explicit=None):
    path=explicit or os.environ.get('COMSOL_BIN')
    if path:
        p=Path(path).resolve()
    else:
        exe=shutil.which('comsolbatch') or shutil.which('comsolbatch.exe')
        if not exe:
            raise FileNotFoundError('Set --comsol-bin or COMSOL_BIN to the COMSOL bin directory')
        p=Path(exe).parent
    for name in ('comsolbatch.exe','comsolcompile.exe'):
        if not (p/name).is_file():
            raise FileNotFoundError(p/name)
    return p


def run_java(source,out,properties,bin_dir,cores=3):
    runtime=out/'runtime';runtime.mkdir(parents=True)
    prefs=runtime/'preferences';prefs.mkdir()
    (prefs/'comsol.prefs').write_text('security.external.filepermission=full\n',encoding='utf-8')
    source=Path(source);target=runtime/source.name;shutil.copy2(source,target)
    # Reader-based Java Properties handles unicode; values cannot inject code.
    text='\n'.join(f'{k}={str(v).replace(chr(92), "/")}' for k,v in properties.items())+'\n'
    (runtime/'run.properties').write_text(text,encoding='utf-8')
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    start=time.time()
    with (runtime/'compile.log').open('w',encoding='utf-8') as f:
        subprocess.run([str(bin_dir/'comsolcompile.exe'),'-prefsdir',str(prefs),'-tmpdir',str(runtime),str(target)],cwd=runtime,stdout=f,stderr=subprocess.STDOUT,check=True,creationflags=flags)
    if not target.with_suffix('.class').is_file():
        raise RuntimeError(f'Native Java compilation produced no class; see {runtime / "compile.log"}')
    log=runtime/'solver.log'
    with log.open('w',encoding='utf-8') as f:
        process=subprocess.run([str(bin_dir/'comsolbatch.exe'),'-inputfile',str(target.with_suffix('.class')),
            '-batchlog',str(runtime/'batch.log'),'-np',str(cores),'-tmpdir',str(runtime),
            '-prefsdir',str(prefs),'-nosave'],cwd=runtime,stdout=f,stderr=subprocess.STDOUT,creationflags=flags)
    status=dict(returncode=process.returncode,seconds=time.time()-start,source_sha256=sha256(source))
    write_json(out/'solver-status.json',status)
    if process.returncode or 'COMPLETE' not in log.read_text(encoding='utf-8',errors='replace'):
        raise RuntimeError(f'COMSOL did not complete; see {log}')
    return status


def solve(out,cs,widths,wavelengths,radii,channels,bin_dir,mesh=.7,cores=3,mode_search=None):
    out=Path(out);out.mkdir(parents=True)
    (out/'raw').mkdir();(out/'models').mkdir()
    bend=any(r>0 for r in radii)
    if bend and any(r<=13 for r in radii):
        raise ValueError('Bend radius must exceed 13 µm for this local domain')
    # Frozen run03 search heuristics locate branches; these are not material
    # models and never replace FEM eigenvalues. Explicit numeric overrides help
    # inspect a shifted branch without editing or rewriting Java source.
    wide='1.598+0.093*(Wbottom/1[um]-1.22)-0.04*(Wbottom/1[um]-1.22)^2'
    narrow='1.5394+0.19*(Wbottom/1[um]-0.8)-0.14*(Wbottom/1[um]-0.8)^2'
    seeds={'TE0':f'if(Wbottom<1[um],{narrow},{wide})',
           'TE1':'1.444+0.12*(Wbottom/1[um]-1.27)','TM0':'1.515-0.00015*(lambda0/1[nm]-1550)'}
    search=mode_search or {};seeds.update(search.get('shifts',{}))
    counts=[search.get('eigenmodes',8 if c=='TE1' else 4) for c in channels]
    properties=dict(root=out.resolve().as_posix(),bend=str(bend).lower(),mesh=mesh,
        thickness_um=cs.thickness_nm/1000,wall_deg=cs.wall_deg,lower_oxide_um=cs.lower_oxide_um,
        upper_oxide_um=cs.upper_oxide_um,widths=' '.join(map(str,widths)),
        wavelengths=' '.join(map(str,wavelengths)),radii=' '.join(map(str,radii)),
        channels=','.join(channels),seeds='|'.join(str(seeds[c]) for c in channels),eigenmodes=','.join(map(str,counts)),
        count=len(widths)*len(wavelengths)*len(radii),n_core=expression('sin',cs.material),
        n_oxide=expression('oxide'),material=cs.material)
    status=run_java(Path(__file__).with_name('native')/'NativeModes.java',out,properties,bin_dir,cores)
    files=list((out/'raw').glob('*.npz'))
    if len(files)!=int(properties['count'])*len(channels):
        raise RuntimeError('Incomplete NPZ export')
    for path in files:
        with np.load(path,allow_pickle=False) as z:
            if not all(np.isfinite(z[k]).all() for k in z.files):
                raise RuntimeError(f'Nonfinite export {path}')
    from .modes import catalog,select
    rows=catalog(out/'raw')
    for w in widths:
        for wl in wavelengths:
            for rad in radii:
                for channel in channels:
                    select(rows,w,wl,rad,channel,True)
    write_json(out/'manifest.json',dict(status='solved',comsol='6.1',configuration=properties,
        files=[dict(path=str(p.relative_to(out)),sha256=sha256(p),bytes=p.stat().st_size) for p in [*files,*list((out/'models').glob('*.mph'))]],solver=status))
    return out/'raw'
