"""Read-only generation inventory and integrity checks; never changes the pointer."""
import argparse
import json
from pathlib import Path
import re
from publication import active_root


def generations(root):
    selected=active_root(root);directory=root/'data/generations'
    candidates=sorted(directory.iterdir(),key=lambda item:item.name) if directory.is_dir() else []
    rows=[]
    for target in candidates:
        if target.is_symlink() or not re.fullmatch('[a-f0-9]{32}',target.name) or not target.is_dir():continue
        catalog=target/'data/catalog.json'
        rows.append({'generation':target.name,'selected':target==selected,'catalog_present':catalog.is_file(),
                     'published_timestamp':catalog.stat().st_mtime if catalog.is_file() else None})
    return sorted(rows,key=lambda row:row['published_timestamp'] or 0,reverse=True)


def inspect(root, identifier=None):
    rows=generations(root)
    report={'mode':'read_only','generations':rows,'external_backup':'not_observed','integrity':'not_checked'}
    if identifier:
        if not re.fullmatch('[a-f0-9]{32}',identifier) or not any(row['generation']==identifier for row in rows):
            raise ValueError('Génération inconnue.')
        try:from verify_storage import verify
        except ModuleNotFoundError:from scripts.verify_storage import verify
        result=verify(root/'data/generations'/identifier)
        report['integrity']={'generation':identifier,**result}
    return report


def main():
    parser=argparse.ArgumentParser(description='Inventorier et vérifier des générations sans les restaurer.')
    parser.add_argument('--root',type=Path)
    parser.add_argument('--generation',help='Identifiant exact de la génération à vérifier')
    args=parser.parse_args()
    from settings import Settings
    root=args.root or Settings.from_env().root
    try:print(json.dumps(inspect(root,args.generation),ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError):
        print(json.dumps({'state':'error','message':'Génération absente ou incohérente ; aucun changement appliqué.'},ensure_ascii=False))
        raise SystemExit(1)


if __name__=='__main__':main()
