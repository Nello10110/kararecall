"""Build/run/check/stop a disposable OrbStack or Docker Compose test service.

Credentials are random, passed through process environment, never written or printed.
"""
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    defaults=dict(line.split('=',1) for line in (ROOT/'.env.example').read_text().splitlines() if line and not line.startswith('#'))
    # Never inherit the real installation's connections or enabled automation.
    env=dict(os.environ,**defaults)
    env.update(KARARECALL_USERNAME='smoke-test',KARARECALL_PASSWORD=secrets.token_urlsafe(30),KARARECALL_PORT='18765',KARARECALL_VOLUME_NAME='kararecall-smoke-'+secrets.token_hex(6),COMPOSE_PROFILES='automation',DIGEST_ENABLED='false',DIGEST_WRITE_ARTICLES='false',DIGEST_SEND_ENABLED='false',SYNC_ENABLED='false',LLM_ENABLED='false',ASR_MODEL='',VISION_MODEL='')
    command=['docker','compose','--project-name','kararecall-smoke','--file',str(ROOT/'compose.yaml'),'--file',str(ROOT/'compose.build.yaml')]
    def compose(*args):
        return subprocess.run(command+list(args),cwd=ROOT,env=env,check=True,capture_output=True,text=True)
    restored_volume=env['KARARECALL_VOLUME_NAME']+'-restore'
    auth='Basic '+base64.b64encode((env['KARARECALL_USERNAME']+':'+env['KARARECALL_PASSWORD']).encode()).decode()
    base='http://127.0.0.1:18765'
    def request(path,authenticated=True,headers=None,data=None):
        request=urllib.request.Request(base+path,data=data,headers={**({'Authorization':auth} if authenticated else {}),**(headers or {})})
        return urllib.request.urlopen(request,timeout=5)
    try:
        compose('up','--detach','--build')
        deadline=time.monotonic()+30
        while True:
            try:
                with request('/api/health') as r:
                    assert json.load(r)['status']=='ok'
                break
            except (OSError,urllib.error.URLError):
                if time.monotonic()>deadline:
                    raise
                time.sleep(0.25)
        try:
            request('/api/catalog',authenticated=False)
            raise AssertionError('Unauthenticated access was accepted')
        except urllib.error.HTTPError as error:
            assert error.code==401
        with request('/api/catalog') as r:
            catalog=json.load(r)
        with request('/api/overview') as r:
            overview=json.load(r);assert overview['summary']['sources']==0
        with request('/api/administration/diagnostic') as r:
            diagnostic=json.load(r);assert diagnostic['application']=='KaraRecall' and 'sources' not in diagnostic
        for asset in ('/glass.css','/workspace.js'):
            with request(asset) as r:assert r.status==200
            assert catalog['stats']==dict(tools=0,sources=0,processed=0)
        while True:
            with request('/api/catalog') as response:disabled=json.load(response).get('worker',{}).get('state')=='disabled'
            if disabled:break
            if time.monotonic()>deadline:raise AssertionError('Disabled worker did not report its state')
            time.sleep(.25)
        with request('/api/control') as r:csrf=json.load(r)['csrf_token']
        with request('/api/import-history',headers={'Content-Type':'application/json','X-KaraRecall-CSRF':csrf},data=b'{}') as r:
            assert r.status==202 and json.load(r)['state']=='queued'
        deadline=time.monotonic()+10
        while True:
            with request('/api/control') as r:task=json.load(r)['history_import']
            if task['state']=='error':
                assert 'KARAKEEP_BASE_URL' in task['message']
                break
            if time.monotonic()>deadline:raise AssertionError('Disabled worker did not consume manual import request')
            time.sleep(.25)
        container=compose('ps','--quiet','web').stdout.strip()
        fixture=(ROOT/'tests/fixtures.py').read_text()+'''
corpus(kararecall.ROOT)
from publication import generation,migrate
with generation(kararecall.ROOT) as (draft,publish):
    sources,entities=migrate(kararecall.read_json(draft/'data/sources.json'),kararecall.read_json(draft/'data/entities.json'),draft)
    kararecall.write_json(draft/'data/sources.json',sources)
    kararecall.write_json(draft/'data/entities.json',entities)
    publish()
'''
        subprocess.run(['docker','exec','-i',container,'python','-'],input=fixture,text=True,check=True,capture_output=True)
        with request('/api/catalog') as r:
            assert json.load(r)['stats']==dict(tools=2,sources=2,processed=2)
        with request('/api/sources?limit=1&offset=1') as r:
            page=json.load(r)
            assert page['offset']==1 and page['total']==2 and len(page['sources'])==1
        with request('/api/search?q=pubs%20applis%20inutiles%20tele&scope=tools') as r:
            assert json.load(r)['results'][0]['id']=='tv-detox'
        with request('/api/context/heretic') as r:
            context=json.load(r)['markdown']
            assert '00:18' in context and 'example.com/demo-model' in context
        with request('/download/tool/heretic.md') as r:
            assert 'Comment ça fonctionne' in r.read().decode()
        with request('/assets/data/media/demo-model.mp4',headers={'Range':'bytes=100-199'}) as r:
            assert r.status==206 and len(r.read())==100
        with request('/api/control') as r:csrf=json.load(r)['csrf_token']
        headers={'Content-Type':'application/json','X-KaraRecall-CSRF':csrf}
        with request('/api/digests/generate',headers=headers,data=json.dumps({'kind':'weekly','anchor':'2026-11-02'}).encode()) as r:
            edition=json.load(r)
            assert len(edition['items'])==2
        path='/api/digests/'+edition['id']
        with request(path+'/approve',headers=headers,data=json.dumps({'revision':edition['revision']}).encode()) as r:
            assert json.load(r)['approved']
        compose('up','--detach','--no-deps','--force-recreate','web')
        deadline=time.monotonic()+30
        while True:
            try:
                with request(path) as r:assert json.load(r)['approved']
                break
            except (OSError,urllib.error.URLError):
                if time.monotonic()>deadline:raise
                time.sleep(.25)
        container=compose('ps','--quiet','web').stdout.strip()
        verified=json.loads(compose('exec','-T','web','python','verify_storage.py').stdout)
        assert verified['versioned'] and verified['tools']==2 and verified['digests']==1
        image=subprocess.check_output(['docker','inspect','--format','{{.Config.Image}}',container],text=True).strip()
        compose('stop','worker')
        backup=subprocess.run(['docker','exec',container,'tar','-C','/workspace','-czf','-','data','vault'],check=True,capture_output=True).stdout
        subprocess.run(['docker','volume','create',restored_volume],check=True,capture_output=True)
        subprocess.run(['docker','run','--rm','-i','--mount','type=volume,src='+restored_volume+',dst=/workspace',image,'tar','-C','/workspace','-xzf','-'],input=backup,check=True,capture_output=True)
        restored=subprocess.run(['docker','run','--rm','--read-only','--mount','type=volume,src='+restored_volume+',dst=/workspace',image,'python','verify_storage.py'],check=True,capture_output=True,text=True)
        assert json.loads(restored.stdout)==verified
        usage=subprocess.check_output(['docker','stats','--no-stream','--format','{{.MemUsage}}',container],text=True).strip()
        print('Docker/OrbStack : corpus synthétique, auth, recherche, exports, vidéo, bulletin conservé après recréation du web et sauvegarde/restauration vérifiés.')
        print('RAM observée au repos après les requêtes :',usage)
    finally:
        subprocess.run(['docker','volume','rm',restored_volume],capture_output=True)
        compose('down','--remove-orphans','--volumes')
        print('Conteneur, réseau et volume de test supprimés.')


if __name__=='__main__':
    main()
