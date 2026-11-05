import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class SetupTests(unittest.TestCase):
    def test_default_deepseek_profile_keeps_audio_and_paid_calls_disabled(self):
        origin=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'scripts').mkdir()
            shutil.copy2(origin/'scripts/setup_env.py',root/'scripts/setup_env.py')
            shutil.copy2(origin/'.env.example',root/'.env.example')
            subprocess.run([sys.executable,str(root/'scripts/setup_env.py')],capture_output=True,text=True,check=True)
            fields=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if line and not line.startswith('#'))
            self.assertEqual(fields['LLM_MODEL'],'deepseek-flash')
            self.assertEqual(fields['VISION_MODEL'],'deepseek-flash')
            self.assertEqual(fields['ASR_MODEL'],'')
            self.assertEqual(fields['KARAKEEP_URL_FILTER'],'')
            self.assertEqual(fields['AI_TOKEN_LIMIT_PARAM'],'max_tokens')
            self.assertEqual(fields['LLM_THINKING'],'disabled')
            self.assertEqual(fields['LLM_API_KEY'],'')
            self.assertEqual(fields['SYNC_ENABLED'],'false');self.assertEqual(fields['LLM_ENABLED'],'false')

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
            self.assertNotIn(fields['KARARECALL_PASSWORD'],created.stdout)
            self.assertNotEqual(fields['KARARECALL_PASSWORD'],'change-me-before-start')
            second=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0);self.assertEqual((root/'.env').read_text(),env)
