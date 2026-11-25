"""Assemble and verify the complete faucet revision with its existing mix."""

import argparse
import json
from pathlib import Path
import subprocess

from mechanical_video_next.remotion_build import render
from revision import encode, label
from scripts.common import ROOT, filehash, run, writejson

EPISODE = "quarter-turn-faucet"
BASE = ROOT / "output" / EPISODE
WORK = ROOT / "work" / EPISODE / "structure-fix"
BASELINE = BASE / "水龙头只转一点，水为什么就停了-去标注版.mp4"
BASELINE_SHA = "0578931ea23caca04ac0d9eaff1df61a2bb4e69fa8ac9ac869699123efa6065b"
TITLE = "水龙头只转一点，水为什么就停了-阀芯结构修正版"
CLEAN = ROOT / "remotion/public/cache/faucet-remove-label"
CACHE = ROOT / "remotion/public/cache/faucet-structure-fix"
COUNTS = (150, 289, 319, 327, 264, 283, 240)


def probe(path, *args):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", *args, "-of", "json", path]))


def image_sequence(view):
    return ["-framerate", "30", "-i", WORK / "full" / view / "%05d.jpg"]


def opening():
    right = label("陶瓷片通水口", 1104, 47)
    filters = (
        "[0:v]trim=end_frame=60,setpts=PTS-STARTPTS,crop=1056:1080:0:0[left];"
        "[1:v]crop=864:1080[ports];"
        f"[left][ports]hstack,drawbox=x=1053:y=0:w=6:h=ih:color=0x142321:t=fill,{right},setsar=1[hook];"
        "[2:v]setsar=1[body];[hook][body]concat=n=2:v=1:a=0[out]"
    )
    encode(["-i", CLEAN / "0.mp4", *image_sequence("opening-ports"),
            *image_sequence("opening-body")], filters, COUNTS[0], CACHE / "0.mp4")


def end_shots():
    for index, view in enumerate(("plates", "flow", "closure", "reopen"), 2):
        encode(image_sequence(view), "[0:v]setsar=1[out]", COUNTS[index], CACHE / f"{index}.mp4")
    right = label("陶瓷片通水口", 1104, 47)
    encode(["-i", CLEAN / "6.mp4", *image_sequence("replay-ports")], (
        "[0:v]crop=1056:1080:0:0[left];[1:v]crop=864:1080[ports];"
        f"[left][ports]hstack,drawbox=x=1053:y=0:w=6:h=ih:color=0x142321:t=fill,{right},setsar=1[out]"
    ), COUNTS[6], CACHE / "6.mp4")


def composition(which):
    props = json.loads((WORK.parent / "remove-label" / "edit-props.json").read_text())
    indices = range(2, 7) if which == "end" else (0,)
    for index in indices:
        props["shots"][index]["media"] = f"cache/{CACHE.name}/{index}.mp4"
    prop_path = WORK / f"props-{which}.json"
    writejson(prop_path, props)
    output = WORK / f"composited-{which}.mp4"
    render(prop_path, output, WORK / f"remotion-{which}.log", visual=True,
           frame_range=(439, 1871) if which == "end" else (0, 149))
    # Frame zero has no subtitle. Take it straight from the rendered split
    # screen because Chromium previously returned a tiled frame at this boundary.
    filter_args = ["-vf", "setsar=1"]
    if which == "opening":
        filter_args = ["-i", CACHE / "0.mp4", "-filter_complex",
                       "[1:v]trim=end_frame=1,setpts=PTS-STARTPTS[head];"
                       "[0:v]trim=start_frame=1,setpts=PTS-STARTPTS[tail];"
                       "[head][tail]concat=n=2:v=1:a=0,setpts=N/(30*TB),setsar=1"]
    run(["ffmpeg", "-y", "-v", "error", "-xerror", "-i", output, *filter_args, "-an",
         "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-r", "30", "-pix_fmt", "yuv420p",
         "-color_range", "pc", "-colorspace", "bt470bg", "-video_track_timescale", "15360",
         WORK / f"final-{which}.mp4"])


def stream_hash(path):
    return subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-i", path, "-map", "0:a:0",
                                    "-c:a", "copy", "-f", "streamhash", "-hash", "sha256", "-"], text=True).strip()


