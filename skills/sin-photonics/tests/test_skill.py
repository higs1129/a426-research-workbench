"""Static contract and real launcher checks, without external scientific data."""
import pathlib
import re
import subprocess
import sys
import unittest
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[1]


class SkillContract(unittest.TestCase):
    def test_frontmatter_links_and_launcher(self):
        text=(ROOT/'SKILL.md').read_text(encoding='utf-8')
        metadata=yaml.safe_load(text.split('---',2)[1])
        self.assertEqual(metadata['name'],ROOT.name)
        self.assertIsInstance(metadata['metadata']['version'],str)
        self.assertLess(len(text.splitlines()),500)
        for link in re.findall(r'\]\(([^)]+)\)',text):self.assertTrue((ROOT/link).is_file(),link)
        toolkit=ROOT.parents[1]/'research/sin-photonics'
        run=subprocess.run([sys.executable,str(ROOT/'scripts/run.py'),'--toolkit',str(toolkit),'--version'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(run.stdout.strip(),'1.1.0')


if __name__=='__main__':unittest.main()
