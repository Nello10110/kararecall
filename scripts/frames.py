"""Software video decoding with PyAV; no external ffmpeg binary required."""
import argparse
import hashlib
import json
from pathlib import Path
import av


def extract(video, interval=1.0):
    path = Path(video)
    output = Path(__file__).resolve().parents[1] / "data/extracted" / path.stem
    output.mkdir(parents=True, exist_ok=True)
    rows, next_time = [], 0.0
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        for frame in container.decode(stream):
            if frame.time is None or frame.time + 1e-6 < next_time:
                continue
            filename = f"frame-{frame.time:08.3f}.jpg"
            frame.to_image().save(output / filename, quality=85)
            rows.append({"time": frame.time, "image": filename})
            next_time += interval
        duration = float(stream.duration * stream.time_base) if stream.duration else rows[-1]["time"]
    data = {"decoder": "PyAV", "duration": duration, "interval": interval, "frames": rows,
            "media_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (output / "frames.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(rows)} images: {path.name}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("interval doit être positif")
    for video in args.videos:
        extract(video, args.interval)
