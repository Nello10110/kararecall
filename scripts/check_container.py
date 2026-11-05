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
    env=dict(os.environ,MEMOIRE_USERNAME='smoke-test',MEMOIRE_PASSWORD=secrets.token_urlsafe(30),MEMOIRE_PORT='18765',MEMOIRE_VOLUME_NAME='memoire-smoke-'+secrets.token_hex(6))
    command=['docker','compose','--project-name','memoire-smoke','--file',str(ROOT/'compose.yaml')]
    def compose(*args):
        return subprocess.run(command+list(args),cwd=ROOT,env=env,check=True,capture_output=True,text=True)
    auth='Basic '+base64.b64encode((env['MEMOIRE_USERNAME']+':'+env['MEMOIRE_PASSWORD']).encode()).decode()
    base='http://127.0.0.1:18765'
    def request(path,authenticated=True,headers=None):
        request=urllib.request.Request(base+path,headers={**({'Authorization':auth} if authenticated else {}),**(headers or {})})
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
            assert catalog['stats']==dict(tools=0,sources=0,processed=0)
        container=compose('ps','--quiet','web').stdout.strip()
        fixture=(ROOT/'tests/fixtures.py').read_text()+'\ncorpus(cerveau.ROOT)\n'
        subprocess.run(['docker','exec','-i',container,'python','-'],input=fixture,text=True,check=True,capture_output=True)
        with request('/api/catalog') as r:
            assert json.load(r)['stats']==dict(tools=2,sources=2,processed=2)
        with request('/api/search?q=pubs%20applis%20inutiles%20tele&scope=tools') as r:
            assert json.load(r)['results'][0]['id']=='tv-detox'
        with request('/api/context/heretic') as r:
            context=json.load(r)['markdown']
            assert '00:18' in context and 'example.com/demo-model' in context
        with request('/download/tool/heretic.md') as r:
            assert 'Comment ça fonctionne' in r.read().decode()
        with request('/assets/data/media/demo-model.mp4',headers={'Range':'bytes=100-199'}) as r:
            assert r.status==206 and len(r.read())==100
        container=compose('ps','--quiet','web').stdout.strip()
        usage=subprocess.check_output(['docker','stats','--no-stream','--format','{{.MemUsage}}',container],text=True).strip()
        print('Docker/OrbStack : volume vide puis corpus synthétique, auth, recherche, contexte, Markdown et requêtes vidéo vérifiés.')
        print('Mémoire observée au repos après les requêtes :',usage)
    finally:
        compose('down','--remove-orphans','--volumes')
        print('Conteneur, réseau et volume de test supprimés.')


if __name__=='__main__':
    main()
