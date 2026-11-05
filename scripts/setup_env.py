#!/usr/bin/env python3
"""Create a private local configuration without replacing an existing one."""
import argparse
import os
from pathlib import Path
import secrets


def main():
    parser=argparse.ArgumentParser(description='Créer une configuration privée sans remplacer un fichier existant')
    parser.add_argument('--profile',choices=['deepseek','api','empty'],default='deepseek')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    target=root/'.env'
    text=(root/'.env.example').read_text().replace('MEMOIRE_PASSWORD=change-me-before-start',
        'MEMOIRE_PASSWORD='+secrets.token_urlsafe(32))
    values={}
    if args.profile=='deepseek':
        values={'LLM_BASE_URL':'https://api.deepseek.com','LLM_MODEL':'deepseek-flash',
                'VISION_BASE_URL':'https://api.deepseek.com','VISION_MODEL':'deepseek-flash',
                'AI_TOKEN_LIMIT_PARAM':'max_tokens','LLM_THINKING':'disabled','VISION_THINKING':'disabled',
                'LLM_INPUT_USD_PER_MILLION':'0.30','LLM_OUTPUT_USD_PER_MILLION':'1.20',
                'VISION_INPUT_USD_PER_MILLION':'0.30','VISION_OUTPUT_USD_PER_MILLION':'1.20'}
    elif args.profile=='api':
        values={'LLM_BASE_URL':'https://api.openai.com/v1','LLM_MODEL':'gpt-6-luna',
                'ASR_BASE_URL':'https://api.groq.com/openai/v1','ASR_MODEL':'whisper-large-v3-turbo',
                'VISION_BASE_URL':'https://api.openai.com/v1','VISION_MODEL':'gpt-6-luna',
                'LLM_REASONING_EFFORT':'none','VISION_REASONING_EFFORT':'none',
                'LLM_INPUT_USD_PER_MILLION':'0.10','LLM_OUTPUT_USD_PER_MILLION':'0.50',
                'VISION_INPUT_USD_PER_MILLION':'0.10','VISION_OUTPUT_USD_PER_MILLION':'0.50','ASR_USD_PER_HOUR':'0.04'}
    if values:
        lines=[]
        for line in text.splitlines():
            key=line.partition('=')[0]
            lines.append(key+'='+values[key] if key in values else line)
        text='\n'.join(lines)+'\n'
    try:
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        raise SystemExit('.env existe déjà : conservé sans modification.')
    with os.fdopen(descriptor,'w') as output:
        output.write(text)
    print('.env créé avec un mot de passe aléatoire. Identifiants à consulter dans ce fichier, puis compléter les clés et activer les étapes souhaitées. Aucun appel n’a été lancé.')


if __name__=='__main__':
    main()
