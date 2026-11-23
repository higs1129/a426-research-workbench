"""Static contract and real launcher checks, without external scientific data."""
import pathlib
import re
import subprocess
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]


class SkillContract(unittest.TestCase):
    def test_frontmatter_links_and_launcher(self):
        text=(ROOT/'SKILL.md').read_text(encoding='utf-8')
        frontmatter=text.split('---',2)[1]
        self.assertIn('name: sin-photonics',frontmatter)
        self.assertIn('version: "2.0"',frontmatter)
        self.assertLess(len(text.splitlines()),500)
        for link in re.findall(r'\]\(([^)]+)\)',text):self.assertTrue((ROOT/link).is_file(),link)
        run=subprocess.run([sys.executable,str(ROOT/'scripts/run.py'),'--version'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(run.stdout.strip(),'2.0.0')

    def test_plotting_snapshot_and_bundled_material(self):
        import hashlib,json
        root=ROOT/'scripts/plotting-runtime'
        manifest=json.loads((root/'provenance.json').read_text(encoding='utf-8'))
        for item in manifest['files']:
            self.assertEqual(hashlib.sha256((root/item['path']).read_bytes()).hexdigest(),item['sha256'])
        data=json.loads((ROOT/'scripts/toolkit/sinphotonics/materials.json').read_text(encoding='utf-8'))
        self.assertEqual(data['version'],'reference300-v1')

    def test_external_environment_does_not_replace_bundled_toolkit(self):
        import os
        env=os.environ.copy();env.update(SIN_PHOTONICS_HOME='nonexistent-old-toolkit',SIN_PLOTTING_ROOT='nonexistent-old-renderer')
        run=subprocess.run([sys.executable,str(ROOT/'scripts/run.py'),'ring-bus','--config',str(ROOT/'examples/ring-scan-small.json'),'--plan'],capture_output=True,text=True,env=env)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('"native_mode_cases": 18',run.stdout)


if __name__=='__main__':unittest.main()
