"""Targeted real-browser consistency regression; all output stays inside Skill tests."""
import functools
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from bundle_report_figures import bundle
from check_semantic_svg_integrity import inspect


def main():
    browser = next((Path(p) for p in [os.environ.get('SCIENTIFIC_TEST_BROWSER', ''),
        'C:/Program Files/Google/Chrome/Application/chrome.exe',
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'] if p and Path(p).is_file()), None)
    if browser is None:
        raise SystemExit('Set SCIENTIFIC_TEST_BROWSER to an installed Chromium browser')
    with tempfile.TemporaryDirectory(prefix='component-', dir=ROOT / 'tests', ignore_cleanup_errors=True) as temp:
        run = Path(temp)
        env = {**os.environ, 'MPLBACKEND': 'Agg', 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONPATH': str(ROOT / 'tests/fixtures'), 'MPLCONFIGDIR': str(run / 'mpl')}
        for name, fixture in [('scatter','report_component_scatter.py'), ('lines','report_component_plot.py')]:
            subprocess.run([sys.executable, str(ROOT / 'scripts/render_matplotlib_editable.py'),
                '--plot-script', str(ROOT / 'tests/fixtures' / fixture), '--profile-id','90mm-single',
                '--output',str(run / f'{name}.html')], check=True, env=env, capture_output=True)
        model = {'figureId':'synthetic-scatter', 'profile':'90mm-single', 'heightMm':58.24,
            'sourceOrigin':'authoritative-data', 'coordinateConfidence':'exact',
            'x':{'domain':[0.5,16.5], 'scale':'linear', 'title':'Sample', 'unit':'', 'ticks':[1,4,7,10,13,16]},
            'y':{'domain':[0,60], 'scale':'linear', 'title':'Response', 'unit':'dB'},
            'series':[{'id':'points','kind':'scatter','label':'Scatter A','color':'#0072b2',
                       'points':[[i+1,20+(i*7%19)] for i in range(16)]}],
            'legend':{'visible':True,'loc':'lower left'}}
        model_path = run/'model.json'; model_path.write_text(json.dumps(model),encoding='utf-8')
        command = [sys.executable,str(ROOT/'scripts/render_matplotlib_editable.py'),'--model',str(model_path),
                   '--profile-id','90mm-single','--output',str(run/'model.html')]
        subprocess.run(command,check=True,env=env,capture_output=True)
        def payload(path):
            return json.loads(re.search(r'<script id="scientific-figure-data"[^>]*>(.*?)</script>',path.read_text(encoding='utf-8'),re.S)[1])
        a,b = payload(run/'scatter.html'),payload(run/'model.html')
        for key in ['fullView','initialTicks','series','legend','plotBounds']:
            assert a[key] == b[key], f'Semantic-model/Matplotlib adapter disagreement: {key}'
        model['series'][0]['unmappedStyle'] = True
        model_path.write_text(json.dumps(model),encoding='utf-8')
        command[-1] = str(run/'unsupported.html')
        failure = subprocess.run(command,env=env,capture_output=True)
        assert failure.returncode != 0 and not (run/'unsupported.html').exists(), 'Capability gap must stop before output'
        shell = '''<!doctype html><html><head><title>Figure component regression</title></head><body>
        <p id="report-prose" contenteditable="true">Original report</p>
        <div style="width:640px"><!-- SCIENTIFIC_FIGURE:scatter --><!-- SCIENTIFIC_FIGURE:lines --></div>
        <!-- SCIENTIFIC_REPORT_RUNTIME --><script id="regression-harness">HARNESS</script></body></html>'''
        shell = shell.replace('HARNESS', (ROOT / 'tests/report_component_browser.js').read_text(encoding='utf-8'))
        document = bundle(shell, [{'id':name, 'html':f'{name}.html'} for name in ['scatter','lines']], run)
        (run/'report.html').write_text(document, encoding='utf-8')
        server = ThreadingHTTPServer(('127.0.0.1',0), functools.partial(SimpleHTTPRequestHandler, directory=str(run)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/report.html'
            response = build_opener(ProxyHandler({})).open(url)
            assert response.status == 200 and b'Figure component regression' in response.read()
            process = subprocess.run(['node', str(ROOT / 'tests/run_component_browser.mjs'), str(browser),str(run / 'browser'),url],
                capture_output=True, encoding='utf-8', errors='replace', timeout=40)
            match = re.search(r'<pre id="regression-result"[^>]*>(.*?)</pre>', process.stdout, re.S)
            if not match:
                raise AssertionError('Browser produced no test result: '+process.stderr[-1500:])
            result = json.loads(html.unescape(match[1])); print(json.dumps(result, ensure_ascii=False))
            assert result['ok'], result
            for index, svg in enumerate(re.findall(r'<textarea data-exported-svg="[^"]+">(.*?)</textarea>',process.stdout,re.S)):
                path = run / f'export-{index}.svg'; path.write_text(html.unescape(svg),encoding='utf-8')
                issues = inspect(path); assert not issues, issues
            print('Real browser geometry, initial-state parity, current SVG export and portable report save/reopen verified.')
            print('Semantic-model and Matplotlib inputs share the component path; unsupported model fields stop before output.')
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
