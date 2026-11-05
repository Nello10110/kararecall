"""Process explicitly supplied local attachments, then rebuild the portable vault."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cerveau


def main():
    p = argparse.ArgumentParser()
    p.add_argument('videos', nargs='+', help='Local MP4 files named BOOKMARK_ID.mp4 in data/media')
    p.add_argument('--model', default='small')
    p.add_argument('--interval', type=float, default=1.0)
    p.add_argument('--offline', action='store_true')
    args = p.parse_args()
    if args.interval <= 0:
        p.error('interval doit être positif')
    paths = [Path(v).resolve() for v in args.videos]
    known = {s['id'] for s in cerveau.read_json(ROOT/'data/sources.json', [])}
    for path in paths:
        if path.parent != ROOT/'data/media' or path.suffix != '.mp4' or path.stem not in known:
            p.error('Chaque vidéo doit être dans data/media, nommée avec un ID déjà importé.')
    errors = []
    command = [sys.executable, str(ROOT/'scripts/transcribe.py'), '--model', args.model]
    if args.offline:
        command += ['--offline']
    try:
        subprocess.run(command + [str(p) for p in paths], check=True)
    except subprocess.CalledProcessError as exc:
        errors.append({'stage': 'asr', 'exit_code': exc.returncode})
    if platform.system() != 'Darwin':
        errors.append({'stage': 'ocr', 'error': 'Apple Vision requires macOS; OCR worker replaceable'})
    else:
        binary = ROOT/'.build/ocr'
        swift = ROOT/'scripts/ocr.swift'
        binary.parent.mkdir(exist_ok=True)
        try:
            if not binary.exists() or swift.stat().st_mtime > binary.stat().st_mtime:
                subprocess.run(['swiftc', '-module-cache-path', str(ROOT/'.build/swift-cache'), str(swift), '-o', str(binary)], check=True)
            from frames import extract
            for path in paths:
                directory = ROOT/'data/extracted'/path.stem
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                current = cerveau.read_json(directory/'ocr.json', {})
                if current.get('media_sha256') == digest and current.get('interval') == args.interval and current.get('status') == 'complete':
                    print('OCR déjà extrait:', path.name, flush=True)
                    continue
                extract(path, args.interval)
                subprocess.run([str(binary), str(directory)], check=True)
        except (subprocess.CalledProcessError, ImportError, OSError) as exc:
            errors.append({'stage': 'ocr', 'error': str(exc)})
    cerveau.write_json(ROOT/'data/last-process.json', {'errors': errors, 'media': [p.name for p in paths]})
    cerveau.build()
    if errors:
        print(json.dumps(errors, ensure_ascii=False), file=sys.stderr)
        return 1
    print('Traitement complet. Le coffre est prêt dans vault/INDEX.md.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
