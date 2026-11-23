"""Seal or verify a portable package; all paths are relative and traversal-checked."""
import argparse
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sinphotonics.io import write_json,sha256


def seal(root,zip_path=None):
    manifest=root/'checksums.json'
    if manifest.exists():raise FileExistsError(manifest)
    files=[f for f in root.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
    write_json(manifest,dict(files=[dict(path=f.relative_to(root).as_posix(),sha256=sha256(f),bytes=f.stat().st_size) for f in sorted(files)]))
    if zip_path:
        zip_path=Path(zip_path).resolve()
        if zip_path.exists() or zip_path.is_relative_to(root):raise ValueError('ZIP must be new and outside the package')
        with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
            for f in files+[manifest]:z.write(f,f.relative_to(root).as_posix())
        print('ZIP SHA256',sha256(zip_path))


def verify(root):
    data=json.loads((root/'checksums.json').read_text(encoding='utf-8'))
    for item in data['files']:
        p=(root/item['path']).resolve()
        if not p.is_relative_to(root) or sha256(p)!=item['sha256'] or p.stat().st_size!=item['bytes']:
            raise ValueError(f'Integrity mismatch: {item["path"]}')
    print('Verified',len(data['files']),'files')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','verify']);p.add_argument('package');p.add_argument('--zip');a=p.parse_args()
    root=Path(a.package).resolve()
    seal(root,a.zip) if a.action=='seal' else verify(root)
