"""Optional local ASR worker. Download the model once; never upload audio."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("videos", nargs="+")
    p.add_argument("--model", default="small")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--force", action="store_true", help="Recalculer une transcription existante")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    # All model/cache writes stay inside this project.
    os.environ.setdefault("HF_HOME", str(root / "data/models/huggingface"))
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=4,
                         download_root=str(root / "data/models"), local_files_only=args.offline)
    for video in args.videos:
        path = Path(video)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        output = root / "data/extracted" / path.stem / "transcript.json"
        if output.exists() and not args.force:
            old = json.loads(output.read_text())
            if old.get("media_sha256") == digest and old.get("model") == args.model:
                print("Déjà transcrit:", path.name, flush=True)
                continue
        print("Transcription:", path.name, flush=True)
        segments, info = model.transcribe(str(path), language="fr", beam_size=5,
                                          vad_filter=True, condition_on_previous_text=False)
        rows = []
        for s in segments:
            rows.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                         "avg_logprob": s.avg_logprob, "no_speech_prob": s.no_speech_prob})
            print(f"[{s.start:.1f}–{s.end:.1f}] {s.text}", flush=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        result = {"engine": "faster-whisper 1.2.1", "model": args.model,
                  "media_sha256": digest, "language": info.language, "duration": info.duration,
                  "status": "complete", "segments": rows}
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(output)


if __name__ == "__main__":
    main()
