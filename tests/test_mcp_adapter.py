from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from fixtures import corpus
from web_server import Corpus, make_handler

try:
    SDK_V2=version('mcp').startswith('2.')
except PackageNotFoundError:
    SDK_V2=False


@unittest.skipUnless(SDK_V2,'Le SDK MCP 2 est une dépendance facultative')
class MCPStdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_citations_read_only_and_absent_data(self):
        from mcp import Client, StdioServerParameters

        with tempfile.TemporaryDirectory() as name:
            root=Path(name);corpus(root)
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Corpus(root),'mcp','fixture'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                executable=Path(__file__).resolve().parents[1]/'kararecall_mcp.py'
                if not executable.exists():executable=Path('/app/kararecall_mcp.py')
                params=StdioServerParameters(command=sys.executable,args=[str(executable)],env={
                    'KARARECALL_URL':f'http://127.0.0.1:{server.server_port}',
                    'KARARECALL_USERNAME':'mcp','KARARECALL_PASSWORD':'fixture','PYTHONDONTWRITEBYTECODE':'1'})
                async with Client(params) as client:
                    tools=await client.list_tools()
                    self.assertEqual({tool.name for tool in tools.tools},{'search','get_tool','get_source','get_evidence','get_context'})
                    result=await client.call_tool('search',{'query':'enlever les pubs de ma télé','limit':1})
                    self.assertFalse(result.is_error)
                    self.assertEqual(result.structured_content['results'][0]['id'],'tv-detox')
                    result=await client.call_tool('get_evidence',{'source_id':'demo-tv','evidence_id':'asr-000'})
                    self.assertEqual(result.structured_content['ref'],'demo-tv#asr-000')
                    self.assertEqual(result.structured_content['start_seconds'],18)
                    self.assertEqual(result.structured_content['url_originale'],'https://example.com/demo-tv')
                    result=await client.call_tool('get_context',{'tool_id':'tv-detox','max_chars':30})
                    self.assertEqual(len(result.structured_content['markdown']),30)
                    self.assertEqual(result.structured_content['next_offset'],30)
                    result=await client.call_tool('search',{'query':'zzzxqxkwg'})
                    self.assertEqual(result.structured_content['results'],[])
                    result=await client.call_tool('get_source',{'source_id':'inconnu'})
                    self.assertEqual(result.structured_content,{'found':False})
                    result=await client.call_tool('get_source',{'source_id':'../.env'})
                    self.assertTrue(result.is_error)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=5)
