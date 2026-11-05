#!/usr/bin/env python3
"""Create a private local configuration without replacing an existing one."""
import os
from pathlib import Path
import secrets


def main():
    root=Path(__file__).resolve().parents[1]
    target=root/'.env'
    text=(root/'.env.example').read_text().replace('MEMOIRE_PASSWORD=change-me-before-start',
        'MEMOIRE_PASSWORD='+secrets.token_urlsafe(32))
    try:
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        raise SystemExit('.env existe déjà : conservé sans modification.')
    with os.fdopen(descriptor,'w') as output:
        output.write(text)
    print('.env créé avec un mot de passe aléatoire. Identifiants à consulter dans ce fichier, puis compléter les connexions souhaitées.')


if __name__=='__main__':
    main()