def pixels(path, start=None, end=None):
    selection = ["-vf", f"trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS"] if end else []
    hashes = subprocess.check_output(["ffmpeg", "-v", "error", "-xerror", "-i", path, "-map", "0:v:0",
                                      *selection, "-f", "framemd5", "-"], text=True)
    return [line.split(",")[-1].strip() for line in hashes.splitlines() if not line.startswith("#")]


def verify(candidate, replacement):
    picture, audio = probe(candidate, "-show_streams")["streams"]
    assert (picture["codec_name"], picture["width"], picture["height"], picture["avg_frame_rate"],
            picture["time_base"], picture["nb_frames"], picture["start_time"], picture["duration"]) == (
                "h264", 1920, 1080, "30/1", "1/15360", "1872", "0.000000", "62.400000")
    assert (audio["codec_name"], audio["disposition"]["default"], audio["start_time"], audio["duration"]) == (
        "aac", 1, "0.000000", "62.400000")
    frames = probe(candidate, "-select_streams", "v", "-show_frames",
                   "-show_entries", "frame=best_effort_timestamp")["frames"]
    assert [frame["best_effort_timestamp"] for frame in frames] == [index * 512 for index in range(sum(COUNTS))]
    audio_packets = ("-select_streams", "a", "-show_packets",
                     "-show_entries", "packet=pts,dts,duration,size,side_data_list")
    assert probe(candidate, *audio_packets) == probe(BASELINE, *audio_packets)
    assert stream_hash(candidate) == stream_hash(BASELINE)
    assert pixels(candidate, 150, 439) == pixels(replacement) == pixels(BASELINE, 150, 439)
    run(["ffmpeg", "-v", "error", "-xerror", "-i", candidate, "-map", "0:v", "-map", "0:a", "-f", "null", "-"])
    return {
        "baseline_sha256": BASELINE_SHA,
        "final_sha256": filehash(candidate),
        "audio_sha256": stream_hash(candidate).split("=")[1],
        "matching_audio_timestamps": True,
        "matching_disassembly_frames": [150, 438],
        "video_frames": sum(COUNTS),
        "duration_seconds": 62.4,
        "full_decode": "PASS",
    }


def join():
    opening_mp4 = WORK / "final-opening.mp4"
    end = WORK / "final-end.mp4"
    replacement = WORK.parent / "thread-fix" / "replacement.mp4"
    extras = ("-select_streams", "v", "-show_entries", "stream=extradata_hash", "-show_data_hash", "sha256")
    hashes = [probe(clip, *extras)["streams"][0]["extradata_hash"] for clip in (opening_mp4, replacement, end)]
    assert len(set(hashes)) == 1, hashes
    concat = WORK / "concat.ffconcat"
    concat.write_text("ffconcat version 1.0\nfile final-opening.mp4\nduration 5.0\n"
                      "file ../thread-fix/replacement.mp4\nduration 9.633333\nfile final-end.mp4\n")
    candidate = WORK / "candidate.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-xerror", "-f", "concat", "-safe", "0", "-i", concat,
         "-i", BASELINE, "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-disposition:a:0", "default",
         "-movflags", "+faststart", candidate])
    report = verify(candidate, replacement)
    source = Path(__file__).with_name("structure_scene.py")
    report["render_source_sha256"] = filehash(source)
    report["clean_picture_sha256"] = {path.name: filehash(path) for path in sorted(CACHE.glob("*.mp4"))}
    writejson(WORK / "verification.json", report)
    output = BASE / f"{TITLE}.mp4"
    if output.exists():
        assert filehash(output) == report["final_sha256"]
    else:
        output.hardlink_to(candidate)
    for suffix in (".srt", "-配音文案.txt"):
        source = BASE / f"水龙头只转一点，水为什么就停了-机械修订版{suffix}"
        target = BASE / f"{TITLE}{suffix}"
        if not target.exists():
            source_text = source.read_text()
            target.write_text(source_text)
    print(output, report["final_sha256"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("opening", "end", "join"))
    args = parser.parse_args()
    assert filehash(BASELINE) == BASELINE_SHA
    CACHE.mkdir(parents=True, exist_ok=True)
    if args.stage == "opening":
        opening()
        composition("opening")
    elif args.stage == "end":
        end_shots()
        composition("end")
    else:
        join()


if __name__ == "__main__":
    main()
