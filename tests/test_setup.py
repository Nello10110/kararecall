import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class SetupTests(unittest.TestCase):
    def test_api_profile_is_private_disabled_and_never_overwrites(self):
        origin=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'scripts').mkdir()
            shutil.copy2(origin/'scripts/setup_env.py',root/'scripts/setup_env.py')
            shutil.copy2(origin/'.env.example',root/'.env.example')
            command=[sys.executable,str(root/'scripts/setup_env.py'),'--profile','api']
            created=subprocess.run(command,capture_output=True,text=True,check=True)
            env=(root/'.env').read_text()
            fields=dict(line.split('=',1) for line in env.splitlines() if line and not line.startswith('#'))
            self.assertEqual(fields['SYNC_ENABLED'],'false');self.assertEqual(fields['LLM_ENABLED'],'false')
            self.assertEqual(fields['LLM_MODEL'],'gpt-6-luna');self.assertEqual(fields['ASR_MODEL'],'whisper-large-v3-turbo')
            self.assertEqual(fields['LLM_API_KEY'],'');self.assertEqual(fields['ASR_API_KEY'],'')
            self.assertEqual((root/'.env').stat().st_mode&0o777,0o600)
            self.assertNotIn(fields['MEMOIRE_PASSWORD'],created.stdout)
            self.assertNotEqual(fields['MEMOIRE_PASSWORD'],'change-me-before-start')
            second=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0);self.assertEqual((root/'.env').read_text(),env)
