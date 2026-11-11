#!/usr/bin/env python3
"""Label native diagnostic media without scaling; emit verifiable source receipts.

Requires Pillow. Uses cache paths only after validating complete.json hashes.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def overlay(size, labels, path):
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    font_path = "/System/Library/Fonts/STHeiti Medium.ttc"
    for index, label in enumerate(labels):
        font = ImageFont.truetype(font_path, 20 if index == 0 else 18)
        box = draw.textbbox((0, 0), label, font=font)
        width = box[2] - box[0]
        y = 10 + index * 30
        draw.rounded_rectangle((10, y, width + 30, y + 27), radius=4,
                               fill=(15, 23, 32, 230))
        draw.text((20, y + 3), label, font=font, fill="white")
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", action="append", default=[])
    parser.add_argument("--cache-root", default="work/cache/shots")
    parser.add_argument("--stage", help="Exact metrics stage when several are present")
    args = parser.parse_args()
    start = time.monotonic()
    output = pathlib.Path(args.output)
    if shutil.disk_usage(pathlib.Path.cwd()).free < 3 * 1024 ** 3:
        raise SystemExit("Free disk below 3 GiB; refusing generation")
    if output.exists():
        raise SystemExit("Refusing to overwrite existing review output")
    metrics = pathlib.Path(args.metrics)
    data = json.loads(metrics.read_text())
    if data["status"] != "passed":
        raise SystemExit("Source production metrics did not pass")
    stages = [s for s in data["stages"] if s["stage"] != "asset"]
    if args.stage:
        stages = [s for s in stages if s["stage"] == args.stage]
    if len(stages) != 1:
        raise SystemExit("Require one explicitly bound diagnostic stage")
    cache = pathlib.Path(args.cache_root) / stages[0]["key"]
    complete = json.loads((cache / "complete.json").read_text())
    for relative, expected in complete.items():
        if digest(cache / relative) != expected:
            raise SystemExit("Source cache hash mismatch: " + relative)
    sources = [cache / name for name in complete
               if pathlib.Path(name).suffix in (".mp4", ".png")]
    videos = [p for p in sources if p.suffix == ".mp4"]
    sources = videos or sources
    if not sources:
        raise SystemExit("No manifest-bound media")
    output.mkdir(parents=True)
    records = []
    for index, source in enumerate(sources):
        if source.suffix == ".png":
            original = Image.open(source).convert("RGBA")
            stamp = output / ("overlay-%d.png" % index)
            overlay(original.size, args.label, stamp)
            original.alpha_composite(Image.open(stamp))
            result = output / ("review-%d.png" % index)
            original.convert("RGB").save(result)
            details = {"width": original.width, "height": original.height}
        else:
            probe = json.loads(run(["ffprobe", "-v", "error", "-show_streams",
                                    "-show_format", "-of", "json", str(source)]))
            stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
            stamp = output / ("overlay-%d.png" % index)
            overlay((stream["width"], stream["height"]), args.label, stamp)
            result = output / ("review-%d.mp4" % index)
            run(["ffmpeg", "-v", "error", "-i", str(source), "-i", str(stamp),
                 "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
                 "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", str(result)])
            run(["ffmpeg", "-v", "error", "-xerror", "-i", str(result), "-f", "null", "-"])
            details = json.loads(run(["ffprobe", "-v", "error", "-count_frames",
                                      "-show_streams", "-show_format", "-of", "json", str(result)]))
        records.append({"source": str(source), "source_sha256": digest(source),
                        "output": str(result), "sha256": digest(result), "details": details})
    receipt = {"role": "Editor", "status": "LABELED_DIAGNOSTIC_NOT_ACCEPTED",
               "metrics": str(metrics), "metrics_sha256": digest(metrics),
               "complete_sha256": digest(cache / "complete.json"),
               "labels": args.label, "outputs": records,
               "elapsed_seconds": round(time.monotonic() - start, 3),
               "disk_free_bytes": shutil.disk_usage(output).free,
               "cache_hit": True, "tts_submissions": 0,
               "tokens": None, "cost": None, "human_interventions": None,
               "limitations": ["No continuous video or listening acceptance", "Labels only; no mechanical picture scaling or geometry edits"]}
    (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(output / "receipt.json")


if __name__ == "__main__":
    main()
